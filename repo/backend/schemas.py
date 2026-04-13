from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime
from models import RoleEnum

class MaterialVersionResponse(BaseModel):
    id: int
    file_name: str
    file_size: int
    uploaded_at: datetime
    model_config = ConfigDict(from_attributes=True)

class MaterialChecklistResponse(BaseModel):
    id: int
    item_name: str
    status: str
    correction_deadline: Optional[datetime] = None
    correction_reason: Optional[str] = None
    supplement_used: int = 0
    supplement_started_at: Optional[datetime] = None
    supplement_expires_at: Optional[datetime] = None
    versions: List[MaterialVersionResponse] = []
    model_config = ConfigDict(from_attributes=True)

class RegistrationFormResponse(BaseModel):
    id: int
    status: str
    created_at: datetime
    deadline: Optional[datetime] = None
    checklists: List[MaterialChecklistResponse] = []
    model_config = ConfigDict(from_attributes=True)

class ReviewerApplicantInfo(BaseModel):
    id: int
    username: str
    id_number: Optional[str] = None

class ReviewerFormResponse(BaseModel):
    id: int
    status: str
    created_at: datetime
    deadline: Optional[datetime] = None
    applicant: ReviewerApplicantInfo
    checklists: List[MaterialChecklistResponse] = []

class TransitionRequest(BaseModel):
    target_state: str
    comment: Optional[str] = None

class BatchTransitionRequest(BaseModel):
    form_ids: List[int]
    target_state: str
    comment: Optional[str] = None

class ReviewCommentRequest(BaseModel):
    comment: str

class NeedsCorrectionRequest(BaseModel):
    comment: str

class AuditRecordResponse(BaseModel):
    id: int
    action: str
    from_state: Optional[str] = None
    to_state: Optional[str] = None
    comment: Optional[str] = None
    actor_user_id: int
    created_at: datetime

class FundingAccountCreate(BaseModel):
    registration_form_id: int
    total_budget: int

class FundingAccountResponse(BaseModel):
    id: int
    registration_form_id: int
    total_budget: int
    created_at: datetime
    financial_admin_user_id: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)

class TransactionResponse(BaseModel):
    id: int
    funding_account_id: int
    transaction_type: str
    category: str
    amount: int
    note: Optional[str] = None
    invoice_path: Optional[str] = None
    created_by_user_id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class FinancialAggregateItem(BaseModel):
    dimension: str
    total_amount: int

class UserManagementResponse(BaseModel):
    id: int
    username: str
    role: RoleEnum
    is_blocked: int
    model_config = ConfigDict(from_attributes=True)

class UserManagementUpdate(BaseModel):
    username: str
    role: RoleEnum

class MetricThresholdUpdate(BaseModel):
    metric_name: str
    threshold_value: int

class MetricItem(BaseModel):
    metric_name: str
    metric_value: int

class AlertRecordResponse(BaseModel):
    id: int
    metric_name: str
    metric_value: int
    threshold_value: int
    message: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class WhitelistPolicyCreate(BaseModel):
    policy_name: str
    payload: str

class WhitelistPolicyResponse(BaseModel):
    id: int
    policy_name: str
    payload: str
    created_at: datetime
    updated_at: datetime

class DuplicateCheckRequest(BaseModel):
    file_hash: str

class DuplicateCheckResponse(BaseModel):
    enabled: bool
    duplicate_found: bool
    matching_material_version_ids: List[int] = []
    message: str

class DataCollectionBatchCreate(BaseModel):
    batch_name: str
    status: str = "Open"

class DataCollectionBatchResponse(BaseModel):
    id: int
    batch_name: str
    status: str
    created_by_user_id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class QualityValidationResultCreate(BaseModel):
    batch_id: int
    registration_form_id: int
    score: int
    result_status: str
    notes: Optional[str] = None

class QualityValidationResultResponse(BaseModel):
    id: int
    batch_id: int
    registration_form_id: int
    score: int
    result_status: str
    notes: Optional[str] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class UserCreate(BaseModel):
    username: str
    password: str
    role: Optional[RoleEnum] = None  # Ignored on /register — always Applicant
    id_number: Optional[str] = None

class UserLogin(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    id: int
    username: str
    role: RoleEnum
    id_number: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None
    role: Optional[RoleEnum] = None
