# Locker Project Roadmap

This document outlines the development roadmap and vision for **Locker**. It reflects planned features, community feedback, architectural evolution, and cryptographic enhancements.

---

## 📍 Current Baseline: Version 1.0 (Released)

- [x] **Zero-Knowledge Core Engine**: AES-256-GCM authenticated encryption + Argon2id key derivation.
- [x] **Single Binary Container**: Atomic `.vault` container format with 47-byte fixed header.
- [x] **Native Desktop GUI**: Cross-platform Tkinter/TTK app with search, category filtering, password generator, and auto-lock.
- [x] **Power-User CLI**: Terminal commands for init, list, add-file, add-note, extract, delete, and password management.
- [x] **Virtual Drive Mount**: Local directory extraction with OS file manager & GTK sidebar integration.
- [x] **Secure Shredding**: 0-byte buffer overwrite (`0x00`) on temporary unmounted files.

---

## 🚀 Short-Term Roadmap (v1.1 - v1.2)

### Target: Streamlined Scripting, Packaging & Developer UX

- [ ] **CLI JSON Output Flag (`--json`)**
  - Add `--json` output flag to `cli.py list` and `cli.py status` to enable shell automation and script integration.
- [ ] **GUI Password Entropy Meter**
  - Add real-time entropy calculation (bits) and visual strength meter bar to the password generator component in `app.py`.
- [ ] **Vault Raw Export Command**
  - Add `cli.py export-raw` command for generating encrypted `.locker.bak` timestamped backups.
- [ ] **Automated Release Packages**
  - Standalone PyInstaller / AppImage builds for Linux and executable bundles for Windows/macOS.

---

## 🎯 Medium-Term Roadmap (v1.5 - v2.0)

### Target: FUSE Filesystem & Hardware Authentication

- [ ] **Native FUSE Filesystem Backend (`vault_fuse.py`)**
  - Implement a true FUSE (Filesystem in Userspace) driver allowing transparent read/write mounting of `.vault` containers without requiring temp folder extractions.
- [ ] **YubiKey & FIDO2 / WebAuthn Integration**
  - Support hardware token HMAC-SHA1 challenge-response key derivation (YubiKey 5 Series) as a secondary factor for vault decryption.
- [ ] **Shamir's Secret Sharing (Split-Key Recovery)**
  - Optional threshold key splitting ($M$-of-$N$ shares) for multi-party vault recovery without single master password failure.
- [ ] **Multi-Vault Tabbed Interface**
  - Desktop GUI support for opening and unlocking multiple `.vault` containers simultaneously in tabbed views.

---

## 🔮 Long-Term Vision (Post-v2.0)

### Target: Post-Quantum Cryptography & Enclave Hardware

- [ ] **Post-Quantum Hybrid Cryptography (ML-KEM / Kyber768)**
  - Upgrade container header to support hybrid key encapsulation pairing AES-256-GCM with post-quantum ML-KEM algorithms to protect against future quantum decapsulation attacks.
- [ ] **Hardware Enclave Key Storage (TPM 2.0 / Apple Secure Enclave)**
  - Optional binding of vault master keys to host hardware security modules (TPM 2.0 / Secure Enclave).
- [ ] **Zero-Knowledge Encrypted Backup Sync Driver**
  - Optional local rclone-compatible encrypted envelope sync adapter for automated offsite USB/NAS backups.

---

## 💬 Community Feedback & Contributions

Have a feature request or suggestion?
- Check out existing proposals in [ISSUES.md](file:///home/amit/github/locker/ISSUES.md).
- Open a discussion or feature request on [GitHub Issues](https://github.com/amitpadhan525/locker/issues).
- See [CONTRIBUTING.md](file:///home/amit/github/locker/CONTRIBUTING.md) to start building new features!
