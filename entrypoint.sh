#!/bin/sh
# Bridge localhost:631 → host CUPS so lp/lpstat Host header says "localhost"
if [ -n "$CUPS_HOST" ]; then
    socat TCP-LISTEN:631,fork,reuseaddr TCP:"$CUPS_HOST":631 &
fi

exec python3 -m uvicorn api.server:app --host 0.0.0.0 --port 8000
