#!/usr/bin/env python3
"""
Create an admin user from a trusted environment.

Usage:
    python scripts/create_admin.py --email admin@example.com --password 'StrongPass1!'
"""

import argparse
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.core.security import get_password_hash
from app.db.base import SessionLocal
from app.models.user import User


def create_admin(email: str, password: str) -> int | None:
    db = SessionLocal()
    try:
        existing_user = db.query(User).filter(User.email == email).first()
        if existing_user:
            print(f"User {email} already exists with role '{existing_user.role}'.")
            return None

        user = User(
            email=email,
            hashed_password=get_password_hash(password),
            role="admin",
            is_active=True,
            is_verified=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        print(f"Admin user created: id={user.id}, email={user.email}")
        return user.id
    finally:
        db.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create an admin user.")
    parser.add_argument("--email", required=True, help="Admin email")
    parser.add_argument("--password", required=True, help="Admin password")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    create_admin(args.email, args.password)
