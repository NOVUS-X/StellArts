import os
import shutil

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user, require_admin
from app.core.config import settings
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import UserOut, UserUpdate

router = APIRouter(prefix="/users")


@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_active_user)):
    """Get current user profile"""
    return current_user


@router.put("/me", response_model=UserOut)
def update_me(
    user_in: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Update current user profile"""
    update_data = user_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(current_user, field, value)

    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return current_user


@router.post("/me/avatar", response_model=UserOut)
async def upload_avatar(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Upload user avatar"""
    # Create directory if it doesn't exist
    static_path = os.path.join(os.getcwd(), settings.STATIC_DIR)
    avatars_path = os.path.join(static_path, settings.AVATARS_DIR)
    if not os.path.exists(avatars_path):
        os.makedirs(avatars_path)

    # Save file
    file_extension = file.filename.split(".")[-1]
    file_name = f"user_{current_user.id}.{file_extension}"
    file_path = os.path.join(avatars_path, file_name)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Update user avatar URL
    current_user.avatar = f"/{settings.STATIC_DIR}/{settings.AVATARS_DIR}/{file_name}"
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return current_user


@router.get("/{user_id}", response_model=UserOut)
def get_user_by_id(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get user by ID - only accessible by admin or the user themselves"""
    # Check if user is admin or accessing their own profile
    if current_user.role != "admin" and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. You can only access your own profile or need admin privileges.",
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    return user


@router.get("/", response_model=list[UserOut])
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
    skip: int = 0,
    limit: int = 100,
):
    """List all users - admin only"""
    users = db.query(User).offset(skip).limit(limit).all()
    return users
