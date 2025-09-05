from datetime import datetime, timedelta
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from database import get_db, AdminUser

# Configuration
SECRET_KEY = "your-secret-key-change-this-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440  # 24 hours

# Auth token for agents (simple token-based auth)
AGENT_TOKEN = "agent-secret-token-change-this-in-production"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

class AuthenticationError(HTTPException):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_admin_token(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise AuthenticationError()
    except JWTError:
        raise AuthenticationError()
    
    user = db.query(AdminUser).filter(AdminUser.username == username).first()
    if user is None or user.is_active is False:
        raise AuthenticationError()
    return user

def verify_agent_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if credentials.credentials != AGENT_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid agent token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return True