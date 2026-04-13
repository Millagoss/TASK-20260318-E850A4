# Delivery Acceptance & Project Architecture — Static Audit Report

**Audit date:** 2026-04-13  
**Scope:** `D:\Eagle-task\TASK-20260318-E850A4` (primary evidence under `repo/`)  
**Method:** Static analysis only — no runtime execution, Docker, tests, or browsers.

---

## 1. Verdict

**Overall conclusion: Partial Pass (with Blocker-level authorization and alert-logic defects)**

The repository implements a coherent FastAPI + Vue 3 split, PostgreSQL-oriented persistence, role-gated routes, reviewer/financial/admin surfaces, and several prompt-aligned mechanisms (material limits, SHA-256, batch cap 50, budget warning API, encrypted whitelist payloads). However, **public self-registration accepts any role from the client**, which conflicts with typical **permission isolation** and turns `/register` into a **privilege-escalation surface**. **Metric alerting uses a single “greater than threshold” rule**, which is **semantically wrong for `approval_rate`** (high approval should not be treated as a breach). Together with **thin automated testing**, **no documented non-Docker / test workflow**, and **gaps vs. “access auditing”** in the prompt, the delivery is **not statically defensible as production-complete** without follow-up.

---

## 2. Scope and Static Verification Boundary

**Reviewed**

- `repo/README.md`, `repo/.env.example`, `repo/docker-compose.yml`
- Backend: `repo/backend/main.py`, `repo/backend/auth.py`, `repo/backend/models.py`, `repo/backend/schemas.py`, `repo/backend/database.py`, `repo/backend/requirements.txt`, `repo/backend/scripts/daily_backup.sh`, `repo/backend/Dockerfile`
- Tests: `repo/backend/tests/test_phase_a_baseline.py`
- Frontend: `repo/frontend/package.json`, `repo/frontend/src/router/index.ts`, `repo/frontend/src/App.vue`, `repo/frontend/src/stores/auth.ts`, `repo/frontend/src/views/LoginView.vue`, `repo/frontend/src/views/SignupView.vue`, `repo/frontend/src/views/FormWizardView.vue`, `repo/frontend/src/views/FinancialDashboardView.vue`, `repo/frontend/src/views/ReviewerDashboardView.vue` (partial), `repo/frontend/src/components/FileUpload.vue`

**Not reviewed (no evidence gathered)**

- Full contents of every Vue view (e.g. `SystemAdminDashboardView.vue`, `DashboardView.vue` beyond cross-checks), all `node_modules/`, `venv/`
- Runtime behavior of Docker builds, DB migrations at runtime, browser rendering, PDF/binary handling edge cases

**Intentionally not executed**

- Application start, pytest, Docker Compose, database connectivity, file I/O on real disks

**Claims requiring manual verification**

- Any statement that flows “work end-to-end in production” — **Manual Verification Required**
- Uvicorn access logs for HTTP-level auditing — **Cannot Confirm Statistically** (depends on deployment flags and process manager)

---

## 3. Repository / Requirement Mapping Summary

**Prompt core:** Closed-loop English platform for applicants (wizard + checklist materials with validation, versioning, deadlines, one-time 72h supplement), reviewers (state machine, batch ≤50, comments, traceable logs), financial admins (transactions, invoices, aggregates, >10% budget warning with secondary confirm), system admins (metrics, thresholds, alerts, backups/recovery, exports, whitelist, data collection / quality validation), PostgreSQL, local files + SHA-256, optional duplicate/similarity off by default, username/password with strong hashing, lockout policy, RBAC + masking, access auditing, encrypted sensitive config, offline-first.

**Implementation mapping:** Monolithic `main.py` registers all routes; SQLAlchemy models cover forms, checklists/versions, review records, funding/transactions, thresholds/alerts, whitelist, batches, quality results, users/login attempts; Vue routes + role meta guard applicant/reviewer/financial/system areas; README documents Docker-first run and role-based pages.

---

## 4. Section-by-section Review

### 4.1 Hard Gates — Documentation and static verifiability

| Item | Conclusion | Rationale | Evidence |
|------|------------|-----------|----------|
| Startup / run / test / config instructions | **Partial Pass** | Clear Docker path and `.env` template; **no** documented local (non-Docker) backend/frontend commands; **no** documented `pytest` invocation despite `pytest` in `requirements.txt`. | `repo/README.md:15–100`, `repo/.env.example:1–7`, `repo/frontend/package.json:6–9`, `repo/backend/requirements.txt:11` |
| Doc ↔ code / structure consistency | **Partial Pass** | README lists routes and stack consistent with `main.py` and Vue router; README notes `create_all` vs Alembic — matches `main.py` using `create_all`. | `repo/README.md:104–105`, `repo/backend/main.py:22–23` |
| Enough static evidence to verify without rewriting core | **Partial Pass** | Substantial surface area is inspectable; **very small** automated test surface limits verification of critical flows. | `repo/backend/tests/test_phase_a_baseline.py:1–78` |

### 4.2 Hard Gates — Material deviation from Prompt

| Item | Conclusion | Rationale | Evidence |
|------|------------|-----------|----------|
| Centered on business goal | **Partial Pass** | Major domains exist; several prompt details are simplified (fixed checklist seed, mock deadline offset, manual quality scores). | `repo/backend/main.py:153–167`, `repo/backend/main.py:1043–1065` |
| Loose / unrelated parts | **Pass** | No large unrelated subsystems observed in reviewed files. | — |
| Replaces / ignores core problem | **Partial Pass** | **Open role assignment on registration** undermines closed-loop governance implied by strict roles; **access auditing** beyond review logs not modeled. | `repo/backend/main.py:57–80`, `repo/backend/schemas.py:174–178`; audit grep hits only review/export paths — `repo/backend/main.py:539–552`, `repo/backend/main.py:999–1006` |

### 4.3 Delivery Completeness — Core requirements coverage

| Item | Conclusion | Rationale | Evidence |
|------|------------|-----------|----------|
| All explicit core FRs implemented | **Partial Pass** | Wizard + upload validation + 3 versions + totals + supplement window + reviewer SM + batch 50 + financial + budget API + duplicate stub + lockout + bcrypt + many admin endpoints: **present in code**. Gaps: **no first-class “access audit” store/API**; **quality / registration “rule-based validation”** is largely manual/admin API rather than automated rules over form fields; **version-level labels** (Pending Submission / Submitted / Needs Correction) are **checklist-level**, not per `MaterialVersion` row. | `repo/backend/main.py:181–274`, `repo/backend/models.py:24–49`, `repo/backend/main.py:303–372`, `repo/backend/main.py:492–517`, `repo/backend/auth.py:31–60` |
| 0→1 deliverable vs fragment | **Pass** | Full stack layout, multiple views, persistence models — not a single-file toy. | `repo/frontend/src/router/index.ts:12–65`, `repo/backend/models.py:13–155` |
| Mock / hardcoded without explanation | **Partial Pass** | README disclaims migrations; code uses fixed checklist and `+ timedelta(days=7)` deadline — **mock-like** but partially explained in README for migrations only. | `repo/README.md:104–105`, `repo/backend/main.py:153–167` |
| README or equivalent | **Pass** | `repo/README.md` exists and is substantive. | `repo/README.md:1–107` |

### 4.4 Engineering and Architecture Quality

| Item | Conclusion | Rationale | Evidence |
|------|------------|-----------|----------|
| Structure / decomposition | **Partial Pass** | Reasonable for a demo/small product but **~1077 lines** of API surface in one module is heavy coupling. | `repo/backend/main.py` (route density per grep) |
| Maintainability / extensibility | **Partial Pass** | Clear models/schemas; business rules embedded in handlers; Alembic listed but not used as migration path. | `repo/backend/requirements.txt:4`, `repo/README.md:104–105` |

### 4.5 Engineering Details and Professionalism

| Item | Conclusion | Rationale | Evidence |
|------|------------|-----------|----------|
| Error handling / validation / logging / API design | **Partial Pass** | Pydantic on JSON bodies; many `HTTPException`s; structured `logger` calls for login/review/backup/recovery/budget warning; **no global request/access audit logger to DB**; **HTTP 409 detail** for budget warning is a **dict** — fine for machine clients, easy to mishandle in generic clients. | `repo/backend/main.py:26–30`, `repo/backend/main.py:87–105`, `repo/backend/main.py:604–629` |
| Product-like vs demo | **Partial Pass** | UI and API breadth resemble a product; hardcoded `http://localhost:8000` across views limits real deployment without code/config changes. | e.g. `repo/frontend/src/views/FinancialDashboardView.vue:23–35`, `repo/frontend/src/components/FileUpload.vue:66–67` |

### 4.6 Prompt Understanding — Requirement Fit

| Item | Conclusion | Rationale | Evidence |
|------|------------|-----------|----------|
| Business goal / constraints | **Partial Pass** | Strong fit on materials, reviewer batch, financial warning path, whitelist encryption, duplicate feature flag; **weak** on holistic access auditing, automated quality/rule engine, and **secure role provisioning**. | `repo/backend/main.py:276–301`, `repo/backend/main.py:776–780`, `repo/backend/main.py:57–80` |

### 4.7 Aesthetics (frontend — static source review)

| Item | Conclusion | Rationale | Evidence |
|------|------------|-----------|----------|
| Layout / hierarchy / consistency | **Partial Pass** | `App.vue` sidebar + cards in dashboards show spacing, cards, modals for budget warning; **Cannot Confirm Statistically** for actual render, fonts loaded, or icon correctness (no icon library reviewed). | `repo/frontend/src/App.vue:34–50`, `repo/frontend/src/views/FinancialDashboardView.vue:119–201`, `repo/frontend/src/views/FormWizardView.vue:76–141` |
| Interaction feedback | **Partial Pass** | Hover on login button, disabled states, modal for budget confirmation present in source. | `repo/frontend/src/views/LoginView.vue:191–194`, `repo/frontend/src/views/FinancialDashboardView.vue:176–186` |

---

## 5. Issues / Suggestions (Severity-Rated)

### Blocker

1. **Public registration accepts client-chosen privileged roles (`SystemAdmin`, `Reviewer`, `FinancialAdmin`)**  
   - **Conclusion:** Any unauthenticated caller can create a `SystemAdmin` (also exercised in tests), violating prompt-level **permission isolation** / realistic governance.  
   - **Evidence:** `repo/backend/schemas.py:174–178`, `repo/backend/main.py:57–80`, `repo/backend/tests/test_phase_a_baseline.py:42–47`  
   - **Impact:** Full tenant compromise without social engineering.  
   - **Minimum fix:** Restrict self-signup to `Applicant` (or remove role from public schema); provision privileged roles only via bootstrap script or authenticated `SystemAdmin` workflow.

### High

2. **Approval-rate alerting logic is inverted**  
   - **Conclusion:** Alerts fire when `metric_value > threshold` for **all** metrics; for `approval_rate`, higher values are better, so breaches should typically be **below** threshold.  
   - **Evidence:** `repo/backend/main.py:810–841` (metrics list includes `approval_rate`; alert condition `item["metric_value"] > threshold` at `831–833`)  
   - **Impact:** False positives when approval is strong; no alert when approval collapses — undermines “local alerts when thresholds are exceeded” for that metric.  
   - **Minimum fix:** Per-metric direction (or separate comparators), e.g. alert `approval_rate < threshold`.

3. **One-click recovery accepts `file_name` without path hardening**  
   - **Conclusion:** `os.path.join(backup_dir, file_name)` with user-controlled `file_name` is a classic **path traversal** pattern unless normalized and constrained under `backup_dir`.  
   - **Evidence:** `repo/backend/main.py:945–954`  
   - **Impact:** **Suspected Risk** of reading/restoring arbitrary files reachable from process — severity **High** pending OS path behavior; **Manual Verification Required** on target OS.  
   - **Minimum fix:** `realpath` + require `commonpath` prefix of `backup_dir`; reject `..` and absolute paths.

4. **Backup script embeds default database credentials when `DATABASE_URL` unset**  
   - **Conclusion:** Fallback URL contains `postgres:password@db` — dangerous default if ever run outside Compose-injected env.  
   - **Evidence:** `repo/backend/scripts/daily_backup.sh:7–11`  
   - **Impact:** Credential leakage in image/script; accidental use of weak defaults.  
   - **Minimum fix:** Remove fallback; fail fast if `DATABASE_URL` missing (align with backend startup strictness).

5. **Prompt “access auditing” not implemented as a cross-cutting audit trail**  
   - **Conclusion:** Only **review workflow** records and CSV export exist; no generalized access/audit log model for API reads/writes.  
   - **Evidence:** `repo/backend/models.py:51–63`, `repo/backend/main.py:539–552`, `repo/backend/main.py:999–1006` (no `AccessAudit` / equivalent in `models.py`)  
   - **Impact:** Compliance / forensics gap vs prompt.  
   - **Minimum fix:** Add audit middleware or service + persistence, cover sensitive routes.

### Medium

6. **README documents Docker run but not automated tests or non-Docker dev**  
   - **Evidence:** `repo/README.md:15–100` vs absence of pytest; `repo/backend/requirements.txt:11`  
   - **Impact:** Reviewers must discover `pytest` themselves.  
   - **Fix:** Document `cd backend && pytest` (and env vars mirroring test file).

7. **Frontend API base URL hardcoded to `localhost:8000`**  
   - **Evidence:** `repo/frontend/src/views/FinancialDashboardView.vue:23–35`, `repo/frontend/src/components/FileUpload.vue:66–67`, `repo/frontend/src/views/FormWizardView.vue:52–53`  
   - **Impact:** Offline / LAN / TLS deployments require code edits or build-time replacement.  
   - **Fix:** `import.meta.env.VITE_API_BASE` with documented `.env`.

8. **Wizard “now” for deadline / lock UI is a one-shot `ref(new Date())` — not updated over time**  
   - **Evidence:** `repo/frontend/src/views/FormWizardView.vue:11`, `repo/frontend/src/views/FormWizardView.vue:41–46`, `repo/frontend/src/views/FormWizardView.vue:91–94`  
   - **Impact:** Long-lived tab may show stale lock/deadline state until refresh — **Manual Verification Required** for UX timing.  
   - **Fix:** `setInterval` or server-time sync.

9. **`correction_rate` metric uses count of forms in status `Supplemented`**  
   - **Evidence:** `repo/backend/main.py:789–812` (`supplemented_count` filter)  
   - **Impact:** Semantic mismatch vs “correction rate” as event-based metric — **Partial** requirement fit.

### Low

10. **JWT payload decoded in browser only for sidebar role (`atob` on middle segment)**  
    - **Evidence:** `repo/frontend/src/views/LoginView.vue:44–46`, `repo/frontend/src/stores/auth.ts:4–12`  
    - **Impact:** UI role can desync from token payload if tampered in storage; API still uses DB user on each request — mostly UX confusion.  
    - **Fix:** Return explicit `role` in JSON from `/login` or use a small `/users/me` fetch after login.

11. **Duplicate-check when enabled scans global `MaterialVersion` hashes**  
    - **Evidence:** `repo/backend/main.py:290–294`  
    - **Impact:** Cross-applicant duplicate surfacing may or may not match policy — document or scope by tenant.

---

## 6. Security Review Summary

| Dimension | Conclusion | Evidence & reasoning |
|-----------|------------|----------------------|
| Authentication entry points | **Partial Pass** | `/register`, `/signup`, `/login`, OAuth2 form + JWT — `repo/backend/main.py:57–110`, `repo/backend/auth.py:16–17`, `repo/backend/auth.py:81–99`. Lockout hooks present — `repo/backend/auth.py:31–60`. |
| Route-level authorization | **Partial Pass** | `RoleChecker` used on financial/admin/reviewer routes — e.g. `repo/backend/main.py:558–563`, `repo/backend/main.py:708–711`, `repo/backend/main.py:375–378`. **Gap:** `/register` has **no** auth and accepts any `role`. |
| Object-level authorization | **Partial Pass** | Applicant upload checks `checklist.registration_form.user_id == current_user.id` — `repo/backend/main.py:192–194`. Reviewer/financial list endpoints are **global** (no per-reviewer assignment) — `repo/backend/main.py:374–410`, `repo/backend/main.py:576–581` — may be acceptable for single-pool prompt but not multi-tenant isolation. |
| Function-level authorization | **Cannot Confirm Statistically** | Depends on all routes audited; large `main.py` increases miss risk — spot-checked major groups only. |
| Tenant / user data isolation | **Partial Pass** | Applicant path tied to `user_id`; reviewer/financial admin see cross-user business data by design in current API. |
| Admin / internal / debug protection | **Partial Pass** | `/admin/*` routes use `RoleChecker` — e.g. `repo/backend/main.py:823–827`. `/admin/data` sample is admin-only — `repo/backend/main.py:145–147`. **No debug** routes found in reviewed `main.py` grep list. |

---

## 7. Tests and Logging Review

| Area | Conclusion | Evidence |
|------|------------|----------|
| Unit tests | **Partial Pass** | Single test module with two tests — `repo/backend/tests/test_phase_a_baseline.py:19–78`. |
| API / integration tests | **Partial Pass** | Uses `TestClient` against `app` — same file; **very narrow** surface. |
| Logging / observability | **Partial Pass** | Named logger + structured fields for key events — `repo/backend/main.py:26–30`, `repo/backend/main.py:93–105`, `repo/backend/main.py:351–357`, `repo/backend/main.py:939–942`. Not a full audit trail. |
| Sensitive data in logs / responses | **Partial Pass** | Usernames in logs; `id_number` masked for reviewers — `repo/backend/main.py:324–331`, `repo/backend/main.py:351–357`. **Risk:** backup/recovery logs include stderr/stdout strings — `repo/backend/main.py:939–942`, `repo/backend/main.py:971–973` — **Cannot Confirm Statistically** if secrets leak without runtime samples. |

---

## 8. Test Coverage Assessment (Static Audit)

### 8.1 Test Overview

- **Unit tests:** Present but minimal (`2` test functions).  
- **API / integration tests:** `httpx` via FastAPI `TestClient` — `repo/backend/tests/test_phase_a_baseline.py:12–17`.  
- **Framework:** `pytest` declared — `repo/backend/requirements.txt:11`.  
- **Entry point:** `repo/backend/tests/test_phase_a_baseline.py`.  
- **Documentation:** README **does not** document pytest — **Gap** — `repo/README.md:15–100`.  

### 8.2 Coverage Mapping Table

| Requirement / Risk Point | Mapped Test Case(s) | Key Assertion / Fixture | Coverage Assessment | Gap | Minimum Test Addition |
|---------------------------|---------------------|-------------------------|---------------------|-----|------------------------|
| Register + login happy path | `test_register_login_and_duplicate_interface_disabled` | `repo/backend/tests/test_phase_a_baseline.py:19–32` | **Basically covered** | Password rules, invalid email, duplicate username | Parametrized 4xx cases |
| Duplicate-check disabled | same | `repo/backend/tests/test_phase_a_baseline.py:34–40` | **Sufficient** for stub | Enabled=true path, hash match | Toggle env + assert IDs |
| System admin block/unblock | `test_system_admin_user_management_block_unblock` | `repo/backend/tests/test_phase_a_baseline.py:42–77` | **Basically covered** | Wrong role calling `/admin/users/.../block` | `403` as `Reviewer` |
| **Privilege escalation via `/register` role=`SystemAdmin`** | **None** | — | **Missing** | No negative test restricting roles | Assert `403` or role stripped for non-admin caller |
| Upload validation (type/size/total/deadline) | **None** | — | **Missing** | Core applicant compliance | `TestClient` multipart + DB fixtures |
| Supplementary 72h window | **None** | — | **Missing** | — | Needs correction + boundary timestamps |
| Reviewer state machine illegal transition | **None** | — | **Missing** | — | `400` on illegal edge |
| Batch > 50 rejected | **None** | — | **Missing** | — | `400` with 51 ids |
| Financial budget warning `409` | **None** | — | **Missing** | — | Expense pushing `>1.1` budget without override |
| Object-level upload isolation | **None** | — | **Missing** | Another user’s `checklist_id` | `404` as other applicant |
| JWT missing / invalid → `401` | **None** | — | **Missing** | — | No `Authorization` header on `/registration-form` |
| Recovery path traversal | **None** | — | **Missing** | — | Static negative cases if fixing code first |
| Metric alert direction (`approval_rate`) | **None** | — | **Missing** | Logic bug undetected | Seed forms; call `/admin/metrics/calculate` |

### 8.3 Security Coverage Audit

| Risk | Tests meaningfully reduce undetected severe defects? |
|------|------------------------------------------------------|
| Authentication | **Partial** — login/register only; no token/JWT edge cases. |
| Route authorization | **Insufficient** — no `403` matrix for role-gated routes. |
| Object-level authorization | **Missing** — highest static risk for data isolation bugs. |
| Tenant isolation | **Missing** — not covered beyond implicit single-user flows. |
| Admin protection | **Partial** — block/unblock covered for one path only. |

### 8.4 Final Coverage Judgment

**Fail**

**Explanation:** While two smoke tests exist (`repo/backend/tests/test_phase_a_baseline.py:19–78`), **critical negative paths and cross-user isolation are untested**, and **known-high-risk behaviors** (open role registration, alert comparator, recovery filename) have **no** automated assertions. The suite can **pass while severe authorization and business-logic defects remain**.

---

## 9. Final Notes

- Static review confirms **substantial feature alignment** with the prompt in **materials, reviewer workflow shape, financial operations, and admin operations**, but **does not** establish runtime correctness.  
- The strongest **evidence-backed** risks for acceptance are: **(1) open privileged registration**, **(2) inverted approval-rate alerting**, **(3) suspected recovery path traversal**, **(4) backup script default credentials**.  
- **Frontend aesthetics** judged only from source structure — final UI fidelity remains **Cannot Confirm Statistically** without running the app.

---

## Sources (evidence index)

- `repo/README.md`  
- `repo/docker-compose.yml`, `repo/.env.example`  
- `repo/backend/main.py`  
- `repo/backend/auth.py`, `repo/backend/models.py`, `repo/backend/schemas.py`, `repo/backend/database.py`  
- `repo/backend/scripts/daily_backup.sh`  
- `repo/backend/tests/test_phase_a_baseline.py`  
- `repo/frontend/package.json`, `repo/frontend/src/router/index.ts`, `repo/frontend/src/App.vue`, `repo/frontend/src/views/*.vue`, `repo/frontend/src/components/FileUpload.vue`, `repo/frontend/src/stores/auth.ts`
