/* ══════════════════════════════════════════════
   DADI AI — custom.js
   ══════════════════════════════════════════════ */
(function () {

  /* ── Google Analytics ── */
  const _ga = document.createElement('script');
  _ga.async = true;
  _ga.src = 'https://www.googletagmanager.com/gtag/js?id=G-7ZQ5T31FJ8';
  document.head.appendChild(_ga);
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
  gtag('config', 'G-7ZQ5T31FJ8');

  /* ── GA4: track login vs chat page context ── */
  setTimeout(() => {
    gtag('event', 'page_context', {
      page_type: document.querySelector('form input[type="password"]') ? 'login' : 'chat'
    });
  }, 1000);

  /* ── Browser tab title + favicon ── */
  document.title = 'Dadi AI';
  setInterval(() => { if (document.title !== 'Dadi AI') document.title = 'Dadi AI'; }, 500);
  const _favicon = document.createElement('link');
  _favicon.rel = 'icon';
  _favicon.type = 'image/png';
  _favicon.href = '/public/favicon.png';
  document.head.appendChild(_favicon);

  /* ── Login page: white background + replace right-panel image with dadi.png ── */
  const loginCss = document.createElement('style');
  loginCss.textContent = [
    'html,body{background:#ffffff!important;}',
    // Hide the persistent top-center logo on the login page only
    'html.dadi-login::before{display:none!important;}',
    'html.dadi-login #dadi-chat-logo{display:none!important;}',
  ].join('');
  document.head.appendChild(loginCss);

  function styleLoginPage() {
    if (document.getElementById('dadi-page-styled')) return;
    // Chainlit's right panel: <div class="relative hidden bg-muted lg:block overflow-hidden">
    const rightPanel = document.querySelector('div.relative.bg-muted');
    if (!rightPanel) return;

    document.getElementById('dadi-page-styled')?.remove();
    const marker = document.createElement('span');
    marker.id = 'dadi-page-styled';
    marker.style.display = 'none';
    document.body.appendChild(marker);

    // Mark <html> so CSS can hide the logo on the login page
    document.documentElement.classList.add('dadi-login');

    // White background on the panel itself
    rightPanel.style.background = '#ffffff';

    // Swap the image: remove dark filter, show dadi.png
    const img = rightPanel.querySelector('img');
    if (img) {
      img.src = '/public/dadi.png';
      img.alt = 'Dadi';
      img.style.cssText = [
        'position:absolute', 'inset:0', 'height:100%', 'width:100%',
        'object-fit:contain', 'object-position:bottom center',
        'filter:none', 'brightness:unset',
      ].join(';');
    }

    // Colour headings + labels to match the Sign In button (#8B1A1A)
    document.querySelectorAll('form h1, form h2, form h3, form label').forEach(el => {
      el.style.color = '#8B1A1A';
    });

    // Also catch the login page title which sits above the form
    document.querySelectorAll('h1, h2').forEach(el => {
      if (el.closest('form') || el.textContent.toLowerCase().includes('login') || el.textContent.toLowerCase().includes('access')) {
        el.style.color = '#8B1A1A';
      }
    });

    // White background on all inputs
    document.querySelectorAll('form input').forEach(el => {
      el.style.backgroundColor = '#ffffff';
    });
  }

  /* ── Persist login page text/input colours on re-renders ── */
  const loginColorCss = document.createElement('style');
  loginColorCss.textContent = `
    form h1, form h2, form h3, form label { color: #8B1A1A !important; }
    form input { background-color: #ffffff !important; }
  `;
  document.head.appendChild(loginColorCss);

  /* ── Loading overlay — fades out once the chat textarea mounts ── */
  const overlay = document.createElement('div');
  overlay.id = 'dadi-overlay';
  overlay.style.cssText = 'position:fixed;inset:0;background:#FDF6F0;z-index:99998;';
  document.documentElement.appendChild(overlay);

  let _firstMsgTracked = false;
  function trackChatEngagement() {
    // First message sent
    const textarea = document.querySelector('textarea');
    if (textarea && !textarea.dataset.gaTracked) {
      textarea.dataset.gaTracked = '1';
      textarea.closest('form')?.addEventListener('submit', () => {
        if (!_firstMsgTracked) { _firstMsgTracked = true; gtag('event', 'first_message_sent'); }
      });
    }
    // Starter prompt clicked (delegated, one-time setup)
    if (!document.body.dataset.starterTracked) {
      document.body.dataset.starterTracked = '1';
      document.body.addEventListener('click', (e) => {
        const btn = e.target.closest('button');
        if (!btn) return;
        const parent = btn.closest('[class*="starter"], [data-testid*="starter"]');
        if (parent) gtag('event', 'starter_prompt_clicked', { starter_label: btn.textContent?.trim() });
      });
    }
  }

  function fadeOverlay() {
    overlay.style.transition = 'opacity 0.3s';
    overlay.style.opacity = '0';
    setTimeout(() => overlay.remove(), 350);
    trackChatEngagement();
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
          gtag('event', 'otp_code_sent', { method: 'email' });
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

    // GA4: track Sign In button click
    if (submitBtn && !submitBtn.dataset.gaTracked) {
      submitBtn.dataset.gaTracked = '1';
      submitBtn.addEventListener('click', () => {
        gtag('event', 'login_attempted', { method: 'otp' });
      });
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
      gtag('event', 'guest_login_clicked');
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
    if (isLoginPage()) { styleLoginPage(); transformLoginForm(); }
    if (document.getElementById('dadi-send-code-btn')) clearInterval(loginPoll);
  }, 200);
  setTimeout(() => clearInterval(loginPoll), 10000);

  // Re-run on SPA re-renders
  new MutationObserver(() => {
    if (isLoginPage()) { styleLoginPage(); transformLoginForm(); }
  }).observe(document.body, { childList: true, subtree: true });

  /* ── Persistent logo — re-inject into <html> if ever removed (chat page only) ── */
  function ensureLogo() {
    if (isLoginPage()) return; // no logo on login page
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

  /* ── Replace disclaimer text ── */
  function fixDisclaimer() {
    document.querySelectorAll('*').forEach(el => {
      if (el.childNodes.length === 1 && el.childNodes[0].nodeType === Node.TEXT_NODE) {
        if (el.childNodes[0].textContent.includes('LLMs can make mistakes')) {
          el.childNodes[0].textContent = el.childNodes[0].textContent.replace('LLMs can make mistakes', 'Dadi can make mistakes');
        }
      }
    });
  }
  fixDisclaimer();
  new MutationObserver(fixDisclaimer).observe(document.body, { childList: true, subtree: true });

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

  /* ── Social Share ── */
  const _shareCss = document.createElement('style');
  _shareCss.textContent = `
    .dadi-msg-wrapper { position: relative !important; }
    .dadi-share-btn {
      display: inline-flex; align-items: center; gap: 4px;
      padding: 3px 9px; border-radius: 999px;
      border: 1px solid rgba(139,26,26,0.25);
      background: rgba(253,246,240,0.95); color: #8B1A1A;
      font-size: 0.7rem; cursor: pointer;
      opacity: 0; pointer-events: none;
      transition: opacity 0.18s, background 0.15s;
      position: absolute; bottom: -14px; right: 6px; z-index: 50;
      white-space: nowrap;
      box-shadow: 0 1px 5px rgba(0,0,0,0.09);
      font-family: 'Inter', sans-serif;
    }
    .dadi-msg-wrapper:hover .dadi-share-btn {
      opacity: 1; pointer-events: auto;
    }
    .dadi-share-btn:hover { background: rgba(139,26,26,0.09); }
    .dadi-share-modal {
      position: fixed; inset: 0; z-index: 999999;
      display: flex; align-items: center; justify-content: center;
      background: rgba(0,0,0,0.38);
      animation: dadiModalIn 0.15s ease;
    }
    @keyframes dadiModalIn { from { opacity:0; transform:scale(0.97); } to { opacity:1; transform:scale(1); } }
    .dadi-share-box {
      background: #FDF6F0; border-radius: 18px; padding: 22px 20px 16px;
      max-width: 340px; width: 92%;
      box-shadow: 0 12px 40px rgba(0,0,0,0.18);
      font-family: 'Inter', sans-serif;
    }
    .dadi-share-title {
      font-size: 0.95rem; font-weight: 700; color: #8B1A1A;
      margin: 0 0 10px; letter-spacing: -0.01em;
    }
    .dadi-share-preview {
      background: #fff; border-radius: 9px; padding: 9px 11px;
      font-size: 0.76rem; color: #555; line-height: 1.55;
      max-height: 76px; overflow: hidden;
      display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical;
      margin-bottom: 14px; border: 1px solid rgba(139,26,26,0.13);
    }
    .dadi-share-opts { display: flex; gap: 9px; margin-bottom: 12px; }
    .dadi-share-opt {
      flex: 1; display: flex; flex-direction: column; align-items: center;
      gap: 5px; padding: 11px 6px; border-radius: 12px;
      border: 1.5px solid rgba(139,26,26,0.18); background: #fff;
      cursor: pointer; transition: border-color 0.15s, background 0.15s;
      font-size: 0.7rem; color: #444; font-weight: 600;
    }
    .dadi-share-opt:hover { border-color: #8B1A1A; background: rgba(139,26,26,0.04); }
    .dadi-share-opt svg { width: 26px; height: 26px; }
    .dadi-share-status { font-size: 0.7rem; color: #2e7d32; text-align: center; min-height: 1rem; margin-bottom: 6px; }
    .dadi-share-cancel {
      width: 100%; padding: 7px; border: none; border-radius: 8px;
      background: none; color: #aaa; font-size: 0.76rem; cursor: pointer;
    }
    .dadi-share-cancel:hover { color: #8B1A1A; }
  `;
  document.head.appendChild(_shareCss);

  function _buildShareText(rawText) {
    return '\u2728 Dadi AI says:\n\n\u201c' + rawText.trim() + '\u201d\n\n\uD83D\uDCAC Chat with Dadi at dadi.ai';
  }

  function showShareModal(rawText) {
    const shareText = _buildShareText(rawText);
    const modal = document.createElement('div');
    modal.className = 'dadi-share-modal';
    modal.innerHTML =
      '<div class="dadi-share-box">' +
        '<p class="dadi-share-title">Share this message</p>' +
        '<div class="dadi-share-preview" id="dadi-sp"></div>' +
        '<div class="dadi-share-opts">' +
          '<button class="dadi-share-opt" id="dadi-sw">' +
            '<svg viewBox="0 0 24 24" fill="#25D366"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347z"/><path d="M12 0C5.373 0 0 5.373 0 12c0 2.126.558 4.122 1.532 5.856L.057 23.57l5.865-1.54A11.945 11.945 0 0012 24c6.627 0 12-5.373 12-12S18.627 0 12 0zm0 21.818a9.818 9.818 0 01-5.032-1.39l-.36-.214-3.481.914.929-3.395-.235-.37A9.818 9.818 0 012.182 12C2.182 6.567 6.567 2.182 12 2.182S21.818 6.567 21.818 12 17.433 21.818 12 21.818z"/></svg>' +
            'WhatsApp' +
          '</button>' +
          '<button class="dadi-share-opt" id="dadi-si">' +
            '<svg viewBox="0 0 24 24"><defs><linearGradient id="igG" x1="0%" y1="100%" x2="100%" y2="0%"><stop offset="0%" stop-color="#f09433"/><stop offset="25%" stop-color="#e6683c"/><stop offset="50%" stop-color="#dc2743"/><stop offset="75%" stop-color="#cc2366"/><stop offset="100%" stop-color="#bc1888"/></linearGradient></defs><path fill="url(#igG)" d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zM12 0C8.741 0 8.333.014 7.053.072 2.695.272.273 2.69.073 7.052.014 8.333 0 8.741 0 12c0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98C8.333 23.986 8.741 24 12 24c3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98C15.668.014 15.259 0 12 0zm0 5.838a6.162 6.162 0 100 12.324 6.162 6.162 0 000-12.324zM12 16a4 4 0 110-8 4 4 0 010 8zm6.406-11.845a1.44 1.44 0 100 2.881 1.44 1.44 0 000-2.881z"/></svg>' +
            'Instagram' +
          '</button>' +
        '</div>' +
        '<div class="dadi-share-status" id="dadi-ss"></div>' +
        '<button class="dadi-share-cancel" id="dadi-sc">Cancel</button>' +
      '</div>';

    // Set preview text safely
    modal.querySelector('#dadi-sp').textContent = rawText.trim();
    document.body.appendChild(modal);

    modal.querySelector('#dadi-sw').onclick = () => {
      window.open('https://wa.me/?text=' + encodeURIComponent(shareText), '_blank');
      if (typeof gtag !== 'undefined') gtag('event', 'share_message', { platform: 'whatsapp' });
      modal.remove();
    };

    modal.querySelector('#dadi-si').onclick = async () => {
      try {
        await navigator.clipboard.writeText(shareText);
      } catch (_) {
        const ta = document.createElement('textarea');
        ta.value = shareText; ta.style.cssText = 'position:fixed;opacity:0;';
        document.body.appendChild(ta); ta.select(); document.execCommand('copy'); ta.remove();
      }
      if (typeof gtag !== 'undefined') gtag('event', 'share_message', { platform: 'instagram' });
      modal.querySelector('#dadi-ss').textContent = '\u2713 Copied! Open Instagram \u2192 New Post \u2192 Paste';
      setTimeout(() => { if (modal.parentNode) modal.remove(); }, 2600);
    };

    modal.querySelector('#dadi-sc').onclick = () => modal.remove();
    modal.addEventListener('click', e => { if (e.target === modal) modal.remove(); });
  }

  /* Detect and decorate AI message elements with a share button */
  const _decoratedMsgs = new WeakSet();

  function injectShareButtons() {
    if (isLoginPage()) return;

    // Chainlit renders AI message content in [role="article"] divs
    document.querySelectorAll('[role="article"]').forEach(el => {
      if (_decoratedMsgs.has(el)) return;

      // Skip very short content (e.g. still streaming / single words)
      if ((el.innerText || el.textContent).trim().length < 40) return;

      _decoratedMsgs.add(el);
      el.classList.add('dadi-msg-wrapper');

      const btn = document.createElement('button');
      btn.className = 'dadi-share-btn';
      btn.title = 'Share this message';
      btn.innerHTML =
        '<svg viewBox="0 0 24 24" width="11" height="11" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">' +
          '<circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/>' +
          '<line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/>' +
        '</svg> Share';

      btn.onclick = e => {
        e.stopPropagation();
        showShareModal((el.innerText || el.textContent).trim());
      };

      el.appendChild(btn);
    });
  }

  new MutationObserver(injectShareButtons).observe(document.body, { childList: true, subtree: true });

})();
