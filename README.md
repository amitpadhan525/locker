# Aegis - Local Encrypted Data Storage & Vault Application

**Aegis** is a 100% offline, zero-knowledge encrypted container application designed to securely store files, secret notes, API keys, and credentials on your computer without relying on any external cloud or internet connection.

---

## 🔒 Security Specifications

* **Authenticated Encryption**: **AES-256-GCM** (Galois/Counter Mode) with 128-bit authentication tags to detect any bit-flips or tampering.
* **Key Derivation (KDF)**: **Argon2id** (memory-hard password hashing competition winner) deriving a 256-bit master key from your master password.
* **Random Salt & Nonce**: Cryptographically secure 128-bit salt and unique 96-bit nonce per encryption cycle generated using `os.urandom`.
* **Zero-Knowledge Architecture**: All encryption and decryption operations take place in local RAM. Master keys are never written to disk and are automatically wiped upon locking or timeout.
* **Single Container File**: Encrypted items are compiled into an atomic binary container file (`vault.vault`).

---

## 🚀 Quick Start (Running the App)

### 1. Launch the Application
Run `app.py` in your terminal:

```bash
python3 app.py
```

This starts the local server at `http://127.0.0.1:5000` and automatically opens the standalone application interface in your web browser.

> **Note**: To run headless without opening a browser window:
> ```bash
> python3 app.py --no-browser
> ```

---

## 🖥️ User Interface Features

1. **Initial Setup**: Set your Master Password upon first launch.
2. **Unlock Screen**: Unlock your vault with your master password.
3. **Drag & Drop File Encryptor**: Drag any document, PDF, image, archive, or code file to encrypt and store it inside `vault.vault`.
4. **Secret Notes & Credentials**: Store passwords, bank PINs, and private text notes.
5. **Password & Key Generator**: Generate high-entropy passwords with custom length and character sets.
6. **Search & Category Filters**: Search through your stored encrypted items by title, category, or note.
7. **Decryption & Export**: Preview or download your original files on demand with a single click.
8. **Offline Backup**: Download a raw copy of `vault.vault` to back up to a USB flash drive or offline storage.

---

## 💻 Command Line Interface (CLI) Usage

For power users or headless terminal environments, use `cli.py`:

```bash
# 1. Initialize a new vault
python3 cli.py init

# 2. Check vault status
python3 cli.py status

# 3. Add an encrypted file
python3 cli.py add-file /path/to/confidential.pdf --category "Documents" --notes "Tax documents 2026"

# 4. Add a secret note
python3 cli.py add-note --title "WiFi Password" --content "SuperSecretPassphrase123" --category "Passwords"

# 5. List all items in vault
python3 cli.py list

# 6. Extract/Decrypt an item to file
python3 cli.py extract --id <ITEM_UUID> --out decrypted_document.pdf

# 7. Delete an item from vault
python3 cli.py delete --id <ITEM_UUID>

# 8. Change Master Password (re-encrypts vault)
python3 cli.py change-password
```

---

## 🧪 Automated Testing

To run the unit test suite verifying AES-GCM encryption, Argon2id derivation, and tampering detection:

```bash
python3 -m unittest test_vault.py
```

---

## 📜 License

This project is open-source software licensed under the **[GNU General Public License v3.0 (GPL-3.0)](LICENSE)**. 

You are free to use, modify, and distribute this software under the terms of the GPL-3.0 license. Any derivative works or distributions must also remain free and open-source under the same GPL v3.0 license terms.

