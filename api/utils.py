
# def send_fcm_notification(token, title, body):
#     message = messaging.Message(
#         notification=messaging.Notification(
#             title=title,
#             body=body,
#         ),
#         token=token,
#     )

#     response = messaging.send(message)
#     return response  # Returns message ID


from firebase_admin import messaging
from .models import FCMToken, Notification


def send_fcm_notification(user, shop, title, body, data=None):
    """
    Sends a notification to all FCM tokens of a user for a given shop.
    """
    tokens = FCMToken.objects.filter(
        user=user, shop=shop).values_list("token", flat=True)
    if not tokens:
        return None

    responses = []
    for token in tokens:
        try:
            message = messaging.Message(
                notification=messaging.Notification(title=title, body=body),
                token=token,
                data={k: str(v) for k, v in (data or {}).items()},
            )
            response = messaging.send(message)
            responses.append(
                {"token": token, "success": True, "response": response})

            Notification.objects.create(
                user=user, shop=shop, title=title, body=body)
        except Exception as e:
            responses.append(
                {"token": token, "success": False, "error": str(e)})

    return responses
