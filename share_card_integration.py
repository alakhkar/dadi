"""
Dadi AI — Share Card Integration
=================================

Drop this into your app.py (or import it and register the route).

Usage in app.py:
    from share_card_integration import register_share_card_route
    register_share_card_route(_cl_app)

Then call from Chainlit chat after Dadi responds:
    await _send_share_card_action(user_question, dadi_response)
"""

import html as _html
import pathlib
import urllib.parse

# ── Card HTML template ────────────────────────────────────────────────────────
# Inlines all styles + html2canvas for offline PNG export.
# q / r are injected server-side (HTML-escaped) → no XSS risk.

_CARD_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>Dadi AI — Share Card</title>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,700;1,700;1,900&family=DM+Sans:opsz,wght@9..40,400;9..40,600&display=swap" rel="stylesheet"/>
<script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>
<style>
*{{box-sizing:border-box;margin:0;padding:0;}}
body{{
  background:#0d0d0d;font-family:'DM Sans',sans-serif;
  min-height:100vh;display:flex;flex-direction:column;
  align-items:center;justify-content:center;padding:24px;gap:20px;
}}

/* ── CARD ── */
#card{{
  width:480px;height:480px;
  position:relative;border-radius:18px;overflow:hidden;
  box-shadow:0 0 0 1px rgba(255,255,255,0.07),0 40px 100px rgba(0,0,0,0.9);
  flex-shrink:0;
}}
.bg-base{{position:absolute;inset:0;background:#0a0208;}}
.bg-grad{{
  position:absolute;inset:0;
  background:radial-gradient(ellipse 55% 60% at 88% 95%,#c99060 0%,#7a3520 25%,#2a0a14 55%,transparent 75%);
}}
.bg-vignette{{
  position:absolute;inset:0;
  background:linear-gradient(to right,#0a0208 0%,#0a0208 45%,rgba(10,2,8,0.85) 60%,rgba(10,2,8,0.3) 75%,transparent 100%);
}}
.bg-glow{{
  position:absolute;bottom:-60px;left:-40px;
  width:300px;height:300px;border-radius:50%;
  background:#b42838;opacity:0.12;filter:blur(60px);
}}
.top-line{{
  position:absolute;top:0;left:0;right:0;height:2.5px;z-index:10;
  background:linear-gradient(90deg,transparent 0%,#b42838 15%,#f0c84a 45%,#f5da80 55%,#b42838 85%,transparent 100%);
}}
.dadi-img{{
  position:absolute;bottom:0;right:-40px;
  height:80%;width:auto;object-fit:contain;object-position:bottom right;
  -webkit-mask-image:linear-gradient(to right,transparent 0%,transparent 8%,rgba(0,0,0,0.5) 20%,black 32%);
  mask-image:linear-gradient(to right,transparent 0%,transparent 8%,rgba(0,0,0,0.5) 20%,black 32%);
  filter:drop-shadow(-20px 0 40px rgba(10,2,8,0.9));
}}
.text-panel{{
  position:absolute;top:0;left:0;bottom:0;width:58%;
  background:linear-gradient(to right,#0a0208 0%,#0a0208 80%,transparent 100%);
  z-index:4;pointer-events:none;
}}
.content{{
  position:absolute;top:0;left:0;bottom:0;width:54%;
  z-index:5;padding:32px 24px 28px 32px;
  display:flex;flex-direction:column;
}}
.logo{{display:flex;align-items:center;gap:7px;margin-bottom:22px;}}
.logo-gem{{
  width:13px;height:13px;background:#b42838;
  clip-path:polygon(50% 0%,100% 50%,50% 100%,0% 50%);flex-shrink:0;
}}
.logo-text{{font-size:10px;letter-spacing:0.28em;text-transform:uppercase;color:#e8b84b;font-weight:700;}}
.question{{
  display:flex;align-items:center;gap:8px;
  font-size:12px;color:rgba(255,255,255,0.38);
  margin-bottom:18px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;
}}
.question::before{{content:'';display:block;width:16px;height:1px;background:rgba(255,255,255,0.2);flex-shrink:0;}}
.quote-wrap{{display:flex;gap:13px;align-items:stretch;flex:1;overflow:hidden;}}
.quote-bar{{
  width:2.5px;border-radius:2px;flex-shrink:0;
  background:linear-gradient(180deg,#b42838 0%,rgba(180,40,56,0.2) 100%);
}}
.response{{
  font-family:'Playfair Display',serif;font-style:italic;
  font-size:15px;line-height:1.55;color:rgba(255,255,255,0.95);
  overflow:hidden;display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:8;
}}
.footer{{margin-top:16px;}}
.footer-url{{font-size:10px;letter-spacing:0.22em;text-transform:uppercase;color:rgba(255,255,255,0.4);font-weight:600;}}

/* ── DOWNLOAD BUTTON ── */
#dl-btn{{
  padding:12px 28px;background:#b42838;color:#fff;
  border:none;border-radius:100px;font-size:14px;font-weight:600;
  font-family:'DM Sans',sans-serif;cursor:pointer;
  letter-spacing:0.04em;transition:all 0.18s;
}}
#dl-btn:hover{{background:#8f1f2c;transform:translateY(-1px);}}
#dl-btn:active{{transform:none;}}
#dl-btn.loading{{opacity:0.6;cursor:default;}}
</style>
</head>
<body>
<div id="card">
  <div class="bg-base"></div>
  <div class="bg-grad"></div>
  <div class="bg-vignette"></div>
  <div class="bg-glow"></div>
  <div class="top-line"></div>
  <img class="dadi-img" src="/public/images/dadi_dancing.png" onerror="this.style.display='none'"/>
  <div class="text-panel"></div>
  <div class="content">
    <div class="logo">
      <div class="logo-gem"></div>
      <div class="logo-text">Dadi AI</div>
    </div>
    <div class="question">{question}</div>
    <div class="quote-wrap">
      <div class="quote-bar"></div>
      <div class="response">{response}</div>
    </div>
    <div class="footer">
      <div class="footer-url">mydadi.in</div>
    </div>
  </div>
</div>

<button id="dl-btn" onclick="downloadCard()">⬇ Download Card</button>

<script>
async function downloadCard() {{
  const btn = document.getElementById('dl-btn');
  btn.textContent = 'Generating…';
  btn.classList.add('loading');
  try {{
    const canvas = await html2canvas(document.getElementById('card'), {{
      scale: 2,          // 2× = 960×960px output (crisp on Retina)
      useCORS: true,
      backgroundColor: null,
      logging: false,
    }});
    const link = document.createElement('a');
    link.download = 'dadi-share-card.png';
    link.href = canvas.toDataURL('image/png');
    link.click();
  }} catch(e) {{
    alert('Could not generate card: ' + e.message);
  }} finally {{
    btn.textContent = '⬇ Download Card';
    btn.classList.remove('loading');
  }}
}}
</script>
</body>
</html>"""


def build_share_card_html(question: str, response: str) -> str:
    """
    Returns the full share card HTML with question + response safely injected.
    """
    MAX_RESPONSE = 280
    if len(response) > MAX_RESPONSE:
        response = response[:MAX_RESPONSE].rsplit(" ", 1)[0] + "…"

    return _CARD_TEMPLATE.format(
        question=_html.escape(question),
        response=_html.escape(response),
    )


def register_share_card_route(app) -> None:
    """
    Register GET /share-card on the given FastAPI app.

    Query params:
      q  — the user's question
      r  — Dadi's response
    """
    from fastapi import Request
    from fastapi.responses import HTMLResponse

    @app.get("/share-card")
    async def share_card(request: Request):
        q = request.query_params.get("q", "").strip()
        r = request.query_params.get("r", "").strip()
        if not q or not r:
            return HTMLResponse("<p>Missing q or r params</p>", status_code=400)
        return HTMLResponse(build_share_card_html(q, r))


# ── Chainlit helper ───────────────────────────────────────────────────────────

async def send_share_card_action(question: str, response: str) -> None:
    """
    Call this after Dadi replies to offer a share card button in the chat.
    """
    import chainlit as cl
    import urllib.parse

    url = "/share-card?q={}&r={}".format(
        urllib.parse.quote(question[:200], safe=""),
        urllib.parse.quote(response[:300], safe=""),
    )

    await cl.Message(
        content="",
        actions=[
            cl.Action(
                name="share_card",
                label="🪴 Share this as a card",
                url=url,
                description="Open your Dadi share card",
            )
        ],
    ).send()
