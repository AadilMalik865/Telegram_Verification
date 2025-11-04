from flask import Blueprint, render_template, request, redirect, url_for, session
from client_manager import get_client, run_async

auth_bp = Blueprint("auth", __name__)

# ✅ Login Route
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        phone = request.form.get("phone")
        session["phone"] = phone

        client = get_client(phone)

        # ✅ Check authorization
        authorized = run_async(client.is_user_authorized())

        if not authorized:
            try:
                result = run_async(client.send_code_request(phone))
                session["phone_code_hash"] = result.phone_code_hash
                session["code_sent"] = True
                return render_template("verify.html", phone=phone)
            except Exception as e:
                return f"Error: {e}"
        else:
            return redirect(url_for("index"))

    return render_template("login.html")


# ✅ Verify OTP
@auth_bp.route("/verify", methods=["POST"])
def verify():
    phone = session.get("phone")
    code = request.form.get("code")
    phone_code_hash = session.get("phone_code_hash")

    if not phone or not phone_code_hash:
        return "Session expired. Please login again."

    client = get_client(phone)

    try:
        run_async(client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash))
        print("[DEBUG] OTP Verified Successfully ✅")
    except Exception as e:
        return f"Error: {e}"

    return redirect(url_for("index"))
