import random
from attendance_db import AttendanceDB

def seed_database():
    print("Initializing AttendanceDB...")
    db = AttendanceDB()
    
    print("Generating mock QR scan data...")
    
    mock_students = [
        {"id": "EMP-101", "name": "Saravana", "role": "Data Analyst"},
        {"id": "EMP-102", "name": "Taasha", "role": "ML Engineer"},
        {"id": "EMP-103", "name": "Alice", "role": "Backend Dev"},
        {"id": "EMP-104", "name": "Bob", "role": "Frontend Dev"},
        {"id": "EMP-105", "name": "Charlie", "role": "DevOps"}
    ]
    
    # Generate 20 fake scans
    for _ in range(20):
        student = random.choice(mock_students)
        
        # We simulate the exact payload the QR scanner would send
        payload = {
            "student_id": student["id"],
            "raw_qr_data": student,  # Simulating a full JSON string inside the QR
            "status": "Present",
            "device": "Webcam Scanner"
        }
        
        db.log_scan(student_id=student["id"], raw_payload=payload)
        
    print("Successfully inserted 20 mock attendance records into SQLite!")
    print("You can view them at: http://localhost:8000/api/attendance")

if __name__ == "__main__":
    seed_database()
