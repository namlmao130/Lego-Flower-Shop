# Admin UI architecture

The admin area uses one shared Jinja shell and a small set of reusable visual patterns.

## Files

- `templates/admin/base.html`: sidebar, top bar, flash messages and shared asset loading.
- `static/css/admin.css`: design tokens, layout, forms, tables and responsive rules.
- `static/js/admin-shell.js`: mobile navigation and the unread-chat badge.
- `templates/admin/*.html`: page content only, implemented through Jinja blocks.

## Template blocks

Admin pages extend `admin/base.html` and can define:

- `title`: browser title.
- `page_title`: visible page heading.
- `page_description`: one short supporting sentence.
- `page_actions`: primary actions in the top bar.
- `content`: page content.
- `head_extra`: page-only styles when a complex screen needs them.
- `scripts`: page-only behavior.

## Reusable classes

- `.admin-panel`: standard white surface.
- `.admin-panel-header` and `.admin-panel-body`: panel structure.
- `.admin-filter-panel`: search and filter surface.
- `.admin-form-card`: constrained form layout.
- `.admin-table`: consistent data-table treatment.
- `.admin-stat`: small count or metadata pill.
- `.btn-admin-primary`: primary Lego Flower action.

Use the CSS custom properties at the top of `admin.css` for color, radius, spacing and elevation changes. Avoid adding hardcoded page-level colors unless they represent data status.

## Interaction rules

- Sidebar navigation is keyboard accessible and closes with Escape on small screens.
- The global unread badge polls every 30 seconds and pauses in hidden tabs.
- The admin inbox polls its active thread every 5 seconds and the conversation list every 15 seconds; both requests use in-flight guards and pause in hidden tabs.
- Destructive actions require confirmation and retain the existing server-side POST routes.
