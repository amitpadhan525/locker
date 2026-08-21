import os
import json
import base64
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Tuple, Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

MAGIC_HEADER = b"SECVAULT"
VERSION = 1
KDF_ARGON2ID = 1
KDF_PBKDF2 = 2
DEFAULT_SALT_SIZE = 16
DEFAULT_NONCE_SIZE = 12
DEFAULT_VAULT_FILE = "vault.vault"


class VaultSecurityError(Exception):
    """Raised when authentication fails, password is wrong, or vault is corrupted."""
    pass


class VaultCore:
    """
    Cryptographic core engine for zero-knowledge, local-only encrypted vault storage.
    Uses AES-256-GCM for authenticated encryption and Argon2id / PBKDF2 for KDF.
    """

    @staticmethod
    def derive_key(password: str, salt: bytes, kdf_type: int = KDF_ARGON2ID) -> bytes:
        """Derives a 256-bit symmetric encryption key from a master password and salt."""
        password_bytes = password.encode('utf-8')
        if kdf_type == KDF_ARGON2ID:
            try:
                kdf = Argon2id(
                    salt=salt,
                    length=32,
                    iterations=2,
                    memory_cost=65536,  # 64 MB RAM cost
                    lanes=4,
                )
                return kdf.derive(password_bytes)
            except Exception:
                # Fall back to PBKDF2 if Argon2id fails
                kdf_type = KDF_PBKDF2

        if kdf_type == KDF_PBKDF2:
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=600000,
            )
            return kdf.derive(password_bytes)
        
        raise ValueError("Unsupported KDF type")

    @classmethod
    def create_vault(cls, filepath: str, master_password: str) -> Tuple[bytes, bytes, int, Dict[str, Any]]:
        """Initializes a new encrypted vault container file."""
        if not master_password or len(master_password) < 6:
            raise ValueError("Master password must be at least 6 characters long.")

        salt = os.urandom(DEFAULT_SALT_SIZE)
        kdf_type = KDF_ARGON2ID
        master_key = cls.derive_key(master_password, salt, kdf_type)

        now_iso = datetime.now(timezone.utc).isoformat()
        vault_data = {
            "vault_id": str(uuid.uuid4()),
            "created_at": now_iso,
            "updated_at": now_iso,
            "version": VERSION,
            "items": {}
        }

        cls.save_vault(filepath, master_key, salt, kdf_type, vault_data)
        return master_key, salt, kdf_type, vault_data

    @classmethod
    def save_vault(cls, filepath: str, master_key: bytes, salt: bytes, kdf_type: int, vault_data: Dict[str, Any]) -> None:
        """Encrypts vault data and writes to the binary container file via atomic write."""
        vault_data["updated_at"] = datetime.now(timezone.utc).isoformat()
        json_bytes = json.dumps(vault_data, ensure_ascii=False).encode('utf-8')

        aesgcm = AESGCM(master_key)
        nonce = os.urandom(DEFAULT_NONCE_SIZE)
        ciphertext = aesgcm.encrypt(nonce, json_bytes, MAGIC_HEADER)

        # Header binary layout:
        # MAGIC_HEADER (8 bytes) + VERSION (2 bytes uint16) + KDF_TYPE (1 byte) + SALT (16 bytes) + NONCE (12 bytes) + CIPHERTEXT_LEN (8 bytes uint64)
        version_bytes = VERSION.to_bytes(2, byteorder='big')
        kdf_bytes = kdf_type.to_bytes(1, byteorder='big')
        len_bytes = len(ciphertext).to_bytes(8, byteorder='big')

        header = MAGIC_HEADER + version_bytes + kdf_bytes + salt + nonce + len_bytes

        # Atomic write to temporary file first
        temp_filepath = f"{filepath}.tmp"
        with open(temp_filepath, "wb") as f:
            f.write(header)
            f.write(ciphertext)
        
        os.replace(temp_filepath, filepath)

    @classmethod
    def unlock_vault(cls, filepath: str, master_password: str) -> Tuple[bytes, bytes, int, Dict[str, Any]]:
        """
        Reads binary vault container, derives key, and decrypts payload.
        Returns: (master_key, salt, kdf_type, vault_data)
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Vault file '{filepath}' does not exist.")

        with open(filepath, "rb") as f:
            content = f.read()

        min_header_len = 8 + 2 + 1 + DEFAULT_SALT_SIZE + DEFAULT_NONCE_SIZE + 8
        if len(content) < min_header_len:
            raise VaultSecurityError("Invalid or corrupted vault file (file too small).")

        magic = content[:8]
        if magic != MAGIC_HEADER:
            raise VaultSecurityError("Invalid vault header. File is not a recognized vault format.")

        version = int.from_bytes(content[8:10], byteorder='big')
        if version > VERSION:
            raise VaultSecurityError(f"Unsupported vault format version ({version}).")
        kdf_type = content[10]
        salt = content[11:27]
        nonce = content[27:39]
        ciphertext_len = int.from_bytes(content[39:47], byteorder='big')

        ciphertext = content[47:47 + ciphertext_len]
        if len(ciphertext) != ciphertext_len:
            raise VaultSecurityError("Corrupted vault payload length mismatch.")

        master_key = cls.derive_key(master_password, salt, kdf_type)

        try:
            aesgcm = AESGCM(master_key)
            decrypted_bytes = aesgcm.decrypt(nonce, ciphertext, MAGIC_HEADER)
            vault_data = json.loads(decrypted_bytes.decode('utf-8'))
            return master_key, salt, kdf_type, vault_data
        except Exception:
            raise VaultSecurityError("Invalid master password or corrupted ciphertext tag verification failed.")

    @classmethod
    def add_file_item(cls, vault_data: Dict[str, Any], filepath_or_name: str, file_bytes: Optional[bytes] = None, category: str = "Documents", notes: str = "", mime_type: str = "application/octet-stream", rel_path: Optional[str] = None) -> str:
        """Adds an encrypted file entry to vault data."""
        item_id = str(uuid.uuid4())

        if file_bytes is None:
            file_path_obj = Path(filepath_or_name)
            filename = file_path_obj.name
            if os.path.exists(filepath_or_name):
                with open(filepath_or_name, "rb") as f:
                    file_bytes = f.read()
            else:
                file_bytes = b""
        else:
            filename = Path(filepath_or_name).name

        b64_data = base64.b64encode(file_bytes).decode('utf-8')

        now_iso = datetime.now(timezone.utc).isoformat()
        default_rel_path = str(Path(category) / filename)
        item = {
            "id": item_id,
            "type": "file",
            "name": filename,
            "category": category,
            "rel_path": rel_path or default_rel_path,
            "mime_type": mime_type,
            "size": len(file_bytes),
            "created_at": now_iso,
            "updated_at": now_iso,
            "data_b64": b64_data,
            "notes": notes,
            "favorite": False
        }

        vault_data.setdefault("items", {})[item_id] = item
        return item_id

    @classmethod
    def add_note_item(cls, vault_data: Dict[str, Any], title: str, content: str, category: str = "Notes", notes: str = "") -> str:
        """Adds a secure note / text entry to vault data."""
        item_id = str(uuid.uuid4())
        b64_data = base64.b64encode(content.encode('utf-8')).decode('utf-8')

        now_iso = datetime.now(timezone.utc).isoformat()
        rel_path = str(Path(category) / f"{title}.txt")
        item = {
            "id": item_id,
            "type": "note",
            "name": title,
            "category": category,
            "rel_path": rel_path,
            "mime_type": "text/plain",
            "size": len(content.encode('utf-8')),
            "created_at": now_iso,
            "updated_at": now_iso,
            "data_b64": b64_data,
            "notes": notes,
            "favorite": False
        }

        vault_data.setdefault("items", {})[item_id] = item
        return item_id

    @classmethod
    def extract_item_data(cls, item: Dict[str, Any]) -> Tuple[str, bytes]:
        """Decodes item base64 payload to raw bytes."""
        b64_data = item.get("data_b64", "")
        raw_bytes = base64.b64decode(b64_data.encode('utf-8'))
        return item.get("name", "extracted_file"), raw_bytes

    @classmethod
    def delete_item(cls, vault_data: Dict[str, Any], item_id: str) -> bool:
        """Removes an item from vault data by ID."""
        if item_id in vault_data.get("items", {}):
            del vault_data["items"][item_id]
            return True
        return False

    @classmethod
    def toggle_favorite(cls, vault_data: Dict[str, Any], item_id: str) -> bool:
        """Toggles the favorite state of an item by ID."""
        items = vault_data.get("items", {})
        if item_id in items:
            items[item_id]["favorite"] = not items[item_id].get("favorite", False)
            items[item_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
            return items[item_id]["favorite"]
        return False

    @classmethod
    def change_password(cls, filepath: str, old_password: str, new_password: str) -> Tuple[bytes, bytes, int, Dict[str, Any]]:
        """Re-encrypts vault payload with a new master password."""
        _, _, _, vault_data = cls.unlock_vault(filepath, old_password)
        new_salt = os.urandom(DEFAULT_SALT_SIZE)
        kdf_type = KDF_ARGON2ID
        new_master_key = cls.derive_key(new_password, new_salt, kdf_type)

        cls.save_vault(filepath, new_master_key, new_salt, kdf_type, vault_data)
        return new_master_key, new_salt, kdf_type, vault_data

    @classmethod
    def mount_vault_to_dir(cls, vault_data: Dict[str, Any], target_dir: str) -> Dict[str, str]:
        """
        Exports decrypted vault items into target_dir with secure permissions (0o700).
        Returns a dictionary mapping relative file paths to item IDs.
        """
        path_obj = Path(target_dir)
        path_obj.mkdir(parents=True, exist_ok=True)
        os.chmod(target_dir, 0o700)

        # 1. Recreate custom folders
        folders = vault_data.get("folders", [])
        for rel_d in folders:
            folder_path = path_obj / rel_d
            folder_path.mkdir(parents=True, exist_ok=True)
            os.chmod(folder_path, 0o700)

        index_map = {}
        items = vault_data.get("items", {})

        for item_id, item in items.items():
            rel_path = item.get("rel_path")
            if not rel_path:
                cat = item.get("category", "General")
                if item.get("type") == "note":
                    filename = f"{item.get('name', 'note')}.txt"
                else:
                    filename = item.get("filename", item.get("name", "file"))
                rel_path = str(Path(cat) / filename)

            file_path = path_obj / rel_path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            os.chmod(file_path.parent, 0o700)

            b64_str = item.get("data_b64", "")
            content_bytes = base64.b64decode(b64_str.encode('utf-8')) if b64_str else item.get("content", "").encode('utf-8')

            with open(file_path, "wb") as f:
                f.write(content_bytes)
            os.chmod(file_path, 0o600)

            index_map[rel_path] = item_id

        index_file = path_obj / ".locker_index.json"
        with open(index_file, "w", encoding="utf-8") as f:
            json.dump(index_map, f, indent=2)
        os.chmod(index_file, 0o600)

        return index_map

    @classmethod
    def sync_dir_to_vault(cls, vault_data: Dict[str, Any], target_dir: str):
        """
        Scans target_dir for new, updated, or deleted files and directories and syncs them back into vault_data.
        """
        path_obj = Path(target_dir)
        index_file = path_obj / ".locker_index.json"

        index_map = {}
        if index_file.exists():
            with open(index_file, "r", encoding="utf-8") as f:
                index_map = json.load(f)

        scanned_rel_paths = set()
        scanned_rel_folders = set()

        for root, dirs, files in os.walk(target_dir):
            for d in dirs:
                if d.startswith("."):
                    continue
                full_d = Path(root) / d
                rel_d = str(full_d.relative_to(path_obj))
                scanned_rel_folders.add(rel_d)

            for file in files:
                if file.startswith(".locker_index") or file.startswith(".directory"):
                    continue
                full_p = Path(root) / file
                rel_p = str(full_p.relative_to(path_obj))
                scanned_rel_paths.add(rel_p)

                with open(full_p, "rb") as f:
                    raw_data = f.read()

                parts = Path(rel_p).parts
                cat = parts[0] if len(parts) > 1 else "Documents"

                # If file existed previously, update it
                if rel_p in index_map:
                    item_id = index_map[rel_p]
                    if item_id in vault_data.get("items", {}):
                        item = vault_data["items"][item_id]
                        b64_data = base64.b64encode(raw_data).decode('utf-8')
                        if item.get("type") == "note":
                            item["content"] = raw_data.decode('utf-8', errors='ignore')
                        item["data_b64"] = b64_data
                        item["rel_path"] = rel_p
                        item["category"] = cat
                        item["size"] = len(raw_data)
                        item["updated_at"] = datetime.now(timezone.utc).isoformat()
                else:
                    # New file created in mounted folder
                    item_id = cls.add_file_item(vault_data, str(full_p), category=cat, rel_path=rel_p)
                    index_map[rel_p] = item_id

        # Preserve created directories (even if empty)
        vault_data["folders"] = list(scanned_rel_folders)

        # Handle deleted files
        for rel_p, item_id in list(index_map.items()):
            if rel_p not in scanned_rel_paths:
                cls.delete_item(vault_data, item_id)
                del index_map[rel_p]

    @classmethod
    def secure_unmount_dir(cls, target_dir: str):
        """Safely wipes temporary unencrypted files and removes target_dir."""
        path_obj = Path(target_dir)
        if not path_obj.exists():
            return

        for root, dirs, files in os.walk(target_dir, topdown=False):
            for f in files:
                fp = os.path.join(root, f)
                try:
                    size = os.path.getsize(fp)
                    with open(fp, "ba+", buffering=0) as file_obj:
                        file_obj.write(b"\x00" * size)
                    os.remove(fp)
                except Exception:
                    pass
            for d in dirs:
                try:
                    os.rmdir(os.path.join(root, d))
                except Exception:
                    pass

        try:
            os.rmdir(target_dir)
        except Exception:
            pass

