(() => {
    'use strict';

    function initProductSearch(root) {
        const form = root.querySelector('[data-search-form]');
        const input = root.querySelector('[data-search-input]');
        const clearButton = root.querySelector('[data-clear-search]');
        const categoryInput = root.querySelector('[data-category-input]');
        const pills = [...root.querySelectorAll('[data-category]')];
        const productsContainer = root.nextElementSibling?.matches('[data-products-container]')
            ? root.nextElementSibling : document.querySelector('[data-products-container]');
        if (!form || !input || !productsContainer) return;

        const endpoint = root.dataset.endpoint || form.action;
        const historyPath = root.dataset.historyPath || new URL(endpoint, location.origin).pathname;
        const supportsPagination = root.dataset.pagination === 'true';
        let currentCategory = categoryInput?.value || '';
        let activeRequest = null;

        function setLoading(isLoading) {
            productsContainer.setAttribute('aria-busy', String(isLoading));
            productsContainer.classList.toggle('products-loading', isLoading);
            const submit = root.querySelector('[data-search-submit]');
            if (submit) submit.disabled = isLoading;
        }

        function updateClearButton() {
            clearButton?.classList.toggle('d-none', !input.value.trim());
        }

        function updateActivePill() {
            pills.forEach(pill => {
                const active = (pill.dataset.category || '') === currentCategory;
                pill.classList.toggle('active', active);
                pill.setAttribute('aria-pressed', String(active));
            });
        }

        async function loadProducts({ page = null, scroll = false } = {}) {
            activeRequest?.abort();
            const controller = new AbortController();
            activeRequest = controller;
            document.getElementById('searchError')?.remove();
            setLoading(true);

            const params = new URLSearchParams();
            const query = input.value.trim();
            if (query) params.set('q', query);
            if (currentCategory) params.set('category', currentCategory);
            if (supportsPagination && page && page > 1) params.set('page', page);
            params.set('ajax', '1');

            try {
                const url = new URL(endpoint, location.origin);
                url.search = params.toString();
                const response = await fetch(url, {
                    headers: { 'X-Requested-With': 'XMLHttpRequest' }, signal: controller.signal
                });
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                const html = await response.text();
                if (controller !== activeRequest) return;
                productsContainer.innerHTML = html;
                params.delete('ajax');
                const queryString = params.toString();
                history.replaceState({}, '', queryString ? `${historyPath}?${queryString}` : historyPath);
                updateClearButton();
                if (scroll) productsContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
            } catch (error) {
                if (error.name === 'AbortError') return;
                const notice = document.createElement('p');
                notice.id = 'searchError';
                notice.className = 'alert alert-warning';
                notice.role = 'alert';
                notice.textContent = 'Chưa tải được kết quả. Vui lòng thử lại.';
                productsContainer.before(notice);
                console.error('Không thể tải danh sách sản phẩm:', error);
            } finally {
                if (controller === activeRequest) {
                    activeRequest = null;
                    setLoading(false);
                }
            }
        }

        form.addEventListener('submit', event => {
            event.preventDefault();
            loadProducts();
            input.blur();
        });
        input.addEventListener('input', updateClearButton);
        clearButton?.addEventListener('click', () => {
            input.value = '';
            updateClearButton();
            loadProducts();
            input.focus();
        });
        pills.forEach(pill => {
            pill.addEventListener('click', event => {
                event.preventDefault();
                currentCategory = pill.dataset.category || '';
                if (categoryInput) categoryInput.value = currentCategory;
                updateActivePill();
                loadProducts();
            });
        });
        productsContainer.addEventListener('click', event => {
            const pageLink = event.target.closest('.page-link-ajax');
            if (pageLink && supportsPagination) {
                event.preventDefault();
                if (pageLink.closest('.page-item')?.classList.contains('disabled')) return;
                loadProducts({ page: Number(pageLink.dataset.page) || 1, scroll: true });
                return;
            }
            if (event.target.closest('.btn-clear-filters')) {
                event.preventDefault();
                input.value = '';
                currentCategory = '';
                if (categoryInput) categoryInput.value = '';
                updateClearButton();
                updateActivePill();
                loadProducts();
            }
        });
    }

    document.querySelectorAll('[data-product-search]').forEach(initProductSearch);
})();
