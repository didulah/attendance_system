# Fingerprint Attendance System (Mock/Demo)

A small Flask + SQLite web app for recording and viewing student attendance.
The fingerprint scanner is simulated — attendance is marked manually through
the Update page, but the UI is designed to be swapped for real scanner
hardware later without changing the database structure.

## Project structure

```
attendance_system/
├── app.py                  Flask application (routes, login, logic)
├── database_setup.py       Creates project.db with sample data
├── requirements.txt        Python dependencies
├── templates/              HTML pages (Jinja2)
│   ├── base.html
│   ├── login.html
│   ├── home.html
│   ├── student_info.html
│   ├── stats.html
│   ├── update.html
│   └── report.html
└── static/
    └── css/
        └── style.css
```

## Running locally

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Create the database (only needed once, or whenever you want a fresh start):
   ```
   python database_setup.py
   ```

3. Run the app:
   ```
   python app.py
   ```

4. Open http://127.0.0.1:5000 in a browser.

   Demo login: `admin` / `1234`
   Demo student IDs: `249001`, `249002`, `249003`

## Before deploying to a real server

- Set a real `SECRET_KEY` as an environment variable (do not hardcode it).
- Change `app.run(debug=True)` to `debug=False` in `app.py`.
- Make sure `project.db` is stored somewhere that persists between restarts
  (see hosting notes below — some free hosting tiers wipe the filesystem).

## Deploying (suggested: PythonAnywhere)

1. Push this project to a GitHub repository (see `.gitignore` — it already
   excludes `project.db` and `.env`, so each environment creates its own).
2. On PythonAnywhere: create a new Web App (Flask), then open a Bash console
   and clone your GitHub repo.
3. Install dependencies inside that console: `pip install -r requirements.txt`.
4. Run `python database_setup.py` once on the server to create `project.db`.
5. In the Web tab, set the `SECRET_KEY` environment variable, and point the
   WSGI file to your `app.py`'s `app` object.
6. Reload the web app — it will be live at `https://<yourusername>.pythonanywhere.com`.