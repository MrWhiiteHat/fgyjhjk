"""Authentication routes for RealFake Detection System."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from pydantic import BaseModel, EmailStr
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
import jwt
router = APIRouter(tags=["auth"])

SECRET_KEY = "realfake_super_secret_key_for_prototype_only"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440  # 24 hours

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")

USERS_DB_FILE = Path("app/backend/users.json")

def _load_users() -> dict:
    if not USERS_DB_FILE.exists():
        return {}
    try:
        with open(USERS_DB_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_users(users: dict) -> None:
    with open(USERS_DB_FILE, "w") as f:
        json.dump(users, f, indent=4)

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str = ""

class Token(BaseModel):
    access_token: str
    token_type: str

class UserResponse(BaseModel):
    email: str
    full_name: str

import bcrypt

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def get_password_hash(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = time.time() + (ACCESS_TOKEN_EXPIRE_MINUTES * 60)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

@router.post("/signup", response_model=UserResponse)
def signup(user: UserCreate):
    users = _load_users()
    if user.email in users:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    users[user.email] = {
        "email": user.email,
        "full_name": user.full_name,
        "hashed_password": get_password_hash(user.password)
    }
    _save_users(users)
    
    return UserResponse(email=user.email, full_name=user.full_name)

@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    users = _load_users()
    user = users.get(form_data.username)
    
    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    access_token = create_access_token(data={"sub": user["email"]})
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=UserResponse)
def read_users_me(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
        
    users = _load_users()
    user = users.get(email)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
        
    return UserResponse(email=user["email"], full_name=user["full_name"])
