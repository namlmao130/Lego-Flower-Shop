// Attach the session token only to same-origin requests that change state.
(() => {
    const token = document.querySelector('meta[name="csrf-token"]')?.content;
    const originalFetch = window.fetch;
    window.fetch = (input, options = {}) => {
        const url = new URL(input instanceof Request ? input.url : input, location.href);
        const method = (options.method || (input instanceof Request ? input.method : 'GET')).toUpperCase();
        if (token && url.origin === location.origin && !['GET', 'HEAD', 'OPTIONS'].includes(method)) {
            const headers = new Headers(options.headers || (input instanceof Request ? input.headers : undefined));
            headers.set('X-CSRFToken', token);
            options = { ...options, headers };
        }
        return originalFetch.call(window, input, options);
    };
})();
