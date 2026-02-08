# Better Breeze Check-in: Polish Plan

## Context

Working POC in `/Users/wimp/src/breeze-chms`. FastAPI backend + SvelteKit frontend + DYMO 550 printing via DYMO Web Service. Core flow works but needs: family-aware UX, client-side code gen, parallel attendance, infra polish. Target use case: kids check-in at church.

**Label design:** Shared family code. All kid labels + parent tear-off have the same code. One code per family per event instance.

---

## Stream 1: Client-Side Code Generation

Eliminates N API round-trips per person. Pure math — no server needed.

**Create** `web/src/lib/codes.ts`
- Port algorithm from `api/codes.py`: base30 encoding, 15-bit instance + 15-bit person packing, nibble checksum
- Export `generateCode(personId, instanceId)` and `decodeCode(code)`

**Edit** `web/src/lib/api.ts`
- Remove `generateCode()` and `decodeCode()` functions

**Edit** `web/src/routes/+page.svelte`
- Import `generateCode` from `$lib/codes` instead of `$lib/api`
- Replace async Promise.all code generation with synchronous `new Map(people.map(...))`

---

## Stream 2: Event Date Filtering

Only show today's/upcoming events.

**Edit** `api/breeze.py` — `get_events()`
- Add optional `start` and `end` params, pass through to Breeze API

**Edit** `api/server.py` — `/events` endpoint
- Default `start` to `date.today().isoformat()` if not provided

---

## Stream 3: Parallel Attendance Calls

**Edit** `api/server.py` — `batch_checkin()`
- Replace sequential loop with `asyncio.gather()`
- Add max batch size guard (15) as safety against rate limit (20 req/min)

---

## Stream 4: Family Flow UX (largest change)

### Backend changes

**Edit** `api/server.py`
- Add `extra_labels: list[LabelData] = []` to `BatchCheckinRequest` model
- In `batch_checkin`, append `extra_labels` to the print batch (these are parent labels, not attendance records)

### Frontend changes

**Edit** `web/src/lib/api.ts`
- Add `LabelData` interface (`name`, `code`, `extra`)
- Update `checkinBatch()` to accept `extraLabels` param
- Ensure `getFamily()` is typed and available

**Rewrite** `web/src/routes/+page.svelte` — two-phase flow:

**Phase 1 — Search & Select:**
- Event selector (unchanged)
- Search/filter the eligible people list (unchanged)
- Clicking a person fetches their family via `getFamily(person.id)` (lazy load, 1 API call)
- Display a **Family Card**: family members grouped, eligible members get checkboxes (auto-checked)

**Phase 2 — Check In & Print:**
- Confirm selection → build batch:
  - **Kid labels:** One per selected child. `name` = kid name, `code` = shared family code
  - **Parent label:** One per family. `name` = "[LastName] Family", `code` = same shared family code, `extra` = kid names
- Family code = `generateCode(min(selected_kid_ids), instanceId)` — deterministic, collision-resistant
- All labels in single print job via `extra_labels` field
- On success, clear selection, ready for next family

### State model change
- Replace flat `selectedPeople: Set<string>` with family-aware model: `selectedFamily`, `kidsToCheckin: Set<string>`
- Codes computed inline (not stored in map)

---

## Stream 5: Infrastructure

**Fix** `requirements.txt`
- Replace `requests` with: `fastapi>=0.109.0`, `uvicorn[standard]>=0.27.0`, `httpx>=0.26.0`, `pydantic>=2.5.0`, `pydantic-settings>=2.1.0`

**Edit** `web/package.json`
- Replace `@sveltejs/adapter-auto` with `@sveltejs/adapter-node`

**Edit** `web/svelte.config.js`
- Import from `@sveltejs/adapter-node`

**Edit** `web/src/lib/api.ts`
- `API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'`

**Edit** `api/server.py` — CORS
- Restrict `allow_origins` to localhost ports + LAN regex `^https?://192\.168\.\d+\.\d+:\d+$`

**Create** `Makefile`
- `install`: pip install + npm install
- `backend`: uvicorn with --host 0.0.0.0
- `frontend`: npm run dev -- --host
- `dev`: run both in parallel via `make -j2`

---

## Stream 6: Cleanup

- Delete `print.py`, `batch-print.py`, `get-printers.py` (superseded by `api/printer.py`)
- Add `.gitignore` if missing (`__pycache__`, `node_modules`, `.env`, `build/`, `.svelte-kit/`)

---

## Execution Order

1. Stream 5 (infra) — unblocks running the app
2. Stream 1 (client codes) — unblocks Stream 4
3. Stream 2 (event filtering) — independent
4. Stream 3 (parallel attendance) — independent
5. Stream 4 (family flow) — depends on 1, largest change
6. Stream 6 (cleanup) — last

## Verification

1. `make install` succeeds
2. `make dev` starts both backend (8000) and frontend (5173)
3. Frontend loads, shows today's events only
4. Select event → eligible people appear with codes (no API calls for codes)
5. Click a person → family card loads → kids auto-selected
6. Check in → attendance API calls fire in parallel → kid labels + parent label print in single batch
7. Access from second machine on LAN via `http://<host-ip>:5173`
