/* ══════════════════════════════════════════════
   DADI AI — custom.js
   Injects Dadi image on login page + chat widget
   ══════════════════════════════════════════════ */
(function () {
  const DADI_IMG = "/public/dadi.png";

  /* ── Styles injected into <head> ── */
  const STYLES = `
    @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,700;1,400;1,600&family=Lora:ital,wght@0,400;1,400&display=swap');

    /* ── LOGIN PAGE PANEL ── */
    #dadi-right-panel {
      position: fixed;
      top: 0; right: 0;
      width: 50%;
      height: 100vh;
      z-index: 1000;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      overflow: hidden;
      pointer-events: none;
    }
    #dadi-right-panel .drp-bg {
      position: absolute; inset: 0;
      background:
        radial-gradient(ellipse at 60% 30%, rgba(42,189,176,0.18) 0%, transparent 55%),
        radial-gradient(ellipse at 25% 80%, rgba(194,24,91,0.12) 0%, transparent 50%),
        linear-gradient(160deg, #f5e8d8 0%, #edddd0 45%, #e5cfc7 100%);
    }
    #dadi-right-panel .drp-pattern {
      position: absolute; inset: 0; opacity: 0.55;
      background-image: url("data:image/svg+xml,%3Csvg width='80' height='80' viewBox='0 0 80 80' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' stroke='%23D4AF37' stroke-opacity='0.1' stroke-width='0.8'%3E%3Ccircle cx='40' cy='40' r='30'/%3E%3Ccircle cx='40' cy='40' r='20'/%3E%3Ccircle cx='40' cy='40' r='10'/%3E%3Cpath d='M40 10L40 70M10 40L70 40M18 18L62 62M62 18L18 62'/%3E%3C/g%3E%3C/svg%3E");
    }
    #dadi-right-panel .drp-halo {
      position: absolute;
      top: 50%; left: 50%;
      transform: translate(-50%, -50%);
      width: 500px; height: 500px;
      background: radial-gradient(circle, rgba(212,175,55,0.15) 0%, rgba(194,24,91,0.08) 40%, transparent 70%);
      border-radius: 50%;
      animation: drp-halo-pulse 4s ease-in-out infinite;
    }
    @keyframes drp-halo-pulse {
      0%,100%{ transform: translate(-50%, -50%) scale(1); opacity: 1; }
      50%    { transform: translate(-50%, -50%) scale(1.06); opacity: 0.75; }
    }
    #dadi-right-panel img {
      position: relative; z-index: 2;
      height: 90vh; max-height: 640px;
      width: auto; object-fit: contain; object-position: bottom;
      mix-blend-mode: multiply;
      filter: drop-shadow(-10px 18px 40px rgba(80,20,30,0.28)) drop-shadow(0 4px 12px rgba(0,0,0,0.14));
      animation: drp-float 4s ease-in-out infinite, drp-enter 0.9s 0.2s cubic-bezier(0.34,1.56,0.64,1) both;
      transform-origin: bottom center;
    }
    @keyframes drp-float { 0%,100%{ transform: translateY(0); } 50%{ transform: translateY(-14px); } }
    @keyframes drp-enter { from{ transform: translateY(50px) scale(0.9); opacity: 0; } to{ transform: translateY(0) scale(1); opacity: 1; } }

    #dadi-right-panel .drp-card {
      position: absolute; top: 2.2rem; left: 2rem; z-index: 3;
      background: rgba(255,255,255,0.9);
      backdrop-filter: blur(14px);
      border: 1px solid rgba(212,175,55,0.28);
      border-radius: 16px;
      padding: 1rem 1.3rem;
      max-width: 200px;
      box-shadow: 0 8px 32px rgba(0,0,0,0.09);
      animation: drp-fadein 0.8s 0.7s ease both;
    }
    #dadi-right-panel .drp-card h3 {
      font-family: 'Playfair Display', serif !important;
      font-size: 1rem; font-style: italic;
      color: #2C1A0E; margin-bottom: 0.3rem;
    }
    #dadi-right-panel .drp-card h3 em { color: #C2185B; font-style: normal; }
    #dadi-right-panel .drp-card p {
      font-size: 0.74rem; color: #7A5C44;
      line-height: 1.5; font-family: 'Lora', serif;
      font-style: italic;
    }
    #dadi-right-panel .drp-pills {
      position: absolute; bottom: 2rem; left: 1.5rem; right: 1.5rem;
      display: flex; flex-wrap: wrap; gap: 0.45rem;
      justify-content: center; z-index: 3;
      animation: drp-fadein 0.8s 1s ease both;
    }
    #dadi-right-panel .drp-pill {
      background: rgba(255,255,255,0.85);
      backdrop-filter: blur(8px);
      border: 1px solid rgba(212,175,55,0.22);
      border-radius: 999px;
      padding: 0.3rem 0.78rem;
      font-size: 0.69rem; color: #3C2010;
      font-family: 'Lora', serif; font-style: italic;
    }
    @keyframes drp-fadein { from{ opacity: 0; transform: translateY(14px); } to{ opacity: 1; transform: translateY(0); } }

    /* ── RESPONSIVE ── */
    @media (max-width: 1023px) {
      #dadi-right-panel { width: 42%; }
      #dadi-right-panel img { height: 70vh; max-height: 480px; }
      #dadi-right-panel .drp-halo { width: 340px; height: 340px; }
      #dadi-right-panel .drp-card, #dadi-right-panel .drp-pills { display: none; }
    }
    @media (max-width: 767px) {
      #dadi-right-panel { width: 38%; opacity: 0.85; }
      #dadi-right-panel img { height: 55vh; max-height: 360px; }
      #dadi-right-panel .drp-halo { width: 240px; height: 240px; }
    }
    @media (max-width: 599px) {
      #dadi-right-panel { display: none; }
    }
  `;

  if (!document.getElementById('dadi-styles')) {
    const s = document.createElement('style');
    s.id = 'dadi-styles';
    s.textContent = STYLES;
    document.head.appendChild(s);
  }

  function isLoginPage() {
    return window.location.pathname.includes('login') ||
           !!document.querySelector('input[type="password"]');
  }

  function injectPanel() {
    if (document.getElementById('dadi-right-panel')) return;
    if (!isLoginPage()) return;

    const panel = document.createElement('div');
    panel.id = 'dadi-right-panel';
    panel.innerHTML = `
      <div class="drp-bg"></div>
      <div class="drp-pattern"></div>
      <div class="drp-halo"></div>
      <div class="drp-card">
        <h3>Meet <em>Dadi</em></h3>
        <p>Your AI grandmother — ancient wisdom, sharp roasts &amp; home remedies for everything.</p>
      </div>
      <img src="${DADI_IMG}" alt="Dadi" />
      <div class="drp-pills">
        <div class="drp-pill">RAG-powered wisdom</div>
        <div class="drp-pill">Desi roasts included</div>
        <div class="drp-pill">Home remedies</div>
      </div>
    `;
    document.body.appendChild(panel);
    console.log('[Dadi] Login panel injected');
  }

  /* ── Persistent chat logo injected into <html> — outside React's tree ── */
  function injectChatLogo() {
    if (document.getElementById('dadi-chat-logo')) return;
    const el = document.createElement('div');
    el.id = 'dadi-chat-logo';
    el.style.cssText = [
      'position:fixed', 'top:8px', 'left:50%', 'transform:translateX(-50%)',
      'z-index:99999', 'pointer-events:none', 'display:flex',
      'align-items:center', 'justify-content:center',
    ].join(';');
    const img = document.createElement('img');
    img.src = DADI_IMG;
    img.alt = 'Dadi';
    img.style.cssText = 'height:48px;width:auto;object-fit:contain;display:block;';
    el.appendChild(img);
    document.documentElement.appendChild(el); // inject into <html>, not <body>
    console.log('[Dadi] Chat logo injected into <html>');
  }

  function removeChatLogo() {
    const el = document.getElementById('dadi-chat-logo');
    if (el) el.remove();
  }

  function removePanel() {
    const p = document.getElementById('dadi-right-panel');
    if (p) p.remove();
    const s = document.getElementById('dadi-skip-wrapper');
    if (s) s.remove();
  }

  function injectSkipButton() {
    if (document.getElementById('dadi-skip-wrapper')) return;
    const submitBtn = document.querySelector('button[type="submit"]');
    if (!submitBtn) return;

    const wrapper = document.createElement('div');
    wrapper.id = 'dadi-skip-wrapper';
    wrapper.style.cssText = 'display:flex; align-items:center; gap:0.6rem; margin-top:0.85rem; justify-content:center;';

    const btn = document.createElement('button');
    btn.type = 'button';
    btn.textContent = 'Skip Login';
    btn.style.cssText = [
      'background:none',
      'border:1px solid rgba(194,24,91,0.35)',
      'border-radius:999px',
      'color:#C2185B',
      'font-size:0.78rem',
      'padding:0.3rem 0.9rem',
      'cursor:pointer',
      'font-family:Lora,serif',
      'font-style:italic',
      'transition:background 0.2s',
      'white-space:nowrap',
      'flex-shrink:0',
    ].join(';');
    btn.onmouseenter = () => btn.style.background = 'rgba(194,24,91,0.07)';
    btn.onmouseleave = () => btn.style.background = 'none';

    const note = document.createElement('span');
    note.textContent = "Dadi won't save your chat history.";
    note.style.cssText = 'font-size:0.68rem; color:#9e7a5a; font-family:Lora,serif; font-style:italic; line-height:1.3;';

    btn.onclick = async () => {
      btn.disabled = true;
      btn.textContent = 'Entering...';
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
          btn.textContent = 'Skip Login';
          btn.disabled = false;
        }
      } catch (e) {
        btn.textContent = 'Skip Login';
        btn.disabled = false;
      }
    };

    wrapper.appendChild(btn);
    wrapper.appendChild(note);
    submitBtn.closest('form')
      ? submitBtn.closest('form').appendChild(wrapper)
      : submitBtn.parentNode.insertAdjacentElement('afterend', wrapper);
  }

  /* ── Route change cleanup ── */
  let lastPath = window.location.pathname;
  new MutationObserver(() => {
    if (window.location.pathname !== lastPath) {
      lastPath = window.location.pathname;
      removePanel();
    }
    if (isLoginPage()) {
      injectPanel();
      injectSkipButton();
      removeChatLogo();
    } else {
      removePanel();
      injectChatLogo();
    }
  }).observe(document.body, { childList: true, subtree: true });

  /* ── Poll until injected ── */
  const poll = setInterval(() => {
    if (isLoginPage()) {
      injectPanel();
      injectSkipButton();
      removeChatLogo();
    } else {
      injectChatLogo();
    }
    if (document.getElementById('dadi-right-panel') || document.getElementById('dadi-chat-logo')) clearInterval(poll);
  }, 200);
  setTimeout(() => clearInterval(poll), 10000);
})();
