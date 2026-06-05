import argparse
import sys

from sqlmodel import Session, select

from app.database import engine, create_tables
from app.models import AdminUser
from app.auth import hash_password


def main():
    parser = argparse.ArgumentParser(description="Interview Form Summarizer CLI")
    subparsers = parser.add_subparsers(dest="command")

    create_admin_parser = subparsers.add_parser("create-admin", help="Create an admin user")
    create_admin_parser.add_argument("username", help="Admin username")
    create_admin_parser.add_argument("password", help="Admin password")

    args = parser.parse_args()

    if args.command == "create-admin":
        create_tables()
        with Session(engine) as db:
            existing = db.exec(
                select(AdminUser).where(AdminUser.username == args.username)
            ).first()
            if existing:
                print(f"User '{args.username}' already exists.")
                sys.exit(1)
            admin = AdminUser(
                username=args.username,
                hashed_password=hash_password(args.password),
            )
            db.add(admin)
            db.commit()
            print(f"Admin user '{args.username}' created.")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
