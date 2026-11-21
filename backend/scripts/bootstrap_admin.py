"""Create the first named administrator from an interactive terminal."""
from __future__ import annotations

import argparse
import warnings
from getpass import GetPassWarning, getpass

from sqlalchemy import select, text


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("username")
    parser.add_argument("email")
    args = parser.parse_args()

    from app.auth import hash_password
    from app.database import SyncSessionLocal
    from app.models import User
    from app.schemas.auth import ACCOUNT_USERNAME_PATTERN, is_valid_account_email

    username = args.username.strip()
    email = args.email.strip().lower()
    if not ACCOUNT_USERNAME_PATTERN.fullmatch(username):
        parser.error("Username must be 3–64 characters (letters, digits, '.', '_' or '-').")
    if not is_valid_account_email(email):
        parser.error("Enter a valid email address.")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", GetPassWarning)
            password = getpass("Admin password: ")
            confirmation = getpass("Confirm password: ")
    except (GetPassWarning, EOFError):
        raise SystemExit("An interactive terminal with hidden password input is required.") from None
    if not 8 <= len(password.encode("utf-8")) <= 72:
        parser.error("Password must be 8 to 72 bytes long.")
    if password != confirmation:
        parser.error("Passwords do not match.")
    password_hash = hash_password(password)

    with SyncSessionLocal.begin() as db:
        # Serialize the first-admin check with concurrent account writes.
        db.execute(text("LOCK TABLE users IN SHARE ROW EXCLUSIVE MODE"))
        if db.scalar(select(User.id).where(User.role == "Admin").limit(1)) is not None:
            raise SystemExit("An administrator already exists. Use admin account management.")
        if db.scalar(select(User.id).where((User.username == username) | (User.email == email)).limit(1)) is not None:
            raise SystemExit("Username or email already exists.")
        db.add(User(username=username, email=email, password_hash=password_hash, role="Admin", is_active=True))

    print(f"Created administrator {username}.")


if __name__ == "__main__":
    main()
