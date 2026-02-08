#!/usr/bin/env bash
set -euo pipefail

# macOS setup for better-breeze-checkin
# Ensures CUPS is running and DYMO printer is configured.
# Run: chmod +x setup/macos-setup.sh && ./setup/macos-setup.sh

PRINTER_NAME="DYMO_LabelWriter_550"

step() { printf '\n\033[36m>> %s\033[0m\n' "$1"; }
ok()   { printf '   \033[32m%s\033[0m\n' "$1"; }
warn() { printf '   \033[33m%s\033[0m\n' "$1"; }

# --- 1. Check Docker ---

step "Checking Docker..."
if ! command -v docker &>/dev/null; then
    echo "Docker not found. Install Docker Desktop for Mac first."
    echo "  https://www.docker.com/products/docker-desktop/"
    exit 1
fi
if ! docker info &>/dev/null; then
    echo "Docker is installed but not running. Start Docker Desktop first."
    exit 1
fi
ok "Docker is running."

# --- 2. Check CUPS ---

step "Checking CUPS..."
if ! lpstat -r &>/dev/null; then
    warn "CUPS not responding. Starting..."
    sudo cupsctl
fi
ok "CUPS is running."

# --- 3. Check DYMO printer ---

step "Looking for DYMO LabelWriter..."
if lpstat -p "$PRINTER_NAME" &>/dev/null; then
    ok "Printer '$PRINTER_NAME' already configured."
else
    PRINTER_URI=$(lpinfo -v 2>/dev/null | grep -i 'usb.*dymo\|usb.*label' | head -1 | awk '{print $2}')
    if [ -z "$PRINTER_URI" ]; then
        warn "DYMO not detected via USB."
        warn "Make sure it's plugged in. You can add it manually:"
        warn "  sudo lpadmin -p $PRINTER_NAME -E -v usb://DYMO/LabelWriter%20550 -m everywhere"
    else
        ok "Found: $PRINTER_URI"
        sudo lpadmin -p "$PRINTER_NAME" -E -v "$PRINTER_URI" -m everywhere 2>/dev/null || \
        sudo lpadmin -p "$PRINTER_NAME" -E -v "$PRINTER_URI" -m raw
        sudo cupsaccept "$PRINTER_NAME" 2>/dev/null || true
        sudo cupsenable "$PRINTER_NAME" 2>/dev/null || true
        ok "Printer '$PRINTER_NAME' configured."
    fi
fi

# --- 4. Check .env ---

step "Checking .env..."
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

if [ -f "$PROJECT_DIR/.env" ]; then
    ok ".env exists."
    if grep -q "your_api_key_here" "$PROJECT_DIR/.env"; then
        warn ".env still has placeholder API key. Edit it before running."
    fi
else
    if [ -f "$PROJECT_DIR/.env.example" ]; then
        cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
        warn "Created .env from .env.example — edit it with your API key."
    else
        warn "No .env file found. Create one with CHECKIN_BREEZE_API_KEY."
    fi
fi

# --- Done ---

printf '\n\033[32m========================================\033[0m\n'
printf '\033[32m Setup complete!\033[0m\n'
printf '\033[32m========================================\033[0m\n'
echo ""
echo " Next steps:"
echo "   make docker-up"
echo "   Open http://localhost:5173"
echo ""
echo " To verify printing:"
echo "   lpstat -p $PRINTER_NAME"
echo ""
