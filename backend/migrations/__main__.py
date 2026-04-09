"""
CLI для ручного запуска миграций

Использование:
    python -m backend.migrations
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env"))

from backend.core.config import settings
from backend.migrations.runner import run_migrations


def main():
    db_url = settings.history_db_url
    if not db_url:
        print("❌ HISTORY_DATABASE_URL не задан в .env")
        sys.exit(1)

    print(f"[MIGRATIONS] URL: {db_url[:40]}...")
    run_migrations(db_url)


if __name__ == "__main__":
    main()
