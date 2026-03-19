/* ══════════════════════════════════════════════
   DADI AI — custom.js
   ══════════════════════════════════════════════ */
(function () {

  /* ── Login page styles: white bg + Dadi image column ── */
  const loginStyles = document.createElement('style');
  loginStyles.id = 'dadi-login-styles';
  loginStyles.textContent = `
    html, body, #root { background: #ffffff !important; }

    #dadi-img-col {
      flex-shrink: 0;
      display: flex;
      align-items: flex-end;
      justify-content: center;
    }
    #dadi-img-col img {
      height: 80vh;
      max-height: 600px;
      width: auto;
      object-fit: contain;
      object-position: bottom;
      filter: drop-shadow(-4px 12px 28px rgba(80,20,30,0.18));
      animation: dadi-float 4s ease-in-out infinite;
    }
    @keyframes dadi-float {
      0%, 100% { transform: translateY(0); }
      50%       { transform: translateY(-14px); }
    }
    @media (max-width: 768px) {
      #dadi-img-col { display: none !important; }
    }
  `;
  document.head.appendChild(loginStyles);

  function injectLoginImage() {
    if (document.getElementById('dadi-img-col')) return;
    const form = document.querySelector('form');
    if (!form) return;

    // Find the form's centering/layout ancestor to convert into a side-by-side row
    let container = form.parentElement;
    for (let i = 0; i < 8; i++) {
      if (!container || container === document.body) break;
      const cs = window.getComputedStyle(container);
      if (cs.display === 'flex' || cs.display === 'grid' || cs.minHeight === '100vh') break;
      container = container.parentElement;
    }
    if (!container || container === document.body) container = form.parentElement;

    container.style.cssText = [
      'display:flex', 'flex-direction:row', 'align-items:center',
      'justify-content:center', 'gap:4rem', 'min-height:100vh',
      'padding:2rem', 'background:#ffffff', 'box-sizing:border-box',
    ].join(';');

    const imgCol = document.createElement('div');
    imgCol.id = 'dadi-img-col';
    const img = document.createElement('img');
    img.src = '/public/dadi.png';
    img.alt = 'Dadi';
    imgCol.appendChild(img);
    container.appendChild(imgCol);
  }

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

  /* ── OTP login UI — injected into Chainlit's native login form ──
     Layout after injection:
       [Email field]
       [Send Code button]  ← injected
       [Status message]    ← injected
       [Password/OTP field]
       [Sign In button]
       [Continue as Guest] ← injected
  ── */

  function isLoginPage() {
    return !!document.querySelector('form input[type="password"]');
  }

  function transformLoginForm() {
    if (document.getElementById('dadi-send-code-btn')) return;
    const form = document.querySelector('form');
    if (!form) return;
    const emailInput = form.querySelector('input:not([type="password"])');
    const otpInput   = form.querySelector('input[type="password"]');
    const submitBtn  = form.querySelector('button[type="submit"]');
    if (!emailInput || !otpInput || !submitBtn) return;

    // Repurpose the password field as OTP input
    otpInput.placeholder = '6-digit code from your email';
    otpInput.setAttribute('inputmode', 'numeric');
    otpInput.setAttribute('maxlength', '6');
    otpInput.setAttribute('autocomplete', 'one-time-code');

    // Status line
    const status = document.createElement('p');
    status.id = 'dadi-otp-status';
    status.style.cssText = 'margin:2px 0 6px;font-size:0.8rem;min-height:1.1em;text-align:center;';

    // Send Code button
    const sendBtn = document.createElement('button');
    sendBtn.id = 'dadi-send-code-btn';
    sendBtn.type = 'button';
    sendBtn.textContent = 'Send Code';
    sendBtn.style.cssText = [
      'width:100%', 'padding:10px', 'background:#8B1A1A', 'color:#fff',
      'border:none', 'border-radius:8px', 'font-size:0.9rem', 'cursor:pointer',
      'margin-bottom:4px', 'transition:opacity 0.2s',
    ].join(';');

    sendBtn.onclick = async () => {
      const email = emailInput.value.trim().toLowerCase();
      status.style.color = '#c0392b';
      if (!email || !email.includes('@') || !email.split('@')[1]?.includes('.')) {
        status.textContent = 'Enter a valid email address first.';
        return;
      }
      sendBtn.disabled = true;
      sendBtn.style.opacity = '0.6';
      sendBtn.textContent = 'Sending…';
      status.textContent = '';
      try {
        const resp = await fetch('/auth/request-otp', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email }),
        });
        const data = await resp.json();
        if (resp.ok) {
          status.style.color = '#2e7d32';
          status.textContent = `Code sent to ${email}`;
          sendBtn.textContent = 'Resend Code';
          otpInput.value = '';
          otpInput.focus();
        } else {
          status.textContent = data.error || 'Failed to send code.';
          sendBtn.textContent = 'Send Code';
        }
      } catch (_) {
        status.textContent = 'Network error — please try again.';
        sendBtn.textContent = 'Send Code';
      } finally {
        sendBtn.disabled = false;
        sendBtn.style.opacity = '1';
      }
    };

    // Insert Send Code + status after the email field, before the OTP field.
    // Walk up from each input to find their branch within the nearest common ancestor.
    function branchUnder(ancestor, el) {
      let node = el;
      while (node && node.parentElement !== ancestor) node = node.parentElement;
      return node;
    }
    // Find nearest common ancestor of both inputs
    const emailAncestors = new Set();
    let n = emailInput;
    while (n) { emailAncestors.add(n); n = n.parentElement; }
    let common = otpInput.parentElement;
    while (common && !emailAncestors.has(common)) common = common.parentElement;

    const emailBranch = branchUnder(common || form, emailInput);
    if (emailBranch) {
      emailBranch.insertAdjacentElement('afterend', sendBtn);
      sendBtn.insertAdjacentElement('afterend', status);
    } else {
      submitBtn.insertAdjacentElement('beforebegin', sendBtn);
      submitBtn.insertAdjacentElement('beforebegin', status);
    }

    // Continue as Guest button
    const guestWrapper = document.createElement('div');
    guestWrapper.id = 'dadi-skip-wrapper';
    guestWrapper.style.cssText = 'display:flex;align-items:center;gap:0.6rem;margin-top:0.85rem;justify-content:center;';

    const guestBtn = document.createElement('button');
    guestBtn.type = 'button';
    guestBtn.textContent = 'Continue as Guest →';
    guestBtn.style.cssText = [
      'background:none', 'border:1px solid rgba(139,26,26,0.35)', 'border-radius:999px',
      'color:#8B1A1A', 'font-size:0.78rem', 'padding:0.35rem 1rem', 'cursor:pointer',
      'font-style:italic', 'transition:background 0.2s', 'white-space:nowrap',
    ].join(';');
    guestBtn.onmouseenter = () => { guestBtn.style.background = 'rgba(139,26,26,0.06)'; };
    guestBtn.onmouseleave = () => { guestBtn.style.background = 'none'; };

    const guestNote = document.createElement('span');
    guestNote.textContent = "Chat history won't be saved.";
    guestNote.style.cssText = 'font-size:0.67rem;color:#9e7a5a;font-style:italic;line-height:1.3;';

    guestBtn.onclick = async () => {
      guestBtn.disabled = true;
      guestBtn.textContent = 'Entering…';
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
          guestBtn.textContent = 'Continue as Guest →';
          guestBtn.disabled = false;
        }
      } catch (_) {
        guestBtn.textContent = 'Continue as Guest →';
        guestBtn.disabled = false;
      }
    };

    guestWrapper.appendChild(guestBtn);
    guestWrapper.appendChild(guestNote);
    form.appendChild(guestWrapper);
  }

  // Poll until login form appears, then inject everything
  const loginPoll = setInterval(() => {
    if (isLoginPage()) {
      injectLoginImage();
      transformLoginForm();
    }
    if (document.getElementById('dadi-send-code-btn')) clearInterval(loginPoll);
  }, 200);
  setTimeout(() => clearInterval(loginPoll), 10000);

  // Re-inject on SPA re-renders
  new MutationObserver(() => {
    if (isLoginPage()) {
      injectLoginImage();
      transformLoginForm();
    }
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
