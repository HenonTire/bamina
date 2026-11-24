from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken


class OptionalJWTAuthentication(JWTAuthentication):
    """
    Uses the JWT when it is valid. A missing, expired or garbage token is treated
    as a guest instead of failing, so guest checkout never breaks because a
    browser still holds an old token.
    """

    def authenticate(self, request):
        try:
            return super().authenticate(request)
        except (InvalidToken, AuthenticationFailed):
            return None