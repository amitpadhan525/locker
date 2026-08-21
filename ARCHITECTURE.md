# Locker Architecture & Technical Specification

This document details the internal architecture, cryptographic design, memory lifecycle, container binary layout, and OS virtual drive mounting mechanics of **Locker**.

---

## 1. High-Level Architecture Overview

Locker is a **zero-knowledge, 100% offline encrypted container application**. It consists of three primary layers:

```
+-----------------------------------------------------------------------+
|                         User Interface Layer                          |
|    Desktop GUI (Tkinter/TTK)    |    CLI Tool (cli.py)                |
+-----------------------------------------------------------------------+
                                   |
                                   v
+-----------------------------------------------------------------------+
|                        Vault Core Engine                              |
|                    [vault_core.py](file:///home/amit/github/locker/vault_core.py)                     |
|  - Key Derivation: Argon2id (64 MB RAM, t=2, p=4) / PBKDF2 HMAC-SHA256  |
|  - Authenticated Symmetric Cipher: AES-256-GCM (128-bit MAC Tag)       |
|  - Virtual Drive Mount Manager & Secure Wiping / Shredder              |
+-----------------------------------------------------------------------+
                                   |
                                   v
+-----------------------------------------------------------------------+
|                    Single Binary Container File                       |
|                          (vault.vault)                                |
+-----------------------------------------------------------------------+
```

---

## 2. Container File Format (.vault / .locker)

A Locker container file consists of a **47-byte fixed binary header** followed immediately by an **AES-256-GCM encrypted ciphertext** and its **16-byte authentication tag**.

![Vault Binary Layout](assets/vault-binary-layout.svg)

### Binary Header Specification (47 Bytes)

| Offset (Bytes) | Field Name | Data Type | Value / Description |
|---|---|---|---|
| `0..7` (8B) | Magic Header | ASCII Bytes | `b"SECVAULT"` (`0x5345435641554c54`) |
| `8..9` (2B) | Format Version | uint16 (Big-Endian) | `1` (`0x0001`) |
| `10` (1B) | KDF Type ID | uint8 | `1` = Argon2id, `2` = PBKDF2 HMAC-SHA256 |
| `11..26` (16B)| Cryptographic Salt | Raw Bytes | 128-bit CSPRNG salt generated via `os.urandom(16)` |
| `27..38` (12B)| AES Nonce / IV | Raw Bytes | 96-bit CSPRNG nonce generated via `os.urandom(12)` |
| `39..46` (8B) | Ciphertext Length | uint64 (Big-Endian) | Exact byte length of the trailing payload |
| `47..end` | Payload + Tag | Ciphertext + Tag | AES-256-GCM encrypted JSON payload ending with 16B MAC tag |

---

## 3. Cryptographic Operations & Key Derivation

```
Master Password ("Secret123") + 16B Salt (os.urandom)
                    |
                    v
          Argon2id (m=64MB, t=2, p=4)
                    |
                    v
          256-bit Symmetric Key (32 Bytes)
                    |
                    v
   AES-256-GCM Encrypt/Decrypt (Nonce=12B, AD=b"SECVAULT")
```

### Key Derivation Function (KDF)
- **Primary KDF**: **Argon2id** configured with:
  - **Memory Cost**: 65,536 KiB (64 MB RAM)
  - **Time Cost / Iterations**: 2
  - **Parallelism / Lanes**: 4
  - **Output Key Size**: 32 bytes (256 bits)
- **Fallback KDF**: PBKDF2 HMAC-SHA256 with 600,000 iterations (used if Argon2 C-extensions are missing).

### Authenticated Encryption
- **Cipher**: **AES-256-GCM** (Galois/Counter Mode).
- **Associated Data (AD)**: `MAGIC_HEADER` (`b"SECVAULT"`). The header magic is bound to the authentication tag, ensuring header tampering causes immediate decryption failure.
- **Bit-Flip Protection**: Any modification to salt, nonce, header, ciphertext, or MAC tag causes a `VaultSecurityError` and halts decryption.

---

## 4. In-Memory Vault State Schema

Once decrypted, the payload is held in local RAM as a UTF-8 JSON object with the following structure:

```json
{
  "vault_id": "8f3b2a1c-9988-4e12-b123-abcdef456789",
  "created_at": "2026-08-21T19:00:00.000000+00:00",
  "updated_at": "2026-08-21T19:05:00.000000+00:00",
  "version": 1,
  "folders": ["Documents/Work", "Finance/Tax2026"],
  "items": {
    "e4a1b2c3-9876-4a12-8811-998877665544": {
      "id": "e4a1b2c3-9876-4a12-8811-998877665544",
      "type": "file",
      "name": "tax_document.pdf",
      "category": "Finance",
      "rel_path": "Finance/Tax2026/tax_document.pdf",
      "mime_type": "application/pdf",
      "size": 45281,
      "created_at": "2026-08-21T19:02:00+00:00",
      "updated_at": "2026-08-21T19:02:00+00:00",
      "data_b64": "<BASE64_ENCODED_BINARY_PAYLOAD>",
      "notes": "2026 Tax Return Copy",
      "favorite": true
    }
  }
}
```

---

## 5. Virtual Drive Mounting & OS Integration

Locker provides a **virtual drive mounting mechanism** allowing users to interact with decrypted files in their native OS File Manager (Thunar, Nautilus, Explorer, Finder).

![Lifecycle Sequence Diagram](assets/architecture-sequence.svg)

### Mount & Sync Workflow
1. **Mount**: `VaultCore.mount_vault_to_dir()` extracts decrypted items into a target local folder with restricted Unix permissions (`0o700` directory, `0o600` files).
2. **GTK Sidebar Bookmark**: On Linux, Locker registers the target path into `~/.config/gtk-3.0/bookmarks` to simulate a USB external drive.
3. **Double-Buffering Sync**: `VaultCore.sync_dir_to_vault()` scans the mounted directory for modifications, new files, or deletions and updates the JSON vault payload.
4. **Secure Unmount & Shred**: `VaultCore.secure_unmount_dir()` overwrites every decrypted file with zero bytes (`0x00`) before deleting the folder and removing GTK bookmarks.

---

## 6. Atomic File Persistence

To prevent vault corruption during power loss or application crashes:
1. Updated vault payload is encrypted and written to a temporary file (`vault.vault.tmp`).
2. `os.replace("vault.vault.tmp", "vault.vault")` performs an atomic POSIX filesystem swap.
3. If writing or encryption fails mid-operation, the existing `vault.vault` container remains untouched.

---

## 7. Key Code Modules

- [`vault_core.py`](file:///home/amit/github/locker/vault_core.py): Cryptographic engine, container format parser, KDF derivation, and mounting/shredding algorithms.
- [`app.py`](file:///home/amit/github/locker/app.py): Native Desktop GUI (Tkinter/TTK) with zero-knowledge session timer, file manager integration, and password generator.
- [`cli.py`](file:///home/amit/github/locker/cli.py): Headless command-line interface for terminal power users and OS file association installer.
- [`test_vault.py`](file:///home/amit/github/locker/test_vault.py): Automated unit test suite verifying encryption integrity, KDF derivation, and bit-flip tampering detection.
