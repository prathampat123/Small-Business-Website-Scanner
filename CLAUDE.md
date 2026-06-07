# Small Business Website Scanner — CLAUDE.md

This file is the authoritative reference for AI assistants working on this codebase.
It describes the actual implemented state, development conventions, and quality gates.

---

## What This Project Does

Scans a geographic area (location + radius) to find small businesses, evaluates their
online presence, and generates AI-powered website proposals for businesses with no site
or an outdated one. The goal is automated lead discovery for a web design/development service.

---

## Core Features

### 1. Area Scanner
- User inputs a location (city, address, or zip) and a radius in miles
- Calls the Google Places API (New) to return businesses within that radius
- Pulls: name, address, phone, website URL, category, rating, review count, top reviews, lat/lng
- Geocoding via Nominatim (OpenStreetMap) — no auth required
- Category filter maps friendly names (e.g. "restaurants") to Google Places types

### 2. Website Scorer
- For each business, fetches their website and runs two-step analysis:
  1. **Signal extraction** — copyright year (regex), mobile viewport meta, HTTPS status,
     `Last-Modified` header, CMS/generator meta tag
  2. **Claude scoring** — stripped HTML (scripts/styles removed, truncated to 3000 chars)
     + signals sent to Claude; returns structured JSON lead classification
- Lead status outcomes:
  - **Hot Lead** — no website, or URL returns error/timeout/blank
  - **Warm Lead** — website exists but outdated (old copyright, no viewport, old CMS)
  - **Not a Lead** — modern, mobile-friendly, recently updated site
- Claude returns: `{"lead_status": "Hot Lead|Warm Lead|Not a Lead", "reason": "...", "signals": [...]}`

### 3. Lead Dashboard — two UIs exist

**React SPA** (`frontend/`) — primary production UI:
- Three themes: daylight, midnight, carbon (CSS variables)
- Two density modes: comfortable / compact
- Sidebar with nav (Overview, Leads, Map, Areas) + live stats breakdown
- Topbar with search, area selector, "New Scan" button
- Stats row: total leads, no-website %, outdated %, high-opportunity %, has-website %
- Filter chips (All / No website / Outdated / Has site) + sort dropdown
- Lead table with columns: Business, Web presence, Category, Site age, Rating, Reviews, Phone, Social, Opportunity
- Lead detail slideover (slides in from right) — shows full info + proposal output
- Scan modal with animated radar during scan, live discovered count, progress bar
- Category chips: Any, Restaurants, Retail, Contractors, Real Estate, Law Firms, Finance, Health, Beauty, Auto, Home Services

**Streamlit dashboard** (`dashboard/app.py`) — alternative/legacy UI:
- Sidebar scan form (location, radius slider, max results slider)
- Pydeck/Mapbox map with color-coded pins
- Metrics cards + filterable business table
- Proposal generator dropdown + display

### 4. Website Proposal Generator
- For any Hot or Warm Lead, user clicks "Generate Proposal"
- Claude receives: name, category, address, phone, rating, review count, website URL, top 10 reviews verbatim
- Claude returns structured JSON:
  ```json
  {
    "design_brief": "2-3 sentences on tone, style, color palette",
    "sections": ["Hero", "Services", "About", "Testimonials", "Contact"],
    "headline": "punchy hero headline",
    "tagline": "short supporting tagline",
    "selling_points": ["3-5 points extracted from reviews"],
    "seo_keywords": ["5-8 local SEO keywords"]
  }
  ```

### 5. Automation (Planned — not yet implemented)
- Scheduled re-scans of saved areas (weekly cron)
- Email digest of new leads (Resend or SendGrid)
- Auto-generate proposals for every new Hot Lead

---

## Tech Stack

| Layer | Choice | Notes |
|---|---|---|
| Language | Python 3.10+ | |
| Backend API | FastAPI + Uvicorn | Async, also serves the React SPA static files |
| Primary UI | React 18 (no build step) | Loaded via CDN + Babel standalone in `frontend/index.html` |
| Secondary UI | Streamlit 1.39 | dashboard/app.py — calls FastAPI at localhost |
| HTTP client | httpx 0.27 | Used in scanner.py and analyzer.py |
| HTML parsing | BeautifulSoup4 | analyzer.py — signal extraction from fetched pages |
| AI | Claude API (`claude-sonnet-4-6`) | Website scoring + proposal generation |
| Business data | Google Places API (New) | REST, POST to searchNearby |
| Geocoding | Nominatim (OpenStreetMap) | Free, no auth; used in scanner.py |
| Maps (React) | Leaflet 1.9.4 | map.jsx |
| Maps (Streamlit) | Pydeck + Mapbox | dashboard/app.py |
| Storage | Airtable via pyairtable | database.py — Scans, Businesses, Proposals tables |
| Data frames | pandas ≥ 2.2 | Streamlit dashboard table |
| Deployment | Railway (API) + Streamlit Community Cloud (dashboard) | |

> **Note:** SQLite/SQLAlchemy is NOT used. The only persistence layer is Airtable.
> `models.py` and `schemas.py` are not yet created (referenced in early docs but not implemented).

---

## Project Structure — Actual State

```
Small-Business-Scanner/
├── CLAUDE.md                    # This file
├── README.md
├── .env                         # Not committed — contains API keys
├── .env.example                 # Key template
├── .gitignore
├── requirements.txt
├── .streamlit/
│   └── config.toml              # headless=true, port=8501
│
├── backend/
│   ├── __init__.py
│   ├── main.py                  # FastAPI app: 7 endpoints + static file serving
│   ├── scanner.py               # Google Places search + Nominatim geocoding
│   ├── analyzer.py              # Website fetch + signal extract + Claude scoring
│   ├── proposal.py              # Claude proposal generation
│   └── database.py              # Airtable connection (pyairtable)
│                                # NOTE: models.py and schemas.py do NOT yet exist
│
├── dashboard/
│   └── app.py                   # Streamlit dashboard (secondary UI)
│
├── frontend/                    # React SPA — primary production UI
│   ├── index.html               # Entry point: CSS theming system + CDN script tags
│   ├── main.jsx                 # React.render entry
│   ├── app.jsx                  # Main dashboard layout + state management
│   ├── ui.jsx                   # Shared components: Icon, Avatar, StatusBadge, StatCard
│   ├── data.jsx                 # API fetch wrappers: fetchBusinesses, runScanAPI, etc.
│   ├── map.jsx                  # Leaflet map integration
│   └── tweaks-panel.jsx         # Theme/density switcher panel
│
└── tests/                       # NOT YET CREATED — no test files exist
```

---

## API Endpoints (backend/main.py)

| Method | Path | Description |
|---|---|---|
| `POST` | `/scan` | Geocode location → Places search → score each site → save to Airtable |
| `POST` | `/propose/{business_id}` | Generate Claude proposal for a business |
| `GET` | `/businesses` | List businesses; optional `?scan_id=` and `?lead_status=` filters |
| `GET` | `/scans` | List all past scans from Airtable |
| `GET` | `/config` | Returns `{"mapbox_token": "..."}` for the frontend |
| `GET` | `/health` | Health check — returns `{"status": "ok"}` |
| `GET` | `/` | Serves `frontend/index.html` (React SPA entry) |
| Static | `/static/*` | Serves `frontend/` directory (JSX files, assets) |

**Port:** FastAPI runs on **8080** (not 8000 — changed in commit `feba649`).
The Streamlit dashboard connects to `http://localhost:8000` — update if the port is ever unified.

---

## Data Flow

```
Browser (React SPA)
        │ HTTP POST /scan
        ▼
FastAPI main.py
  ├── scanner.py
  │     ├── Nominatim → geocode location to (lat, lng)
  │     └── Google Places API → list of businesses
  ├── analyzer.py  (per business)
  │     ├── httpx → fetch website HTML
  │     ├── BeautifulSoup → extract signals
  │     └── Claude API → classify lead status
  └── database.py
        └── Airtable → save Scan + Business records

Browser clicks "Generate Proposal"
        │ HTTP POST /propose/{id}
        ▼
FastAPI → proposal.py → Claude API → Airtable → JSON response
```

---

## Environment Variables

All read from `.env` via `python-dotenv`. See `.env.example` for the template.

```
GOOGLE_PLACES_API_KEY=   # Google Cloud — Places API (New)
ANTHROPIC_API_KEY=       # console.anthropic.com
MAPBOX_TOKEN=            # mapbox.com — used in Streamlit dashboard + Leaflet tiles
AIRTABLE_API_KEY=        # airtable.com — personal access token
AIRTABLE_BASE_ID=        # Airtable base ID (starts with "app...")
```

Airtable vars are optional — the backend handles Airtable errors gracefully and
continues without persisting if they are missing or fail.

---

## Airtable Data Models

### Scans table
`id`, `created_at`, `location_query`, `lat`, `lng`, `radius_miles`, `total_results`

### Businesses table
`id`, `scan_id`, `name`, `address`, `phone`, `website_url`, `category`, `rating`,
`review_count`, `lead_status` (Hot Lead / Warm Lead / Not a Lead),
`website_signals` (comma-separated), `lat`, `lng`

### Proposals table
`id`, `business_id`, `created_at`, `design_brief`, `sections`, `headline`,
`tagline`, `selling_points`, `seo_keywords`

---

## Key API Details

### Google Places API (New)
- Endpoint: `POST https://places.googleapis.com/v1/places:searchNearby`
- Field mask: `places.displayName,places.formattedAddress,places.websiteUri,places.rating,places.userRatingCount,places.types,places.nationalPhoneNumber,places.reviews,places.location`
- Max results per request: 20
- Radius unit: meters (convert miles → meters: `miles × 1609.34`)
- Category filter uses `includedTypes` array in request body

### Claude API
- **Model: `claude-sonnet-4-6`** — do not switch models without updating this file
- Website scoring: max_tokens=256, plain text prompt, JSON parse with regex fallback
- Proposal generation: max_tokens=1024, plain text prompt, JSON parse with regex fallback
- HTML sent to Claude is stripped of `<script>`, `<style>`, `<head>` tags and truncated to 3000 chars

---

## Claude Usage Guidelines

**Website scoring prompt structure:**
```
URL: {url}
Signals: HTTPS={bool}, viewport={bool}, copyright={year}, CMS={generator}, last-modified={date}
Page text (first 3000 chars): {text}

Classify as Hot Lead / Warm Lead / Not a Lead. Return JSON only:
{"lead_status": "...", "reason": "...", "signals": [...]}
```

**Proposal prompt structure:**
```
Business: {name}, {category}, {address}
Phone: {phone} | Rating: {rating} ({review_count} reviews) | Website: {url}
Reviews:
1. {review_text}
...
Return JSON: {design_brief, sections, headline, tagline, selling_points, seo_keywords}
```

---

## Frontend Architecture (React SPA)

The React frontend has **no build step** — files are loaded directly in the browser via
CDN Babel standalone. All JSX is parsed client-side.

**Dependencies (via CDN in index.html):**
- React 18.3.1 + ReactDOM
- Babel standalone (JSX transform)
- Leaflet 1.9.4 (maps)
- IBM Plex Sans + IBM Plex Mono (Google Fonts)

**Theme system:** Three CSS variable presets in `index.html` — `midnight` (default dark),
`daylight` (light), `carbon` (high-contrast dark). Switched via `tweaks-panel.jsx`.

**State management:** Plain React hooks in `app.jsx` — no Redux or external state lib.

**API calls:** Centralized in `data.jsx` — `fetchBusinesses()`, `runScanAPI()`,
`generateProposalAPI()`. All call `http://localhost:8080` (FastAPI backend).

**Component hierarchy:**
```
app.jsx (App)
 ├── tweaks-panel.jsx (TweaksPanel) — theme/density settings
 ├── Sidebar — nav + scan stats
 ├── Topbar — search + area selector + new-scan trigger
 ├── StatsRow — 5 stat cards with sparklines
 ├── FilterBar — filter chips + sort dropdown
 ├── LeadTable — business rows; click → opens LeadDetail
 ├── LeadDetail (slideover) — full detail + proposal display
 └── ScanModal — location form + animated radar scan state
```

---

## Development Workflow

### Running locally

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Copy and fill in .env
cp .env.example .env

# 3. Start the FastAPI backend (serves React SPA at http://localhost:8080)
uvicorn backend.main:app --reload --port 8080

# 4. (Optional) Start the Streamlit dashboard
streamlit run dashboard/app.py
# → available at http://localhost:8501, calls FastAPI at localhost:8000
```

### Git conventions
- Primary development branch: `master`
- Feature/AI branches: prefix with `claude/`
- Commit messages: imperative mood, describe the "what" and "why"
- Never commit `.env` or `scanner.db`

### Adding a new API endpoint
1. Add the route function in `backend/main.py`
2. If it needs new business logic, add a module in `backend/`
3. Update the endpoint table in this CLAUDE.md

### Adding a new frontend component
1. Create the `.jsx` file in `frontend/`
2. Add a `<script type="text/babel" src="/static/<file>.jsx">` tag in `index.html`
3. Load order matters — utility modules (`ui.jsx`, `data.jsx`) before `app.jsx`

---

## Known Gaps (not yet implemented)

| Gap | Impact |
|---|---|
| No `models.py` / `schemas.py` | No Pydantic request/response validation on API — add to improve type safety and auto-docs |
| No tests directory | No test coverage — `tests/test_scanner.py`, `test_analyzer.py`, `test_proposal.py` are planned |
| No structured logging | Basic try/except only — add Python `logging` module or Sentry |
| No authentication | API is open — any client can call `/scan` or `/propose` |
| No rate limiting | Google Places and Claude calls are unbounded per request |
| Streamlit port mismatch | `dashboard/app.py` calls port 8000 but backend runs on 8080 |
| No scheduled scans | Automation feature is planned but not started |

---

## Quality Gates (applies to all new features)

These are non-negotiable before calling any feature "done":

### Functionality
- All API endpoints return consistent JSON shapes
- Claude prompts return valid JSON (regex fallback handles edge cases)
- Airtable errors are caught and do not crash the scan pipeline
- Website fetch timeouts (10s) and Places API timeouts (15s) are respected

### Frontend (React SPA)
- New components follow existing CSS variable conventions (use `var(--color-*)` tokens)
- No hardcoded colors — all styling via CSS variables so themes work
- Touch targets ≥ 24×24px; no hover-only interactions
- Test at mobile (375px), tablet (768px), and desktop (1280px+) widths
- Respect `prefers-reduced-motion` for any animations

### Code conventions
- All API keys read from `.env` via `python-dotenv` — never hardcoded
- New Python modules in `backend/` follow the same pattern: one public function per module
- HTML sent to Claude is always stripped and truncated before the API call
- `claude-sonnet-4-6` is the only model used — do not introduce other models

### Security
- Never log or store raw API keys
- User-supplied location strings are passed to external APIs only — no shell execution
- Website URLs fetched by `analyzer.py` use httpx with explicit timeouts (no infinite waits)

---

## Out of Scope

- Actually building or hosting client websites (proposals only)
- Payment processing or client management
- Competitor analysis between businesses
- Social media presence scoring
- Multi-user authentication or team accounts
