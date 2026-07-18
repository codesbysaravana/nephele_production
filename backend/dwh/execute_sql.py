import os
import json
import psycopg

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def run_transformation():
    DATABASE_URL = os.getenv("DATABASE_URL")
    if not DATABASE_URL:
        print("Error: DATABASE_URL not found in environment.")
        return

    try:
        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                current_dir = os.path.dirname(os.path.abspath(__file__))
                file_path = os.path.join(current_dir, "transform.sql")

                with open(file_path, "r", encoding="utf-8") as file:
                    sql = file.read()

                # psycopg can execute multiple statements separated by semicolon
                cur.execute(sql)
                conn.commit()

        print("Transformation completed.")
    except Exception as e:
        print(f"Error during transformation: {e}")