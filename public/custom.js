/* ══════════════════════════════════════════════
   DADI AI — custom.js
   ══════════════════════════════════════════════ */
(function () {

  /* ── Loading overlay — fades out once the chat textarea mounts ── */
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
