import urllib.parse

from .base_scraper import CardScraper


class CromaScraper(CardScraper):
    platform_key = 'croma'
    platform_name = 'Croma'
    base_url = 'https://www.croma.com'
    brand_color = '#14b8a6'

    card_selectors = ['li.product-item', 'div.product-item', 'li[class*="product-item"]']
    title_selectors = ['h3.product-title', 'h3 a', 'h3']
    price_selectors = ['span.amount', '.new-price', '[data-testid="new-price"]']
    mrp_selectors = ['.old-price', 'span.old-price', '[data-testid="old-price"]']
    link_selectors = ['h3 a', 'a[href*="/p/"]', 'a[href]']
    link_must_contain = ('/p/',)
    image_selectors = ['img']

    def build_search_url(self, query):
        q = urllib.parse.quote(query)
        return f'{self.base_url}/searchB?q={q}%3Arelevance&text={q}'