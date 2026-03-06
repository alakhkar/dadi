(function () {
  const DADI_IMG = "/public/dadi.png";

  /* ── Styles ── */
  const STYLES = `
    @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,700;1,400&family=Lora:ital,wght@0,400;1,400&display=swap');

    html, body, #root { background: #ffffff !important; }

    #dadi-img-col {
      flex-shrink: 0;
      display: flex;
      align-items: flex-end;
    }
    #dadi-img-col img {
      height: 460px;
      width: auto;
      object-fit: contain;
      object-position: bottom;
      filter: drop-shadow(-4px 12px 24px rgba(80, 20, 30, 0.15));
      animation: dadi-float 4s ease-in-out infinite;
    }
    @keyframes dadi-float {
      0%, 100% { transform: translateY(0); }
      50%       { transform: translateY(-12px); }
    }

    @media (max-width: 768px) {
      #dadi-img-col { display: none !important; }
    }
  `;

  if (!document.getElementById('dadi-styles')) {
    const s = document.createElement('style');
    s.id = 'dadi-styles';
    s.textContent = STYLES;
    document.head.appendChild(s);
  }

  /* ── Helpers ── */
  function isLoginPage() {
    return window.location.pathname.includes('login') ||
           !!document.querySelector('input[type="password"]');
  }

  function removeAll() {
    ['dadi-img-col', 'dadi-skip-wrapper'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.remove();
    });
  }

  /* ── Inject Dadi image next to the login form ── */
  function injectImage() {
    if (document.getElementById('dadi-img-col')) return;
    const form = document.querySelector('form');
    if (!form) return;

    // Find the nearest flex/centering ancestor of the form
    let container = form.parentElement;
    for (let i = 0; i < 6; i++) {
      if (!container || container === document.body) break;
      const cs = window.getComputedStyle(container);
      if (cs.display === 'flex' || cs.display === 'grid') break;
      container = container.parentElement;
    }
    if (!container || container === document.body) container = form.parentElement;

    // Lay it out as a centered row
    container.style.cssText = [
      'display:flex',
      'flex-direction:row',
      'align-items:center',
      'justify-content:center',
      'gap:3rem',
      'min-height:100vh',
      'padding:2rem',
      'background:#ffffff',
    ].join(';');

    // Image column
    const imgCol = document.createElement('div');
    imgCol.id = 'dadi-img-col';
    imgCol.innerHTML = `<img src="${DADI_IMG}" alt="Dadi">`;
    container.appendChild(imgCol);

    console.log('[Dadi] Login redesign applied ✓');
  }

  /* ── Inject Skip Login button ── */
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
      'font-family:Lora,serif',
      'font-style:italic',
      'transition:background 0.2s',
      'white-space:nowrap',
    ].join(';');
    btn.onmouseenter = () => btn.style.background = 'rgba(139,26,26,0.06)';
    btn.onmouseleave = () => btn.style.background = 'none';

    const note = document.createElement('span');
    note.textContent = "Chat history won't be saved.";
    note.style.cssText = 'font-size:0.67rem;color:#9e7a5a;font-family:Lora,serif;font-style:italic;line-height:1.3;';

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
          btn.textContent = 'Continue as Guest →';
          btn.disabled = false;
        }
      } catch (e) {
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

  /* ── Route change cleanup ── */
  let lastPath = window.location.pathname;
  new MutationObserver(() => {
    if (window.location.pathname !== lastPath) {
      lastPath = window.location.pathname;
      removeAll();
    }
    if (!isLoginPage()) removeAll();
  }).observe(document.body, { childList: true, subtree: true });

  /* ── Poll until injected ── */
  const poll = setInterval(() => {
    if (isLoginPage()) {
      injectImage();
      injectSkipButton();
    }
    if (document.getElementById('dadi-img-col')) clearInterval(poll);
  }, 200);
  setTimeout(() => clearInterval(poll), 10000);
})();
