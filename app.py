from flask import Flask, render_template, request, send_file, url_for, redirect, session, Response, jsonify
import os, queue, threading, tempfile
from scraper import fetch_messages
from auth import auth_bp
from client_manager import run_async

app = Flask(__name__)
app.secret_key = "supersecret"

# ✅ Always use /tmp for Render deployments
BASE_DIR = tempfile.gettempdir()

# Register Blueprint
app.register_blueprint(auth_bp, url_prefix="/auth")

# Global message queue and control
log_queue = queue.Queue()
stop_event = threading.Event()  # Stop scraper
scraped_file = None             # Track completed CSV


# ----------------------------------------------------------
# Helper: push messages to SSE
# ----------------------------------------------------------
def log_message(msg):
    print(msg, flush=True)  # log also to console (for debugging Render logs)
    log_queue.put(msg)


# ----------------------------------------------------------
# Routes
# ----------------------------------------------------------
@app.route("/")
def home():
    return redirect(url_for("auth.login"))


@app.route("/index", methods=["GET", "POST"])
def index():
    global scraped_file
    phone = session.get("phone")
    if not phone:
        return redirect(url_for("auth.login"))

    file_exists = scraped_file and os.path.exists(scraped_file)

    if request.method == "POST":
        # Clear old logs
        while not log_queue.empty():
            log_queue.get_nowait()

        urls_text = request.form.get("channel_urls")
        urls = [u.strip() for u in urls_text.splitlines() if u.strip()]

        stop_event.clear()
        scraped_file = None

        # Run background scraping
        def background_scrape():
            global scraped_file
            log_message("🚀 Scraping started in background...")
            try:
                # ✅ Force /tmp output path
                file_name = "scraped_data.csv"
                output_path = os.path.join(BASE_DIR, file_name)

                # Run your async scraper
                result_file = run_async(fetch_messages(urls, phone, log_message, stop_event))

                # Ensure saved in /tmp
                if result_file and os.path.exists(result_file):
                    scraped_file = result_file
                elif os.path.exists(output_path):
                    scraped_file = output_path
                else:
                    scraped_file = output_path  # fallback

                if not stop_event.is_set():
                    log_message("✅ Scraping completed successfully.")
                else:
                    log_message("🛑 Scraping stopped by user.")

            except Exception as e:
                log_message(f"❌ Error during scraping: {e}")

        threading.Thread(target=background_scrape, daemon=True).start()
        log_message("⏳ Please wait... scraping is running in background.")
        return render_template("index.html", file_exists=False)

    return render_template("index.html", file_exists=file_exists, file_name=scraped_file)


# ----------------------------------------------------------
# Server-Sent Events (SSE) – Live log updates
# ----------------------------------------------------------
@app.route("/progress")
def progress():
    def generate():
        while True:
            msg = log_queue.get()
            yield f"data: {msg}\n\n"

    # ✅ Disable buffering on Render
    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 🔥 Important for Render
        },
    )


# ----------------------------------------------------------
# Stop scraping
# ----------------------------------------------------------
@app.route("/stop", methods=["POST"])
def stop_scraping():
    stop_event.set()
    log_message("🛑 Stop signal received — scraper will stop soon.")
    return jsonify({"status": "stopping"})


# ----------------------------------------------------------
# Check file existence
# ----------------------------------------------------------
@app.route("/check_file")
def check_file():
    global scraped_file
    temp_path = os.path.join(BASE_DIR, "telegram_data.csv")

    # ✅ Fallback to telegram_data.csv in /tmp
    if scraped_file and os.path.exists(scraped_file):
        file_path = scraped_file
    elif os.path.exists(temp_path):
        file_path = temp_path
    else:
        file_path = None

    if file_path:
        return jsonify({
            "exists": True,
            "file_name": os.path.basename(file_path)
        })
    return jsonify({"exists": False})



# ----------------------------------------------------------
# File download
# ----------------------------------------------------------
@app.route("/download/<file_name>")
def download(file_name):
    full_path = os.path.join(BASE_DIR, file_name)
    if os.path.exists(full_path):
        return send_file(full_path, as_attachment=True)
    return "File not found!", 404


# ----------------------------------------------------------
# Start app
# ----------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True, threaded=True)
