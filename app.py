#!/usr/bin/env python3
import os
import sys
import json
import time
import base64
import urllib.parse
import webbrowser
import subprocess
from pathlib import Path
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from typing import Optional, Dict, Any

from vault_core import VaultCore, VaultSecurityError, DEFAULT_VAULT_FILE

PORT = 5000
HOST = "127.0.0.1"


class VaultSession:
    """In-memory session holding active unlocked vault state with auto-lock."""
    def __init__(self, vault_path: str = DEFAULT_VAULT_FILE):
        self.vault_path = vault_path
        self.master_key: Optional[bytes] = None
        self.salt: Optional[bytes] = None
        self.kdf_type: Optional[int] = None
        self.vault_data: Optional[Dict[str, Any]] = None
        self.last_activity: float = time.time()
        self.auto_lock_seconds: int = 900  # 15 minutes auto-lock timeout

    def is_initialized(self) -> bool:
        return os.path.exists(self.vault_path)

    def is_unlocked(self) -> bool:
        if self.master_key is None or self.vault_data is None:
            return False
        # Check auto lock timeout
        if time.time() - self.last_activity > self.auto_lock_seconds:
            self.lock()
            return False
        return True

    def touch(self):
        self.last_activity = time.time()

    def lock(self):
        self.master_key = None
        self.salt = None
        self.kdf_type = None
        self.vault_data = None
        self.last_activity = 0

    def unlock(self, password: str) -> bool:
        master_key, salt, kdf_type, vault_data = VaultCore.unlock_vault(self.vault_path, password)
        self.master_key = master_key
        self.salt = salt
        self.kdf_type = kdf_type
        self.vault_data = vault_data
        self.touch()
        return True

    def create(self, password: str) -> bool:
        master_key, salt, kdf_type, vault_data = VaultCore.create_vault(self.vault_path, password)
        self.master_key = master_key
        self.salt = salt
        self.kdf_type = kdf_type
        self.vault_data = vault_data
        self.touch()
        return True

    def save(self):
        if not self.is_unlocked():
            raise VaultSecurityError("Vault is locked. Cannot save changes.")
        VaultCore.save_vault(self.vault_path, self.master_key, self.salt, self.kdf_type, self.vault_data)
        self.touch()


session = VaultSession()


class VaultHTTPRequestHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        # Silence default verbose log output
        pass

    def send_json(self, status_code: int, data: Dict[str, Any]):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.end_headers()
        self.wfile.write(body)

    def send_error_json(self, status_code: int, message: str):
        self.send_json(status_code, {"error": message, "success": False})

    def serve_static(self, rel_path: str):
        static_dir = Path(__file__).parent / "static"
        target_path = (static_dir / rel_path.lstrip("/")).resolve()

        # Prevent path traversal
        if not str(target_path).startswith(str(static_dir.resolve())):
            self.send_error_json(403, "Access denied")
            return

        if not target_path.exists() or target_path.is_dir():
            target_path = static_dir / "index.html"

        ext = target_path.suffix.lower()
        content_type = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".json": "application/json",
            ".png": "image/png",
            ".svg": "image/svg+xml",
            ".ico": "image/x-icon"
        }.get(ext, "application/octet-stream")

        with open(target_path, "rb") as f:
            content = f.read()

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path.startswith("/api/"):
            self.handle_api_get(path, parsed.query)
        else:
            rel = "index.html" if path in ("/", "") else path
            self.serve_static(rel)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        content_len = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(content_len) if content_len > 0 else b""

        body_json = {}
        if raw_body:
            try:
                body_json = json.loads(raw_body.decode('utf-8'))
            except Exception:
                pass

        self.handle_api_post(path, body_json, raw_body)

    def do_DELETE(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path.startswith("/api/item/"):
            item_id = path.replace("/api/item/", "")
            self.handle_delete_item(item_id)
        else:
            self.send_error_json(404, "Endpoint not found")

    def handle_api_get(self, path: str, query_str: str):
        if path == "/api/status":
            unlocked = session.is_unlocked()
            item_count = 0
            if unlocked and session.vault_data:
                item_count = len(session.vault_data.get("items", {}))

            self.send_json(200, {
                "initialized": session.is_initialized(),
                "unlocked": unlocked,
                "item_count": item_count,
                "vault_path": session.vault_path,
                "success": True
            })

        elif path == "/api/items":
            if not session.is_unlocked():
                self.send_error_json(401, "Vault is locked")
                return

            items_list = []
            category_counts = {"All": 0, "Favorites": 0, "Documents": 0, "Notes": 0, "Passwords": 0, "Personal": 0}
            for item_id, item in session.vault_data.get("items", {}).items():
                is_fav = item.get("favorite", False)
                cat = item.get("category", "Documents")
                
                category_counts["All"] += 1
                if is_fav:
                    category_counts["Favorites"] += 1
                if cat in category_counts:
                    category_counts[cat] += 1
                else:
                    category_counts[cat] = 1

                items_list.append({
                    "id": item.get("id"),
                    "type": item.get("type"),
                    "name": item.get("name"),
                    "category": cat,
                    "mime_type": item.get("mime_type"),
                    "size": item.get("size", 0),
                    "created_at": item.get("created_at"),
                    "updated_at": item.get("updated_at"),
                    "notes": item.get("notes", ""),
                    "favorite": is_fav
                })

            # Sort by created_at descending
            items_list.sort(key=lambda x: x.get("created_at", ""), reverse=True)
            self.send_json(200, {"items": items_list, "counts": category_counts, "success": True})

        elif path.startswith("/api/item/"):
            if not session.is_unlocked():
                self.send_error_json(401, "Vault is locked")
                return

            item_id = path.replace("/api/item/", "")
            item = session.vault_data.get("items", {}).get(item_id)
            if not item:
                self.send_error_json(404, "Item not found")
                return

            self.send_json(200, {"item": item, "success": True})

        elif path.startswith("/api/download/"):
            if not session.is_unlocked():
                self.send_error_json(401, "Vault is locked")
                return

            item_id = path.replace("/api/download/", "")
            item = session.vault_data.get("items", {}).get(item_id)
            if not item:
                self.send_error_json(404, "Item not found")
                return

            fname, raw_bytes = VaultCore.extract_item_data(item)
            mime = item.get("mime_type", "application/octet-stream")

            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Disposition", f'attachment; filename="{urllib.parse.quote(fname)}"')
            self.send_header("Content-Length", str(len(raw_bytes)))
            self.end_headers()
            self.wfile.write(raw_bytes)

        elif path == "/api/export":
            if not session.is_unlocked():
                self.send_error_json(401, "Vault is locked")
                return

            if not os.path.exists(session.vault_path):
                self.send_error_json(404, "Vault file not found")
                return

            with open(session.vault_path, "rb") as f:
                content = f.read()

            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Disposition", f'attachment; filename="backup_{os.path.basename(session.vault_path)}"')
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        else:
            self.send_error_json(404, "Endpoint not found")

    def handle_api_post(self, path: str, body: Dict[str, Any], raw_body: bytes):
        if path == "/api/init":
            password = body.get("password", "")
            if not password:
                self.send_error_json(400, "Password required")
                return
            try:
                session.create(password)
                self.send_json(200, {"message": "Vault created successfully", "success": True})
            except Exception as e:
                self.send_error_json(400, str(e))

        elif path == "/api/unlock":
            password = body.get("password", "")
            if not password:
                self.send_error_json(400, "Password required")
                return
            try:
                session.unlock(password)
                self.send_json(200, {"message": "Vault unlocked", "success": True})
            except VaultSecurityError as e:
                self.send_error_json(401, str(e))
            except Exception as e:
                self.send_error_json(400, str(e))

        elif path == "/api/lock":
            session.lock()
            self.send_json(200, {"message": "Vault locked", "success": True})

        elif path == "/api/upload":
            if not session.is_unlocked():
                self.send_error_json(401, "Vault is locked")
                return

            filename = body.get("filename", "file.bin")
            b64_data = body.get("data_b64", "")
            category = body.get("category", "Documents")
            notes = body.get("notes", "")
            mime_type = body.get("mime_type", "application/octet-stream")

            if not b64_data:
                self.send_error_json(400, "File content missing")
                return

            try:
                file_bytes = base64.b64decode(b64_data.encode('utf-8'))
                item_id = VaultCore.add_file_item(session.vault_data, filename, file_bytes, category=category, notes=notes, mime_type=mime_type)
                session.save()
                self.send_json(200, {"item_id": item_id, "message": "File encrypted and stored", "success": True})
            except Exception as e:
                self.send_error_json(500, f"Error saving file: {e}")

        elif path == "/api/note":
            if not session.is_unlocked():
                self.send_error_json(401, "Vault is locked")
                return

            title = body.get("title", "")
            content = body.get("content", "")
            category = body.get("category", "Notes")
            notes = body.get("notes", "")

            if not title or not content:
                self.send_error_json(400, "Title and content required")
                return

            try:
                item_id = VaultCore.add_note_item(session.vault_data, title, content, category=category, notes=notes)
                session.save()
                self.send_json(200, {"item_id": item_id, "message": "Note encrypted and saved", "success": True})
            except Exception as e:
                self.send_error_json(500, f"Error saving note: {e}")

        elif path == "/api/favorite":
            if not session.is_unlocked():
                self.send_error_json(401, "Vault is locked")
                return

            item_id = body.get("item_id", "")
            if not item_id:
                self.send_error_json(400, "Item ID required")
                return

            is_fav = VaultCore.toggle_favorite(session.vault_data, item_id)
            session.save()
            self.send_json(200, {"item_id": item_id, "favorite": is_fav, "message": "Favorite updated", "success": True})

        elif path == "/api/batch-upload":
            if not session.is_unlocked():
                self.send_error_json(401, "Vault is locked")
                return

            files = body.get("files", [])
            if not files or not isinstance(files, list):
                self.send_error_json(400, "Files array required")
                return

            added_ids = []
            try:
                for file_info in files:
                    filename = file_info.get("filename", "file.bin")
                    b64_data = file_info.get("data_b64", "")
                    category = file_info.get("category", "Documents")
                    notes = file_info.get("notes", "")
                    mime_type = file_info.get("mime_type", "application/octet-stream")

                    if b64_data:
                        file_bytes = base64.b64decode(b64_data.encode('utf-8'))
                        item_id = VaultCore.add_file_item(session.vault_data, filename, file_bytes, category=category, notes=notes, mime_type=mime_type)
                        added_ids.append(item_id)

                session.save()
                self.send_json(200, {"added_count": len(added_ids), "item_ids": added_ids, "message": f"{len(added_ids)} files encrypted & stored", "success": True})
            except Exception as e:
                self.send_error_json(500, f"Error processing batch upload: {e}")

        elif path == "/api/change-password":
            if not session.is_unlocked():
                self.send_error_json(401, "Vault is locked")
                return

            old_pwd = body.get("old_password", "")
            new_pwd = body.get("new_password", "")

            if not old_pwd or not new_pwd:
                self.send_error_json(400, "Both current and new passwords are required")
                return

            try:
                master_key, salt, kdf_type, vault_data = VaultCore.change_password(session.vault_path, old_pwd, new_pwd)
                session.master_key = master_key
                session.salt = salt
                session.kdf_type = kdf_type
                session.vault_data = vault_data
                session.touch()
                self.send_json(200, {"message": "Password changed successfully", "success": True})
            except VaultSecurityError as e:
                self.send_error_json(401, str(e))
            except Exception as e:
                self.send_error_json(500, str(e))

        else:
            self.send_error_json(404, "Endpoint not found")

    def handle_delete_item(self, item_id: str):
        if not session.is_unlocked():
            self.send_error_json(401, "Vault is locked")
            return

        if VaultCore.delete_item(session.vault_data, item_id):
            session.save()
            self.send_json(200, {"message": "Item deleted", "success": True})
        else:
            self.send_error_json(404, "Item not found")


def launch_desktop_app_mode(url: str):
    """Attempts to launch Chromium/Chrome/Edge in standalone App Mode window."""
    browsers = ["google-chrome", "chromium-browser", "chromium", "microsoft-edge", "chrome"]
    for browser_cmd in browsers:
        try:
            res = subprocess.run(["which", browser_cmd], capture_output=True, text=True)
            if res.returncode == 0:
                print(f"Launching standalone app mode using '{browser_cmd}'...")
                subprocess.Popen([browser_cmd, f"--app={url}", "--name=EncryptedVault"])
                return True
        except Exception:
            pass

    # Fallback to standard web browser
    print("Opening in default browser...")
    webbrowser.open(url)
    return False


def prompt_master_password_gui(vault_path: str, session_obj: VaultSession) -> bool:
    """
    Opens a native Tkinter modal dialog to unlock or initialize the specified vault.
    Returns True if successfully unlocked/created, False if canceled or closed.
    """
    try:
        import tkinter as tk
    except ImportError:
        print("Warning: tkinter is not installed. Cannot open native GUI prompt.")
        return False

    is_existing = os.path.exists(vault_path)
    vault_name = os.path.basename(vault_path)
    success = False

    root = tk.Tk()
    root.title(f"Locker - {'Unlock' if is_existing else 'Create'} Vault")
    root.geometry("440x260")
    root.resizable(False, False)
    root.configure(bg="#0f172a")

    # Center window on screen
    root.update_idletasks()
    width = root.winfo_width()
    height = root.winfo_height()
    x = (root.winfo_screenwidth() // 2) - (width // 2)
    y = (root.winfo_screenheight() // 2) - (height // 2)
    root.geometry(f'+{x}+{y}')

    # Header
    header_frame = tk.Frame(root, bg="#0f172a")
    header_frame.pack(fill="x", padx=20, pady=(15, 5))

    title_label = tk.Label(
        header_frame,
        text="🔐 Locker Vault",
        font=("Helvetica", 14, "bold"),
        fg="#06b6d4",
        bg="#0f172a"
    )
    title_label.pack(anchor="w")

    subtitle_text = f"Opening: {vault_name}" if is_existing else f"Initializing: {vault_name}"
    sub_label = tk.Label(
        header_frame,
        text=subtitle_text,
        font=("Helvetica", 9),
        fg="#94a3b8",
        bg="#0f172a"
    )
    sub_label.pack(anchor="w", pady=(2, 0))

    # Form Container
    form_frame = tk.Frame(root, bg="#1e293b", padx=15, pady=15)
    form_frame.pack(fill="both", expand=True, padx=15, pady=5)

    pwd_label_text = "Master Password:" if is_existing else "Set Master Password:"
    pwd_label = tk.Label(
        form_frame,
        text=pwd_label_text,
        font=("Helvetica", 10, "bold"),
        fg="#f8fafc",
        bg="#1e293b"
    )
    pwd_label.pack(anchor="w", pady=(0, 5))

    pwd_entry = tk.Entry(
        form_frame,
        show="•",
        font=("Helvetica", 11),
        bg="#0f172a",
        fg="#f8fafc",
        insertbackground="#06b6d4",
        relief="flat",
        bd=4
    )
    pwd_entry.pack(fill="x", pady=(0, 5))
    pwd_entry.focus_set()

    error_label = tk.Label(
        form_frame,
        text="",
        font=("Helvetica", 9),
        fg="#f87171",
        bg="#1e293b"
    )
    error_label.pack(anchor="w")

    def on_submit(event=None):
        nonlocal success
        pwd = pwd_entry.get().strip()
        if not pwd:
            error_label.config(text="Password cannot be empty.", fg="#f87171")
            return

        error_label.config(text="Decrypting & Verifying...", fg="#38bdf8")
        root.update()

        try:
            if is_existing:
                session_obj.unlock(pwd)
            else:
                session_obj.create(pwd)
            success = True
            root.destroy()
        except VaultSecurityError:
            error_label.config(text="Incorrect password. Access denied.", fg="#f87171")
            pwd_entry.delete(0, tk.END)
        except Exception as err:
            error_label.config(text=f"Error: {str(err)}", fg="#f87171")

    pwd_entry.bind("<Return>", on_submit)

    # Button Container
    btn_frame = tk.Frame(root, bg="#0f172a", pady=10, padx=20)
    btn_frame.pack(fill="x")

    cancel_btn = tk.Button(
        btn_frame,
        text="Cancel",
        command=root.destroy,
        bg="#334155",
        fg="#f8fafc",
        activebackground="#475569",
        activeforeground="#ffffff",
        relief="flat",
        padx=15,
        pady=5,
        cursor="hand2"
    )
    cancel_btn.pack(side="right", padx=(10, 0))

    action_text = "Unlock" if is_existing else "Create & Unlock"
    action_btn = tk.Button(
        btn_frame,
        text=action_text,
        command=on_submit,
        bg="#06b6d4",
        fg="#0f172a",
        font=("Helvetica", 10, "bold"),
        activebackground="#0891b2",
        activeforeground="#ffffff",
        relief="flat",
        padx=18,
        pady=5,
        cursor="hand2"
    )
    action_btn.pack(side="right")

    root.mainloop()
    return success


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Local Encrypted Storage Vault Server")
    parser.add_argument("vault_file", nargs="?", default=None, help="Path to .locker or .vault file to open")
    parser.add_argument("--vault", default=None, help="Path to .locker or .vault file")
    parser.add_argument("--gui", action="store_true", help="Force native GUI password prompt")
    parser.add_argument("--no-browser", action="store_true", help="Do not open browser automatically")
    parser.add_argument("--port", type=int, default=PORT, help="Port to run server on")

    args = parser.parse_args()

    target_vault = args.vault or args.vault_file
    if target_vault:
        session.vault_path = os.path.abspath(target_vault)
        # Prompt password via native Tkinter GUI when opened with a file argument or --gui flag
        print(f"Opening target vault file: {session.vault_path}")
        unlocked = prompt_master_password_gui(session.vault_path, session)
        if not unlocked:
            print("Vault unlock canceled by user. Exiting.")
            sys.exit(0)

    server = ThreadingHTTPServer((HOST, args.port), VaultHTTPRequestHandler)
    url = f"http://{HOST}:{args.port}"

    print("=" * 60)
    print("      LOCAL ENCRYPTED STORAGE VAULT (100% OFFLINE)")
    print("=" * 60)
    print(f" Vault File: {session.vault_path}")
    print(f" Server running locally at: {url}")
    print(" Security: Zero cloud access, bound strictly to 127.0.0.1")
    print(" Press Ctrl+C to stop the vault server.")
    print("=" * 60)

    # Launch browser / app mode unless --no-browser flag is passed
    if not args.no_browser:
        launch_desktop_app_mode(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nLocking vault and shutting down server safely...")
        session.lock()
        server.server_close()
        sys.exit(0)


if __name__ == "__main__":
    main()

