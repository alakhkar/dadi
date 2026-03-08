/* ══════════════════════════════════════════════
   DADI AI — custom.js
   ══════════════════════════════════════════════ */
(function () {

  /* ── Stable guest cookie — prevents "not authorized" on WebSocket reconnects ── */
  function getCookie(name) {
    return document.cookie.split(';').map(c => c.trim())
      .find(c => c.startsWith(name + '='))?.split('=')[1] || null;
  }
  if (!getCookie('dadi_guest') && !getCookie('dadi_user')) {
    const gid = 'guest_' + Math.random().toString(36).slice(2, 10);
    document.cookie = `dadi_guest=${gid}; path=/; max-age=86400; SameSite=Lax`;
  }

  /* ── Session activation link — set cookie client-side, clear old JWT, reload ── */
  document.addEventListener('click', function (e) {
    const link = e.target.closest('a');
    if (!link) return;
    try {
      const url = new URL(link.href);
      if (!url.pathname.startsWith('/activate-session')) return;
      e.preventDefault();
      const email = url.searchParams.get('email');
      if (!email) return;
      document.cookie = `dadi_user=${encodeURIComponent(email)}; path=/; max-age=31536000; SameSite=Lax`;
      localStorage.removeItem('access_token');
      window.location.href = '/';
    } catch (_) {}
  }, true);

  /* ── Hide readme button ── */
  function hideReadmeButton() {
    document.querySelectorAll('a[href="/readme"], a[href*="readme"]').forEach(el => {
      el.style.display = 'none';
    });
    document.querySelectorAll('button, a').forEach(el => {
      if (el.textContent.trim().toLowerCase() === 'readme') el.style.display = 'none';
    });
  }

  new MutationObserver(hideReadmeButton).observe(document.body, { childList: true, subtree: true });

})();
