# Design Approach: Activity Registration Platform

## Core Architecture
The platform follows a modern decoupled architecture:
- **Frontend**: Vue 3 (Vite) + TypeScript + Pinia.
- **Backend**: FastAPI (Python) + SQLAlchemy (PostgreSQL).
- **Infrastructure**: Docker Compose for containerization.

## Key Design Principles
1. **Role-Based Access Control (RBAC)**: Strict separation of concerns for Applicants, Reviewers, Financial Admins, and System Admins.
2. **State Machine Workflow**: Application lifecycles are managed through defined state transitions (e.g., `Submitted` -> `Under Review` -> `Approved/Rejected/Correction`).
3. **Data Privacy & Security**: 
   - Sensitive data (e.g., ID numbers) is masked by the backend based on user roles.
   - Whitelist policies are stored with Fernet encryption.
   - OAuth2 with JWT for secure authentication.
4. **Auditability**: Every state transition and review comment is logged in an audit trail.
5. **Financial Integrity**: Budget checks (10% threshold alerts) and transaction categorization for financial monitoring.
6. **Material Versioning**: Retention of the last 3 versions of uploaded materials (PDF/JPG/PNG) with a 20MB limit.

## Component Strategy
- **Views**: Dedicated dashboards for each role to minimize UI clutter.
- **State Management**: Pinia stores for Auth, Applications, Financials, and System Metrics.
- **API Communication**: Centralized Axios instance with interceptors for JWT injection.
