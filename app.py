from flask import Flask, render_template, request, jsonify
from config import Config
from scraper import AmazonScraper, FlipkartScraper

app = Flask(__name__)
app.config.from_object(Config)

def get_comparison_data(query):
    results = []
    amazon_scraper = None
    flipkart_scraper = None
    
    try:
        print(f"Scraping Amazon for: {query}")
        amazon_scraper = AmazonScraper(headless=True)
        amazon_results = amazon_scraper.scrape(query, max_results=5)
        results.extend(amazon_results)
        print(f"Amazon: found {len(amazon_results)} products")
    except Exception as e:
        print(f"Amazon error: {e}")
    finally:
        if amazon_scraper:
            amazon_scraper.close()
    
    try:
        print(f"Scraping Flipkart for: {query}")
        flipkart_scraper = FlipkartScraper(headless=True)
        flipkart_results = flipkart_scraper.scrape(query, max_results=5)
        results.extend(flipkart_results)
        print(f"Flipkart: found {len(flipkart_results)} products")
    except Exception as e:
        print(f"Flipkart error: {e}")
    finally:
        if flipkart_scraper:
            flipkart_scraper.close()
    
    return results

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/results')
def results_page():
    query = request.args.get('q', '')
    return render_template('results.html', query=query)

@app.route('/api/search', methods=['POST'])
def api_search():
    data = request.get_json()
    query = data.get('query', '').strip()
    
    if not query:
        return jsonify({'error': 'Query is required'}), 400
    
    try:
        results = get_comparison_data(query)
        
        grouped = {}
        for item in results:
            platform = item.get('platform_name') or item.get('platform')
            if platform not in grouped:
                grouped[platform] = []
            grouped[platform].append(item)
        
        all_prices = [item['price'] for item in results]
        best_price = min(all_prices) if all_prices else None
        
        return jsonify({
            'query': query,
            'results': results,
            'grouped': grouped,
            'best_price': best_price,
            'count': len(results)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
