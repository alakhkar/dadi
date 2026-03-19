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

  /* ── Cookie utilities ── */
  function getCookie(name) {
    return document.cookie.split(';').map(c => c.trim())
      .find(c => c.startsWith(name + '='))?.split('=')[1] || null;
  }
  function setCookie(name, value, maxAge) {
    document.cookie = `${name}=${value}; path=/; max-age=${maxAge}; SameSite=Lax`;
  }
  function deleteCookie(name) {
    document.cookie = `${name}=; path=/; max-age=0; SameSite=Lax`;
  }
  function getLoggedInEmail() {
    const val = getCookie('dadi_user');
    return val ? decodeURIComponent(val) : null;
  }

  /* ── Stable guest cookie — prevents "not authorized" on WebSocket reconnects ── */
  if (!getCookie('dadi_guest') && !getCookie('dadi_user')) {
    const gid = 'guest_' + Math.random().toString(36).slice(2, 10);
    setCookie('dadi_guest', gid, 86400);
  }

  /* ══════════════════════════════════════════
     AUTH POPUP MODAL
  ══════════════════════════════════════════ */

  let popupOpen = false;
  let popupDismissed = false;

  function showPopup() {
    if (popupOpen || popupDismissed || getLoggedInEmail()) return;
    popupOpen = true;
    buildPopup();
  }

  function dismissPopup() {
    const backdrop = document.getElementById('dadi-auth-backdrop');
    if (backdrop) {
      backdrop.style.transition = 'opacity 0.2s';
      backdrop.style.opacity = '0';
      setTimeout(() => backdrop.remove(), 250);
    }
    popupOpen = false;
    popupDismissed = true;
  }

  function buildPopup() {
    if (document.getElementById('dadi-auth-backdrop')) return;

    const backdrop = document.createElement('div');
    backdrop.id = 'dadi-auth-backdrop';

    const modal = document.createElement('div');
    modal.id = 'dadi-auth-modal';

    modal.innerHTML = `
      <div id="dadi-step-email">
        <div class="dadi-modal-header">
          <img src="/public/logo_dark.png" alt="Dadi" class="dadi-modal-logo" />
          <h2 class="dadi-modal-title">Save your chats with Dadi</h2>
          <p class="dadi-modal-subtitle">
            You're chatting as a guest — your conversations disappear when you leave.
            Sign in with your email so Dadi can remember you.
          </p>
        </div>
        <div id="dadi-email-err" class="dadi-modal-error" style="display:none"></div>
        <input id="dadi-email-inp" type="email" placeholder="Your email address" class="dadi-modal-input" autocomplete="email" />
        <button id="dadi-send-btn" class="dadi-modal-btn-primary">Send Code</button>
        <button id="dadi-guest-btn" class="dadi-modal-btn-ghost">Continue as Guest</button>
      </div>

      <div id="dadi-step-otp" style="display:none">
        <div class="dadi-modal-header">
          <img src="/public/logo_dark.png" alt="Dadi" class="dadi-modal-logo" />
          <h2 class="dadi-modal-title">Enter your code</h2>
          <p id="dadi-otp-subtitle" class="dadi-modal-subtitle">
            Dadi sent a 6-digit code to your email.
          </p>
        </div>
        <div id="dadi-otp-err" class="dadi-modal-error" style="display:none"></div>
        <input id="dadi-otp-inp" type="text" placeholder="6-digit code" maxlength="6"
          class="dadi-modal-input dadi-otp-input" inputmode="numeric" autocomplete="one-time-code" />
        <button id="dadi-verify-btn" class="dadi-modal-btn-primary">Verify</button>
        <button id="dadi-back-btn" class="dadi-modal-btn-ghost">Change email</button>
      </div>
    `;

    backdrop.appendChild(modal);
    document.documentElement.appendChild(backdrop);

    let pendingEmail = '';

    setTimeout(() => {
      const inp = document.getElementById('dadi-email-inp');
      if (inp) inp.focus();
    }, 80);

    document.getElementById('dadi-otp-inp').addEventListener('input', function () {
      this.value = this.value.replace(/\D/g, '');
    });

    document.getElementById('dadi-email-inp').addEventListener('keydown', e => { if (e.key === 'Enter') sendCode(); });
    document.getElementById('dadi-otp-inp').addEventListener('keydown', e => { if (e.key === 'Enter') verifyCode(); });

    document.getElementById('dadi-send-btn').addEventListener('click', sendCode);
    document.getElementById('dadi-verify-btn').addEventListener('click', verifyCode);
    document.getElementById('dadi-guest-btn').addEventListener('click', dismissPopup);
    document.getElementById('dadi-back-btn').addEventListener('click', () => {
      document.getElementById('dadi-step-otp').style.display = 'none';
      document.getElementById('dadi-step-email').style.display = 'block';
      document.getElementById('dadi-email-err').style.display = 'none';
      document.getElementById('dadi-email-inp').value = pendingEmail;
      setTimeout(() => document.getElementById('dadi-email-inp').focus(), 50);
    });

    backdrop.addEventListener('click', e => { if (e.target === backdrop) dismissPopup(); });

    function setBtn(id, loading, label) {
      const b = document.getElementById(id);
      b.disabled = loading;
      b.style.opacity = loading ? '0.6' : '1';
      b.textContent = loading ? 'Please wait…' : label;
    }

    async function sendCode() {
      const email = document.getElementById('dadi-email-inp').value.trim().toLowerCase();
      const errEl = document.getElementById('dadi-email-err');
      errEl.style.display = 'none';

      if (!email || !email.includes('@') || !email.split('@')[1]?.includes('.')) {
        errEl.textContent = 'Please enter a valid email address.';
        errEl.style.display = 'block';
        return;
      }

      setBtn('dadi-send-btn', true, 'Send Code');
      try {
        const res = await fetch('/auth/request-otp', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email }),
        });
        const data = await res.json();
        if (!res.ok) {
          errEl.textContent = data.error || 'Something went wrong. Please try again.';
          errEl.style.display = 'block';
          return;
        }
        pendingEmail = email;
        document.getElementById('dadi-otp-subtitle').textContent =
          `Dadi sent a 6-digit code to ${email}`;
        document.getElementById('dadi-step-email').style.display = 'none';
        document.getElementById('dadi-step-otp').style.display = 'block';
        setTimeout(() => document.getElementById('dadi-otp-inp').focus(), 60);
      } catch (_) {
        errEl.textContent = 'Network error — please try again.';
        errEl.style.display = 'block';
      } finally {
        setBtn('dadi-send-btn', false, 'Send Code');
      }
    }

    async function verifyCode() {
      const code = document.getElementById('dadi-otp-inp').value.trim();
      const errEl = document.getElementById('dadi-otp-err');
      errEl.style.display = 'none';

      if (code.length !== 6) {
        errEl.textContent = 'Please enter the full 6-digit code.';
        errEl.style.display = 'block';
        return;
      }

      setBtn('dadi-verify-btn', true, 'Verify');
      try {
        const res = await fetch('/auth/verify-otp', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email: pendingEmail, code }),
        });
        const data = await res.json();
        if (!res.ok) {
          errEl.textContent = data.error || 'Invalid code. Please try again.';
          errEl.style.display = 'block';
          return;
        }
        setCookie('dadi_user', encodeURIComponent(data.email), 31536000);
        deleteCookie('dadi_guest');
        localStorage.removeItem('access_token');
        window.location.href = '/';
      } catch (_) {
        errEl.textContent = 'Network error — please try again.';
        errEl.style.display = 'block';
      } finally {
        setBtn('dadi-verify-btn', false, 'Verify');
      }
    }
  }

  /* ── Popup trigger ──
     Show the sign-in prompt after the user has had time to experience the chat.
     Timer fires 20 seconds after page load — simple and reliable. ── */
  setTimeout(showPopup, 20000);

  /* ══════════════════════════════════════════
     USER BADGE — top-right email + sign out
  ══════════════════════════════════════════ */
  const loggedEmail = getLoggedInEmail();

  if (loggedEmail) {
    function shortEmail(e) {
      if (e.length <= 26) return e;
      const [u, d] = e.split('@');
      return (u.length > 10 ? u.slice(0, 8) + '…' : u) + '@' + d;
    }

    function buildUserBadge() {
      if (document.getElementById('dadi-user-badge')) return;

      const badge = document.createElement('div');
      badge.id = 'dadi-user-badge';
      badge.innerHTML = `
        <button id="dadi-badge-btn" title="${loggedEmail}">
          <span class="dadi-badge-icon">👤</span>
          <span id="dadi-badge-label">${shortEmail(loggedEmail)}</span>
          <span class="dadi-badge-caret">▾</span>
        </button>
        <div id="dadi-badge-menu">
          <div class="dadi-badge-email-full">${loggedEmail}</div>
          <button id="dadi-signout-btn">Sign Out</button>
        </div>
      `;
      document.documentElement.appendChild(badge);

      const menu = document.getElementById('dadi-badge-menu');
      document.getElementById('dadi-badge-btn').addEventListener('click', e => {
        e.stopPropagation();
        menu.style.display = menu.style.display === 'block' ? 'none' : 'block';
      });
      document.addEventListener('click', () => { menu.style.display = 'none'; });
      document.getElementById('dadi-signout-btn').addEventListener('click', () => {
        deleteCookie('dadi_user');
        localStorage.removeItem('access_token');
        window.location.href = '/';
      });
    }

    buildUserBadge();
    const badgeObs = new MutationObserver(buildUserBadge);
    badgeObs.observe(document.documentElement, { childList: true });
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

})();
