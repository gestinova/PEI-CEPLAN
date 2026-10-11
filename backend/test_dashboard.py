import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app import create_app
from models import Generation, User, hash_password


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({"TESTING": True, "DATABASE_URL": "sqlite+pysqlite:///:memory:"})
        self.client = self.app.test_client()
        with self.app.extensions["db_session_factory"]() as database:
            admin = User(username="admin", password_hash=hash_password("admin password secure"), is_admin=True)
            member = User(username="member", password_hash=hash_password("member password secure"))
            database.add_all([admin, member])
            database.flush()
            database.add_all([
                Generation(generation_request_id="11111111-1111-4111-8111-111111111111", user_id=member.id, output_name="PEI_1.docx", municipality="A", completed_at=datetime(2026, 9, 3, tzinfo=timezone.utc)),
                Generation(generation_request_id="22222222-2222-4222-8222-222222222222", user_id=member.id, output_name="PEI_2.docx", municipality="A", completed_at=datetime(2026, 9, 5, tzinfo=timezone.utc)),
                Generation(generation_request_id="33333333-3333-4333-8333-333333333333", user_id=admin.id, output_name="PEI_3.docx", municipality="B", completed_at=datetime(2026, 10, 1, tzinfo=timezone.utc)),
            ])
            database.commit()

    def login(self, username, password):
        self.client.get("/login")
        with self.client.session_transaction() as browser_session:
            token = browser_session["csrf_token"]
        self.client.post("/login", data={"csrf_token": token, "username": username, "password": password})

    def test_admin_sees_total_user_and_month_metrics(self):
        self.login("admin", "admin password secure")
        response = self.client.get("/admin/dashboard")
        text = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Total histórico", text)
        self.assertIn("2026-09", text)
        self.assertIn("2026-10", text)
        self.assertIn("member", text)

    def test_member_cannot_view_dashboard(self):
        self.login("member", "member password secure")
        self.assertEqual(self.client.get("/admin/dashboard").status_code, 403)

    def test_generator_assets_require_authentication(self):
        anonymous = self.app.test_client()
        self.assertEqual(anonymous.get("/generator").status_code, 302)
        self.assertEqual(anonymous.get("/matriz_estandar.json").status_code, 302)


if __name__ == "__main__":
    unittest.main()
