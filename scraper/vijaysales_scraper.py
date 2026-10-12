import urllib.parse

from .base_scraper import CardScraper


class VijaySalesScraper(CardScraper):
    platform_key = 'vijaysales'
    platform_name = 'Vijay Sales'
    base_url = 'https://www.vijaysales.com'
    brand_color = '#8b5cf6'

    card_selectors = [
        'div.product-box', 'div.product-item', 'li.product-item',
        'div[class*="product-card"]', 'div[class*="productBox"]',
    ]
    title_selectors = ['.product-name', '.product-title', 'h3', 'h2']
    price_selectors = ['.final-price', '.product-price', '.price']
    mrp_selectors = ['.mrp', 'del', 's']
    link_selectors = ['a[href*="/p/"]', 'a[href]']
    link_must_contain = ('/p/',)
    image_selectors = ['img']

    def build_search_url(self, query):
        return f'{self.base_url}/search/{urllib.parse.quote(query)}'