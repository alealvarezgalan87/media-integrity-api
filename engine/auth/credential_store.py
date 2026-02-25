"""Encrypted credential storage for per-client OAuth tokens.

Supports:
- Fernet encryption at rest (local JSON files)
- Key generation and rotation
- Per-account credential CRUD
"""

import json
import os
from pathlib import Path

import structlog
from cryptography.fernet import Fernet, InvalidToken

logger = structlog.get_logger(__name__)

DEFAULT_STORE_DIR = os.path.join(os.path.expanduser("~"), ".msie", "credentials")
DEFAULT_KEY_PATH = os.path.join(os.path.expanduser("~"), ".msie", "fernet.key")


class CredentialStore:
    """Manages encrypted storage of OAuth2 credentials per client."""

    def __init__(
        self,
        store_dir: str | None = None,
        key_path: str | None = None,
    ):
        self.store_dir = store_dir or DEFAULT_STORE_DIR
        self.key_path = key_path or DEFAULT_KEY_PATH
        self._fernet: Fernet | None = None
        os.makedirs(self.store_dir, exist_ok=True)
        os.makedirs(os.path.dirname(self.key_path), exist_ok=True)

    def _get_fernet(self) -> Fernet:
        if self._fernet is not None:
            return self._fernet
        if not os.path.exists(self.key_path):
            self.generate_key()
        key = Path(self.key_path).read_bytes().strip()
        self._fernet = Fernet(key)
        return self._fernet

    def generate_key(self) -> str:
        """Generate a new Fernet encryption key and save to disk."""
        key = Fernet.generate_key()
        Path(self.key_path).write_bytes(key)
        os.chmod(self.key_path, 0o600)
        self._fernet = None
        logger.info("fernet_key_generated", path=self.key_path)
        return key.decode()

    def _account_path(self, account_id: str) -> str:
        safe_id = account_id.replace("-", "").replace(" ", "")
        return os.path.join(self.store_dir, f"{safe_id}.enc")

    def store_credentials(self, account_id: str, credentials: dict) -> None:
        """Encrypt and store credentials for an account."""
        f = self._get_fernet()
        payload = json.dumps(credentials).encode("utf-8")
        encrypted = f.encrypt(payload)
        path = self._account_path(account_id)
        Path(path).write_bytes(encrypted)
        os.chmod(path, 0o600)
        logger.info("credentials_stored", account_id=account_id)

    def get_credentials(self, account_id: str) -> dict | None:
        """Retrieve and decrypt credentials for an account."""
        path = self._account_path(account_id)
        if not os.path.exists(path):
            logger.warning("credentials_not_found", account_id=account_id)
            return None
        f = self._get_fernet()
        try:
            encrypted = Path(path).read_bytes()
            decrypted = f.decrypt(encrypted)
            return json.loads(decrypted.decode("utf-8"))
        except InvalidToken:
            logger.error("credentials_decrypt_failed", account_id=account_id)
            return None

    def delete_credentials(self, account_id: str) -> bool:
        """Delete credentials for an account."""
        path = self._account_path(account_id)
        if os.path.exists(path):
            os.remove(path)
            logger.info("credentials_deleted", account_id=account_id)
            return True
        return False

    def list_accounts(self) -> list[str]:
        """List all account IDs with stored credentials."""
        accounts = []
        for f in os.listdir(self.store_dir):
            if f.endswith(".enc"):
                accounts.append(f.replace(".enc", ""))
        return accounts

    def rotate_key(self, new_key: str | None = None) -> None:
        """Re-encrypt all stored credentials with a new key."""
        old_fernet = self._get_fernet()

        all_creds = {}
        for account_id in self.list_accounts():
            path = self._account_path(account_id)
            encrypted = Path(path).read_bytes()
            try:
                decrypted = old_fernet.decrypt(encrypted)
                all_creds[account_id] = json.loads(decrypted.decode("utf-8"))
            except InvalidToken:
                logger.error("rotate_decrypt_failed", account_id=account_id)

        if new_key:
            Path(self.key_path).write_bytes(new_key.encode())
        else:
            self.generate_key()

        self._fernet = None
        new_fernet = self._get_fernet()

        for account_id, creds in all_creds.items():
            payload = json.dumps(creds).encode("utf-8")
            encrypted = new_fernet.encrypt(payload)
            path = self._account_path(account_id)
            Path(path).write_bytes(encrypted)

        logger.info("key_rotated", accounts_re_encrypted=len(all_creds))
