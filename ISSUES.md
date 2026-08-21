# Prepared Community Issues & Tasks

This file contains pre-formulated, high-quality **Good First Issue** and **Help Wanted** tasks for open-source contributors looking to work on **Locker**.

If you'd like to claim one of these issues, simply open a pull request or comment on GitHub referencing the issue title below!

---

## 🟢 Good First Issues (Beginner-Friendly)

### Issue #1: Add `--json` output flag to `cli.py list` for scriptable automation
- **Difficulty**: Beginner
- **Labels**: `good first issue`, `cli`, `enhancement`
- **Component**: [`cli.py`](file:///home/amit/github/locker/cli.py)
- **Description**:
  Currently, `python3 cli.py list` prints a formatted tabular text output suitable for human terminal reading. Power users who want to parse vault items in bash scripts or jq need structured JSON.
- **Tasks**:
  1. Add `--json` optional boolean argument to `list_parser` in `cli.py`.
  2. If `--json` is set, dump the items list as pretty-printed JSON (`json.dumps(items, indent=2)`).
  3. Add unit test in [`test_cli.py`](file:///home/amit/github/locker/test_cli.py) verifying `--json` output structure.

---

### Issue #2: Implement Password Entropy Meter in Desktop GUI
- **Difficulty**: Beginner
- **Labels**: `good first issue`, `gui`, `ux`
- **Component**: [`app.py`](file:///home/amit/github/locker/app.py)
- **Description**:
  Locker has a built-in random password generator modal in the Tkinter GUI. Adding a real-time entropy calculation display (e.g. $E = L \times \log_2(R)$ bits) and a color-coded strength bar (Weak / Moderate / Strong / Excellent) will help users craft stronger passphrases.
- **Tasks**:
  1. Calculate entropy bits based on character set size $R$ and length $L$.
  2. Render a dynamic `ttk.Progressbar` or colored indicator label in the password generator frame.
  3. Update dynamically whenever sliders or length checkboxes change.

---

### Issue #3: Add `cli.py export-raw` command for encrypted container backups
- **Difficulty**: Beginner
- **Labels**: `good first issue`, `cli`, `backup`
- **Component**: [`cli.py`](file:///home/amit/github/locker/cli.py)
- **Description**:
  Users frequently back up their encrypted `vault.vault` container to external USB drives. Adding a convenience subcommand `cli.py export-raw --dest /path/to/backup.vault` will validate container header integrity before copying.
- **Tasks**:
  1. Add `export-raw` subcommand parser to `cli.py`.
  2. Verify magic header `SECVAULT` before copying.
  3. Safely copy to target destination with timestamp suffix option (`--timestamp`).

---

## 🟡 Help Wanted Issues (Intermediate & Advanced)

### Issue #4: Native FUSE Filesystem Backend Driver (`vault_fuse.py`)
- **Difficulty**: Advanced
- **Labels**: `help wanted`, `filesystem`, `fuse`, `architecture`
- **Component**: `vault_fuse.py` (New File)
- **Description**:
  Currently, mounting a vault extracts decrypted files into a local folder (`0o700`). Implementing a native FUSE driver using `pyfuse3` or `fusepy` will allow users to mount `.vault` files directly as virtual filesystems in RAM without writing temporary files to disk.
- **Tasks**:
  1. Implement read-only/read-write FUSE operations mapping memory JSON data.
  2. Provide fallback gracefully if FUSE kernel modules are absent.
  3. Benchmark read/write performance compared to current mount implementation.

---

### Issue #5: YubiKey / FIDO2 HMAC-SHA1 Challenge-Response KDF Integration
- **Difficulty**: Advanced
- **Labels**: `help wanted`, `security`, `hardware-token`
- **Component**: [`vault_core.py`](file:///home/amit/github/locker/vault_core.py)
- **Description**:
  Enhance master key derivation by allowing users to mandate a YubiKey hardware token challenge-response output mixed with the Argon2id salt.
- **Tasks**:
  1. Add KDF type `KDF_ARGON2ID_YUBIKEY = 3`.
  2. Integrate `ykman` / `yubikey-manager` python bindings.
  3. Fall back gracefully with clear error prompts if hardware token is unplugged.
