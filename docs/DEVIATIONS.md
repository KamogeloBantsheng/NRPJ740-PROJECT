# Architectural & Implementation Deviations Register

This document records any variance between the implementation and the text of `NPRJ740_Final_Project_Report_v4.pdf`, along with rationale and resolution.

| ID | Topic | Report Statement | Implementation Choice | Rationale |
|---|---|---|---|---|
| DEV-01 | Python Runtime Version in Local Dev | Section 5.2 / 5.8 specifies Python 3.12 LTS. | Local development environment utilizes installed Python 3.14.5; Docker containers in Phase 9 will pin Python 3.12 LTS. | User requested to use pre-installed host Python 3.14 for local developer loop to avoid redundant installations. |
| DEV-02 | Developer Loop Reverse Proxy | Section 5.8 specifies Nginx reverse proxy routing traffic on port 8080. | Local dev runs Vite dev server with proxy forwarding `/api` to native Django on port 8000. Full Nginx container stack is introduced in Phase 9 (Hardening). | Provides fast HMR during development while preserving single-origin cookie/CSRF semantics. |
| DEV-03 | Database Port Exposure in Development | Section 5.8 specifies database publishes no port to the host. | `docker-compose.dev.yml` maps port 5432 to host localhost. Full deployment stack in Phase 9 leaves database off host network. | Required for native Django dev server to communicate with the PostgreSQL container. |
| DEV-04 | Dedicated Development Compose Configuration | Section 6.1 specifies single `docker-compose.yml`. | Separate `docker-compose.dev.yml` runs PostgreSQL standalone for development, preserving `docker-compose.yml` for the full four-container production stack in Phase 9. | Isolates dev service management from full production multi-container orchestration. |
| DEV-05 | Moroka Hall Room Data & Layout | Brief / initial assumptions estimated Blocks A-C across floors 1-3. | Institutional master data (`Everyone .xlsx`) contains 414 rooms across Block A (floors 2-3) and Block B (floors 0-4), plus standard common areas across all floors. | Accurately models real-world Sol Plaatje University campus facilities. |
