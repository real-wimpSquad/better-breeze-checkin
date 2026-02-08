# better-breeze-checkin

Kids check-in kiosk for [Breeze ChMS](https://www.breezechms.com/). Family-aware batch check-in with DYMO label printing over CUPS.

## Quick Start

```bash
# 1. Clone and configure
git clone https://github.com/real-wimpSquad/better-breeze-checkin.git
cd better-breeze-checkin
cp .env.example .env
# Edit .env with your Breeze API key
```

### macOS

```bash
./setup/macos-setup.sh   # Verifies Docker, CUPS, and printer
make docker-up            # Builds and starts containers
# Open http://localhost:5173
```

### Windows

1. Install [Docker Desktop](https://www.docker.com/products/docker-desktop/) (uses WSL2 backend)
2. Plug in the DYMO LabelWriter 550
3. Open an **Admin PowerShell** and run:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\setup\windows-setup.ps1
```

This will:
- Install `usbipd-win` (forwards USB to WSL2)
- Attach the DYMO printer to WSL2
- Install and configure CUPS inside WSL2
- Create a scheduled task so the printer reconnects after reboot

4. Then in a WSL2 terminal:

```bash
cd /path/to/better-breeze-checkin
docker compose up --build -d
# Open http://localhost:5173
```

### Development (no Docker)

```bash
make install   # pip install + npm install
make dev       # Runs API (port 8000) + frontend (port 5173) in parallel
```

## Architecture

```
┌─────────────────┐     ┌──────────────────┐
│  Web (SvelteKit) │────▶│  API (FastAPI)    │
│  :5173           │     │  :8000            │
│  adapter-node    │     │  uvicorn          │
└─────────────────┘     └──────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │  Breeze ChMS API     │
                    │  breezechms.com      │
                    └──────────────────────┘
                               │
                    ┌──────────▼───────────┐
                    │  CUPS → DYMO 550     │
                    │  Label printing      │
                    └──────────────────────┘
```

- **Web container** — SvelteKit with adapter-node, serves the kiosk UI on port 5173
- **API container** — FastAPI, talks to Breeze ChMS and prints labels via CUPS
- API uses `network_mode: host` so `lp` commands reach the host's CUPS daemon directly

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `CHECKIN_BREEZE_API_KEY` | Yes | — | Your Breeze API key |
| `CHECKIN_BREEZE_SUBDOMAIN` | No | `connectionpointchurch` | Your Breeze subdomain |
| `CHECKIN_PRINTER_NAME` | No | `DYMO_LabelWriter_550` | CUPS printer name |

## Printing

Labels are rendered with Pillow (no DYMO proprietary software needed) and sent to CUPS as a single PDF batch job.

- **Kid labels** — Full-width with name and check-in code
- **Parent labels** — Two-half tear-off with family name, code, and kid names

The printer name must match your CUPS configuration. Verify with:

```bash
lpstat -p    # List configured printers
```

### Printing on Windows

The Windows setup script handles this automatically. Under the hood:
- `usbipd-win` forwards the USB printer from Windows into WSL2
- CUPS runs inside WSL2 and manages the printer
- The API container reaches CUPS via `network_mode: host`
- A scheduled task re-attaches the printer after each reboot

If the printer stops working after a reboot, open Admin PowerShell and run:

```powershell
usbipd list                           # Find the DYMO bus ID
usbipd attach --wsl --busid <BUS_ID>  # Re-attach
```

## Docker Commands

```bash
make docker-up     # Build and start (detached)
make docker-down   # Stop and remove containers
```

Or directly:

```bash
docker compose up --build -d
docker compose down
docker compose logs -f        # Tail logs
docker compose logs api       # API logs only
```

## API Endpoints

The API runs on port 8000. See `breeze.http` for runnable examples (VS Code REST Client / IntelliJ).

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `GET` | `/events` | List events (defaults to today) |
| `GET` | `/events/:id/eligible` | Eligible people for check-in |
| `GET` | `/events/:id/attendance` | Current attendance |
| `POST` | `/checkin` | Check in one person |
| `POST` | `/checkin/batch` | Batch check-in (max 15) |
| `POST` | `/checkout` | Remove from event |
| `GET` | `/people/:id` | Person details |
| `GET` | `/people/:id/family` | Family members |
| `GET` | `/printer/status` | Printer connected? |
| `POST` | `/printer/print` | Print labels directly |

## License

MIT
