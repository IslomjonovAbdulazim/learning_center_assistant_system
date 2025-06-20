from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
import hashlib
import secrets
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session
from .database import get_db
from .models import User
import os
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here-change-this-in-production")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

security = HTTPBearer()


def verify_password(plain_password, hashed_password):
    """Verify a password against its hash using simple SHA256 + salt"""
    try:
        # Split the stored hash to get salt and hash
        stored_salt, stored_hash = hashed_password.split(':')
        # Hash the provided password with the same salt
        password_hash = hashlib.sha256((plain_password + stored_salt).encode()).hexdigest()
        return password_hash == stored_hash
    except:
        return False


def get_password_hash(password):
    """Hash a password using SHA256 + random salt"""
    # Generate a random salt
    salt = secrets.token_hex(16)
    # Hash password with salt
    password_hash = hashlib.sha256((password + salt).encode()).hexdigest()
    # Return salt:hash format
    return f"{salt}:{password_hash}"


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def authenticate_user(db: Session, phone: str, password: str, learning_center_id: Optional[int] = None):
    if learning_center_id is None:  # Admin login
        user = db.query(User).filter(User.phone == phone, User.role == "admin").first()
    else:
        user = db.query(User).filter(
            User.phone == phone,
            User.learning_center_id == learning_center_id
        ).first()

    if not user:
        return False
    if not verify_password(password, user.password):
        return False
    return user


def get_current_user(token: str = Depends(security), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Kirish uchun qayta tizimga kiring",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception
    return user


def require_role(allowed_roles: list):
    def role_checker(current_user: User = Depends(get_current_user)):
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bu amalni bajarish uchun ruxsatingiz yo'q"
            )
        return current_user

    return role_checker