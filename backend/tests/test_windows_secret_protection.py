"""Native DPAPI regression checks with synthetic secrets only."""
import os
import unittest
from backend.windows_credentials import protect_secret, unprotect_secret


@unittest.skipUnless(os.name == 'nt', 'Native Windows DPAPI')
class WindowsSecretTests(unittest.TestCase):
    def test_current_user_round_trip_and_ciphertext_randomness(self):
        original = b'synthetic-private-key-and-refresh-token'
        first, second = protect_secret(original), protect_secret(original)
        self.assertNotIn(original, first)
        self.assertNotEqual(first, second)
        self.assertEqual(unprotect_secret(first), original)
        self.assertEqual(unprotect_secret(second), original)

    def test_corrupt_ciphertext_is_rejected(self):
        encrypted = bytearray(protect_secret(b'synthetic-secret'))
        encrypted[-1] ^= 1
        with self.assertRaises(ValueError):
            unprotect_secret(bytes(encrypted))
