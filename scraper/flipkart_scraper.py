import urllib.parse

from .base_scraper import CardScraper


class FlipkartScraper(CardScraper):
    """Flipkart uses obfuscated class names, so this relies on the stable
    `data-id` attribute plus the text-based fallbacks in CardScraper
    (first title-like line, first rupee amount = price, second = MRP)."""

    platform_key = 'flipkart'
    platform_name = 'Flipkart'
    base_url = 'https://www.flipkart.com'
    brand_color = '#047bd5'

    card_selectors = ['div[data-id]', '[data-id]']
    link_selectors = ['a[href*="/p/"]', 'a[href]']
    link_must_contain = ('/p/',)
    image_selectors = ['img']

    def build_search_url(self, query):
        return f'{self.base_url}/search?q={urllib.parse.quote_plus(query)}'

    def clean_link(self, href):
        # Drop tracking parameters; the path alone identifies the product.
        return super().clean_link(href).split('?')[0]