"""
database_setup.py
------------------
This script creates the project.db (SQLite database) from scratch.
Run with: python database_setup.py

What this does:
1. Deletes the old project.db if it exists (fresh start)
2. Creates 4 tables: users, student, lecture, attendance
3. Inserts sample/demo data (login credentials + demo students/lectures)
"""

import sqlite3
import os
from werkzeug.security import generate_password_hash

DB_NAME = os.path.join(os.path.dirname(os.path.abspath(__file__)), "project.db")

# Fresh database requested -> remove old file if it exists
if os.path.exists(DB_NAME):
    os.remove(DB_NAME)
    print(f"Old '{DB_NAME}' file removed.")

conn = sqlite3.connect(DB_NAME)
cur = conn.cursor()

# ---------------------------------------------------------
# 1. users table - for server-side login validation
# ---------------------------------------------------------
cur.execute("""
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL
)
""")

# ---------------------------------------------------------
# 2. student table
# ---------------------------------------------------------
cur.execute("""
CREATE TABLE student (
    stId INTEGER NOT NULL PRIMARY KEY,
    stName VARCHAR(50) NOT NULL
)
""")

# ---------------------------------------------------------
# 3. lecture table
# ---------------------------------------------------------
cur.execute("""
CREATE TABLE lecture (
    lecId INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    lecDate DATE NOT NULL,
    startTime TIME NOT NULL,
    endTime TIME NOT NULL,
    lecTitle VARCHAR(100)
)
""")

# ---------------------------------------------------------
# 4. attendance table (spelling fixed: attendence -> attendance)
#    auto-increment id added so duplicate/multiple records
#    can be tracked correctly
# ---------------------------------------------------------
cur.execute("""
CREATE TABLE attendance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stId INTEGER NOT NULL,
    lecId INTEGER NOT NULL,
    attendedTime TIME,
    status VARCHAR(10) NOT NULL DEFAULT 'absent',
    FOREIGN KEY (stId) REFERENCES student(stId),
    FOREIGN KEY (lecId) REFERENCES lecture(lecId)
)
""")

print("All 4 tables created successfully: users, student, lecture, attendance")

# ---------------------------------------------------------
# Sample Data - Login (admin/1234 - stored as a hash)
# ---------------------------------------------------------
cur.execute(
    "INSERT INTO users (username, password_hash) VALUES (?, ?)",
    ("admin", generate_password_hash("1234"))
)

# ---------------------------------------------------------
# Sample Data - Students
# ---------------------------------------------------------
students = [
    (249001, "Kasun Perera"),
    (249002, "Nadeesha Silva"),
    (249003, "Tharindu Fernando"),
]
cur.executemany("INSERT INTO student (stId, stName) VALUES (?, ?)", students)

# ---------------------------------------------------------
# Sample Data - Lectures
# ---------------------------------------------------------
lectures = [
    ("2026-07-01", "08:30", "10:30", "Database Systems"),
    ("2026-07-02", "09:00", "11:00", "Web Application Development"),
    ("2026-07-03", "08:30", "10:30", "Software Engineering"),
]
cur.executemany(
    "INSERT INTO lecture (lecDate, startTime, endTime, lecTitle) VALUES (?, ?, ?, ?)",
    lectures
)

# ---------------------------------------------------------
# Sample Data - Attendance records
# (lecId 1,2,3 = auto-generated in order of insertion above)
# ---------------------------------------------------------
attendance_records = [
    (249001, 1, "08:25", "present"),
    (249001, 2, "09:15", "present"),
    (249002, 1, None, "absent"),
    (249002, 2, "09:05", "present"),
    (249003, 1, "08:45", "present"),
]
cur.executemany(
    "INSERT INTO attendance (stId, lecId, attendedTime, status) VALUES (?, ?, ?, ?)",
    attendance_records
)

conn.commit()
conn.close()

print(f"'{DB_NAME}' created successfully with sample data.")
print("Login: username='admin', password='1234'")