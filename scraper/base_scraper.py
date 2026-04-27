from abc import ABC, abstractmethod
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time

class BaseScraper(ABC):
    def __init__(self, platform_name, base_url, headless=True):
        self.platform_name = platform_name
        self.base_url = base_url
        self.headless = headless
        self.driver = None
    
    def _init_driver(self):
        chrome_options = Options()
        if self.headless:
            chrome_options.add_argument('--headless=new')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--disable-plugins-discovery')
        chrome_options.add_argument('--start-maximized')
        chrome_options.add_experimental_option('excludeSwitches', ['enable-automation'])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument(
            '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            ' (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
        )
        
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        self.driver.implicitly_wait(8)
    
    def _close_driver(self):
        if self.driver:
            self.driver.quit()
            self.driver = None
    
    @abstractmethod
    def search(self, query):
        pass
    
    @abstractmethod
    def extract_products(self):
        pass
    
    def scrape(self, query):
        try:
            self._init_driver()
            self.search(query)
            time.sleep(2)
            products = self.extract_products()
            return products
        except Exception as e:
            print(f"Error scraping {self.platform_name}: {str(e)}")
            return []
        finally:
            self._close_driver()
