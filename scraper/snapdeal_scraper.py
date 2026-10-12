import urllib.parse

from .base_scraper import CardScraper


class SnapdealScraper(CardScraper):
    platform_key = 'snapdeal'
    platform_name = 'Snapdeal'
    base_url = 'https://www.snapdeal.com'
    brand_color = '#e40046'

    card_selectors = ['div.product-tuple-listing', '.product-tuple-listing']
    title_selectors = ['p.product-title', '.product-title']
    price_selectors = ['span.product-price', '.lfloat.product-price', '.product-price']
    mrp_selectors = ['span.product-desc-price', '.lfloat.product-desc-price', '.product-desc-price']
    link_selectors = ['a.dp-widget-link', 'a[href*="/product/"]', 'a[href]']
    link_must_contain = ('/product/',)
    image_selectors = ['img.product-image', 'img']

    def build_search_url(self, query):
        return f'{self.base_url}/search?keyword={urllib.parse.quote_plus(query)}&sort=rlvncy'

    def clean_link(self, href):
        return super().clean_link(href).split('#')[0]