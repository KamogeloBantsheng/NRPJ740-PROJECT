# Technical Specification: NPRJ740 Campus Maintenance Request & Work-Order Management System

**Author:** Kamogelo Bantsheng  
**Student Number:** 202311455  
**Course:** NPRJ740 — Advanced Diploma in Information Technology Project  
**Institution:** Sol Plaatje University (SPU), Kimberley, South Africa  
**Deployment Scope:** Moroka Hall of Residence  

---

## 1. Engineering Principles & Development Methodology

This specification governs the software architecture, technical implementation, and verification standards for the NPRJ740 Capstone Software Project. The implementation is developed under rigorous engineering practices to ensure complete architectural alignment with the project report and defense requirements:

1. **Phase-Driven Iterative Delivery:** Development proceeds in discrete, verified vertical slices. Each slice delivers full end-to-end functionality (database, service layer, REST endpoints, and responsive user interface) before subsequent slices are implemented.
2. **Architecture and Planning First:** Prior to code implementation, each slice defines its exact functional requirements (FR), non-functional requirements (NFR), business rules (BR), touched components, risk factors, and verification criteria.
3. **Rigorous Layering and Traceability:** Clear separation of concerns is maintained across all layers:
   - **Presentation Layer:** React + TypeScript (Vite), mobile-first responsive layout (360 px minimum width).
   - **API Layer:** Django REST Framework views and serializers handling request validation and status mapping.
   - **Domain / Service Layer:** Pure business logic encapsulation (`TransitionService`, `PermissionPolicy`, `AuditService`, `ReportingService`). Status transitions and state changes are strictly prohibited in views and serializers.
   - **Persistence Layer:** PostgreSQL 16 relational database with native constraints, triggers, and dual-role access control (`nrpj_owner` and `nrpj_app`).
4. **Empirical Verification:** Functionality is verified through live automated testing and reproducible manual checks. No feature is marked complete without direct test execution output and database assertion.
5. **Strict Scope Discipline:** Implementation focuses strictly on the included core requirements (FR-01 through FR-18). Out-of-scope features identified in Report Section 3.3 (SMS/push notifications, binary file attachments, resident self-cancellation, master-data administrative screens, safety flags, SSO/OAuth, native mobile app, and automated predictive ML models) are intentionally excluded to maintain system reliability, security, and project deadlines.
6. **Justified Dependencies:** Minimal external dependencies are utilized. Heavy external abstractions (third-party UI component kits, Axios, Redux/Zustand, Tailwind CSS, Celery, Redis) are excluded in favor of standard web APIs (`fetch`), native CSS design tokens, and lightweight specialized utilities (`@tanstack/react-query`, `react-hook-form`, `zod`).
7. **Cross-Platform Compatibility:** Full support for Windows 11 host development (PowerShell) and Linux containerized production deployments (Docker Compose with Alpine/Slim images). Line endings are standardized via `.gitattributes` (`* text=auto eol=lf`).
8. **Automated Verification:** Comprehensive test suite adhering to the assessment rubric (functional unit tests, API integration tests, concurrency tests, and database security invariant checks).
9. **Version Control Integrity:** Clean Git commit history utilizing Conventional Commits tagged with specific requirement IDs (e.g., `feat(workflow): assign work order with row lock (FR-10, BR-01)`). Secrets, environments, and build artifacts are strictly excluded from version control.
10. **Living Documentation:** Continuous synchronization of project documentation:
    - `docs/TRACEABILITY.md`: Bidirectional mapping from requirements to screens, services, tables, rules, and automated test cases.
    - `docs/DEVIATIONS.md`: Formal record of architectural adaptations and refinements made relative to early design drafts.

---

## 2. Source of Truth

- **Controlling Document:** `docs/source/NPRJ740_Final_Project_Report_v4.pdf` (and `v5`) serves as the authoritative baseline specification.
- **Assessment Criteria:** `docs/source/FINAL_PROJECT_RUBRIC.pdf` establishes the evaluation standard: Functional Implementation (12), Code Quality & Clean Code (9), Software Architecture (7), Data & State Management (5), Security, Validation & Failure Handling (5), Automated Testing (7), and Repository Integrity (5).
- **Domain Consistency:** All problem statements, functional requirements, relational schemas, and application services use uniform nomenclature across the entire codebase.

---

## 3. System Specification Digest

### 3.1 System Overview
A multi-role maintenance workflow web application for Moroka Hall of Residence at Sol Plaatje University. Residents lodge fault reports; Supervisors triage, prioritize, and assign them; Technicians execute the physical maintenance; and Supervisors inspect and close or reopen requests. Wardens possess read-only observational oversight for their residence, while Administrators manage user credentials and system auditing.

### 3.2 Canonical Terminology
- **Roles:** `RESIDENT`, `TECHNICIAN`, `SUPERVISOR`, `WARDEN`, `ADMIN`.
- **Maintenance Request:** The core fault report entity representing the user's maintenance issue. It carries the **sole** lifecycle status of the workflow.
- **Work Order:** Represents an assignment dispatch of an approved request to a specific Technician. A work order has **no status column** of its own; its state is derived strictly from `ended_at` and `end_reason` (`REASSIGNED` or `COMPLETED`).

### 3.3 Request State Machine

All request state transitions are executed exclusively through `TransitionService.execute` under PostgreSQL row-level locks (`SELECT ... FOR UPDATE`). Any invalid transition returns HTTP 409 Conflict.

| # | Action | Transition | Authorized Actor | Validation & Business Guard |
|---|---|---|---|---|
| **T1** | `SUBMIT` | *Initial* &rarr; `SUBMITTED` | Resident | Active location in resident's residence; active category; description 10–2,000 chars. |
| **T2** | `REQUEST_CLARIFICATION` | `SUBMITTED` &rarr; `NEEDS_CLARIFICATION` | Supervisor | Question text &ge; 10 chars. |
| **T3** | `PROVIDE_CLARIFICATION` | `NEEDS_CLARIFICATION` &rarr; `SUBMITTED` | Request Owner | Resident answer &ge; 10 chars. |
| **T4** | `APPROVE` | `SUBMITTED` &rarr; `APPROVED` | Supervisor | Priority classification assigned (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`). |
| **T5** | `REJECT` | `SUBMITTED` or `APPROVED` &rarr; `REJECTED` | Supervisor | Rejection rationale &ge; 10 chars. Terminal state. |
| **T6** | `ASSIGN` | `APPROVED` &rarr; `ASSIGNED` | Supervisor | Active technician selected; instantiates active `WorkOrder`. |
| **T7** | `REASSIGN` | `ASSIGNED`, `IN_PROGRESS`, or `REOPENED` &rarr; `ASSIGNED` | Supervisor | Different active technician selected; reason &ge; 10 chars; terminates existing work order with `REASSIGNED`, creates new work order. |
| **T8** | `START_WORK` | `ASSIGNED` or `REOPENED` &rarr; `IN_PROGRESS` | Assigned Technician | Actor must be assigned technician; work order must be currently active. |
| **T9** | `COMPLETE_WORK` | `IN_PROGRESS` &rarr; `WORK_COMPLETED` | Assigned Technician | Detailed completion notes &ge; 20 trimmed characters. |
| **T10** | `VERIFY_CLOSE` | `WORK_COMPLETED` &rarr; `VERIFIED_CLOSED` | Supervisor | Supervisor verification notes; terminates active work order (`COMPLETED`), records `closed_at`. Terminal state. |
| **T11** | `REOPEN` | `WORK_COMPLETED` &rarr; `REOPENED` | Supervisor | Unsatisfactory work feedback &ge; 10 chars. Re-enters technician queue. |

*Notes:*
- `REJECTED` and `VERIFIED_CLOSED` are immutable terminal states (BR-06).
- Every transition invocation accepts an `expected_status` token to guarantee optimistic concurrency control; a mismatch against the locked row aborts with HTTP 409 and returns the live status.

### 3.4 Core Business Rules (BR)
- **BR-01:** Exactly one active work order per request (`partial unique index` where `ended_at IS NULL`).
- **BR-02:** Mandatory audit justification notes on all state changes (character length constraints enforced at service layer).
- **BR-03:** Only Supervisors may assign or reassign work orders.
- **BR-04:** Data minimization: Wardens and Technicians never receive resident PII (full name, student number, email). Wardens are scoped strictly to their assigned residence.
- **BR-05:** Residents can only view requests lodged by themselves.
- **BR-06:** Terminal states (`REJECTED`, `VERIFIED_CLOSED`) cannot transition to any other status.
- **BR-07:** Only active accounts may authenticate or be assigned tasks. Deactivating an account terminates active sessions. Technicians with active work orders cannot be deactivated until orders are reassigned. The last remaining Administrator account cannot be deactivated or deleted.
- **BR-08:** Priority can only be assigned during Supervisor approval (`T4`).
- **BR-09:** Residents may only submit requests for their assigned room or common areas within their designated residence.
- **BR-10:** Only Supervisors can verify, close, or reopen completed maintenance jobs.

### 3.5 Relational Database Schema & Data Integrity (PostgreSQL 16)
- **Tables:** `residences`, `users`, `locations`, `fault_categories`, `maintenance_requests`, `work_orders`, `audit_logs`, `django_session`.
- **Identity & Time:** Bigint identity primary keys, UTC ISO timestamps (`timestamptz`), strict foreign keys (`ON DELETE RESTRICT`), no hard row deletions.
- **Native Database Constraints (NFR-08):**
  - `users`: Case-insensitive uniqueness on `lower(email)`; check constraint restricting `role`; residence foreign key required for `RESIDENT` and `WARDEN`; student number unique when present and required for `RESIDENT`.
  - `locations`: Composite uniqueness constraint on `(residence_id, block, floor, label)`.
  - `maintenance_requests`: Check constraint ensuring trimmed description between 10 and 2,000 characters; check constraint on `status`; `priority` mandatory once approved; `closed_at` populated exactly when status is `REJECTED` or `VERIFIED_CLOSED`; unique `(resident_id, client_token)` for idempotent submissions; human-readable tracking ID `MR-000123` generated deterministically from primary key.
  - `work_orders`: Partial unique index on `(request_id)` where `ended_at IS NULL`; check constraint enforcing `end_reason IS NOT NULL` if and only if `ended_at IS NOT NULL`.
  - `audit_logs`: Append-only architecture. Native database triggers abort `UPDATE`, `DELETE`, and `TRUNCATE` operations.
  - **Database Security Roles:** Dual-role architecture separating schema migration privileges (`nrpj_owner`) from application runtime privileges (`nrpj_app` restricted to `SELECT`, `INSERT`, and limited `UPDATE`).

### 3.6 Application Security Architecture
- **Authentication:** Server-side sessions with `HttpOnly`, `SameSite=Lax`, and `Secure` cookies (session rotated upon authentication).
- **Password Security:** Argon2id cryptographic password hashing, strict password policy (&ge; 10 characters, common password dictionary check), temporary credentials displayed once upon generation and marked for mandatory first-login password reset.
- **Brute-Force Protection:** Progressive IP and account rate-limiting based on recent `LOGIN_FAILED` audit events in the database (5 failed attempts per minute trigger HTTP 429).
- **Two-Factor Authentication (TOTP):** Cryptographic RFC 6238 time-based one-time password verification with emergency recovery backup codes.
- **HTTP Protection:** Reverse proxy enforced security headers:
  - `Content-Security-Policy (CSP)`
  - `Strict-Transport-Security (HSTS)`
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `Referrer-Policy: strict-origin-when-cross-origin`
- **Data Sanitization:** Strict CSV upload sanitization preventing spreadsheet formula injection (`=`, `+`, `-`, `@`, `\t`, `\r`). Request bodies restricted to 1 MB; CSV imports capped at 2 MB / 2,000 records.

---

## 4. Technology Stack & Architectural Decisions

### 4.1 Technology Stack
- **Backend Framework:** Python 3.12 LTS, Django 5.2 LTS, Django REST Framework.
- **Database Engine:** PostgreSQL 16 with native triggers and dual-role permission separation.
- **Frontend Architecture:** React 18, TypeScript, Vite, React Router, `@tanstack/react-query`, `react-hook-form`, `zod`.
- **Infrastructure & Packaging:** Docker Compose, Nginx reverse proxy, multi-stage production container builds.
- **Quality & Verification:** Pytest, Pytest-Django, Ruff linter/formatter, ESLint, TypeScript compiler checks.

### 4.2 Key Architectural Decisions
1. **Developer Loop:** Standalone PostgreSQL container with native backend and Vite frontend development servers. Vite reverse proxies `/api` requests to eliminate cross-origin complexity while preserving cookie security.
2. **Stateless Service Layer:** Business logic resides exclusively in service classes (`TransitionService`, `ReportingService`, `UserAdminService`). Views are thin request-response controllers.
3. **Database-Driven Concurrency:** High-concurrency operations use pessimistic database row locks (`SELECT ... FOR UPDATE`) with deterministic acquisition ordering (request lock first, technician lock second) to prevent deadlocks.
4. **Append-Only Audit Trail:** Every business action generates an immutable audit record containing actor ID, IP address, user agent, action type, timestamp, and JSON details snapshot.
5. **Idempotent Seeding:** Master room layout and default demo credentials seed deterministically through idempotent management commands (`seed_data` and `seed_demo_users`).

---

## 5. Development Phases & Milestones

- **Phase 0: Foundations:** Monolith structure, environment configuration, database connection, health checks, and CI pipeline setup.
- **Phase 1: Data & Audit Architecture:** Relational models, constraints, seed data, and append-only audit trigger verification.
- **Slice 1: Identity & Access Management (FR-01, FR-02; SCR-01, SCR-02):** Session authentication, password reset, rate-limiting, and role-based permissions.
- **Slice 2: Request Submission & Tracking (FR-05, FR-06; SCR-03, 04, 05):** Fault reporting, client token idempotency, and audit event timeline visualization.
- **Slice 3: Triage Workflow (FR-07, 08, 09; SCR-06):** Clarification loops, priority assignment, request rejection, and triage queues.
- **Slice 4: Work Order Dispatch (FR-10, FR-11; SCR-07):** Technician allocation, reassignments, and partial unique index constraints.
- **Slice 5: Technician Execution (FR-13, 14, 15; SCR-09):** Technician queues, task execution, and work completion verification notes.
- **Slice 6: Verification & Closure (FR-12; SCR-08):** Quality inspection, job closure, and reopening loops.
- **Slice 7: Administration & CSV Ingestion (FR-03, FR-04; SCR-11, SCR-12):** Account lifecycle controls and validated student batch import.
- **Slice 8: Analytics & Audit Search (FR-16, FR-18; SCR-10, SCR-13):** Operational metrics, KPI dashboards, and administrative audit search.
- **Phase 9: Production Packaging:** Multi-container Docker Compose deployment, Nginx proxy configuration, and OpenAPI schema generation.
- **Phase 10: Verification Suite:** Complete test suite execution (TC-01 to TC-42, NT-01 to NT-09, ST-01 to ST-06) covering functional, security, and performance criteria.
- **Phase 11: Release & Documentation:** Final repository packaging, deployment runbooks, traceability matrix, and technical defense preparation.

---

## 6. Technical Defense & Demonstration Runbook

During academic evaluation, the system can be demonstrated live through three primary modes:

1. **Automated Verification:**
   ```bash
   pytest backend/tests/ -v
   ruff check backend/
   npm --prefix frontend run lint
   npm --prefix frontend run build
   ```
2. **Containerized Production Run:**
   ```bash
   docker compose up --build -d
   ```
   Accessible at `http://localhost:8080` with Nginx reverse proxy, security headers, and static asset distribution.
3. **Local Developer Loop:**
   - PostgreSQL running via `docker compose -f docker-compose.dev.yml up -d`
   - Backend running via `python backend/manage.py runserver`
   - Frontend running via `npm --prefix frontend run dev` at `http://localhost:5173`
