from datetime import datetime, timedelta, timezone
from typing import Optional, List
import os
from passlib.context import CryptContext
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from database import get_db
import models, schemas

SECRET_KEY = os.getenv("JWT_SECRET")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

def _bcrypt_safe_password(password: str) -> str:
    # bcrypt limit is 72 BYTES, not 72 characters.
    while len(password.encode("utf-8")) > 72:
        password = password[:-1]
    return password

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(_bcrypt_safe_password(plain_password), hashed_password)

def get_password_hash(password):
    return pwd_context.hash(_bcrypt_safe_password(password))

def check_login_attempts(username: str, db: Session):
    now = datetime.now(timezone.utc)
    user = db.query(models.User).filter(models.User.username == username).first()
    if user and user.locked_until and user.locked_until.replace(tzinfo=timezone.utc) > now:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Account locked until {user.locked_until.isoformat()}"
        )

def record_failed_attempt(username: str, db: Session):
    now = datetime.now(timezone.utc)
    db.add(models.LoginAttempt(username=username, attempted_at=now.replace(tzinfo=None)))
    db.commit()

    five_mins_ago = (now - timedelta(minutes=5)).replace(tzinfo=None)
    attempts = (
        db.query(models.LoginAttempt)
        .filter(models.LoginAttempt.username == username, models.LoginAttempt.attempted_at >= five_mins_ago)
        .count()
    )

    if attempts >= 10:
        user = db.query(models.User).filter(models.User.username == username).first()
        if user:
            user.locked_until = (now + timedelta(minutes=30)).replace(tzinfo=None)
            db.commit()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed attempts. Account locked for 30 minutes."
        )

def clear_login_attempts(username: str, db: Session):
    db.query(models.LoginAttempt).filter(models.LoginAttempt.username == username).delete()
    user = db.query(models.User).filter(models.User.username == username).first()
    if user and user.locked_until:
        user.locked_until = None
    db.commit()

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    if not SECRET_KEY:
        raise HTTPException(status_code=500, detail="JWT_SECRET is not configured")
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        role: str = payload.get("role")
        if username is None:
            raise credentials_exception
        token_data = schemas.TokenData(username=username, role=role)
    except JWTError:
        raise credentials_exception
    user = db.query(models.User).filter(models.User.username == token_data.username).first()
    if user is None:
        raise credentials_exception
    return user

class RoleChecker:
    def __init__(self, allowed_roles: List[models.RoleEnum]):
        self.allowed_roles = allowed_roles

    def __call__(self, user: models.User = Depends(get_current_user)):
        if user.role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Operation not permitted"
            )
        return user
