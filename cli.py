#!/usr/bin/env python3
import sys
import os
import argparse
import getpass
from pathlib import Path
from vault_core import VaultCore, VaultSecurityError, DEFAULT_VAULT_FILE


def get_password(prompt="Enter Master Password: ", confirm=False):
    p1 = getpass.getpass(prompt)
    if confirm:
        p2 = getpass.getpass("Confirm Master Password: ")
        if p1 != p2:
            print("Error: Passwords do not match.", file=sys.stderr)
            sys.exit(1)
    return p1


def main():
    parser = argparse.ArgumentParser(description="Local Encrypted Vault CLI Tool")
    parser.add_argument("--vault", default=DEFAULT_VAULT_FILE, help="Path to vault file (default: vault.vault)")

    subparsers = parser.add_subparsers(dest="command", help="Subcommand to execute")

    # init
    subparsers.add_parser("init", help="Initialize a new encrypted vault")

    # status
    subparsers.add_parser("status", help="Check status of the vault file")

    # list
    subparsers.add_parser("list", help="List all items in the vault")

    # add-file
    add_file_parser = subparsers.add_parser("add-file", help="Encrypt and add a file to the vault")
    add_file_parser.add_argument("file_path", help="Path to local file to encrypt and store")
    add_file_parser.add_argument("--category", default="Documents", help="Category (e.g. Work, Personal)")
    add_file_parser.add_argument("--notes", default="", help="Optional description/notes")

    # add-note
    add_note_parser = subparsers.add_parser("add-note", help="Add a secure text note to the vault")
    add_note_parser.add_argument("--title", required=True, help="Title of note")
    add_note_parser.add_argument("--content", help="Text content (if omitted, will prompt)")
    add_note_parser.add_argument("--category", default="Notes", help="Category")

    # extract
    extract_parser = subparsers.add_parser("extract", help="Decrypt and extract an item from vault")
    extract_parser.add_argument("--id", required=True, help="Item ID to extract")
    extract_parser.add_argument("--out", help="Output file path (default: original filename)")

    # delete
    delete_parser = subparsers.add_parser("delete", help="Delete an item from vault")
    delete_parser.add_argument("--id", required=True, help="Item ID to remove")

    # change-password
    subparsers.add_parser("change-password", help="Re-encrypt vault with a new master password")

    # register-association
    subparsers.add_parser("register-association", help="Register .locker and .vault file association in OS for double-clicking")



    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    vault_path = args.vault

    if args.command == "init":
        if os.path.exists(vault_path):
            print(f"Error: Vault file '{vault_path}' already exists.", file=sys.stderr)
            sys.exit(1)
        pwd = get_password("Set New Master Password: ", confirm=True)
        try:
            VaultCore.create_vault(vault_path, pwd)
            print(f"Success: Initialized new encrypted vault at '{vault_path}'!")
        except Exception as e:
            print(f"Error initializing vault: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.command == "status":
        if not os.path.exists(vault_path):
            print(f"Vault status: File '{vault_path}' does not exist. Run 'init' first.")
        else:
            size_bytes = os.path.getsize(vault_path)
            print(f"Vault status: File '{vault_path}' exists ({size_bytes} bytes, encrypted).")

    elif args.command == "list":
        pwd = get_password()
        try:
            _, _, _, vault_data = VaultCore.unlock_vault(vault_path, pwd)
            items = vault_data.get("items", {})
            print(f"\n--- Vault Items ({len(items)}) ---")
            print(f"{'ID':<38} {'Type':<8} {'Category':<12} {'Size':<10} {'Name'}")
            print("-" * 80)
            for item_id, item in items.items():
                size_str = f"{item.get('size', 0)} B"
                print(f"{item_id:<38} {item.get('type'):<8} {item.get('category'):<12} {size_str:<10} {item.get('name')}")
            print("-" * 80)
        except VaultSecurityError as e:
            print(f"Authentication error: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.command == "add-file":
        if not os.path.exists(args.file_path):
            print(f"Error: File '{args.file_path}' not found.", file=sys.stderr)
            sys.exit(1)

        pwd = get_password()
        try:
            master_key, salt, kdf_type, vault_data = VaultCore.unlock_vault(vault_path, pwd)
            with open(args.file_path, "rb") as f:
                file_bytes = f.read()

            filename = os.path.basename(args.file_path)
            item_id = VaultCore.add_file_item(vault_data, filename, file_bytes, category=args.category, notes=args.notes)
            VaultCore.save_vault(vault_path, master_key, salt, kdf_type, vault_data)
            print(f"Success: Encrypted and stored '{filename}' (ID: {item_id})")
        except VaultSecurityError as e:
            print(f"Authentication error: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.command == "add-note":
        pwd = get_password()
        content = args.content
        if not content:
            content = input("Enter Note Content: ")

        try:
            master_key, salt, kdf_type, vault_data = VaultCore.unlock_vault(vault_path, pwd)
            item_id = VaultCore.add_note_item(vault_data, args.title, content, category=args.category)
            VaultCore.save_vault(vault_path, master_key, salt, kdf_type, vault_data)
            print(f"Success: Stored encrypted note '{args.title}' (ID: {item_id})")
        except VaultSecurityError as e:
            print(f"Authentication error: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.command == "extract":
        pwd = get_password()
        try:
            _, _, _, vault_data = VaultCore.unlock_vault(vault_path, pwd)
            items = vault_data.get("items", {})
            if args.id not in items:
                print(f"Error: Item ID '{args.id}' not found in vault.", file=sys.stderr)
                sys.exit(1)

            item = items[args.id]
            default_fname, raw_bytes = VaultCore.extract_item_data(item)
            out_path = args.out or default_fname

            with open(out_path, "wb") as f:
                f.write(raw_bytes)
            print(f"Success: Decrypted and saved '{item.get('name')}' to '{out_path}'")
        except VaultSecurityError as e:
            print(f"Authentication error: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.command == "delete":
        pwd = get_password()
        try:
            master_key, salt, kdf_type, vault_data = VaultCore.unlock_vault(vault_path, pwd)
            if VaultCore.delete_item(vault_data, args.id):
                VaultCore.save_vault(vault_path, master_key, salt, kdf_type, vault_data)
                print(f"Success: Deleted item '{args.id}' from vault.")
            else:
                print(f"Error: Item '{args.id}' not found.", file=sys.stderr)
        except VaultSecurityError as e:
            print(f"Authentication error: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.command == "change-password":
        old_pwd = get_password("Enter Current Master Password: ")
        new_pwd = get_password("Enter New Master Password: ", confirm=True)
        try:
            VaultCore.change_password(vault_path, old_pwd, new_pwd)
            print("Success: Master password updated and vault re-encrypted successfully.")
        except VaultSecurityError as e:
            print(f"Authentication error: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.command == "register-association":
        register_file_association()


def register_file_association():
    """Registers .locker and .vault file associations with the host OS."""
    import subprocess
    import platform

    system = platform.system()
    project_dir = Path(__file__).parent.resolve()
    app_py_path = project_dir / "app.py"

    print(f"Registering file association for system: {system}...")
    print(f"Target executable handler: python3 {app_py_path} --vault %f")

    if system == "Linux":
        apps_dir = Path.home() / ".local" / "share" / "applications"
        mime_dir = Path.home() / ".local" / "share" / "mime" / "packages"
        apps_dir.mkdir(parents=True, exist_ok=True)
        mime_dir.mkdir(parents=True, exist_ok=True)

        desktop_file = apps_dir / "locker-vault.desktop"
        desktop_content = f"""[Desktop Entry]
Name=Locker Encrypted Vault
Comment=Open local encrypted .locker and .vault files
Exec=python3 {app_py_path} --vault %f
Icon=lock
Terminal=false
Type=Application
MimeType=application/x-locker;application/x-vault;
Categories=Utility;Security;
"""
        with open(desktop_file, "w", encoding="utf-8") as f:
            f.write(desktop_content)
        os.chmod(desktop_file, 0o755)

        mime_xml = mime_dir / "application-x-locker.xml"
        mime_content = """<?xml version="1.0" encoding="UTF-8"?>
<mime-info xmlns="http://www.freedesktop.org/standards/shared-mime-info">
  <mime-type type="application/x-locker">
    <comment>Locker Encrypted Vault</comment>
    <glob pattern="*.locker"/>
    <glob pattern="*.vault"/>
  </mime-type>
</mime-info>
"""
        with open(mime_xml, "w", encoding="utf-8") as f:
            f.write(mime_content)

        # Update mime database and default applications
        try:
            subprocess.run(["update-mime-database", str(Path.home() / ".local" / "share" / "mime")], check=False)
            subprocess.run(["xdg-mime", "default", "locker-vault.desktop", "application/x-locker"], check=False)
            subprocess.run(["xdg-mime", "default", "locker-vault.desktop", "application/x-vault"], check=False)
        except Exception as e:
            print(f"Notice: xdg-mime command output: {e}")

        print(f"Success: Registered .locker desktop handler on Linux at:\n  {desktop_file}")

    elif system == "Windows":
        try:
            import winreg
            python_exe = sys.executable
            cmd = f'"{python_exe}" "{app_py_path}" --vault "%1"'
            
            for ext in [".locker", ".vault"]:
                with winreg.CreateKey(winreg.HKEY_CURRENT_USER, f"Software\\Classes\\{ext}") as key:
                    winreg.SetValue(key, "", winreg.REG_SZ, "LockerVaultFile")

            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, "Software\\Classes\\LockerVaultFile") as key:
                winreg.SetValue(key, "", winreg.REG_SZ, "Locker Encrypted Vault")

            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, "Software\\Classes\\LockerVaultFile\\shell\\open\\command") as key:
                winreg.SetValue(key, "", winreg.REG_SZ, cmd)

            print("Success: Registered .locker and .vault file associations in Windows Registry.")
        except Exception as e:
            print(f"Error registering Windows file association: {e}", file=sys.stderr)

    else:
        print(f"File association registered for {system}. Double-clicking .locker files will launch app.py with --vault argument.")


if __name__ == "__main__":
    main()

