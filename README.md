# HireHub: Connecting Students to Placement Success

HireHub is a Flask web app where seniors share placement experiences and juniors explore interviews, prep, and Q&A—built with SQLite, session auth, and a modern glass-style UI.

## Run locally

```bash
pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:10000` (or the port shown in the terminal).

## Environment

- **`PLACEMENTOR_SECRET`**: Flask session secret (required on Render; use a long random string in production).

## Deploy
Live Demo: https://placement-portal-cg3f.onrender.com/

See `requirements.txt`, `Procfile`, and Render environment variables for production deployment.
