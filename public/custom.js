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
     LOGIN POPUP
     ══════════════════════════════════════════════ */

  function showLoginPopup() {
    if (document.getElementById('dadi-login-popup')) return;

    const backdrop = document.createElement('div');
    backdrop.id = 'dadi-login-popup';
    backdrop.className = 'dadi-popup-backdrop';

    const modal = document.createElement('div');
    modal.className = 'dadi-popup-modal';

    function closePopup() {
      backdrop.remove();
    }

    /* ── Panel 1: Email input ── */
    function showEmailPanel() {
      modal.innerHTML = '';

      const title = document.createElement('h2');
      title.className = 'dadi-popup-title';
      title.textContent = 'Save your chats with Dadi';

      const sub = document.createElement('p');
      sub.className = 'dadi-popup-sub';
      sub.textContent = 'Sign up with just your email — no password. Dadi will remember you.';

      const input = document.createElement('input');
      input.type = 'email';
      input.placeholder = 'your@email.com';
      input.className = 'dadi-popup-input';

      const err = document.createElement('p');
      err.className = 'dadi-popup-error';

      const btnSend = document.createElement('button');
      btnSend.textContent = 'Send Code';
      btnSend.className = 'dadi-popup-btn-primary';

      const btnGuest = document.createElement('button');
      btnGuest.textContent = 'Continue as Guest';
      btnGuest.className = 'dadi-popup-btn-ghost';

      btnSend.addEventListener('click', async () => {
        const email = input.value.trim().toLowerCase();
        if (!email || !email.includes('@') || !email.includes('.')) {
          err.textContent = 'Please enter a valid email address.';
          return;
        }
        btnSend.disabled = true;
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
            btnSend.textContent = 'Send Code';
          }
        } catch (_) {
          err.textContent = 'Network error. Please try again.';
          btnSend.disabled = false;
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
      title.className = 'dadi-popup-title';
      title.textContent = 'Enter your code';

      const sub = document.createElement('p');
      sub.className = 'dadi-popup-sub';
      sub.textContent = `Dadi sent a 6-digit code to ${email}`;

      const input = document.createElement('input');
      input.type = 'text';
      input.inputMode = 'numeric';
      input.maxLength = 6;
      input.placeholder = '123456';
      input.className = 'dadi-popup-input dadi-popup-otp-input';

      const err = document.createElement('p');
      err.className = 'dadi-popup-error';

      const btnVerify = document.createElement('button');
      btnVerify.textContent = 'Verify';
      btnVerify.className = 'dadi-popup-btn-primary';

      const btnBack = document.createElement('button');
      btnBack.textContent = 'Change Email';
      btnBack.className = 'dadi-popup-btn-ghost';

      btnVerify.addEventListener('click', async () => {
        const code = input.value.trim();
        if (code.length < 6) {
          err.textContent = 'Please enter the full 6-digit code.';
          return;
        }
        btnVerify.disabled = true;
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
            btnVerify.textContent = 'Verify';
          }
        } catch (_) {
          err.textContent = 'Network error. Please try again.';
          btnVerify.disabled = false;
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
  let popupTriggered = false;
  new MutationObserver(() => {
    if (popupTriggered) return;
    if (getCookie('dadi_user')) return; // don't show to already-logged-in users on thread replay
    const link = document.querySelector('a[href="/show-login-popup"]');
    if (!link) return;
    popupTriggered = true;
    showLoginPopup();
  }).observe(document.body, { childList: true, subtree: true });

  /* ══════════════════════════════════════════════
     USER EMAIL BADGE (top-right, shown when logged in)
     ══════════════════════════════════════════════ */

  function injectUserBadge() {
    if (document.getElementById('dadi-user-badge')) return;
    const email = getCookie('dadi_user');
    if (!email) return;

    const decoded = decodeURIComponent(email);

    const badge = document.createElement('div');
    badge.id = 'dadi-user-badge';
    badge.className = 'dadi-user-badge';
    badge.textContent = decoded;

    const menu = document.createElement('div');
    menu.className = 'dadi-user-menu';
    menu.style.display = 'none';

    const signOut = document.createElement('button');
    signOut.textContent = 'Sign Out';
    signOut.className = 'dadi-user-signout';
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

    document.addEventListener('click', () => {
      menu.style.display = 'none';
    });

    document.documentElement.appendChild(badge);
  }

  injectUserBadge();
  new MutationObserver(injectUserBadge).observe(document.documentElement, { childList: true });

})();
