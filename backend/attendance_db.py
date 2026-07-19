import sqlite3
import json
import os
from datetime import datetime

class AttendanceDB:
    DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "attendance.db")

    def __init__(self):
        # Automatically initialize the DB structure when the object is created
        self._initialize_db()

    def _get_connection(self):
        # Using check_same_thread=False allows us to share the connection across FastAPI threads
        # though we create a new connection per request to be extremely safe.
        return sqlite3.connect(self.DB_PATH)

    def _initialize_db(self):
        """Private method to create the table if it doesn't exist."""
        query = """
        CREATE TABLE IF NOT EXISTS scans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            scan_time TEXT NOT NULL,
            raw_payload JSON
        );
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            conn.commit()

    def log_scan(self, student_id: str, raw_payload: dict) -> int:
        """
        Logs a new QR scan into the database.
        Returns the inserted row ID.
        """
        query = """
        INSERT INTO scans (student_id, scan_time, raw_payload)
        VALUES (?, ?, ?)
        """
        scan_time = datetime.now().isoformat()
        payload_str = json.dumps(raw_payload)
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (student_id, scan_time, payload_str))
            conn.commit()
            return cursor.lastrowid

    def get_all_scans(self) -> list:
        """
        Fetches all scanned records and returns them as a list of dictionaries.
        Blazing fast execution.
        """
        query = "SELECT id, student_id, scan_time, raw_payload FROM scans ORDER BY scan_time DESC"
        results = []
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            rows = cursor.fetchall()
            
            for row in rows:
                results.append({
                    "id": row[0],
                    "student_id": row[1],
                    "scan_time": row[2],
                    "raw_payload": json.loads(row[3]) if row[3] else {}
                })
                
        return results
