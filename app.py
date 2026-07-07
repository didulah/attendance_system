"""
app.py
------
Flask backend for the Fingerprint Attendance System.

Browser routes (session-based login, @login_required):
GET  /               -> redirect to /home if logged in, else show login page
GET  /login          -> show login form
POST /login          -> validate credentials, start session
GET  /logout         -> clear session, back to login
GET  /home           -> search box to enter a Student ID
POST /home           -> redirect to /student/<id>
GET  /student/<id>   -> show student info + latest attendance
GET  /stats/<id>     -> show attendance statistics (total/present/late)
GET  /update/<id>    -> show form to mark attendance for a lecture
POST /update/<id>    -> save attendance record (insert or update)
GET  /reports        -> choose a lecture
GET  /reports/go     -> redirect to /reports/<lec_id>
GET  /reports/<id>   -> printable report for one lecture, all students
GET  /report/<id>    -> printable full attendance history for one student
GET/POST /enroll     -> admin page: queue a fingerprint enrollment job

Device routes (ESP32, API-key auth, NOT session-based):
POST /api/mark_attendance -> device sends {fingerprint_id, lecId}
GET  /api/enroll/next     -> device polls for the next enrollment job
POST /api/enroll/confirm  -> device reports enrollment success/failure
"""

import os
import sqlite3
from functools import wraps
from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import check_password_hash
from dotenv import load_dotenv

# Load variables from a local .env file (if one exists) into the environment.
# This file is git-ignored, so secrets never get pushed to GitHub.
load_dotenv()

app = Flask(__name__)

# Secret key is needed for session/cookies to work.
# Always comes from an environment variable - never hardcode the real value here.
# On PythonAnywhere (or any host), set SECRET_KEY in that platform's
# environment variable settings instead of using a .env file.
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-this")

# API key used by the ESP32 device to call the /api/* routes.
# The ESP32 sends this in an "X-API-Key" header on every request.
# Set DEVICE_API_KEY as an environment variable on PythonAnywhere
# (same way SECRET_KEY is set) - never hardcode the real value.
DEVICE_API_KEY = os.environ.get("DEVICE_API_KEY", "dev-device-key-change-this","your-esp32-shared-secret-here")

DB_NAME = os.path.join(os.path.dirname(os.path.abspath(__file__)), "project.db")


def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------
# Decorator: protects browser routes that require login
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
# Decorator: protects device (ESP32) routes with an API key
# instead of a session cookie, since the ESP32 cannot easily
# maintain browser-style sessions.
# ---------------------------------------------------------
def api_key_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        key = request.headers.get("X-API-Key", "")
        if key != DEVICE_API_KEY:
            return jsonify({"error": "unauthorized"}), 401
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


def _mark_attendance(st_id, lec_id, att_status):
    """
    Shared insert-or-update logic for marking attendance.
    Used by both the browser /update route and the device
    /api/mark_attendance route, so both stay consistent.
    Returns the attendedTime that was stored (or None).
    """
    conn = get_db()
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
    return attended_time


# ---------------------------------------------------------
# Update / mark attendance page (manual, from the browser)
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

        conn.close()
        _mark_attendance(st_id, lec_id, att_status)
        flash("Attendance record saved" + (f" (reason: {reason})" if reason else ""))
        return redirect(url_for("student_info", st_id=st_id))

    lectures = conn.execute(
        "SELECT * FROM lecture ORDER BY lecDate DESC"
    ).fetchall()
    conn.close()

    return render_template("update.html", student=student, lectures=lectures)


# ---------------------------------------------------------
# Reports: choose a lecture, then see every student's
# attendance status for that lecture.
# ---------------------------------------------------------
@app.route("/reports")
@login_required
def reports_select():
    conn = get_db()
    lectures = conn.execute(
        "SELECT * FROM lecture ORDER BY lecDate DESC"
    ).fetchall()
    conn.close()
    return render_template("reports_select.html", lectures=lectures)


@app.route("/reports/go")
@login_required
def reports_go():
    lec_id = request.args.get("lecId")
    if not lec_id:
        flash("Please choose a lecture.")
        return redirect(url_for("reports_select"))
    return redirect(url_for("reports_view", lec_id=lec_id))


@app.route("/reports/<int:lec_id>")
@login_required
def reports_view(lec_id):
    conn = get_db()
    lecture = conn.execute(
        "SELECT * FROM lecture WHERE lecId = ?", (lec_id,)
    ).fetchone()

    if lecture is None:
        conn.close()
        flash(f"No lecture found with ID {lec_id}.")
        return redirect(url_for("reports_select"))

    # LEFT JOIN so students with no attendance record for this lecture
    # still appear in the report, with status = NULL ("not marked yet").
    rows = conn.execute(
        """
        SELECT s.stId, s.stName, a.attendedTime, a.status
        FROM student s
        LEFT JOIN attendance a ON a.stId = s.stId AND a.lecId = ?
        ORDER BY s.stName
        """,
        (lec_id,),
    ).fetchall()
    conn.close()

    return render_template("reports_view.html", lecture=lecture, rows=rows)


# ===========================================================
# FINGERPRINT ENROLLMENT (admin page) - Flask side, phase 1
# ===========================================================
@app.route("/enroll", methods=["GET", "POST"])
@login_required
def enroll():
    conn = get_db()

    if request.method == "POST":
        st_id = request.form.get("stId", "").strip()

        student = conn.execute(
            "SELECT * FROM student WHERE stId = ?", (st_id,)
        ).fetchone()

        if student is None:
            conn.close()
            flash(f"No student found with ID {st_id}.")
            return redirect(url_for("enroll"))

        if student["fingerprint_id"] is not None:
            conn.close()
            flash(f"Student {st_id} already has a fingerprint slot ({student['fingerprint_id']}).")
            return redirect(url_for("enroll"))

        # Next free slot number = 1 higher than the highest slot in use.
        # The R307S has room for ~1000 templates (slots 1-999 here).
        max_slot = conn.execute(
            "SELECT MAX(fingerprint_id) AS m FROM student"
        ).fetchone()["m"]
        next_slot = (max_slot or 0) + 1

        conn.execute(
            "INSERT INTO enroll_queue (stId, fingerprint_id, status) VALUES (?, ?, 'pending')",
            (st_id, next_slot),
        )
        conn.commit()
        conn.close()

        flash(f"Enrollment job queued for student {st_id} -> slot {next_slot}. "
              f"Ask them to scan their finger at the device when it prompts.")
        return redirect(url_for("enroll"))

    # GET: show the queue-a-job form + current job list
    jobs = conn.execute(
        """
        SELECT eq.*, s.stName
        FROM enroll_queue eq
        JOIN student s ON s.stId = eq.stId
        ORDER BY eq.created_at DESC
        """
    ).fetchall()

    # students without a fingerprint slot yet, for the dropdown
    unenrolled = conn.execute(
        "SELECT * FROM student WHERE fingerprint_id IS NULL ORDER BY stName"
    ).fetchall()
    conn.close()

    return render_template("enroll.html", jobs=jobs, unenrolled=unenrolled)


# ===========================================================
# DEVICE API (ESP32) - API-key auth, no session/cookies
# ===========================================================

@app.route("/api/mark_attendance", methods=["POST"])
@api_key_required
def api_mark_attendance():
    """
    Called by the ESP32 after the R307S sensor matches a fingerprint.
    Expects JSON: {"fingerprint_id": <int>, "lecId": <int>}
    The sensor already did the matching - it just tells us which slot
    matched, so we look up which student owns that slot.
    """
    data = request.get_json(silent=True) or {}
    fingerprint_id = data.get("fingerprint_id")
    lec_id = data.get("lecId")

    if fingerprint_id is None or lec_id is None:
        return jsonify({"error": "fingerprint_id and lecId are required"}), 400

    conn = get_db()
    student = conn.execute(
        "SELECT * FROM student WHERE fingerprint_id = ?", (fingerprint_id,)
    ).fetchone()
    conn.close()

    if student is None:
        return jsonify({"error": "no student enrolled with this fingerprint_id"}), 404

    attended_time = _mark_attendance(student["stId"], lec_id, "present")

    return jsonify({
        "stId": student["stId"],
        "stName": student["stName"],
        "status": "present",
        "time": attended_time,
    })


@app.route("/api/enroll/next", methods=["GET"])
@api_key_required
def api_enroll_next():
    """
    Polled repeatedly by the ESP32 (e.g. every few seconds) to check
    whether the admin has queued a new enrollment job.
    Returns the OLDEST pending job, or {"job": null} if the queue is empty.
    """
    conn = get_db()
    job = conn.execute(
        """
        SELECT eq.id AS job_id, eq.stId, eq.fingerprint_id, s.stName
        FROM enroll_queue eq
        JOIN student s ON s.stId = eq.stId
        WHERE eq.status = 'pending'
        ORDER BY eq.created_at ASC
        LIMIT 1
        """
    ).fetchone()
    conn.close()

    if job is None:
        return jsonify({"job": None})

    return jsonify({"job": dict(job)})


@app.route("/api/enroll/confirm", methods=["POST"])
@api_key_required
def api_enroll_confirm():
    """
    Called by the ESP32 after it attempts an R307S enrollment scan.
    Expects JSON: {"job_id": <int>, "success": true/false}
    On success: student.fingerprint_id is set and the job is marked 'done'.
    On failure: the job is marked 'failed' so the admin can requeue it.
    """
    data = request.get_json(silent=True) or {}
    job_id = data.get("job_id")
    success = data.get("success")

    if job_id is None or success is None:
        return jsonify({"error": "job_id and success are required"}), 400

    conn = get_db()
    job = conn.execute(
        "SELECT * FROM enroll_queue WHERE id = ?", (job_id,)
    ).fetchone()

    if job is None:
        conn.close()
        return jsonify({"error": "job not found"}), 404

    if success:
        conn.execute(
            "UPDATE student SET fingerprint_id = ? WHERE stId = ?",
            (job["fingerprint_id"], job["stId"]),
        )
        conn.execute(
            "UPDATE enroll_queue SET status = 'done', completed_at = CURRENT_TIMESTAMP WHERE id = ?",
            (job_id,),
        )
    else:
        conn.execute(
            "UPDATE enroll_queue SET status = 'failed', completed_at = CURRENT_TIMESTAMP WHERE id = ?",
            (job_id,),
        )
    conn.commit()
    conn.close()

    return jsonify({"message": "recorded"})


if __name__ == "__main__":
    # debug=True is fine for local development only.
    # Turn this off (debug=False) before deploying to a real server.
    app.run(debug=True)