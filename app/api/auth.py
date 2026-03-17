from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from passlib.context import CryptContext

from app.database import get_db
from app.models import UserModel
from app.services.auth_service import get_password_hash, verify_password, create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])

class AuthRequest(BaseModel):
    phone: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    role: str

ADMIN_PHONES = {"+77024383624", "+77470470059"}

@router.post("/register", response_model=TokenResponse)
async def register(req: AuthRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(UserModel).where(UserModel.phone == req.phone))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Phone number already registered")

    role = "admin" if req.phone in ADMIN_PHONES else "user"
    hashed_pwd = get_password_hash(req.password)

    user = UserModel(
        phone=req.phone,
        password_hash=hashed_pwd,
        role=role
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    access_token = create_access_token(data={"sub": user.id, "role": user.role})
    return {"access_token": access_token, "token_type": "bearer", "role": user.role}

@router.post("/login", response_model=TokenResponse)
async def login(req: AuthRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(UserModel).where(UserModel.phone == req.phone))
    user = result.scalar_one_or_none()

    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect phone or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(data={"sub": user.id, "role": user.role})
    return {"access_token": access_token, "token_type": "bearer", "role": user.role}
