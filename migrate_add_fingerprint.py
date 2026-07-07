"""
migrate_add_fingerprint.py
---------------------------
<<<<<<< HEAD
Run this ONCE on the LIVE PythonAnywhere project.db to add fingerprint
support WITHOUT deleting existing students/lectures/attendance records.

(database_setup.py deletes the whole db and rebuilds it - do NOT run
that on the live server, or you will lose all real attendance data.)

Usage:
    python migrate_add_fingerprint.py
"""

=======
One-time migration: adds a fingerprint_id column to the student table,
without wiping existing data. Safe to run multiple times (checks first).
"""
>>>>>>> main
import sqlite3
import os

DB_NAME = os.path.join(os.path.dirname(os.path.abspath(__file__)), "project.db")

conn = sqlite3.connect(DB_NAME)
cur = conn.cursor()

<<<<<<< HEAD
# --- 1. Add fingerprint_id to student, only if it doesn't exist yet ---
cur.execute("PRAGMA table_info(student)")
existing_columns = [row[1] for row in cur.fetchall()]

if "fingerprint_id" not in existing_columns:
    cur.execute("ALTER TABLE student ADD COLUMN fingerprint_id INTEGER")
    print("Added column: student.fingerprint_id")
else:
    print("Column student.fingerprint_id already exists - skipped.")

# --- 2. Create enroll_queue table, only if it doesn't exist yet ---
cur.execute("""
CREATE TABLE IF NOT EXISTS enroll_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stId INTEGER NOT NULL,
    fingerprint_id INTEGER NOT NULL,
    status VARCHAR(10) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    FOREIGN KEY (stId) REFERENCES student(stId)
)
""")
print("Ensured table enroll_queue exists.")

conn.commit()
conn.close()

print("Migration complete. Existing student/lecture/attendance data was not touched.")
=======
# Step 1: Check if the column already exists before trying to add it
cur.execute("PRAGMA table_info(student)")
columns = [row[1] for row in cur.fetchall()]

if "fingerprint_id" not in columns:
    # NOTE: SQLite does not allow UNIQUE directly in ALTER TABLE ADD COLUMN,
    # so we add it as a plain column first.
    cur.execute("ALTER TABLE student ADD COLUMN fingerprint_id INTEGER")
    conn.commit()
    print("✅ fingerprint_id column added to student table.")
else:
    print("ℹ️ fingerprint_id column already exists — skipping column add.")

# Step 2: Enforce uniqueness separately, using an index instead
cur.execute(
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_student_fingerprint_id "
    "ON student(fingerprint_id)"
)
conn.commit()
print("✅ Unique index on fingerprint_id ensured.")

conn.close()
>>>>>>> main
