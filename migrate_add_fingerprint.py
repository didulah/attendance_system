"""
migrate_add_fingerprint.py
---------------------------
Safe, non-destructive migration for the Fingerprint Attendance System.

What this does:
1. Connects to the EXISTING project.db (does NOT delete or recreate it)
2. Checks the current columns of the 'student' table using PRAGMA table_info
3. Adds a new column 'fingerprint_id INTEGER' ONLY if it does not already exist
4. Safe to run multiple times - it will not duplicate the column or wipe data

Why fingerprint_id is an INTEGER (not a BLOB):
The R307S sensor stores the actual fingerprint template on the sensor module
itself. When a scan matches, the sensor only returns a slot/ID number
(an integer), never the raw template data. So the Flask database only
ever needs to store that integer, not a binary template.

Run with (PowerShell):
    python migrate_add_fingerprint.py

Safe to run on:
- Local project.db
- Live PythonAnywhere project.db (via Bash console, after git pull)

Do NOT use database_setup.py for this - that script deletes the whole
database and recreates it from scratch, which would wipe all real
attendance records on a live deployment.
"""

import sqlite3
import os

# Use an absolute path anchored to this file's location.
# Relative paths silently break under PythonAnywhere's WSGI process
# (the working directory is not what you expect), which can make the
# app look like it is talking to an empty database.
DB_NAME = os.path.join(os.path.dirname(os.path.abspath(__file__)), "project.db")


def column_exists(cursor, table_name, column_name):
    """Return True if column_name already exists in table_name."""
    cursor.execute("PRAGMA table_info(%s)" % table_name)
    columns = [row[1] for row in cursor.fetchall()]
    return column_name in columns


def main():
    if not os.path.exists(DB_NAME):
        print("ERROR: project.db not found at: " + DB_NAME)
        print("Make sure this script is in the same folder as project.db,")
        print("or that project.db has already been created (see database_setup.py).")
        return

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    if column_exists(cur, "student", "fingerprint_id"):
        print("No changes needed: 'fingerprint_id' column already exists on 'student' table.")
    else:
        cur.execute("ALTER TABLE student ADD COLUMN fingerprint_id INTEGER")
        conn.commit()
        print("SUCCESS: 'fingerprint_id' column added to 'student' table.")

    # Show the final schema so you can confirm the change
    cur.execute("PRAGMA table_info(student)")
    print("\nCurrent 'student' table schema:")
    for row in cur.fetchall():
        # row format: (cid, name, type, notnull, dflt_value, pk)
        print("  - %s (%s)" % (row[1], row[2]))

    conn.close()


if __name__ == "__main__":
    main()