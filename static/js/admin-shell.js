(() => {
    const body = document.body;
    const sidebar = document.getElementById('adminSidebar');
    const toggle = document.getElementById('adminMenuToggle');
    const backdrop = document.getElementById('adminSidebarBackdrop');

    const setSidebar = open => {
        body.classList.toggle('admin-sidebar-open', open);
        toggle?.setAttribute('aria-expanded', String(open));
    };

    toggle?.addEventListener('click', () => setSidebar(!body.classList.contains('admin-sidebar-open')));
    backdrop?.addEventListener('click', () => setSidebar(false));
    sidebar?.querySelectorAll('a').forEach(link => link.addEventListener('click', () => setSidebar(false)));
    document.addEventListener('keydown', event => {
        if (event.key === 'Escape') setSidebar(false);
    });

    let badgeRequestInFlight = false;
    async function updateUnreadBadge() {
        if (document.hidden || badgeRequestInFlight) return;
        badgeRequestInFlight = true;
        try {
            const response = await fetch('/api/admin/chat/unread_count', { headers: { Accept: 'application/json' } });
            if (!response.ok) return;
            const data = await response.json();
            const badge = document.getElementById('adminUnreadChatBadge');
            if (!badge) return;
            const count = Number(data.unread_count || 0);
            badge.textContent = count > 99 ? '99+' : String(count);
            badge.classList.toggle('d-none', count === 0);
        } catch (_) {
            // Badge is non-critical; keep the rest of the admin UI available.
        } finally {
            badgeRequestInFlight = false;
        }
    }

    updateUnreadBadge();
    window.setInterval(updateUnreadBadge, 30000);
    document.addEventListener('visibilitychange', () => {
        if (!document.hidden) updateUnreadBadge();
    });
})();
