# MASTER PROMPT: NPRJ740 Campus Maintenance Request & Work-Order Management System

Save this file in the repo as `docs/AGENT_BRIEF.md`, then paste the "Kickoff message" at the bottom into Antigravity. Section 0 can also be added as a workspace rule so it applies to every session.

---

## 0. How we work (standing rules, apply to every message)

You are my pair-programming partner on a final-year Advanced Diploma software project. I am coding alongside you. I will be assessed on a live demo, lecturer-selected functionality and a technical defence, so I must understand every line that goes into this repo.

1. **One phase at a time, one step at a time.** Finish a step, summarise it, then STOP and wait for me to say "continue". Never chain phases together.
2. **Plan before code.** At the start of every phase or slice, post a short plan: goal, requirement IDs covered (FR/NFR/BR/AC), files you will create or change, what "done" looks like, risks. Wait for my approval before writing code.
3. **Explain as you go.** After each step give 3 to 5 lines: what changed, why, and which requirement ID it serves. No essays.
4. **Do not be delusional.**
   - Never say something works unless you ran it and showed me the output. If you did not run it, say "not verified".
   - Never invent requirement IDs, endpoints, columns, business rules, library APIs or package versions. Check the installed package source or official docs, or tell me you are unsure.
   - If the report is silent, ambiguous or contradicts itself, STOP and ask me. List any assumption you make in a line starting with "ASSUMPTION:".
   - If something fails, show the real error and diagnose it. Do not paper over it or silently work around it.
5. **Scope discipline.** Build only the Included requirements (FR-01 to FR-18). Do NOT build FR-19 to FR-23 or anything in report Section 3.3 (notifications, attachments, cancel, master-data screens, safety flag, SSO, mobile app, AI/ML). No extras, no "while I am here" refactors.
6. **Dependencies: justify before installing.** Only the packages in Section 3 are pre-approved, and each is installed in the phase where it is first needed, with a one-line reason. Anything else: stop and ask with (a) what it is, (b) why it is needed, (c) the no-dependency alternative, (d) cost in size or maintenance. Do not add UI kits, axios, Redux/Zustand, Tailwind, Celery, Redis, Django admin customisation or anything similar.
7. **Terminal.** I am on Windows 11 and use PowerShell. Use PowerShell-compatible commands only (no bash-only syntax). You may run commands, but say the command and its purpose first. Never run destructive commands (`docker compose down -v`, `git reset --hard`, deleting files or folders, dropping databases) without my explicit OK. Stay inside the project folder.
8. **Tests come later, by my choice.** Do not write automated tests until the Test Phase. Do keep code testable: business rules in services, not in views. At the end of each slice, give me the exact manual check (browser steps or `Invoke-RestMethod`) and run whatever you can yourself.
9. **Git.** I created the repo. At the end of each step or slice propose a Conventional Commits message that names requirement IDs, for example `feat(workflow): assign work order with row lock (FR-10, BR-01)`. I run the commit myself unless I say otherwise. Keep commits small. Never commit `.env`, secrets, venvs or `node_modules`.
10. **Living documents.** After every slice update:
    - `docs/TRACEABILITY.md`: FR to use case to screen to class/service to table to rule to code path to test (test column "TBD" until the Test Phase).
    - `docs/DEVIATIONS.md`: every place the code differs from the report, with the reason, so I can update the report to match.
11. **Code style.** Simple, readable, small functions, clear names, comments only where the "why" is not obvious. Layers: API (views/serialisers) then services then ORM. No business rules in views or serialisers.

---

## 1. Source of truth

- `docs/source/NPRJ740_Final_Project_Report_v4.pdf` is the controlling document. If it disagrees with any earlier phase document, the report wins. (I will copy the report, the rubric and the feedback slides into `docs/source/` before we start.)
- `docs/source/FINAL_PROJECT_RUBRIC.pdf` shows how the implementation is marked: functional implementation 12, code quality 9, architecture 7, data/state 5, security/validation/failure handling 5, testing 7, repository integrity 5. The code must match the report, so organisation and consistency matter as much as features.
- The lecturer's feedback is that the problem statement, requirements, models, database and code must all describe the same system. Use the same names everywhere, and flag every deviation in `docs/DEVIATIONS.md`.
- The digest in Section 2 is a convenience copy. If it disagrees with the report, the report wins and you tell me.

---

## 2. Spec digest

**System.** Web app for Moroka Hall Residence at Sol Plaatje University. Residents report faults; a Supervisor triages and assigns; a Technician does the work; the Supervisor verifies and closes. Wardens watch read-only. Admins manage accounts.

**Vocabulary (use exactly).** Roles: RESIDENT, TECHNICIAN, SUPERVISOR, WARDEN, ADMIN. A *request* is the fault report and carries the ONLY lifecycle status. A *work order* is the assignment of a request to a Technician and has NO status of its own (only `ended_at` and `end_reason`).

**Request lifecycle (the transition service is driven by this table; anything else returns 409):**

| # | Action | From to To | Actor | Guard |
|---|---|---|---|---|
| T1 | SUBMIT | none to SUBMITTED | Resident | own-residence active location, active category, description 10 to 2,000 chars |
| T2 | REQUEST_CLARIFICATION | SUBMITTED to NEEDS_CLARIFICATION | Supervisor | question >= 10 |
| T3 | PROVIDE_CLARIFICATION | NEEDS_CLARIFICATION to SUBMITTED | Owner | answer >= 10 |
| T4 | APPROVE | SUBMITTED to APPROVED | Supervisor | priority LOW/MEDIUM/HIGH/CRITICAL |
| T5 | REJECT | SUBMITTED or APPROVED to REJECTED | Supervisor | reason >= 10 |
| T6 | ASSIGN | APPROVED to ASSIGNED | Supervisor | active Technician; creates work order |
| T7 | REASSIGN | ASSIGNED, IN_PROGRESS or REOPENED to ASSIGNED | Supervisor | different active Technician; reason >= 10; ends old work order (REASSIGNED), creates new |
| T8 | START_WORK | ASSIGNED or REOPENED to IN_PROGRESS | Assigned Technician | none |
| T9 | COMPLETE_WORK | IN_PROGRESS to WORK_COMPLETED | Assigned Technician | notes >= 20 after trimming |
| T10 | VERIFY_CLOSE | WORK_COMPLETED to VERIFIED_CLOSED | Supervisor | ends work order (COMPLETED), sets closed_at |
| T11 | REOPEN | WORK_COMPLETED to REOPENED | Supervisor | feedback >= 10 |

REJECTED and VERIFIED_CLOSED are final. Every transition call carries `expected_status`; the server compares it with the locked row and returns 409 with the current status if different. Text is trimmed before length checks.

**Business rules.** BR-01 one active work order per request. BR-02 mandatory notes (lengths above). BR-03 only a Supervisor reassigns. BR-04 Wardens and Technicians never receive resident identity; Warden sees only own residence. BR-05 Resident sees only own requests. BR-06 terminal states final. BR-07 only active users sign in or get work; deactivation ends sessions; cannot deactivate a Technician with active work orders; cannot remove the last active Admin. BR-08 priority set only at approval. BR-09 Resident reports only against active locations in own residence. BR-10 only a Supervisor verifies, closes or reopens.

**Error codes.** 401 not authenticated, 403 role not permitted, 404 object absent OR outside caller's scope, 409 state conflict, 422 validation, 429 throttled.

**Data (PostgreSQL 16).** Tables: `residences`, `users`, `locations`, `fault_categories`, `maintenance_requests`, `work_orders`, `audit_logs`, plus Django's `django_session`. Bigint identity keys, UTC timestamps, no hard deletes, every FK `ON DELETE RESTRICT`. Key database-level rules (NFR-08, not only in app code):
- `users`: unique `lower(email)`; CHECK role in Role; residence set exactly when role is RESIDENT or WARDEN; student_number unique when not null, required for RESIDENT.
- `locations`: unique (residence_id, block, floor, label).
- `maintenance_requests`: CHECK trimmed description length 10 to 2,000; CHECK status in RequestStatus; priority NOT NULL from APPROVED onwards; closed_at set exactly when REJECTED or VERIFIED_CLOSED; unique (resident_id, client_token) for idempotent submit; tracking ID `MR-000123` built from the PK.
- `work_orders`: partial unique index on (request_id) WHERE ended_at IS NULL; CHECK end_reason null exactly when ended_at null.
- `audit_logs`: append-only. Trigger rejects UPDATE, DELETE and TRUNCATE; the runtime role has INSERT and SELECT only. Call it "append-only", never "immutable".
- Two DB roles: **owner** (runs migrations) and **app** (runtime, restricted).

**Architecture.** Modular Django monolith. Django apps: `accounts`, `locations`, `workflow`, `audit`, `reporting`. Services: TransitionService, PermissionPolicy, AuditService, AuthService, UserAdminService, UserImportService, ReportingService. **Request status is changed only inside `TransitionService.execute(request_id, action, actor, expected_status, payload)`**, which opens one transaction, locks the request row with `SELECT ... FOR UPDATE`, checks `expected_status`, applies the rule from the TransitionRule table, changes the data, writes the audit event, commits. Lock order: request first, Technician second. Models never change their own status.

**Security.** Server-side sessions in HttpOnly SameSite=Lax cookies (NOT JWT), 8-hour expiry, session rotated at sign-in, CSRF token on writes, Argon2id hashing, one generic sign-in error, throttle 5 failures per minute per account and per IP (then 429), role and active flag read from the DB on every request, password policy (>= 10 chars, not a common password), temporary passwords hashed and shown once, forced change at first sign-in. Security headers (CSP, X-Content-Type-Options, Referrer-Policy, framing protection) via nginx. Request body limit 1 MB, CSV 2 MB / 2,000 rows, pagination capped at 50.

**Screens (SCR-01 to SCR-13).** Sign in; Change password; My requests; Report a fault; Request detail/timeline; Triage queue; Dispatch; Verification review; My work; Dashboard; Users; CSV import; Audit log; plus system pages (403, 404, session expired, network error). Every screen needs loading, empty, error, conflict and access-denied states. Mobile-first at 360 px.

---

## 3. Stack (fixed by the report; do not substitute)

Python 3.12, Django 5.2 LTS, PostgreSQL 16, React + TypeScript + Vite, Docker Compose, nginx.

**Pre-approved packages (install only when first needed, with a one-line reason):**
- Backend: `django`, `djangorestframework`, `drf-spectacular` (OpenAPI schema for generated client types), `argon2-cffi` (Argon2id), `psycopg` v3 (PostgreSQL driver), `gunicorn` (production server in the container), `ruff` (lint). Test Phase only: `pytest`, `pytest-django`, `locust`.
- Frontend: `react`, `react-dom`, `typescript`, `vite`, `react-router`, `@tanstack/react-query`, `react-hook-form`, `zod`, `@hookform/resolvers` (needed to connect the two), `openapi-typescript` (types from the OpenAPI schema), `eslint`. Test Phase only: `vitest`, `@playwright/test`.
- Styling: plain CSS with a small tokens file. No component library. Use the browser `fetch`, no axios.
- Ask first for anything else, including a backend type checker (the report says "type checks pass"; propose the lightest option at CI time and justify it).
- Docker Desktop (WSL2) is needed for PostgreSQL and the final packaging. I do not mind installing it, but tell me what it is and why before you suggest the install.

---

## 4. Gaps in the report that you should fill this way (tell me if you disagree)

1. **Windows.** Add `.gitattributes` with `* text=auto eol=lf` so line endings do not break Docker scripts. No bash-only scripts.
2. **Dev loop.** In development, run only PostgreSQL in Docker; run Django and the Vite dev server natively, and have Vite proxy `/api` to Django so the browser sees one origin (needed for cookies and CSRF). Build the full Compose stack (nginx + api + db + one-shot migrate) in the Hardening phase.
3. **Two DB roles from day one.** An init SQL script in `deploy/db/` creates the owner and app roles and the grants. Settings read `DB_USER` and `DB_PASSWORD` from the environment; migrations run with the owner credentials, the server runs with the app credentials.
4. **Login throttle without extra infrastructure.** The report allows no cache or queue. Count `LOGIN_FAILED` audit events in the last 60 seconds per account email and per IP (both are stored in `details`) instead of adding Redis.
5. **Custom user model** with email as the login field, created in the very first migration (Django cannot change it later). Use only the `users` table columns in the report.
6. **Do not enable or customise Django admin.** It would bypass TransitionService and the audit rules.
7. **Consistent error body** for every non-2xx: `{ "code": "...", "message": "...", "fields": {...}, "current_status": "..." }` (the last two only when relevant). Mapping to 401/403/404/409/422/429 happens in one place.
8. **Seed data.** I have an Excel file of the real rooms (Blocks A, B, C; floors 1 to 3; rooms 101 to 110 per floor, to be confirmed against the file). I will export it to CSV into `data/seed/`. Write an idempotent seed migration or command that reads it. Do not invent rooms. Propose the fault-category list (for example Plumbing, Electrical, Carpentry, Locks and doors, Other) and wait for my approval. If `SEED_DEMO_DATA=true`, also seed one demo account per role (password from `DEMO_PASSWORD` in `.env`) and a few sample requests.
9. **Idempotent submit.** The React form generates a UUID `client_token` when the form mounts and reuses it on retry.
10. **Time.** Store UTC; display in Africa/Johannesburg.
11. **Client-side guards** (route protection by role) are for usability only. The server decides everything.

---

## 5. Phases (vertical slices: one feature fully working end to end before the next)

Each phase ends with: manual check I can perform, proposed commit message, updated TRACEABILITY.md and DEVIATIONS.md, then STOP.

**Phase 0: Foundations.** Repo layout from report Section 6.1; `.gitignore`, `.gitattributes`, `.env.example`; PostgreSQL in Docker with owner/app roles; Django skeleton with settings reading env vars; `/api/health/`; Vite React TS skeleton proxying `/api`; minimal GitHub Actions CI (ruff, ESLint, TypeScript build; tests are added in the Test Phase). No features yet.

**Phase 1: Data and audit foundation.** Custom User model; Residence, Location, FaultCategory; their CHECK/unique constraints; seed from my CSV; `audit_logs` table with trigger and grants; AuditService (`record`). Prove with SQL that UPDATE/DELETE/TRUNCATE on `audit_logs` fail for the app role.

**Slice 1: Authentication (FR-01, FR-02; SCR-01, SCR-02).** Sessions, CSRF, Argon2id, generic error, DB-based throttle, forced password change, `/api/me`, role home routing, PermissionPolicy skeleton, shared error mapping, 401/403/404 pages.

**Slice 2: Report and track (FR-05, FR-06; SCR-03, 04, 05).** MaintenanceRequest model and constraints; TransitionRule table and TransitionService with only T1; idempotent submit; role-scoped querysets; request timeline from audit events.

**Slice 3: Triage (FR-07, 08, 09; SCR-06).** T2 to T5, `expected_status`, 409 handling in the UI, triage queue (oldest first, filters, page size 50).

**Slice 4: Assign and reassign (FR-10, FR-11; SCR-07).** WorkOrder model, partial unique index, T6 and T7, Technician row lock, open-work counts in the picker.

**Slice 5: Technician work (FR-13, 14, 15; SCR-09).** Own queue without resident identity, T8, T9 with notes validation.

**Slice 6: Verify, close, reopen (FR-12; SCR-08).** T10, T11. After this slice the whole lifecycle (including reopen and reassign loops) must work in the browser; do a full manual walkthrough.

**Slice 7: User administration and CSV import (FR-03, FR-04; SCR-11, SCR-12).** Account guards (BR-07), temporary passwords, all-or-nothing validated import, one-time credentials file.

**Slice 8: Dashboard and audit review (FR-16, FR-18; SCR-10, SCR-13).** Role-scoped aggregates, request history, Admin audit search.

**Phase 9: Hardening and packaging.** nginx with security headers and body limits, Dockerfiles, full Compose stack (proxy, api non-root, db with no published port, migrate one-shot), `.env.example` complete, three-command start from a clean clone, 360 px and empty/error/conflict state review for every screen, OpenAPI schema and generated client types.

**Phase 10: Test Phase.** Implement the test plan in report Section 7 using its IDs (TC-01 to TC-42, NT-01 to NT-09, ST-01 to ST-06) against real PostgreSQL. Known trap to plan for: the audit trigger blocks TRUNCATE, which Django's transactional test cleanup uses. Propose a teardown strategy (for example a fixture that disables and re-enables the trigger as the owner role) and ask me before choosing. Then extend CI to run the tests, and fill the "Actual result" and "Status" columns from real runs only.

**Phase 11: Release.** README with the three-command setup, final TRACEABILITY.md, DEVIATIONS.md summary for updating the report, tag and commit hash. Free-tier deployment is a later optional phase; discuss it with me first and keep the local Compose setup as the assessed system.

---

## 6. Kickoff message (paste this into Antigravity)

> Read `docs/AGENT_BRIEF.md` fully, then read Sections 2 to 6 of `docs/source/NPRJ740_Final_Project_Report_v4.pdf` and `docs/source/FINAL_PROJECT_RUBRIC.pdf`.
>
> Do NOT write any code or install anything yet. Reply with:
> 1. A summary of the system in 15 lines or fewer, in your own words, so I can confirm you understood it.
> 2. Every place where the brief and the report disagree, or where the report is ambiguous or incomplete.
> 3. Any question you need answered before Phase 0.
> 4. Your plan for Phase 0 only: files to create, commands you would run, packages you would install and why, and what "done" looks like.
>
> Then stop and wait for my approval.
