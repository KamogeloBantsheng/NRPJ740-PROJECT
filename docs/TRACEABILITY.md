# Requirements Traceability Matrix

This living document tracks each Included requirement (FR-01 to FR-18) from problem evidence, use case, screen, service/class, database table, business rules, code path, and verification test.

| FR | Evidence | Use Case | Screen | Class / Service | Tables | Rules | Code Path | Tests (Test Phase) |
|---|---|---|---|---|---|---|---|---|
| FR-01 | SC-2 | UC-01 | SCR-01 | AuthService, PermissionPolicy | `users`, `django_session`, `audit_logs` | BR-07, NFR-02 | `AuthService.authenticate`, `LoginView`, `LogoutView`, `MeView`, `LoginPage` (SCR-01), `AuthContext`, `ProtectedRoute`, `Navbar`, `seed_demo_users` (Slice 1) | TBD (TC-01 to TC-04) |
| FR-02 | SC-2 | UC-02 | SCR-02 | AuthService | `users` | NFR-02 | `AuthService.change_password`, `ChangePasswordView`, `ChangePasswordPage` (SCR-02) (Slice 1) | TBD (TC-05) |
| FR-03 | SC-2 | UC-03 | SCR-11 | UserAdminService | `users`, `audit_logs` | BR-07 | TBD (Slice 7) | TBD (TC-06) |
| FR-04 | SC-2 | UC-04 | SCR-12 | UserImportService, UserAdminService | `users`, `audit_logs` | BR-07, NFR-03 | TBD (Slice 7) | TBD (TC-07 to TC-09) |
| FR-05 | P-1, P-2, SC-1 | UC-05 | SCR-04 | TransitionService, PermissionPolicy | `maintenance_requests`, `locations`, `fault_categories`, `audit_logs` | BR-05, BR-09 | `apps.workflow.views` (RequestListCreateView.post), `apps.workflow.services` (TransitionService.submit_request), `apps.locations.views` (LocationListView, FaultCategoryListView), `SubmitRequestPage` (SCR-04), `workflowApi.submitRequest` (Slice 2) | TBD (TC-10 to TC-13, TC-35) |
| FR-06 | P-2, SC-1 | UC-06 | SCR-03, SCR-05 | PermissionPolicy (scope), AuditService | `maintenance_requests`, `audit_logs` | BR-05 | `apps.workflow.views` (RequestListCreateView.get, RequestDetailView, RequestTimelineView), `apps.workflow.permissions` (PermissionPolicy.scope_requests), `ResidentRequestsPage` (SCR-03), `RequestDetailPage` (SCR-05), `StatusBadge` (Slice 2) | TBD (TC-14) |
| FR-07 | P-1, SC-1 | UC-07 | SCR-05 | TransitionService | `maintenance_requests`, `audit_logs` | BR-02, BR-05 | TBD (Slice 3) | TBD (TC-15, TC-19, TC-35) |
| FR-08 | P-1, P-3, SC-1 | UC-08 | SCR-06 | PermissionPolicy (scope) | `maintenance_requests` | — | TBD (Slice 3) | TBD (TC-16) |
| FR-09 | P-1, P-3, SC-1 | UC-09 | SCR-06 | TransitionService, TransitionRule | `maintenance_requests`, `audit_logs` | BR-02, BR-08 | TBD (Slice 3) | TBD (TC-17 to TC-20, TC-35) |
| FR-10 | P-1, P-3, SC-3 | UC-10 | SCR-07 | TransitionService | `work_orders`, `maintenance_requests`, `audit_logs` | BR-01, NFR-04 | TBD (Slice 4) | TBD (TC-21 to TC-25, TC-35) |
| FR-11 | P-3, SC-3 | UC-11 | SCR-07 | TransitionService | `work_orders`, `maintenance_requests`, `audit_logs` | BR-01, BR-02, BR-03 | TBD (Slice 4) | TBD (TC-26, TC-27, TC-35) |
| FR-12 | P-3, SC-1 | UC-12 | SCR-08 | TransitionService | `work_orders`, `maintenance_requests`, `audit_logs` | BR-02, BR-06, BR-10 | TBD (Slice 6) | TBD (TC-32 to TC-35) |
| FR-13 | P-3, SC-2 | UC-13 | SCR-09 | PermissionPolicy (scope) | `work_orders`, `maintenance_requests` | BR-04 | TBD (Slice 5) | TBD (TC-28) |
| FR-14 | P-3, SC-1 | UC-14 | SCR-09 | TransitionService | `maintenance_requests`, `audit_logs` | BR-01 | TBD (Slice 5) | TBD (TC-29, TC-35) |
| FR-15 | P-3, SC-1 | UC-15 | SCR-09 | TransitionService | `maintenance_requests`, `audit_logs` | BR-02 | TBD (Slice 5) | TBD (TC-30, TC-31, TC-35) |
| FR-16 | P-4, SC-2 | UC-16 | SCR-10 | ReportingService, PermissionPolicy | `maintenance_requests`, `work_orders` | BR-04, NFR-06 | TBD (Slice 8) | TBD (TC-36, TC-37) |
| FR-17 | P-4, SC-4 | (system behavior) | — | AuditService, TransitionService | `audit_logs` | NFR-03, NFR-05 | `apps.audit.models` (AuditEvent), `0001_initial` triggers, `AuditService.record` (Phase 1 / Slice 1-8) | TBD (TC-38 to TC-40) |
| FR-18 | P-4, SC-4 | UC-18 | SCR-05, SCR-13 | AuditService, PermissionPolicy | `audit_logs` | NFR-05 | `AuditService.get_request_history`, `RequestTimelineView`, `workflowApi.getRequestTimeline`, `RequestDetailPage` timeline (Slice 2 / Slice 8) | TBD (TC-41) |

---
*Note: FR-19 through FR-23 are excluded/deferred per Section 3.3 of the Final Project Report and are not built.*
