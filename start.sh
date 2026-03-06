#!/bin/bash
set -e

# Find Chainlit's frontend index.html and inject custom.js
CHAINLIT_DIR=$(python -c "import chainlit, os; print(os.path.dirname(chainlit.__file__))")
INDEX_HTML="$CHAINLIT_DIR/frontend/dist/index.html"

if [ -f "$INDEX_HTML" ]; then
    if ! grep -q "custom.js" "$INDEX_HTML"; then
        sed -i 's|</head>|<script src="/public/custom.js"></script></head>|' "$INDEX_HTML"
        echo "[Dadi] Injected custom.js into Chainlit frontend ✓"
    else
        echo "[Dadi] custom.js already injected ✓"
    fi
else
    echo "[Dadi] Warning: Chainlit index.html not found at $INDEX_HTML"
fi

exec chainlit run app.py --host 0.0.0.0 --port ${PORT:-8000}
