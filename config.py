import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def _env_bool(name, default):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ('1', 'true', 'yes', 'on')


class Config:
    # Flask
    SECRET_KEY = os.environ.get('SECRET_KEY', 'change-me-in-production')
    DEBUG = _env_bool('FLASK_DEBUG', False)
    HOST = os.environ.get('HOST', '127.0.0.1')
    PORT = int(os.environ.get('PORT', 5000))

    # Scraping
    HEADLESS = _env_bool('HEADLESS', True)
    MAX_RESULTS_PER_PLATFORM = int(os.environ.get('MAX_RESULTS_PER_PLATFORM', 4))
    MAX_PARALLEL_BROWSERS = int(os.environ.get('MAX_PARALLEL_BROWSERS', 1))
    PAGE_LOAD_TIMEOUT = int(os.environ.get('PAGE_LOAD_TIMEOUT', 20))

    # Which stores are active (keys from scraper/__init__.py -> SCRAPERS)
    ENABLED_SCRAPERS = [
        'amazon',
        'flipkart',
        'croma',
        'reliancedigital',
        'snapdeal',
        'vijaysales',
    ]

    # Caching / limits
    CACHE_TTL_SECONDS = int(os.environ.get('CACHE_TTL_SECONDS', 600))
    RATE_LIMIT_PER_MIN = int(os.environ.get('RATE_LIMIT_PER_MIN', 8))
    MAX_QUERY_LENGTH = 100

    # Storage (price history + search log)
    DATABASE_PATH = os.environ.get('DATABASE_PATH', os.path.join(BASE_DIR, 'price_history.db'))
