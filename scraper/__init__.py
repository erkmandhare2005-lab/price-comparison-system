from .base_scraper import BaseScraper, CardScraper, ScraperBlocked
from .amazon_scraper import AmazonScraper
from .flipkart_scraper import FlipkartScraper
from .croma_scraper import CromaScraper
from .reliance_scraper import RelianceDigitalScraper
from .snapdeal_scraper import SnapdealScraper
from .vijaysales_scraper import VijaySalesScraper

# Registry: platform_key -> scraper class. To add a store, create a new
# CardScraper subclass (see croma_scraper.py) and add it here and in
# Config.ENABLED_SCRAPERS.
SCRAPERS = {
    cls.platform_key: cls
    for cls in (
        AmazonScraper,
        FlipkartScraper,
        CromaScraper,
        RelianceDigitalScraper,
        SnapdealScraper,
        VijaySalesScraper,
    )
}

__all__ = [
    'BaseScraper', 'CardScraper', 'ScraperBlocked', 'SCRAPERS',
    'AmazonScraper', 'FlipkartScraper', 'CromaScraper',
    'RelianceDigitalScraper', 'SnapdealScraper', 'VijaySalesScraper',
]