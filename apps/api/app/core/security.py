import secrets
import string
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
from passlib.context import CryptContext
from jose import jwt, JWTError
from fastapi import Request, Depends, status
from fastapi.security import OAuth2PasswordBearer

from app.config import settings
from app.core.errors import UnauthorizedError, ForbiddenError

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)

ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(subject: str, expires_delta: Optional[timedelta] = None) -> str:
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=7)
    
    payload = {
        "sub": str(subject),
        "exp": int(expire.timestamp()),
        "iat": int(datetime.now(timezone.utc).timestamp())
    }
    encoded_jwt = jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")
    return encoded_jwt

def decode_access_token(token: str) -> Dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
        return payload
    except JWTError as e:
        raise UnauthorizedError("Invalid authentication token")

def generate_user_code(name: str) -> str:
    """Generate NAME-XXXX universal user code."""
    first_name = name.strip().split()[0].upper() if name else "USER"
    # Keep up to 6 alpha characters
    clean_name = "".join(c for c in first_name if c.isalpha())[:6] or "USER"
    random_suffix = "".join(secrets.choice(ALPHABET) for _ in range(4))
    return f"{clean_name}-{random_suffix}"

async def get_current_user_id(request: Request) -> str:
    # 1. Try httpOnly cookie
    token = request.cookies.get("access_token")
    
    # 2. Try Authorization Bearer header
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1]
            
    if not token:
        raise UnauthorizedError("Authentication required")
        
    payload = decode_access_token(token)
    user_id = payload.get("sub")
    if not user_id:
        raise UnauthorizedError("Invalid token payload")
        
    return str(user_id)
