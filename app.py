import os
import sqlite3
from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from utils.model_utils import predict_price, predict_range, get_price_tag, get_top_feature_importance


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database", "vehiclestore.db")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__)
app.secret_key = "super_secret_key_change_me"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS listings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        vehicle_type TEXT NOT NULL,
        brand TEXT NOT NULL,
        model TEXT NOT NULL,
        year INTEGER NOT NULL,
        kms INTEGER NOT NULL,
        fuel_type TEXT NOT NULL,
        transmission TEXT NOT NULL,
        owner_count INTEGER NOT NULL,
        city TEXT NOT NULL,
        condition_score INTEGER NOT NULL,
        listed_price INTEGER NOT NULL,
        predicted_price INTEGER,
        price_tag TEXT,
        image TEXT,
        status TEXT NOT NULL DEFAULT 'PENDING',
        created_at TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    """)

    conn.commit()
    conn.close()


@app.route("/")
def home():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) as c FROM listings")
    total_listings = cur.fetchone()["c"]

    cur.execute("SELECT COUNT(*) as c FROM listings WHERE status='APPROVED'")
    approved_listings = cur.fetchone()["c"]

    cur.execute("SELECT COUNT(*) as c FROM listings WHERE status='PENDING'")
    pending_listings = cur.fetchone()["c"]

    cur.execute("SELECT COUNT(*) as c FROM listings WHERE status='APPROVED' AND price_tag='Underpriced'")
    underpriced = cur.fetchone()["c"]

    cur.execute("SELECT AVG(listed_price) as a FROM listings WHERE status='APPROVED'")
    avg_price = cur.fetchone()["a"]
    avg_price = int(avg_price) if avg_price else 0

    conn.close()

    return render_template(
        "home.html",
        total_listings=total_listings,
        approved_listings=approved_listings,
        pending_listings=pending_listings,
        underpriced=underpriced,
        avg_price=avg_price
    )


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        conn = get_db()
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO users(name, email, password_hash, created_at) VALUES(?,?,?,?)",
                (name, email, generate_password_hash(password), datetime.now().isoformat())
            )
            conn.commit()
            flash("Registration successful. Please login.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Email already exists.", "danger")
        finally:
            conn.close()

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE email=?", (email,))
        user = cur.fetchone()
        conn.close()

        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            flash("Login successful!", "success")
            return redirect(url_for("listings"))
        flash("Invalid credentials.", "danger")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.", "info")
    return redirect(url_for("home"))


@app.route("/predict", methods=["GET", "POST"])
def predict():
    if request.method == "POST":
        data = {
            "vehicle_type": request.form["vehicle_type"],
            "brand": request.form["brand"],
            "model": request.form["model"],
            "year": int(request.form["year"]),
            "kms": int(request.form["kms"]),
            "fuel_type": request.form["fuel_type"],
            "transmission": request.form["transmission"],
            "owner_count": int(request.form["owner_count"]),
            "city": request.form["city"],
            "condition_score": int(request.form["condition_score"])
        }

        predicted = predict_price(data)
        low, high, mae = predict_range(predicted)

        return render_template("result.html", form=data, predicted=predicted, low=low, high=high, mae=mae)

    return render_template("predict.html")


@app.route("/listings")
def listings():
    vehicle_type = request.args.get("vehicle_type", "").strip()
    city = request.args.get("city", "").strip()
    min_price = request.args.get("min_price", "").strip()
    max_price = request.args.get("max_price", "").strip()
    sort = request.args.get("sort", "").strip()

    query = "SELECT * FROM listings WHERE status='APPROVED'"
    params = []

    if vehicle_type:
        query += " AND vehicle_type=?"
        params.append(vehicle_type)

    if city:
        query += " AND city=?"
        params.append(city)

    if min_price:
        query += " AND listed_price >= ?"
        params.append(int(min_price))

    if max_price:
        query += " AND listed_price <= ?"
        params.append(int(max_price))

    if sort == "low":
        query += " ORDER BY listed_price ASC"
    elif sort == "high":
        query += " ORDER BY listed_price DESC"
    else:
        query += " ORDER BY id DESC"

    conn = get_db()
    cur = conn.cursor()
    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()

    return render_template(
        "listings.html",
        listings=rows,
        vehicle_type=vehicle_type,
        city=city,
        min_price=min_price,
        max_price=max_price,
        sort=sort
    )


@app.route("/listing/<int:lid>")
def listing_detail(lid):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT l.*, u.name as seller
        FROM listings l
        JOIN users u ON l.user_id = u.id
        WHERE l.id=?
    """, (lid,))
    row = cur.fetchone()
    conn.close()

    low = high = mae = None
    if row and row["predicted_price"]:
        low, high, mae = predict_range(int(row["predicted_price"]))

    return render_template("listings_detail.html", listing=row, low=low, high=high, mae=mae)


@app.route("/post", methods=["GET", "POST"])
def post_listing():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        vehicle_type = request.form["vehicle_type"]
        brand = request.form["brand"]
        model_name = request.form["model"]
        year = int(request.form["year"])
        kms = int(request.form["kms"])
        fuel_type = request.form["fuel_type"]
        transmission = request.form["transmission"]
        owner_count = int(request.form["owner_count"])
        city = request.form["city"]
        condition_score = int(request.form["condition_score"])
        listed_price = int(request.form["listed_price"])

        image_file = request.files.get("image")
        filename = None
        if image_file and image_file.filename:
            filename = secure_filename(image_file.filename)
            image_file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

        form_data = {
            "vehicle_type": vehicle_type,
            "brand": brand,
            "model": model_name,
            "year": year,
            "kms": kms,
            "fuel_type": fuel_type,
            "transmission": transmission,
            "owner_count": owner_count,
            "city": city,
            "condition_score": condition_score
        }

        predicted = predict_price(form_data)
        tag = get_price_tag(listed_price, predicted)

        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO listings(
                user_id, vehicle_type, brand, model, year, kms,
                fuel_type, transmission, owner_count, city, condition_score,
                listed_price, predicted_price, price_tag, image, status, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session["user_id"], vehicle_type, brand, model_name, year, kms,
            fuel_type, transmission, owner_count, city, condition_score,
            listed_price, predicted, tag, filename, "PENDING",
            datetime.now().isoformat()
        ))
        conn.commit()
        conn.close()

        flash("Listing posted! Waiting for admin approval.", "success")
        return redirect(url_for("listings"))

    return render_template("post_listing.html")


@app.route("/insights")
def insights():
    top = get_top_feature_importance(10)
    return render_template("insights.html", top=top)


@app.route("/admin", methods=["GET", "POST"])
def admin():
    ADMIN_PASS = "admin123"
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASS:
            session["admin"] = True
            return redirect(url_for("admin_dashboard"))
        flash("Wrong admin password", "danger")
    return render_template("admin_login.html")


@app.route("/admin/dashboard")
def admin_dashboard():
    if not session.get("admin"):
        return redirect(url_for("admin"))

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT l.*, u.name as seller 
        FROM listings l
        JOIN users u ON l.user_id = u.id
        WHERE l.status='PENDING'
        ORDER BY l.id DESC
    """)
    pending = cur.fetchall()
    conn.close()

    return render_template("admin_dashboard.html", pending=pending)


@app.route("/admin/action/<int:lid>/<string:action>")
def admin_action(lid, action):
    if not session.get("admin"):
        return redirect(url_for("admin"))

    if action not in ["APPROVED", "REJECTED"]:
        flash("Invalid action", "danger")
        return redirect(url_for("admin_dashboard"))

    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE listings SET status=? WHERE id=?", (action, lid))
    conn.commit()
    conn.close()

    flash(f"Listing {action.lower()}!", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    flash("Admin logged out", "info")
    return redirect(url_for("home"))


if __name__ == "__main__":
    init_db()
    app.run(debug=True)