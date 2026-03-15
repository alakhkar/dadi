/* ══════════════════════════════════════════════
   DADI AI — custom.js
   ══════════════════════════════════════════════ */
(function () {

  /* ── Loading overlay — hides login page flash while header auth completes ──
     The logo (html::before, z-index 99999) shows above it, creating a branded
     loading screen. Fades out once the chat textarea mounts. ── */
  const overlay = document.createElement('div');
  overlay.id = 'dadi-overlay';
  overlay.style.cssText = 'position:fixed;inset:0;background:#FDF6F0;z-index:99998;';
  document.documentElement.appendChild(overlay);

  function fadeOverlay() {
    overlay.style.transition = 'opacity 0.3s';
    overlay.style.opacity = '0';
    setTimeout(() => overlay.remove(), 350);
  }

  const overlayObs = new MutationObserver(() => {
    if (document.querySelector('textarea')) {
      fadeOverlay();
      overlayObs.disconnect();
    }
  });
  overlayObs.observe(document.body, { childList: true, subtree: true });
  setTimeout(fadeOverlay, 3000); // hard fallback

  /* ── Stable guest cookie — prevents "not authorized" on WebSocket reconnects ── */
  function getCookie(name) {
    return document.cookie.split(';').map(c => c.trim())
      .find(c => c.startsWith(name + '='))?.split('=')[1] || null;
  }
  if (!getCookie('dadi_guest') && !getCookie('dadi_user')) {
    const gid = 'guest_' + Math.random().toString(36).slice(2, 10);
    document.cookie = `dadi_guest=${gid}; path=/; max-age=86400; SameSite=Lax`;
  }

  /* ── Session activation — auto-fires when Dadi's OTP success message appears ── */
  function activateSession(email) {
    document.cookie = `dadi_user=${encodeURIComponent(email)}; path=/; max-age=31536000; SameSite=Lax`;
    localStorage.removeItem('access_token');
    window.location.href = '/';
  }

  // Auto-detect activation link in chat messages and handle without user click
  let activating = false;
  new MutationObserver(() => {
    if (activating) return;
    const link = document.querySelector('a[href*="/activate-session"]');
    if (!link) return;
    try {
      const email = new URL(link.href).searchParams.get('email');
      if (!email) return;
      activating = true;
      setTimeout(() => activateSession(email), 1500); // brief delay so user reads Dadi's message
    } catch (_) {}
  }).observe(document.body, { childList: true, subtree: true });

  // Manual click fallback
  document.addEventListener('click', function (e) {
    const link = e.target.closest('a');
    if (!link) return;
    try {
      const url = new URL(link.href);
      if (!url.pathname.startsWith('/activate-session')) return;
      e.preventDefault();
      const email = url.searchParams.get('email');
      if (email) activateSession(email);
    } catch (_) {}
  }, true);

  /* ── Persistent logo — re-inject into <html> if ever removed ── */
  function ensureLogo() {
    if (document.getElementById('dadi-chat-logo')) return;
    const el = document.createElement('div');
    el.id = 'dadi-chat-logo';
    el.style.cssText = 'position:fixed;top:15px;left:50%;transform:translateX(-50%);z-index:99999;pointer-events:none;';
    const img = document.createElement('img');
    img.src = '/public/logo_dark.png';
    img.alt = 'Dadi';
    img.style.cssText = 'height:72px;width:auto;object-fit:contain;display:block;';
    el.appendChild(img);
    document.documentElement.appendChild(el);
  }
  ensureLogo();
  // Watch direct children of <html> — re-inject if logo is removed
  new MutationObserver(ensureLogo).observe(document.documentElement, { childList: true });

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
