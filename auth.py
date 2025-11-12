from flask import Blueprint, render_template, request, redirect, url_for, session
from client_manager import get_client, run_async, normalize_phone

auth_bp = Blueprint("auth", __name__)

# Login Route
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        phone_raw = request.form.get("phone")
        phone_norm = normalize_phone(phone_raw)
        if not phone_norm:
            return "Invalid phone number", 400

        # store both raw and normalized (normalized used for backend mapping)
        session["phone_raw"] = phone_raw
        session["phone"] = phone_norm  # canonical key

        client = get_client(phone_norm)

        # Check authorization
        authorized = run_async(client.is_user_authorized())

        if not authorized:
            try:
                result = run_async(client.send_code_request(phone_raw))
                # store phone_code_hash and the phone_raw (Telethon expects original format)
                session["phone_code_hash"] = result.phone_code_hash
                session["code_sent"] = True
                return render_template("verify.html", phone=phone_raw)
            except Exception as e:
                return f"Error sending code: {e}"
        else:
            return redirect(url_for("index"))

    return render_template("login.html")


# Verify OTP
@auth_bp.route("/verify", methods=["POST"])
def verify():
    phone_norm = session.get("phone")
    phone_raw = session.get("phone_raw")
    code = request.form.get("code")
    phone_code_hash = session.get("phone_code_hash")

    if not phone_norm or not phone_code_hash or not phone_raw:
        return "Session expired. Please login again.", 400

    client = get_client(phone_norm)

    try:
        run_async(client.sign_in(phone=phone_raw, code=code, phone_code_hash=phone_code_hash))
        print("[DEBUG] OTP Verified Successfully ✅")
    except Exception as e:
        return f"Error verifying code: {e}"

    return redirect(url_for("index"))
