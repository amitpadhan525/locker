#!/usr/bin/env python3
"""
Locker - Encrypted Storage Vault & Virtual Drive Mount
100% Offline, Native Desktop Application (Tkinter/TTK)
Zero Cloud Access, Zero HTTP Server, Zero Open Ports.
"""

import sys
import os
import re
import time
import json
import base64
import random
import string
import math
import subprocess
import platform
import shutil
import getpass
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from vault_core import VaultCore, VaultSecurityError, DEFAULT_VAULT_FILE


def open_in_file_manager(folder_path: str):
    """Launches the native OS file manager pointing to the specified directory."""
    system = platform.system()
    try:
        if system == "Linux":
            file_managers = ["thunar", "nautilus", "dolphin", "pcmanfm", "nemo", "caja", "spacefm"]
            launched = False
            for fm in file_managers:
                if shutil.which(fm):
                    subprocess.Popen([fm, folder_path])
                    launched = True
                    break
            if not launched:
                subprocess.Popen(["xdg-open", folder_path])
        elif system == "Windows":
            os.startfile(folder_path)
        elif system == "Darwin":
            subprocess.Popen(["open", folder_path])
    except Exception as e:
        print(f"Error launching OS file manager for {folder_path}: {e}")


def add_gtk_bookmark(path: str, label: str):
    """Adds path as a USB/Drive Bookmark in GTK sidebars (Thunar, Nautilus, PCManFM)."""
    try:
        uri = Path(path).as_uri()
        line_to_add = f"{uri} {label}\n"
        for cfg in ["~/.config/gtk-3.0", "~/.config/gtk-4.0"]:
            folder = os.path.expanduser(cfg)
            os.makedirs(folder, exist_ok=True)
            bm_file = os.path.join(folder, "bookmarks")
            lines = []
            if os.path.exists(bm_file):
                with open(bm_file, "r", encoding="utf-8") as f:
                    lines = f.readlines()
            if not any(uri in l for l in lines):
                lines.append(line_to_add)
                with open(bm_file, "w", encoding="utf-8") as f:
                    f.writelines(lines)
    except Exception as e:
        print(f"Notice: Failed to register GTK sidebar bookmark: {e}")


def remove_gtk_bookmark(path: str):
    """Removes path from GTK sidebars (Simulates USB Eject)."""
    try:
        uri = Path(path).as_uri()
        for cfg in ["~/.config/gtk-3.0", "~/.config/gtk-4.0"]:
            bm_file = os.path.expanduser(os.path.join(cfg, "bookmarks"))
            if os.path.exists(bm_file):
                with open(bm_file, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                new_lines = [l for l in lines if uri not in l]
                with open(bm_file, "w", encoding="utf-8") as f:
                    f.writelines(new_lines)
    except Exception as e:
        print(f"Notice: Failed to remove GTK sidebar bookmark: {e}")


class VaultSession:
    """In-memory session holding active unlocked vault state with auto-lock."""
    def __init__(self, vault_path: str = DEFAULT_VAULT_FILE):
        self.vault_path = os.path.abspath(vault_path)
        self.master_key: Optional[bytes] = None
        self.salt: Optional[bytes] = None
        self.kdf_type: Optional[int] = None
        self.vault_data: Optional[Dict[str, Any]] = None
        self.last_activity: float = time.time()
        self.auto_lock_seconds: int = 900  # 15 minutes auto-lock timeout
        self.mount_dir: Optional[str] = None
        self.loop_device: Optional[str] = None
        self.block_img_file: Optional[str] = None

    def is_initialized(self) -> bool:
        return os.path.exists(self.vault_path)

    def is_unlocked(self) -> bool:
        if self.master_key is None or self.vault_data is None:
            return False
        if time.time() - self.last_activity > self.auto_lock_seconds:
            self.lock()
            return False
        return True

    def touch(self):
        self.last_activity = time.time()

    def _get_existing_mount(self, vault_name: str) -> Optional[Tuple[Optional[str], str]]:
        """Returns (loop_device, mount_path) if locker_block_<vault_name>.img is already mounted."""
        img_file = f"/tmp/locker_block_{vault_name}.img"
        vol_label = vault_name[:11].upper()
        user = getpass.getuser()
        expected_mount = f"/run/media/{user}/{vol_label}"

        if os.path.exists("/proc/mounts"):
            try:
                with open("/proc/mounts", "r", encoding="utf-8") as f:
                    for line in f:
                        if img_file in line or expected_mount in line:
                            parts = line.split()
                            if len(parts) >= 2:
                                dev, target = parts[0], parts[1]
                                return (dev if dev.startswith("/dev/loop") else None), target
            except Exception:
                pass

        if os.path.exists(expected_mount) and os.path.ismount(expected_mount):
            return None, expected_mount

        return None

    def _mount_loop_block_device(self, vault_name: str) -> Optional[str]:
        """Creates a virtual VFAT block disk image, maps loop device via udisksctl, and mounts as USB volume."""
        # 1. Check if vault block device is already mounted (prevents duplicate mounts)
        existing = self._get_existing_mount(vault_name)
        if existing:
            dev, mount_path = existing
            self.loop_device = dev
            self.block_img_file = f"/tmp/locker_block_{vault_name}.img"
            return mount_path

        try:
            total_size_bytes = 0
            if self.vault_data and "items" in self.vault_data:
                for item in self.vault_data["items"].values():
                    total_size_bytes += item.get("size", 1024 * 10)

            size_mb = max(32, int((total_size_bytes / (1024 * 1024)) + 32))
            img_file = f"/tmp/locker_block_{vault_name}.img"
            if os.path.exists(img_file):
                try:
                    os.remove(img_file)
                except Exception:
                    pass

            subprocess.run(["truncate", "-s", f"{size_mb}M", img_file], check=True, capture_output=True)

            vol_label = vault_name[:11].upper()
            subprocess.run(["mkfs.vfat", "-n", vol_label, img_file], check=True, capture_output=True)

            res_loop = subprocess.run(["udisksctl", "loop-setup", "-f", img_file], capture_output=True, text=True, check=True)
            match = re.search(r"(/dev/loop\d+)", res_loop.stdout)
            if not match:
                return None
            loop_dev = match.group(1)

            res_mount = subprocess.run(["udisksctl", "mount", "-b", loop_dev], capture_output=True, text=True, check=True)
            match_path = re.search(r"at\s+(/\S+)", res_mount.stdout)
            if not match_path:
                subprocess.run(["udisksctl", "loop-delete", "-b", loop_dev], capture_output=True)
                return None

            mount_path = match_path.group(1).rstrip(".")

            self.loop_device = loop_dev
            self.block_img_file = img_file
            return mount_path
        except Exception as e:
            print(f"Notice: Block device udisksctl mount failed ({e}), falling back to media directory.")
            return None

    def _unmount_loop_block_device(self):
        """Unmounts and detaches udisksctl loop block device and cleans up disk image."""
        vault_name = Path(self.vault_path).stem
        existing = self._get_existing_mount(vault_name)

        loop_dev = self.loop_device
        if not loop_dev and existing and existing[0]:
            loop_dev = existing[0]

        if loop_dev:
            try:
                subprocess.run(["udisksctl", "unmount", "-b", loop_dev], capture_output=True)
            except Exception:
                pass
            try:
                subprocess.run(["udisksctl", "loop-delete", "-b", loop_dev], capture_output=True)
            except Exception:
                pass
            self.loop_device = None

        img_file = self.block_img_file or f"/tmp/locker_block_{vault_name}.img"
        if img_file and os.path.exists(img_file):
            try:
                os.remove(img_file)
            except Exception:
                pass
            self.block_img_file = None

    def lock(self):
        if self.mount_dir and os.path.exists(self.mount_dir):
            try:
                VaultCore.sync_dir_to_vault(self.vault_data, self.mount_dir)
                if self.master_key and self.vault_data:
                    VaultCore.save_vault(self.vault_path, self.master_key, self.salt, self.kdf_type, self.vault_data)
            except Exception:
                pass
            remove_gtk_bookmark(self.mount_dir)
            self._unmount_loop_block_device()
            VaultCore.secure_unmount_dir(self.mount_dir)
            self.mount_dir = None

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
        if self.mount_dir and os.path.exists(self.mount_dir):
            VaultCore.sync_dir_to_vault(self.vault_data, self.mount_dir)
        VaultCore.save_vault(self.vault_path, self.master_key, self.salt, self.kdf_type, self.vault_data)
        self.touch()

    def mount_virtual_drive(self) -> str:
        """Mounts vault contents to media USB drive directory and registers volume."""
        if not self.is_unlocked():
            raise VaultSecurityError("Vault is locked. Cannot mount drive.")

        vault_name = Path(self.vault_path).stem

        # 1. If vault block device is ALREADY mounted, sync and return existing mount
        existing = self._get_existing_mount(vault_name)
        if existing:
            dev, mount_path = existing
            self.loop_device = dev
            self.block_img_file = f"/tmp/locker_block_{vault_name}.img"
            self.mount_dir = mount_path
            try:
                VaultCore.sync_dir_to_vault(self.vault_data, mount_path)
                self.save()
            except Exception:
                pass
            return mount_path

        # 2. Fresh mount: setup loop device
        target_dir = self._mount_loop_block_device(vault_name)

        if not target_dir:
            user = getpass.getuser()
            candidate_dirs = [
                os.path.join("/media", user, vault_name),
                os.path.join("/run/media", user, vault_name),
                os.path.join("/tmp", "media", user, vault_name),
                os.path.join("/tmp", "locker_mounts", vault_name)
            ]

            for cand in candidate_dirs:
                try:
                    os.makedirs(cand, exist_ok=True)
                    target_dir = cand
                    break
                except Exception:
                    continue

        if not target_dir:
            target_dir = os.path.join("/tmp", "locker_mounts", vault_name)
            os.makedirs(target_dir, exist_ok=True)

        VaultCore.mount_vault_to_dir(self.vault_data, target_dir)
        self.mount_dir = target_dir

        # Add Desktop metadata for USB removable icon in file managers
        dot_directory = os.path.join(target_dir, ".directory")
        try:
            with open(dot_directory, "w", encoding="utf-8") as f:
                f.write(f"[Desktop Entry]\nIcon=drive-removable-media-usb\nName=🔒 USB Drive ({vault_name})\nType=Directory\n")
            os.chmod(dot_directory, 0o600)
        except Exception:
            pass

        # Register in file manager sidebar under Devices/Places
        add_gtk_bookmark(target_dir, f"🔒 USB Drive ({vault_name})")

        return target_dir

    def unmount_virtual_drive(self):
        if self.mount_dir and os.path.exists(self.mount_dir):
            if self.is_unlocked():
                VaultCore.sync_dir_to_vault(self.vault_data, self.mount_dir)
                self.save()
            remove_gtk_bookmark(self.mount_dir)
            self._unmount_loop_block_device()
            VaultCore.secure_unmount_dir(self.mount_dir)
            self.mount_dir = None


class LockerApp(tk.Tk):
    """Native Desktop GUI Application for Locker Encrypted Storage Vault."""

    def __init__(self, vault_path: str = DEFAULT_VAULT_FILE, auto_mount: bool = False):
        super().__init__()
        self.session = VaultSession(vault_path)
        self.auto_mount = auto_mount

        self.title(f"Locker - Encrypted Storage Vault [{os.path.basename(self.session.vault_path)}]")
        self.geometry("1020x660")
        self.minsize(840, 520)
        self.configure(bg="#0f172a")

        # Color Palette
        self.colors = {
            "bg": "#0f172a",
            "card": "#1e293b",
            "card_hover": "#334155",
            "primary": "#06b6d4",
            "primary_dark": "#0891b2",
            "text": "#f8fafc",
            "muted": "#94a3b8",
            "dim": "#64748b",
            "emerald": "#10b981",
            "danger": "#ef4444",
            "amber": "#f59e0b"
        }

        self.setup_styles()

        self.current_category = "All"
        self.search_query = ""

        # Protocol for graceful window closing (unmount virtual drive if active)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # Container Frame
        self.container = tk.Frame(self, bg=self.colors["bg"])
        self.container.pack(fill="both", expand=True)

        self.show_auth_screen()

        # Start background auto-sync timer (syncs folder & file changes from File Manager in real-time)
        self.after(2000, self.start_auto_sync_timer)

    def start_auto_sync_timer(self):
        """Periodically syncs mounted USB drive changes to encrypted vault every 2 seconds."""
        try:
            if hasattr(self, 'session') and self.session.is_unlocked() and self.session.mount_dir:
                if os.path.exists(self.session.mount_dir):
                    VaultCore.sync_dir_to_vault(self.session.vault_data, self.session.mount_dir)
                    VaultCore.save_vault(
                        self.session.vault_path,
                        self.session.master_key,
                        self.session.salt,
                        self.session.kdf_type,
                        self.session.vault_data
                    )
                    if hasattr(self, 'tree') and self.tree.winfo_exists():
                        self.refresh_items()
        except Exception:
            pass
        finally:
            self.after(2000, self.start_auto_sync_timer)

    def on_close(self):
        if self.session.is_unlocked() and self.session.mount_dir:
            try:
                VaultCore.sync_dir_to_vault(self.session.vault_data, self.session.mount_dir)
                self.session.save()
            except Exception:
                pass

            answer = messagebox.askyesnocancel(
                "Keep Virtual USB Drive Mounted?",
                f"The Vault USB Drive is currently active in your File Manager at:\n  {self.session.mount_dir}\n\n"
                "• Click [YES] to KEEP the USB Drive mounted & active in your File Manager.\n"
                "• Click [NO] to LOCK & UNMOUNT the USB Drive now.\n"
                "• Click [CANCEL] to stay in Locker.",
                parent=self
            )
            if answer is True:
                print(f"🟢 Vault USB Drive remains mounted & active at: {self.session.mount_dir}")
                self.destroy()
                return
            elif answer is False:
                self.session.lock()
                self.destroy()
            else:
                return
        else:
            if self.session.is_unlocked():
                self.session.lock()
            self.destroy()

    def setup_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")

        # Configure Treeview style
        style.configure(
            "Treeview",
            background=self.colors["card"],
            foreground=self.colors["text"],
            fieldbackground=self.colors["card"],
            rowheight=36,
            font=("Helvetica", 10),
            borderwidth=0
        )
        style.configure(
            "Treeview.Heading",
            background="#111827",
            foreground=self.colors["muted"],
            font=("Helvetica", 9, "bold"),
            borderwidth=0
        )
        style.map("Treeview", background=[("selected", self.colors["primary_dark"])], foreground=[("selected", "#ffffff")])

    def make_modal(self, window: tk.Toplevel):
        """Safely configures a Toplevel window as a modal dialog without grab errors."""
        window.transient(self)
        window.deiconify()
        window.update_idletasks()
        try:
            window.grab_set()
        except Exception:
            pass

    def show_auth_screen(self):
        for widget in self.container.winfo_children():
            widget.destroy()

        is_existing = self.session.is_initialized()
        vault_name = os.path.basename(self.session.vault_path)

        auth_frame = tk.Frame(self.container, bg=self.colors["bg"])
        auth_frame.place(relx=0.5, rely=0.5, anchor="center")

        card = tk.Frame(auth_frame, bg=self.colors["card"], padx=35, pady=35, highlightbackground=self.colors["card_hover"], highlightthickness=1)
        card.pack()

        # Icon & Title
        icon_label = tk.Label(card, text="🛡️" if not is_existing else "🔒", font=("Segoe UI Emoji", 36), bg=self.colors["card"])
        icon_label.pack(pady=(0, 10))

        title_text = "Create Encrypted Vault" if not is_existing else "Unlock Vault"
        lbl_title = tk.Label(card, text=title_text, font=("Helvetica", 16, "bold"), fg=self.colors["primary"], bg=self.colors["card"])
        lbl_title.pack()

        lbl_sub = tk.Label(card, text=f"Vault File: {vault_name}", font=("Helvetica", 9), fg=self.colors["muted"], bg=self.colors["card"])
        lbl_sub.pack(pady=(2, 20))

        # Password Entry
        lbl_pwd = tk.Label(card, text="Master Password:", font=("Helvetica", 10, "bold"), fg=self.colors["text"], bg=self.colors["card"])
        lbl_pwd.pack(anchor="w", pady=(0, 5))

        pwd_frame = tk.Frame(card, bg=self.colors["card"])
        pwd_frame.pack(fill="x", pady=(0, 10))

        self.entry_pwd = tk.Entry(
            pwd_frame,
            show="•",
            font=("Helvetica", 12),
            bg=self.colors["bg"],
            fg=self.colors["text"],
            insertbackground=self.colors["primary"],
            relief="flat",
            bd=6,
            width=30
        )
        self.entry_pwd.pack(side="left", fill="x", expand=True)
        self.entry_pwd.focus_set()

        self.show_pwd_var = tk.BooleanVar(value=False)
        btn_eye = tk.Checkbutton(
            pwd_frame,
            text="👁",
            variable=self.show_pwd_var,
            command=self.toggle_pwd_visibility,
            bg=self.colors["card"],
            fg=self.colors["muted"],
            activebackground=self.colors["card"],
            selectcolor=self.colors["bg"],
            indicatoron=False,
            bd=0,
            padx=8,
            cursor="hand2"
        )
        btn_eye.pack(side="right", padx=(5, 0))

        if not is_existing:
            lbl_confirm = tk.Label(card, text="Confirm Master Password:", font=("Helvetica", 10, "bold"), fg=self.colors["text"], bg=self.colors["card"])
            lbl_confirm.pack(anchor="w", pady=(5, 5))

            self.entry_confirm = tk.Entry(
                card,
                show="•",
                font=("Helvetica", 12),
                bg=self.colors["bg"],
                fg=self.colors["text"],
                insertbackground=self.colors["primary"],
                relief="flat",
                bd=6
            )
            self.entry_confirm.pack(fill="x", pady=(0, 15))

        self.lbl_auth_error = tk.Label(card, text="", font=("Helvetica", 9), fg=self.colors["danger"], bg=self.colors["card"])
        self.lbl_auth_error.pack(anchor="w", pady=(0, 10))

        btn_text = "🚀 Initialize Vault" if not is_existing else "🔓 Unlock & Open Vault"
        btn_submit = tk.Button(
            card,
            text=btn_text,
            command=self.handle_auth_submit,
            font=("Helvetica", 11, "bold"),
            bg=self.colors["primary"],
            fg=self.colors["bg"],
            activebackground=self.colors["primary_dark"],
            activeforeground="#ffffff",
            relief="flat",
            pady=8,
            cursor="hand2"
        )
        btn_submit.pack(fill="x")

        self.entry_pwd.bind("<Return>", lambda e: self.handle_auth_submit())
        if not is_existing:
            self.entry_confirm.bind("<Return>", lambda e: self.handle_auth_submit())

    def toggle_pwd_visibility(self):
        show_char = "" if self.show_pwd_var.get() else "•"
        self.entry_pwd.config(show=show_char)
        if hasattr(self, 'entry_confirm'):
            self.entry_confirm.config(show=show_char)

    def handle_auth_submit(self):
        pwd = self.entry_pwd.get().strip()
        if not pwd:
            self.lbl_auth_error.config(text="Password cannot be empty.")
            return

        is_existing = self.session.is_initialized()
        if not is_existing:
            confirm = self.entry_confirm.get().strip()
            if pwd != confirm:
                self.lbl_auth_error.config(text="Passwords do not match.")
                return

        self.lbl_auth_error.config(text="Decrypting & verifying...", fg=self.colors["primary"])
        self.update_idletasks()

        try:
            if is_existing:
                self.session.unlock(pwd)
            else:
                self.session.create(pwd)

            if self.auto_mount or True:  # Auto mount and open file manager on unlock
                self.mount_and_open_file_manager()

            self.show_dashboard()
        except VaultSecurityError:
            self.lbl_auth_error.config(text="Incorrect password. Access denied.", fg=self.colors["danger"])
            self.entry_pwd.delete(0, tk.END)
        except Exception as e:
            self.lbl_auth_error.config(text=f"Error: {str(e)}", fg=self.colors["danger"])

    def mount_and_open_file_manager(self):
        """Mounts vault to /tmp/locker_mounts and opens system file manager."""
        try:
            mount_path = self.session.mount_virtual_drive()
            open_in_file_manager(mount_path)
            messagebox.showinfo(
                "Vault Mounted as Virtual Drive",
                f"🟢 Vault successfully mounted to:\n  {mount_path}\n\nOpened in your File Manager! You can browse, edit, and save files natively."
            )
        except Exception as e:
            messagebox.showerror("Mount Error", f"Failed to mount virtual drive: {e}")

    def show_dashboard(self):
        for widget in self.container.winfo_children():
            widget.destroy()

        # Main Layout: Header, Filter Bar, Treeview, Action Bar
        header = tk.Frame(self.container, bg=self.colors["card"], padx=20, pady=12)
        header.pack(fill="x")

        # Brand / Title
        brand_frame = tk.Frame(header, bg=self.colors["card"])
        brand_frame.pack(side="left")

        lbl_logo = tk.Label(brand_frame, text="🛡️", font=("Segoe UI Emoji", 18), bg=self.colors["card"])
        lbl_logo.pack(side="left", padx=(0, 8))

        lbl_brand = tk.Label(brand_frame, text="Locker Vault", font=("Helvetica", 14, "bold"), fg=self.colors["primary"], bg=self.colors["card"])
        lbl_brand.pack(side="left")

        lbl_tag = tk.Label(brand_frame, text="OFFLINE", font=("Helvetica", 8, "bold"), fg=self.colors["emerald"], bg="#064e3b", padx=6, pady=2)
        lbl_tag.pack(side="left", padx=(10, 0))

        # Header Right Controls
        ctrl_frame = tk.Frame(header, bg=self.colors["card"])
        ctrl_frame.pack(side="right")

        self.lbl_stats = tk.Label(ctrl_frame, text="", font=("Helvetica", 9), fg=self.colors["muted"], bg=self.colors["card"])
        self.lbl_stats.pack(side="left", padx=(0, 12))

        btn_mount_fm = tk.Button(
            ctrl_frame,
            text="📁 Open File Manager",
            command=self.mount_and_open_file_manager,
            bg=self.colors["primary_dark"],
            fg="#ffffff",
            font=("Helvetica", 9, "bold"),
            relief="flat",
            padx=12,
            pady=4,
            cursor="hand2"
        )
        btn_mount_fm.pack(side="left", padx=(0, 8))

        btn_settings = tk.Button(
            ctrl_frame,
            text="⚙️ Settings",
            command=self.open_settings_modal,
            bg=self.colors["bg"],
            fg=self.colors["text"],
            relief="flat",
            padx=10,
            pady=4,
            cursor="hand2"
        )
        btn_settings.pack(side="left", padx=(0, 8))

        btn_lock = tk.Button(
            ctrl_frame,
            text="🔒 Lock & Unmount",
            command=self.lock_vault,
            bg=self.colors["danger"],
            fg="#ffffff",
            font=("Helvetica", 9, "bold"),
            relief="flat",
            padx=12,
            pady=4,
            cursor="hand2"
        )
        btn_lock.pack(side="left")

        # Toolbar Frame
        toolbar = tk.Frame(self.container, bg=self.colors["bg"], padx=20, pady=12)
        toolbar.pack(fill="x")

        # Search Box
        search_frame = tk.Frame(toolbar, bg=self.colors["card"], padx=10, pady=4)
        search_frame.pack(side="left", fill="x", expand=True, padx=(0, 15))

        lbl_src_icon = tk.Label(search_frame, text="🔍", font=("Segoe UI Emoji", 10), bg=self.colors["card"], fg=self.colors["muted"])
        lbl_src_icon.pack(side="left", padx=(0, 5))

        self.entry_search = tk.Entry(
            search_frame,
            font=("Helvetica", 10),
            bg=self.colors["card"],
            fg=self.colors["text"],
            insertbackground=self.colors["primary"],
            relief="flat",
            bd=2
        )
        self.entry_search.pack(side="left", fill="x", expand=True)
        self.entry_search.bind("<KeyRelease>", lambda e: self.refresh_items())

        # Category Chips
        cat_frame = tk.Frame(toolbar, bg=self.colors["bg"])
        cat_frame.pack(side="right")

        self.cat_buttons = {}
        categories = ["All", "Favorites", "Documents", "Notes", "Passwords", "Personal"]
        for cat in categories:
            btn = tk.Button(
                cat_frame,
                text=cat,
                command=lambda c=cat: self.set_category_filter(c),
                font=("Helvetica", 9),
                bg=self.colors["primary_dark"] if cat == "All" else self.colors["card"],
                fg="#ffffff" if cat == "All" else self.colors["muted"],
                relief="flat",
                padx=10,
                pady=4,
                cursor="hand2"
            )
            btn.pack(side="left", padx=2)
            self.cat_buttons[cat] = btn

        # Main Table / Treeview Container
        main_body = tk.Frame(self.container, bg=self.colors["bg"], padx=20, pady=0)
        main_body.pack(fill="both", expand=True)

        columns = ("fav", "name", "type", "category", "size", "date")
        self.tree = ttk.Treeview(main_body, columns=columns, show="headings", selectmode="browse")

        self.tree.heading("fav", text="⭐")
        self.tree.heading("name", text="Name")
        self.tree.heading("type", text="Type")
        self.tree.heading("category", text="Category")
        self.tree.heading("size", text="Size")
        self.tree.heading("date", text="Date Added")

        self.tree.column("fav", width=40, anchor="center")
        self.tree.column("name", width=340, anchor="w")
        self.tree.column("type", width=80, anchor="center")
        self.tree.column("category", width=120, anchor="center")
        self.tree.column("size", width=100, anchor="center")
        self.tree.column("date", width=160, anchor="center")

        scrollbar = ttk.Scrollbar(main_body, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.tree.bind("<Double-1>", lambda e: self.open_selected_item())
        self.tree.bind("<Return>", lambda e: self.open_selected_item())

        # Action Bar (Bottom - Dedicated Add Buttons)
        action_bar = tk.Frame(self.container, bg=self.colors["card"], padx=20, pady=10)
        action_bar.pack(fill="x")

        # Left Add Options
        btn_add_file = tk.Button(
            action_bar,
            text="📥 Encrypt File",
            command=self.open_add_files_modal,
            font=("Helvetica", 9, "bold"),
            bg=self.colors["primary"],
            fg=self.colors["bg"],
            activebackground=self.colors["primary_dark"],
            relief="flat",
            padx=12,
            pady=6,
            cursor="hand2"
        )
        btn_add_file.pack(side="left", padx=(0, 6))

        btn_add_note = tk.Button(
            action_bar,
            text="✍️ Secret Note",
            command=self.open_add_note_modal,
            font=("Helvetica", 9),
            bg=self.colors["bg"],
            fg=self.colors["text"],
            relief="flat",
            padx=10,
            pady=6,
            cursor="hand2"
        )
        btn_add_note.pack(side="left", padx=(0, 6))

        btn_add_pwd = tk.Button(
            action_bar,
            text="🔑 Add Password",
            command=self.open_add_password_modal,
            font=("Helvetica", 9),
            bg=self.colors["bg"],
            fg=self.colors["text"],
            relief="flat",
            padx=10,
            pady=6,
            cursor="hand2"
        )
        btn_add_pwd.pack(side="left", padx=(0, 6))

        btn_add_other = tk.Button(
            action_bar,
            text="📁 Add Other",
            command=self.open_add_other_modal,
            font=("Helvetica", 9),
            bg=self.colors["bg"],
            fg=self.colors["text"],
            relief="flat",
            padx=10,
            pady=6,
            cursor="hand2"
        )
        btn_add_other.pack(side="left", padx=(0, 10))

        btn_gen = tk.Button(
            action_bar,
            text="🎲 Generator",
            command=self.open_generator_modal,
            font=("Helvetica", 9),
            bg=self.colors["bg"],
            fg=self.colors["text"],
            relief="flat",
            padx=10,
            pady=6,
            cursor="hand2"
        )
        btn_gen.pack(side="left", padx=(0, 15))

        # Right Action Buttons
        btn_fav = tk.Button(
            action_bar,
            text="⭐ Favorite",
            command=self.toggle_favorite_selected,
            font=("Helvetica", 9),
            bg=self.colors["bg"],
            fg=self.colors["amber"],
            relief="flat",
            padx=10,
            pady=6,
            cursor="hand2"
        )
        btn_fav.pack(side="right", padx=(6, 0))

        btn_delete = tk.Button(
            action_bar,
            text="🗑️ Delete",
            command=self.delete_selected_item,
            font=("Helvetica", 9),
            bg=self.colors["bg"],
            fg=self.colors["danger"],
            relief="flat",
            padx=10,
            pady=6,
            cursor="hand2"
        )
        btn_delete.pack(side="right", padx=(6, 0))

        btn_extract = tk.Button(
            action_bar,
            text="⬇️ Extract / Save",
            command=self.extract_selected_item,
            font=("Helvetica", 9),
            bg=self.colors["bg"],
            fg=self.colors["text"],
            relief="flat",
            padx=10,
            pady=6,
            cursor="hand2"
        )
        btn_extract.pack(side="right")

        self.refresh_items()

    def set_category_filter(self, category: str):
        self.current_category = category
        for cat, btn in self.cat_buttons.items():
            if cat == category:
                btn.config(bg=self.colors["primary_dark"], fg="#ffffff")
            else:
                btn.config(bg=self.colors["card"], fg=self.colors["muted"])
        self.refresh_items()

    def refresh_items(self):
        if not self.session.is_unlocked():
            self.show_auth_screen()
            return

        for row in self.tree.get_children():
            self.tree.delete(row)

        items = self.session.vault_data.get("items", {})
        query = self.entry_search.get().lower().strip() if hasattr(self, 'entry_search') else ""

        total_bytes = 0

        for item_id, item in items.items():
            size = item.get("size", 0)
            total_bytes += size

            # Category filter
            cat = item.get("category", "Documents")
            is_fav = item.get("favorite", False)
            if self.current_category == "Favorites" and not is_fav:
                continue
            elif self.current_category not in ["All", "Favorites"] and cat != self.current_category:
                continue

            # Search filter
            name = item.get("name", "")
            notes = item.get("notes", "")
            if query and query not in name.lower() and query not in notes.lower() and query not in cat.lower():
                continue

            fav_str = "⭐" if is_fav else ""
            item_type = item.get("type", "file").upper()
            size_str = self.format_size(size)
            date_str = item.get("created_at", "")[:10]

            self.tree.insert("", "end", iid=item_id, values=(fav_str, name, item_type, cat, size_str, date_str))

        if hasattr(self, 'lbl_stats'):
            self.lbl_stats.config(text=f"📦 {len(items)} Items  |  💾 {self.format_size(total_bytes)}")

    def format_size(self, size_bytes: int) -> str:
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.2f} MB"

    def get_selected_item_id(self) -> Optional[str]:
        selected = self.tree.selection()
        return selected[0] if selected else None

    # --- MODALS & ADD OPTIONS ---

    def open_add_files_modal(self):
        """Improved File Selector & Encryptor Modal UI."""
        modal = tk.Toplevel(self)
        modal.title("📥 Encrypt & Store File(s)")
        modal.geometry("520x460")
        modal.configure(bg=self.colors["bg"])
        self.make_modal(modal)

        lbl_hdr = tk.Label(modal, text="📥 Encrypt & Store Files into Vault", font=("Helvetica", 12, "bold"), fg=self.colors["primary"], bg=self.colors["bg"])
        lbl_hdr.pack(anchor="w", padx=20, pady=(15, 2))

        lbl_sub = tk.Label(modal, text="Select files to encrypt. Files are stored 100% offline inside your vault container.", font=("Helvetica", 9), fg=self.colors["muted"], bg=self.colors["bg"])
        lbl_sub.pack(anchor="w", padx=20, pady=(0, 10))

        selected_files: List[str] = []

        # Files List Display Frame
        list_frame = tk.Frame(modal, bg=self.colors["card"], padx=10, pady=10)
        list_frame.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        file_listbox = tk.Listbox(list_frame, font=("Helvetica", 9), bg=self.colors["card"], fg=self.colors["text"], selectbackground=self.colors["primary_dark"], bd=0)
        file_listbox.pack(side="left", fill="both", expand=True)

        sb = ttk.Scrollbar(list_frame, orient="vertical", command=file_listbox.yview)
        file_listbox.config(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")

        btn_bar = tk.Frame(modal, bg=self.colors["bg"])
        btn_bar.pack(fill="x", padx=20, pady=(0, 10))

        def browse_files():
            fps = filedialog.askopenfilenames(title="Select File(s) to Encrypt", parent=modal)
            for fp in fps:
                if fp not in selected_files:
                    selected_files.append(fp)
                    size = os.path.getsize(fp)
                    file_listbox.insert(tk.END, f"📄 {os.path.basename(fp)} ({self.format_size(size)})")

        def remove_selected_file():
            sel = file_listbox.curselection()
            if sel:
                idx = sel[0]
                selected_files.pop(idx)
                file_listbox.delete(idx)

        btn_browse = tk.Button(btn_bar, text="📁 Browse File(s)...", command=browse_files, font=("Helvetica", 9, "bold"), bg=self.colors["card"], fg=self.colors["text"], relief="flat", padx=10, pady=4, cursor="hand2")
        btn_browse.pack(side="left")

        btn_rem = tk.Button(btn_bar, text="❌ Remove Selected", command=remove_selected_file, font=("Helvetica", 9), bg=self.colors["bg"], fg=self.colors["danger"], relief="flat", padx=10, pady=4, cursor="hand2")
        btn_rem.pack(side="left", padx=10)

        # Options Frame
        opt_frame = tk.Frame(modal, bg=self.colors["bg"])
        opt_frame.pack(fill="x", padx=20, pady=(0, 15))

        lbl_cat = tk.Label(opt_frame, text="Category:", font=("Helvetica", 10, "bold"), fg=self.colors["text"], bg=self.colors["bg"])
        lbl_cat.grid(row=0, column=0, sticky="w", pady=(0, 5))

        c_cat = ttk.Combobox(opt_frame, values=["Documents", "Work", "Personal", "Finance", "Media", "Archives", "Other"], state="readonly")
        c_cat.set("Documents")
        c_cat.grid(row=0, column=1, sticky="ew", padx=(10, 0), pady=(0, 5))

        lbl_notes = tk.Label(opt_frame, text="Notes (Optional):", font=("Helvetica", 10, "bold"), fg=self.colors["text"], bg=self.colors["bg"])
        lbl_notes.grid(row=1, column=0, sticky="w", pady=(5, 0))

        e_notes = tk.Entry(opt_frame, font=("Helvetica", 10), bg=self.colors["card"], fg=self.colors["text"], insertbackground=self.colors["primary"], bd=2)
        e_notes.grid(row=1, column=1, sticky="ew", padx=(10, 0), pady=(5, 0))

        opt_frame.columnconfigure(1, weight=1)

        def encrypt_and_save():
            if not selected_files:
                messagebox.showwarning("Warning", "Please select at least one file to encrypt.", parent=modal)
                return

            cat = c_cat.get()
            notes = e_notes.get().strip()
            added_count = 0

            for fp in selected_files:
                try:
                    VaultCore.add_file_item(self.session.vault_data, fp, category=cat, notes=notes)
                    added_count += 1
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to encrypt file {os.path.basename(fp)}: {e}", parent=modal)

            if added_count > 0:
                self.session.save()
                self.refresh_items()
                modal.destroy()
                messagebox.showinfo("Success", f"Successfully encrypted and saved {added_count} file(s) into vault.")

        btn_submit = tk.Button(modal, text="🔒 Encrypt & Save All Files", command=encrypt_and_save, font=("Helvetica", 10, "bold"), bg=self.colors["primary"], fg=self.colors["bg"], activebackground=self.colors["primary_dark"], relief="flat", pady=8, cursor="hand2")
        btn_submit.pack(fill="x", padx=20, pady=(0, 15))

    def open_add_note_modal(self):
        """Add Secret Note Modal Dialog."""
        modal = tk.Toplevel(self)
        modal.title("✍️ Add Secret Note")
        modal.geometry("460x380")
        modal.configure(bg=self.colors["bg"])
        self.make_modal(modal)

        lbl_t = tk.Label(modal, text="Title / Name:", font=("Helvetica", 10, "bold"), fg=self.colors["text"], bg=self.colors["bg"])
        lbl_t.pack(anchor="w", padx=20, pady=(15, 4))

        e_title = tk.Entry(modal, font=("Helvetica", 10), bg=self.colors["card"], fg=self.colors["text"], insertbackground=self.colors["primary"], bd=2)
        e_title.pack(fill="x", padx=20)

        lbl_c = tk.Label(modal, text="Category:", font=("Helvetica", 10, "bold"), fg=self.colors["text"], bg=self.colors["bg"])
        lbl_c.pack(anchor="w", padx=20, pady=(10, 4))

        c_cat = ttk.Combobox(modal, values=["Notes", "Personal", "Work", "Finance", "Other"], state="readonly")
        c_cat.set("Notes")
        c_cat.pack(fill="x", padx=20)

        lbl_n = tk.Label(modal, text="Secret Note Content:", font=("Helvetica", 10, "bold"), fg=self.colors["text"], bg=self.colors["bg"])
        lbl_n.pack(anchor="w", padx=20, pady=(10, 4))

        t_content = tk.Text(modal, height=8, font=("Helvetica", 10), bg=self.colors["card"], fg=self.colors["text"], insertbackground=self.colors["primary"], bd=2)
        t_content.pack(fill="both", expand=True, padx=20, pady=(0, 15))

        def save_note():
            title = e_title.get().strip()
            content = t_content.get("1.0", tk.END).strip()
            cat = c_cat.get()
            if not title or not content:
                messagebox.showwarning("Warning", "Title and content cannot be empty.", parent=modal)
                return

            VaultCore.add_note_item(self.session.vault_data, title, content, category=cat)
            self.session.save()
            self.refresh_items()
            modal.destroy()
            messagebox.showinfo("Success", "Secret note encrypted and saved successfully.")

        btn_save = tk.Button(modal, text="🔒 Encrypt & Save Note", command=save_note, font=("Helvetica", 10, "bold"), bg=self.colors["primary"], fg=self.colors["bg"], activebackground=self.colors["primary_dark"], relief="flat", pady=7, cursor="hand2")
        btn_save.pack(fill="x", padx=20, pady=(0, 15))

    def open_add_password_modal(self):
        """Add Password / Credential Item Modal Dialog."""
        modal = tk.Toplevel(self)
        modal.title("🔑 Add Password / Credential")
        modal.geometry("480x440")
        modal.configure(bg=self.colors["bg"])
        self.make_modal(modal)

        lbl_h = tk.Label(modal, text="🔑 Add Encrypted Password", font=("Helvetica", 12, "bold"), fg=self.colors["primary"], bg=self.colors["bg"])
        lbl_h.pack(anchor="w", padx=20, pady=(15, 10))

        # Title / Service
        lbl_t = tk.Label(modal, text="Service / Account Name (e.g. Google, GitHub):", font=("Helvetica", 9, "bold"), fg=self.colors["text"], bg=self.colors["bg"])
        lbl_t.pack(anchor="w", padx=20, pady=(5, 2))
        e_title = tk.Entry(modal, font=("Helvetica", 10), bg=self.colors["card"], fg=self.colors["text"], insertbackground=self.colors["primary"], bd=2)
        e_title.pack(fill="x", padx=20, pady=(0, 8))

        # Username / Email
        lbl_u = tk.Label(modal, text="Username / Email:", font=("Helvetica", 9, "bold"), fg=self.colors["text"], bg=self.colors["bg"])
        lbl_u.pack(anchor="w", padx=20, pady=(0, 2))
        e_user = tk.Entry(modal, font=("Helvetica", 10), bg=self.colors["card"], fg=self.colors["text"], insertbackground=self.colors["primary"], bd=2)
        e_user.pack(fill="x", padx=20, pady=(0, 8))

        # Password Frame with Generate button
        lbl_p = tk.Label(modal, text="Password:", font=("Helvetica", 9, "bold"), fg=self.colors["text"], bg=self.colors["bg"])
        lbl_p.pack(anchor="w", padx=20, pady=(0, 2))

        p_frame = tk.Frame(modal, bg=self.colors["bg"])
        p_frame.pack(fill="x", padx=20, pady=(0, 8))

        e_pwd = tk.Entry(p_frame, font=("Helvetica", 10), bg=self.colors["card"], fg=self.colors["text"], insertbackground=self.colors["primary"], bd=2)
        e_pwd.pack(side="left", fill="x", expand=True)

        def quick_gen():
            chars = string.ascii_letters + string.digits + "!@#$%^&*"
            pwd = "".join(random.choice(chars) for _ in range(20))
            e_pwd.delete(0, tk.END)
            e_pwd.insert(0, pwd)

        btn_gen = tk.Button(p_frame, text="🎲 Generate", command=quick_gen, font=("Helvetica", 9), bg=self.colors["card"], fg=self.colors["primary"], relief="flat", padx=8, pady=2, cursor="hand2")
        btn_gen.pack(side="right", padx=(5, 0))

        # URL / Website
        lbl_url = tk.Label(modal, text="Website URL (Optional):", font=("Helvetica", 9, "bold"), fg=self.colors["text"], bg=self.colors["bg"])
        lbl_url.pack(anchor="w", padx=20, pady=(0, 2))
        e_url = tk.Entry(modal, font=("Helvetica", 10), bg=self.colors["card"], fg=self.colors["text"], insertbackground=self.colors["primary"], bd=2)
        e_url.pack(fill="x", padx=20, pady=(0, 8))

        # Notes
        lbl_n = tk.Label(modal, text="Notes / Security Answers (Optional):", font=("Helvetica", 9, "bold"), fg=self.colors["text"], bg=self.colors["bg"])
        lbl_n.pack(anchor="w", padx=20, pady=(0, 2))
        e_notes = tk.Entry(modal, font=("Helvetica", 10), bg=self.colors["card"], fg=self.colors["text"], insertbackground=self.colors["primary"], bd=2)
        e_notes.pack(fill="x", padx=20, pady=(0, 15))

        def save_password_credential():
            title = e_title.get().strip()
            user = e_user.get().strip()
            pwd = e_pwd.get().strip()
            url = e_url.get().strip()
            notes = e_notes.get().strip()

            if not title or not pwd:
                messagebox.showwarning("Warning", "Title and password are required.", parent=modal)
                return

            content = f"Username: {user}\nPassword: {pwd}"
            if url:
                content += f"\nURL: {url}"
            if notes:
                content += f"\nNotes: {notes}"

            VaultCore.add_note_item(self.session.vault_data, title, content, category="Passwords")
            self.session.save()
            self.refresh_items()
            modal.destroy()
            messagebox.showinfo("Success", "Password credential encrypted and saved successfully.")

        btn_save = tk.Button(modal, text="🔒 Save Encrypted Password", command=save_password_credential, font=("Helvetica", 10, "bold"), bg=self.colors["primary"], fg=self.colors["bg"], activebackground=self.colors["primary_dark"], relief="flat", pady=7, cursor="hand2")
        btn_save.pack(fill="x", padx=20, pady=(0, 15))

    def open_add_other_modal(self):
        """Add Other Custom Secure Item Modal Dialog."""
        modal = tk.Toplevel(self)
        modal.title("📁 Add Other Secure Item")
        modal.geometry("460x400")
        modal.configure(bg=self.colors["bg"])
        self.make_modal(modal)

        lbl_h = tk.Label(modal, text="📁 Add Custom Secure Item", font=("Helvetica", 12, "bold"), fg=self.colors["primary"], bg=self.colors["bg"])
        lbl_h.pack(anchor="w", padx=20, pady=(15, 10))

        lbl_t = tk.Label(modal, text="Item Title / Name (e.g. Credit Card, API Key, License):", font=("Helvetica", 9, "bold"), fg=self.colors["text"], bg=self.colors["bg"])
        lbl_t.pack(anchor="w", padx=20, pady=(0, 2))
        e_title = tk.Entry(modal, font=("Helvetica", 10), bg=self.colors["card"], fg=self.colors["text"], insertbackground=self.colors["primary"], bd=2)
        e_title.pack(fill="x", padx=20, pady=(0, 8))

        lbl_c = tk.Label(modal, text="Category:", font=("Helvetica", 9, "bold"), fg=self.colors["text"], bg=self.colors["bg"])
        lbl_c.pack(anchor="w", padx=20, pady=(0, 2))
        c_cat = ttk.Combobox(modal, values=["Personal", "Finance", "Documents", "Notes", "Other"], state="readonly")
        c_cat.set("Personal")
        c_cat.pack(fill="x", padx=20, pady=(0, 8))

        lbl_det = tk.Label(modal, text="Item Secret Details / Data:", font=("Helvetica", 9, "bold"), fg=self.colors["text"], bg=self.colors["bg"])
        lbl_det.pack(anchor="w", padx=20, pady=(0, 2))
        t_det = tk.Text(modal, height=8, font=("Helvetica", 10), bg=self.colors["card"], fg=self.colors["text"], insertbackground=self.colors["primary"], bd=2)
        t_det.pack(fill="both", expand=True, padx=20, pady=(0, 15))

        def save_other():
            title = e_title.get().strip()
            content = t_det.get("1.0", tk.END).strip()
            cat = c_cat.get()

            if not title or not content:
                messagebox.showwarning("Warning", "Title and details cannot be empty.", parent=modal)
                return

            VaultCore.add_note_item(self.session.vault_data, title, content, category=cat)
            self.session.save()
            self.refresh_items()
            modal.destroy()
            messagebox.showinfo("Success", "Custom item encrypted and saved successfully.")

        btn_save = tk.Button(modal, text="🔒 Save Encrypted Item", command=save_other, font=("Helvetica", 10, "bold"), bg=self.colors["primary"], fg=self.colors["bg"], activebackground=self.colors["primary_dark"], relief="flat", pady=7, cursor="hand2")
        btn_save.pack(fill="x", padx=20, pady=(0, 15))

    def open_selected_item(self):
        item_id = self.get_selected_item_id()
        if not item_id:
            return

        item = self.session.vault_data.get("items", {}).get(item_id)
        if not item:
            return

        modal = tk.Toplevel(self)
        modal.title(f"View Item - {item.get('name')}")
        modal.geometry("520x420")
        modal.configure(bg=self.colors["bg"])
        self.make_modal(modal)

        lbl_t = tk.Label(modal, text=item.get("name"), font=("Helvetica", 12, "bold"), fg=self.colors["primary"], bg=self.colors["bg"])
        lbl_t.pack(anchor="w", padx=20, pady=(15, 2))

        meta_str = f"Type: {item.get('type').upper()}  |  Category: {item.get('category')}  |  Size: {self.format_size(item.get('size', 0))}"
        lbl_meta = tk.Label(modal, text=meta_str, font=("Helvetica", 9), fg=self.colors["muted"], bg=self.colors["bg"])
        lbl_meta.pack(anchor="w", padx=20, pady=(0, 10))

        content_box = tk.Text(modal, font=("Courier", 10), bg=self.colors["card"], fg=self.colors["text"], bd=2)
        content_box.pack(fill="both", expand=True, padx=20, pady=(0, 15))

        if item.get("type") == "note":
            content_box.insert("1.0", item.get("content", ""))
        else:
            content_box.insert("1.0", f"[Encrypted File Payload]\nFilename: {item.get('filename')}\nNotes: {item.get('notes', 'N/A')}")
            content_box.config(state="disabled")

        btn_frame = tk.Frame(modal, bg=self.colors["bg"])
        btn_frame.pack(fill="x", padx=20, pady=(0, 15))

        def copy_to_clipboard():
            text = item.get("content", "") if item.get("type") == "note" else item.get("filename")
            self.clipboard_clear()
            self.clipboard_append(text)
            messagebox.showinfo("Copied", "Content copied to clipboard!", parent=modal)

        btn_copy = tk.Button(btn_frame, text="📋 Copy Content", command=copy_to_clipboard, bg=self.colors["card"], fg=self.colors["text"], relief="flat", padx=12, pady=4, cursor="hand2")
        btn_copy.pack(side="left")

        if item.get("type") == "file":
            btn_dl = tk.Button(btn_frame, text="⬇️ Save Decrypted File", command=lambda: self.extract_item_by_id(item_id), bg=self.colors["primary"], fg=self.colors["bg"], relief="flat", padx=12, pady=4, cursor="hand2")
            btn_dl.pack(side="right")

    def toggle_favorite_selected(self):
        item_id = self.get_selected_item_id()
        if not item_id:
            messagebox.showwarning("Select Item", "Please select an item from the list first.")
            return

        VaultCore.toggle_favorite(self.session.vault_data, item_id)
        self.session.save()
        self.refresh_items()

    def delete_selected_item(self):
        item_id = self.get_selected_item_id()
        if not item_id:
            messagebox.showwarning("Select Item", "Please select an item to delete.")
            return

        item = self.session.vault_data.get("items", {}).get(item_id, {})
        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete '{item.get('name')}' permanently?"):
            VaultCore.delete_item(self.session.vault_data, item_id)
            self.session.save()
            self.refresh_items()

    def extract_selected_item(self):
        item_id = self.get_selected_item_id()
        if not item_id:
            messagebox.showwarning("Select Item", "Please select an item to extract.")
            return
        self.extract_item_by_id(item_id)

    def extract_item_by_id(self, item_id: str):
        item = self.session.vault_data.get("items", {}).get(item_id)
        if not item:
            return

        default_name = item.get("filename", f"{item.get('name')}.txt")
        out_path = filedialog.asksaveasfilename(title="Save Decrypted File As", initialfile=default_name)
        if not out_path:
            return

        try:
            if item.get("type") == "note":
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(item.get("content", ""))
            else:
                raw_bytes = base64.b64decode(item.get("data_b64", item.get("data", "")))
                with open(out_path, "wb") as f:
                    f.write(raw_bytes)
            messagebox.showinfo("Success", f"Decrypted item saved to:\n{out_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save file: {e}")

    def open_generator_modal(self):
        modal = tk.Toplevel(self)
        modal.title("Password & Key Generator")
        modal.geometry("420x340")
        modal.configure(bg=self.colors["bg"])
        self.make_modal(modal)

        lbl_out = tk.Label(modal, text="Generated Password:", font=("Helvetica", 10, "bold"), fg=self.colors["text"], bg=self.colors["bg"])
        lbl_out.pack(anchor="w", padx=20, pady=(15, 4))

        e_res = tk.Entry(modal, font=("Courier", 12, "bold"), bg=self.colors["card"], fg=self.colors["primary"], bd=2)
        e_res.pack(fill="x", padx=20)

        lbl_entropy = tk.Label(modal, text="Entropy: 128 bits (Very Strong)", font=("Helvetica", 9), fg=self.colors["emerald"], bg=self.colors["bg"])
        lbl_entropy.pack(anchor="w", padx=20, pady=(4, 10))

        scale_len = tk.Scale(modal, from_=8, to=64, orient="horizontal", label="Password Length", bg=self.colors["bg"], fg=self.colors["text"], highlightthickness=0)
        scale_len.set(20)
        scale_len.pack(fill="x", padx=20, pady=5)

        def generate():
            chars = string.ascii_letters + string.digits + "!@#$%^&*()"
            pwd_len = scale_len.get()
            pwd = "".join(random.choice(chars) for _ in range(pwd_len))
            e_res.delete(0, tk.END)
            e_res.insert(0, pwd)

            entropy = pwd_len * math.log2(len(chars))
            lbl_entropy.config(text=f"Entropy: {entropy:.1f} bits (Very Strong)")

        scale_len.config(command=lambda e: generate())
        generate()

        btn_copy = tk.Button(modal, text="📋 Copy Password", command=lambda: (self.clipboard_clear(), self.clipboard_append(e_res.get()), messagebox.showinfo("Copied", "Password copied!")), font=("Helvetica", 10, "bold"), bg=self.colors["primary"], fg=self.colors["bg"], relief="flat", pady=6, cursor="hand2")
        btn_copy.pack(fill="x", padx=20, pady=15)

    def open_settings_modal(self):
        modal = tk.Toplevel(self)
        modal.title("Vault Settings & Backup")
        modal.geometry("450x300")
        modal.configure(bg=self.colors["bg"])
        self.make_modal(modal)

        lbl_h = tk.Label(modal, text="⚙️ Vault Settings", font=("Helvetica", 12, "bold"), fg=self.colors["primary"], bg=self.colors["bg"])
        lbl_h.pack(anchor="w", padx=20, pady=(15, 10))

        def backup_vault():
            out_path = filedialog.asksaveasfilename(title="Backup Vault Container File", initialfile=os.path.basename(self.session.vault_path))
            if out_path:
                import shutil
                shutil.copy(self.session.vault_path, out_path)
                messagebox.showinfo("Backup Success", f"Vault file backed up to:\n{out_path}", parent=modal)

        btn_bk = tk.Button(modal, text="💾 Export Backup Vault Container", command=backup_vault, bg=self.colors["card"], fg=self.colors["text"], relief="flat", padx=12, pady=6, cursor="hand2")
        btn_bk.pack(fill="x", padx=20, pady=10)

    def lock_vault(self):
        self.session.lock()
        self.show_auth_screen()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Locker - Encrypted Storage Vault & Virtual Drive Mount")
    parser.add_argument("vault_file", nargs="?", default=None, help="Path to .locker or .vault file to open")
    parser.add_argument("--vault", default=None, help="Path to .locker or .vault file")
    parser.add_argument("--mount", action="store_true", help="Auto-mount vault into OS File Manager on unlock")

    args = parser.parse_args()
    target_vault = args.vault or args.vault_file or DEFAULT_VAULT_FILE

    # If launched with a target file or --mount flag, auto-mount upon unlocking
    auto_mount = bool(args.vault or args.vault_file or args.mount)

    app = LockerApp(target_vault, auto_mount=auto_mount)
    app.mainloop()


if __name__ == "__main__":
    main()
