# Small Business Website Scanner — CLAUDE.md

## What This Project Does

This tool scans a geographic area (user-defined location + radius) to find small businesses, evaluates their online presence, and generates AI-powered website proposals for businesses that have no website or an outdated one. The goal is to automate lead discovery for a web design/development service.

---

## Core Features

### 1. Area Scanner
- User inputs a location (city, address, or zip code) and a radius in miles
- Calls the Google Places API (New) to return all businesses within that radius
- Pulls: business name, address, phone number, website URL, business category, rating, review count, and top reviews

### 2. Website Scorer
- For each business returned, checks their website URL (if any)
- Fetches the page and runs a two-step analysis:
  1. **Automated signal extraction** — pulls copyright year, mobile viewport tag, HTTPS status, HTTP Last-Modified header, CMS version hints (e.g. WordPress meta), CSS framework hints (Bootstrap version, etc.), and whether the page responds at all
  2. **Claude review** — receives the stripped HTML (scripts/styles removed) + extracted signals, returns structured JSON with lead classification
- Lead status outcomes:
  - **Hot Lead** — no website URL, or URL returns error/blank/timeout
  - **Warm Lead** — website exists but Claude finds 2+ outdated signals (e.g. copyright 2016, no mobile viewport, old Bootstrap)
  - **Not a Lead** — modern, mobile-friendly, recently updated site
- Claude returns: `{"lead_status": "hot|warm|none", "reason": "...", "signals": [...]}`

### 3. Lead Dashboard (Streamlit)
- Interactive map (Folium/Pydeck) showing color-coded business pins by lead status
- Filterable table: filter by category, lead status, rating, review count
- "Run Scan" form: input location + radius + optional category filter
- Scan history: past scans are saved and can be re-opened
- Each business row is clickable to open the full lead detail view

### 4. Website Proposal Generator (Claude)
- For any Hot or Warm Lead, user clicks "Generate Proposal"
- Claude receives: business name, category, address, rating, review count, and the top 5–10 Google reviews verbatim
- Claude returns a structured proposal including:
  - **Design brief** — tone, color palette suggestion, style direction
  - **Suggested page sections** — e.g., Hero, Services, About, Testimonials, Contact
  - **Sample hero headline and tagline** — written to match the business vibe
  - **Key selling points** — extracted and reframed from their actual reviews
  - **SEO keywords** — 5–8 suggested keywords for their category and location

### 5. Automation (Planned)
- Scheduled re-scans of saved areas (weekly cron)
- Email digest of new leads discovered since last scan (Resend or SendGrid)
- Auto-generate a proposal for every new Hot Lead

---

## Tech Stack

| Layer | Choice | Reason |
|---|---|---|
| Language | Python 3.10+ | User's environment; best Claude + data tooling |
| Backend API | FastAPI | Async, clean routing, easy to test |
| Dashboard | Streamlit | Pure Python, no Node.js required, fast to build |
| Database | SQLite via SQLAlchemy | Zero-config, local-first, easy to migrate later |
| AI | Claude API (`claude-sonnet-4-6`) | Website scoring + proposal generation |
| Business Data | Google Places API (New) | Best coverage, reviews, website URLs, categories |
| Maps | Mapbox | Polished UI, satellite view, custom icons, free up to 50k loads/month |
| Database | Airtable | Spreadsheet-style web UI, shareable, no code needed to browse data |
| Deployment | Streamlit Community Cloud (dashboard) + Railway (API) | Free tiers available |

---

## Project Structure

```
Small-Business-Website-Scanner/
├── CLAUDE.md                  # This file
├── README.md
├── .env                       # Not committed — contains API keys
├── .env.example               # Template for .env
├── .gitignore
├── requirements.txt
│
├── backend/
│   ├── main.py                # FastAPI app — mounts all routers
│   ├── scanner.py             # Google Places API integration
│   ├── analyzer.py            # Website fetching + Claude website scoring
│   ├── proposal.py            # Claude proposal generation
│   ├── models.py              # SQLAlchemy models (Scan, Business, Proposal)
│   ├── database.py            # DB connection + session setup
│   └── schemas.py             # Pydantic request/response models
│
├── dashboard/
│   └── app.py                 # Streamlit dashboard (map, table, proposal viewer)
│
└── tests/
    ├── test_scanner.py
    ├── test_analyzer.py
    └── test_proposal.py
```

---

## Environment Variables

```
GOOGLE_PLACES_API_KEY=   # Google Cloud — Places API (New)
ANTHROPIC_API_KEY=       # console.anthropic.com
MAPBOX_TOKEN=            # mapbox.com — free account
AIRTABLE_API_KEY=        # airtable.com — personal access token
AIRTABLE_BASE_ID=        # ID of the Airtable base (starts with "app...")
```

---

## Key API Details

### Google Places API (New)
- Endpoint used: `POST https://places.googleapis.com/v1/places:searchNearby`
- Required fields mask: `places.displayName,places.formattedAddress,places.websiteUri,places.rating,places.userRatingCount,places.types,places.nationalPhoneNumber,places.reviews,places.location`
- Max results per request: 20 (paginate for more)
- Radius is in meters (convert from miles: miles × 1609.34)

### Claude API
- Model: `claude-sonnet-4-6`
- Used for two tasks:
  1. **Website scoring** — given HTML snippet + metadata, classify lead quality
  2. **Proposal generation** — given business info + reviews, return structured proposal
- Both use structured JSON output via tool use

---

## Data Models (Airtable Tables)

### Scans table
- `id`, `created_at`, `location_query`, `lat`, `lng`, `radius_miles`, `total_results`

### Businesses table
- `id`, `scan_id`, `name`, `address`, `phone`, `website_url`, `category`, `rating`, `review_count`, `lead_status` (Hot/Warm/Not a Lead), `website_signals` (comma-separated), `lat`, `lng`

### Proposals table
- `id`, `business_id`, `created_at`, `design_brief`, `sections`, `headline`, `tagline`, `selling_points`, `seo_keywords`

---

## Claude Usage Guidelines

- **Website scoring prompt:** Keep HTML to under 2000 tokens — strip scripts, styles, and comments before sending. Ask Claude to return JSON: `{"lead_status": "hot|warm|none", "reason": "...", "signals": [...]}`
- **Proposal prompt:** Include the top 5–10 reviews verbatim. Ask Claude to return structured JSON matching the Proposal model fields.
- **Always use `claude-sonnet-4-6`** — do not switch models without updating this file.

---

## Development Notes

- Run the FastAPI backend with: `uvicorn backend.main:app --reload`
- Run the Streamlit dashboard with: `streamlit run dashboard/app.py`
- The dashboard calls the FastAPI backend via `http://localhost:8000`
- SQLite database file is `scanner.db` in the project root — not committed
- All new code goes to GitHub via commits to `master` branch
- Keep all API keys out of code — read from `.env` using `python-dotenv`

---

## Out of Scope (for now)
- Actually building or hosting client websites (this tool generates proposals only)
- Payment processing or client management
- Competitor analysis
- Social media presence scoring
