FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --prefer-binary -r requirements.txt

# Patch Chainlit config.py for Pydantic 2.12 compatibility.
# Pydantic 2.12 strict forward-reference enforcement breaks Chainlit 1.3.x:
# CodeSettings references Action before it is fully defined (circular import).
# Fix: replace the action_callbacks annotation with Any.
RUN python3 -c "import re, pathlib; p = pathlib.Path('/usr/local/lib/python3.11/site-packages/chainlit/config.py'); t = p.read_text(); t = t.replace('from typing import', 'from typing import Any,', 1) if 'from typing import' in t and 'Any' not in t else t; t = re.sub(r'action_callbacks\s*:\s*[^\n=]+', 'action_callbacks: Any', t); p.write_text(t); print('[Patch] Chainlit config.py patched for Pydantic 2.12')"

COPY . .

RUN chmod +x start.sh

EXPOSE 8000
CMD ["./start.sh"]
