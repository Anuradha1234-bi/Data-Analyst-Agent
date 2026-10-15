import argparse
import os
import sys

# Ensure backend root is on sys.path if run directly
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.database.database import SessionLocal, init_db
from app.services.auth_service import AuthService


def main():
    parser = argparse.ArgumentParser(description="Seed an administrative user for AI Data Analyst Agent.")
    parser.add_argument(
        "--username",
        default=os.getenv("ADMIN_USERNAME", "admin"),
        help="Admin username (default: env ADMIN_USERNAME or 'admin')",
    )
    parser.add_argument(
        "--email",
        default=os.getenv("ADMIN_EMAIL", "admin@example.com"),
        help="Admin email (default: env ADMIN_EMAIL or 'admin@example.com')",
    )
    parser.add_argument(
        "--password",
        default=os.getenv("ADMIN_PASSWORD"),
        help="Admin password (or supply via ADMIN_PASSWORD environment variable)",
    )

    args = parser.parse_args()

    password = args.password
    if not password:
        import getpass
        password = getpass.getpass("Enter Admin Password: ")

    if len(password) < 8:
        print("Error: Password must be at least 8 characters long.")
        sys.exit(1)

    init_db()
    db = SessionLocal()
    try:
        user = AuthService.seed_admin_user(
            db=db,
            username=args.username,
            email=args.email,
            password=password,
        )
        print(f"Successfully seeded admin user: '{user.username}' ({user.email}) with role '{user.role}'.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
