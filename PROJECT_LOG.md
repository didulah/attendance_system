# Attendance System — Development Log

A record of the design decisions, architecture, bugs fixed, and deployment
steps taken while rebuilding the Fingerprint Attendance System (mock/demo)
from scratch.

---

## 1. Project Overview

A Flask + SQLite web application for recording and viewing student
attendance. The fingerprint scanner itself is **simulated** — attendance is
marked manually through an Update page — but the architecture is designed so
real scanner hardware can be plugged in later without restructuring the app.

**Stack decisions (confirmed with the project owner):**
- Backend: Flask (Python) — same as the original prototype
- Database: SQLite — same as the original prototype
- Frontend: Multiple server-rendered HTML pages (Jinja2), not a JS single-page app
- Login: Server-side session-based authentication

---

## 2. Why the Project Was Rebuilt

The original prototype (single `index.html` with embedded JS, plus a
Flask `app.py`) had accumulated several issues:

| Issue | Problem |
|---|---|
| `students` object referenced in JS | Was never defined — "More" and "Update" pages threw `students is not defined` and were completely broken |
| Report showed `lecId` as "Date" | The attendance table has no date column; date lives in `lecture` table and was never joined |
| No backend logic for statistics | Total/late/present counts were only attempted client-side, against the missing `students` object |
| Login was client-side only | Hardcoded `admin`/`1234` check in JavaScript — no real security |
| Unused "Lecturer ID" field | Present in the UI but never used by any route |
| `attendence` table name | Misspelled, and had no auto-increment primary key, making duplicate records possible |

Rather than patch these individually, the project was rebuilt from a clean
folder structure while keeping the original idea, tech stack, and general
database design.

---

## 3. Database Schema (`database_setup.py`)

```
users        (id, username, password_hash)
student      (stId, stName)
lecture      (lecId, lecDate, startTime, endTime, lecTitle)
attendance   (id, stId, lecId, attendedTime, status)
```

Key changes from the original schema:
- Added `users` table for server-side login (passwords stored as hashes via
  `werkzeug.security.generate_password_hash`, never as plain text).
- `lecture.lecId` is now auto-increment (previously entered manually).
- `attendance` (spelling fixed from `attendence`) has its own auto-increment
  `id`, so a student/lecture pair can be safely looked up and updated instead
  of accumulating duplicate rows.
- `status` defaults to `'absent'` if not specified.

The script drops and recreates `project.db` from scratch and inserts demo
data: one login (`admin` / `1234`), three students, three lectures, and a
handful of attendance records.

---

## 4. Application Routes (`app.py`)

| Route | Method | Purpose |
|---|---|---|
| `/` | GET | Redirect to `/home` or `/login` depending on session |
| `/login` | GET/POST | Show login form; validate against `users` table |
| `/logout` | GET | Clear session |
| `/home` | GET/POST | Student ID search box; POST redirects to `/student/<id>` |
| `/student/<id>` | GET | Student details + latest attendance record |
| `/stats/<id>` | GET | Total / present / late counts for one student |
| `/update/<id>` | GET/POST | Mark attendance for a student against a chosen lecture (insert-or-update, not duplicate) |
| `/reports` | GET | Choose a lecture for a report |
| `/reports/go` | GET | Reads `lecId` query param, redirects to the report |
| `/reports/<lec_id>` | GET | **All students'** attendance for one lecture (see §6) |

All routes except `/`, `/login`, and `/logout` are protected by a
`@login_required` decorator that checks `session["user"]`.

**Late rule (demo):** a `present` record with `attendedTime` after 08:00 is
counted as late. This is a placeholder business rule, easy to change in one
place (`_is_late()`).

---

## 5. Frontend Structure

```
templates/
├── base.html            Shared layout: <head>, nav bar, flash messages
├── login.html            Extends base — no nav bar shown
├── home.html              Student ID search
├── student_info.html      Latest attendance + links to stats/update
├── stats.html             Total/present/late counts
├── update.html            Lecture dropdown + present/absent + reason
├── reports_select.html    Choose a lecture for a report
└── reports_view.html      All students' attendance for that lecture

static/css/style.css       Shared stylesheet
```

**Design theme:** deep teal (`#2f6f63`) + warm amber accent (`#c98a3e`) on a
soft neutral background, serif headings (Source Serif 4) for a scholarly
feel, monospace for IDs. A single signature element — a quiet
fingerprint-ridge SVG motif — appears once, on the login card, as a nod to
the biometric theme without using literal clipart icons.

---

## 6. Feature Change: Report Redesign

**Original design:** report showed one student's attendance across all
lectures.

**Revised design (requested mid-project):** report shows **all students'**
attendance for **one chosen lecture**, because that's how a lecturer
actually wants to review a session.

Implementation used a `LEFT JOIN` so students with no attendance record for
the selected lecture still appear, labelled distinctly:

```sql
SELECT s.stId, s.stName, a.attendedTime, a.status
FROM student s
LEFT JOIN attendance a ON a.stId = s.stId AND a.lecId = ?
ORDER BY s.stName
```

Three status states are shown: `present`, `absent`, and **`not marked yet`**
(when the `LEFT JOIN` produces `NULL` — no attendance row exists yet for
that student/lecture pair).

The old per-student `/report/<id>` route and `report.html` were removed and
replaced by the lecture-based `/reports` flow, reachable from a "Reports"
link in the top nav bar.

---

## 7. Security Practices Applied

- Passwords hashed with `werkzeug.security` — never stored or compared in
  plain text.
- `app.secret_key` loaded from an environment variable via `python-dotenv`
  (`.env` file), not hardcoded in source.
- `.env` and `project.db` are both in `.gitignore` — secrets and
  environment-specific data are never pushed to GitHub. (`project.db` was
  accidentally committed early on and had to be removed with
  `git rm --cached project.db`.)
- All data-viewing/editing routes require an active login session
  (`@login_required`).
- `debug=True` is explicitly marked as local-development-only in the code
  comments; must be `False` in production.

---

## 8. Deployment Issues Hit & Fixed

| Symptom | Root cause | Fix |
|---|---|---|
| `UnicodeEncodeError` on Windows terminal | Sinhala characters inside `print()`/comments; Windows console defaults to `cp1252` | Rewrote all code comments/print statements in English |
| `ModuleNotFoundError: No module named 'dotenv'` | `python-dotenv` used in code but not installed / not in `requirements.txt` | `pip install python-dotenv`; added to `requirements.txt` |
| `jinja2.exceptions.TemplateNotFound` (several times) | Routes were built before their templates existed (expected, step-by-step build) | Created each missing template in turn |
| GitHub repo still contained `project.db` despite `.gitignore` | `.gitignore` only affects *untracked* files; the db had been committed before `.gitignore` was added | `git rm --cached project.db` + commit |
| `sqlite3.OperationalError: no such table: users` on PythonAnywhere | `DB_NAME = "project.db"` was a **relative path**; the WSGI process's working directory differs from where `database_setup.py` was run, so Flask silently created a new, empty database file elsewhere | Changed to an absolute path: `os.path.join(os.path.dirname(os.path.abspath(__file__)), "project.db")` in both `app.py` and `database_setup.py` |

---

## 9. Git Workflow Used

A feature-branch workflow was adopted partway through:

```
main        stable, working code
  └── branch1   experimental changes, merged into main once verified
```

```bash
git checkout main
git merge branch1
git push
```

---

## 10. Deploying to PythonAnywhere (steps followed)

1. Create a PythonAnywhere account and a new Flask web app.
2. In a Bash console: `git clone <repo-url>`, `cd attendance_system`.
3. `pip install --user -r requirements.txt`.
4. `python database_setup.py` (creates `project.db` on the server, since it's
   git-ignored and not part of the repo).
5. Create a `.env` file on the server with a **real, randomly generated**
   `SECRET_KEY` (not a placeholder string) — e.g.
   `python3 -c "import secrets; print(secrets.token_hex(32))"`.
6. Edit the WSGI configuration file to point to the project path and import
   `app` as `application`.
7. Set the static files mapping: URL `/static/` → project's `static/` folder.
8. Reload the web app from the "Web" tab.

---

## 11. Discussed but Not Yet Built

These were explained at the architecture level; code has not been written
for them yet.

**Fingerprint enrollment (software side only, no hardware available):**
- Add `fingerprint_template BLOB` column to `student` table.
- New `/enroll` route + `enroll.html`: enter new student ID/name, then a
  "Scan Fingerprint" action. Without real hardware, this would be mocked
  (generate a placeholder template) so the architecture is ready to swap in
  a real scanner SDK later without touching the rest of the app.

**Multiple lecturer logins:**
- No code changes needed to `login()` — it already checks any row in the
  `users` table. Only requires inserting additional rows (username +
  `generate_password_hash(...)`), e.g. via a small script or a future
  "Add User" admin page.

---

## 12. Useful Commands Reference

```bash
# Local development
pip install -r requirements.txt
python database_setup.py     # (re)creates project.db with sample data
python app.py                 # runs the dev server at 127.0.0.1:5000

# Git
git add .
git commit -m "message"
git push
git rm --cached <file>        # stop tracking a file without deleting it locally

# Generate a real secret key
python3 -c "import secrets; print(secrets.token_hex(32))"
```