#!/usr/bin/env python3
"""Set a new random password for the admin account and print it once.

Run from the deployed application so it uses that directory's .env:

    cd /var/www/neuralxpert
    .venv/bin/python scripts/generate_admin_password.py
    .venv/bin/python scripts/generate_admin_password.py neuralxperts@gmail.com
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from app import create_app
from app.admin.security import issue_staff_password


def main():
    email = sys.argv[1] if len(sys.argv) > 1 else "neuralxperts@gmail.com"
    config_name = os.environ.get("FLASK_CONFIG", "development")
    app = create_app(config_name)
    with app.app_context():
        staff, password, created = issue_staff_password(email)
        account = staff.email
    action = "created" if created else "updated"
    print(f"Staff account {action} for {account}")
    print(f"Temporary password: {password}")
    print("Sign in at /admin/login. This password is shown only once.")
    print("The email code and Google Authenticator are still required.")


if __name__ == "__main__":
    main()
