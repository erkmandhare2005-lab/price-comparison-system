/* ==========================================================================
   PriceCompare India - front-end
   Sections: helpers, Theme, Toast, Recent, Wishlist, Suggest, page chrome,
             IndexPage, ResultsPage
   ========================================================================== */
'use strict';

/* ---------- helpers ---------------------------------------------------- */
const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

const store = {
    get(key, fallback) {
        try {
            const raw = localStorage.getItem(key);
            return raw === null ? fallback : JSON.parse(raw);
        } catch (e) {
            return fallback;
        }
    },
    set(key, value) {
        try { localStorage.setItem(key, JSON.stringify(value)); } catch (e) { /* storage unavailable */ }
    },
};

function escapeHtml(text) {
    return String(text == null ? '' : text).replace(/[&<>"']/g, (c) => (
        { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
    ));
}

function safeUrl(url) {
    try {
        const parsed = new URL(url, window.location.href);
        return ['http:', 'https:'].includes(parsed.protocol) ? parsed.href : '#';
    } catch (e) {
        return '#';
    }
}

function safeColor(color) {
    return /^#[0-9a-f]{6}$/i.test(color || '') ? color : '#6366f1';
}

function formatPrice(value) {
    if (value == null || Number.isNaN(Number(value))) return '-';
    return '₹' + Number(value).toLocaleString('en-IN', { maximumFractionDigits: 0 });
}

function debounce(fn, wait = 250) {
    let timer;
    return (...args) => {
        clearTimeout(timer);
        timer = setTimeout(() => fn(...args), wait);
    };
}

function itemKey(item) {
    return `${item.platform_key}|${item.url || item.name}`;
}

function timeAgo(seconds) {
    if (seconds < 60) return 'just now';
    const minutes = Math.round(seconds / 60);
    return `${minutes} min ago`;
}

function goSearch(query) {
    const q = (query || '').trim();
    if (q.length < 2) return;
    Recent.add(q);
    window.location.href = '/results?q=' + encodeURIComponent(q);
}

/* ---------- Theme ------------------------------------------------------ */
const Theme = {
    current() {
        return document.documentElement.getAttribute('data-theme') || 'light';
    },
    apply(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        document.documentElement.setAttribute('data-bs-theme', theme);
        store.set('theme', theme);
        const btn = $('#theme-toggle');
        if (btn) btn.setAttribute('aria-pressed', String(theme === 'dark'));
        document.dispatchEvent(new CustomEvent('theme:change', { detail: theme }));
    },
    init() {
        const btn = $('#theme-toggle');
        if (btn) {
            btn.setAttribute('aria-pressed', String(this.current() === 'dark'));
            btn.addEventListener('click', () => this.apply(this.current() === 'dark' ? 'light' : 'dark'));
        }
    },
};

/* ---------- Toast ------------------------------------------------------ */
const Toast = {
    show(message, type = 'info') {
        const host = $('#toast-host');
        if (!host) return;
        const el = document.createElement('div');
        el.className = `toast-item toast-${type}`;
        el.textContent = message;
        host.appendChild(el);
        requestAnimationFrame(() => el.classList.add('show'));
        setTimeout(() => {
            el.classList.remove('show');
            setTimeout(() => el.remove(), 300);
        }, 2800);
    },
};

/* ---------- Recent searches ------------------------------------------- */
const Recent = {
    key: 'recent_searches',
    all() { return store.get(this.key, []); },
    add(query) {
        const list = this.all().filter((q) => q.toLowerCase() !== query.toLowerCase());
        list.unshift(query);
        store.set(this.key, list.slice(0, 8));
    },
    clear() { store.set(this.key, []); },
};

/* ---------- Wishlist --------------------------------------------------- */
const Wishlist = {
    key: 'wishlist',
    all() { return store.get(this.key, []); },
    has(item) {
        const k = itemKey(item);
        return this.all().some((x) => itemKey(x) === k);
    },
    toggle(item) {
        let list = this.all();
        const k = itemKey(item);
        if (list.some((x) => itemKey(x) === k)) {
            list = list.filter((x) => itemKey(x) !== k);
            Toast.show('Removed from wishlist');
        } else {
            list.unshift({ ...item, saved_at: Date.now() });
            Toast.show('Saved to wishlist', 'success');
        }
        store.set(this.key, list);
        this.refresh();
        document.dispatchEvent(new CustomEvent('wishlist:change'));
    },
    removeKey(k) {
        store.set(this.key, this.all().filter((x) => itemKey(x) !== k));
        this.refresh();
        document.dispatchEvent(new CustomEvent('wishlist:change'));
    },
    clear() {
        store.set(this.key, []);
        this.refresh();
        document.dispatchEvent(new CustomEvent('wishlist:change'));
    },
    refresh() {
        const list = this.all();
        const badge = $('#wishlist-count');
        if (badge) {
            badge.textContent = list.length;
            badge.classList.toggle('d-none', list.length === 0);
        }
        const host = $('#wishlist-list');
        if (!host) return;
        if (!list.length) {
            host.innerHTML = '<div class="wish-empty"><div class="fs-1 mb-2">&#9825;</div>Nothing saved yet.<br>Tap the heart on any product.</div>';
            return;
        }
        host.innerHTML = list.map((item) => {
            const img = item.image_url
                ? `<img src="${escapeHtml(safeUrl(item.image_url))}" alt="" loading="lazy">`
                : `<div class="ph">${escapeHtml((item.platform || '?')[0])}</div>`;
            return `
                <div class="wish-item" data-key="${escapeHtml(itemKey(item))}">
                    ${img}
                    <div class="info">
                        <div class="nm">${escapeHtml(item.name)}</div>
                        <div class="pr">${formatPrice(item.price)}</div>
                        <div class="st">${escapeHtml(item.platform)} &middot; price when saved</div>
                        <div class="actions">
                            <a href="${escapeHtml(safeUrl(item.url))}" target="_blank" rel="noopener noreferrer">Open</a>
                            <button type="button" data-remove>Remove</button>
                        </div>
                    </div>
                </div>`;
        }).join('');
    },
    init() {
        this.refresh();
        const host = $('#wishlist-list');
        if (host) {
            host.addEventListener('click', (event) => {
                const btn = event.target.closest('[data-remove]');
                if (!btn) return;
                this.removeKey(btn.closest('.wish-item').dataset.key);
            });
            host.addEventListener('error', (event) => {
                if (event.target.tagName === 'IMG') event.target.style.visibility = 'hidden';
            }, true);
        }
        const clear = $('#wishlist-clear');
        if (clear) clear.addEventListener('click', () => this.clear());
    },
};

/* ---------- Search suggestions ---------------------------------------- */
function attachSuggest(input, box, onPick) {
    if (!input || !box) return;
    let items = [];
    let active = -1;

    const hide = () => {
        box.classList.add('d-none');
        input.setAttribute('aria-expanded', 'false');
        active = -1;
    };

    const render = () => {
        if (!items.length) { hide(); return; }
        box.innerHTML = items.map((entry, i) => `
            <li class="suggest-item${i === active ? ' active' : ''}" role="option" data-i="${i}">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">${entry.recent
                    ? '<path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5M12 7v5l3 2"/>'
                    : '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>'}</svg>
                <span>${escapeHtml(entry.text)}</span>
                ${entry.recent ? '<small>recent</small>' : ''}
            </li>`).join('');
        box.classList.remove('d-none');
        input.setAttribute('aria-expanded', 'true');
    };

    const gather = async () => {
        const q = input.value.trim().toLowerCase();
        const recents = Recent.all()
            .filter((r) => !q || r.toLowerCase().includes(q))
            .map((text) => ({ text, recent: true }));
        items = recents.slice(0, 4);
        active = -1;
        render();
        if (q.length < 2) return;
        try {
            const res = await fetch('/api/suggest?q=' + encodeURIComponent(q));
            if (!res.ok) return;
            const data = await res.json();
            if (input.value.trim().toLowerCase() !== q) return; // stale response
            const seen = new Set(items.map((i) => i.text.toLowerCase()));
            data.suggestions.forEach((text) => {
                if (!seen.has(text.toLowerCase())) items.push({ text, recent: false });
            });
            items = items.slice(0, 7);
            render();
        } catch (e) { /* suggestions are optional */ }
    };

    input.addEventListener('input', debounce(gather, 200));
    input.addEventListener('focus', gather);
    input.addEventListener('keydown', (event) => {
        if (box.classList.contains('d-none')) return;
        if (event.key === 'ArrowDown') {
            event.preventDefault();
            active = (active + 1) % items.length;
            render();
        } else if (event.key === 'ArrowUp') {
            event.preventDefault();
            active = (active - 1 + items.length) % items.length;
            render();
        } else if (event.key === 'Enter' && active >= 0) {
            event.preventDefault();
            const text = items[active].text;
            input.value = text;
            hide();
            onPick(text);
        } else if (event.key === 'Escape') {
            hide();
        }
    });
    box.addEventListener('mousedown', (event) => {
        const li = event.target.closest('.suggest-item');
        if (!li) return;
        event.preventDefault();
        const text = items[Number(li.dataset.i)].text;
        input.value = text;
        hide();
        onPick(text);
    });
    document.addEventListener('click', (event) => {
        if (!box.contains(event.target) && event.target !== input) hide();
    });
}

/* ---------- Page chrome ------------------------------------------------ */
function initBackToTop() {
    const btn = $('#back-to-top');
    if (!btn) return;
    window.addEventListener('scroll', () => btn.classList.toggle('visible', window.scrollY > 500), { passive: true });
    btn.addEventListener('click', () => window.scrollTo({ top: 0, behavior: 'smooth' }));
}

function initReveal() {
    const targets = $$('[data-reveal]');
    if (!targets.length) return;
    if (!('IntersectionObserver' in window)) {
        targets.forEach((el) => el.classList.add('revealed'));
        return;
    }
    const observer = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
            if (entry.isIntersecting) {
                entry.target.classList.add('revealed');
                observer.unobserve(entry.target);
            }
        });
    }, { threshold: 0.12 });
    targets.forEach((el, i) => {
        el.style.transitionDelay = `${(i % 3) * 80}ms`;
        observer.observe(el);
    });
}

function animateCount(el, target) {
    const duration = 900;
    const start = performance.now();
    const from = Number(el.textContent.replace(/,/g, '')) || 0;
    const step = (now) => {
        const t = Math.min(1, (now - start) / duration);
        const eased = 1 - Math.pow(1 - t, 3);
        el.textContent = Math.round(from + (target - from) * eased).toLocaleString('en-IN');
        if (t < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
}

function initParticles() {
    const container = $('#particles');
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

/* ==========================================================================
   Index page
   ========================================================================== */
const IndexPage = {
    examples: ['iPhone 15', 'Sony WH-1000XM5', 'Samsung 55 inch smart TV', 'MacBook Air M2', 'boAt Airdopes'],

    init() {
        initParticles();

        const form = $('#search-form');
        const input = $('#search-input');
        if (form && input) {
            form.addEventListener('submit', (event) => {
                event.preventDefault();
                goSearch(input.value);
            });
            attachSuggest(input, $('#suggest-box'), goSearch);
            this.rotatePlaceholder(input);
            document.addEventListener('keydown', (event) => {
                if (event.key === '/' && !/^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName)) {
                    event.preventDefault();
                    input.focus();
                }
            });
        }

        this.renderRecents();
        const clear = $('#recent-clear');
        if (clear) clear.addEventListener('click', () => { Recent.clear(); this.renderRecents(); });

        this.loadTrending();
        this.loadStats();
    },

    rotatePlaceholder(input) {
        let i = 0;
        const base = 'Search for ';
        setInterval(() => {
            if (document.activeElement === input || input.value) return;
            i = (i + 1) % this.examples.length;
            input.placeholder = base + this.examples[i] + '...';
        }, 2600);
    },

    renderRecents() {
        const wrap = $('#recent-wrap');
        const host = $('#recent-searches');
        if (!wrap || !host) return;
        const list = Recent.all();
        wrap.hidden = list.length === 0;
        host.innerHTML = list.slice(0, 6).map((q) =>
            `<a href="/results?q=${encodeURIComponent(q)}" class="popular-tag">${escapeHtml(q)}</a>`
        ).join('');
    },

    async loadTrending() {
        const host = $('#trending-searches');
        if (!host) return;
        try {
            const res = await fetch('/api/trending');
            if (!res.ok) return;
            const data = await res.json();
            if (!data.terms.length) return;
            const label = $('#trending-label');
            if (label) label.textContent = data.is_default ? 'Popular' : 'Trending';
            host.innerHTML = data.terms.slice(0, 6).map((q) =>
                `<a href="/results?q=${encodeURIComponent(q)}" class="popular-tag">${escapeHtml(q)}</a>`
            ).join('');
        } catch (e) { /* keep the static fallback chips */ }
    },

    async loadStats() {
        try {
            const res = await fetch('/api/stats');
            if (!res.ok) return;
            const data = await res.json();
            const targets = { 'stat-stores': data.stores, 'stat-searches': data.searches, 'stat-prices': data.prices };
            const run = () => Object.entries(targets).forEach(([id, value]) => {
                const el = document.getElementById(id);
                if (el) animateCount(el, value);
            });
            const strip = $('.stats-strip');
            if (strip && 'IntersectionObserver' in window) {
                const observer = new IntersectionObserver((entries) => {
                    if (entries.some((e) => e.isIntersecting)) { run(); observer.disconnect(); }
                }, { threshold: 0.4 });
                observer.observe(strip);
            } else {
                run();
            }
        } catch (e) { /* stats are decorative */ }
    },
};

/* ==========================================================================
   Results page
   ========================================================================== */
const ResultsPage = {
    state: {
        query: '',
        jobId: null,
        runId: 0,
        items: [],
        platforms: {},
        done: false,
        cached: false,
        cachedAge: 0,
        sort: 'price-asc',
        view: 'grid',
        priceTouched: false,
        filters: { hidden: new Set(), maxPrice: null, minRating: 0, strict: false, text: '' },
        compare: new Map(),
        seen: new Set(),
        chart: null,
    },
    el: {},

    /* ---- setup --------------------------------------------------------- */
    init(query) {
        const s = this.state;
        s.query = query;
        s.sort = store.get('sort', 'price-asc');
        s.view = store.get('view', 'grid');

        const ids = [
            'results-grid', 'platform-status', 'search-progress', 'stats-row', 'result-count', 'cached-note',
            'sort-select', 'view-grid', 'view-list', 'filter-text', 'filter-platforms', 'price-max',
            'price-max-label', 'price-min-label', 'price-high-label', 'min-rating', 'strict-match',
            'reset-filters', 'error-state', 'error-text', 'retry-btn', 'no-results', 'no-results-title',
            'no-results-text', 'clear-filters-btn', 'export-btn', 'share-btn', 'refresh-btn', 'history-btn',
            'compare-tray', 'compare-items', 'compare-hint', 'compare-clear', 'compare-open', 'compare-table',
            'results-subtitle', 'research-form', 'research-input', 'research-suggest', 'history-chart', 'history-empty',
        ];
        ids.forEach((id) => { this.el[id] = document.getElementById(id); });

        this.el['sort-select'].value = s.sort;
        this.applyView();
        this.bind();
        this.start(false);
    },

    bind() {
        const el = this.el;
        const s = this.state;

        el['research-form'].addEventListener('submit', (event) => {
            event.preventDefault();
            goSearch(el['research-input'].value);
        });
        attachSuggest(el['research-input'], el['research-suggest'], goSearch);

        el['sort-select'].addEventListener('change', () => {
            s.sort = el['sort-select'].value;
            store.set('sort', s.sort);
            this.render();
        });
        el['view-grid'].addEventListener('click', () => { s.view = 'grid'; store.set('view', 'grid'); this.applyView(); });
        el['view-list'].addEventListener('click', () => { s.view = 'list'; store.set('view', 'list'); this.applyView(); });

        el['filter-text'].addEventListener('input', debounce(() => {
            s.filters.text = el['filter-text'].value.trim().toLowerCase();
            this.render();
        }, 150));
        el['price-max'].addEventListener('input', () => {
            s.priceTouched = true;
            const slider = el['price-max'];
            s.filters.maxPrice = Number(slider.value) >= Number(slider.max) ? null : Number(slider.value);
            this.render();
        });
        el['min-rating'].addEventListener('change', () => {
            s.filters.minRating = Number(el['min-rating'].value);
            this.render();
        });
        el['strict-match'].addEventListener('change', () => {
            s.filters.strict = el['strict-match'].checked;
            this.render();
        });
        el['filter-platforms'].addEventListener('change', (event) => {
            const box = event.target.closest('input[type="checkbox"]');
            if (!box) return;
            if (box.checked) s.filters.hidden.delete(box.value); else s.filters.hidden.add(box.value);
            this.render();
        });
        el['reset-filters'].addEventListener('click', () => this.resetFilters());
        el['clear-filters-btn'].addEventListener('click', () => this.resetFilters());

        el['retry-btn'].addEventListener('click', () => this.start(true));
        el['refresh-btn'].addEventListener('click', () => this.start(true));
        el['cached-note'].addEventListener('click', () => this.start(true));
        el['share-btn'].addEventListener('click', () => this.share());
        el['history-btn'].addEventListener('click', () => this.showHistory());

        el['results-grid'].addEventListener('click', (event) => this.onGridClick(event));
        el['results-grid'].addEventListener('error', (event) => {
            if (event.target.tagName === 'IMG') {
                event.target.style.display = 'none';
                const placeholder = event.target.nextElementSibling;
                if (placeholder) placeholder.classList.add('show');
            }
        }, true);

        el['compare-clear'].addEventListener('click', () => { s.compare.clear(); this.render(); });
        el['compare-open'].addEventListener('click', () => this.showCompare());
        el['compare-items'].addEventListener('click', (event) => {
            const btn = event.target.closest('[data-remove-compare]');
            if (!btn) return;
            s.compare.delete(btn.dataset.removeCompare);
            this.render();
        });

        document.addEventListener('wishlist:change', () => this.render());
        document.addEventListener('theme:change', () => { if (s.chart) this.showHistory(true); });
        document.addEventListener('keydown', (event) => {
            if (event.key === '/' && !/^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName)) {
                event.preventDefault();
                el['filter-text'].focus();
            }
        });
    },

    applyView() {
        const s = this.state;
        this.el['results-grid'].classList.toggle('view-list', s.view === 'list');
        this.el['view-grid'].classList.toggle('active', s.view === 'grid');
        this.el['view-list'].classList.toggle('active', s.view === 'list');
    },

    resetFilters() {
        const s = this.state;
        s.filters = { hidden: new Set(), maxPrice: null, minRating: 0, strict: false, text: '' };
        s.priceTouched = false;
        this.el['filter-text'].value = '';
        this.el['min-rating'].value = '0';
        this.el['strict-match'].checked = false;
        this.syncPriceSlider();
        this.render();
    },

    /* ---- search lifecycle --------------------------------------------- */
    async start(refresh) {
        const s = this.state;
        s.runId += 1;
        const runId = s.runId;
        s.items = [];
        s.platforms = {};
        s.done = false;
        s.seen.clear();
        s.compare.clear();
        s.cached = false;

        this.el['error-state'].classList.add('d-none');
        this.el['search-progress'].classList.add('indeterminate');
        this.el['search-progress'].style.opacity = '1';
        this.el['export-btn'].classList.add('disabled');
        this.el['refresh-btn'].disabled = true;
        this.render();

        try {
            const res = await fetch('/api/search', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query: s.query, refresh: Boolean(refresh) }),
            });
            const data = await res.json().catch(() => ({}));
            if (!res.ok) throw new Error(data.error || 'Search failed');
            if (runId !== s.runId) return;
            s.jobId = data.job_id;
            this.el['export-btn'].href = `/api/export/${s.jobId}.csv`;
            this.poll(runId);
        } catch (error) {
            this.showError(error.message);
        }
    },

    poll(runId) {
        const s = this.state;
        const startedAt = Date.now();
        let failures = 0;

        const tick = async () => {
            if (runId !== s.runId) return;
            try {
                const res = await fetch(`/api/search/${s.jobId}`);
                if (!res.ok) throw new Error(`Status check failed (${res.status})`);
                const data = await res.json();
                if (runId !== s.runId) return;
                failures = 0;
                this.ingest(data);
                if (data.status === 'done') {
                    this.finish(data);
                    return;
                }
            } catch (error) {
                failures += 1;
                if (failures >= 3) { this.showError(error.message); return; }
            }
            if (Date.now() - startedAt > 240000) {
                this.showError('The search took too long. Please try again.');
                return;
            }
            setTimeout(tick, 1200);
        };
        tick();
    },

    ingest(data) {
        const s = this.state;
        s.items = data.results || [];
        s.platforms = data.platforms || {};
        s.cached = Boolean(data.cached);
        s.cachedAge = data.cachedAge || data.cached_age || 0;

        const progress = this.el['search-progress'];
        if (data.finished > 0) {
            progress.classList.remove('indeterminate');
            progress.style.width = `${Math.round((data.finished / data.total) * 100)}%`;
        }
        this.renderStatus();
        this.buildPlatformFilter();
        this.syncPriceSlider();
        this.render();
    },

    finish(data) {
        const s = this.state;
        s.done = true;
        const progress = this.el['search-progress'];
        progress.classList.remove('indeterminate');
        progress.style.width = '100%';
        setTimeout(() => { progress.style.opacity = '0'; }, 800);
        this.el['refresh-btn'].disabled = false;
        this.el['export-btn'].classList.toggle('disabled', !s.items.length);

        const stores = new Set(s.items.map((i) => i.platform_key)).size;
        this.el['results-subtitle'].textContent = s.items.length
            ? `${s.items.length} listings from ${stores} of ${data.total} stores`
            : 'No listings found';
        if (s.items.length) {
            Toast.show(`Found ${s.items.length} deals across ${stores} stores`, 'success');
        }
        this.render();
    },

    showError(message) {
        const s = this.state;
        s.done = true;
        this.el['error-text'].textContent = message;
        this.el['error-state'].classList.remove('d-none');
        this.el['search-progress'].classList.remove('indeterminate');
        this.el['search-progress'].style.opacity = '0';
        this.el['refresh-btn'].disabled = false;
        this.render();
    },

    /* ---- store status chips ------------------------------------------- */
    renderStatus() {
        const entries = Object.entries(this.state.platforms);
        this.el['platform-status'].innerHTML = entries.map(([key, p]) => {
            const color = safeColor(p.color);
            let state = 'waiting';
            if (p.status === 'running') state = '<span class="mini-spinner"></span>';
            else if (p.status === 'done') state = `${p.count} found${p.elapsed != null ? ` &middot; ${p.elapsed}s` : ''}`;
            else if (p.status === 'error') state = 'failed';
            const title = p.status === 'error' ? ` title="${escapeHtml(p.error || 'Failed')}"` : '';
            return `<span class="status-chip ${escapeHtml(p.status)}" style="--brand:${color}"${title} data-store="${escapeHtml(key)}">
                        <span class="dot"></span><strong>${escapeHtml(p.name)}</strong><span class="state">${state}</span>
                    </span>`;
        }).join('');
    },

    /* ---- filters ------------------------------------------------------- */
    buildPlatformFilter() {
        const s = this.state;
        const counts = {};
        s.items.forEach((item) => { counts[item.platform_key] = (counts[item.platform_key] || 0) + 1; });
        this.el['filter-platforms'].innerHTML = Object.entries(s.platforms).map(([key, p]) => `
            <label class="filter-check" style="--brand:${safeColor(p.color)}">
                <input class="form-check-input mt-0" type="checkbox" value="${escapeHtml(key)}" ${s.filters.hidden.has(key) ? '' : 'checked'}>
                <span class="dot"></span>${escapeHtml(p.name)}
                <span class="n">${counts[key] || 0}</span>
            </label>`).join('');
    },

    syncPriceSlider() {
        const s = this.state;
        const slider = this.el['price-max'];
        const prices = s.items.map((i) => i.price);
        if (!prices.length) {
            slider.disabled = true;
            ['price-max-label', 'price-min-label', 'price-high-label'].forEach((id) => { this.el[id].textContent = '-'; });
            return;
        }
        const low = Math.floor(Math.min(...prices));
        const high = Math.ceil(Math.max(...prices));
        slider.disabled = low === high;
        slider.min = low;
        slider.max = high;
        slider.step = Math.max(1, Math.round((high - low) / 100));
        if (!s.priceTouched || s.filters.maxPrice == null) {
            slider.value = high;
            s.filters.maxPrice = null;
        } else {
            slider.value = Math.min(s.filters.maxPrice, high);
        }
        this.el['price-min-label'].textContent = formatPrice(low);
        this.el['price-high-label'].textContent = formatPrice(high);
        this.el['price-max-label'].textContent = s.filters.maxPrice == null ? 'No limit' : formatPrice(s.filters.maxPrice);
    },

    filtered() {
        const s = this.state;
        const f = s.filters;
        const list = s.items.filter((item) => {
            if (f.hidden.has(item.platform_key)) return false;
            if (f.maxPrice != null && item.price > f.maxPrice) return false;
            if (f.minRating > 0 && !(item.rating != null && item.rating >= f.minRating)) return false;
            if (f.strict && (item.relevance == null || item.relevance < 0.6)) return false;
            if (f.text && !item.name.toLowerCase().includes(f.text)) return false;
            return true;
        });

        const by = {
            'price-asc': (a, b) => a.price - b.price,
            'price-desc': (a, b) => b.price - a.price,
            'discount': (a, b) => (b.discount_pct || 0) - (a.discount_pct || 0) || a.price - b.price,
            'rating': (a, b) => (b.rating || 0) - (a.rating || 0) || a.price - b.price,
            'relevance': (a, b) => (b.relevance || 0) - (a.relevance || 0) || a.price - b.price,
            'name': (a, b) => a.name.localeCompare(b.name),
        };
        return list.sort(by[s.sort] || by['price-asc']);
    },

    /* ---- rendering ----------------------------------------------------- */
    render() {
        const s = this.state;
        const list = this.filtered();
        const best = list.length ? list.reduce((a, b) => (b.price < a.price ? b : a)) : null;
        const bestKey = best ? itemKey(best) : null;

        this.renderStats(list);
        this.renderCount(list);

        const grid = this.el['results-grid'];
        const cards = list.map((item) => this.cardHtml(item, best, bestKey)).join('');
        const skeletons = !s.done ? this.skeletonHtml(Math.max(0, 6 - list.length)) : '';
        grid.innerHTML = cards + skeletons;
        list.forEach((item) => s.seen.add(itemKey(item)));

        // empty states
        const none = this.el['no-results'];
        const showNone = s.done && list.length === 0 && this.el['error-state'].classList.contains('d-none');
        none.classList.toggle('d-none', !showNone);
        if (showNone) {
            const filtersActive = s.items.length > 0;
            this.el['no-results-title'].textContent = filtersActive ? 'Nothing matches your filters' : 'No results found';
            this.el['no-results-text'].textContent = filtersActive
                ? 'Try loosening the price, rating or store filters.'
                : this.failureHint();
            this.el['clear-filters-btn'].classList.toggle('d-none', !filtersActive);
            $('#back-search-btn').classList.toggle('d-none', filtersActive);
        }

        this.renderCompareTray();
    },

    failureHint() {
        const errors = Object.values(this.state.platforms).filter((p) => p.status === 'error');
        if (errors.length && errors.length === Object.keys(this.state.platforms).length) {
            return 'Every store failed to respond. Check that Chrome is installed and your connection works, then try again.';
        }
        return 'Try searching with a different product name.';
    },

    renderCount(list) {
        const s = this.state;
        const total = s.items.length;
        const label = this.el['result-count'];
        if (!s.done && total === 0) label.textContent = 'Searching...';
        else if (list.length === total) label.textContent = `${total} ${total === 1 ? 'deal' : 'deals'} found`;
        else label.textContent = `${list.length} of ${total} shown`;

        const note = this.el['cached-note'];
        note.classList.toggle('d-none', !s.cached);
        if (s.cached) {
            note.textContent = `Cached ${timeAgo(s.cachedAge)} - click to refresh`;
            note.style.cursor = 'pointer';
        }
    },

    renderStats(list) {
        const row = this.el['stats-row'];
        if (!list.length) { row.classList.add('d-none'); return; }
        row.classList.remove('d-none');
        const prices = list.map((i) => i.price);
        const low = list.reduce((a, b) => (b.price < a.price ? b : a));
        const high = list.reduce((a, b) => (b.price > a.price ? b : a));
        const avg = prices.reduce((a, b) => a + b, 0) / prices.length;

        $('#stat-lowest').textContent = formatPrice(low.price);
        $('#stat-lowest-sub').textContent = low.platform;
        $('#stat-avg').textContent = formatPrice(avg);
        $('#stat-avg-sub').textContent = `across ${list.length} listings`;
        $('#stat-high').textContent = formatPrice(high.price);
        $('#stat-high-sub').textContent = high.platform;
        $('#stat-save').textContent = list.length > 1 ? formatPrice(high.price - low.price) : '-';
        $('#stat-save-sub').textContent = list.length > 1
            ? `${Math.round(((high.price - low.price) / high.price) * 100)}% less than ${high.platform}`
            : 'need 2+ listings';
    },

    skeletonHtml(count) {
        let html = '';
        for (let i = 0; i < count; i++) {
            html += `<div class="skeleton-card" aria-hidden="true">
                        <div class="skeleton-img"></div>
                        <div class="skeleton-body">
                            <div class="skeleton-line" style="width:35%"></div>
                            <div class="skeleton-line" style="width:90%"></div>
                            <div class="skeleton-line" style="width:70%"></div>
                            <div class="skeleton-line" style="width:40%;height:20px;margin-top:18px"></div>
                        </div>
                     </div>`;
        }
        return html;
    },

    cardHtml(item, best, bestKey) {
        const s = this.state;
        const key = itemKey(item);
        const color = safeColor(item.brand_color);
        const isBest = key === bestKey;
        const saved = Wishlist.has(item);
        const comparing = s.compare.has(key);
        const entering = !s.seen.has(key);
        const diff = !isBest && best ? item.price - best.price : 0;
        const initial = escapeHtml((item.platform || '?')[0]);

        const badges = [];
        if (isBest) {
            badges.push(`<span class="best-badge"><svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01z"/></svg>Best price</span>`);
        }
        if (item.discount_pct && item.discount_pct >= 25) {
            badges.push(`<span class="deal-badge">${item.discount_pct}% off</span>`);
        }

        const rating = item.rating
            ? `<span class="rating-chip" title="Customer rating">&#9733; ${Number(item.rating).toFixed(1)}</span>` : '';
        const mrp = item.mrp ? `<span class="mrp">${formatPrice(item.mrp)}</span>` : '';
        const discount = item.discount_pct ? `<span class="discount-pill">${item.discount_pct}% off</span>` : '';
        const diffNote = isBest
            ? '<div class="price-diff is-best">Lowest across stores</div>'
            : `<div class="price-diff">${diff > 0 ? `${formatPrice(diff)} more than the best price` : ''}</div>`;
        const img = item.image_url
            ? `<img src="${escapeHtml(safeUrl(item.image_url))}" alt="${escapeHtml(item.name)}" loading="lazy" referrerpolicy="no-referrer">
               <div class="product-image-placeholder">${initial}</div>`
            : `<div class="product-image-placeholder show">${initial}</div>`;

        return `
        <article class="product-card${isBest ? ' best-price' : ''}${comparing ? ' comparing' : ''}${entering ? ' enter' : ''}" data-key="${escapeHtml(key)}">
            <div class="product-image-wrap">
                <div class="badge-stack">${badges.join('')}</div>
                <button type="button" class="wish-btn${saved ? ' active' : ''}" data-action="wishlist" aria-pressed="${saved}" aria-label="${saved ? 'Remove from' : 'Add to'} wishlist">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1-1.1a5.5 5.5 0 0 0-7.8 7.8l1 1.1L12 21l7.8-7.5 1-1.1a5.5 5.5 0 0 0 0-7.8z"/></svg>
                </button>
                ${img}
            </div>
            <div class="product-body">
                <div class="card-meta">
                    <span class="platform-badge" style="color:${color};background:${color}1f">${escapeHtml(item.platform)}</span>
                    ${rating}
                </div>
                <h5 class="product-name" title="${escapeHtml(item.name)}">${escapeHtml(item.name)}</h5>
                <div class="price-row"><span class="product-price">${formatPrice(item.price)}</span>${mrp}${discount}</div>
                ${diffNote}
                <div class="product-footer">
                    <button type="button" class="btn-compare${comparing ? ' active' : ''}" data-action="compare" aria-pressed="${comparing}">
                        ${comparing ? '&#10003; Added' : '+ Compare'}
                    </button>
                    <a href="${escapeHtml(safeUrl(item.url))}" target="_blank" rel="noopener noreferrer" class="btn-buy">
                        Buy now
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M7 17L17 7M17 7H7M17 7v10"/></svg>
                    </a>
                </div>
            </div>
        </article>`;
    },

    /* ---- interactions -------------------------------------------------- */
    onGridClick(event) {
        const btn = event.target.closest('[data-action]');
        if (!btn) return;
        const card = btn.closest('.product-card');
        if (!card) return;
        const item = this.state.items.find((i) => itemKey(i) === card.dataset.key);
        if (!item) return;

        if (btn.dataset.action === 'wishlist') {
            Wishlist.toggle(item);
        } else if (btn.dataset.action === 'compare') {
            const compare = this.state.compare;
            const key = itemKey(item);
            if (compare.has(key)) {
                compare.delete(key);
            } else if (compare.size >= 3) {
                Toast.show('You can compare up to 3 products', 'error');
                return;
            } else {
                compare.set(key, item);
            }
            this.render();
        }
    },

    renderCompareTray() {
        const compare = this.state.compare;
        const tray = this.el['compare-tray'];
        tray.hidden = compare.size === 0;
        document.body.classList.toggle('has-tray', compare.size > 0);
        if (!compare.size) return;

        this.el['compare-items'].innerHTML = Array.from(compare.entries()).map(([key, item]) => {
            const thumb = item.image_url
                ? `<img src="${escapeHtml(safeUrl(item.image_url))}" alt="" referrerpolicy="no-referrer">`
                : `<div class="ph">${escapeHtml((item.platform || '?')[0])}</div>`;
            return `<div class="compare-chip">${thumb}<span class="t">${escapeHtml(item.name)}</span>
                        <button type="button" data-remove-compare="${escapeHtml(key)}" aria-label="Remove from comparison">&times;</button></div>`;
        }).join('');
        this.el['compare-open'].disabled = compare.size < 2;
        this.el['compare-hint'].textContent = compare.size < 2 ? 'Add one more product to compare' : `${compare.size} of 3 selected`;
    },

    showCompare() {
        const items = Array.from(this.state.compare.values());
        if (items.length < 2) return;
        const lowest = Math.min(...items.map((i) => i.price));
        const cell = (fn, cls = () => '') => items.map((i) => `<td class="${cls(i)}">${fn(i)}</td>`).join('');

        const rows = [
            ['', cell((i) => i.image_url
                ? `<img src="${escapeHtml(safeUrl(i.image_url))}" alt="" referrerpolicy="no-referrer">` : '')],
            ['Product', cell((i) => `<div class="cmp-name">${escapeHtml(i.name)}</div>`)],
            ['Store', cell((i) => escapeHtml(i.platform))],
            ['Price', cell((i) => formatPrice(i.price), (i) => (i.price === lowest ? 'cmp-best' : ''))],
            ['MRP', cell((i) => (i.mrp ? formatPrice(i.mrp) : '-'))],
            ['Discount', cell((i) => (i.discount_pct ? `${i.discount_pct}%` : '-'))],
            ['Rating', cell((i) => (i.rating ? `&#9733; ${Number(i.rating).toFixed(1)}` : '-'))],
            ['Vs best', cell((i) => (i.price === lowest ? 'Lowest' : `+${formatPrice(i.price - lowest)}`))],
            ['', cell((i) => `<a class="btn-buy" href="${escapeHtml(safeUrl(i.url))}" target="_blank" rel="noopener noreferrer">Buy now</a>`)],
        ];

        this.el['compare-table'].innerHTML = `<table class="compare-table"><tbody>${
            rows.map(([label, cells]) => `<tr><th class="row-label" scope="row">${label}</th>${cells}</tr>`).join('')
        }</tbody></table>`;
        bootstrap.Modal.getOrCreateInstance(document.getElementById('compareModal')).show();
    },

    async share() {
        const url = window.location.href;
        try {
            if (navigator.share && /Mobi|Android/i.test(navigator.userAgent)) {
                await navigator.share({ title: `Prices for ${this.state.query}`, url });
                return;
            }
            await navigator.clipboard.writeText(url);
            Toast.show('Link copied to clipboard', 'success');
        } catch (e) {
            Toast.show('Could not copy the link', 'error');
        }
    },

    async showHistory(silent) {
        const s = this.state;
        const modalEl = document.getElementById('historyModal');
        if (!silent) bootstrap.Modal.getOrCreateInstance(modalEl).show();
        const empty = this.el['history-empty'];
        const canvas = this.el['history-chart'];
        empty.classList.add('d-none');

        try {
            const res = await fetch('/api/history?q=' + encodeURIComponent(s.query));
            const data = await res.json();
            const series = Object.entries(data.series || {});
            const labels = Array.from(new Set(series.flatMap(([, v]) => v.points.map((p) => p.t)))).sort();

            if (s.chart) { s.chart.destroy(); s.chart = null; }
            if (!labels.length || typeof Chart === 'undefined') {
                canvas.classList.add('d-none');
                empty.textContent = typeof Chart === 'undefined'
                    ? 'The chart library could not be loaded.'
                    : 'No history yet. Search this product again later to see how prices move.';
                empty.classList.remove('d-none');
                return;
            }
            canvas.classList.remove('d-none');

            const style = getComputedStyle(document.documentElement);
            const muted = style.getPropertyValue('--muted').trim() || '#64748b';
            const grid = style.getPropertyValue('--border').trim() || '#e2e8f0';
            const pretty = (t) => new Date(t.replace(' ', 'T') + 'Z')
                .toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });

            s.chart = new Chart(canvas, {
                type: 'line',
                data: {
                    labels: labels.map(pretty),
                    datasets: series.map(([, v]) => {
                        const byTime = new Map(v.points.map((p) => [p.t, p.min]));
                        return {
                            label: v.name,
                            data: labels.map((t) => (byTime.has(t) ? byTime.get(t) : null)),
                            borderColor: safeColor(v.color),
                            backgroundColor: safeColor(v.color),
                            tension: 0.3,
                            spanGaps: true,
                            pointRadius: 4,
                            borderWidth: 2,
                        };
                    }),
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: { mode: 'index', intersect: false },
                    plugins: {
                        legend: { labels: { color: muted, usePointStyle: true } },
                        tooltip: { callbacks: { label: (ctx) => `${ctx.dataset.label}: ${formatPrice(ctx.parsed.y)}` } },
                    },
                    scales: {
                        x: { ticks: { color: muted, maxRotation: 0, autoSkip: true }, grid: { color: grid } },
                        y: { ticks: { color: muted, callback: (v) => formatPrice(v) }, grid: { color: grid } },
                    },
                },
            });
        } catch (error) {
            canvas.classList.add('d-none');
            empty.textContent = 'Could not load price history.';
            empty.classList.remove('d-none');
        }
    },
};

/* ---------- boot ------------------------------------------------------- */
document.addEventListener('DOMContentLoaded', () => {
    Theme.init();
    Wishlist.init();
    initBackToTop();
    initReveal();
});