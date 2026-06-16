# LiquorIQ — MVP Roadmap

## Phase 1 ✅ — Project Scaffold + FastAPI Setup
- Folder structure
- FastAPI app with CORS, health check, root endpoint
- `config.py` with pydantic-settings
- `requirements.txt`, `.env.example`, `.gitignore`, `README.md`

## Phase 2 🔄 — PostgreSQL + SQLAlchemy + Alembic
- `database.py` — async engine + session dependency
- Alembic migrations setup
- Base model class

## Phase 3 ⏳ — Authentication
- `users` + `stores` tables
- POST /auth/register
- POST /auth/login (returns JWT)
- GET /auth/me
- JWT middleware dependency

## Phase 4 ⏳ — Report Upload System
- `uploaded_reports` table
- POST /uploads/report (multipart file)
- File saved to disk, record stored in DB
- Detect source type (POS, Uber, DoorDash, etc.)

## Phase 5 ⏳ — CSV/Excel Parser + Normalization
- Generic parser
- Source-specific parsers (Square, DoorDash, Uber)
- `normalized_sales` table
- Column mapping logic

## Phase 6 ⏳ — Analytics Endpoints
- GET /analytics/summary
- GET /analytics/top-products
- GET /analytics/slow-products
- GET /analytics/category-performance
- GET /analytics/channel-performance

## Phase 7 ⏳ — AI Promotion Strategy Generator
- POST /ai/generate-promotion
- OpenAI call with structured JSON output
- `ai_strategy_reports` table

## Phase 8 ⏳ — React Frontend Dashboard
- Login / Register pages
- Upload report page
- Analytics dashboard
- AI strategy page

## Phase 9 ⏳ — AI Weekly Growth Report
- POST /ai/weekly-growth-report
- Summarize week's data, flag risks + opportunities

## Phase 10 ⏳ — Polish + Deploy
- Full README with screenshots
- Docker Compose
- Environment hardening
- GitHub cleanup