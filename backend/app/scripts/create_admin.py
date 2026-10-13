"""Create (or reset) a site administrator.

    python -m app.scripts.create_admin --email you@college.edu --name "Your Name"

The password is read from --password, the ADMIN_PASSWORD environment variable, or a prompt.
"""

from __future__ import annotations

import argparse
import getpass
import os
import sys

from sqlalchemy import select

from app.core.security import hash_password
from app.db import get_sessionmaker
from app.models import User


def create_admin(email: str, name: str, password: str) -> User:
    db = get_sessionmaker()()
    try:
        email = email.strip().lower()
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(name=name, email=email, password_hash=hash_password(password))
            db.add(user)
        else:
            user.name = name or user.name
            user.password_hash = hash_password(password)
        user.is_active = True
        user.is_superadmin = True
        db.commit()
        db.refresh(user)
        return user
    finally:
        db.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", default="Admin")
    parser.add_argument("--password", default=os.environ.get("ADMIN_PASSWORD"))
    args = parser.parse_args(argv)
    password = args.password
    if not password:
        password = getpass.getpass("Password for the admin account: ")
    if len(password) < 8:
        print("The password must be at least 8 characters.", file=sys.stderr)
        return 2
    user = create_admin(args.email, args.name, password)
    print(f"Admin ready: {user.name} <{user.email}>")
    return 0


if __name__ == "__main__":
    sys.exit(main())
