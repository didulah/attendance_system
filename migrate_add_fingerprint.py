"""
migrate_add_fingerprint.py
---------------------------
One-time migration: adds a fingerprint_id column to the student table,
without wiping existing data. Safe to run multiple times (checks first).
"""
import sqlite3
import os

DB_NAME = os.path.join(os.path.dirname(os.path.abspath(__file__)), "project.db")

conn = sqlite3.connect(DB_NAME)
cur = conn.cursor()

# Check if the column already exists before trying to add it
cur.execute("PRAGMA table_info(student)")
columns = [row[1] for row in cur.fetchall()]

if "fingerprint_id" not in columns:
    cur.execute("ALTER TABLE student ADD COLUMN fingerprint_id INTEGER UNIQUE")
    conn.commit()
    print("✅ fingerprint_id column added to student table.")
else:
    print("ℹ️ fingerprint_id column already exists — nothing to do.")

conn.close()