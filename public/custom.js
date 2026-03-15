/* ══════════════════════════════════════════════
   DADI AI — custom.js
   ══════════════════════════════════════════════ */
(function () {

  /* ── Loading overlay — hides page flash while header auth completes ──
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

  /* ── Cookie helpers ── */
  function getCookie(name) {
    return document.cookie.split(';').map(c => c.trim())
      .find(c => c.startsWith(name + '='))?.split('=')[1] || null;
  }

  function setCookie(name, value, maxAge) {
    document.cookie = `${name}=${value}; path=/; max-age=${maxAge}; SameSite=Lax`;
  }

  function clearCookie(name) {
    document.cookie = `${name}=; path=/; max-age=0; SameSite=Lax`;
  }

  /* ── Stable guest cookie — prevents "not authorized" on WebSocket reconnects ── */
  if (!getCookie('dadi_guest') && !getCookie('dadi_user')) {
    const gid = 'guest_' + Math.random().toString(36).slice(2, 10);
    setCookie('dadi_guest', gid, 86400);
  }

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

  /* ══════════════════════════════════════════════
     LOGIN POPUP — all styles inline (no CSS class dependency)
     ══════════════════════════════════════════════ */

  var S = {
    backdrop: 'position:fixed;inset:0;background:rgba(0,0,0,0.55);z-index:100000;display:flex;align-items:center;justify-content:center;font-family:sans-serif;',
    modal:    'background:#FEF0E7;border-radius:16px;padding:2rem 2.25rem;width:100%;max-width:420px;box-shadow:0 8px 40px rgba(0,0,0,0.25);display:flex;flex-direction:column;gap:0.75rem;box-sizing:border-box;',
    title:    'margin:0 0 0.25rem;font-size:1.4rem;color:#8B1A1A;font-weight:700;font-family:"Playfair Display",serif;',
    sub:      'margin:0 0 0.5rem;font-size:0.95rem;color:#555;',
    input:    'padding:0.65rem 0.9rem;border:1.5px solid #ccc;border-radius:8px;font-size:1rem;outline:none;font-family:sans-serif;background:#fff;box-sizing:border-box;width:100%;',
    otpInput: 'padding:0.65rem 0.9rem;border:1.5px solid #ccc;border-radius:8px;font-size:1.4rem;outline:none;font-family:sans-serif;background:#fff;box-sizing:border-box;width:100%;letter-spacing:0.35em;text-align:center;',
    err:      'margin:0;min-height:1.2em;color:#c0392b;font-size:0.875rem;',
    btnPri:   'padding:0.7rem 1rem;background:#8B1A1A;color:#fff;border:none;border-radius:8px;font-size:1rem;font-family:"Playfair Display",serif;cursor:pointer;width:100%;',
    btnGhost: 'padding:0.5rem 1rem;background:transparent;color:#8B1A1A;border:1.5px solid #8B1A1A;border-radius:8px;font-size:0.9rem;font-family:"Playfair Display",serif;cursor:pointer;width:100%;',
  };

  function showLoginPopup() {
    if (document.getElementById('dadi-login-popup')) return;

    const backdrop = document.createElement('div');
    backdrop.id = 'dadi-login-popup';
    backdrop.style.cssText = S.backdrop;

    const modal = document.createElement('div');
    modal.style.cssText = S.modal;

    function closePopup() { backdrop.remove(); }

    /* ── Panel 1: Email input ── */
    function showEmailPanel() {
      modal.innerHTML = '';

      const title = document.createElement('h2');
      title.style.cssText = S.title;
      title.textContent = 'Save your chats with Dadi';

      const sub = document.createElement('p');
      sub.style.cssText = S.sub;
      sub.textContent = 'Sign up with just your email — no password. Dadi will remember you.';

      const input = document.createElement('input');
      input.type = 'email';
      input.placeholder = 'your@email.com';
      input.style.cssText = S.input;
      input.addEventListener('focus', () => { input.style.borderColor = '#8B1A1A'; });
      input.addEventListener('blur',  () => { input.style.borderColor = '#ccc'; });

      const err = document.createElement('p');
      err.style.cssText = S.err;

      const btnSend = document.createElement('button');
      btnSend.textContent = 'Send Code';
      btnSend.style.cssText = S.btnPri;

      const btnGuest = document.createElement('button');
      btnGuest.textContent = 'Continue as Guest';
      btnGuest.style.cssText = S.btnGhost;

      btnSend.addEventListener('click', async () => {
        const email = input.value.trim().toLowerCase();
        if (!email || !email.includes('@') || !email.split('@')[1]?.includes('.')) {
          err.textContent = 'Please enter a valid email address.';
          return;
        }
        btnSend.disabled = true;
        btnSend.style.opacity = '0.6';
        btnSend.textContent = 'Sending…';
        err.textContent = '';
        try {
          const res = await fetch('/auth/request-otp', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email }),
          });
          const data = await res.json();
          if (data.ok) {
            showOtpPanel(email);
          } else {
            err.textContent = data.error || 'Something went wrong. Try again.';
            btnSend.disabled = false;
            btnSend.style.opacity = '1';
            btnSend.textContent = 'Send Code';
          }
        } catch (_) {
          err.textContent = 'Network error. Please try again.';
          btnSend.disabled = false;
          btnSend.style.opacity = '1';
          btnSend.textContent = 'Send Code';
        }
      });

      input.addEventListener('keydown', (e) => { if (e.key === 'Enter') btnSend.click(); });
      btnGuest.addEventListener('click', closePopup);

      modal.append(title, sub, input, err, btnSend, btnGuest);
      setTimeout(() => input.focus(), 50);
    }

    /* ── Panel 2: OTP input ── */
    function showOtpPanel(email) {
      modal.innerHTML = '';

      const title = document.createElement('h2');
      title.style.cssText = S.title;
      title.textContent = 'Enter your code';

      const sub = document.createElement('p');
      sub.style.cssText = S.sub;
      sub.textContent = 'Dadi sent a 6-digit code to ' + email;

      const input = document.createElement('input');
      input.type = 'text';
      input.inputMode = 'numeric';
      input.maxLength = 6;
      input.placeholder = '123456';
      input.style.cssText = S.otpInput;
      input.addEventListener('focus', () => { input.style.borderColor = '#8B1A1A'; });
      input.addEventListener('blur',  () => { input.style.borderColor = '#ccc'; });

      const err = document.createElement('p');
      err.style.cssText = S.err;

      const btnVerify = document.createElement('button');
      btnVerify.textContent = 'Verify';
      btnVerify.style.cssText = S.btnPri;

      const btnBack = document.createElement('button');
      btnBack.textContent = 'Change Email';
      btnBack.style.cssText = S.btnGhost;

      btnVerify.addEventListener('click', async () => {
        const code = input.value.trim();
        if (code.length < 6) {
          err.textContent = 'Please enter the full 6-digit code.';
          return;
        }
        btnVerify.disabled = true;
        btnVerify.style.opacity = '0.6';
        btnVerify.textContent = 'Verifying…';
        err.textContent = '';
        try {
          const res = await fetch('/auth/verify-otp', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, code }),
          });
          const data = await res.json();
          if (data.ok) {
            setCookie('dadi_user', encodeURIComponent(email), 31536000);
            localStorage.removeItem('access_token');
            closePopup();
            window.location.href = '/';
          } else {
            err.textContent = data.error || 'Wrong code. Try again.';
            btnVerify.disabled = false;
            btnVerify.style.opacity = '1';
            btnVerify.textContent = 'Verify';
          }
        } catch (_) {
          err.textContent = 'Network error. Please try again.';
          btnVerify.disabled = false;
          btnVerify.style.opacity = '1';
          btnVerify.textContent = 'Verify';
        }
      });

      input.addEventListener('keydown', (e) => { if (e.key === 'Enter') btnVerify.click(); });
      btnBack.addEventListener('click', showEmailPanel);

      modal.append(title, sub, input, err, btnVerify, btnBack);
      setTimeout(() => input.focus(), 50);
    }

    showEmailPanel();
    backdrop.appendChild(modal);
    document.body.appendChild(backdrop);
  }

  /* ── Popup trigger — detects [](/show-login-popup) sent by backend ── */
  var popupTriggered = false;
  new MutationObserver(() => {
    if (popupTriggered) return;
    if (getCookie('dadi_user')) return; // don't show to logged-in users on thread replay
    var link = document.querySelector('a[href="/show-login-popup"]');
    if (!link) return;
    popupTriggered = true;
    showLoginPopup();
  }).observe(document.body, { childList: true, subtree: true });

  /* ══════════════════════════════════════════════
     USER EMAIL BADGE — top-right, all styles inline
     ══════════════════════════════════════════════ */

  function injectUserBadge() {
    if (document.getElementById('dadi-user-badge')) return;
    var email = getCookie('dadi_user');
    if (!email) return;

    var decoded = decodeURIComponent(email);

    var badge = document.createElement('div');
    badge.id = 'dadi-user-badge';
    badge.style.cssText = 'position:fixed;top:14px;right:16px;z-index:99999;background:#8B1A1A;color:#fff;padding:0.3rem 0.75rem;border-radius:20px;font-size:0.8rem;font-family:sans-serif;cursor:pointer;white-space:nowrap;max-width:220px;overflow:hidden;text-overflow:ellipsis;user-select:none;box-shadow:0 2px 8px rgba(0,0,0,0.15);';
    badge.textContent = decoded;

    var menu = document.createElement('div');
    menu.style.cssText = 'position:absolute;top:calc(100% + 6px);right:0;background:#FEF0E7;border:1px solid #ddd;border-radius:8px;box-shadow:0 4px 16px rgba(0,0,0,0.12);min-width:120px;overflow:hidden;z-index:100001;display:none;';

    var signOut = document.createElement('button');
    signOut.textContent = 'Sign Out';
    signOut.style.cssText = 'display:block;width:100%;padding:0.6rem 1rem;background:none;border:none;text-align:left;font-family:sans-serif;font-size:0.875rem;color:#8B1A1A;cursor:pointer;';
    signOut.addEventListener('mouseover', () => { signOut.style.background = '#f5e6dc'; });
    signOut.addEventListener('mouseout',  () => { signOut.style.background = 'none'; });
    signOut.addEventListener('click', (e) => {
      e.stopPropagation();
      clearCookie('dadi_user');
      clearCookie('dadi_guest');
      window.location.href = '/';
    });

    menu.appendChild(signOut);
    badge.appendChild(menu);

    badge.addEventListener('click', (e) => {
      e.stopPropagation();
      menu.style.display = menu.style.display === 'none' ? 'block' : 'none';
    });
    document.addEventListener('click', () => { menu.style.display = 'none'; });

    document.documentElement.appendChild(badge);
  }

  injectUserBadge();
  new MutationObserver(injectUserBadge).observe(document.documentElement, { childList: true });

})();
