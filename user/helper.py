from datetime import timedelta
from rest_framework.response import Response

def set_refresh_cookie(response, refresh_token):
    """
    Attaches the refresh token as an HttpOnly cookie to the Response.

    """
   
    cookie_max_age = int(timedelta(days=15).total_seconds())  # match REFRESH_TOKEN_LIFETIME
    response.set_cookie(
            key='refresh',
            value=str(refresh_token),
            httponly=True,
            secure=False,    # In production, always True (requires HTTPS)
            samesite='Lax', # or 'Strict' for more security
            max_age=60 * 60 * 24 * 60,
        )
    return response



