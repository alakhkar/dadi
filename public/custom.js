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

  /* ── Skip login button — injected into Chainlit's login form ── */
  function isLoginPage() {
    return !!document.querySelector('form input[type="password"]');
  }

  function injectSkipButton() {
    if (document.getElementById('dadi-skip-wrapper')) return;
    const submitBtn = document.querySelector('button[type="submit"]');
    if (!submitBtn) return;

    const wrapper = document.createElement('div');
    wrapper.id = 'dadi-skip-wrapper';
    wrapper.style.cssText = 'display:flex;align-items:center;gap:0.6rem;margin-top:0.85rem;justify-content:center;';

    const btn = document.createElement('button');
    btn.type = 'button';
    btn.textContent = 'Continue as Guest →';
    btn.style.cssText = [
      'background:none',
      'border:1px solid rgba(139,26,26,0.35)',
      'border-radius:999px',
      'color:#8B1A1A',
      'font-size:0.78rem',
      'padding:0.35rem 1rem',
      'cursor:pointer',
      'font-style:italic',
      'transition:background 0.2s',
      'white-space:nowrap',
    ].join(';');
    btn.onmouseenter = () => { btn.style.background = 'rgba(139,26,26,0.06)'; };
    btn.onmouseleave = () => { btn.style.background = 'none'; };

    const note = document.createElement('span');
    note.textContent = "Chat history won't be saved.";
    note.style.cssText = 'font-size:0.67rem;color:#9e7a5a;font-style:italic;line-height:1.3;';

    btn.onclick = async () => {
      btn.disabled = true;
      btn.textContent = 'Entering…';
      const guestId = 'guest_' + Math.random().toString(36).slice(2, 8);
      try {
        const resp = await fetch('/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
          body: new URLSearchParams({ username: guestId, password: 'guest', grant_type: 'password' }),
          credentials: 'include',
        });
        if (resp.ok) {
          const data = await resp.json();
          if (data.access_token) localStorage.setItem('access_token', data.access_token);
          window.location.href = '/';
        } else {
          btn.textContent = 'Continue as Guest →';
          btn.disabled = false;
        }
      } catch (_) {
        btn.textContent = 'Continue as Guest →';
        btn.disabled = false;
      }
    };

    wrapper.appendChild(btn);
    wrapper.appendChild(note);
    const formEl = submitBtn.closest('form');
    if (formEl) formEl.appendChild(wrapper);
    else submitBtn.parentNode.insertAdjacentElement('afterend', wrapper);
  }

  // Poll until the login form appears, then inject the button
  const skipPoll = setInterval(() => {
    if (isLoginPage()) injectSkipButton();
    if (document.getElementById('dadi-skip-wrapper')) clearInterval(skipPoll);
  }, 200);
  setTimeout(() => clearInterval(skipPoll), 10000);

  // Re-inject if Chainlit re-renders the form (SPA navigation)
  new MutationObserver(() => {
    if (isLoginPage()) injectSkipButton();
  }).observe(document.body, { childList: true, subtree: true });

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
