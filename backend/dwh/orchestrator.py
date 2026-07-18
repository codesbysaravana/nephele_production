import time
from datetime import datetime

from ingest import ingest_data
from execute_sql import run_transformation

INTERVAL = 300  # 5 minutes


def run_pipeline():
    while True:
        try:
            print("=" * 50)
            print(f"Pipeline started at {datetime.now()}")

            # Step 1: Extract & Load
            ingest_data()

            # Step 2: Transform
            run_transformation()

            print("Pipeline completed successfully.")

        except Exception as e:
            print(f"Pipeline failed: {e}")

        print(f"Waiting {INTERVAL} seconds...\n")
        time.sleep(INTERVAL)


if __name__ == "__main__":
    run_pipeline()