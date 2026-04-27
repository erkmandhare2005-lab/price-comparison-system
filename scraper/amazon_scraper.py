import time
import urllib.parse
import re
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

class AmazonScraper:
    def __init__(self, headless=True):
        self.platform_name = 'Amazon'
        self.base_url = 'https://www.amazon.in'
        self.headless = headless
        self.driver = self._init_driver()
    
    def _init_driver(self):
        chrome_options = Options()
        if self.headless:
            chrome_options.add_argument('--headless=new')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option('excludeSwitches', ['enable-automation'])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36')
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        driver.implicitly_wait(8)
        return driver
    
    def scrape(self, query, max_results=5):
        try:
            search_url = f"{self.base_url}/s?k={urllib.parse.quote(query)}"
            print(f"Navigating to: {search_url}")
            self.driver.get(search_url)
            time.sleep(4)
            
            products = []
            items = self.driver.find_elements(By.CSS_SELECTOR, '[data-component-type="s-search-result"]')
            print(f"Found {len(items)} items")
            
            organic_items = []
            for item in items:
                if not item.get_attribute('data-sponsored'):
                    organic_items.append(item)
                if len(organic_items) >= max_results * 2:
                    break
            
            print(f"Organic items: {len(organic_items)}")
            
            for item in organic_items[:max_results]:
                try:
                    full_text = item.text.strip()
                    lines = [l.strip() for l in full_text.split('\n') if l.strip()]
                    # Skip short lines and metadata
                    title_lines = [l for l in lines if len(l) > 3 and not l.startswith(('₹', '₹', 'M.R.P', 'FREE', 'Up to', 'Only', 'Upto'))]
                    title = ' '.join(title_lines[:2]) if title_lines else ''  # Brand + product name
                    
                    if not title or len(title) < 5 or 'Sponsored' in title:
                        continue
                except:
                    continue
                
                price = None
                try:
                    price_offscreen = item.find_element(By.CSS_SELECTOR, '.a-price .a-offscreen')
                    price_text = price_offscreen.text or price_offscreen.get_attribute('textContent') or ''
                    price_text = price_text.replace('₹', '').replace(',', '').strip()
                    if price_text:
                        price = float(price_text)
                except:
                    pass
                
                link = ''
                try:
                    links = item.find_elements(By.CSS_SELECTOR, 'a[href]')
                    for link_elem in links:
                        href = link_elem.get_attribute('href') or ''
                        if '/dp/' in href:
                            match = re.search(r'(/dp/[A-Z0-9]+)', href)
                            if match:
                                link = self.base_url + match.group(1)
                                break
                except:
                    pass
                if not link:
                    link = f"{self.base_url}/s?k={urllib.parse.quote(query)}"
                
                image_url = ''
                try:
                    img_elem = item.find_element(By.CSS_SELECTOR, '.s-image')
                    image_url = img_elem.get_attribute('src') or ''
                except:
                    pass
                
                if title and price:
                    print(f"✓ {title[:60]} ₹{int(price)}")
                    products.append({
                        'name': title,
                        'price': price,
                        'currency': 'INR',
                        'url': link,
                        'image_url': image_url,
                        'platform': self.platform_name
                    })
            
            print(f"Extracted {len(products)} products\n")
            return products
        except Exception as e:
            print(f"Amazon scrape error: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def close(self):
        try:
            self.driver.quit()
        except:
            pass
