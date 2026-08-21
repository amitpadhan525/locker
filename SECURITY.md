# Security Policy & Cryptographic Specifications

Security is the core pillar of **Locker**. Because Locker handles sensitive credentials, secret notes, private files, and cryptographic keys, we maintain strict security guarantees, formal specifications, and transparent vulnerability reporting procedures.

---

## 1. Supported Versions

| Version | Supported | Security Fixes |
| ------- | --------- | -------------- |
| `v1.x`  | :white_check_mark: Yes | Active Maintenance & Security Patches |
| `< 1.0` | :x: No | Obsolete |

---

## 2. Cryptographic Specifications

Locker relies exclusively on battle-tested cryptographic primitives from Python's standard `cryptography` hazard-mat primitives.

| Primitive | Specification | Configuration / Parameters |
|---|---|---|
| **Authenticated Cipher** | **AES-256-GCM** | 256-bit symmetric key, 96-bit nonce (`os.urandom(12)`), 128-bit MAC auth tag |
| **Primary Key Derivation (KDF)** | **Argon2id** | Memory: 64 MB (65,536 KiB), Iterations: 2, Lanes: 4, Salt: 16 Bytes (`os.urandom(16)`) |
| **Fallback Key Derivation** | **PBKDF2 HMAC-SHA256** | Iterations: 600,000, Hash: SHA-256, Salt: 16 Bytes (`os.urandom(16)`) |
| **Entropy Source** | `os.urandom` | Cryptographically Secure Pseudorandom Number Generator (CSPRNG) |
| **Header Integrity** | Associated Data (AD) | Header magic `SECVAULT` bound to AES-GCM MAC tag |

---

## 3. Threat Model

### In Scope (Guaranteed Protections)

- **Physical Theft of Storage Device**: An attacker who steals a laptop, USB drive, or `.vault` file cannot decrypt or read stored files without the master password.
- **Bit-Flip / Ciphertext Tampering**: Any modification to the binary header, salt, nonce, ciphertext payload, or authentication tag is detected immediately during tag verification, preventing corrupted payload execution.
- **Shoulder Surfing / Inactivity**: Automated 15-minute auto-lock locks the vault session, purging master key material from RAM.
- **Data Inflight Corruption**: Atomic file replacement (`os.replace` via `.vault.tmp`) ensures container files are never truncated or corrupted if system power fails mid-save.

### Out of Scope (Assumed Risks)

- **Compromised Host Kernel / Root Malware**: If an attacker installs an active rootkit or kernel-level keylogger on the host machine, they may intercept master passwords as typed.
- **Active Memory Dump During Unlocked State**: While unlocked, the master key exists in RAM. Memory scraping tools with administrative privileges on the host OS could read process memory while active.
- **Extreme Weak Master Passwords**: If a user selects a trivial master password (e.g. `123456`), high-performance GPU dictionary attacks may bypass Argon2id derivation over time.

---

## 4. Memory Lifecycle & Wiping Strategy

1. **RAM-Only Key Existence**: Master keys and derived keys are generated in RAM upon unlock and are never written to disk or swapped out to unencrypted storage.
2. **Auto-Lock Timeout**: If no user interaction occurs for 900 seconds (15 minutes), the active session purges `master_key`, `salt`, and `vault_data` references from memory.
3. **Secure Directory Unmounting & Shredding**: When unmounting a virtual drive folder, Locker executes a 0-byte overwrite (`0x00`) across all unencrypted temporary files before removing them from the filesystem.

---

## 5. Security Best Practices for Users

- **Use a Strong Master Passphrase**: Combine 4+ random words or a passphrase with 16+ characters.
- **Keep Backups Offline**: Copy `vault.vault` to an encrypted USB flash drive stored in a physically secure location.
- **Lock Manual Sessions**: Use `Ctrl+L` or click **Lock Vault** whenever walking away from your workstation.

---

## 6. Reporting a Vulnerability

If you discover a security vulnerability or cryptographic flaw in Locker, please do **NOT** open a public GitHub issue.

### Responsible Disclosure Protocol

1. **Email Contact**: Send details to `security@locker-vault.org` (or directly contact repository maintainers via private security advisory on GitHub).
2. **Details to Include**:
   - Description of the vulnerability or flaw.
   - Proof-of-concept (PoC) script or detailed steps to reproduce.
   - Impact assessment (e.g., key recovery, plaintext leak, denial of service).
3. **Response SLA**:
   - **Initial Acknowledgement**: Within 48 hours.
   - **Triage & Assessment**: Within 5 business days.
   - **Security Release / Patch**: Expedited priority patch release.

We strictly honor responsible disclosure and will attribute credit in our release notes for valid security reports.
