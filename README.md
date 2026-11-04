# Campus Maintenance Request & Work-Order Management System

**Module:** NPRJ740 Software Development Project (Final Year Advanced Diploma in ICT)  
**Institution:** Sol Plaatje University  
**Case Study:** Moroka Hall Residence  

---

## 1. System Overview

A robust, role-based maintenance management web application connecting Residents, Technicians, Supervisors, Wardens, and Administrators. Request lifecycles are governed by strict database transactions, row-level locks, and an append-only audit trail.

---

## 2. Prerequisites

- **Python:** 3.12+ (Python 3.14 on local dev, Python 3.12 in container profiles)
- **Node.js:** 20+ & npm
- **Docker:** Docker Engine with Compose v2
- **PostgreSQL:** 16 (hosted via Docker)

---

## 3. Production Deployment (3-Command Bootstrap per Section 8 / NFR-09)

To run the complete production-grade stack (Nginx reverse proxy, Django WSGI as non-root user, PostgreSQL 16 on internal network, and automated migrations/seed):

```bash
# 1. Clone the repository and enter directory
git clone https://github.com/KamogeloBantsheng/NRPJ740-PROJECT.git && cd NRPJ740-PROJECT

# 2. Create environment configuration
cp .env.example .env

# 3. Build images, run migrations & seed, and start the 4-container stack
docker compose up --build
```

Open **`http://localhost:8080`** in your browser.

### Seeded Demo Accounts (Evaluation Profile)
The evaluation profile seeds these accounts. Their password is the value of `DEMO_PASSWORD` in `.env`:

| Role | Email | Notes |
|---|---|---|
| **Resident** | `resident@example.test` | Room A.203, Block A, Moroka Hall |
| **Supervisor** | `supervisor@example.test` | Triage, assignment, close & reopen |
| **Technician** | `technician@example.test` | Work orders queue & job execution |
| **Technician** | `technician2@example.test` | Second Technician, for reassignment |
| **Warden** | `warden@example.test` | Read-only dashboard; reports faults for residents who cannot reach their accounts |
| **Admin** | `admin@example.test` | User administration & audit search |

Five failed sign-ins in one minute, for one account or from one IP address, block further attempts until the minute passes. Every browser reaching the Compose stack on one machine shares an IP address, so wait a minute after demonstrating the throttle.

---

## 4. Local Development Loop (Fast HMR)

For active feature development:

### Step 1: Start Isolated PostgreSQL Dev Container
```powershell
docker compose -f docker-compose.dev.yml up -d
```

### Step 2: Run Django Backend
```powershell
.\.venv\Scripts\Activate.ps1
python backend/manage.py migrate
python backend/manage.py seed_data --with-demo
python backend/manage.py runserver 127.0.0.1:8000
```

### Step 3: Run Vite Frontend Dev Server
In a separate terminal:
```powershell
cd frontend
npm run dev
```
Open **`http://localhost:5173`** (Vite proxies `/api` directly to Django on port 8000).

---

## 5. Verification & Quality Gates

- **API Health Check:** `GET http://localhost:8080/api/health/`
- **OpenAPI 3.0 Schema:** `GET http://localhost:8080/api/schema/` (regenerate with `python backend/manage.py spectacular --file docs/openapi.yaml`)
- **Interactive API Docs:** `http://localhost:8080/api/schema/swagger-ui/` and `/api/schema/redoc/` (need internet access, because they load from a CDN)
- **Frontend Types Generation:** `npm run generate-api-types --prefix frontend`
- **Backend Linting:** `python -m ruff check backend`
- **Frontend Linting & Build:** `npm run lint --prefix frontend` and `npm run build --prefix frontend`
- **Backend Tests:** `pytest backend/tests/`, with PostgreSQL and the `DB_` variables from `.github/workflows/ci.yml`
- **Client Tests:** `npm test --prefix frontend`
- **Browser Journeys:** `npm run test:e2e --prefix frontend`, with the stack running (set `E2E_CHANNEL=msedge` or `chrome` for a real browser)
- **Load Test:** see `loadtests/locustfile.py`. Use a throwaway database, because `seed_load_data` adds 5,000 requests.

Diagrams are in `docs/diagrams/` as draw.io files with exported PNGs. Test run summaries and screenshots are in `docs/evidence/`.
