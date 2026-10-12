import http.client
import json
import os

CHAT_ID = YOUR_PROJECT_ID

def send_telegram_message(text):
    token = os.environ["telegram-key"]

    conn = http.client.HTTPSConnection("api.telegram.org", timeout=10)
    body = json.dumps({"chat_id": CHAT_ID, "text": text})
    headers = {"Content-Type": "application/json"}
    conn.request("POST", f"/bot{token}/sendMessage", body=body, headers=headers)

    res = conn.getresponse()
    response_text = res.read().decode("utf-8")
    if res.status != 200:
        raise RuntimeError(f"Telegram error {res.status}: {response_text}")
