import time
import urllib.parse
import re
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

class FlipkartScraper:
    def __init__(self, headless=True):
        self.platform_name = 'Flipkart'
        self.base_url = 'https://www.flipkart.com'
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
            search_url = f"{self.base_url}/search?q={urllib.parse.quote(query)}"
            print(f"Navigating to: {search_url}")
            self.driver.get(search_url)
            time.sleep(4)
            
            products = []
            items = self.driver.find_elements(By.CSS_SELECTOR, '[data-id]')
            print(f"Found {len(items)} items")
            
            for item in items[:max_results]:
                try:
                    full_text = item.text.strip()
                    lines = [l.strip() for l in full_text.split('\n') if l.strip()]
                    # Skip "Bestseller", "Add to Compare" - get actual product name
                    title_lines = [l for l in lines if l and not l.startswith(('Bestseller', 'Add to', 'Sponsored'))]
                    title = title_lines[0] if title_lines else ''
                    if not title or len(title) < 5:
                        continue
                except:
                    continue
                
                price = None
                try:
                    # Find price from text (lines starting with ₹)
                    for line in lines:
                        if line.startswith('₹'):
                            price_text = line.replace('₹', '').replace(',', '').strip()
                            if price_text and price_text[0].isdigit():
                                price = float(price_text)
                                break
                except:
                    pass
                
                link = ''
                try:
                    link_elems = item.find_elements(By.CSS_SELECTOR, 'a[href]')
                    for link_elem in link_elems:
                        href = link_elem.get_attribute('href') or ''
                        if href and ('/p/' in href or href.startswith('/')):
                            if href.startswith('/'):
                                link = self.base_url + href.split('?')[0]
                            else:
                                link = href.split('?')[0]
                            break
                except:
                    pass
                if not link:
                    link = f"{self.base_url}/search?q={urllib.parse.quote(query)}"
                
                image_url = ''
                try:
                    img_elem = item.find_element(By.CSS_SELECTOR, 'img')
                    image_url = img_elem.get_attribute('src') or img_elem.get_attribute('data-src') or ''
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
            print(f"Flipkart scrape error: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def close(self):
        try:
            self.driver.quit()
        except:
            pass
