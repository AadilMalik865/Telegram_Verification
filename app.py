from flask import Flask, render_template, request, send_file, url_for, redirect, session, Response, jsonify
import os, queue, threading, tempfile
from scraper import fetch_messages
from auth import auth_bp
from client_manager import run_async, normalize_phone
from google_sheet import append_row  # <-- import your updated Google Sheets function

app = Flask(__name__)
app.secret_key = "supersecret"

BASE_DIR = tempfile.gettempdir()

app.register_blueprint(auth_bp, url_prefix="/auth")

# -------------------------------
# Per-user state
# -------------------------------
user_log_queues = {}    # phone_norm -> Queue()
user_stop_events = {}   # phone_norm -> threading.Event()
user_scraped_files = {} # phone_norm -> filepath

def _get_user_queue(phone_norm):
    if phone_norm not in user_log_queues:
        user_log_queues[phone_norm] = queue.Queue()
    return user_log_queues[phone_norm]

def _get_user_stop_event(phone_norm):
    if phone_norm not in user_stop_events:
        user_stop_events[phone_norm] = threading.Event()
    return user_stop_events[phone_norm]

def _set_user_file(phone_norm, path):
    user_scraped_files[phone_norm] = path

def _get_user_file(phone_norm):
    return user_scraped_files.get(phone_norm)

def log_message_for(phone_norm, msg):
    """Push messages to SSE queue and server log."""
    print(f"[{phone_norm}] {msg}", flush=True)
    q = _get_user_queue(phone_norm)
    q.put(msg)

# -------------------------------
# Routes
# -------------------------------
@app.route("/")
def home():
    return redirect(url_for("auth.login"))

@app.route("/index", methods=["GET", "POST"])
def index():
    phone_norm = session.get("phone")
    if not phone_norm:
        return redirect(url_for("auth.login"))

    file_exists = False
    user_file = _get_user_file(phone_norm)
    if user_file and os.path.exists(user_file):
        file_exists = True

    if request.method == "POST":
        # Clear old logs for this user
        q = _get_user_queue(phone_norm)
        while not q.empty():
            q.get_nowait()

        urls_text = request.form.get("channel_urls", "")
        urls = [u.strip() for u in urls_text.splitlines() if u.strip()]

        stop_event = _get_user_stop_event(phone_norm)
        stop_event.clear()
        _set_user_file(phone_norm, None)

        def background_scrape(local_phone_norm):
            log_message_for(local_phone_norm, "🚀 Scraping started...")
            try:
                result_file = run_async(
                    fetch_messages(
                        urls,
                        local_phone_norm,
                        logger=lambda m: log_message_for(local_phone_norm, m),
                        stop_event=stop_event
                    )
                )

                # Store final CSV path
                if result_file and os.path.exists(result_file):
                    _set_user_file(local_phone_norm, result_file)
                else:
                    fallback = os.path.join(BASE_DIR, "telegram_data.csv")
                    _set_user_file(local_phone_norm, fallback if os.path.exists(fallback) else result_file)

                if not stop_event.is_set():
                    log_message_for(local_phone_norm, "✅ Scraping completed successfully.")
                else:
                    log_message_for(local_phone_norm, "🛑 Scraping stopped by user.")
            except Exception as e:
                log_message_for(local_phone_norm, f"❌ Error during scraping: {e}")

        threading.Thread(target=background_scrape, args=(phone_norm,), daemon=True).start()
        log_message_for(phone_norm, "⏳ Please wait... scraping is running in background.")
        return render_template("index.html", file_exists=False)

    return render_template("index.html", file_exists=file_exists, file_name=user_file)

# -------------------------------
# SSE – live log updates
# -------------------------------
@app.route("/progress")
def progress():
    phone_norm = session.get("phone")
    if not phone_norm:
        return "Unauthorized", 401

    def generate():
        q = _get_user_queue(phone_norm)
        while True:
            msg = q.get()
            yield f"data: {msg}\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

# -------------------------------
# Stop scraping
# -------------------------------
@app.route("/stop", methods=["POST"])
def stop_scraping():
    phone_norm = session.get("phone")
    if not phone_norm:
        return jsonify({"status": "not_logged_in"}), 401

    event = _get_user_stop_event(phone_norm)
    event.set()
    log_message_for(phone_norm, "🛑 Stop signal received — scraper will stop soon.")
    return jsonify({"status": "stopping"})

# -------------------------------
# Check if CSV file exists
# -------------------------------
@app.route("/check_file")
def check_file():
    phone_norm = session.get("phone")
    user_file = _get_user_file(phone_norm)
    if user_file and os.path.exists(user_file):
        return {"exists": True, "file_name": os.path.basename(user_file)}
    return {"exists": False}

# -------------------------------
# Download CSV per-user
# -------------------------------
@app.route("/download/<file_name>")
def download(file_name):
    phone_norm = session.get("phone")
    file_path = _get_user_file(phone_norm)

    if not file_path or not os.path.isfile(file_path):
        return "File not found on server", 404

    return send_file(
        file_path,
        as_attachment=True,
        mimetype="text/csv",
        download_name=file_name
    )

# -------------------------------
# Run app
# -------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True, threaded=True)