# SoccerSolver — Player Similarity & Scouting Intelligence

> An improved parallel implementation of the MIT Sports Analytics Conference paper  
> _"Redefining Scouting Intelligence"_ (Paper ID 36) — with real scraped economic data,  
> multi-season historical evolution, and a full-stack web platform.

**Live demo:** https://soccersolver.vercel.app (not hosted now)
**API docs:** https://soccersolver-api.railway.app/docs (not hosted now)

Improvement tried upon: https://github.com/davidsuarezgnz/mit-paper-mvp

---

## What this is

This is a **standalone improved version** of the MVP — not a modification of it.

The core methodology follows the paper exactly:

- Z-score normalisation per position group
- PCA (90% cumulative variance threshold) per positional subset
- K-Means clustering with silhouette scoring (Rousseeuw, 1987)
- Hybrid similarity: `S_ij = 1 − [α·(‖xi−xj‖₂/‖x‖₂) + (1−α)·(1 − cos(xi, xj))]` where α=0.5 (tunable)
- Player Uniqueness Index: `U_i = 1 − (1/k)·Σ s_ij`
- Club Replaceability Index: `R_club = (1/N)·Σ(1 − U_i)`

**Key improvements over the CSV-based MVP:**
Here is MVP url made by @davidsuarezgnz: https://github.com/davidsuarezgnz/mit-paper-scouting-intelligence

| Feature              | MVP                       | SoccerSolver                                            |
| -------------------- | ------------------------- | ------------------------------------------------------- |
| Data source          | Static CSV (FIFA ratings) | Live SoFIFA scraper                                     |
| Economic data        | ❌ None                   | ✅ Salary, market value, release clause                 |
| Historical evolution | ❌ Single season          | ✅ 3 seasons (2022/23 – 2025/26)                        |
| Database             | None (in-memory)          | PostgreSQL                                              |
| Similarity filters   | Basic                     | Age, salary, value, release clause, league, nationality |
| Player profile       | Static                    | Historical charts with economic evolution               |
| Data freshness       | N/A                       | Live indicator + scrape log                             |
| UI                   | Streamlit                 | React + Vite                                            |

> **Accuracy note:** Using SoFIFA public data introduces approximately 5–10% accuracy reduction  
> compared to proprietary data (as noted in the paper, Section 5). This is an expected trade-off  
> for public reproducibility.

---

## Stack

| Layer       | Technology                       | Reason                                                                  |
| ----------- | -------------------------------- | ----------------------------------------------------------------------- |
| Scraper     | Python + Playwright              | SoFIFA is JS-rendered; requests/BeautifulSoup won't work                |
| ML pipeline | scikit-learn, pandas, numpy      | Matches paper methodology exactly                                       |
| Database    | PostgreSQL + TimescaleDB         | Paper's own architecture; TimescaleDB for time-partitioned player stats |
| API         | FastAPI                          | Fast, async, auto-generated OpenAPI docs                                |
| Frontend    | React + Vite + Tailwind          | Modern, fast, component-based                                           |
| Deploy      | Railway (DB + API) + Vercel (FE) | Railway supports TimescaleDB extension natively                         |

---

## Quick Start (local with mock data)

For testing without scraping SoFIFA, use the mock data generator.  
This gives you a fully working system in ~3 minutes.

### Prerequisites

- Docker + Docker Compose
- Python 3.11+
- Node.js 20+

### Easiest way

```bash
bash scripts/setup.sh
```

## If you are more nerdy then follow below steps:

### 1. Clone and configure

```bash
git clone https://github.com/RadientBrain/soccersolver
cd soccersolver
cp .env.example .env
```

### 2. Start the database

```bash
docker-compose up db -d
# Wait for it to be healthy (10–15 seconds)
docker-compose logs db | tail -5
```

### 3. Install Python dependencies

```bash
cd scraper
pip install -r requirements.txt
cd ..
```

### 4. Generate mock data + run ML pipeline

```bash
# Generate 500 players × 3 seasons in the database
cd scraper
python mock_data_generator.py

# Run the ML pipeline (PCA, K-Means, similarity, uniqueness, replaceability)
cd ../pipeline
pip install -r ../api/requirements.txt
python ml_pipeline.py
```

### 5. Start the API

```bash
cd api
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
# API docs at http://localhost:8000/docs
```

### 6. Start the frontend

```bash
cd frontend
npm install
npm run dev
# UI at http://localhost:3000
```

---

## Full Setup (with real SoFIFA data)

### Prerequisites

Install Playwright browsers:

```bash
pip install playwright
playwright install chromium
```

### Scrape current season (2025/26)

```bash
cd scraper
python sofifa_scraper.py "2025/26"
```

The scraper:

- Uses Playwright (full Chromium browser) — required for JS-rendered pages
- Applies 2–5 second random delays between requests
- Rotates User-Agent headers
- Retries with exponential backoff on 429/503
- Logs every scrape run to the `scrape_log` table
- Phase 1: collects player index pages (all player URLs)
- Phase 2: scrapes each player detail page (where salary + release clause live)

### Scrape historical seasons

```bash
python sofifa_scraper.py "2024/25" "2023/24" "2022/23"
```

Historical seasons use SoFIFA's version URL parameter. Version IDs are hardcoded in  
`SOFIFA_VERSIONS` dict in `sofifa_scraper.py`. Update them if SoFIFA changes their versioning.

Known version IDs:

- 2025/26 (current): no version param needed
- 2024/25 (EA FC 25): `?version=240072`
- 2023/24 (EA FC 24): `?version=230054`
- 2022/23 (FIFA 23): `?version=220054`

### Run the ML pipeline

```bash
cd pipeline
python ml_pipeline.py
# Or for specific seasons:
python ml_pipeline.py "2025/26" "2024/25"
```

Pipeline runtime: ~30–60 seconds for 500 players, ~3–5 minutes for 15,000+.

---

## Environment Variables

| Variable            | Default                                                     | Description                   |
| ------------------- | ----------------------------------------------------------- | ----------------------------- |
| `DATABASE_URL`      | `postgresql://soccer:soccer123@localhost:5432/soccersolver` | PostgreSQL connection string  |
| `VITE_API_URL`      | `http://localhost:8000`                                     | API base URL for the frontend |
| `POSTGRES_DB`       | `soccersolver`                                              | DB name (Docker Compose)      |
| `POSTGRES_USER`     | `soccer`                                                    | DB user (Docker Compose)      |
| `POSTGRES_PASSWORD` | `soccer123`                                                 | DB password (Docker Compose)  |

---

## Project Structure

```
soccersolver/
├── db/
│   └── migrations/
│       └── 001_init.sql         # Full schema: hypertable, indexes, cache tables
├── scraper/
│   ├── sofifa_scraper.py        # Playwright scraper — two-phase: index + detail pages
│   ├── mock_data_generator.py   # 500-player mock data for testing
│   └── requirements.txt
├── pipeline/
│   └── ml_pipeline.py           # PCA, K-Means, hybrid similarity, uniqueness, replaceability
├── api/
│   ├── main.py                  # FastAPI — all endpoints
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── api.js               # Axios API client
│   │   ├── components/
│   │   │   ├── Navbar.jsx
│   │   │   └── ui.jsx           # Shared components: StatBar, PlayerCard, etc.
│   │   └── pages/
│   │       ├── HomePage.jsx
│   │       ├── SearchPage.jsx   # Advanced filters, pagination
│   │       ├── PlayerPage.jsx   # Full profile, history charts, similar players
│   │       └── AnalyticsPage.jsx # Uniqueness, replaceability, temporal evolution
│   ├── Dockerfile
│   └── package.json
├── tests/
│   └── test_integration.py      # 8 integration tests covering critical path
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## API Endpoints

| Method | Endpoint                             | Description                         |
| ------ | ------------------------------------ | ----------------------------------- |
| GET    | `/api/seasons`                       | Available seasons                   |
| GET    | `/api/leagues?season=`               | Leagues in a season                 |
| GET    | `/api/data-freshness`                | Scrape log — last update times      |
| GET    | `/api/players/search`                | Search + filter players             |
| GET    | `/api/players/{id}`                  | Full player profile                 |
| GET    | `/api/players/{id}/history`          | Historical evolution across seasons |
| GET    | `/api/players/{id}/similar`          | Top-N similar players with filters  |
| GET    | `/api/analytics/uniqueness`          | Uniqueness index rankings           |
| GET    | `/api/analytics/replaceability`      | Club replaceability rankings        |
| GET    | `/api/analytics/position-uniqueness` | Stats per position (Table 1)        |
| GET    | `/api/analytics/temporal-uniqueness` | Uniqueness over time (Figure 4)     |
| GET    | `/api/clubs/{name}/players`          | All players for a club              |

Full interactive docs at `/docs` (Swagger UI).

---

## Running Tests

```bash
cd tests
pip install pytest
pytest test_integration.py -v
```

Tests cover:

1. DB connection
2. Player data exists
3. ML pipeline results populated (uniqueness index)
4. Similarity cache populated
5. Similarity scores valid range [0,1]
6. Top-N similar players returned for a known player (the key integration test)
7. Uniqueness index range [0,1]
8. Club replaceability computed

All tests require the DB to be running with data loaded and the pipeline to have run.

---

## Deployment

### Railway (API + DB)

```bash
# Install Railway CLI
npm install -g @railway/cli
railway login

# Create project
railway init

# Add TimescaleDB (PostgreSQL plugin, then run extension)
# In Railway dashboard: Add PostgreSQL plugin
# Run migration: railway run psql $DATABASE_URL < db/migrations/001_init.sql

# Deploy API
cd api
railway up
```

### Vercel (Frontend)

```bash
cd frontend
npm run build

# Install Vercel CLI
npm install -g vercel
vercel --prod

# Set environment variable in Vercel dashboard:
# VITE_API_URL = https://your-api.railway.app
```

---

## Similarity Formula Parameters

The α parameter in the hybrid similarity formula is set to 0.5 (equal weight between  
Euclidean and cosine distance), as recommended in the paper. This can be tuned in  
`pipeline/ml_pipeline.py`:

```python
sim_matrix = hybrid_similarity(X_pca, alpha=0.5)  # adjust alpha here
```

- `alpha=1.0` → pure Euclidean distance (sensitive to magnitude)
- `alpha=0.0` → pure cosine distance (sensitive to direction/pattern)
- `alpha=0.5` → hybrid (paper default)

---

## Known Gaps & Honest Notes

- **SoFIFA anti-bot risk:** SoFIFA may block scrapers intermittently. The scraper uses  
  realistic delays and user-agent rotation, but if blocked, re-running after a cooldown  
  usually works. All scrape attempts are logged with status in `scrape_log`.

- **Historical version IDs:** The SoFIFA URL version IDs for older seasons are hardcoded.  
  If SoFIFA changes their URL structure, these will need to be updated manually.

- **~5–10% accuracy gap:** As stated in the paper (Section 5), using SoFIFA public data  
  introduces a ~5–10% accuracy reduction versus proprietary Wyscout/StatsBomb data.

- **Similarity cache granularity:** The cached top-20 similar players per player are  
  pre-computed. Applying context filters (e.g. "only Premier League players under 25")  
  filters from this cache, so very specific filter combinations may return fewer than  
  requested results. With more time: recompute similarity on-the-fly for filtered subsets.

- **With more time:** Live webhook-triggered re-scraping, player comparison view (side-by-side),  
  radar charts per player, transfer value delta alerts, club squad gap analysis.

---

## Paper Reference

Suárez, D. et al. (2024). _Redefining Scouting Intelligence: A Quantitative Framework  
for Player Similarity and Tactical Fit in Modern Football._ MIT Sloan Sports Analytics  
Conference, Paper ID 36.
