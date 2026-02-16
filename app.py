from flask import Flask, render_template, request, redirect, url_for, flash, session
import psycopg
from psycopg.rows import dict_row
import os
import re
from rl_agent import RLAgent

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key")

# ---------- DATABASE CONNECTION ----------
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is not set")

def get_conn():
    return psycopg.connect(
        DATABASE_URL,
        row_factory=dict_row
    )

# ---------- RL AGENT ----------
agent = RLAgent()

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

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, issue_type, area, status, priority
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

    with get_conn() as conn:
        with conn.cursor() as cur:

            # Count pending requests
            cur.execute("SELECT COUNT(*) as count FROM service_requests WHERE status='Pending'")
            pending_count = cur.fetchone()['count']

            # Define state
            state = agent.get_state(issue, area, pending_count)

            # Agent chooses priority
            priority = agent.choose_action(state)

            # Insert request with priority
            cur.execute("""
                INSERT INTO service_requests
                (citizen_name, mobile, issue_type, area, address, description, status, priority)
                VALUES (%s, %s, %s, %s, %s, %s, 'Pending', %s)
            """, (
                session["user_name"],
                session["user_mobile"],
                issue,
                area,
                address,
                description,
                priority
            ))

    flash(f"Service request submitted with {priority} priority", "success")
    return redirect(url_for("user_dashboard"))

# ---------- ADMIN DASHBOARD ----------
@app.route("/admin")
def admin_dashboard():
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))

    with get_conn() as conn:
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

    with get_conn() as conn:
        with conn.cursor() as cur:

            # Get request info before updating
            cur.execute("SELECT issue_type, area, priority FROM service_requests WHERE id=%s", (req_id,))
            row = cur.fetchone()

            issue = row["issue_type"]
            area = row["area"]
            priority = row["priority"]

            # Reward logic (simple simulation)
            reward = 0
            if status == "Approved" and priority == "High":
                reward = 10
            elif status == "Approved" and priority == "Medium":
                reward = 5
            elif status == "Rejected":
                reward = -5

            # Count pending for state
            cur.execute("SELECT COUNT(*) as count FROM service_requests WHERE status='Pending'")
            pending_count = cur.fetchone()['count']

            state = agent.get_state(issue, area, pending_count)

            # Update Q-table
            agent.update(state, priority, reward)

            # Update DB status
            cur.execute(
                "UPDATE service_requests SET status = %s WHERE id = %s",
                (status, req_id)
            )

    flash("Status updated and RL agent trained", "success")
    return redirect(url_for("admin_dashboard"))

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

# ---------- LOGOUTS ----------
@app.route("/logout")
def user_logout():
    session.clear()
    return redirect(url_for("user_login"))

@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))

# ---------- RUN ----------
if __name__ == "__main__":
    app.run()
