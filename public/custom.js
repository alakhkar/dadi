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

  /* ── Social Share (image card) ── */
  const _shareCss = document.createElement('style');
  _shareCss.textContent = `
    .dadi-share-btn { cursor: pointer; flex-shrink: 0; }
    .dadi-share-modal {
      position: fixed; inset: 0; z-index: 999999;
      display: flex; align-items: center; justify-content: center;
      background: rgba(0,0,0,0.42); padding: 1rem;
      animation: dsModalIn 0.15s ease;
    }
    @keyframes dsModalIn { from { opacity:0; transform:scale(0.96); } to { opacity:1; transform:scale(1); } }
    .dadi-share-box {
      background: #fff; border-radius: 18px; padding: 20px;
      max-width: 420px; width: 100%;
      box-shadow: 0 12px 50px rgba(0,0,0,0.22);
      font-family: 'Inter', sans-serif;
    }
    .dadi-share-header {
      display: flex; align-items: center; justify-content: space-between;
      margin-bottom: 14px;
    }
    .dadi-share-title { font-size: 0.95rem; font-weight: 700; color: #8B1A1A; }
    .dadi-share-x {
      background: none; border: none; font-size: 1.2rem; color: #aaa;
      cursor: pointer; line-height: 1; padding: 2px 4px;
    }
    .dadi-share-x:hover { color: #8B1A1A; }
    .dadi-share-img-wrap {
      border-radius: 10px; overflow: hidden; margin-bottom: 14px;
      border: 1px solid #f0d9c8; line-height: 0;
    }
    .dadi-share-img-wrap img { width: 100%; display: block; }
    .dadi-share-generating {
      height: 120px; display: flex; align-items: center; justify-content: center;
      color: #9e7a5a; font-size: 0.8rem; background: #FDF6F0; border-radius: 10px;
      margin-bottom: 14px;
    }
    .dadi-share-grid {
      display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 8px;
    }
    .dadi-share-grid-wide { grid-column: 1 / -1; }
    .dadi-share-opt {
      display: flex; align-items: center; justify-content: center; gap: 7px;
      padding: 10px 8px; border-radius: 10px;
      border: 1px solid #f0d9c8; background: #fff;
      font-size: 0.78rem; font-weight: 500; color: #2d1a10;
      cursor: pointer; transition: all 0.15s;
      font-family: 'Inter', sans-serif;
    }
    .dadi-share-opt:hover { border-color: #8B1A1A; background: #FEF0E7; }
    .dadi-share-opt.primary { background: #8B1A1A; color: #fff; border-color: #8B1A1A; }
    .dadi-share-opt.primary:hover { background: #6e1414; }
    .dadi-share-status {
      font-size: 0.72rem; color: #2e7d32; text-align: center;
      min-height: 1.2em; margin-top: 4px;
    }
  `;
  document.head.appendChild(_shareCss);

  /* ── Canvas image generation ── */
  function _cleanText(raw) {
    return raw
      .replace(/\*\*(.+?)\*\*/g, '$1')
      .replace(/\*(.+?)\*/g, '$1')
      .replace(/^#{1,6}\s+/gm, '')
      .replace(/\[(.+?)\]\(.+?\)/g, '$1')
      .replace(/`+/g, '')
      .replace(/\n{3,}/g, '\n\n')
      .trim();
  }

  function _wrapLines(ctx, text, maxWidth) {
    const paragraphs = text.split('\n');
    const lines = [];
    for (const para of paragraphs) {
      if (!para.trim()) { lines.push(''); continue; }
      const words = para.split(' ').filter(Boolean);
      let line = '';
      for (const word of words) {
        const test = line ? line + ' ' + word : word;
        if (ctx.measureText(test).width > maxWidth && line) {
          lines.push(line);
          line = word;
        } else {
          line = test;
        }
      }
      if (line) lines.push(line);
    }
    return lines;
  }

  function _generateCard(text) {
    const W = 1080, H = 1080;
    const canvas = document.createElement('canvas');
    canvas.width = W; canvas.height = H;
    const ctx = canvas.getContext('2d');

    // Background
    ctx.fillStyle = '#FDF6F0';
    ctx.fillRect(0, 0, W, H);

    // Inner border
    const BRD = 36;
    ctx.strokeStyle = '#eacfba';
    ctx.lineWidth = 3;
    _rrect(ctx, BRD, BRD, W - BRD * 2, H - BRD * 2, 20);
    ctx.stroke();

    // Decorative quote mark (top-left)
    ctx.fillStyle = 'rgba(139,26,26,0.13)';
    ctx.font = '260px Georgia, serif';
    ctx.fillText('\u201C', 68, 300);

    // Message text
    const PAD = 90, TEXT_X = PAD, TEXT_MAX = W - PAD * 2;
    const FONT_SIZE = 48, LINE_H = 72;
    ctx.fillStyle = '#2d1a10';
    ctx.font = `${FONT_SIZE}px Georgia, 'Times New Roman', serif`;

    const allLines = _wrapLines(ctx, text, TEXT_MAX);
    const MAX_LINES = 9;
    let displayLines = allLines.slice(0, MAX_LINES);
    if (allLines.length > MAX_LINES) {
      displayLines[MAX_LINES - 1] = displayLines[MAX_LINES - 1].replace(/\s+\S*$/, '') + '\u2026';
    }

    const TEXT_Y_START = 320;
    displayLines.forEach((line, i) => {
      if (line === '') return;
      ctx.fillText(line, TEXT_X, TEXT_Y_START + i * LINE_H);
    });

    // Divider above branding
    const DIV_Y = H - 170;
    ctx.strokeStyle = '#eacfba';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(PAD, DIV_Y); ctx.lineTo(W - PAD, DIV_Y);
    ctx.stroke();

    // Branding row
    const BRAND_Y = H - 100;

    // "Dadi AI" in serif red
    ctx.fillStyle = '#8B1A1A';
    ctx.font = 'bold 52px Georgia, serif';
    ctx.fillText('Dadi AI', PAD, BRAND_Y);

    // Dot separator
    const aiTextW = ctx.measureText('Dadi AI').width;
    ctx.fillStyle = '#c0a080';
    ctx.font = '40px Georgia, serif';
    ctx.fillText('\u00B7', PAD + aiTextW + 18, BRAND_Y - 4);
    const dotW = ctx.measureText('\u00B7').width;

    // URL
    ctx.fillStyle = '#9e7a5a';
    ctx.font = '40px Inter, Arial, sans-serif';
    ctx.fillText('www.mydadi.in', PAD + aiTextW + 18 + dotW + 16, BRAND_Y - 2);

    return canvas.toDataURL('image/png');
  }

  function _rrect(ctx, x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.lineTo(x + w - r, y); ctx.arcTo(x + w, y, x + w, y + r, r);
    ctx.lineTo(x + w, y + h - r); ctx.arcTo(x + w, y + h, x + w - r, y + h, r);
    ctx.lineTo(x + r, y + h); ctx.arcTo(x, y + h, x, y + h - r, r);
    ctx.lineTo(x, y + r); ctx.arcTo(x, y, x + r, y, r);
    ctx.closePath();
  }

  /* ── Share modal ── */
  function showShareModal(rawText) {
    document.getElementById('dadi-share-modal')?.remove();

    const text = _cleanText(rawText);
    const url = 'https://www.mydadi.in';
    const waText = `\u2728 "${text.slice(0, 300)}${text.length > 300 ? '\u2026' : ''}"\n\n\uD83D\uDCAC Chat with Dadi \u2192 ${url}`;
    const twText = `"${text.slice(0, 220)}${text.length > 220 ? '\u2026' : ''}"\n\n\u2014 Dadi AI`;

    const modal = document.createElement('div');
    modal.className = 'dadi-share-modal';
    modal.id = 'dadi-share-modal';
    modal.innerHTML = `
      <div class="dadi-share-box">
        <div class="dadi-share-header">
          <span class="dadi-share-title">Share this response</span>
          <button class="dadi-share-x" id="ds-close">\u2715</button>
        </div>
        <div class="dadi-share-generating" id="ds-generating">Generating image\u2026</div>
        <div class="dadi-share-img-wrap" id="ds-img-wrap" style="display:none"></div>
        <div class="dadi-share-grid" id="ds-btns" style="display:none">
          ${navigator.canShare ? '<button class="dadi-share-opt primary dadi-share-grid-wide" id="ds-native">\u2b06\ufe0f Share Image\u2026</button>' : ''}
          <button class="dadi-share-opt" id="ds-download">\u2b07\ufe0f Download</button>
          <button class="dadi-share-opt" id="ds-copyimg">\ud83d\udccb Copy Image</button>
          <button class="dadi-share-opt" id="ds-wa">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="#25D366"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347z"/><path d="M12 0C5.373 0 0 5.373 0 12c0 2.126.558 4.122 1.532 5.856L.057 23.57l5.865-1.54A11.945 11.945 0 0012 24c6.627 0 12-5.373 12-12S18.627 0 12 0zm0 21.818a9.818 9.818 0 01-5.032-1.39l-.36-.214-3.481.914.929-3.395-.235-.37A9.818 9.818 0 012.182 12C2.182 6.567 6.567 2.182 12 2.182S21.818 6.567 21.818 12 17.433 21.818 12 21.818z"/></svg>
            WhatsApp
          </button>
          <button class="dadi-share-opt" id="ds-tw">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="#000"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-4.714-6.231-5.401 6.231H2.747l7.73-8.835L1.254 2.25H8.08l4.253 5.622L18.244 2.25zm-1.161 17.52h1.833L7.084 4.126H5.117L17.083 19.77z"/></svg>
            Twitter / X
          </button>
          <button class="dadi-share-opt" id="ds-link">\uD83D\uDD17 Copy Link</button>
        </div>
        <div class="dadi-share-status" id="ds-status"></div>
      </div>`;

    document.body.appendChild(modal);

    const setStatus = (msg, color) => {
      const el = modal.querySelector('#ds-status');
      el.textContent = msg;
      el.style.color = color || '#2e7d32';
    };

    modal.querySelector('#ds-close').onclick = () => modal.remove();
    modal.addEventListener('click', e => { if (e.target === modal) modal.remove(); });

    // Generate image off main thread via setTimeout
    let _imgDataUrl = null;
    setTimeout(() => {
      try {
        _imgDataUrl = _generateCard(text);
        const img = document.createElement('img');
        img.src = _imgDataUrl;
        img.alt = 'Share card';
        modal.querySelector('#ds-generating').style.display = 'none';
        const wrap = modal.querySelector('#ds-img-wrap');
        wrap.appendChild(img);
        wrap.style.display = 'block';
        modal.querySelector('#ds-btns').style.display = 'grid';
      } catch (err) {
        modal.querySelector('#ds-generating').textContent = 'Could not generate image.';
      }
    }, 30);

    // Native share (mobile — shares the image file)
    modal.querySelector('#ds-native')?.addEventListener('click', async () => {
      if (!_imgDataUrl) return;
      try {
        const blob = await (await fetch(_imgDataUrl)).blob();
        const file = new File([blob], 'dadi-ai.png', { type: 'image/png' });
        if (navigator.canShare({ files: [file] })) {
          await navigator.share({ files: [file], title: 'Dadi AI', text: waText });
        } else {
          await navigator.share({ title: 'Dadi AI', text: waText, url });
        }
      } catch (_) {}
    });

    // Download
    modal.querySelector('#ds-download')?.addEventListener('click', () => {
      if (!_imgDataUrl) return;
      const a = document.createElement('a');
      a.href = _imgDataUrl; a.download = 'dadi-ai.png'; a.click();
      if (typeof gtag !== 'undefined') gtag('event', 'share_message', { platform: 'download' });
    });

    // Copy image to clipboard
    modal.querySelector('#ds-copyimg')?.addEventListener('click', async () => {
      if (!_imgDataUrl) return;
      try {
        const blob = await (await fetch(_imgDataUrl)).blob();
        await navigator.clipboard.write([new ClipboardItem({ 'image/png': blob })]);
        setStatus('\u2713 Image copied to clipboard!');
        if (typeof gtag !== 'undefined') gtag('event', 'share_message', { platform: 'copy_image' });
      } catch (_) {
        setStatus('Could not copy image \u2014 try Download instead.', '#c0392b');
      }
    });

    // WhatsApp
    modal.querySelector('#ds-wa')?.addEventListener('click', () => {
      window.open('https://wa.me/?text=' + encodeURIComponent(waText), '_blank');
      if (typeof gtag !== 'undefined') gtag('event', 'share_message', { platform: 'whatsapp' });
    });

    // Twitter / X
    modal.querySelector('#ds-tw')?.addEventListener('click', () => {
      window.open(`https://twitter.com/intent/tweet?text=${encodeURIComponent(twText)}&url=${encodeURIComponent(url)}`, '_blank');
      if (typeof gtag !== 'undefined') gtag('event', 'share_message', { platform: 'twitter' });
    });

    // Copy link
    modal.querySelector('#ds-link')?.addEventListener('click', async e => {
      try { await navigator.clipboard.writeText(url); } catch (_) {}
      setStatus('\u2713 Link copied!');
      e.target.textContent = '\u2713 Copied!';
      setTimeout(() => { if (e.target) e.target.textContent = '\uD83D\uDD17 Copy Link'; }, 2000);
    });
  }

  /* ── Inject share button into Chainlit action bar ── */
  const _decoratedBars = new WeakSet();

  // Chainlit action buttons (copy/thumbs) have Tailwind class "h-9 w-9"
  // Use class selector (.h-9) for exact word match, not substring.
  const _iconBtnSel = 'button.h-9:not(.dadi-share-btn)';

  function findActionBar(article) {
    // Walk UP from the article; at each level search DOWN for h-9 buttons
    // that are NOT inside the article itself. First match = action bar container.
    let el = article.parentElement;
    for (let depth = 0; depth < 10 && el && el !== document.body; depth++) {
      const btns = Array.from(el.querySelectorAll(_iconBtnSel))
        .filter(b => !article.contains(b));
      if (btns.length > 0) {
        // Return the direct parent of the first button (the flex row container)
        const bar = btns[0].parentElement;
        return (bar && bar !== document.body) ? bar : el;
      }
      el = el.parentElement;
    }
    return null;
  }

  function injectShareButtons() {
    if (isLoginPage()) return;
    document.querySelectorAll('[role="article"]').forEach(article => {
      if ((article.innerText || article.textContent || '').trim().length < 40) return;

      const bar = findActionBar(article);
      if (!bar || _decoratedBars.has(bar)) return;
      if (bar.querySelector('.dadi-share-btn')) { _decoratedBars.add(bar); return; }

      _decoratedBars.add(bar);

      // Clone className from an existing action button so we blend in perfectly
      const existingBtn = bar.querySelector('button:not(.dadi-share-btn)');
      const btn = document.createElement('button');
      btn.className = (existingBtn ? existingBtn.className + ' ' : '') + 'dadi-share-btn';
      btn.title = 'Share as image';
      // Match SVG class/size from existing icon if present
      const existingSvgClass = existingBtn?.querySelector('svg')?.getAttribute('class') || '';
      btn.innerHTML =
        `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="${existingSvgClass}" style="width:1em;height:1em">` +
          '<circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/>' +
          '<line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/>' +
        '</svg>';

      btn.onclick = e => {
        e.stopPropagation();
        showShareModal((article.innerText || article.textContent || '').trim());
      };

      bar.appendChild(btn);
    });
  }

  new MutationObserver(injectShareButtons).observe(document.body, { childList: true, subtree: true });

})();
