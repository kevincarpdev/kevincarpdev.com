"""Add or reset a team member. Run:
  docker compose exec app python -m app.add_user <username> [display name]
"""
import getpass
import sys

from .auth import hash_password
from .db import SessionLocal, User, init_db


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    username = sys.argv[1].strip().lower()
    display = " ".join(sys.argv[2:]) or username.title()
    pw = getpass.getpass(f"Password for {username}: ")
    if len(pw) < 8:
        print("Use at least 8 characters.")
        sys.exit(1)

    init_db()
    db = SessionLocal()
    u = db.query(User).filter_by(username=username).first()
    if u:
        u.pw_hash = hash_password(pw)
        print(f"Password reset for {username}.")
    else:
        db.add(User(username=username, display_name=display,
                    pw_hash=hash_password(pw), peer_id=f"team-{username}"))
        print(f"User {username} created (honcho peer: team-{username}).")
    db.commit()
    db.close()


if __name__ == "__main__":
    main()
