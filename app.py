import copy
import csv
import io
import logging
import re
import sqlite3
import threading
import time
import uuid
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager

from flask import Flask, Response, jsonify, redirect, render_template, request, url_for

from config import Config
from scraper import SCRAPERS

app = Flask(__name__)
app.config.from_object(Config)

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
log = logging.getLogger('pricecompare')

# --------------------------------------------------------------------------
# In-memory state
# --------------------------------------------------------------------------
JOBS = {}
JOBS_LOCK = threading.Lock()
CACHE = {}                      # (normalized query, platforms) -> {'ts', 'results', 'platforms'}
RATE = defaultdict(list)        # ip -> [timestamps]
EXECUTOR = ThreadPoolExecutor(max_workers=Config.MAX_PARALLEL_BROWSERS, thread_name_prefix='scraper')

DEFAULT_TRENDING = [
    'iPhone 15', 'Samsung Galaxy S24', 'MacBook Air M2',
    'Sony WH-1000XM5', 'boAt Airdopes', 'Noise ColorFit',
]


# --------------------------------------------------------------------------
# Database (search log + price history)
# --------------------------------------------------------------------------
@contextmanager
def get_db():
    conn = sqlite3.connect(Config.DATABASE_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS search_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query TEXT NOT NULL,
                result_count INTEGER NOT NULL DEFAULT 0,
                ts TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query TEXT NOT NULL,
                platform_key TEXT NOT NULL,
                name TEXT NOT NULL,
                price REAL NOT NULL,
                url TEXT,
                ts TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_history_query ON price_history(query, ts);
            CREATE INDEX IF NOT EXISTS idx_search_query ON search_log(query, ts);
            """
        )


def normalize_query(query):
    return ' '.join(query.lower().split())


def log_search(query, count):
    with get_db() as conn:
        conn.execute(
            'INSERT INTO search_log (query, result_count) VALUES (?, ?)',
            (normalize_query(query), count),
        )


def save_prices(query, items):
    norm = normalize_query(query)
    with get_db() as conn:
        conn.executemany(
            'INSERT INTO price_history (query, platform_key, name, price, url) VALUES (?, ?, ?, ?, ?)',
            [(norm, it['platform_key'], it['name'], it['price'], it.get('url')) for it in items],
        )


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def enabled_platforms():
    return [key for key in Config.ENABLED_SCRAPERS if key in SCRAPERS]


def platform_meta():
    return [
        {'key': key, 'name': SCRAPERS[key].platform_name, 'color': SCRAPERS[key].brand_color}
        for key in enabled_platforms()
    ]


def clean_query(raw):
    text = re.sub(r'[\x00-\x1f\x7f]', ' ', raw or '')
    return ' '.join(text.split())[: Config.MAX_QUERY_LENGTH]


def relevance(query, name):
    tokens = [t for t in re.findall(r'[a-z0-9]+', query.lower()) if t]
    if not tokens:
        return 1.0
    lowered = name.lower()
    return round(sum(1 for t in tokens if t in lowered) / len(tokens), 2)


def short_error(exc):
    first_line = (str(exc).strip().splitlines() or [exc.__class__.__name__])[0]
    return first_line[:160] or exc.__class__.__name__


def rate_limited(ip):
    now = time.time()
    RATE[ip] = [t for t in RATE[ip] if now - t < 60]
    if len(RATE[ip]) >= Config.RATE_LIMIT_PER_MIN:
        return True
    RATE[ip].append(now)
    return False


def purge_old_jobs():
    cutoff = time.time() - 1800
    with JOBS_LOCK:
        for job_id in [j for j, job in JOBS.items() if job['created'] < cutoff]:
            del JOBS[job_id]


def csv_safe(value):
    text = '' if value is None else str(value)
    return "'" + text if text[:1] in ('=', '+', '-', '@') else text


# --------------------------------------------------------------------------
# Search jobs
# --------------------------------------------------------------------------
def run_scraper(job_id, key):
    job = JOBS.get(job_id)
    if not job:
        return
    with JOBS_LOCK:
        job['platforms'][key]['status'] = 'running'

    started = time.time()
    items, error = [], None
    try:
        scraper = SCRAPERS[key](
            headless=Config.HEADLESS,
            max_results=Config.MAX_RESULTS_PER_PLATFORM,
        )
        scraper.page_load_timeout = Config.PAGE_LOAD_TIMEOUT
        items = scraper.scrape(job['query'])
        for item in items:
            item['relevance'] = relevance(job['query'], item['name'])
    except Exception as exc:  # report per-store failures without failing the whole search
        log.warning('[%s] failed: %s', key, short_error(exc))
        error = short_error(exc)

    if items:
        try:
            save_prices(job['query'], items)
        except Exception:
            log.exception('could not save price history')

    with JOBS_LOCK:
        state = job['platforms'][key]
        state.update(
            status='error' if error else 'done',
            count=len(items),
            error=error,
            elapsed=round(time.time() - started, 1),
        )
        job['results'].extend(items)
        job['finished'] += 1
        all_done = job['finished'] >= job['total']
        if all_done:
            job['results'].sort(key=lambda r: r['price'])
            job['status'] = 'done'
            job['finished_at'] = time.time()

    if all_done:
        finalize_job(job)


def finalize_job(job):
    count = len(job['results'])
    if count:
        CACHE[job['cache_key']] = {
            'ts': time.time(),
            'results': copy.deepcopy(job['results']),
            'platforms': copy.deepcopy(job['platforms']),
        }
    try:
        log_search(job['query'], count)
    except Exception:
        log.exception('could not log search')


def create_job(query, keys, refresh=False):
    purge_old_jobs()
    cache_key = (normalize_query(query), tuple(sorted(keys)))
    job_id = uuid.uuid4().hex[:12]
    cached = None if refresh else CACHE.get(cache_key)

    if cached and time.time() - cached['ts'] < Config.CACHE_TTL_SECONDS:
        job = {
            'id': job_id, 'query': query, 'created': time.time(), 'status': 'done',
            'cached': True, 'cached_at': cached['ts'], 'cache_key': cache_key,
            'platforms': copy.deepcopy(cached['platforms']),
            'results': copy.deepcopy(cached['results']),
            'finished': len(keys), 'total': len(keys),
        }
        with JOBS_LOCK:
            JOBS[job_id] = job
        return job

    job = {
        'id': job_id, 'query': query, 'created': time.time(), 'status': 'running',
        'cached': False, 'cached_at': None, 'cache_key': cache_key,
        'platforms': {
            key: {
                'name': SCRAPERS[key].platform_name,
                'color': SCRAPERS[key].brand_color,
                'status': 'pending', 'count': 0, 'error': None, 'elapsed': None,
            }
            for key in keys
        },
        'results': [], 'finished': 0, 'total': len(keys),
    }
    with JOBS_LOCK:
        JOBS[job_id] = job
    for key in keys:
        EXECUTOR.submit(run_scraper, job_id, key)
    return job


def job_payload(job):
    with JOBS_LOCK:
        results = sorted(job['results'], key=lambda r: r['price'])
        return {
            'job_id': job['id'],
            'query': job['query'],
            'status': job['status'],
            'cached': job['cached'],
            'cached_age': int(time.time() - job['cached_at']) if job['cached_at'] else 0,
            'elapsed': round(time.time() - job['created'], 1),
            'finished': job['finished'],
            'total': job['total'],
            'platforms': copy.deepcopy(job['platforms']),
            'results': results,
            'count': len(results),
        }


# --------------------------------------------------------------------------
# Pages
# --------------------------------------------------------------------------
@app.context_processor
def inject_globals():
    return {'platform_list': platform_meta()}


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/results')
def results():
    query = clean_query(request.args.get('q', ''))
    if not query:
        return redirect(url_for('index'))
    return render_template('results.html', query=query)


# --------------------------------------------------------------------------
# API
# --------------------------------------------------------------------------
@app.route('/api/search', methods=['POST'])
def api_search():
    payload = request.get_json(silent=True) or {}
    query = clean_query(payload.get('query', ''))
    if len(query) < 2:
        return jsonify({'error': 'Please enter at least 2 characters.'}), 400

    if rate_limited(request.remote_addr or 'unknown'):
        return jsonify({'error': 'Too many searches. Please wait a minute and try again.'}), 429

    requested = payload.get('platforms')
    keys = enabled_platforms()
    if isinstance(requested, list) and requested:
        keys = [k for k in keys if k in requested] or keys

    job = create_job(query, keys, refresh=bool(payload.get('refresh')))
    return jsonify({'job_id': job['id'], 'status': job['status'], 'cached': job['cached']})


@app.route('/api/search/<job_id>')
def api_search_status(job_id):
    job = JOBS.get(job_id)
    if not job:
        return jsonify({'error': 'Search not found or expired.'}), 404
    return jsonify(job_payload(job))


@app.route('/api/export/<job_id>.csv')
def api_export(job_id):
    job = JOBS.get(job_id)
    if not job:
        return jsonify({'error': 'Search not found or expired.'}), 404
    payload = job_payload(job)

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(['Store', 'Product', 'Price (INR)', 'MRP (INR)', 'Discount %', 'Rating', 'URL'])
    for item in payload['results']:
        writer.writerow([
            csv_safe(item['platform']), csv_safe(item['name']), item['price'],
            item['mrp'] or '', item['discount_pct'] or '', item['rating'] or '',
            csv_safe(item['url']),
        ])
    filename = re.sub(r'[^a-z0-9]+', '-', normalize_query(job['query'])).strip('-') or 'results'
    return Response(
        buffer.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=pricecompare-{filename}.csv'},
    )


@app.route('/api/history')
def api_history():
    query = normalize_query(clean_query(request.args.get('q', '')))
    if not query:
        return jsonify({'query': '', 'series': {}})

    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT platform_key,
                   strftime('%Y-%m-%d %H:%M', ts) AS run,
                   MIN(price) AS min_price,
                   ROUND(AVG(price), 2) AS avg_price
            FROM price_history
            WHERE query = ? AND ts >= datetime('now', '-90 days')
            GROUP BY platform_key, run
            ORDER BY run
            """,
            (query,),
        ).fetchall()

    series = {}
    for row in rows:
        key = row['platform_key']
        if key not in SCRAPERS:
            continue
        entry = series.setdefault(key, {
            'name': SCRAPERS[key].platform_name,
            'color': SCRAPERS[key].brand_color,
            'points': [],
        })
        entry['points'].append({'t': row['run'], 'min': row['min_price'], 'avg': row['avg_price']})
    for entry in series.values():
        entry['points'] = entry['points'][-30:]
    return jsonify({'query': query, 'series': series})


@app.route('/api/trending')
def api_trending():
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT query, COUNT(*) AS c
            FROM search_log
            WHERE result_count > 0 AND ts >= datetime('now', '-30 days')
            GROUP BY query
            ORDER BY c DESC, MAX(ts) DESC
            LIMIT 8
            """
        ).fetchall()
    terms = [row['query'] for row in rows] or DEFAULT_TRENDING
    return jsonify({'terms': terms, 'is_default': not rows})


@app.route('/api/suggest')
def api_suggest():
    prefix = clean_query(request.args.get('q', '')).lower()
    if len(prefix) < 2:
        return jsonify({'suggestions': []})
    escaped = prefix.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT query FROM search_log
            WHERE query LIKE ? ESCAPE '\\' AND result_count > 0
            GROUP BY query ORDER BY MAX(ts) DESC LIMIT 6
            """,
            (f'%{escaped}%',),
        ).fetchall()
    suggestions = [row['query'] for row in rows]
    if len(suggestions) < 4:
        suggestions += [t for t in DEFAULT_TRENDING if prefix in t.lower() and t.lower() not in suggestions]
    return jsonify({'suggestions': suggestions[:6]})


@app.route('/api/stats')
def api_stats():
    with get_db() as conn:
        searches = conn.execute('SELECT COUNT(*) FROM search_log').fetchone()[0]
        prices = conn.execute('SELECT COUNT(*) FROM price_history').fetchone()[0]
    return jsonify({'searches': searches, 'prices': prices, 'stores': len(enabled_platforms())})


@app.route('/api/platforms')
def api_platforms():
    return jsonify({'platforms': platform_meta()})


@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'jobs': len(JOBS)})


@app.errorhandler(404)
def not_found(_):
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Not found'}), 404
    return redirect(url_for('index'))


init_db()

if __name__ == '__main__':
    # use_reloader=False: the reloader would start a second process (and a second
    # pool of Chrome drivers) and wipe the in-memory job state on every edit.
    app.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG, threaded=True, use_reloader=False)