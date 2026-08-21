# Contributing to Locker

Thank you for your interest in contributing to **Locker**! We welcome contributions from developers of all skill levels—whether you're fixing a bug, improving documentation, adding new CLI features, or building cryptographic enhancements.

Because Locker handles user security and encrypted data, all contributions must adhere to high standards of security, code quality, and test coverage.

---

## ⚡ Quick Start: Clone & Run Locker in 60 Seconds

Get up and running locally with three simple commands:

```bash
# 1. Clone the repository
git clone https://github.com/amitpadhan525/locker.git
cd locker

# 2. Create virtual environment & install dependencies
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install cryptography pyperclip pytest coverage flake8

# 3. Run Locker Desktop GUI or CLI
python3 app.py        # Launch Desktop GUI Application
python3 cli.py status # Run Command Line Interface
```

### Run the Test Suite

Verify that your local environment is functioning correctly:

```bash
python3 -m unittest discover -p "test_*.py"
```

---

## 🏷️ Issue Labels Guide

We organize tasks on GitHub using standardized issue labels:

| Label | Description | Color |
|---|---|---|
| `good first issue` | Beginner-friendly tasks with clear instructions and code pointers. | `#7057ff` (Purple) |
| `help wanted` | Tasks seeking community contributions or specialized expertise. | `#008672` (Teal) |
| `security` | Cryptographic primitives, threat model, or memory lifecycle tasks. | `#d93f0b` (Red-Orange) |
| `documentation` | README, ARCHITECTURE, comments, or docstring improvements. | `#0075ca` (Blue) |
| `testing` | Unit test suite, CLI test coverage, or edge-case validation. | `#d4c5f9` (Light Purple) |

See [**ISSUES.md**](ISSUES.md) for a curated list of open tasks tagged with these labels!

---

## 🔒 Security Principles for Contributors

When writing code for Locker, you **MUST** follow these core security rules:

1. **Zero Cloud Dependencies**: Never add external HTTP network requests, analytics, telemetry, or remote API calls. Locker is 100% offline.
2. **Never Log Sensitive Key Material**: Never log, print, or store raw master passwords, salt, nonces, derived key bytes, or unencrypted payloads in debug output or log files.
3. **Use CSPRNG Output**: Always use `os.urandom()` for salts, nonces, and random token generation. Never use standard `random.random()`.
4. **Atomic File Persistence**: Always write modified containers to `.vault.tmp` temporary files first, then swap atomically using `os.replace()`.
5. **Secure Unmounting & Shredding**: Any temporary file creation must be paired with zero-byte (`0x00`) shred overwriting prior to unlinking/deletion.

---

## 📐 Coding Standards & Conventions

- **PEP 8 Compliance**: Follow standard Python style guidelines. Limit line length to 120 characters where readable.
- **Type Annotations**: Add type hints (`from typing import Optional, Dict, Tuple, Any`) for function arguments and return types.
- **Docstrings**: Document public functions, classes, and subcommands clearly.
- **Error Handling**: Use explicit exceptions (`VaultSecurityError`, `ValueError`, `FileNotFoundError`). Never catch raw `Exception` silently without rationale.

---

## 🧪 Testing Guidelines

Every pull request that modifies logic or adds features **must** include corresponding tests.

- Place unit tests in [`test_vault.py`](file:///home/amit/github/locker/test_vault.py) or [`test_cli.py`](file:///home/amit/github/locker/test_cli.py).
- Run the full test suite with coverage before submitting a PR:
  ```bash
  pytest --cov=.
  ```
- All tests must pass cleanly on Linux, macOS, and Windows.

---

## 🌿 Git & Pull Request Workflow

1. **Create a Feature Branch**:
   ```bash
   git checkout -b feature/cli-json-output
   # or
   git checkout -b fix/tamper-header-check
   ```

2. **Commit Your Changes**:
   Write clear, descriptive commit messages:
   ```bash
   git commit -m "feat(cli): add --json flag to list subcommand for machine parsing"
   ```

3. **Push to Your Fork**:
   ```bash
   git push origin feature/cli-json-output
   ```

4. **Open a Pull Request**:
   - Provide a clear title and description explaining what changed and why.
   - Reference any related issues (e.g. `Fixes #12`).
   - Confirm all checklist items are met.

---

## ✅ Pull Request Checklist

Before submitting your PR, ensure:

- [ ] Code passes PEP 8 linting (`flake8`).
- [ ] All unit tests pass (`python3 -m unittest discover -p "test_*.py"`).
- [ ] No security guidelines or offline constraints are violated.
- [ ] Documentation has been updated for new features or CLI options.
- [ ] PR description clearly explains the changes made.
