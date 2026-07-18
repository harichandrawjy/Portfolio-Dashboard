import asyncio

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.deps import CurrentUser, Session
from app.models import User
from app.schemas import LoginIn, RegisterIn, TokenOut, UserOut
from app.security import create_access_token, hash_password, verify_password

router = APIRouter(tags=["auth"])


@router.post("/auth/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterIn, session: Session) -> User:
    email = payload.email.lower()
    # bcrypt is CPU-bound (~100ms by design) — keep it off the event loop
    password_hash = await asyncio.to_thread(hash_password, payload.password)
    user = User(
        email=email,
        password_hash=password_hash,
        display_name=payload.display_name,
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    await session.refresh(user)
    return user


@router.post("/auth/login", response_model=TokenOut)
async def login(payload: LoginIn, session: Session) -> TokenOut:
    user = await session.scalar(
        select(User).where(User.email == payload.email.lower())
    )
    # identical error for unknown email and wrong password — leak nothing
    if user is None or not await asyncio.to_thread(
        verify_password, payload.password, user.password_hash
    ):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Incorrect email or password"
        )
    return TokenOut(access_token=create_access_token(user.id))


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser) -> User:
    return user
