from datetime import datetime, timezone as datetime_timezone

from django.db import transaction
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken,
)
from rest_framework_simplejwt.tokens import RefreshToken

from .models import DeviceSession


@transaction.atomic
def create_token_pair(user, request=None):
    """
    Create JWT tokens and register the refresh token
    as a device session.
    """

    refresh = RefreshToken.for_user(user)

    access = refresh.access_token

    device_name = ""
    device_type = ""
    ip_address = None

    if request:
        user_agent = request.META.get("HTTP_USER_AGENT", "")
        device_name = user_agent[:150]

        forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")

        if forwarded_for:
            ip_address = forwarded_for.split(",")[0].strip()
        else:
            ip_address = request.META.get("REMOTE_ADDR")

    expires_at = datetime.fromtimestamp(
        refresh["exp"],
        tz=datetime_timezone.utc,
    )

    session = DeviceSession.objects.create(
        user=user,
        jti=refresh["jti"],
        device_name=device_name,
        device_type=device_type,
        last_ip=ip_address,
        expires_at=expires_at,
    )

    return {
        "access": str(access),
        "refresh": str(refresh),
        "session_id": str(session.id),
    }


@transaction.atomic
def revoke_device_session(user, session_id):
    """
    Revoke one device session belonging to the given user.
    """

    try:
        session = DeviceSession.objects.select_for_update().get(
            id=session_id,
            user=user,
        )
    except DeviceSession.DoesNotExist:
        return False

    if session.is_revoked:
        return True

    session.is_revoked = True
    session.save(update_fields=["is_revoked"])

    outstanding_token = OutstandingToken.objects.filter(
        user=user,
        jti=session.jti,
    ).first()

    if outstanding_token:
        BlacklistedToken.objects.get_or_create(
            token=outstanding_token,
        )

    return True