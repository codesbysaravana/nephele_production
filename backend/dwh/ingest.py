# extracting and loading

import os
import json
import psycopg

from dotenv import load_dotenv

load_dotenv()

def ingest_data():
    DATABASE_URL = os.getenv("DATABASE_URL")
    if not DATABASE_URL:
        print("Error: DATABASE_URL not found in environment.")
        return

    # Connect to PostgreSQL
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:

            # Create table if it doesn't exist
            cur.execute("""
                CREATE TABLE IF NOT EXISTS raw_transactions (
                    id SERIAL PRIMARY KEY,
                    raw_data JSONB NOT NULL
                );
            """)
            conn.commit()

            # Get absolute path based on this file's location
            current_dir = os.path.dirname(os.path.abspath(__file__))
            file_path = os.path.join(current_dir, "raw_data.json")

            # Read raw JSON file
            with open(file_path, "r", encoding="utf-8") as file:
                transactions = json.load(file)

            # Insert each JSON object directly
            for transaction in transactions:
                cur.execute(
                    """
                    INSERT INTO raw_transactions (raw_data)
                    VALUES (%s::jsonb);
                    """,
                    (json.dumps(transaction),)
                )

            conn.commit()
            print(f"Inserted {len(transactions)} raw transactions successfully.")