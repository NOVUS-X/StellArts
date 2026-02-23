from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user
from app.core.config import settings
from app.core.email_verification import (
    generate_verification_token,
    verify_verification_token,
)
from app.core.security import (
    blacklist_token,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    is_token_blacklisted,
    verify_password,
)
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import (
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
)
from app.services.email import send_verification_email

router = APIRouter(prefix="/auth")

bearer_scheme = HTTPBearer()


@router.post(
    "/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED
)
async def register_user(
    user_in: RegisterRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    existing_user = db.query(User).filter(User.email == user_in.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_pw = get_password_hash(user_in.password)

    user = User(
        email=user_in.email,
        hashed_password=hashed_pw,
        role=user_in.role.value,
        full_name=user_in.full_name,
        phone=user_in.phone,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Send verification email in background
    token = generate_verification_token(user.id, user.email)
    verify_url = (
        f"{settings.FRONTEND_URL}/verify-email?token={token}&email={user.email}"
    )

    background_tasks.add_task(
        send_verification_email,
        to=user.email,
        full_name=user.full_name or "there",
        verify_url=verify_url,
    )

    return {
        "id": user.id,
        "role": user.role,
        "message": "Check your email to verify your account",
    }


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = get_user_by_email(request.email, db)

    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )

    access_token = create_access_token(subject=user.id)
    refresh_token = create_refresh_token(subject=user.id)

    return {"access_token": access_token, "refresh_token": refresh_token}


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(request: RefreshRequest):
    try:
        payload = decode_token(request.refresh_token)
        jti = payload.get("jti")
        if not jti:
            raise HTTPException(status_code=401, detail="Malformed refresh token")
        if is_token_blacklisted(jti):
            raise HTTPException(
                status_code=401, detail="Refresh token has been revoked"
            )

        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Malformed refresh token")

        access_token = create_access_token(user_id)
        return {
            "access_token": access_token,
            "refresh_token": request.refresh_token,
            "token_type": "bearer",
        }
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token") from None


@router.post("/logout")
def logout(
    request: LogoutRequest,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    current_user: User = Depends(get_current_active_user),
):
    """Logout user by blacklisting both access and refresh tokens."""
    try:
        access_payload = decode_token(credentials.credentials)
        refresh_payload = decode_token(request.refresh_token)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token") from None

    access_jti = access_payload.get("jti")
    access_exp = access_payload.get("exp")
    refresh_jti = refresh_payload.get("jti")
    refresh_exp = refresh_payload.get("exp")
    if not access_jti or not access_exp or not refresh_jti or not refresh_exp:
        raise HTTPException(status_code=400, detail="Malformed token")

    blacklist_token(access_jti, access_exp)
    blacklist_token(refresh_jti, refresh_exp)
    return {"message": "Successfully logged out", "user": current_user.email}


def get_user_by_email(email: str, db: Session) -> User | None:
    return db.query(User).filter(User.email == email).first()


@router.get("/verify-email")
def verify_email(token: str, email: str, db: Session = Depends(get_db)):
    """Verify email address using signed token from email link."""
    user_id = verify_verification_token(token, email)
    if not user_id:
        raise HTTPException(
            status_code=400, detail="Invalid or expired verification token"
        )

    user = db.query(User).filter(User.id == user_id, User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.is_verified:
        return {"message": "Email already verified"}

    user.is_verified = True
    db.commit()
    return {"message": "Email verified successfully"}


@router.post("/resend-verification")
async def resend_verification(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
):
    """Resend verification email for the current user."""
    if current_user.is_verified:
        raise HTTPException(status_code=400, detail="Email is already verified")

    token = generate_verification_token(current_user.id, current_user.email)
    verify_url = (
        f"{settings.FRONTEND_URL}/verify-email?token={token}&email={current_user.email}"
    )
    background_tasks.add_task(
        send_verification_email,
        to=current_user.email,
        full_name=current_user.full_name or "there",
        verify_url=verify_url,
    )
    return {"message": "Verification email sent"}
