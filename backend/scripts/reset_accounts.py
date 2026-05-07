import os
import sys
from pathlib import Path

from pymongo import MongoClient

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(*_args, **_kwargs):
        return False


CONFIRMATION_VALUE = "delete-all-accounts"
COLLECTIONS_TO_RESET = [
    "users",
    "decks",
    "analysis_runs",
    "auth_tokens",
    "rate_limits",
]


def main() -> int:
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")

    if os.environ.get("RESET_ACCOUNTS_CONFIRM") != CONFIRMATION_VALUE:
        print(
            "Refusing to reset accounts. Set "
            f"RESET_ACCOUNTS_CONFIRM={CONFIRMATION_VALUE} to continue."
        )
        return 1

    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME")
    if not mongo_url or not db_name:
        print("MONGO_URL and DB_NAME are required.")
        return 1

    client = MongoClient(mongo_url, serverSelectionTimeoutMS=10000)
    client.admin.command("ping")
    db = client[db_name]

    print(f"Resetting account data in database: {db_name}")
    for collection_name in COLLECTIONS_TO_RESET:
        count = db[collection_name].count_documents({})
        print(f"{collection_name}: {count} document(s) found")

    for collection_name in COLLECTIONS_TO_RESET:
        result = db[collection_name].delete_many({})
        print(f"{collection_name}: {result.deleted_count} document(s) deleted")

    client.close()
    print("Account reset complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
