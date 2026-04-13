from sqlalchemy import Column, Integer, String, Enum, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from database import Base
import enum
from datetime import datetime

class RoleEnum(str, enum.Enum):
    Applicant = "Applicant"
    Reviewer = "Reviewer"
    FinancialAdmin = "FinancialAdmin"
    SystemAdmin = "SystemAdmin"

class RegistrationForm(Base):
    __tablename__ = "registration_forms"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    status = Column(String, default="Draft")
    created_at = Column(DateTime, default=datetime.utcnow)
    deadline = Column(DateTime, nullable=True) # Overall deadline
    
    user = relationship("User")
    checklists = relationship("MaterialChecklist", back_populates="registration_form")

class MaterialChecklist(Base):
    __tablename__ = "material_checklists"
    id = Column(Integer, primary_key=True, index=True)
    registration_form_id = Column(Integer, ForeignKey("registration_forms.id"))
    item_name = Column(String, nullable=False) # e.g. "Passport Copy", "Business Plan"
    status = Column(String, default="Pending Submission") # Pending Submission, Submitted, Needs Correction
    correction_deadline = Column(DateTime, nullable=True) # Set when Needs Correction
    correction_reason = Column(String, nullable=True) # Supplied by applicant
    supplement_used = Column(Integer, default=0, nullable=False)  # one-time supplementary window usage
    supplement_started_at = Column(DateTime, nullable=True)
    supplement_expires_at = Column(DateTime, nullable=True)
    
    registration_form = relationship("RegistrationForm", back_populates="checklists")
    versions = relationship("MaterialVersion", back_populates="checklist", cascade="all, delete-orphan")

class MaterialVersion(Base):
    __tablename__ = "material_versions"
    id = Column(Integer, primary_key=True, index=True)
    checklist_id = Column(Integer, ForeignKey("material_checklists.id"))
    file_path = Column(String, nullable=False)
    file_name = Column(String, nullable=False)
    file_hash = Column(String, nullable=False) # SHA-256 fingerprint
    file_size = Column(Integer, default=0) # File size in bytes
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    
    checklist = relationship("MaterialChecklist", back_populates="versions")

class ReviewWorkflowRecord(Base):
    __tablename__ = "review_workflow_records"
    id = Column(Integer, primary_key=True, index=True)
    registration_form_id = Column(Integer, ForeignKey("registration_forms.id"), nullable=False)
    actor_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action = Column(String, nullable=False)  # TRANSITION | COMMENT
    from_state = Column(String, nullable=True)
    to_state = Column(String, nullable=True)
    comment = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    registration_form = relationship("RegistrationForm")
    actor = relationship("User")

class FundingAccount(Base):
    __tablename__ = "funding_accounts"
    id = Column(Integer, primary_key=True, index=True)
    registration_form_id = Column(Integer, ForeignKey("registration_forms.id"), nullable=False)
    total_budget = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    # FinancialAdmin who owns this account; NULL = system-admin-managed only (no FinancialAdmin access)
    financial_admin_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    registration_form = relationship("RegistrationForm")
    transactions = relationship("TransactionRecord", back_populates="funding_account", cascade="all, delete-orphan")

class TransactionRecord(Base):
    __tablename__ = "transaction_records"
    id = Column(Integer, primary_key=True, index=True)
    funding_account_id = Column(Integer, ForeignKey("funding_accounts.id"), nullable=False)
    transaction_type = Column(String, nullable=False)  # income | expense
    category = Column(String, nullable=False)
    amount = Column(Integer, nullable=False)
    note = Column(String, nullable=True)
    invoice_path = Column(String, nullable=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    funding_account = relationship("FundingAccount", back_populates="transactions")
    created_by = relationship("User")

class MetricThreshold(Base):
    __tablename__ = "metric_thresholds"
    id = Column(Integer, primary_key=True, index=True)
    metric_name = Column(String, unique=True, nullable=False)  # approval_rate | correction_rate | overspending_rate
    threshold_value = Column(Integer, nullable=False, default=80)  # integer percentage (0-100)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)

class AlertRecord(Base):
    __tablename__ = "alert_records"
    id = Column(Integer, primary_key=True, index=True)
    metric_name = Column(String, nullable=False)
    metric_value = Column(Integer, nullable=False)  # integer percentage
    threshold_value = Column(Integer, nullable=False)
    message = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

class WhitelistPolicy(Base):
    __tablename__ = "whitelist_policies"
    id = Column(Integer, primary_key=True, index=True)
    policy_name = Column(String, unique=True, nullable=False)
    encrypted_payload = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)

class DataCollectionBatch(Base):
    __tablename__ = "data_collection_batches"
    id = Column(Integer, primary_key=True, index=True)
    batch_name = Column(String, unique=True, nullable=False)
    status = Column(String, nullable=False, default="Open")
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    created_by = relationship("User")
    validation_results = relationship("QualityValidationResult", back_populates="batch", cascade="all, delete-orphan")

class QualityValidationResult(Base):
    __tablename__ = "quality_validation_results"
    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(Integer, ForeignKey("data_collection_batches.id"), nullable=False)
    registration_form_id = Column(Integer, ForeignKey("registration_forms.id"), nullable=False)
    score = Column(Integer, nullable=False, default=0)
    result_status = Column(String, nullable=False, default="Pending")  # Pending | Passed | Failed
    notes = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    batch = relationship("DataCollectionBatch", back_populates="validation_results")
    registration_form = relationship("RegistrationForm")

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(Enum(RoleEnum), nullable=False)
    is_blocked = Column(Integer, default=0, nullable=False)  # 0 = active, 1 = blocked
    locked_until = Column(DateTime, nullable=True)
    
    id_number = Column(String, nullable=True) # Sensitive field example

class LoginAttempt(Base):
    __tablename__ = "login_attempts"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, index=True, nullable=False)
    attempted_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class ApiAccessAuditLog(Base):
    __tablename__ = "api_access_audit_logs"
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    method = Column(String, nullable=False)
    path = Column(String, nullable=False)
    status_code = Column(Integer, nullable=False)
