import os
import sys
import requests


def main() -> int:
    token = os.getenv("BOT_TOKEN", "").strip()
    chat_id = os.getenv("ADMIN_CHAT_ID", "").strip()
    if not token or not chat_id:
        print("BOT_TOKEN or ADMIN_CHAT_ID missing; skip уведомление.")
        return 0

    message = " ".join(sys.argv[1:]).strip() if len(sys.argv) > 1 else "Pipeline failed."
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message}
    resp = requests.post(url, json=payload, timeout=20)
    if resp.status_code >= 300:
        print(f"Telegram notify failed: {resp.status_code} {resp.text}")
        return 1
    print("Telegram notify sent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
