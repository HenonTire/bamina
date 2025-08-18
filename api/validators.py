from django.core.exceptions import ValidationError
import re

ETH_PHONE_REGEX = re.compile(
    r'^(\+251|0)(9\d{8}|7\d{8})$'
)


def ethiopian_phone_validator(value):
    if not ETH_PHONE_REGEX.match(value):
        raise ValidationError("Enter a valid Ethiopian phone number")
