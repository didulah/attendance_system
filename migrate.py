import sqlite3

conn = sqlite3.connect("project.db")
conn.execute("ALTER TABLE student ADD COLUMN fingerprint_id INTEGER UNIQUE")
conn.commit()
conn.close()

print("Done! fingerprint_id column added.")