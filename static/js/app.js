function initParticles() {
    const container = document.getElementById('particles');
    if (!container) return;
    
    for (let i = 0; i < 20; i++) {
        const dot = document.createElement('div');
        dot.style.cssText = `
            position: absolute;
            width: ${Math.random() * 4 + 2}px;
            height: ${Math.random() * 4 + 2}px;
            background: rgba(255,255,255,${Math.random() * 0.3 + 0.1});
            border-radius: 50%;
            left: ${Math.random() * 100}%;
            top: ${Math.random() * 100}%;
            animation: float ${15 + Math.random() * 20}s infinite ease-in-out;
            animation-delay: -${Math.random() * 20}s;
        `;
        container.appendChild(dot);
    }
}

function initIndexPage() {
    const searchForm = document.getElementById('search-form');
    if (!searchForm) return;
    
    searchForm.addEventListener('submit', function(e) {
        e.preventDefault();
        const query = document.getElementById('search-input').value.trim();
        if (query) {
            window.location.href = '/results?q=' + encodeURIComponent(query);
        }
    });
}

async function loadResults(query) {
    const loadingState = document.getElementById('loading-state');
    const resultsContent = document.getElementById('results-content');
    const resultsGrid = document.getElementById('results-grid');
    const errorState = document.getElementById('error-state');
    const noResults = document.getElementById('no-results');
    const resultCount = document.getElementById('result-count');
    const queryDisplay = document.getElementById('query-display');
    
    if (queryDisplay) {
        queryDisplay.textContent = query;
    }
    
    try {
        const response = await fetch('/api/search', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query: query })
        });
        
        const data = await response.json();
        
        if (loadingState) loadingState.classList.add('d-none');
        
        if (!response.ok) {
            throw new Error(data.error || 'Search failed');
        }
        
        if (data.count === 0) {
            if (noResults) noResults.classList.remove('d-none');
            return;
        }
        
        if (resultsContent) resultsContent.classList.remove('d-none');
        if (resultCount) resultCount.textContent = data.count + ' deals found';
        
        renderProductCards(data.results, data.best_price, resultsGrid);
        
    } catch (error) {
        if (loadingState) loadingState.classList.add('d-none');
        if (errorState) {
            errorState.textContent = 'Error: ' + error.message;
            errorState.classList.remove('d-none');
        }
        console.error('Search error:', error);
    }
}

function renderProductCards(results, bestPrice, container) {
    if (!container) return;
    container.innerHTML = '';
    
    results.forEach((item, index) => {
        const isBestPrice = item.price === bestPrice;
        const platform = item.platform_name || item.platform;
        const badgeClass = platform.toLowerCase().includes('amazon') ? 'badge-amazon' : 'badge-flipkart';
        const platformDisplay = platform.toLowerCase().includes('amazon') ? 'Amazon' : 'Flipkart';
        const productUrl = item.product_url || item.url;
        const imgId = 'img-' + index;
        
        const col = document.createElement('div');
        col.className = 'col-md-6 col-lg-4';
        
        col.innerHTML = `
            <div class="product-card ${isBestPrice ? 'best-price' : ''}" style="animation: fadeInUp 0.5s ease ${index * 0.08}s both;">
                ${isBestPrice ? `
                    <div class="best-badge">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                            <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/>
                        </svg>
                        Best Price
                    </div>
                ` : ''}
                <div class="product-image-wrap">
                    <img id="${imgId}" src="${item.image_url ? escapeHtml(item.image_url) : ''}" 
                         alt="${escapeHtml(item.name)}" loading="lazy" 
                         onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';"
                         onload="this.style.display='block'; this.nextElementSibling.style.display='none';">
                    <div class="product-image-placeholder" style="${item.image_url ? 'display:none' : 'display:flex'}">
                        <span style="font-size:2rem; font-weight:800; color:#cbd5e1;">${escapeHtml(platformDisplay[0])}</span>
                    </div>
                </div>
                <div class="product-body">
                    <span class="platform-badge ${badgeClass}">${escapeHtml(platformDisplay)}</span>
                    <h5 class="product-name">${escapeHtml(item.name)}</h5>
                    <div class="product-footer">
                        <span class="product-price">${formatPrice(item.price)}</span>
                        <a href="${escapeHtml(productUrl)}" target="_blank" rel="noopener noreferrer" class="btn-buy">
                            Buy Now
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                                <path d="M7 17L17 7M17 7H7M17 7v10"/>
                            </svg>
                        </a>
                    </div>
                </div>
            </div>
        `;
        
        container.appendChild(col);
    });
    
    addFadeInAnimation();
}

function addFadeInAnimation() {
    if (document.getElementById('fade-style')) return;
    const style = document.createElement('style');
    style.id = 'fade-style';
    style.textContent = `
        @keyframes fadeInUp {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }
    `;
    document.head.appendChild(style);
}

function formatPrice(price) {
    return '₹' + price.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function getPlatformBadgeClass(platform) {
    const name = (platform || '').toLowerCase();
    if (name.includes('amazon')) return 'badge-amazon';
    if (name.includes('flipkart')) return 'badge-flipkart';
    return 'bg-secondary';
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
