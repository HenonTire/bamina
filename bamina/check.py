import os
import requests

TOKEN = "8472991164:AAENERowjdqwFSXJHBg7dXH6_IIhMAVN-w4"
SECRET = "VmD70ObInxA8WtA5mQI_A_AA9FAds1cUeuJJLlNRY7w"

WEBHOOK_URL = "https://bamina.onrender.com/telegram/webhook/"

if not TOKEN:
    raise SystemExit("❌ TELEGRAM_BOT_TOKEN is not set.")

if not SECRET:
    raise SystemExit("❌ TELEGRAM_WEBHOOK_SECRET is not set.")

api_url = f"https://api.telegram.org/bot{TOKEN}"

# Register webhook
response = requests.post(
    f"{api_url}/setWebhook",
    json={
        "url": WEBHOOK_URL,
        "secret_token": SECRET,
    },
    timeout=15,
)

print("SET WEBHOOK:")
print(response.json())

# Check webhook
response = requests.get(
    f"{api_url}/getWebhookInfo",
    timeout=15,
)

print("\nWEBHOOK INFO:")
print(response.json())