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

## 3. Local Development Setup

### Step 1: Clone and Configure Environment
```powershell
cp .env.example .env
```
*(Review and customize secrets in `.env` if required)*

### Step 2: Start the Database Container
```powershell
docker compose -f docker-compose.dev.yml up -d
```

### Step 3: Set up Backend
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt -r backend/requirements-dev.txt
python backend/manage.py migrate
python backend/manage.py runserver 127.0.0.1:8000
```

### Step 4: Set up Frontend
In a separate terminal:
```powershell
npm install --prefix frontend
npm run dev --prefix frontend
```
Open **`http://localhost:5173`** in your browser. All `/api` requests are proxied directly to the Django server.

---

## 4. Verification & Health Check

- **Django Health Endpoint:** `http://127.0.0.1:8000/api/health/`
- **Proxied Vite Health Endpoint:** `http://localhost:5173/api/health/`
- **Lint Backend:** `ruff check backend`
- **Lint & Build Frontend:** `npm run lint --prefix frontend` and `npm run build --prefix frontend`