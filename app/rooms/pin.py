"""방 비밀번호(숫자 4자리). 다시 들어오기 전용이고 로그인이 아니다 (10/4).

DB 에는 원래 숫자 대신 해시만 저장한다. 파이썬 기본 hashlib 만 쓴다 (새 패키지 없음).
"""

import hashlib
import hmac
import secrets

ITERATIONS = 100_000


def hash_pin(pin: str) -> str:
    """'pbkdf2$반복수$salt$해시' 모양 문자열."""
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", pin.encode(), salt, ITERATIONS)
    return f"pbkdf2${ITERATIONS}${salt.hex()}${digest.hex()}"


def check_pin(pin: str, stored: str) -> bool:
    try:
        _, iterations, salt, digest = stored.split("$")
        again = hashlib.pbkdf2_hmac("sha256", pin.encode(), bytes.fromhex(salt), int(iterations))
    except ValueError:
        return False
    return hmac.compare_digest(again.hex(), digest)
