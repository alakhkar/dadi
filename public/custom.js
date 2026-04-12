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

  /* ── SEO — meta tags, Open Graph, Twitter Card, JSON-LD ── */
  (function () {
    const SITE   = 'https://www.mydadi.in';
    const IMG    = SITE + '/public/images/dadi.png';
    const TITLE  = 'Dadi AI — Your Wise Indian Grandmother';
    const DESC   = 'Meet Dadi — your AI Indian grandmother who gives real talk, heartfelt advice, and a healthy dose of desi humor. Chat about life, family, relationships, and everything in between.';

    // helper: set or update a <meta> tag
    const meta = (key, val, isProp) => {
      const attr = isProp ? 'property' : 'name';
      let el = document.querySelector(`meta[${attr}="${key}"]`);
      if (!el) { el = document.createElement('meta'); el.setAttribute(attr, key); document.head.appendChild(el); }
      el.content = val;
    };

    // ── Basic ────────────────────────────────────────────────────────────
    meta('description', DESC);
    meta('keywords', 'dadi ai, indian grandmother chatbot, desi advice, ai chatbot india, life advice ai, indian family chatbot, hindi chatbot, dadi chatbot, ask dadi, indian wisdom ai');
    meta('robots', 'index, follow');
    meta('author', 'Dadi AI');
    meta('theme-color', '#8B1A1A');

    // ── Open Graph ───────────────────────────────────────────────────────
    meta('og:type',        'website',  true);
    meta('og:url',         SITE,       true);
    meta('og:site_name',   'Dadi AI',  true);
    meta('og:locale',      'en_IN',    true);
    meta('og:title',       TITLE,      true);
    meta('og:description', DESC,       true);
    meta('og:image',       IMG,        true);
    meta('og:image:width', '600',      true);
    meta('og:image:height','600',      true);
    meta('og:image:alt',   'Dadi AI',  true);

    // ── Twitter Card ─────────────────────────────────────────────────────
    meta('twitter:card',        'summary_large_image');
    meta('twitter:title',       TITLE);
    meta('twitter:description', DESC);
    meta('twitter:image',       IMG);
    meta('twitter:image:alt',   'Dadi AI');

    // ── Canonical ────────────────────────────────────────────────────────
    if (!document.querySelector('link[rel="canonical"]')) {
      const link = document.createElement('link');
      link.rel = 'canonical';
      link.href = SITE;
      document.head.appendChild(link);
    }

    // ── JSON-LD: WebApplication ──────────────────────────────────────────
    if (!document.getElementById('dadi-jsonld')) {
      const s = document.createElement('script');
      s.id   = 'dadi-jsonld';
      s.type = 'application/ld+json';
      s.text = JSON.stringify({
        '@context': 'https://schema.org',
        '@type': 'WebApplication',
        name: 'Dadi AI',
        url: SITE,
        description: DESC,
        applicationCategory: 'LifestyleApplication',
        operatingSystem: 'All',
        inLanguage: ['en', 'hi'],
        image: IMG,
        offers: { '@type': 'Offer', price: '0', priceCurrency: 'INR' },
        audience: { '@type': 'Audience', audienceType: 'Indian families and youth' },
      });
      document.head.appendChild(s);
    }

    // ── Sitemap link ─────────────────────────────────────────────────────
    if (!document.querySelector('link[rel="sitemap"]')) {
      const sl = document.createElement('link');
      sl.rel  = 'sitemap';
      sl.type = 'application/xml';
      sl.href = '/sitemap.xml';
      document.head.appendChild(sl);
    }

    // ── lang attribute ───────────────────────────────────────────────────
    if (!document.documentElement.lang) document.documentElement.lang = 'en';

    // ── PWA manifest ─────────────────────────────────────────────────────
    if (!document.querySelector('link[rel="manifest"]')) {
      const mf = document.createElement('link');
      mf.rel = 'manifest'; mf.href = '/manifest.json';
      document.head.appendChild(mf);
    }

    // ── Apple PWA meta tags ───────────────────────────────────────────────
    meta('apple-mobile-web-app-capable', 'yes');
    meta('apple-mobile-web-app-status-bar-style', 'black-translucent');
    meta('apple-mobile-web-app-title', 'Dadi AI');
    if (!document.querySelector('link[rel="apple-touch-icon"]')) {
      const atIcon = document.createElement('link');
      atIcon.rel = 'apple-touch-icon'; atIcon.href = '/public/images/dadi.png';
      document.head.appendChild(atIcon);
    }
  })();

  // ── Service Worker registration ─────────────────────────────────────────
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('/sw.js', { scope: '/' })
        .then(reg => console.log('[SW] Registered, scope:', reg.scope))
        .catch(err => console.log('[SW] Registration failed:', err));
    });
  }

  /* ── Login page: glassmorphism theme ── */
  const loginCss = document.createElement('style');
  loginCss.textContent = `
    /* Hide persistent logo on login page */
    html.dadi-login::before { display:none!important; }
    html.dadi-login #dadi-chat-logo { display:none!important; }

    /* Full-page gradient background */
    html.dadi-login, html.dadi-login body {
      background: linear-gradient(135deg, #1a0a0a 0%, #2d0f0f 30%, #1a1a2e 65%, #0f0f23 100%) !important;
      min-height: 100vh;
    }

    /* Animated floating orbs behind everything */
    html.dadi-login::after {
      content: '';
      position: fixed; inset: 0; z-index: 0; pointer-events: none;
      background:
        radial-gradient(ellipse 600px 500px at 15% 20%, rgba(139,26,26,0.18) 0%, transparent 70%),
        radial-gradient(ellipse 500px 400px at 80% 75%, rgba(80,20,80,0.15) 0%, transparent 70%),
        radial-gradient(ellipse 400px 350px at 60% 10%, rgba(26,26,80,0.18) 0%, transparent 70%);
    }

    /* Left (form) panel — glass card */
    html.dadi-login .dadi-glass-left {
      background: rgba(255,255,255,0.06) !important;
      backdrop-filter: blur(24px) saturate(160%) !important;
      -webkit-backdrop-filter: blur(24px) saturate(160%) !important;
      border-right: 1px solid rgba(255,255,255,0.1) !important;
    }

    /* All text in the form panel */
    html.dadi-login form h1,
    html.dadi-login form h2,
    html.dadi-login form h3 {
      color: #ffffff !important;
      font-weight: 700 !important;
      letter-spacing: 0.02em !important;
    }
    html.dadi-login form label,
    html.dadi-login form p:not(#dadi-otp-status) {
      color: rgba(255,255,255,0.75) !important;
    }
    html.dadi-login h1, html.dadi-login h2 {
      color: #ffffff !important;
    }

    /* Glass inputs */
    html.dadi-login form input {
      background: rgba(255,255,255,0.08) !important;
      border: 1px solid rgba(255,255,255,0.18) !important;
      color: #ffffff !important;
      border-radius: 10px !important;
      transition: border-color 0.2s, background 0.2s !important;
    }
    html.dadi-login form input::placeholder { color: rgba(255,255,255,0.38) !important; }
    html.dadi-login form input:focus {
      background: rgba(255,255,255,0.13) !important;
      border-color: rgba(220,80,80,0.7) !important;
      outline: none !important;
      box-shadow: 0 0 0 3px rgba(139,26,26,0.25) !important;
    }

    /* Primary submit button */
    html.dadi-login form button[type="submit"] {
      background: linear-gradient(135deg, #8B1A1A 0%, #c0392b 100%) !important;
      border: none !important;
      color: #fff !important;
      border-radius: 10px !important;
      font-weight: 600 !important;
      letter-spacing: 0.04em !important;
      box-shadow: 0 4px 20px rgba(139,26,26,0.4) !important;
      transition: box-shadow 0.2s, transform 0.15s !important;
    }
    html.dadi-login form button[type="submit"]:hover {
      box-shadow: 0 6px 28px rgba(139,26,26,0.55) !important;
      transform: translateY(-1px) !important;
    }

    /* Send Code button (injected) */
    html.dadi-login #dadi-send-code-btn {
      background: rgba(139,26,26,0.25) !important;
      border: 1px solid rgba(220,80,80,0.5) !important;
      color: #ff9999 !important;
      border-radius: 10px !important;
      backdrop-filter: blur(8px) !important;
      transition: background 0.2s !important;
    }
    html.dadi-login #dadi-send-code-btn:hover {
      background: rgba(139,26,26,0.45) !important;
    }

    /* Guest button */
    html.dadi-login #dadi-skip-wrapper button {
      border-color: rgba(255,255,255,0.25) !important;
      color: rgba(255,255,255,0.7) !important;
    }
    html.dadi-login #dadi-skip-wrapper span {
      color: rgba(255,255,255,0.4) !important;
    }
    html.dadi-login #dadi-skip-wrapper button:hover {
      background: rgba(255,255,255,0.08) !important;
    }

    /* OTP status text */
    html.dadi-login #dadi-otp-status { color: #7dffb3 !important; }

    /* Right panel — full dark with Dadi image */
    html.dadi-login .dadi-glass-right {
      background: transparent !important;
    }

    /* Hide native Chainlit logo on login page (top-left of left panel) */
    html.dadi-login .dadi-glass-left img:not([id="dadi-form-brand"] img),
    html.dadi-login .dadi-glass-left > div > img,
    html.dadi-login .dadi-glass-left a img {
      display: none !important;
    }

    /* Shimmer line — between tagline and Login heading */
    html.dadi-login .dadi-login-shimmer {
      display: block;
      height: 2px;
      width: 60%;
      margin: 16px auto 24px;
      border-radius: 99px;
      background: linear-gradient(90deg, transparent, rgba(220,80,80,0.7), rgba(255,200,200,0.9), rgba(220,80,80,0.7), transparent);
    }
  `;
  document.head.appendChild(loginCss);

  function styleLoginPage() {
    if (document.getElementById('dadi-page-styled')) return;
    const rightPanel = document.querySelector('div.relative.bg-muted');
    if (!rightPanel) return;

    document.getElementById('dadi-page-styled')?.remove();
    const marker = document.createElement('span');
    marker.id = 'dadi-page-styled';
    marker.style.display = 'none';
    document.body.appendChild(marker);

    document.documentElement.classList.add('dadi-login');

    // ── Right panel: dark glass + full-height Dadi image ──
    rightPanel.classList.add('dadi-glass-right');
    rightPanel.style.cssText = 'background:linear-gradient(160deg,rgba(30,10,10,0.85)0%,rgba(10,10,30,0.9)100%)!important;';

    const _dadiImages = [
      '/public/images/dadi.png',
      '/public/images/dadi_dancing.png',
      '/public/images/dadi_karate.png',
      '/public/images/dadi_dancing_with_smirk.png',
      '/public/images/dadi kicking with smirk.png',
      '/public/images/dadi picking flowers.png',
      '/public/images/dadi reading book.png',
      '/public/images/dadi tea.png',
    ];
    const img = rightPanel.querySelector('img');
    if (img) {
      img.src = _dadiImages[Math.floor(Math.random() * _dadiImages.length)];
      img.alt = 'Dadi';
      img.style.cssText = 'position:absolute;inset:0;height:100%;width:100%;object-fit:contain;object-position:bottom center;filter:drop-shadow(0 0 60px rgba(139,26,26,0.3));';
    }

    // Overlay glow on right panel
    const glow = document.createElement('div');
    glow.style.cssText = 'position:absolute;inset:0;background:radial-gradient(ellipse 70% 40% at 50% 100%,rgba(139,26,26,0.25)0%,transparent 70%);pointer-events:none;z-index:1;';
    rightPanel.appendChild(glow);

    // ── Left panel: glass card ──
    const leftPanel = rightPanel.previousElementSibling || rightPanel.parentElement?.firstElementChild;
    if (leftPanel && leftPanel !== rightPanel) {
      leftPanel.classList.add('dadi-glass-left');
      leftPanel.style.position = 'relative';

      // Inject brand + shimmer into the form
      const form = leftPanel.querySelector('form') || document.querySelector('form');
      if (form && !form.querySelector('.dadi-login-shimmer')) {
        // 1. Logo + tagline at the very top
        if (!form.querySelector('#dadi-form-brand')) {
          const formBrand = document.createElement('div');
          formBrand.id = 'dadi-form-brand';
          formBrand.style.cssText = 'text-align:center;margin-bottom:0;pointer-events:none;';
          formBrand.innerHTML = `
            <img src="/public/logo_dark.png" alt="Dadi AI" style="height:112px;width:auto;display:block;margin:0 auto 10px;" />
            <div style="font-size:0.78rem;color:rgba(255,255,255,0.55);letter-spacing:0.14em;text-transform:uppercase;">She will roast you. She will fix you.</div>
          `;
          form.insertBefore(formBrand, form.firstChild);
        }

        // 2. Shimmer divider after brand, before "Login to access app"
        const shimmer = document.createElement('span');
        shimmer.className = 'dadi-login-shimmer';
        const brand = form.querySelector('#dadi-form-brand');
        brand.insertAdjacentElement('afterend', shimmer);
      }
    }
  }

  /* ── Persist glass styles on re-renders ── */
  const loginColorCss = document.createElement('style');
  loginColorCss.textContent = `
    html.dadi-login form h1, html.dadi-login form h2, html.dadi-login form h3 { color:#fff!important; }
    html.dadi-login form label { color:rgba(255,255,255,0.75)!important; }
    html.dadi-login form input { background:rgba(255,255,255,0.08)!important; color:#fff!important; border-color:rgba(255,255,255,0.18)!important; }
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

  /* ── Inject "Meri Profile" into Chainlit's user dropdown menu ── */
  function getLoggedInEmail() {
    // Chainlit often renders the user's identifier as plain text inside the menu
    // or in the trigger button. Walk the menu for an email-shaped string first.
    const menu = document.querySelector('[role="menu"]');
    if (menu) {
      for (const el of menu.querySelectorAll('*')) {
        const t = el.childNodes.length === 1 && el.childNodes[0].nodeType === Node.TEXT_NODE
          ? el.textContent.trim() : '';
        if (/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(t)) return t;
      }
    }
    // Fallback: check the header user button label/title/text
    const btn = document.querySelector('header button[aria-label], header button[title]');
    if (btn) {
      const candidate = (btn.getAttribute('aria-label') || btn.getAttribute('title') || '').trim();
      if (/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(candidate)) return candidate;
    }
    return '';
  }

  function injectProfileMenuItem() {
    const menu = document.querySelector('[role="menu"]');
    if (!menu || document.getElementById('dadi-profile-menu-item')) return;
    // Confirm it's the user menu by checking for a logout/sign-out item
    const hasLogout = [...menu.querySelectorAll('[role="menuitem"]')]
      .some(el => /logout|sign.?out/i.test(el.textContent));
    if (!hasLogout) return;
    const email = getLoggedInEmail();
    const href = email ? '/profile?email=' + encodeURIComponent(email) : '/profile';
    const item = document.createElement('a');
    item.id = 'dadi-profile-menu-item';
    item.href = href;
    item.target = '_blank';
    item.rel = 'noopener';
    item.setAttribute('role', 'menuitem');
    item.textContent = 'Meri Profile';
    item.style.cssText = (
      'display:flex;align-items:center;width:100%;padding:6px 12px;' +
      'font-size:0.875rem;color:#2d1a10;text-decoration:none;cursor:pointer;' +
      'transition:background 0.15s;'
    );
    item.onmouseenter = () => { item.style.background = 'rgba(139,26,26,0.07)'; };
    item.onmouseleave = () => { item.style.background = ''; };
    menu.insertBefore(item, menu.firstChild);
  }
  new MutationObserver(injectProfileMenuItem)
    .observe(document.body, { childList: true, subtree: true });

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
  // If textarea already exists (e.g. refresh with cached page), fade immediately
  if (document.querySelector('textarea')) fadeOverlay();
  setTimeout(fadeOverlay, 2000); // hard fallback

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

  /* ── Load Google Fonts for share card ── */
  (function () {
    if (document.querySelector('link[data-dadi-share-fonts]')) return;
    const l = document.createElement('link');
    l.rel = 'stylesheet';
    l.setAttribute('data-dadi-share-fonts', '1');
    l.href = 'https://fonts.googleapis.com/css2?family=Syne:wght@700;800&family=DM+Sans:ital,wght@0,300;0,400;1,300&family=Space+Mono:wght@400;700&family=Anton&family=Kalam:wght@400;700&display=swap';
    document.head.appendChild(l);
  })();

  /* ── Pre-load Kalam via FontFace API so canvas can use it reliably ── */
  async function _ensureKalam() {
    if (_ensureKalam._done) return;
    try {
      const f400 = new FontFace('Kalam', 'url(https://fonts.gstatic.com/s/kalam/v18/YA9dr0Wd4kDdMuhW.ttf)', { weight: '400' });
      const f700 = new FontFace('Kalam', 'url(https://fonts.gstatic.com/s/kalam/v18/YA9Qr0Wd4kDdMtDqHQLL.ttf)', { weight: '700' });
      const [loaded400, loaded700] = await Promise.all([f400.load(), f700.load()]);
      document.fonts.add(loaded400);
      document.fonts.add(loaded700);
    } catch (e) { /* fallback silently */ }
    _ensureKalam._done = true;
  }

  function _wrapText(ctx, text, maxWidth) {
    const words = text.split(' ');
    const lines = [];
    let line = '';
    for (const word of words) {
      const test = line ? line + ' ' + word : word;
      if (ctx.measureText(test).width > maxWidth && line) { lines.push(line); line = word; }
      else line = test;
    }
    if (line) lines.push(line);
    return lines;
  }


  /* ── Meme generator ── */
  const _MEME_IMAGES = [
    '/public/images/dadi.png',
    '/public/images/dadi_dancing.png',
    '/public/images/dadi_karate.png',
    '/public/images/dadi_dancing_with_smirk.png',
    '/public/images/dadi kicking with smirk.png',
    '/public/images/dadi picking flowers.png',
    '/public/images/dadi reading book.png',
    '/public/images/dadi tea.png',
  ];

  async function _generateMeme(text, imgSrc) {
    await _ensureKalam();
    await document.fonts.ready;
    const SIZE = 1080;
    const canvas = document.createElement('canvas');
    canvas.width = SIZE; canvas.height = SIZE;
    const ctx = canvas.getContext('2d');

    // Draw Dadi image as cover-fill background
    await fetch(imgSrc).then(r => r.blob()).then(blob => new Promise(resolve => {
      const url = URL.createObjectURL(blob);
      const img = new Image();
      img.onload = () => {
        const scale = Math.max(SIZE / img.naturalWidth, SIZE / img.naturalHeight);
        const dw = img.naturalWidth * scale, dh = img.naturalHeight * scale;
        ctx.drawImage(img, (SIZE - dw) / 2, (SIZE - dh) / 2, dw, dh);
        URL.revokeObjectURL(url);
        resolve();
      };
      img.onerror = resolve;
      img.src = url;
    })).catch(() => {
      ctx.fillStyle = '#FDF6F0';
      ctx.fillRect(0, 0, SIZE, SIZE);
    });

    // Text lives in the bottom third — scale font to fill that zone
    const PAD = 44;
    const maxW = SIZE - PAD * 2;
    const memeText = _cleanText(text);
    const BOTTOM_THIRD_H = Math.floor(SIZE / 3) - PAD; // ~316px

    let fontSize = 96, lines;
    while (fontSize >= 18) {
      ctx.font = `700 ${fontSize}px 'Kalam', cursive`;
      lines = _wrapText(ctx, memeText, maxW);
      const lhTmp = Math.round(fontSize * 1.25);
      if (fontSize + (lines.length - 1) * lhTmp <= BOTTOM_THIRD_H) break;
      fontSize -= 4;
    }

    const lh = Math.round(fontSize * 1.25);
    let y = SIZE - PAD - (lines.length - 1) * lh;

    // Gradient covers the bottom third of the image
    const grad = ctx.createLinearGradient(0, SIZE * 0.58, 0, SIZE);
    grad.addColorStop(0, 'rgba(0,0,0,0)');
    grad.addColorStop(1, 'rgba(0,0,0,0.88)');
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, SIZE, SIZE);

    ctx.font = `700 ${fontSize}px 'Kalam', cursive`;
    ctx.textAlign = 'center';
    ctx.lineJoin = 'round';
    ctx.lineWidth = Math.round(fontSize * 0.09);
    ctx.strokeStyle = '#000';

    lines.forEach(line => {
      ctx.strokeText(line, SIZE / 2, y);
      ctx.fillStyle = '#fff';
      ctx.fillText(line, SIZE / 2, y);
      y += lh;
    });

    // Watermark top-right
    ctx.font = `700 26px 'Kalam', cursive`;
    ctx.lineWidth = 3;
    ctx.strokeStyle = 'rgba(0,0,0,0.6)';
    ctx.fillStyle = '#FF4D00';
    ctx.textAlign = 'right';
    ctx.strokeText('MYDADI.IN', SIZE - 20, 44);
    ctx.fillText('MYDADI.IN', SIZE - 20, 44);

    return canvas.toDataURL('image/png');
  }

  function showMemeModal(rawDadiText) {
    document.getElementById('dadi-meme-modal')?.remove();
    const text = _cleanText(rawDadiText);
    let currentIdx = Math.floor(Math.random() * _MEME_IMAGES.length);
    let _memeDataUrl = null;

    const modal = document.createElement('div');
    modal.className = 'dadi-share-modal';
    modal.id = 'dadi-meme-modal';
    modal.innerHTML = `
      <div class="dadi-share-box">
        <div class="dadi-share-header">
          <span class="dadi-share-title">😂 Dadi Meme</span>
          <button class="dadi-share-x" id="dm-close">✕</button>
        </div>
        <div class="dadi-share-generating" id="dm-generating">Generating meme…</div>
        <div class="dadi-share-img-wrap" id="dm-img-wrap" style="display:none"></div>
        <div id="dm-picker" style="display:flex;gap:6px;justify-content:center;margin-bottom:10px;"></div>
        <div class="dadi-share-grid" id="dm-btns" style="display:none">
          ${navigator.canShare ? '<button class="dadi-share-opt primary dadi-share-grid-wide" id="dm-native">⬆️ Share Meme…</button>' : ''}
          <button class="dadi-share-opt primary dadi-share-grid-wide" id="dm-dl">⬇ Download Meme</button>
          <button class="dadi-share-opt" id="dm-copy">📋 Copy Image</button>
          <button class="dadi-share-opt" id="dm-wa">💬 WhatsApp</button>
        </div>
        <div class="dadi-share-status" id="dm-status"></div>
      </div>`;

    document.body.appendChild(modal);

    // Image picker thumbnails
    const picker = modal.querySelector('#dm-picker');
    _MEME_IMAGES.forEach((src, i) => {
      const thumb = document.createElement('img');
      thumb.src = src;
      thumb.title = 'Switch Dadi';
      thumb.style.cssText = `width:46px;height:46px;object-fit:cover;border-radius:8px;cursor:pointer;border:2px solid ${i === currentIdx ? '#8B1A1A' : 'transparent'};transition:border 0.15s;`;
      thumb.onclick = () => {
        currentIdx = i;
        picker.querySelectorAll('img').forEach((t, j) => { t.style.borderColor = j === i ? '#8B1A1A' : 'transparent'; });
        generate();
      };
      picker.appendChild(thumb);
    });

    const setStatus = (msg, ok) => {
      const el = modal.querySelector('#dm-status');
      el.textContent = msg;
      el.style.color = ok === false ? '#c0392b' : '#2e7d32';
    };

    async function generate() {
      const wrap = modal.querySelector('#dm-img-wrap');
      const gen  = modal.querySelector('#dm-generating');
      const btns = modal.querySelector('#dm-btns');
      wrap.style.display = 'none'; btns.style.display = 'none';
      gen.style.display = 'flex'; gen.textContent = 'Generating meme…';
      try {
        _memeDataUrl = await _generateMeme(text, _MEME_IMAGES[currentIdx]);
        const img = document.createElement('img');
        img.src = _memeDataUrl; img.alt = 'Dadi meme';
        wrap.innerHTML = ''; wrap.appendChild(img);
        gen.style.display = 'none';
        wrap.style.display = 'block';
        btns.style.display = 'grid';
      } catch (_) { gen.textContent = 'Could not generate meme.'; }
    }

    modal.querySelector('#dm-close').onclick = () => modal.remove();
    modal.addEventListener('click', e => { if (e.target === modal) modal.remove(); });

    modal.querySelector('#dm-native')?.addEventListener('click', async () => {
      if (!_memeDataUrl) return;
      try {
        const blob = await (await fetch(_memeDataUrl)).blob();
        const file = new File([blob], 'dadi-meme.png', { type: 'image/png' });
        await navigator.share(navigator.canShare({ files: [file] }) ? { files: [file], title: 'Dadi Meme', url: 'https://www.mydadi.in' } : { title: 'Dadi Meme', url: 'https://www.mydadi.in' });
      } catch (_) {}
    });

    modal.querySelector('#dm-dl').addEventListener('click', () => {
      if (!_memeDataUrl) return;
      const a = document.createElement('a');
      a.href = _memeDataUrl; a.download = 'dadi-meme.png'; a.click();
      gtag('event', 'meme_action', { action: 'download' });
    });

    modal.querySelector('#dm-copy').addEventListener('click', async () => {
      if (!_memeDataUrl) return;
      try {
        const blob = await (await fetch(_memeDataUrl)).blob();
        await navigator.clipboard.write([new ClipboardItem({ 'image/png': blob })]);
        setStatus('✓ Copied to clipboard!');
        gtag('event', 'meme_action', { action: 'copy' });
      } catch (_) { setStatus('Copy not supported on this browser.', false); }
    });

    modal.querySelector('#dm-wa').addEventListener('click', () => {
      window.open('https://wa.me/?text=' + encodeURIComponent('😂 Chat with Dadi at https://www.mydadi.in'), '_blank');
      gtag('event', 'meme_action', { action: 'whatsapp' });
    });

    setTimeout(generate, 30);
  }

  function _roundRect(ctx, x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.lineTo(x + w - r, y);
    ctx.quadraticCurveTo(x + w, y, x + w, y + r);
    ctx.lineTo(x + w, y + h - r);
    ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
    ctx.lineTo(x + r, y + h);
    ctx.quadraticCurveTo(x, y + h, x, y + h - r);
    ctx.lineTo(x, y + r);
    ctx.quadraticCurveTo(x, y, x + r, y);
    ctx.closePath();
  }

  async function _generateCard(dadiText, userText) {
    await _ensureKalam();
    await document.fonts.ready;

    const W = 1080, LW = 360, PAD = 56;
    const BW = W - LW - PAD * 2;
    const BPX = 30, BPY = 22;

    const _pre = document.createElement('canvas');
    _pre.width = W; _pre.height = 100;
    const _pc = _pre.getContext('2d');

    // User bubble pre-measure
    let uPreH = 0;
    if (userText) {
      const uFS = 24, uLH = Math.round(uFS * 1.5);
      _pc.font = `400 ${uFS}px "Kalam", cursive`;
      const uL = _wrapText(_pc, userText, BW - BPX * 2);
      uPreH = 26 + BPY + uFS + (uL.length - 1) * uLH + BPY + 36;
    }

    // Dadi bubble pre-measure — shrink font to keep image under ~4000px tall
    let dFS = 28, dLH, dLines;
    while (dFS > 14) {
      _pc.font = `400 ${dFS}px "Kalam", cursive`;
      dLH = Math.round(dFS * 1.55);
      dLines = _wrapText(_pc, dadiText, BW - BPX * 2);
      if (106 + uPreH + 26 + BPY + dFS + (dLines.length - 1) * dLH + BPY + 40 + 70 + 60 <= 4000) break;
      dFS -= 2;
    }
    dLH = Math.round(dFS * 1.55);
    _pc.font = `400 ${dFS}px "Kalam", cursive`;
    dLines = _wrapText(_pc, dadiText, BW - BPX * 2);
    const dBH = BPY + dFS + (dLines.length - 1) * dLH + BPY;
    const H = Math.max(1350, 106 + uPreH + 26 + dBH + 40 + 70 + 60);

    const canvas = document.createElement('canvas');
    canvas.width = W; canvas.height = H;
    const ctx = canvas.getContext('2d');

    // Left panel (white)
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, LW, H);

    // Dadi image in left panel (random)
    const _cardImages = [
      '/public/images/dadi.png', '/public/images/dadi_dancing.png',
      '/public/images/dadi_karate.png', '/public/images/dadi_dancing_with_smirk.png',
    ];
    await fetch(_cardImages[Math.floor(Math.random() * _cardImages.length)])
      .then(r => r.blob()).then(blob => new Promise(resolve => {
        const url = URL.createObjectURL(blob);
        const img = new Image();
        img.onload = () => {
          const scale = Math.min((LW - 40) / img.naturalWidth, (H - 100) / img.naturalHeight);
          const dw = img.naturalWidth * scale, dh = img.naturalHeight * scale;
          ctx.drawImage(img, (LW - dw) / 2, (H - dh) / 2 - 30, dw, dh);
          URL.revokeObjectURL(url); resolve();
        };
        img.onerror = resolve; img.src = url;
      })).catch(() => {});

    // Brand bottom-left
    ctx.fillStyle = '#FF4D00';
    ctx.font = '400 30px "Kalam", cursive';
    ctx.letterSpacing = '3px';
    ctx.textAlign = 'center';
    ctx.fillText('MYDADI.IN', LW / 2, H - 40);
    ctx.textAlign = 'left'; ctx.letterSpacing = '0px';

    // Right panel (cream)
    ctx.fillStyle = '#F2EDE8';
    ctx.fillRect(LW, 0, W - LW, H);

    const RX = LW + PAD, RMAX = W - PAD, FY = H - 70;

    // "DADI AI" header
    ctx.fillStyle = '#8B1A1A';
    ctx.font = '700 22px "Kalam", cursive';
    ctx.letterSpacing = '3px';
    ctx.textAlign = 'center';
    ctx.fillText('DADI AI', LW + (W - LW) / 2, 72);
    ctx.textAlign = 'left'; ctx.letterSpacing = '0px';

    let curY = 106;

    // User bubble
    if (userText) {
      ctx.fillStyle = '#9e7a5a';
      ctx.font = '400 19px "Kalam", cursive';
      ctx.textAlign = 'right';
      ctx.fillText('You', RMAX, curY);
      ctx.textAlign = 'left';
      curY += 26;
      const uFS = 24, uLH = Math.round(uFS * 1.5);
      ctx.font = `400 ${uFS}px "Kalam", cursive`;
      const uLines = _wrapText(ctx, userText, BW - BPX * 2);
      const uBH = BPY + uFS + (uLines.length - 1) * uLH + BPY;
      ctx.fillStyle = '#FFFFFF';
      _roundRect(ctx, RMAX - BW, curY, BW, uBH, 18); ctx.fill();
      ctx.beginPath();
      ctx.moveTo(RMAX - 18, curY + uBH);
      ctx.lineTo(RMAX + 10, curY + uBH + 16);
      ctx.lineTo(RMAX - 46, curY + uBH);
      ctx.fill();
      ctx.fillStyle = '#2d1a10';
      ctx.font = `400 ${uFS}px "Kalam", cursive`;
      uLines.forEach((l, i) => ctx.fillText(l, RMAX - BW + BPX, curY + BPY + uFS + i * uLH));
      curY += uBH + 36;
    }

    // Dadi bubble
    ctx.fillStyle = '#9e7a5a';
    ctx.font = '400 19px "Kalam", cursive';
    ctx.fillText('Dadi \uD83D\uDC75\uD83C\uDFFE', RX, curY);
    curY += 26;
    ctx.fillStyle = '#8B1A1A';
    _roundRect(ctx, RX, curY, BW, dBH, 18); ctx.fill();
    ctx.beginPath();
    ctx.moveTo(RX + 18, curY + dBH);
    ctx.lineTo(RX - 10, curY + dBH + 16);
    ctx.lineTo(RX + 46, curY + dBH);
    ctx.fill();
    ctx.fillStyle = '#ffffff';
    ctx.font = `400 ${dFS}px "Kalam", cursive`;
    ctx.letterSpacing = '0.1px';
    dLines.forEach((l, i) => ctx.fillText(l, RX + BPX, curY + BPY + dFS + i * dLH));
    ctx.letterSpacing = '0px';

    // Footer brand right
    ctx.fillStyle = '#FF4D00';
    ctx.font = '400 22px "Kalam", cursive';
    ctx.letterSpacing = '3px';
    ctx.textAlign = 'right';
    ctx.fillText('MYDADI.IN', W - PAD, FY);
    ctx.textAlign = 'left'; ctx.letterSpacing = '0px';

    return canvas.toDataURL('image/png');
  }

  /* ── Share modal ── */
  function showShareModal(rawDadiText, rawUserText) {
    document.getElementById('dadi-share-modal')?.remove();
    const text = _cleanText(rawDadiText);
    const userText = rawUserText ? _cleanText(rawUserText) : '';
    const url = 'https://www.mydadi.in';

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
      el.textContent = msg; el.style.color = color || '#2e7d32';
    };

    modal.querySelector('#ds-close').onclick = () => modal.remove();
    modal.addEventListener('click', e => { if (e.target === modal) modal.remove(); });

    let _imgDataUrl = null;
    setTimeout(async () => {
      try {
        _imgDataUrl = await _generateCard(text, userText);
        const img = document.createElement('img');
        img.src = _imgDataUrl; img.alt = 'Share card';
        modal.querySelector('#ds-generating').style.display = 'none';
        const wrap = modal.querySelector('#ds-img-wrap');
        wrap.appendChild(img); wrap.style.display = 'block';
        modal.querySelector('#ds-btns').style.display = 'grid';
      } catch (_) { modal.querySelector('#ds-generating').textContent = 'Could not generate image.'; }
    }, 30);

    modal.querySelector('#ds-native')?.addEventListener('click', async () => {
      if (!_imgDataUrl) return;
      try {
        const blob = await (await fetch(_imgDataUrl)).blob();
        const file = new File([blob], 'dadi-ai.png', { type: 'image/png' });
        await navigator.share(navigator.canShare({ files: [file] }) ? { files: [file], title: 'Dadi AI', url } : { title: 'Dadi AI', url });
      } catch (_) {}
    });

    modal.querySelector('#ds-download').addEventListener('click', () => {
      if (!_imgDataUrl) return;
      const a = document.createElement('a');
      a.href = _imgDataUrl; a.download = 'dadi-ai.png'; a.click();
      if (typeof gtag !== 'undefined') gtag('event', 'share_message', { platform: 'download' });
    });

    modal.querySelector('#ds-copyimg').addEventListener('click', async () => {
      if (!_imgDataUrl) return;
      try {
        const blob = await (await fetch(_imgDataUrl)).blob();
        await navigator.clipboard.write([new ClipboardItem({ 'image/png': blob })]);
        setStatus('\u2713 Image copied!');
        if (typeof gtag !== 'undefined') gtag('event', 'share_message', { platform: 'copy_image' });
      } catch (_) { setStatus('Copy failed — try Download.', '#c0392b'); }
    });

    modal.querySelector('#ds-wa').addEventListener('click', () => {
      window.open('https://wa.me/?text=' + encodeURIComponent(url), '_blank');
      if (typeof gtag !== 'undefined') gtag('event', 'share_message', { platform: 'whatsapp' });
    });

    modal.querySelector('#ds-tw').addEventListener('click', () => {
      window.open(`https://twitter.com/intent/tweet?url=${encodeURIComponent(url)}`, '_blank');
      if (typeof gtag !== 'undefined') gtag('event', 'share_message', { platform: 'twitter' });
    });

    modal.querySelector('#ds-link').addEventListener('click', async e => {
      try { await navigator.clipboard.writeText(url); } catch (_) {}
      setStatus('\u2713 Link copied!');
      e.target.textContent = '\u2713 Copied!';
      setTimeout(() => { if (e.target) e.target.textContent = '\uD83D\uDD17 Copy Link'; }, 2000);
    });
  }

  function isUserArticle(article) {
    // User messages in Chainlit are right-aligned — their wrapper has justify-end or flex-row-reverse
    let el = article;
    for (let i = 0; i < 4; i++) {
      if (!el || el === document.body) break;
      const cls = el.className || '';
      if (/\bjustify-end\b/.test(cls) || /\bflex-row-reverse\b/.test(cls)) return true;
      el = el.parentElement;
    }
    return false;
  }

  function findUserMessageForArticle(dadiArticle) {
    const all = Array.from(document.querySelectorAll('[role="article"]'));
    const idx = all.indexOf(dadiArticle);
    // Walk backwards, skipping consecutive Dadi articles, until we hit a user article
    for (let i = idx - 1; i >= 0; i--) {
      if (isUserArticle(all[i])) {
        return (all[i].innerText || all[i].textContent || '').trim();
      }
    }
    return '';
  }

  /* ── Inject meme + share buttons into Dadi messages ── */
  // Meme: every Dadi article, immediately.
  // Share: only in the Chainlit action bar (the exact .-ml-1.5 container that
  //        holds copy/like/dislike). No fallback — if that bar isn't present yet
  //        the MutationObserver will retry when Chainlit adds it.
  const _memeInjected  = new WeakSet();
  const _shareInjected = new WeakSet();

  function _isDadiArticle(article) {
    if (isUserArticle(article)) return false;
    // Skip articles inside the input area
    let el = article.parentElement;
    for (let i = 0; i < 8; i++) {
      if (!el || el === document.body) break;
      if (el.querySelector('textarea, input[type="file"]')) return false;
      el = el.parentElement;
    }
    const text = (article.innerText || article.textContent || '').trim();
    return text.length >= 40;
  }

  function injectButtons() {
    if (isLoginPage()) return;

    document.querySelectorAll('[role="article"]').forEach(article => {
      if (!_isDadiArticle(article)) return;
      const text = (article.innerText || article.textContent || '').trim();

      // ── Meme: inject as soon as article is ready, find any button for styling ──
      if (!_memeInjected.has(article) && !article.querySelector('.dadi-meme-btn')) {
        _memeInjected.add(article);
        const anyBtn = article.querySelector('button');
        const mCls = anyBtn ? anyBtn.className + ' ' : 'inline-flex items-center justify-center h-9 w-9 ';
        const memeBtn = document.createElement('button');
        memeBtn.className = mCls + 'dadi-meme-btn';
        memeBtn.title = 'Make a meme';
        memeBtn.innerHTML = '<img src="/public/meme_icon.png" style="width:18px;height:18px;object-fit:contain;display:block;" alt="meme">';
        memeBtn.onclick = e => { e.stopPropagation(); showMemeModal(text); };
        // Append to article body (below text, before action bar)
        article.appendChild(memeBtn);
      }

      // ── Share: strictly requires the Chainlit action bar with native buttons ──
      if (!_shareInjected.has(article) && !article.querySelector('.dadi-share-btn')) {
        // Only the exact -ml-1.5 bar — no broad fallbacks
        const sBar = article.querySelector('.-ml-1\\.5') || article.querySelector('[class~="-ml-1.5"]');
        const chainlitBtn = sBar && sBar.querySelector('button:not(.dadi-share-btn):not(.dadi-meme-btn)');
        if (sBar && chainlitBtn) {
          _shareInjected.add(article);
          const shareBtn = document.createElement('button');
          shareBtn.className = chainlitBtn.className + ' dadi-share-btn';
          shareBtn.title = 'Share this response';
          shareBtn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8"/><polyline points="16 6 12 2 8 6"/><line x1="12" y1="2" x2="12" y2="15"/></svg>`;
          shareBtn.onclick = e => { e.stopPropagation(); showShareModal(text, findUserMessageForArticle(article)); };
          sBar.appendChild(shareBtn);
        }
      }
    });
  }

  new MutationObserver(injectButtons).observe(document.body, { childList: true, subtree: true });
  injectButtons();


})();
