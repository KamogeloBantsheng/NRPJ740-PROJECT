# Architectural & Implementation Deviations Register

This document records any variance between the implementation and the text of `NPRJ740_Final_Project_Report_v4.pdf`, along with rationale and resolution.

| ID | Topic | Report Statement | Implementation Choice | Rationale |
|---|---|---|---|---|
| DEV-01 | Python Runtime Version in Local Dev | Section 5.2 / 5.8 specifies Python 3.12 LTS. | Local development environment utilizes installed Python 3.14.5; Docker containers in Phase 9 will pin Python 3.12 LTS. | User requested to use pre-installed host Python 3.14 for local developer loop to avoid redundant installations. |
| DEV-02 | Developer Loop Reverse Proxy | Section 5.8 specifies Nginx reverse proxy routing traffic on port 8080. | Local dev runs Vite dev server with proxy forwarding `/api` to native Django on port 8000. Full Nginx container stack is introduced in Phase 9 (Hardening). | Provides fast HMR during development while preserving single-origin cookie/CSRF semantics. |
