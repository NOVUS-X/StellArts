from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.auth import require_admin
from app.db.session import get_db
from app.models.booking import BookingStatus
from app.models.dispute import Dispute, DisputeStatus
from app.models.payment import PaymentStatus
from app.models.user import User
from app.schemas.dispute import DisputeResolve, DisputeResponse

router = APIRouter(prefix="/admin")


@router.get("/users")
def get_all_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
    skip: int = 0,
    limit: int = 100,
    role_filter: str | None = None,
):
    """Get all users with optional role filtering - admin only"""
    query = db.query(User)

    if role_filter:
        query = query.filter(User.role == role_filter)

    users = query.offset(skip).limit(limit).all()

    return {
        "message": "Users retrieved successfully",
        "admin_user": current_user.full_name,
        "total_users": len(users),
        "role_filter": role_filter,
        "users": [
            {
                "id": user.id,
                "email": user.email,
                "role": user.role,
                "full_name": user.full_name,
                "is_active": user.is_active,
                "created_at": user.created_at,
            }
            for user in users
        ],
    }


@router.put("/users/{user_id}/role")
def update_user_role(
    user_id: int,
    new_role: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Update user role - admin only"""
    if new_role not in ["client", "artisan", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid role. Must be 'client', 'artisan', or 'admin'",
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    old_role = user.role
    user.role = new_role
    db.commit()

    return {
        "message": "User role updated successfully",
        "user_id": user_id,
        "old_role": old_role,
        "new_role": new_role,
        "updated_by": current_user.full_name,
    }


@router.put("/users/{user_id}/status")
def update_user_status(
    user_id: int,
    is_active: bool,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Activate/deactivate user account - admin only"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Prevent admin from deactivating themselves
    if user.id == current_user.id and not is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate your own account",
        )

    old_status = user.is_active
    user.is_active = is_active
    db.commit()

    return {
        "message": "User status updated successfully",
        "user_id": user_id,
        "old_status": old_status,
        "new_status": is_active,
        "updated_by": current_user.full_name,
    }


@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Delete user account - admin only"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Prevent admin from deleting themselves
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account",
        )

    deleted_user_info = {
        "id": user.id,
        "email": user.email,
        "role": user.role,
        "full_name": user.full_name,
    }

    db.delete(user)
    db.commit()

    return {
        "message": "User deleted successfully",
        "deleted_user": deleted_user_info,
        "deleted_by": current_user.full_name,
    }


@router.get("/stats")
def get_system_stats(
    db: Session = Depends(get_db), current_user: User = Depends(require_admin)
):
    """Get system statistics - admin only"""
    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.is_active).count()
    clients = db.query(User).filter(User.role == "client").count()
    artisans = db.query(User).filter(User.role == "artisan").count()
    admins = db.query(User).filter(User.role == "admin").count()

    return {
        "message": "System statistics",
        "requested_by": current_user.full_name,
        "stats": {
            "total_users": total_users,
            "active_users": active_users,
            "inactive_users": total_users - active_users,
            "role_distribution": {
                "clients": clients,
                "artisans": artisans,
                "admins": admins,
            },
        },
    }


@router.get("/disputes", response_model=list[DisputeResponse])
def get_all_disputes(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
    skip: int = 0,
    limit: int = 100,
    status_filter: DisputeStatus | None = None,
):
    """Get all disputes with optional status filtering - admin only"""
    query = db.query(Dispute)

    if status_filter:
        query = query.filter(Dispute.status == status_filter)

    disputes = query.order_by(Dispute.created_at.desc()).offset(skip).limit(limit).all()
    return disputes


@router.post("/disputes/{dispute_id}/resolve")
def resolve_dispute(
    dispute_id: uuid.UUID,
    resolution: DisputeResolve,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Resolve a dispute by setting payout ratio and executing transfers - admin only.

    The payout_artisan_ratio determines how much of the escrowed funds
    go to the artisan. The remainder goes back to the client.
    """
    dispute = db.query(Dispute).filter(Dispute.id == dispute_id).first()
    if not dispute:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Dispute not found"
        )

    if dispute.status != DisputeStatus.OPEN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Dispute is already {dispute.status.value}",
        )

    # Update dispute record
    dispute.status = DisputeStatus.RESOLVED
    dispute.payout_artisan_ratio = resolution.payout_artisan_ratio
    dispute.resolution_memo = resolution.resolution_memo
    dispute.resolved_at = func.now()
    dispute.resolved_by = current_user.full_name

    # Update related records
    payment = dispute.payment
    booking = dispute.booking
    # In a real scenario, we would trigger the Stellar/Soroban transfers here.
    # For now, we update the statuses to reflect resolution.

    payment.status = (
        PaymentStatus.RELEASED
        if resolution.payout_artisan_ratio > 0
        else PaymentStatus.REFUNDED
    )
    booking.status = (
        BookingStatus.COMPLETED
        if resolution.payout_artisan_ratio > 0.5
        else BookingStatus.CANCELLED
    )

    db.commit()
    db.refresh(dispute)

    return {
        "message": "Dispute resolved successfully",
        "dispute_id": dispute.id,
        "status": dispute.status.value,
        "payout_artisan_ratio": float(dispute.payout_artisan_ratio),
        "resolved_by": dispute.resolved_by,
    }
