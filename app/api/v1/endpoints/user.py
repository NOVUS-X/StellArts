from fastapi import APIRouter, Depends, HTTPException, status
from app.models.user import User
from app.core.security import decode_token, is_token_blacklisted
from app.db.session import get_db
from app.schemas.user import UserOut
from sqlalchemy.orm import Session
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

router = APIRouter(prefix="/users")

bearer_scheme = HTTPBearer()

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
):
    token = credentials.credentials

    payload = decode_token(token)
    
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    jti = payload.get("jti")
    if is_token_blacklisted(jti):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token revoked")

    user = db.query(User).filter(User.id == payload.get("sub")).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return user

@router.get("/me", response_model=UserOut)
def get_me(current_user=Depends(get_current_user)):
    return current_user
