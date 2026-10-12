import re
import urllib.parse

from selenium.webdriver.common.by import By

from .base_scraper import CardScraper


class AmazonScraper(CardScraper):
    platform_key = 'amazon'
    platform_name = 'Amazon'
    base_url = 'https://www.amazon.in'
    brand_color = '#ff9900'

    card_selectors = ['[data-component-type="s-search-result"]']
    title_selectors = ['h2 span', 'h2']
    price_selectors = ['.a-price:not(.a-text-price) .a-offscreen', '.a-price .a-offscreen']
    mrp_selectors = ['.a-price.a-text-price .a-offscreen']
    rating_selectors = ['span.a-icon-alt', '[aria-label*="out of 5 stars"]']
    link_selectors = ['h2 a', 'a.a-link-normal[href*="/dp/"]', 'a[href*="/dp/"]']
    image_selectors = ['img.s-image']
    link_must_contain = ('/dp/', '/gp/product/')

    def build_search_url(self, query):
        return f'{self.base_url}/s?k={urllib.parse.quote_plus(query)}'

    def skip_card(self, card):
        if not (card.get_attribute('data-asin') or '').strip():
            return True
        if card.get_attribute('data-sponsored'):
            return True
        sponsored = card.find_elements(
            By.CSS_SELECTOR, '.puis-sponsored-label-text, [aria-label*="Sponsored" i]'
        )
        return bool(sponsored)

    def clean_link(self, href):
        match = re.search(r'/(?:dp|gp/product)/([A-Z0-9]{10})', href)
        if match:
            return f'{self.base_url}/dp/{match.group(1)}'
        return super().clean_link(href)