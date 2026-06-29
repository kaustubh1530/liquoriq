# LiquorIQ 

> **AI-powered growth intelligence platform for independent liquor stores.**

LiquorIQ connects sales, inventory, customer, and delivery-platform data (POS, Uber Eats, DoorDash, Shopify) and uses AI to generate analytics dashboards, promotion strategies, and weekly growth reports — so store owners can grow revenue without needing a data team.

---

## The Problem

Independent liquor stores already use POS systems, delivery apps, and websites — but their data lives in silos. There is no centralized system that tells them:

- Which products are selling vs. collecting dust
- Which customer segments to target and when
- What promotions to run and what message to send
- How to reduce dead inventory and increase repeat purchases

## The Solution

LiquorIQ is the **AI brain** for liquor stores. Upload your reports, get instant insights, and receive AI-generated growth strategies — ready to send via SMS, email, or Instagram.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11 + FastAPI |
| Database | PostgreSQL + SQLAlchemy (async) |
| Migrations | Alembic |
| Frontend | React + Tailwind CSS |
| AI | OpenAI API (GPT-4o) |
| Auth | JWT (python-jose + passlib) |
| File Parsing | pandas + openpyxl |
| Payments (later) | Stripe |
| Deployment (later) | Docker + Docker Compose |

---

## MVP Features

- [ ] Store owner authentication (JWT)
- [ ] Store profile setup
- [ ] CSV / Excel report upload (POS, Uber Eats, DoorDash, etc.)
- [ ] Source-aware parser + data normalization
- [ ] Analytics dashboard (top products, slow movers, revenue by category/channel)
- [ ] AI promotion strategy generator (SMS, email, social copy)
- [ ] AI weekly growth report

---

## Project Structure

```
liquoriq/
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI app + router registration
│   │   ├── config.py        # Settings (pydantic-settings)
│   │   ├── database.py      # Async SQLAlchemy engine + session
│   │   ├── models/          # SQLAlchemy ORM models
│   │   ├── schemas/         # Pydantic request/response schemas
│   │   ├── routes/          # One file per feature domain
│   │   ├── services/
│   │   │   ├── parsers/     # Source-specific CSV/Excel parsers
│   │   │   ├── analytics_service.py
│   │   │   ├── strategy_service.py
│   │   │   └── openai_service.py
│   │   ├── integrations/    # Future: POS/Shopify/DoorDash API clients
│   │   └── utils/
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   └── src/
│       ├── pages/
│       ├── components/
│       ├── api/
│       └── dashboard/
├── docs/
│   ├── ARCHITECTURE.md
│   ├── DATABASE_SCHEMA.md
│   ├── MVP_ROADMAP.md
│   └── API_DOCUMENTATION.md
└── docker-compose.yml
```

---

## Getting Started (Local Development)

### 1. Clone the repo

```bash
git clone https://github.com/YOUR_USERNAME/liquoriq.git
cd liquoriq
```

### 2. Set up the Python virtual environment

```bash
cd backend
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure environment variables

```bash
cp .env.example .env
# Edit .env with your PostgreSQL URL, secret key, and OpenAI key
```

### 4. Run the development server

```bash
uvicorn app.main:app --reload --port 8000
```

Visit:
- API root: http://localhost:8000
- Swagger docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health

---

## Development Phases

| Phase | Description | Status |
|---|---|---|
| 1 | Project scaffold + FastAPI setup | ✅ Done |
| 2 | PostgreSQL + SQLAlchemy + Alembic | ✅ Done |
| 3 | Authentication (register / login / me) | ✅ Done |
| 4 | Report upload system | ✅ Done |
| 5 | CSV/Excel parser + data normalization | ✅ Done |
| 6 | Analytics endpoints | ✅ Done |
| 7 | AI promotion strategy generator | ✅ Done |
| 8 | React frontend dashboard | ✅ Done |
| 9 | AI weekly growth report | ⏳ Pending |
| 10 | Polish, README, screenshots, deploy | ⏳ Pending |

---

## Target Market

Independent liquor stores in **Washington DC, Virginia, and Maryland**.

---

## License

MIT
