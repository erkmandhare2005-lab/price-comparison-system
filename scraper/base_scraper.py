
"""Shared scraping infrastructure.

BaseScraper  - owns the Chrome driver lifecycle, waiting, scrolling, block detection.
CardScraper  - a configurable scraper: subclasses only list CSS selectors for the
               product cards and the fields inside them. If a selector misses, the
               parser falls back to reading the card's visible text (price lines
               starting with the rupee sign, first sensible line as the title).
"""
import logging
import os
import re
import threading
import time
import urllib.parse
from abc import ABC, abstractmethod

from selenium import webdriver
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

try:
    from webdriver_manager.chrome import ChromeDriverManager
except Exception:  # webdriver-manager is optional; Selenium Manager can take over
    ChromeDriverManager = None

logger = logging.getLogger(__name__)

PRICE_RE = re.compile(r'(?:₹|Rs\.?|INR)\s*([\d,]+(?:\.\d{1,2})?)', re.IGNORECASE)
NUMBER_RE = re.compile(r'\d[\d,]*(?:\.\d{1,2})?')
RATING_RE = re.compile(r'(?<![\d.])([0-5](?:\.\d)?)(?![\d.])')

USER_AGENT = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
)

SKIP_EXACT = {'ad', 'sponsored', 'bestseller', 'assured', 'new', 'hot', 'trending', 'featured'}
SKIP_PREFIXES = (
    'add to', 'm.r.p', 'free delivery', 'up to', 'upto', 'only ', 'save ',
    'limited time', 'get it by', 'shop now', 'coupon', 'bank offer', 'no cost emi',
)
BLOCK_MARKERS = ('captcha', 'robot check', 'access denied', 'unusual traffic', 'are you a human')

_DRIVER_PATH = None
_DRIVER_LOCK = threading.Lock()


def get_driver_path():
    """Download/locate chromedriver once, even when scrapers start in parallel."""
    global _DRIVER_PATH
    with _DRIVER_LOCK:
        if _DRIVER_PATH is None and ChromeDriverManager is not None:
            try:
                _DRIVER_PATH = ChromeDriverManager().install()
            except Exception as exc:
                logger.warning('webdriver-manager failed (%s); falling back to Selenium Manager', exc)
                _DRIVER_PATH = ''
        return _DRIVER_PATH or None


class ScraperBlocked(RuntimeError):
    """Raised when the store served an anti-bot / captcha page instead of results."""


class BaseScraper(ABC):
    platform_key = ''
    platform_name = ''
    base_url = ''
    brand_color = '#6366f1'          # 6-digit hex, used by the UI

    wait_timeout = 12                # seconds to wait for result cards
    settle_seconds = 1.5             # extra pause so lazy content can render
    scroll_steps = 4                 # scroll passes to trigger lazy-loaded images
    page_load_timeout = 35
    result_selector = ''             # CSS selector (comma list ok) to wait for

    def __init__(self, headless=True, max_results=8):
        self.headless = headless
        self.max_results = max_results
        self.driver = None

    # ---- driver lifecycle -------------------------------------------------
    def _init_driver(self):
        opts = Options()
        if self.headless:
            opts.add_argument('--headless=new')
        opts.add_argument('--no-sandbox')
        opts.add_argument('--disable-dev-shm-usage')
        opts.add_argument('--disable-gpu')
        opts.add_argument('--window-size=1920,1080')
        opts.add_argument('--lang=en-IN')
        opts.add_argument('--disable-extensions')
        opts.add_argument('--disable-blink-features=AutomationControlled')
        opts.add_argument(f'--user-agent={USER_AGENT}')
        opts.add_experimental_option('excludeSwitches', ['enable-automation'])
        opts.add_experimental_option('useAutomationExtension', False)
        opts.page_load_strategy = 'eager'   # don't wait for every tracker/ad to load

        chrome_bin = os.environ.get("CHROME_BIN")
        if chrome_bin:
            opts.binary_location = chrome_bin

        driver_path = (
            os.environ.get("CHROMEDRIVER_PATH")
            or get_driver_path()
        )
        service = Service(driver_path) if driver_path else Service()
        self.driver = webdriver.Chrome(service=service, options=opts)
        self.driver.set_page_load_timeout(self.page_load_timeout)
        # Explicit waits are used instead of implicit ones: an implicit wait makes
        # every missed find_elements() call block, which multiplies scrape time.
        self.driver.implicitly_wait(0)
        try:
            self.driver.execute_cdp_cmd(
                'Page.addScriptToEvaluateOnNewDocument',
                {'source': "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"},
            )
        except Exception:
            pass

    def close(self):
        if self.driver is not None:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None

    # ---- to implement -----------------------------------------------------
    @abstractmethod
    def build_search_url(self, query):
        """Return the store's search URL for the query."""

    @abstractmethod
    def extract_products(self, query):
        """Return a list of product dicts from the loaded page."""

    # ---- public entry point ----------------------------------------------
    def scrape(self, query):
        try:
            self._init_driver()
            url = self.build_search_url(query)
            logger.info('[%s] opening %s', self.platform_name, url)
            try:
                self.driver.get(url)
            except TimeoutException:
                logger.warning('[%s] page load timed out, using what has rendered', self.platform_name)
                try:
                    self.driver.execute_script('window.stop()')
                except Exception:
                    pass
            self.wait_for_results()
            self.scroll_page()
            products = self.extract_products(query)
            logger.info('[%s] extracted %d products', self.platform_name, len(products))
            if not products:
                self.raise_if_blocked()
            return products[: self.max_results]
        finally:
            self.close()

    # ---- helpers ----------------------------------------------------------
    def wait_for_results(self):
        if self.result_selector:
            try:
                WebDriverWait(self.driver, self.wait_timeout).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, self.result_selector))
                )
            except TimeoutException:
                logger.info('[%s] result selector never appeared', self.platform_name)
        time.sleep(self.settle_seconds)

    def scroll_page(self):
        try:
            for _ in range(self.scroll_steps):
                self.driver.execute_script('window.scrollBy(0, Math.round(window.innerHeight * 0.8));')
                time.sleep(0.4)
            self.driver.execute_script('window.scrollTo(0, 0);')
        except Exception:
            pass

    def raise_if_blocked(self):
        try:
            title = (self.driver.title or '').lower()
            body = (self.driver.find_element(By.TAG_NAME, 'body').text or '').lower()[:3000]
        except Exception:
            return
        sample = f'{title} {body}'
        if any(marker in sample for marker in BLOCK_MARKERS):
            raise ScraperBlocked(f'{self.platform_name} showed an anti-bot check. Try again later.')

    @staticmethod
    def text_of(element):
        try:
            return (element.text or element.get_attribute('textContent') or '').strip()
        except StaleElementReferenceException:
            return ''

    @staticmethod
    def parse_price(text):
        if not text:
            return None
        match = PRICE_RE.search(text)
        raw = match.group(1) if match else None
        if raw is None:
            number = NUMBER_RE.search(text)
            raw = number.group(0) if number else None
        try:
            return float(raw.replace(',', '')) if raw else None
        except ValueError:
            return None

    @staticmethod
    def parse_all_prices(text):
        values = []
        for raw in PRICE_RE.findall(text or ''):
            try:
                values.append(float(raw.replace(',', '')))
            except ValueError:
                continue
        return values

    @staticmethod
    def parse_rating(text):
        if not text:
            return None
        match = RATING_RE.search(text)
        if not match:
            return None
        value = float(match.group(1))
        return value if 0 < value <= 5 else None

    def make_product(self, name, price, url, image_url='', mrp=None, rating=None):
        name = re.sub(r'\s+', ' ', name or '').strip()[:200]
        if len(name) < 4 or not price or price <= 0:
            return None
        if mrp is not None and mrp <= price:
            mrp = None
        discount = round((mrp - price) / mrp * 100) if mrp else None
        return {
            'name': name,
            'price': float(price),
            'mrp': float(mrp) if mrp else None,
            'discount_pct': discount,
            'rating': rating,
            'currency': 'INR',
            'url': url,
            'image_url': image_url or '',
            'platform': self.platform_name,
            'platform_key': self.platform_key,
            'brand_color': self.brand_color,
        }


class CardScraper(BaseScraper):
    """Selector-driven scraper. Subclasses set the class attributes below."""

    card_selectors = []      # tried in order; first one that matches wins
    title_selectors = []
    price_selectors = []
    mrp_selectors = []
    rating_selectors = []
    link_selectors = []
    image_selectors = []
    link_must_contain = ()   # prefer anchors whose href contains one of these

    @property
    def result_selector(self):  # type: ignore[override]
        return ', '.join(self.card_selectors)

    # ---- card discovery ---------------------------------------------------
    def find_cards(self):
        for selector in self.card_selectors:
            try:
                cards = self.driver.find_elements(By.CSS_SELECTOR, selector)
            except Exception:
                continue
            if cards:
                logger.info('[%s] %d cards via %r', self.platform_name, len(cards), selector)
                return cards
        return []

    def skip_card(self, card):
        return False

    def extract_products(self, query):
        products, seen = [], set()
        for card in self.find_cards():
            if len(products) >= self.max_results:
                break
            try:
                if self.skip_card(card):
                    continue
                product = self.parse_card(card, query)
            except StaleElementReferenceException:
                continue
            except Exception as exc:
                logger.debug('[%s] card skipped: %s', self.platform_name, exc)
                continue
            if not product:
                continue
            key = product['url'] or product['name']
            if key in seen:
                continue
            seen.add(key)
            products.append(product)
        return products

    # ---- card parsing -----------------------------------------------------
    def parse_card(self, card, query):
        text = self.text_of(card)
        lines = [line.strip() for line in text.split('\n') if line.strip()]

        name = self.pick_text(card, self.title_selectors) or self.guess_title(lines)

        price = None
        price_text = self.pick_text(card, self.price_selectors)
        if price_text:
            price = self.parse_price(price_text)
        mrp = None
        mrp_text = self.pick_text(card, self.mrp_selectors)
        if mrp_text:
            mrp = self.parse_price(mrp_text)

        if price is None:
            prices = self.parse_all_prices(text)
            if prices:
                price = prices[0]
                if mrp is None:
                    mrp = next((p for p in prices[1:] if price < p <= price * 5), None)

        rating = self.parse_rating(self.pick_text(card, self.rating_selectors))
        if rating is None:
            for line in lines:
                if re.fullmatch(r'[1-5]\.\d', line):
                    rating = float(line)
                    break

        url = self.pick_link(card, query)
        image = self.pick_image(card)
        return self.make_product(name, price, url, image, mrp=mrp, rating=rating)

    def pick_text(self, card, selectors):
        for selector in selectors or ():
            try:
                elements = card.find_elements(By.CSS_SELECTOR, selector)
            except Exception:
                continue
            for element in elements:
                value = self.text_of(element)
                if value:
                    return value
        return ''

    def guess_title(self, lines):
        for line in lines:
            low = line.lower()
            if len(line) < 8 or low in SKIP_EXACT or low.startswith(SKIP_PREFIXES):
                continue
            if PRICE_RE.search(line) or re.fullmatch(r'[\d.,()%\s]+', line):
                continue
            if re.search(r'\d+\s*%\s*off', low):
                continue
            return line
        return ''

    def clean_link(self, href):
        return urllib.parse.urljoin(self.base_url, href)

    def pick_link(self, card, query):
        candidates = []
        for selector in (self.link_selectors or ['a[href]']):
            try:
                elements = card.find_elements(By.CSS_SELECTOR, selector)
            except Exception:
                continue
            for element in elements:
                href = (element.get_attribute('href') or '').strip()
                if href and not href.startswith(('javascript:', '#')):
                    candidates.append(href)
        if self.link_must_contain:
            for href in candidates:
                if any(token in href for token in self.link_must_contain):
                    return self.clean_link(href)
        if candidates:
            return self.clean_link(candidates[0])
        return self.build_search_url(query)

    def pick_image(self, card):
        for selector in (self.image_selectors or ['img']):
            try:
                elements = card.find_elements(By.CSS_SELECTOR, selector)
            except Exception:
                continue
            for element in elements:
                for attr in ('src', 'data-src', 'data-lazy-src', 'data-original'):
                    value = (element.get_attribute(attr) or '').strip()
                    if value and not value.startswith('data:'):
                        return urllib.parse.urljoin(self.base_url, value)
                srcset = (element.get_attribute('srcset') or '').strip()
                if srcset:
                    first = srcset.split(',')[0].strip().split(' ')[0]
                    if first and not first.startswith('data:'):
                        return urllib.parse.urljoin(self.base_url, first)
        return ''