import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app import create_app
from models import Base, User, hash_password, verify_password


class AuthTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({"TESTING": True, "DATABASE_URL": "sqlite+pysqlite:///:memory:"})
        self.client = self.app.test_client()
        factory = self.app.extensions["db_session_factory"]
        with factory() as database:
            database.add(User(username="admin", password_hash=hash_password("correct horse battery"), is_admin=True))
            database.commit()

    def csrf(self):
        self.client.get("/login")
        with self.client.session_transaction() as browser_session:
            return browser_session["csrf_token"]

    def test_passwords_use_argon2_and_verify(self):
        encoded = hash_password("correct horse battery")
        self.assertTrue(encoded.startswith("argon2id$"))
        self.assertTrue(verify_password("correct horse battery", encoded))
        self.assertFalse(verify_password("wrong password", encoded))

    def test_login_requires_csrf_and_valid_credentials(self):
        self.assertEqual(self.client.post("/login", data={}).status_code, 400)
        response = self.client.post("/login", data={"csrf_token": self.csrf(), "username": "admin", "password": "correct horse battery"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.get("/").status_code, 200)

    def test_disabled_user_cannot_continue_session(self):
        token = self.csrf()
        self.client.post("/login", data={"csrf_token": token, "username": "admin", "password": "correct horse battery"})
        factory = self.app.extensions["db_session_factory"]
        with factory() as database:
            user = database.query(User).filter_by(username="admin").one()
            user.is_active = False
            database.commit()
        self.assertEqual(self.client.get("/").status_code, 302)

    def test_production_configuration_requires_database_and_secret(self):
        with self.assertRaises(RuntimeError):
            create_app({})


if __name__ == "__main__":
    unittest.main()
