from flask import Flask, render_template, request, redirect, url_for, flash, session
import psycopg2
import psycopg2.extras
import os
import re

app = Flask(__name__)
app.secret_key = "dev-secret-key"

# ---------- DATABASE (POSTGRESQL) ----------
DATABASE_URL = os.environ.get("DATABASE_URL")

conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
conn.autocommit = True

# ---------- ADMIN CREDENTIALS ----------
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"

# ---------- USER LOGIN ----------
@app.route("/", methods=["GET", "POST"])
def user_login():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        mobile = request.form.get("mobile", "").strip()

        if not name:
            flash("Name is required", "error")
            return redirect(url_for("user_login"))

        if not re.fullmatch(r"\d{10}", mobile):
            flash("Enter valid 10-digit mobile number", "error")
            return redirect(url_for("user_login"))

        session["user_name"] = name
        session["user_mobile"] = mobile
        return redirect(url_for("user_dashboard"))

    return render_template("user_login.html")

# ---------- USER DASHBOARD ----------
@app.route("/dashboard")
def user_dashboard():
    if not session.get("user_mobile"):
        return redirect(url_for("user_login"))

    with conn.cursor() as cur:
        cur.execute("""
            SELECT id, issue_type, area, status
            FROM service_requests
            WHERE mobile = %s
            ORDER BY id DESC
        """, (session["user_mobile"],))
        requests_data = cur.fetchall()

    return render_template(
        "user_dashboard.html",
        user_name=session["user_name"],
        requests_data=requests_data
    )

# ---------- SUBMIT REQUEST ----------
@app.route("/submit", methods=["POST"])
def submit_request():
    if not session.get("user_mobile"):
        return redirect(url_for("user_login"))

    issue = request.form.get("issue")
    other_issue = request.form.get("other_issue", "").strip()
    area = request.form.get("area", "").strip()
    address = request.form.get("address", "").strip()
    description = request.form.get("description", "").strip()

    if not issue:
        flash("Select an issue type", "error")
        return redirect(url_for("user_dashboard"))

    if issue == "Other":
        if not other_issue:
            flash("Describe the other issue", "error")
            return redirect(url_for("user_dashboard"))
        issue = other_issue

    if not area or not description:
        flash("All fields are required", "error")
        return redirect(url_for("user_dashboard"))

    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO service_requests
            (citizen_name, mobile, issue_type, area, address, description, status)
            VALUES (%s, %s, %s, %s, %s, %s, 'Pending')
        """, (
            session["user_name"],
            session["user_mobile"],
            issue,
            area,
            address,
            description
        ))

    flash("Service request submitted successfully", "success")
    return redirect(url_for("user_dashboard"))

# ---------- USER LOGOUT ----------
@app.route("/logout")
def user_logout():
    session.clear()
    return redirect(url_for("user_login"))

# ---------- ADMIN LOGIN ----------
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        if (
            request.form.get("username") == ADMIN_USERNAME and
            request.form.get("password") == ADMIN_PASSWORD
        ):
            session["admin_logged_in"] = True
            return redirect(url_for("admin_dashboard"))

        flash("Invalid admin credentials", "error")

    return render_template("admin_login.html")

# ---------- ADMIN DASHBOARD ----------
@app.route("/admin")
def admin_dashboard():
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))

    with conn.cursor() as cur:
        cur.execute("SELECT * FROM service_requests ORDER BY id DESC")
        data = cur.fetchall()

    return render_template("admin_dashboard.html", data=data)

# ---------- UPDATE STATUS ----------
@app.route("/update_status", methods=["POST"])
def update_status():
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))

    req_id = request.form.get("id")
    status = request.form.get("status")

    with conn.cursor() as cur:
        cur.execute(
            "UPDATE service_requests SET status=%s WHERE id=%s",
            (status, req_id)
        )

    flash("Status updated successfully", "success")
    return redirect(url_for("admin_dashboard"))

# ---------- ADMIN LOGOUT ----------
@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))

# ---------- RUN ----------
if __name__ == "__main__":
    app.run()
