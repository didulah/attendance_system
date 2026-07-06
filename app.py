"""
Flask backend for the Fingerprint Attendance System (mock/demo version).
Routes:
  GET  /            -> redirect to /home if logged in, else show login page
  GET  /login       -> show login form
  POST /login       -> validate credentials, start session
  GET  /logout      -> clear session, back to login
  GET  /home        -> search box to enter a Student ID
  POST /home        -> redirect to /student/<id>
  GET  /student/<id>-> show student info + latest attendance
  GET  /stats/<id>  -> show attendance statistics (total/present/late)
  GET  /update/<id> -> show form to mark attendance for a lecture
  POST /update/<id> -> save attendance record (insert or update)
  GET  /report/<id> -> printable full attendance history
"""
import os
import sqlite3
from functools import wraps
from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash

app = Flask(__name__)

# Secret key is needed for session/cookies to work.
# In production, set this via an environment variable instead of hardcoding it.
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-this")

DB_NAME = "project.db"

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

# ---------------------------------------------------------
# Decorator: protects routes that require login
# ---------------------------------------------------------
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user" not in session:
            flash("Please log in first.")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper

# ---------------------------------------------------------
# Root: send user to the right place
# ---------------------------------------------------------
@app.route("/")
def index():
    if "user" in session:
        return redirect(url_for("home"))
    return redirect(url_for("login"))

# ---------------------------------------------------------
# Login
# ---------------------------------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        conn.close()

        if user and check_password_hash(user["password_hash"], password):
            session["user"] = username
            return redirect(url_for("home"))
        else:
            flash("Invalid username or password.")
            return redirect(url_for("login"))

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ---------------------------------------------------------
# Home: enter a Student ID to look up
# ---------------------------------------------------------
@app.route("/home", methods=["GET", "POST"])
@login_required
def home():
    if request.method == "POST":
        st_id = request.form.get("stId", "").strip()
        if not st_id:
            flash("Please enter a Student ID.")
            return redirect(url_for("home"))
        return redirect(url_for("student_info", st_id=st_id))
    return render_template("home.html")

# ---------------------------------------------------------
# Student info page
# ---------------------------------------------------------
@app.route("/student/<int:st_id>")
@login_required
def student_info(st_id):
    conn = get_db()
    student = conn.execute(
        "SELECT * FROM student WHERE stId = ?", (st_id,)
    ).fetchone()

    if student is None:
        conn.close()
        flash(f"No student found with ID {st_id}.")
        return redirect(url_for("home"))

    # latest attendance record, joined with lecture for the date
    latest = conn.execute(
        """
        SELECT a.*, l.lecDate, l.lecTitle
        FROM attendance a
        JOIN lecture l ON a.lecId = l.lecId
        WHERE a.stId = ?
        ORDER BY l.lecDate DESC, a.id DESC
        LIMIT 1
        """,
        (st_id,),
    ).fetchone()
    conn.close()

    return render_template("student_info.html", student=student, latest=latest)

# ---------------------------------------------------------
# Statistics page (the old broken "More" page)
# ---------------------------------------------------------
@app.route("/stats/<int:st_id>")
@login_required
def stats(st_id):
    conn = get_db()
    student = conn.execute(
        "SELECT * FROM student WHERE stId = ?", (st_id,)
    ).fetchone()

    if student is None:
        conn.close()
        flash(f"No student found with ID {st_id}.")
        return redirect(url_for("home"))

    records = conn.execute(
        "SELECT * FROM attendance WHERE stId = ?", (st_id,)
    ).fetchall()
    conn.close()

    total = len(records)
    present_count = sum(1 for r in records if r["status"] == "present")
    late_count = sum(1 for r in records if _is_late(r["attendedTime"]))

    return render_template(
        "stats.html",
        student=student,
        total=total,
        present_count=present_count,
        late_count=late_count,
    )

def _is_late(time_str):
    """Demo rule: present after 08:00 counts as late."""
    if not time_str:
        return False
    try:
        hh, mm = map(int, time_str.split(":")[:2])
    except ValueError:
        return False
    return hh > 8 or (hh == 8 and mm > 0)

# ---------------------------------------------------------
# Update / mark attendance page
# ---------------------------------------------------------
@app.route("/update/<int:st_id>", methods=["GET", "POST"])
@login_required
def update(st_id):
    conn = get_db()
    student = conn.execute(
        "SELECT * FROM student WHERE stId = ?", (st_id,)
    ).fetchone()

    if student is None:
        conn.close()
        flash(f"No student found with ID {st_id}.")
        return redirect(url_for("home"))

    if request.method == "POST":
        lec_id = request.form.get("lecId")
        att_status = request.form.get("attendance")  # 'present' or 'absent'
        reason = request.form.get("reason", "")

        if not lec_id or not att_status:
            flash("Please select a lecture and an attendance status.")
            conn.close()
            return redirect(url_for("update", st_id=st_id))

        attended_time = datetime.now().strftime("%H:%M") if att_status == "present" else None

        existing = conn.execute(
            "SELECT id FROM attendance WHERE stId = ? AND lecId = ?",
            (st_id, lec_id),
        ).fetchone()

        if existing:
            conn.execute(
                "UPDATE attendance SET attendedTime = ?, status = ? WHERE id = ?",
                (attended_time, att_status, existing["id"]),
            )
        else:
            conn.execute(
                "INSERT INTO attendance (stId, lecId, attendedTime, status) VALUES (?, ?, ?, ?)",
                (st_id, lec_id, attended_time, att_status),
            )

        conn.commit()
        conn.close()
        flash("Attendance record saved" + (f" (reason: {reason})" if reason else ""))
        return redirect(url_for("student_info", st_id=st_id))

    lectures = conn.execute(
        "SELECT * FROM lecture ORDER BY lecDate DESC"
    ).fetchall()
    conn.close()

    return render_template("update.html", student=student, lectures=lectures)

# ---------------------------------------------------------
# Printable report
# ---------------------------------------------------------
@app.route("/report/<int:st_id>")
@login_required
def report(st_id):
    conn = get_db()
    student = conn.execute(
        "SELECT * FROM student WHERE stId = ?", (st_id,)
    ).fetchone()

    records = conn.execute(
        """
        SELECT a.*, l.lecDate, l.lecTitle
        FROM attendance a
        JOIN lecture l ON a.lecId = l.lecId
        WHERE a.stId = ?
        ORDER BY l.lecDate ASC
        """,
        (st_id,),
    ).fetchall()
    conn.close()

    return render_template("report.html", student=student, records=records)

if __name__ == "__main__":
    # debug=True is fine for local development only.
    # Turn this off (debug=False) before deploying to a real server.
    app.run(debug=True)