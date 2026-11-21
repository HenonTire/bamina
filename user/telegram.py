import hmac
import logging

import requests
from django.conf import settings
from django.utils import timezone

from .models import (
    TelegramVerificationChallenge as Challenge,
    hash_secret_token,
    normalize_ethiopian_phone,
)

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 5


def _api():
    return f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}"


def send(chat_id, text, contact_button=False):
    body = {"chat_id": chat_id, "text": text}

    if contact_button:
        body["reply_markup"] = {
            "keyboard": [[{"text": "📱 Share my phone number", "request_contact": True}]],
            "resize_keyboard": True,
            "one_time_keyboard": True,
        }
    else:
        body["reply_markup"] = {"remove_keyboard": True}

    try:
        requests.post(f"{_api()}/sendMessage", json=body, timeout=10)
    except requests.RequestException:
        logger.exception("Telegram sendMessage failed")


def secret_ok(header_value):
    secret = settings.TELEGRAM_WEBHOOK_SECRET

    # an empty secret must never validate
    if not secret:
        return False

    return hmac.compare_digest(header_value or "", secret)


def handle_update(update):
    msg = update.get("message") or {}
    sender = msg.get("from") or {}
    chat_id = msg.get("chat", {}).get("id")
    user_id = sender.get("id")

    if not chat_id or not user_id:
        return

    text = (msg.get("text") or "").strip()

    # Step 1: user tapped the deep link  ->  /start <token>
    if text.startswith("/start "):
        raw = text.split(" ", 1)[1].strip()
        ch = Challenge.objects.filter(
            token_hash=hash_secret_token(raw),
            purpose=Challenge.Purpose.LINK,
        ).first()

        if not ch or ch.is_used or ch.is_expired() or ch.verified_at:
            return send(chat_id, "This link is invalid or expired. Please start again in Bami.")

        ch.telegram_user_id = str(user_id)
        ch.telegram_chat_id = str(chat_id)
        ch.save(update_fields=["telegram_user_id", "telegram_chat_id"])

        return send(chat_id, "Tap the button below to confirm your phone number.", contact_button=True)

    # Step 2: user shared their contact
    contact = msg.get("contact")
    if contact:
        ch = (
            Challenge.objects.filter(
                telegram_user_id=str(user_id),
                purpose=Challenge.Purpose.LINK,
                verified_at__isnull=True,
                is_used=False,
            )
            .order_by("-created_at")
            .first()
        )

        if not ch or ch.is_expired() or ch.attempts >= MAX_ATTEMPTS:
            return send(chat_id, "Please start again in Bami.")

        # must be the sender's OWN contact, not a forwarded one
        if str(contact.get("user_id")) != str(user_id):
            return send(chat_id, "Please share your own number using the button.", contact_button=True)

        try:
            shared = normalize_ethiopian_phone(contact.get("phone_number", ""))
        except ValueError:
            shared = None

        if shared != ch.phone:
            ch.attempts += 1
            ch.save(update_fields=["attempts"])
            return send(chat_id, "That number doesn't match your Bami account.")

        ch.verified_at = timezone.now()
        ch.save(update_fields=["verified_at"])

        return send(chat_id, "✅ Linked! Go back to Bami to continue.")

    send(chat_id, "Welcome to Bami 👋 Open the Bami website or app to get started.")