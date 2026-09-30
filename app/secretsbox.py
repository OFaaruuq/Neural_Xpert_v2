"""Encrypt recoverable secrets (SMTP password, authenticator secret) with the application secret.

The construction is HMAC-SHA256 in counter mode, then HMAC-SHA256 over the
ciphertext. Values already stored in plaintext are left readable until the
next save, which replaces them with the sealed form.
"""

import base64
import hashlib
import hmac
import os

from flask import current_app
from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator

_PREFIX = "nx1:"


def _key():
    secret = (current_app.config.get("SECRET_KEY") or "").encode()
    return hashlib.sha256(b"neuralxpert-secret-v1:" + secret).digest()


def _keystream(key, nonce, length):
    output = bytearray()
    counter = 0
    while len(output) < length:
        block = hmac.new(key, nonce + counter.to_bytes(4, "big"), hashlib.sha256).digest()
        output.extend(block)
        counter += 1
    return bytes(output[:length])


def seal(value):
    text = value or ""
    if not text or text.startswith(_PREFIX):
        return text
    key = _key()
    nonce = os.urandom(16)
    raw = text.encode()
    cipher = bytes(left ^ right for left, right in zip(raw, _keystream(key, nonce, len(raw))))
    mac = hmac.new(key, nonce + cipher, hashlib.sha256).digest()
    blob = base64.urlsafe_b64encode(nonce + mac + cipher).decode("ascii")
    return _PREFIX + blob


def open_secret(value):
    text = value or ""
    if not text.startswith(_PREFIX):
        return text
    try:
        raw = base64.urlsafe_b64decode(text[len(_PREFIX):].encode("ascii"))
    except (ValueError, TypeError):
        return ""
    if len(raw) < 48:
        return ""
    nonce, mac, cipher = raw[:16], raw[16:48], raw[48:]
    key = _key()
    expected = hmac.new(key, nonce + cipher, hashlib.sha256).digest()
    if not hmac.compare_digest(mac, expected):
        return ""
    plain = bytes(left ^ right for left, right in zip(cipher, _keystream(key, nonce, len(cipher))))
    try:
        return plain.decode()
    except UnicodeDecodeError:
        return ""


class EncryptedText(TypeDecorator):
    """Stores seal() ciphertext and returns open_secret() plaintext to the application."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return seal(value or "")

    def process_result_value(self, value, dialect):
        return open_secret(value or "")
