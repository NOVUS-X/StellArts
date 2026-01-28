from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user
from app.core.security import (
    blacklist_token,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    verify_password,
)
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import (
    LoginRequest,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
)

router = APIRouter(prefix='/auth')

bearer_scheme = HTTPBearer()

@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
def register_user(user_in: RegisterRequest, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.email == user_in.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_pw = get_password_hash(user_in.password)

    user = User(
        email=user_in.email,
        hashed_password=hashed_pw,
        role=user_in.role,
        full_name=user_in.full_name,
        phone=user_in.phone
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return {"id": user.id, "role": user.role}

@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = get_user_by_email(request.email, db)

    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    access_token = create_access_token(subject=user.id)
    refresh_token = create_refresh_token(subject=user.id)

    return {"access_token": access_token, "refresh_token": refresh_token}

@router.post("/refresh", response_model=TokenResponse)
def refresh_token(refresh_token: str):
    try:
        payload = decode_token(refresh_token)
        user_id = payload.get("sub")
        access_token = create_access_token(user_id)
        return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token") from None

@router.post("/logout")
def logout(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    current_user: User = Depends(get_current_active_user)
):
    """Logout user by blacklisting their current token"""
    token = credentials.credentials
    decoded = decode_token(token)
    if not decoded:
        raise HTTPException(status_code=401, detail="Invalid token")

    jti = decoded.get("jti")
    exp = decoded.get("exp")
    if not jti or not exp:
        raise HTTPException(status_code=400, detail="Malformed token")

    blacklist_token(jti, exp)
    return {
        "message": "Successfully logged out",
        "user": current_user.email
    }

def get_user_by_email(email: str,  db: Session) -> User | None:
    return db.query(User).filter(User.email == email).first()
