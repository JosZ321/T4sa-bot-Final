import os
import logging

import requests
from flask import Flask, request, jsonify, send_from_directory, abort

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("t4tsa-bot")

app = Flask(__name__, static_folder="static", static_url_path="")

BOT_TOKEN = os.environ.get("BOT_TOKEN")
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "")
CHECK_CHANNEL = os.environ.get("CHECK_CHANNEL", "@MugiwaraResearcher")
PUBLIC_URL = os.environ.get("PUBLIC_URL")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is required")

BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
WEB_APP_URL = f"{PUBLIC_URL}/app" if PUBLIC_URL else None


@app.get("/")
def home():
    return {"status": "ok", "service": "T4TSA bot"}, 200


@app.get("/health")
def health():
    return "ok", 200


@app.get("/app")
def webapp():
    return send_from_directory(app.static_folder, "index.html")


@app.get("/api/check")
def check_membership():
    user_id_raw = request.args.get("user_id")
    if not user_id_raw:
        return jsonify(joined=False, error="No user_id provided"), 400

    try:
        user_id = int(user_id_raw)
    except ValueError:
        return jsonify(joined=False, error="Invalid user_id"), 400

    try:
        r = requests.post(
            f"{BASE_URL}/getChatMember",
            json={"chat_id": CHECK_CHANNEL, "user_id": user_id},
            timeout=10,
        )
        data = r.json()
    except requests.RequestException as exc:
        log.warning("Telegram API call failed: %s", exc)
        return jsonify(joined=False, error="Telegram API unreachable"), 200

    if not data.get("ok"):
        return jsonify(joined=False, error=data.get("description", "Unknown error")), 200

    status = data["result"]["status"]
    is_member = status not in ("left", "kicked")
    return jsonify(joined=is_member, status=status), 200


def _secret_ok(req) -> bool:
    if not WEBHOOK_SECRET:
        return True
    return req.headers.get("X-Telegram-Bot-Api-Secret-Token") == WEBHOOK_SECRET


@app.post("/webhook")
def webhook():
    if not _secret_ok(request):
        abort(403)

    update = request.get_json(silent=True) or {}
    msg = update.get("message")

    if msg and msg.get("text") == "/start":
        chat_id = msg["chat"]["id"]
        keyboard = {
            "inline_keyboard": [[
                {"text": "🎬 Open T4TSA App", "web_app": {"url": WEB_APP_URL}}
            ]]
        }
        try:
            requests.post(
                f"{BASE_URL}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": "👋 Welcome! Tap below to open the app.",
                    "reply_markup": keyboard,
                },
                timeout=10,
            )
        except requests.RequestException as exc:
            log.warning("sendMessage failed: %s", exc)

    return "OK", 200


@app.get("/set_webhook")
def set_webhook_route():
    if not PUBLIC_URL:
        return {"error": "Set the PUBLIC_URL environment variable first"}, 400

    params = {"url": f"{PUBLIC_URL}/webhook"}
    if WEBHOOK_SECRET:
        params["secret_token"] = WEBHOOK_SECRET

    r = requests.get(f"{BASE_URL}/setWebhook", params=params, timeout=10)
    return r.json(), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
