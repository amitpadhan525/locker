import os
import unittest
import tempfile
from pathlib import Path
from vault_core import VaultCore, VaultSecurityError, KDF_ARGON2ID, KDF_PBKDF2


class TestVaultCore(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.vault_path = os.path.join(self.temp_dir.name, "test_vault.vault")
        self.master_password = "SuperSecretPassword123!"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_create_and_unlock_vault(self):
        master_key, salt, kdf_type, vault_data = VaultCore.create_vault(self.vault_path, self.master_password)
        self.assertTrue(os.path.exists(self.vault_path))
        self.assertIn("vault_id", vault_data)

        # Unlock with correct password
        unlocked_key, salt, kdf_type, unlocked_data = VaultCore.unlock_vault(self.vault_path, self.master_password)
        self.assertEqual(master_key, unlocked_key)
        self.assertEqual(vault_data["vault_id"], unlocked_data["vault_id"])

    def test_unlock_wrong_password_fails(self):
        VaultCore.create_vault(self.vault_path, self.master_password)
        with self.assertRaises(VaultSecurityError):
            VaultCore.unlock_vault(self.vault_path, "WrongPassword123!")

    def test_add_and_extract_file(self):
        master_key, salt, kdf_type, vault_data = VaultCore.create_vault(self.vault_path, self.master_password)
        
        sample_filename = "document.pdf"
        sample_bytes = b"PDF-1.4 Mock confidential document content line 123"
        
        item_id = VaultCore.add_file_item(vault_data, sample_filename, sample_bytes, category="Work", notes="Confidential PDF")
        self.assertIn(item_id, vault_data["items"])

        # Save changes with original salt and kdf_type
        VaultCore.save_vault(self.vault_path, master_key, salt, kdf_type, vault_data)

        # Re-open vault and extract file
        _, _, _, loaded_data = VaultCore.unlock_vault(self.vault_path, self.master_password)
        extracted_item = loaded_data["items"][item_id]
        fname, extracted_bytes = VaultCore.extract_item_data(extracted_item)

        self.assertEqual(fname, sample_filename)
        self.assertEqual(extracted_bytes, sample_bytes)

    def test_add_and_extract_note(self):
        master_key, salt, kdf_type, vault_data = VaultCore.create_vault(self.vault_path, self.master_password)

        note_title = "Bank PINs"
        note_content = "Checking Account PIN: 9876\nSavings Account PIN: 5432"

        item_id = VaultCore.add_note_item(vault_data, note_title, note_content, category="Finance")
        VaultCore.save_vault(self.vault_path, master_key, salt, kdf_type, vault_data)

        _, _, _, loaded_data = VaultCore.unlock_vault(self.vault_path, self.master_password)
        note_item = loaded_data["items"][item_id]
        _, raw_bytes = VaultCore.extract_item_data(note_item)

        self.assertEqual(raw_bytes.decode('utf-8'), note_content)

    def test_tamper_detection(self):
        master_key, salt, kdf_type, vault_data = VaultCore.create_vault(self.vault_path, self.master_password)
        VaultCore.add_note_item(vault_data, "Test", "Content")
        
        # Modify 1 byte in vault file payload to simulate tampering
        with open(self.vault_path, "rb") as f:
            data = bytearray(f.read())
        
        data[-5] ^= 0xFF  # Flip bits in ciphertext
        with open(self.vault_path, "wb") as f:
            f.write(data)

        with self.assertRaises(VaultSecurityError):
            VaultCore.unlock_vault(self.vault_path, self.master_password)

    def test_change_password(self):
        VaultCore.create_vault(self.vault_path, self.master_password)
        new_password = "BrandNewMasterPassword456!"

        VaultCore.change_password(self.vault_path, self.master_password, new_password)

        # Old password must fail
        with self.assertRaises(VaultSecurityError):
            VaultCore.unlock_vault(self.vault_path, self.master_password)

        # New password must succeed
        _, _, _, data = VaultCore.unlock_vault(self.vault_path, new_password)
        self.assertIn("items", data)


if __name__ == "__main__":
    unittest.main()
