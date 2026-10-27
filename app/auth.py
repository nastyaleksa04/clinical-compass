"""Минимальный вход: логин и пароль, токен сессии в заголовке Authorization."""

import hashlib
import hmac
import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

from app import db

CONFIG_PATH = Path(__file__).resolve().parents[1] / 'config' / 'users.json'
ITERATIONS = 200_000
SESSION_HOURS = 12


@lru_cache(maxsize=1)
def config() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding='utf-8'))


def hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), bytes.fromhex(salt), ITERATIONS).hex()
    return f'pbkdf2_sha256${ITERATIONS}${salt}${digest}'


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iterations, salt, digest = stored.split('$')
    except ValueError:
        return False
    candidate = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), bytes.fromhex(salt), int(iterations)).hex()
    return hmac.compare_digest(candidate, digest)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def seed_demo_users() -> None:
    for user in config()['demo_users']:
        if user.get('patient_id') and not db.get_patient(user['patient_id']):
            continue
        if not db.get_user_by_login(user['login']):
            db.create_user(user['login'], hash_password(user['password']), user['role'], user['display_name'], user.get('patient_id'))


def login(login_value: str, password: str) -> dict[str, Any] | None:
    user = db.get_user_by_login(login_value.strip().lower())
    if not user or not verify_password(password, user['password_hash']):
        return None
    token = secrets.token_urlsafe(32)
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=SESSION_HOURS)).isoformat()
    db.create_session(_token_hash(token), user['id'], expires_at)
    return {'token': token, 'expires_at': expires_at, 'user': public_user(user)}


def resolve(token: str) -> dict[str, Any] | None:
    return db.get_session_user(_token_hash(token))


def logout(token: str) -> None:
    db.delete_session(_token_hash(token))


def public_user(user: dict[str, Any]) -> dict[str, Any]:
    return {'login': user['login'], 'role': user['role'], 'display_name': user['display_name'], 'patient_id': user.get('patient_id')}


def demo_headers_allowed() -> bool:
    """Заголовок X-Demo-Role оставлен только для автотестов и включается переменной окружения."""
    return os.environ.get('CLINICAL_COMPASS_DEMO_HEADERS') == '1'
