import urllib.parse

from .base_scraper import CardScraper


class RelianceDigitalScraper(CardScraper):
    platform_key = 'reliancedigital'
    platform_name = 'Reliance Digital'
    base_url = 'https://www.reliancedigital.in'
    brand_color = '#e11d48'

    card_selectors = ['li.sp.grid', 'div.sp.grid', 'div[class*="product-card"]', 'li[class*="product"]']
    title_selectors = ['.sp__name', 'p.sp__name', 'h3', 'h2']
    link_selectors = ['a[href*="/product/"]', 'a[href]']
    link_must_contain = ('/product/',)
    image_selectors = ['img']
    # Price classes on this site are build-hash names, so prices come from the
    # text fallback (first ₹ amount = price, next higher amount = MRP).

    def build_search_url(self, query):
        return f'{self.base_url}/products?q={urllib.parse.quote(query)}&page=1'