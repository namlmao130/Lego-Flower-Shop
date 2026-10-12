# Security changes

- All state-changing requests require a session-bound CSRF token. Server-rendered forms include it; `static/js/csrf.js` adds it to same-origin fetch requests. Keep the script in the page head and include a hidden token in any new POST form.
- Order detail, success, cancellation and reorder require ownership. Signed-in customers can access their own orders. Guest orders are available only in the browser session used at checkout (up to 50 recent orders). Existing guest orders without session authorization require contacting the shop. Phone numbers and order codes alone no longer grant access.
- Password reset tokens contain keyed digests instead of the OTP. A password fingerprint and conditional database update make them single-use and invalidate other issued links when the password changes. Previously issued legacy links must be requested again.
- On Render, Secure cookies default to enabled. Check that `SESSION_COOKIE_SECURE` is not explicitly set to false in the dashboard.
- Gunicorn uses one worker with in-memory rate limiting; shared Redis storage enables multiple workers. Memory limits reset on restart and are not shared across multiple service instances. Set `REDIS_URL` for persistent, shared limits.
- `shop.db` is excluded from future Git commits; the local database remains intact. This does not remove copies already present in Git history.

## Remaining operations

Rotate the PostgreSQL credential previously disclosed in chat and update Render's `DATABASE_URL`. Do not paste the new secret into chat. If the tracked SQLite file contained real customer data, decide separately whether to purge Git history; doing so rewrites commits and affects collaborators. No history rewrite or production credential rotation is performed by this code change.
