"""Session-based authentication helpers and route protection."""

from __future__ import annotations

from functools import wraps
from urllib.parse import urlparse

from flask import flash, redirect, request, session, url_for

SESSION_USER_ID = "user_id"
SESSION_USERNAME = "username"


def is_logged_in() -> bool:
    """Valid session must include username (and user_id set at login)."""
    return (
        SESSION_USERNAME in session
        and session.get(SESSION_USERNAME)
        and SESSION_USER_ID in session
    )


def current_user_id() -> int | None:
    return session.get(SESSION_USER_ID)


def current_username() -> str | None:
    return session.get(SESSION_USERNAME)


def login_user(user_id: int, username: str) -> None:
    session.clear()
    session.permanent = True
    session[SESSION_USER_ID] = user_id
    session[SESSION_USERNAME] = username


def logout_user() -> None:
    session.clear()


def safe_login_redirect(url: str | None) -> str | None:
    """Allow only same-site relative paths after login (blocks open redirects)."""
    if not url:
        return None
    parsed = urlparse(url)
    if parsed.scheme or parsed.netloc:
        return None
    path = parsed.path or ""
    if not path.startswith("/") or path.startswith("//"):
        return None
    return path + (f"?{parsed.query}" if parsed.query else "")


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if SESSION_USERNAME not in session:
            flash("Please log in to continue.", "error")
            return redirect(url_for("login", next=request.path))
        if not session.get(SESSION_USERNAME):
            session.clear()
            flash("Please log in to continue.", "error")
            return redirect(url_for("login", next=request.path))
        if SESSION_USER_ID not in session:
            session.clear()
            flash("Session expired. Please log in again.", "error")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


def experience_owned_by_session(exp) -> bool:
    """True if sqlite Row experience belongs to the logged-in user (user column vs session username)."""
    if exp is None:
        return False
    name = session.get(SESSION_USERNAME)
    if not name:
        return False
    try:
        owner = exp["user"]
    except (KeyError, IndexError, TypeError):
        return False
    if owner is None:
        return False
    return str(owner).strip() == str(name).strip()
