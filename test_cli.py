import os
import sys
import unittest
import tempfile
import io
from unittest.mock import patch
from pathlib import Path

from vault_core import VaultCore, DEFAULT_VAULT_FILE
import cli


class TestVaultCLI(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.vault_path = os.path.join(self.temp_dir.name, "cli_test.vault")
        self.master_password = "CLITestPassword123!"

    def tearDown(self):
        self.temp_dir.cleanup()

    def run_cli(self, args, password_inputs=None):
        """Helper to invoke cli.main() with specified sys.argv and password prompts."""
        full_args = ["cli.py", "--vault", self.vault_path] + args
        
        with patch.object(sys, "argv", full_args):
            with patch("getpass.getpass", side_effect=password_inputs or []):
                stdout_capture = io.StringIO()
                stderr_capture = io.StringIO()
                with patch("sys.stdout", stdout_capture), patch("sys.stderr", stderr_capture):
                    try:
                        cli.main()
                        exit_code = 0
                    except SystemExit as e:
                        exit_code = e.code if isinstance(e.code, int) else 1
                return exit_code, stdout_capture.getvalue(), stderr_capture.getvalue()

    def test_cli_init_and_status(self):
        # Initialize vault via CLI
        code, out, err = self.run_cli(["init"], password_inputs=[self.master_password, self.master_password])
        self.assertEqual(code, 0)
        self.assertIn("Initialized new encrypted vault", out)

        # Status check
        code, out, err = self.run_cli(["status"])
        self.assertEqual(code, 0)
        self.assertIn("exists", out)

    def test_cli_add_note_list_and_extract(self):
        # Init
        self.run_cli(["init"], password_inputs=[self.master_password, self.master_password])

        # Add note
        code, out, err = self.run_cli(
            ["add-note", "--title", "Secret Key", "--content", "ssh-rsa AAAAB3NzaC1..."],
            password_inputs=[self.master_password]
        )
        self.assertEqual(code, 0)
        self.assertIn("Stored encrypted note", out)

        # Extract item ID from list output
        code, out, err = self.run_cli(["list"], password_inputs=[self.master_password])
        self.assertEqual(code, 0)
        self.assertIn("Secret Key", out)

        # Parse ID from out
        item_id = None
        for line in out.splitlines():
            if "Secret Key" in line:
                item_id = line.split()[0]
                break
        self.assertIsNotNone(item_id)

        # Extract item
        out_file = os.path.join(self.temp_dir.name, "extracted_key.txt")
        code, out, err = self.run_cli(["extract", "--id", item_id, "--out", out_file], password_inputs=[self.master_password])
        self.assertEqual(code, 0)
        self.assertTrue(os.path.exists(out_file))

        with open(out_file, "r") as f:
            self.assertEqual(f.read(), "ssh-rsa AAAAB3NzaC1...")

    def test_cli_add_file_and_delete(self):
        self.run_cli(["init"], password_inputs=[self.master_password, self.master_password])

        # Create dummy file to add
        sample_path = os.path.join(self.temp_dir.name, "sample.pdf")
        with open(sample_path, "wb") as f:
            f.write(b"%PDF-1.5 Sample content for CLI testing")

        code, out, err = self.run_cli(["add-file", sample_path, "--category", "Documents"], password_inputs=[self.master_password])
        self.assertEqual(code, 0)
        self.assertIn("Encrypted and stored 'sample.pdf'", out)

        # List to get ID
        code, out, err = self.run_cli(["list"], password_inputs=[self.master_password])
        item_id = None
        for line in out.splitlines():
            if "sample.pdf" in line:
                item_id = line.split()[0]
                break
        self.assertIsNotNone(item_id)

        # Delete item
        code, out, err = self.run_cli(["delete", "--id", item_id], password_inputs=[self.master_password])
        self.assertEqual(code, 0)
        self.assertIn("Deleted item", out)

    def test_cli_change_password(self):
        self.run_cli(["init"], password_inputs=[self.master_password, self.master_password])
        new_pass = "NewMasterPass987!"

        code, out, err = self.run_cli(["change-password"], password_inputs=[self.master_password, new_pass, new_pass])
        self.assertEqual(code, 0)
        self.assertIn("Master password updated", out)

        # Old password list should fail
        code, out, err = self.run_cli(["list"], password_inputs=[self.master_password])
        self.assertNotEqual(code, 0)

        # New password list should succeed
        code, out, err = self.run_cli(["list"], password_inputs=[new_pass])
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
