# questions.md

## 1. Authentication & Session Management

**Question:** Login is defined, but session handling and password recovery are not specified.
**Assumption:** The system uses token-based authentication with session expiration and supports password reset.
**Solution:** Implement JWT-based authentication with expiration and a secure password reset flow.

## 2. Role-Based Access Control (RBAC) & Visibility

**Question:** The specific boundaries between Reviewers, Financial Admins, and Applicants regarding cross-feature visibility are not defined.
**Assumption:** Reviewers cannot see financial/budget data. Financial Admins can see application statuses but cannot trigger state transitions. Applicants can only see their own data and "Submitted" versions of their materials.
**Solution:** Implement a centralized `PermissionGuard` in the Vue frontend and a decorator-based `RoleChecker` in the FastAPI backend to enforce endpoint-level and field-level access.

## 3. State Machine & Workflow

**Question:** The exact transitions and logic for "Promoted from Waitlist" and "Batch Review" are not fully defined.
**Assumption:** "Promoted from Waitlist" moves an application back to "Submitted" status for review. Batch review applies the same status transition (e.g., Approve all) to up to 50 selected records simultaneously.
**Solution:** Implement a backend state machine service that validates legal transitions and a frontend "Batch Action" bar on the list page with a 50-item selection limit.

## 4. Material Versioning & Locking

**Question:** The behavior for the "three versions" limit and the "72-hour supplementary" window is underspecified.
**Assumption:** The system keeps the 3 most recent uploads per checklist item. The 72-hour window is a one-time global extension per application, triggered manually by a reviewer or automatically upon a "Needs Correction" status.
**Solution:** Use a `material_versions` table with a version counter; auto-delete/archive the 4th oldest. Implement a `supplementary_deadline` timestamp field in the application model to track the 72-hour window.

## 5. Financial Budgeting & Warnings

**Question:** It is unclear which budget baseline is used for the 10% overspending warning.
**Assumption:** The 10% threshold is calculated against the "Total Approved Budget" for a specific activity. The warning is a non-blocking UI modal that requires a "Confirm Overspend" checkbox to be ticked before saving.
**Solution:** Frontend calculates `(current_expenses + new_entry) / total_budget`. If > 1.1, trigger a secondary confirmation dialog before allowing the POST request to the FastAPI backend.

## 6. File Storage & Duplicate Detection

**Question:** The scope of the 200MB limit and the "similarity check" implementation are vague.
**Assumption:** The 200MB limit applies to the sum of all versions of all materials for a single application. The similarity check is a reserved REST endpoint that currently only compares SHA-256 fingerprints.
**Solution:** Backend calculates total file size on every upload attempt and rejects if `sum(existing_files) + new_file > 200MB`. Store SHA-256 in the `materials` table and index it for O(1) duplicate lookups.

## 7. Security & Access Control

**Question:** Specific masking rules for "sensitive fields" and the "access frequency control" implementation are needed.
**Assumption:** Masking replaces all but the last 4 characters of ID numbers and contact info for non-admin roles. The 30-minute lock applies to the specific username used during the failed attempts.
**Solution:** Implement a custom FastAPI dependency to mask PII in the response model based on the user's role. Use a Redis-like local cache or a dedicated `login_attempts` table in PostgreSQL to track and enforce the 10-tries/5-min lockout rule.

## 8. User Registration vs Predefined Accounts

**Question:** The prompt specifies pseudo-login but does not clarify whether users can register new accounts or must use predefined ones.
**Assumption:** Users can create accounts locally within the app.
**Solution:** Implemented a local registration flow storing user credentials securely in IndexedDB.

## 9. Data Masking Logic

**Question:** Which roles are exempt from "role-based masking" for sensitive fields like ID numbers and contact info?
**Assumption:** Only the System Administrator can view unmasked sensitive data. All other roles (Reviewer, Financial Admin, Applicant) see masked values (e.g., `****-****-5678`) in the UI.
**Solution:** Create a Pydantic `ResponseModel` in FastAPI that automatically masks designated fields unless the authenticated user has the `SYS_ADMIN` role.

## 10. Audit Log Ownership

**Question:** Who has the right to view "traceable logs" and "access auditing" records?
**Assumption:** Reviewers can see logs related to applications they are reviewing. System Administrators can see all system-wide access audits. Applicants cannot see any audit logs.
**Solution:** Filter audit log queries by `application_id` for Reviewers and provide a global `AuditDashboard` accessible only to the System Administrator.

## 11. Administrative Overrides

**Question:** Can System Administrators modify application data or force state machine transitions in case of errors?
**Assumption:** System Administrators have "Super-user" privileges to manually override any application state or correct form data if requested by the user, bypassing standard workflow locks.
**Solution:** Implement an `AdminOverrideService` in the backend that logs all "Super-user" actions with a mandatory "Reason for Override" field for the audit trail.

## 12. User & Role Management (UI & API)

**Question:** There is no specification for how administrators create users, assign roles, or deactivate accounts, nor which REST endpoints support those operations.
**Assumption:** Only System Administrators can list, create, update, and deactivate users and assign roles. Roles are a fixed enum aligned with RBAC (e.g., Applicant, Reviewer, Financial Admin, System Administrator). Password changes by admins use a secure reset flow or temporary password; self-service profile edits remain separate from admin user management.
**Solution:** Expose FastAPI routes under `/api/admin/users` and `/api/admin/roles` (or nested `/users/{id}/roles`) with `SYS_ADMIN`-only dependencies, backed by `users` and `user_roles` tables. Add a Vue admin screen: searchable user table, create/edit user modal, role multi-select, active/inactive toggle, and audit-friendly success/error toasts. Reuse the existing `PermissionGuard` for the new routes and navigation entry.