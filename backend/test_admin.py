import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app import create_app
from models import User, hash_password, verify_password


class AdminTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({"TESTING": True, "DATABASE_URL": "sqlite+pysqlite:///:memory:"})
        self.client = self.app.test_client()
        with self.app.extensions["db_session_factory"]() as database:
            database.add_all([
                User(username="admin", password_hash=hash_password("admin password secure"), is_admin=True),
                User(username="member", password_hash=hash_password("member password secure")),
            ])
            database.commit()

    def login(self, username="admin", password="admin password secure"):
        self.client.get("/login")
        with self.client.session_transaction() as browser_session:
            token = browser_session["csrf_token"]
        self.client.post("/login", data={"csrf_token": token, "username": username, "password": password})
        with self.client.session_transaction() as browser_session:
            return browser_session["csrf_token"]

    def test_only_admin_can_list_users(self):
        self.assertEqual(self.client.get("/admin/users").status_code, 302)
        self.login("member", "member password secure")
        self.assertEqual(self.client.get("/admin/users").status_code, 403)

    def test_admin_can_create_disable_and_reset_user(self):
        token = self.login()
        response = self.client.post("/admin/users", data={"csrf_token": token, "username": "new_user", "password": "temporary password"})
        self.assertEqual(response.status_code, 302)
        factory = self.app.extensions["db_session_factory"]
        with factory() as database:
            user = database.query(User).filter_by(username="new_user").one()
            user_id = user.id
        self.assertEqual(self.client.post(f"/admin/users/{user_id}/status", data={"csrf_token": token, "active": "false"}).status_code, 302)
        self.assertEqual(self.client.post(f"/admin/users/{user_id}/password", data={"csrf_token": token, "password": "replacement password"}).status_code, 302)
        with factory() as database:
            user = database.get(User, user_id)
            self.assertFalse(user.is_active)
            self.assertTrue(verify_password("replacement password", user.password_hash))

    def test_admin_cannot_disable_self_and_csrf_is_required(self):
        token = self.login()
        with self.app.extensions["db_session_factory"]() as database:
            admin_id = database.query(User).filter_by(username="admin").one().id
        self.assertEqual(self.client.post(f"/admin/users/{admin_id}/status", data={"csrf_token": token, "active": "false"}).status_code, 400)
        self.assertEqual(self.client.post("/admin/users", data={"username": "other", "password": "temporary password"}).status_code, 400)


if __name__ == "__main__":
    unittest.main()
