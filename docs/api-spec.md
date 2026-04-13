# API Specification

## Authentication & User Management
### `POST /register` (primary) / `POST /signup` (alias)
- **Description**: Register a new user.
- **Request Body**: `{ "username": "string", "password": "string", "role": "string" }`
- **Response**: `{ "id": "int", "username": "string", "role": "string" }`

### `POST /login`
- **Description**: Login and receive a JWT token.
- **Request Body**: `{ "username": "string", "password": "string" }`
- **Response**: `{ "access_token": "string", "token_type": "bearer" }`

### `GET /users/me`
- **Description**: Get current user profile (masked).
- **Auth**: Required
- **Response**: `{ "id": "int", "username": "string", "role": "string" }`

---

## Registration & Materials (Applicant)
### `GET /registration-form`
- **Description**: Get or create the user's form.
- **Auth**: Applicant
- **Response**: `{ "id": "uuid", "status": "string", "data": "object" }`

### `POST /upload/{checklist_id}`
- **Description**: Upload material (max 20MB, latest 3 kept).
- **Auth**: Applicant
- **Request**: `Multipart/form-data (file)`
- **Response**: `{ "id": "uuid", "filename": "string", "version": "int" }`

---

## Review Workflow (Reviewer)
### `GET /reviewer/applications`
- **Description**: List applications for review.
- **Auth**: Reviewer/Admin
- **Response**: `Array<{ "id": "uuid", "applicant": "string", "status": "string" }>`

### `POST /reviewer/applications/{id}/transition`
- **Description**: Change application state.
- **Auth**: Reviewer/Admin
- **Request Body**: `{ "to_state": "string", "comment": "string" }`
- **Response**: `{ "id": "uuid", "new_status": "string" }`

---

## Financial Management
### `POST /financial/transactions`
- **Description**: Record income/expense (with budget check).
- **Auth**: FinancialAdmin/Admin
- **Request Body**: `{ "account_id": "uuid", "amount": "float", "category": "string", "type": "income|expense" }`
- **Response**: `{ "id": "uuid", "status": "recorded", "alert": "boolean" }`

---

## System Operations (System Admin)
### `GET /admin/metrics`
- **Description**: Get current system metrics.
- **Auth**: SystemAdmin
- **Response**: `{ "active_users": "int", "pending_reviews": "int", "system_health": "string" }`

### `POST /admin/backup`
- **Description**: Trigger manual DB backup.
- **Auth**: SystemAdmin
- **Response**: `{ "status": "success", "backup_file": "string" }`
