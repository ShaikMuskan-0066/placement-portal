from datetime import timedelta

from flask import Flask, flash, redirect, render_template, request, session, url_for
import sqlite3
import os

from auth import (
    current_user_id,
    current_username,
    experience_owned_by_session,
    is_logged_in,
    login_required,
    login_user,
    logout_user,
    safe_login_redirect,
)
from database import (
    init_db,
    get_user_by_credentials,
    create_user,
    delete_experience_for_user,
    fetch_queries,
    fetch_experience_count_by_company,
    fetch_all_experiences,
    fetch_experiences_for_user,
    get_experience_by_id,
    insert_experience,
    insert_query,
    get_query_for_answer,
    save_query_answer,
    update_experience,
)


def create_app():
    app = Flask(__name__)
    secret = os.environ.get("PLACEMENTOR_SECRET")
    if os.environ.get("RENDER") and not secret:
        raise RuntimeError("Set PLACEMENTOR_SECRET in the Render dashboard (Environment).")
    app.secret_key = secret or "dev-secret-key"
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=7)

    # Production (e.g. Render HTTPS): send session cookie only over TLS
    if os.environ.get("RENDER"):
        app.config["SESSION_COOKIE_SECURE"] = True

    init_db()

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if is_logged_in():
            return redirect(url_for("dashboard"))

        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "").strip()

            user = get_user_by_credentials(username, password)
            if user:
                login_user(user["id"], user["username"])
                flash("Logged in successfully.", "success")
                next_raw = request.form.get("next") or request.args.get("next")
                next_path = safe_login_redirect(next_raw)
                return redirect(next_path or url_for("dashboard"))
            flash("Invalid username or password.", "error")

        return render_template("login.html")

    @app.route("/signup", methods=["GET", "POST"])
    def signup():
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "").strip()

            if not username or not password:
                flash("Username and password are required.", "error")
                return render_template("signup.html")

            try:
                create_user(username, password)
            except sqlite3.IntegrityError:
                flash("Username already exists. Choose another one.", "error")
                return render_template("signup.html")

            flash("Signup successful. Please log in.", "success")
            return redirect(url_for("login"))

        return render_template("signup.html")

    @app.route("/dashboard")
    @login_required
    def dashboard():
        recent_queries = fetch_queries(limit=6)
        return render_template(
            "dashboard.html",
            username=current_username(),
            recent_queries=recent_queries,
        )

    @app.route("/senior")
    @login_required
    def senior():
        username = session["username"]
        my_experiences = fetch_experiences_for_user(username)
        queries = fetch_queries(unanswered_first=True)
        return render_template(
            "senior.html",
            queries=queries,
            my_experiences=my_experiences,
        )

    @app.route("/junior")
    def junior():
        experiences = fetch_all_experiences()
        queries = fetch_queries()
        chart_labels, chart_counts = fetch_experience_count_by_company()
        chart_data = {"labels": chart_labels, "counts": chart_counts}
        return render_template(
            "junior.html",
            experiences=experiences,
            queries=queries,
            chart_data=chart_data,
        )

    @app.route("/view/<int:experience_id>")
    def view_experience(experience_id):
        exp = get_experience_by_id(experience_id)
        if exp is None:
            flash("Experience not found.", "error")
            return redirect(url_for("junior"))
        return render_template(
            "view.html", exp=exp, logged_in=is_logged_in()
        )

    @app.route("/upload", methods=["GET", "POST"])
    @login_required
    def upload():
        if request.method == "POST":
            senior_name = request.form.get("senior_name", "").strip()
            company = request.form.get("company", "").strip()
            passout_raw = request.form.get("passout_year", "").strip()
            role = request.form.get("role", "").strip()
            questions = request.form.get("questions", "").strip()
            prep = request.form.get("prep", "").strip()
            courses = request.form.get("courses", "").strip()

            if not senior_name or not company or not role:
                flash("Name, company, and role are required.", "error")
                return render_template("upload.html")

            try:
                passout_year = int(passout_raw)
            except ValueError:
                flash("Pass-out year must be a valid number.", "error")
                return render_template("upload.html")

            if passout_year < 1990 or passout_year > 2035:
                flash("Pass-out year must be between 1990 and 2035.", "error")
                return render_template("upload.html")

            owner = session["username"]
            insert_experience(
                senior_name,
                company,
                passout_year,
                role,
                questions,
                prep,
                courses,
                owner,
            )
            flash("Experience uploaded successfully.", "success")
            return redirect(url_for("senior"))

        return render_template("upload.html")

    @app.route("/edit/<int:experience_id>", methods=["GET", "POST"])
    @login_required
    def edit_experience(experience_id):
        exp = get_experience_by_id(experience_id)
        if exp is None:
            flash("Experience not found.", "error")
            return redirect(url_for("senior"))

        if not experience_owned_by_session(exp):
            flash("You can only edit your own experiences.", "error")
            return redirect(url_for("senior"))

        if request.method == "POST":
            senior_name = request.form.get("senior_name", "").strip()
            company = request.form.get("company", "").strip()
            passout_raw = request.form.get("passout_year", "").strip()
            role = request.form.get("role", "").strip()
            questions = request.form.get("questions", "").strip()
            prep = request.form.get("prep", "").strip()
            courses = request.form.get("courses", "").strip()

            if not senior_name or not company or not role:
                flash("Name, company, and role are required.", "error")
                return render_template("edit.html", exp=exp)

            try:
                passout_year = int(passout_raw)
            except ValueError:
                flash("Pass-out year must be a valid number.", "error")
                return render_template("edit.html", exp=exp)

            if passout_year < 1990 or passout_year > 2035:
                flash("Pass-out year must be between 1990 and 2035.", "error")
                return render_template("edit.html", exp=exp)

            owner = session["username"]
            updated = update_experience(
                experience_id,
                owner,
                senior_name,
                company,
                passout_year,
                role,
                questions,
                prep,
                courses,
            )
            if not updated:
                flash("Could not update experience.", "error")
                return render_template("edit.html", exp=exp)

            flash("Experience updated.", "success")
            return redirect(url_for("senior"))

        return render_template("edit.html", exp=exp)

    @app.route("/delete/<int:id>", methods=["POST"])
    @login_required
    def delete_experience(id):
        """Remove one experience row from database.db; only the owning session user may delete."""
        exp = get_experience_by_id(id)
        if exp is None:
            flash("Experience not found.", "error")
            return redirect(url_for("senior"))

        if not experience_owned_by_session(exp):
            flash("You can only delete your own experiences.", "error")
            return redirect(url_for("senior"))

        delete_experience_for_user(id, session["username"])
        flash("Experience deleted.", "success")
        return redirect(url_for("senior"))

    @app.route("/queries/ask", methods=["GET", "POST"])
    @login_required
    def query_ask():
        uid = current_user_id()
        if uid is None:
            return redirect(url_for("login"))

        if request.method == "POST":
            text = request.form.get("question", "").strip()
            if not text:
                flash("Question cannot be empty.", "error")
                return render_template("query_ask.html")

            insert_query(text, uid)
            flash("Your question was posted.", "success")
            return redirect(url_for("junior"))

        return render_template("query_ask.html")

    @app.route("/queries/<int:query_id>/answer", methods=["GET", "POST"])
    @login_required
    def query_answer(query_id):
        uid = current_user_id()
        if uid is None:
            return redirect(url_for("login"))

        row = get_query_for_answer(query_id)
        if not row:
            flash("Question not found.", "error")
            return redirect(url_for("senior"))

        if row["answer"] and str(row["answer"]).strip():
            flash("This question already has an answer.", "error")
            return redirect(url_for("senior"))

        if request.method == "POST":
            answer_text = request.form.get("answer", "").strip()
            if not answer_text:
                flash("Answer cannot be empty.", "error")
                return render_template("query_answer.html", q=row)

            save_query_answer(query_id, answer_text, uid)
            flash("Answer saved.", "success")
            return redirect(url_for("senior"))

        return render_template("query_answer.html", q=row)

    @app.route("/logout")
    def logout():
        logout_user()
        flash("Logged out successfully.", "success")
        return redirect(url_for("index"))

    return app


# WSGI entry for Gunicorn (Procfile: gunicorn app:app)
app = create_app()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port, debug=False)
