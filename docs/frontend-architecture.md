# Frontend architecture

The storefront uses server-rendered Jinja templates with progressively enhanced JavaScript. The server-rendered form and links must remain usable when JavaScript is unavailable.

## Directory structure

```text
templates/
├── base.html                    # Global document shell and extension blocks
├── components/                  # Reusable Jinja UI components
│   ├── site_header.html
│   ├── site_footer.html
│   ├── chat_widget.html
│   ├── confirm_modal.html
│   ├── cart_toast.html
│   └── product_search.html
└── _product_list_partial.html   # AJAX-compatible product results

static/
├── css/
│   ├── style.css                # Existing storefront styles
│   ├── app-shell.css            # Global shell and floating component styles
│   └── design-system.css        # Tokens, shared states and accessibility rules
└── js/
    ├── app-shell.js              # Global navigation, chat, modal and toast behavior
    └── components/
        └── product-search.js     # Progressive enhancement for product filtering
```

## Template extension points

- `title`: page title.
- `head_extra`: page-only styles, preload hints or metadata.
- `content`: page markup.
- `page_scripts`: deferred page-only scripts.

Load shared assets from `base.html`. Load feature-specific JavaScript through `page_scripts` rather than placing a second implementation inline in each page.

## Component conventions

- Use `data-*` attributes as JavaScript hooks. Do not couple behavior to cosmetic class names.
- Keep a real `action` and `href` on forms and links so navigation still works without JavaScript.
- Provide default, loading, disabled, error and empty states for interactive components.
- Use the variables in `design-system.css` before introducing new hardcoded colors, radii, shadows or motion durations.
- Use `:focus-visible`, semantic labels and ARIA only when native HTML does not already express the behavior.
- Respect `prefers-reduced-motion` for non-essential animation.

## Product search contract

`components/product_search.html` accepts these Jinja variables:

- `search_endpoint`: endpoint URL used by the form and AJAX request.
- `history_path`: browser URL updated after a successful request.
- `search_spacing`: optional Bootstrap spacing class.
- `enable_pagination`: whether AJAX pagination links are handled.

The endpoint must return `_product_list_partial.html` when `ajax=1` is present. The JavaScript cancels stale requests, exposes a loading state and keeps the URL synchronized with the visible results.

## Migration direction

When editing a large template, move one self-contained feature at a time into `templates/components`, `static/js/components`, or a page-level asset. Avoid large visual rewrites that mix structural refactoring with behavior changes.
