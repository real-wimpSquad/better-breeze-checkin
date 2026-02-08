from __future__ import annotations

"""
Check-in code generation and decoding.

Encodes instance_id and person_id into a human-readable code
that can be decoded back to its components.

instance_id already implies the date (it's a specific event occurrence),
so we don't need to encode date separately.

Format: 6 alphanumeric characters
Encodes:
- instance_id mod 32768 (15 bits)
- person_id mod 32768 (15 bits)
- checksum (1 character)

Total: 30 bits -> 6 base30 chars + 1 checksum = 7 chars
Display: XXX-XXXX
"""

# Base30 alphabet - removed confusing chars (0/O, 1/I/L)
ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
BASE = len(ALPHABET)


def _checksum(data: int) -> int:
    """Simple checksum: sum of nibbles mod BASE."""
    total = 0
    while data:
        total += data & 0xF
        data >>= 4
    return total % BASE


def encode_checkin_code(person_id: str | int, instance_id: str | int) -> str:
    """
    Generate a check-in code encoding person and instance.

    Returns a 7-character code like "A3K-M9P2"
    """
    pid = int(person_id) if isinstance(person_id, str) else person_id
    iid = int(instance_id) if isinstance(instance_id, str) else instance_id

    # Pack: [instance:15][person:15] = 30 bits
    packed = ((iid & 0x7FFF) << 15) | (pid & 0x7FFF)

    # Convert to base30 (LSB first)
    chars = []
    temp = packed
    for _ in range(6):
        chars.append(ALPHABET[temp % BASE])
        temp //= BASE

    # Reverse to get MSB first
    chars = chars[::-1]

    # Add checksum at the end
    chars.append(ALPHABET[_checksum(packed)])

    code = ''.join(chars)
    return f"{code[:3]}-{code[3:]}"


def decode_checkin_code(code: str) -> dict | None:
    """
    Decode a check-in code back to its components.

    Returns dict with 'instance_id', 'person_id' (mod values)
    or None if invalid/checksum fails.
    """
    code = code.upper().replace("-", "").replace(" ", "")

    if len(code) != 7:
        return None

    try:
        indices = [ALPHABET.index(c) for c in code]
    except ValueError:
        return None

    # Last char is checksum, first 6 are data (MSB first)
    data_indices = indices[:6]
    checksum_idx = indices[6]

    # Reconstruct packed integer (data is MSB first)
    packed = 0
    for idx in data_indices:
        packed = packed * BASE + idx

    # Verify checksum
    if _checksum(packed) != checksum_idx:
        return None

    # Unpack
    person_id = packed & 0x7FFF
    instance_id = (packed >> 15) & 0x7FFF

    return {
        "instance_id": instance_id,
        "person_id": person_id,
    }


def validate_checkin_code(
    code: str,
    expected_instance_id: str | int | None = None,
    expected_person_id: str | int | None = None,
) -> dict | None:
    """
    Decode and validate a check-in code.

    Optionally verify it matches expected instance and/or person (mod 32768).
    Returns decoded data if valid, None otherwise.
    """
    decoded = decode_checkin_code(code)
    if decoded is None:
        return None

    if expected_instance_id is not None:
        iid = int(expected_instance_id) if isinstance(expected_instance_id, str) else expected_instance_id
        if (iid & 0x7FFF) != decoded["instance_id"]:
            return None

    if expected_person_id is not None:
        pid = int(expected_person_id) if isinstance(expected_person_id, str) else expected_person_id
        if (pid & 0x7FFF) != decoded["person_id"]:
            return None

    return decoded


# Convenience alias
def generate_code(person_id: str, instance_id: str) -> str:
    """Generate a display-friendly code for labels."""
    return encode_checkin_code(person_id, instance_id)
