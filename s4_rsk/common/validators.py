import re

from rest_framework import serializers

IBAN_REGEX = re.compile(r"^IR[0-9]{24}$")


def validate_iranian_iban(value: str) -> str:
    """
    GEN-13: Validates IR + 24 digits format
    """
    if not value or not IBAN_REGEX.match(value):
        raise serializers.ValidationError(
            "IBAN must start with 'IR' followed by exactly 24 digits."
        )

    # ISO 13616 Modulo-97 verification (I=18, R=27)
    # rearranged = value[4:] + "1827" + value[2:4]
    # if int(rearranged) % 97 != 1:
    #     raise serializers.ValidationError("Invalid IBAN checksum (ISO 13616).")

    return value


def is_internal_labbank_iban(iban: str) -> bool:
    """
    GEN-13: Digits 5 to 7 (index 4:7) being '099' indicate an internal LabBank account.
    """
    return len(iban) == 26 and iban[4:7] == "099"
