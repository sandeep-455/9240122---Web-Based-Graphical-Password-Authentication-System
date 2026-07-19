import json
import os
import random
import smtplib
import sqlite3
from email.message import EmailMessage
from datetime import datetime, timedelta

from cryptography.fernet import Fernet
from flask import Flask, redirect, render_template, request, session, url_for
from werkzeug.utils import secure_filename


app = Flask(__name__)
app.secret_key = "simple_graphical_password_secret"

DATABASE_NAME = "database.db"
UPLOAD_FOLDER = "static/uploads"
POINT_TOLERANCE = 3
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 465
SMTP_EMAIL = "client3105.tech@gmail.com"
SMTP_PASSWORD = "etbddqbqcdepwnli"
ENCRYPTION_KEY = b"l9mIrLuz5g6rG9XiQ0C6v9cYSWQAnvEET97sUnN226Y="

fernet = Fernet(ENCRYPTION_KEY)


def create_folder():
    # This folder stores images uploaded by users.
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def get_connection():
    # This function opens a connection with the SQLite database.
    connection = sqlite3.connect(DATABASE_NAME)
    connection.row_factory = sqlite3.Row
    return connection


def create_table():
    # This table stores one graphical password for each username.
    connection = get_connection()
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            email TEXT,
            image_name TEXT,
            point_count INTEGER,
            points TEXT
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            event_name TEXT,
            event_time TEXT
        )
        """
    )
    connection.commit()
    connection.close()


def add_email_column():
    # This adds the email column if the old database table does not have it.
    connection = get_connection()
    table_info = connection.execute("PRAGMA table_info(users)").fetchall()
    column_names = []

    for column in table_info:
        column_names.append(column["name"])

    if "email" not in column_names:
        connection.execute("ALTER TABLE users ADD COLUMN email TEXT")
        connection.commit()

    connection.close()


def encrypt_data(data):
    # This changes normal text into encrypted text before saving in SQLite.
    data_bytes = data.encode()
    encrypted_bytes = fernet.encrypt(data_bytes)
    encrypted_text = encrypted_bytes.decode()
    return encrypted_text


def is_encrypted(data):
    # Fernet encrypted text normally starts with this value.
    if data and data.startswith("gAAAAA"):
        return True

    return False


def decrypt_data(data):
    # Old plain records are returned as they are, and new records are decrypted.
    if is_encrypted(data):
        data_bytes = data.encode()
        decrypted_bytes = fernet.decrypt(data_bytes)
        decrypted_text = decrypted_bytes.decode()
        return decrypted_text

    return data


def decrypt_user(user):
    # This makes encrypted database values usable inside the application.
    if not user:
        return user

    decrypted_user = {}
    decrypted_user["id"] = user["id"]
    decrypted_user["username"] = user["username"]
    decrypted_user["email"] = decrypt_data(user["email"])
    decrypted_user["image_name"] = decrypt_data(user["image_name"])
    decrypted_user["point_count"] = user["point_count"]
    decrypted_user["points"] = decrypt_data(user["points"])
    return decrypted_user


def save_user(username, email, image_name, point_count, points):
    # User details are encrypted before saving in SQLite.
    points_text = json.dumps(points)
    encrypted_email = encrypt_data(email)
    encrypted_image_name = encrypt_data(image_name)
    encrypted_points = encrypt_data(points_text)

    connection = get_connection()
    connection.execute(
        "INSERT INTO users (username, email, image_name, point_count, points) VALUES (?, ?, ?, ?, ?)",
        (username, encrypted_email, encrypted_image_name, point_count, encrypted_points),
    )
    connection.commit()
    connection.close()


def get_user(username):
    # This function gets one user record using the username.
    connection = get_connection()
    user = connection.execute(
        "SELECT * FROM users WHERE username = ?",
        (username,),
    ).fetchone()
    connection.close()
    user = decrypt_user(user)
    return user


def username_exists(username):
    # This keeps two users from registering with the same username.
    user = get_user(username)

    if user:
        return True

    return False


def save_log(username, event_name):
    # This saves one event for one user.
    event_time = datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")

    connection = get_connection()
    connection.execute(
        "INSERT INTO logs (username, event_name, event_time) VALUES (?, ?, ?)",
        (username, event_name, event_time),
    )
    connection.commit()
    connection.close()


def get_logs(username):
    # This gets only the events of the logged in user.
    connection = get_connection()
    logs = connection.execute(
        "SELECT * FROM logs WHERE username = ? ORDER BY id DESC",
        (username,),
    ).fetchall()
    connection.close()
    return logs


def get_wait_seconds():
    # This checks how many seconds are left before the next attempt.
    locked_until = session.get("locked_until")

    if not locked_until:
        return 0

    locked_until_time = datetime.strptime(locked_until, "%Y-%m-%d %H:%M:%S")
    now_time = datetime.now()

    if now_time >= locked_until_time:
        session.pop("locked_until", None)
        session["failed_attempts"] = 0
        return 0

    remaining_time = locked_until_time - now_time
    return int(remaining_time.total_seconds()) + 1


def check_points(saved_points, entered_points):
    # The user must click the same number of points during login.
    if len(saved_points) != len(entered_points):
        return False

    for i in range(len(saved_points)):
        saved_x = saved_points[i]["x"]
        saved_y = saved_points[i]["y"]

        entered_x = entered_points[i]["x"]
        entered_y = entered_points[i]["y"]

        x_difference = abs(saved_x - entered_x)
        y_difference = abs(saved_y - entered_y)

        if x_difference > POINT_TOLERANCE:
            return False

        if y_difference > POINT_TOLERANCE:
            return False

    return True


def make_otp():
    # This creates a simple 6 digit OTP.
    otp_number = random.randint(100000, 999999)
    return str(otp_number)


def smtp_is_ready():
    # SMTP details must be set before the app can send email OTP.
    if not SMTP_SERVER:
        return False

    if not SMTP_EMAIL:
        return False

    if not SMTP_PASSWORD:
        return False

    return True


def send_otp_email(receiver_email, otp):
    message = EmailMessage()
    message["Subject"] = "Your Graphical Password OTP"
    message["From"] = SMTP_EMAIL
    message["To"] = receiver_email
    message.set_content(f"Your OTP is: {otp}")

    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, timeout=15) as smtp:
            smtp.login(SMTP_EMAIL, SMTP_PASSWORD)
            smtp.send_message(message)

        print("OTP sent successfully")

    except Exception as e:
        print("SMTP Error:", e)
        raise


def send_alert_email(receiver_email, username):
    # This email alerts the user after 3 wrong graphical password attempts.
    message = EmailMessage()
    message["Subject"] = "Graphical Password Alert"
    message["From"] = SMTP_EMAIL
    message["To"] = receiver_email
    message.set_content("Alert: There were 3 unsuccessful login attempts for username " + username + ".")

    smtp = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
    smtp.starttls()
    smtp.login(SMTP_EMAIL, SMTP_PASSWORD)
    smtp.send_message(message)
    smtp.quit()


def send_otp_to_user(email, purpose):
    # The same function is used for registration OTP and login OTP.
    otp = make_otp()
    session["otp"] = otp
    session["otp_purpose"] = purpose
    session["otp_email"] = email
    send_otp_email(email, otp)


def save_uploaded_image(uploaded_image):
    # The uploaded image is saved with a safe file name.
    image_name = secure_filename(uploaded_image.filename)
    image_path = os.path.join(UPLOAD_FOLDER, image_name)
    uploaded_image.save(image_path)
    return image_name


def get_selected_image(request_data, uploaded_image):
    # A user can use a sample image or upload a new image.
    selected_image = request_data.form.get("selected_image")

    if uploaded_image and uploaded_image.filename:
        uploaded_image_name = save_uploaded_image(uploaded_image)
        return "uploads/" + uploaded_image_name

    return "images/" + selected_image


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    message = ""

    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        point_count = request.form.get("point_count")
        points_text = request.form.get("points")
        uploaded_image = request.files.get("uploaded_image")

        if not smtp_is_ready():
            message = "SMTP settings are missing. Please add SMTP details in app.py."
            return render_template("register.html", message=message)

        if username_exists(username):
            message = "This username is already registered."
            return render_template("register.html", message=message)

        point_count = int(point_count)

        if point_count < 3 or point_count > 6:
            message = "Please select between 3 and 6 points."
            return render_template("register.html", message=message)

        points = json.loads(points_text)
        image_name = get_selected_image(request, uploaded_image)

        session["pending_username"] = username
        session["pending_email"] = email
        session["pending_image_name"] = image_name
        session["pending_point_count"] = point_count
        session["pending_points"] = points

        send_otp_to_user(email, "register")

        return redirect(url_for("otp"))

    return render_template("register.html", message=message)


@app.route("/login", methods=["GET", "POST"])
def login():
    message = ""

    if request.method == "POST":
        username = request.form.get("username")
        user = get_user(username)

        if user:
            session["username"] = username
            session["failed_attempts"] = 0
            save_log(username, "Username entered for login")
            return redirect(url_for("verify"))

        message = "Username was not found."

    return render_template("login.html", message=message)


@app.route("/verify", methods=["GET", "POST"])
def verify():
    username = session.get("username")

    if not username:
        return redirect(url_for("login"))

    user = get_user(username)
    message = ""
    wait_seconds = get_wait_seconds()

    if request.method == "POST":
        wait_seconds = get_wait_seconds()

        if wait_seconds > 0:
            message = "Please wait before trying again."
            return render_template("verify.html", user=user, message=message, wait_seconds=wait_seconds)

        entered_points_text = request.form.get("points")
        entered_points = json.loads(entered_points_text)
        saved_points = json.loads(user["points"])

        if check_points(saved_points, entered_points):
            session["failed_attempts"] = 0
            save_log(username, "Graphical password matched")

            if not smtp_is_ready():
                message = "SMTP settings are missing. Please add SMTP details in app.py."
                return render_template("verify.html", user=user, message=message)

            send_otp_to_user(user["email"], "login")
            save_log(username, "Login OTP sent")
            return redirect(url_for("otp"))

        failed_attempts = session.get("failed_attempts", 0)
        failed_attempts = failed_attempts + 1
        session["failed_attempts"] = failed_attempts
        save_log(username, "Wrong graphical password attempt " + str(failed_attempts))

        if failed_attempts == 3:
            if smtp_is_ready():
                send_alert_email(user["email"], username)
                save_log(username, "Alert mail sent after 3 wrong attempts")

            locked_until = datetime.now() + timedelta(seconds=30)
            session["locked_until"] = locked_until.strftime("%Y-%m-%d %H:%M:%S")
            session["failed_attempts"] = 0
            wait_seconds = get_wait_seconds()
            message = "Graphical password did not match. Alert mail was sent after 3 wrong attempts."
            return render_template("verify.html", user=user, message=message, wait_seconds=wait_seconds)

        message = "Graphical password did not match."

    return render_template("verify.html", user=user, message=message, wait_seconds=wait_seconds)


@app.route("/otp", methods=["GET", "POST"])
def otp():
    message = ""
    otp_purpose = session.get("otp_purpose")
    otp_email = session.get("otp_email")

    if not otp_purpose or not otp_email:
        return redirect(url_for("home"))

    if request.method == "POST":
        entered_otp = request.form.get("otp")
        saved_otp = session.get("otp")

        if entered_otp == saved_otp:
            if otp_purpose == "register":
                username = session.get("pending_username")
                email = session.get("pending_email")
                image_name = session.get("pending_image_name")
                point_count = session.get("pending_point_count")
                points = session.get("pending_points")

                save_user(username, email, image_name, point_count, points)
                save_log(username, "Registration completed with OTP")
                session.clear()
                return redirect(url_for("login"))

            if otp_purpose == "login":
                username = session.get("username")
                session["logged_in"] = True
                save_log(username, "Login completed with OTP")
                session.pop("otp", None)
                session.pop("otp_purpose", None)
                session.pop("otp_email", None)
                return redirect(url_for("dashboard"))

        if otp_purpose == "login":
            username = session.get("username")
            save_log(username, "Wrong login OTP entered")

        message = "OTP did not match."

    return render_template("otp.html", message=message, otp_email=otp_email)


@app.route("/dashboard")
def dashboard():
    username = session.get("username")
    logged_in = session.get("logged_in")

    if not username or not logged_in:
        return redirect(url_for("login"))

    logs = get_logs(username)
    return render_template("dashboard.html", username=username, logs=logs)


@app.route("/logout")
def logout():
    username = session.get("username")

    if username:
        save_log(username, "User logged out")

    session.clear()
    return redirect(url_for("home"))


create_folder()
create_table()
add_email_column()


if __name__ == "__main__":
    app.run(debug=False)
