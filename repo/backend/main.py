import asyncio
import base64
import functools
import logging
import re
import os
import hashlib
import csv
import io
import subprocess
from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import timedelta, datetime, timezone
from cryptography.fernet import Fernet

import models, schemas, auth
from database import engine, get_db, SessionLocal
from jose import JWTError, jwt as jose_jwt

# Create tables for demonstration
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Activity Registration Platform API")
logger = logging.getLogger("activity_platform")
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

REQUIRED_ENV_VARS = ["DATABASE_URL", "JWT_SECRET", "WHITELIST_ENCRYPTION_KEY"]

@app.on_event("startup")
def validate_runtime_config():
    missing = [k for k in REQUIRED_ENV_VARS if not os.getenv(k)]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")

origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _financial_admin_may_access_account(account: models.FundingAccount, user: models.User) -> bool:
    if user.role == models.RoleEnum.SystemAdmin:
        return True
    if user.role != models.RoleEnum.FinancialAdmin:
        return False
    return account.financial_admin_user_id is not None and account.financial_admin_user_id == user.id


@app.middleware("http")
async def access_audit_middleware(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path
    if (
        path in ("/health", "/docs", "/openapi.json", "/redoc")
        or path.startswith("/favicon")
        or request.method == "OPTIONS"
    ):
        return response
    user_id = None
    auth_header = request.headers.get("authorization") or request.headers.get("Authorization") or ""
    if auth_header.lower().startswith("bearer ") and auth.SECRET_KEY:
        token = auth_header[7:].strip()
        try:
            payload = jose_jwt.decode(token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
            username = payload.get("sub")
            if username:
                db = SessionLocal()
                try:
                    u = db.query(models.User).filter(models.User.username == username).first()
                    if u:
                        user_id = u.id
                finally:
                    db.close()
        except JWTError:
            pass
    db = SessionLocal()
    try:
        db.add(
            models.ApiAccessAuditLog(
                user_id=user_id,
                method=request.method,
                path=path[:512],
                status_code=response.status_code,
            )
        )
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()
    return response

@app.get("/health")
def health_check():
    return {"status": "ok", "message": "Backend is running"}

@app.post("/register", response_model=schemas.UserResponse)
def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    if not re.match(r"[^@]+@[^@]+\.[^@]+", user.username):
        raise HTTPException(status_code=400, detail="Invalid email format for username")
    if len(user.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    if len(user.password.encode("utf-8")) > 72:
        raise HTTPException(status_code=400, detail="Password is too long (max 72 bytes)")
        
    db_user = db.query(models.User).filter(models.User.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    hashed_password = auth.get_password_hash(user.password)
    new_user = models.User(
        username=user.username,
        password_hash=hashed_password,
        role=models.RoleEnum.Applicant,
        id_number=user.id_number,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@app.post("/signup", response_model=schemas.UserResponse)
def signup_alias(user: schemas.UserCreate, db: Session = Depends(get_db)):
    # Non-breaking alias for docs/terminology consistency.
    return register(user=user, db=db)

@app.post("/login", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    auth.check_login_attempts(form_data.username, db)
    
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    if user and user.is_blocked:
        logger.warning("blocked_login_attempt username=%s", form_data.username)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is blocked")
    if not user or not auth.verify_password(form_data.password, user.password_hash):
        logger.warning("failed_login_attempt username=%s", form_data.username)
        auth.record_failed_attempt(form_data.username, db)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    auth.clear_login_attempts(form_data.username, db)
    logger.info("successful_login username=%s role=%s", user.username, user.role.value)
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.username, "role": user.role.value}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

def mask_data_decorator(func):
    """
    Decorator to mask sensitive fields (like id_number) for non-SystemAdmin users.
    Assumes the endpoint has a 'current_user' dependency parameter.
    """
    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        res = await func(*args, **kwargs)
        return _apply_mask(res, kwargs.get("current_user"))
        
    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs):
        res = func(*args, **kwargs)
        return _apply_mask(res, kwargs.get("current_user"))
        
    def _apply_mask(response, current_user):
        if current_user and current_user.role != models.RoleEnum.SystemAdmin:
            if isinstance(response, models.User):
                resp_dict = schemas.UserResponse.model_validate(response).model_dump()
                if resp_dict.get("id_number") and len(resp_dict["id_number"]) > 4:
                    resp_dict["id_number"] = "*" * (len(resp_dict["id_number"]) - 4) + resp_dict["id_number"][-4:]
                return resp_dict
        return response

    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    return sync_wrapper

@app.get("/users/me", response_model=schemas.UserResponse)
@mask_data_decorator
def read_users_me(current_user: models.User = Depends(auth.get_current_user)):
    return current_user

@app.get("/admin/data")
def read_admin_data(current_user: models.User = Depends(auth.RoleChecker([models.RoleEnum.SystemAdmin]))):
    return {"message": "Hello Admin, here is your protected data."}

# ==========================================
# PHASE 2: Form Wizard & Material Management
# ==========================================

DEFAULT_CHECKLIST = ["ID Proof", "Business Plan", "Financial Statement"]

@app.get("/registration-form", response_model=schemas.RegistrationFormResponse)
def get_registration_form(db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)):
    if current_user.role != models.RoleEnum.Applicant:
        raise HTTPException(status_code=403, detail="Only applicants can have a registration form")

    form = db.query(models.RegistrationForm).filter(models.RegistrationForm.user_id == current_user.id).first()
    
    if not form:
        form = models.RegistrationForm(
            user_id=current_user.id, 
            status="Draft",
            deadline=datetime.utcnow() + timedelta(days=7),
        )
        db.add(form)
        db.commit()
        db.refresh(form)
        
        # Create default checklists
        for item in DEFAULT_CHECKLIST:
            checklist = models.MaterialChecklist(registration_form_id=form.id, item_name=item)
            db.add(checklist)
        db.commit()
        db.refresh(form)
        
    return form

@app.post("/upload/{checklist_id}")
async def upload_material(
    checklist_id: int, 
    file: UploadFile = File(...), 
    reason: str = Form(None),
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(auth.get_current_user)
):
    if current_user.role != models.RoleEnum.Applicant:
        raise HTTPException(status_code=403, detail="Only applicants can upload materials")

    checklist = db.query(models.MaterialChecklist).filter(models.MaterialChecklist.id == checklist_id).first()
    if not checklist or checklist.registration_form.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Checklist not found")

    form = checklist.registration_form
    now = datetime.utcnow()
    
    # 2.2 + Phase B: Deadline locking with strict one-time 72h supplementary semantics.
    if form.deadline and now > form.deadline:
        if checklist.status != "Needs Correction":
            raise HTTPException(status_code=400, detail="Deadline has passed, uploads are locked.")
        if checklist.supplement_used:
            raise HTTPException(status_code=400, detail="Supplementary submission already used once.")
        if not checklist.supplement_expires_at or now > checklist.supplement_expires_at:
            raise HTTPException(status_code=400, detail="72-hour supplementary window has expired.")
            
    # Reason required during correction window
    if checklist.status == "Needs Correction":
        if not reason or not reason.strip():
            raise HTTPException(status_code=400, detail="A reason for correction is required.")
        checklist.correction_reason = reason.strip()

    # 2.2: File type validation
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in [".pdf", ".jpg", ".jpeg", ".png"]:
        raise HTTPException(status_code=400, detail="Only PDF, JPG, and PNG files are allowed.")

    file_content = await file.read()
    file_size = len(file_content)

    # 2.2: File size limit <= 20MB
    if file_size > 20 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File size exceeds the 20MB limit.")
        
    # 2.2: Total size limit <= 200MB
    total_size = sum(v.file_size for cl in form.checklists for v in cl.versions if v.file_size)
    if total_size + file_size > 200 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Total application size exceeds the 200MB limit.")

    file_hash = hashlib.sha256(file_content).hexdigest()

    UPLOAD_DIR = "/app/uploads"
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    safe_filename = f"{current_user.id}_{checklist_id}_{file_hash[:8]}{file_ext}"
    file_path = os.path.join(UPLOAD_DIR, safe_filename)

    with open(file_path, "wb") as f:
        f.write(file_content)

    # Insert version record
    new_version = models.MaterialVersion(
        checklist_id=checklist.id,
        file_path=file_path,
        file_name=file.filename,
        file_hash=file_hash,
        file_size=file_size
    )
    db.add(new_version)
    
    # Update checklist status
    checklist.status = "Submitted"
    if checklist.supplement_expires_at:
        checklist.supplement_used = 1
    if form.status == "Draft":
        form.status = "Submitted"
    db.commit()
    db.refresh(checklist)

    # Version retention: keep only the latest 3
    versions = db.query(models.MaterialVersion).filter(
        models.MaterialVersion.checklist_id == checklist.id
    ).order_by(models.MaterialVersion.uploaded_at.desc()).all()

    if len(versions) > 3:
        for old_version in versions[3:]:
            # delete file from disk if it exists
            if os.path.exists(old_version.file_path):
                os.remove(old_version.file_path)
            db.delete(old_version)
        db.commit()

    return {"detail": "File uploaded successfully", "checklist_id": checklist.id, "status": checklist.status}

@app.post("/materials/duplicate-check", response_model=schemas.DuplicateCheckResponse)
def duplicate_check(
    payload: schemas.DuplicateCheckRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    enabled = os.getenv("FEATURE_DUPLICATE_CHECK", "false").lower() == "true"
    if not enabled:
        return {
            "enabled": False,
            "duplicate_found": False,
            "matching_material_version_ids": [],
            "message": "Duplicate-check feature is disabled",
        }
    matches = (
        db.query(models.MaterialVersion.id)
        .filter(models.MaterialVersion.file_hash == payload.file_hash)
        .all()
    )
    ids = [m.id for m in matches]
    return {
        "enabled": True,
        "duplicate_found": len(ids) > 0,
        "matching_material_version_ids": ids,
        "message": "Duplicate check completed",
    }

# ==========================================
# PHASE 3: Reviewer Workflow & State Machine
# ==========================================
ALLOWED_STATES = {
    "Submitted",
    "Supplemented",
    "Approved",
    "Rejected",
    "Canceled",
    "Promoted from Waitlist",
}

ALLOWED_TRANSITIONS = {
    "Submitted": {"Supplemented", "Approved", "Rejected", "Canceled"},
    "Supplemented": {"Approved", "Rejected", "Canceled", "Promoted from Waitlist"},
    "Approved": set(),
    "Rejected": set(),
    "Canceled": set(),
    "Promoted from Waitlist": {"Approved", "Rejected", "Canceled"},
}

def _mask_id_number(value: str | None, current_user: models.User):
    if not value:
        return None
    if current_user.role == models.RoleEnum.SystemAdmin:
        return value
    if len(value) <= 4:
        return value
    return "*" * (len(value) - 4) + value[-4:]

def _log_review_action(
    db: Session,
    form_id: int,
    actor_id: int,
    action: str,
    from_state: str | None = None,
    to_state: str | None = None,
    comment: str | None = None,
):
    record = models.ReviewWorkflowRecord(
        registration_form_id=form_id,
        actor_user_id=actor_id,
        action=action,
        from_state=from_state,
        to_state=to_state,
        comment=comment,
    )
    db.add(record)
    logger.info(
        "review_action form_id=%s actor_id=%s action=%s from_state=%s to_state=%s",
        form_id,
        actor_id,
        action,
        from_state,
        to_state,
    )

def _transition_form_state(form: models.RegistrationForm, target_state: str):
    if target_state not in ALLOWED_STATES:
        raise HTTPException(status_code=400, detail="Invalid target state")
    has_submitted_material = any(item.status == "Submitted" for item in form.checklists)
    current_state = form.status or "Submitted"
    # Treat stale drafts with submitted materials as Submitted.
    if current_state == "Draft" and has_submitted_material:
        current_state = "Submitted"
        form.status = "Submitted"
    if target_state not in ALLOWED_TRANSITIONS.get(current_state, set()):
        raise HTTPException(status_code=400, detail=f"Illegal transition from {current_state} to {target_state}")
    form.status = target_state
    return current_state

@app.get("/reviewer/applications")
def reviewer_list_applications(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.RoleChecker([models.RoleEnum.Reviewer, models.RoleEnum.SystemAdmin])),
):
    # Backfill old drafts that already have reviewer-relevant checklist statuses.
    all_forms = db.query(models.RegistrationForm).all()
    for form in all_forms:
        has_reviewer_work = any(item.status in ["Submitted", "Needs Correction"] for item in form.checklists)
        if form.status == "Draft" and has_reviewer_work:
            form.status = "Submitted"
    db.commit()

    forms = []
    for form in db.query(models.RegistrationForm).all():
        if form.status in ["Submitted", "Supplemented"]:
            forms.append(form)
            continue
        if any(item.status in ["Submitted", "Needs Correction"] for item in form.checklists):
            forms.append(form)
    result = []
    for form in forms:
        result.append(
            {
                "id": form.id,
                "status": form.status,
                "created_at": form.created_at,
                "deadline": form.deadline,
                "applicant": {
                    "id": form.user.id,
                    "username": form.user.username,
                    "id_number": _mask_id_number(form.user.id_number, current_user),
                },
                "checklists": form.checklists,
            }
        )
    return result

@app.get("/reviewer/applications/{form_id}")
def reviewer_application_detail(
    form_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.RoleChecker([models.RoleEnum.Reviewer, models.RoleEnum.SystemAdmin])),
):
    form = db.query(models.RegistrationForm).filter(models.RegistrationForm.id == form_id).first()
    if not form:
        raise HTTPException(status_code=404, detail="Application not found")
    return {
        "id": form.id,
        "status": form.status,
        "created_at": form.created_at,
        "deadline": form.deadline,
        "applicant": {
            "id": form.user.id,
            "username": form.user.username,
            "id_number": _mask_id_number(form.user.id_number, current_user),
        },
        "checklists": form.checklists,
    }

@app.post("/reviewer/applications/{form_id}/transition")
def reviewer_transition_application(
    form_id: int,
    payload: schemas.TransitionRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.RoleChecker([models.RoleEnum.Reviewer, models.RoleEnum.SystemAdmin])),
):
    form = db.query(models.RegistrationForm).filter(models.RegistrationForm.id == form_id).first()
    if not form:
        raise HTTPException(status_code=404, detail="Application not found")
    from_state = _transition_form_state(form, payload.target_state)
    _log_review_action(
        db=db,
        form_id=form.id,
        actor_id=current_user.id,
        action="TRANSITION",
        from_state=from_state,
        to_state=payload.target_state,
        comment=payload.comment,
    )
    db.commit()
    logger.info("review_transition form_id=%s by_user=%s target_state=%s", form.id, current_user.id, payload.target_state)
    return {"id": form.id, "status": form.status}

@app.post("/reviewer/checklists/{checklist_id}/needs-correction")
def reviewer_mark_needs_correction(
    checklist_id: int,
    payload: schemas.NeedsCorrectionRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.RoleChecker([models.RoleEnum.Reviewer, models.RoleEnum.SystemAdmin])),
):
    checklist = db.query(models.MaterialChecklist).filter(models.MaterialChecklist.id == checklist_id).first()
    if not checklist:
        raise HTTPException(status_code=404, detail="Checklist not found")
    if checklist.supplement_used or checklist.supplement_started_at:
        raise HTTPException(status_code=400, detail="One-time supplementary window already consumed/opened")
    now = datetime.utcnow()
    checklist.status = "Needs Correction"
    checklist.supplement_started_at = now
    checklist.supplement_expires_at = now + timedelta(hours=72)
    checklist.correction_deadline = checklist.supplement_expires_at
    checklist.registration_form.status = "Supplemented"
    _log_review_action(
        db=db,
        form_id=checklist.registration_form_id,
        actor_id=current_user.id,
        action="COMMENT",
        comment=f"Needs Correction opened for checklist {checklist_id}: {payload.comment.strip()}",
    )
    db.commit()
    logger.info(
        "needs_correction_opened checklist_id=%s by_user=%s expires_at=%s",
        checklist_id,
        current_user.id,
        checklist.supplement_expires_at.isoformat(),
    )
    return {"checklist_id": checklist.id, "status": checklist.status, "supplement_expires_at": checklist.supplement_expires_at}

@app.post("/reviewer/applications/batch-transition")
def reviewer_batch_transition(
    payload: schemas.BatchTransitionRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.RoleChecker([models.RoleEnum.Reviewer, models.RoleEnum.SystemAdmin])),
):
    if len(payload.form_ids) == 0:
        raise HTTPException(status_code=400, detail="No application ids provided")
    if len(payload.form_ids) > 50:
        raise HTTPException(status_code=400, detail="Batch review limit is 50 applications")
    updated = []
    forms = db.query(models.RegistrationForm).filter(models.RegistrationForm.id.in_(payload.form_ids)).all()
    for form in forms:
        from_state = _transition_form_state(form, payload.target_state)
        _log_review_action(
            db=db,
            form_id=form.id,
            actor_id=current_user.id,
            action="TRANSITION",
            from_state=from_state,
            to_state=payload.target_state,
            comment=payload.comment,
        )
        updated.append(form.id)
    db.commit()
    return {"updated_count": len(updated), "updated_ids": updated}

@app.post("/reviewer/applications/{form_id}/comments")
def reviewer_add_comment(
    form_id: int,
    payload: schemas.ReviewCommentRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.RoleChecker([models.RoleEnum.Reviewer, models.RoleEnum.SystemAdmin])),
):
    form = db.query(models.RegistrationForm).filter(models.RegistrationForm.id == form_id).first()
    if not form:
        raise HTTPException(status_code=404, detail="Application not found")
    _log_review_action(
        db=db,
        form_id=form.id,
        actor_id=current_user.id,
        action="COMMENT",
        comment=payload.comment.strip(),
    )
    db.commit()
    return {"detail": "Comment added"}

@app.get("/reviewer/applications/{form_id}/audit-trail", response_model=list[schemas.AuditRecordResponse])
def reviewer_audit_trail(
    form_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.RoleChecker([models.RoleEnum.Reviewer, models.RoleEnum.SystemAdmin])),
):
    form = db.query(models.RegistrationForm).filter(models.RegistrationForm.id == form_id).first()
    if not form:
        raise HTTPException(status_code=404, detail="Application not found")
    return (
        db.query(models.ReviewWorkflowRecord)
        .filter(models.ReviewWorkflowRecord.registration_form_id == form_id)
        .order_by(models.ReviewWorkflowRecord.created_at.desc())
        .all()
    )

# ==========================================
# PHASE 4: Financial Dashboard & Alerts
# ==========================================
@app.post("/financial/accounts", response_model=schemas.FundingAccountResponse)
def create_funding_account(
    payload: schemas.FundingAccountCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.RoleChecker([models.RoleEnum.FinancialAdmin, models.RoleEnum.SystemAdmin])),
):
    form = db.query(models.RegistrationForm).filter(models.RegistrationForm.id == payload.registration_form_id).first()
    if not form:
        raise HTTPException(status_code=404, detail="Registration form not found")
    existing = db.query(models.FundingAccount).filter(models.FundingAccount.registration_form_id == payload.registration_form_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Funding account already exists for this application")
    owner_id = None if current_user.role == models.RoleEnum.SystemAdmin else current_user.id
    account = models.FundingAccount(
        registration_form_id=payload.registration_form_id,
        total_budget=payload.total_budget,
        financial_admin_user_id=owner_id,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return account

@app.get("/financial/accounts", response_model=list[schemas.FundingAccountResponse])
def list_funding_accounts(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.RoleChecker([models.RoleEnum.FinancialAdmin, models.RoleEnum.SystemAdmin])),
):
    q = db.query(models.FundingAccount)
    if current_user.role == models.RoleEnum.FinancialAdmin:
        q = q.filter(models.FundingAccount.financial_admin_user_id == current_user.id)
    return q.order_by(models.FundingAccount.id.desc()).all()

@app.post("/financial/transactions", response_model=schemas.TransactionResponse)
async def create_transaction(
    funding_account_id: int = Form(...),
    transaction_type: str = Form(...),  # income | expense
    category: str = Form(...),
    amount: int = Form(...),
    note: str = Form(None),
    override_budget_warning: bool = Form(False),
    invoice: UploadFile = File(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.RoleChecker([models.RoleEnum.FinancialAdmin, models.RoleEnum.SystemAdmin])),
):
    if transaction_type not in ["income", "expense"]:
        raise HTTPException(status_code=400, detail="transaction_type must be income or expense")
    if amount <= 0:
        raise HTTPException(status_code=400, detail="amount must be greater than zero")

    account = db.query(models.FundingAccount).filter(models.FundingAccount.id == funding_account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Funding account not found")
    if not _financial_admin_may_access_account(account, current_user):
        raise HTTPException(status_code=403, detail="Not allowed to access this funding account")

    # 10% budget warning rule for expense
    if transaction_type == "expense":
        current_expenses = (
            db.query(func.coalesce(func.sum(models.TransactionRecord.amount), 0))
            .filter(
                models.TransactionRecord.funding_account_id == funding_account_id,
                models.TransactionRecord.transaction_type == "expense",
            )
            .scalar()
        )
        projected_ratio = (current_expenses + amount) / account.total_budget if account.total_budget > 0 else 999
        if projected_ratio > 1.1 and not override_budget_warning:
            logger.warning(
                "budget_warning funding_account_id=%s amount=%s projected_ratio=%s by_user=%s",
                funding_account_id,
                amount,
                projected_ratio,
                current_user.id,
            )
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "BUDGET_WARNING",
                    "message": "Expense exceeds budget by more than 10%. Confirmation required.",
                    "projected_ratio": projected_ratio,
                },
            )

    invoice_path = None
    if invoice:
        ext = os.path.splitext(invoice.filename)[1].lower()
        if ext not in [".pdf", ".jpg", ".jpeg", ".png"]:
            raise HTTPException(status_code=400, detail="Invoice must be PDF/JPG/PNG")
        content = await invoice.read()
        upload_dir = "/app/uploads/invoices"
        os.makedirs(upload_dir, exist_ok=True)
        safe_name = f"inv_{funding_account_id}_{int(datetime.utcnow().timestamp())}{ext}"
        invoice_path = os.path.join(upload_dir, safe_name)
        with open(invoice_path, "wb") as f:
            f.write(content)

    tx = models.TransactionRecord(
        funding_account_id=funding_account_id,
        transaction_type=transaction_type,
        category=category,
        amount=amount,
        note=note,
        invoice_path=invoice_path,
        created_by_user_id=current_user.id,
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)
    return tx

@app.get("/financial/transactions", response_model=list[schemas.TransactionResponse])
def list_transactions(
    funding_account_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.RoleChecker([models.RoleEnum.FinancialAdmin, models.RoleEnum.SystemAdmin])),
):
    account = db.query(models.FundingAccount).filter(models.FundingAccount.id == funding_account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Funding account not found")
    if not _financial_admin_may_access_account(account, current_user):
        raise HTTPException(status_code=403, detail="Not allowed to access this funding account")
    return (
        db.query(models.TransactionRecord)
        .filter(models.TransactionRecord.funding_account_id == funding_account_id)
        .order_by(models.TransactionRecord.created_at.desc())
        .all()
    )

@app.get("/financial/aggregates/by-category", response_model=list[schemas.FinancialAggregateItem])
def aggregate_by_category(
    funding_account_id: int,
    transaction_type: str = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.RoleChecker([models.RoleEnum.FinancialAdmin, models.RoleEnum.SystemAdmin])),
):
    account = db.query(models.FundingAccount).filter(models.FundingAccount.id == funding_account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Funding account not found")
    if not _financial_admin_may_access_account(account, current_user):
        raise HTTPException(status_code=403, detail="Not allowed to access this funding account")
    query = (
        db.query(models.TransactionRecord.category, func.sum(models.TransactionRecord.amount))
        .filter(models.TransactionRecord.funding_account_id == funding_account_id)
    )
    if transaction_type:
        query = query.filter(models.TransactionRecord.transaction_type == transaction_type)
    rows = query.group_by(models.TransactionRecord.category).all()
    return [{"dimension": category, "total_amount": int(total or 0)} for category, total in rows]

@app.get("/financial/aggregates/by-month", response_model=list[schemas.FinancialAggregateItem])
def aggregate_by_month(
    funding_account_id: int,
    transaction_type: str = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.RoleChecker([models.RoleEnum.FinancialAdmin, models.RoleEnum.SystemAdmin])),
):
    account = db.query(models.FundingAccount).filter(models.FundingAccount.id == funding_account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Funding account not found")
    if not _financial_admin_may_access_account(account, current_user):
        raise HTTPException(status_code=403, detail="Not allowed to access this funding account")
    month_expr = func.to_char(models.TransactionRecord.created_at, "YYYY-MM")
    query = (
        db.query(month_expr, func.sum(models.TransactionRecord.amount))
        .filter(models.TransactionRecord.funding_account_id == funding_account_id)
    )
    if transaction_type:
        query = query.filter(models.TransactionRecord.transaction_type == transaction_type)
    rows = query.group_by(month_expr).all()
    return [{"dimension": month, "total_amount": int(total or 0)} for month, total in rows]

# ==========================================
# SYSTEM ADMIN: User & Role Management
# ==========================================
@app.get("/admin/users", response_model=list[schemas.UserManagementResponse])
def list_users_for_admin(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.RoleChecker([models.RoleEnum.SystemAdmin])),
):
    return db.query(models.User).order_by(models.User.id.asc()).all()

@app.put("/admin/users/{user_id}", response_model=schemas.UserManagementResponse)
def update_user_for_admin(
    user_id: int,
    payload: schemas.UserManagementUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.RoleChecker([models.RoleEnum.SystemAdmin])),
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == current_user.id and payload.role != models.RoleEnum.SystemAdmin:
        raise HTTPException(status_code=400, detail="SystemAdmin cannot remove own SystemAdmin role")
    duplicate = db.query(models.User).filter(models.User.username == payload.username, models.User.id != user_id).first()
    if duplicate:
        raise HTTPException(status_code=400, detail="Username already exists")
    user.username = payload.username
    user.role = payload.role
    db.commit()
    db.refresh(user)
    return user

@app.post("/admin/users/{user_id}/block", response_model=schemas.UserManagementResponse)
def block_user_for_admin(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.RoleChecker([models.RoleEnum.SystemAdmin])),
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="SystemAdmin cannot block own account")
    user.is_blocked = 1
    db.commit()
    db.refresh(user)
    return user

@app.post("/admin/users/{user_id}/unblock", response_model=schemas.UserManagementResponse)
def unblock_user_for_admin(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.RoleChecker([models.RoleEnum.SystemAdmin])),
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_blocked = 0
    db.commit()
    db.refresh(user)
    return user

# ==========================================
# PHASE 5: System Admin & Operations
# ==========================================
DEFAULT_THRESHOLDS = {
    "approval_rate": 80,
    "correction_rate": 30,
    "overspending_rate": 10,
    "quality_failure_rate": 20,
}

# Higher approval_rate is better; other listed metrics breach when above threshold.
_METRICS_BREACH_WHEN_BELOW_THRESHOLD = frozenset({"approval_rate"})


def _metric_breaches_threshold(metric_name: str, metric_value: int, threshold: int) -> bool:
    if metric_name in _METRICS_BREACH_WHEN_BELOW_THRESHOLD:
        return metric_value < threshold
    return metric_value > threshold


def _metric_alert_message(metric_name: str, metric_value: int, threshold: int) -> str:
    if metric_name in _METRICS_BREACH_WHEN_BELOW_THRESHOLD:
        return f"{metric_name} below threshold ({metric_value} < {threshold})"
    return f"{metric_name} exceeded threshold ({metric_value} > {threshold})"

def _whitelist_fernet_key_bytes(raw: str) -> bytes:
    """Fernet expects url-safe base64 of 32 bytes; accept that or derive from any non-empty secret."""
    s = raw.strip()
    if not s:
        raise HTTPException(status_code=500, detail="WHITELIST_ENCRYPTION_KEY is not configured")
    kb = s.encode("utf-8")
    pad = b"=" * (-len(kb) % 4)
    try:
        if len(base64.urlsafe_b64decode(kb + pad)) == 32:
            return kb
    except Exception:
        pass
    return base64.urlsafe_b64encode(hashlib.sha256(s.encode("utf-8")).digest())


def _get_fernet():
    key = os.getenv("WHITELIST_ENCRYPTION_KEY", "")
    return Fernet(_whitelist_fernet_key_bytes(key))

def _ensure_thresholds(db: Session):
    for metric_name, threshold_value in DEFAULT_THRESHOLDS.items():
        existing = db.query(models.MetricThreshold).filter(models.MetricThreshold.metric_name == metric_name).first()
        if not existing:
            db.add(models.MetricThreshold(metric_name=metric_name, threshold_value=threshold_value))
    db.commit()

def _calculate_metrics(db: Session):
    total_forms = db.query(models.RegistrationForm).count()
    approved_count = db.query(models.RegistrationForm).filter(models.RegistrationForm.status == "Approved").count()
    supplemented_count = db.query(models.RegistrationForm).filter(models.RegistrationForm.status == "Supplemented").count()

    account_ids = [a.id for a in db.query(models.FundingAccount.id).all()]
    overspending_count = 0
    if account_ids:
        accounts = db.query(models.FundingAccount).all()
        for account in accounts:
            expenses = (
                db.query(func.coalesce(func.sum(models.TransactionRecord.amount), 0))
                .filter(
                    models.TransactionRecord.funding_account_id == account.id,
                    models.TransactionRecord.transaction_type == "expense",
                )
                .scalar()
            )
            # Align with transaction rule: "overspend" means expenses > 110% of budget
            if account.total_budget > 0 and expenses > account.total_budget * 1.1:
                overspending_count += 1

    approval_rate = int((approved_count / total_forms) * 100) if total_forms else 0
    correction_rate = int((supplemented_count / total_forms) * 100) if total_forms else 0
    overspending_rate = int((overspending_count / len(account_ids)) * 100) if account_ids else 0
    total_quality_results = db.query(models.QualityValidationResult).count()
    failed_quality_results = db.query(models.QualityValidationResult).filter(models.QualityValidationResult.result_status == "Failed").count()
    quality_failure_rate = int((failed_quality_results / total_quality_results) * 100) if total_quality_results else 0
    return [
        {"metric_name": "approval_rate", "metric_value": approval_rate},
        {"metric_name": "correction_rate", "metric_value": correction_rate},
        {"metric_name": "overspending_rate", "metric_value": overspending_rate},
        {"metric_name": "quality_failure_rate", "metric_value": quality_failure_rate},
    ]

@app.post("/admin/metrics/calculate", response_model=list[schemas.MetricItem])
def calculate_metrics_and_alerts(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.RoleChecker([models.RoleEnum.SystemAdmin])),
):
    _ensure_thresholds(db)
    metrics = _calculate_metrics(db)
    threshold_map = {t.metric_name: t.threshold_value for t in db.query(models.MetricThreshold).all()}
    for item in metrics:
        threshold = threshold_map.get(item["metric_name"], 100)
        mv = item["metric_value"]
        mn = item["metric_name"]
        if _metric_breaches_threshold(mn, mv, threshold):
            db.add(
                models.AlertRecord(
                    metric_name=mn,
                    metric_value=mv,
                    threshold_value=threshold,
                    message=_metric_alert_message(mn, mv, threshold),
                )
            )
    db.commit()
    return metrics

@app.get("/admin/metrics", response_model=list[schemas.MetricItem])
def get_metrics(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.RoleChecker([models.RoleEnum.SystemAdmin])),
):
    return _calculate_metrics(db)

@app.get("/admin/thresholds")
def get_thresholds(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.RoleChecker([models.RoleEnum.SystemAdmin])),
):
    _ensure_thresholds(db)
    rows = db.query(models.MetricThreshold).order_by(models.MetricThreshold.metric_name.asc()).all()
    return [{"metric_name": r.metric_name, "threshold_value": r.threshold_value} for r in rows]

@app.post("/admin/thresholds")
def upsert_threshold(
    payload: schemas.MetricThresholdUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.RoleChecker([models.RoleEnum.SystemAdmin])),
):
    row = db.query(models.MetricThreshold).filter(models.MetricThreshold.metric_name == payload.metric_name).first()
    if not row:
        row = models.MetricThreshold(metric_name=payload.metric_name, threshold_value=payload.threshold_value)
        db.add(row)
    else:
        row.threshold_value = payload.threshold_value
        row.updated_at = datetime.utcnow()
    db.commit()
    return {"metric_name": row.metric_name, "threshold_value": row.threshold_value}

@app.get("/admin/alerts", response_model=list[schemas.AlertRecordResponse])
def list_alerts(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.RoleChecker([models.RoleEnum.SystemAdmin])),
):
    return db.query(models.AlertRecord).order_by(models.AlertRecord.created_at.desc()).all()

@app.post("/admin/whitelist", response_model=schemas.WhitelistPolicyResponse)
def create_or_update_whitelist_policy(
    payload: schemas.WhitelistPolicyCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.RoleChecker([models.RoleEnum.SystemAdmin])),
):
    f = _get_fernet()
    encrypted_payload = f.encrypt(payload.payload.encode("utf-8")).decode("utf-8")
    row = db.query(models.WhitelistPolicy).filter(models.WhitelistPolicy.policy_name == payload.policy_name).first()
    if not row:
        row = models.WhitelistPolicy(policy_name=payload.policy_name, encrypted_payload=encrypted_payload)
        db.add(row)
    else:
        row.encrypted_payload = encrypted_payload
        row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return {
        "id": row.id,
        "policy_name": row.policy_name,
        "payload": payload.payload,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }

@app.get("/admin/whitelist", response_model=list[schemas.WhitelistPolicyResponse])
def list_whitelist_policies(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.RoleChecker([models.RoleEnum.SystemAdmin])),
):
    f = _get_fernet()
    rows = db.query(models.WhitelistPolicy).order_by(models.WhitelistPolicy.policy_name.asc()).all()
    result = []
    for row in rows:
        decrypted = f.decrypt(row.encrypted_payload.encode("utf-8")).decode("utf-8")
        result.append(
            {
                "id": row.id,
                "policy_name": row.policy_name,
                "payload": decrypted,
                "created_at": row.created_at,
                "updated_at": row.updated_at,
            }
        )
    return result

@app.post("/admin/backup")
def trigger_backup(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.RoleChecker([models.RoleEnum.SystemAdmin])),
):
    script_path = "/app/scripts/daily_backup.sh"
    if not os.path.exists(script_path):
        raise HTTPException(status_code=404, detail="Backup script not found")
    process = subprocess.run(["bash", script_path], capture_output=True, text=True)
    if process.returncode != 0:
        logger.error("backup_failed stderr=%s", process.stderr.strip())
        raise HTTPException(status_code=500, detail=f"Backup failed: {process.stderr.strip()}")
    logger.info("backup_completed output=%s", process.stdout.strip())
    return {"detail": "Backup completed", "output": process.stdout.strip()}

@app.post("/admin/recovery")
def one_click_recovery(
    file_name: str = Form(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.RoleChecker([models.RoleEnum.SystemAdmin])),
):
    backup_dir = "/app/backups"
    safe_name = os.path.basename(file_name)
    if not safe_name or safe_name in (".", "..") or file_name != safe_name:
        raise HTTPException(status_code=400, detail="Invalid backup file name")
    file_path = os.path.realpath(os.path.join(backup_dir, safe_name))
    backup_real = os.path.realpath(backup_dir)
    try:
        if os.path.commonpath([file_path, backup_real]) != backup_real:
            raise HTTPException(status_code=400, detail="Invalid backup file path")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid backup file path")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Backup file not found")
    db_url = os.getenv("DATABASE_URL", "")
    if not db_url.startswith("postgresql://"):
        raise HTTPException(status_code=500, detail="DATABASE_URL is missing or invalid")
    # postgresql://user:pass@host:port/db
    parsed = db_url.replace("postgresql://", "")
    creds, host_db = parsed.split("@", 1)
    user, pwd = creds.split(":", 1)
    host_port, db_name = host_db.rsplit("/", 1)
    if ":" in host_port:
        host, port = host_port.split(":", 1)
    else:
        host, port = host_port, "5432"
    env = os.environ.copy()
    env["PGPASSWORD"] = pwd
    cmd = ["psql", "-h", host, "-p", port, "-U", user, "-d", db_name, "-f", file_path]
    process = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if process.returncode != 0:
        logger.error("recovery_failed file=%s stderr=%s", safe_name, process.stderr.strip())
        raise HTTPException(status_code=500, detail=f"Recovery failed: {process.stderr.strip()}")
    logger.info("recovery_completed file=%s", safe_name)
    return {"detail": "Recovery completed"}

def _stream_csv(filename: str, headers: list[str], rows: list[list[str]]):
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(row)
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}.csv"},
    )

@app.get("/admin/exports/reconciliation")
def export_reconciliation(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.RoleChecker([models.RoleEnum.SystemAdmin])),
):
    rows = db.query(models.TransactionRecord).order_by(models.TransactionRecord.created_at.desc()).all()
    data = [[r.id, r.funding_account_id, r.transaction_type, r.category, r.amount, r.created_at.isoformat()] for r in rows]
    return _stream_csv("reconciliation", ["id", "funding_account_id", "transaction_type", "category", "amount", "created_at"], data)

@app.get("/admin/exports/audit")
def export_audit_logs(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.RoleChecker([models.RoleEnum.SystemAdmin])),
):
    rows = db.query(models.ReviewWorkflowRecord).order_by(models.ReviewWorkflowRecord.created_at.desc()).all()
    data = [[r.id, r.registration_form_id, r.actor_user_id, r.action, r.from_state, r.to_state, r.comment, r.created_at.isoformat()] for r in rows]
    return _stream_csv("audit_logs", ["id", "registration_form_id", "actor_user_id", "action", "from_state", "to_state", "comment", "created_at"], data)

@app.get("/admin/exports/compliance")
def export_compliance_report(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.RoleChecker([models.RoleEnum.SystemAdmin])),
):
    rows = db.query(models.User).order_by(models.User.id.asc()).all()
    data = [[u.id, u.username, u.role.value, u.is_blocked] for u in rows]
    return _stream_csv("compliance_report", ["id", "username", "role", "is_blocked"], data)


@app.get("/admin/exports/whitelist")
def export_whitelist_policies_csv(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.RoleChecker([models.RoleEnum.SystemAdmin])),
):
    f = _get_fernet()
    rows = db.query(models.WhitelistPolicy).order_by(models.WhitelistPolicy.policy_name.asc()).all()
    data = []
    for row in rows:
        decrypted = f.decrypt(row.encrypted_payload.encode("utf-8")).decode("utf-8")
        data.append([row.id, row.policy_name, decrypted, row.created_at.isoformat(), row.updated_at.isoformat()])
    return _stream_csv(
        "whitelist_policies",
        ["id", "policy_name", "payload", "created_at", "updated_at"],
        data,
    )


@app.get("/admin/exports/access-audit")
def export_access_audit_csv(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.RoleChecker([models.RoleEnum.SystemAdmin])),
):
    rows = db.query(models.ApiAccessAuditLog).order_by(models.ApiAccessAuditLog.created_at.desc()).limit(50000).all()
    data = [
        [r.id, r.user_id or "", r.method, r.path, r.status_code, r.created_at.isoformat()]
        for r in rows
    ]
    return _stream_csv("access_audit", ["id", "user_id", "method", "path", "status_code", "created_at"], data)


@app.post("/admin/data-collection/batches", response_model=schemas.DataCollectionBatchResponse)
def create_data_collection_batch(
    payload: schemas.DataCollectionBatchCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.RoleChecker([models.RoleEnum.SystemAdmin])),
):
    existing = db.query(models.DataCollectionBatch).filter(models.DataCollectionBatch.batch_name == payload.batch_name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Batch name already exists")
    row = models.DataCollectionBatch(
        batch_name=payload.batch_name,
        status=payload.status,
        created_by_user_id=current_user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row

@app.get("/admin/data-collection/batches", response_model=list[schemas.DataCollectionBatchResponse])
def list_data_collection_batches(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.RoleChecker([models.RoleEnum.SystemAdmin])),
):
    return db.query(models.DataCollectionBatch).order_by(models.DataCollectionBatch.created_at.desc()).all()

@app.post("/admin/quality-validation/results", response_model=schemas.QualityValidationResultResponse)
def create_quality_validation_result(
    payload: schemas.QualityValidationResultCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.RoleChecker([models.RoleEnum.SystemAdmin])),
):
    batch = db.query(models.DataCollectionBatch).filter(models.DataCollectionBatch.id == payload.batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    form = db.query(models.RegistrationForm).filter(models.RegistrationForm.id == payload.registration_form_id).first()
    if not form:
        raise HTTPException(status_code=404, detail="Registration form not found")
    row = models.QualityValidationResult(
        batch_id=payload.batch_id,
        registration_form_id=payload.registration_form_id,
        score=payload.score,
        result_status=payload.result_status,
        notes=payload.notes,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row

@app.get("/admin/quality-validation/results", response_model=list[schemas.QualityValidationResultResponse])
def list_quality_validation_results(
    batch_id: int = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.RoleChecker([models.RoleEnum.SystemAdmin])),
):
    query = db.query(models.QualityValidationResult)
    if batch_id:
        query = query.filter(models.QualityValidationResult.batch_id == batch_id)
    return query.order_by(models.QualityValidationResult.created_at.desc()).all()
