import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))

import app as app_module
from app import create_app
from models import Generation, User, hash_password


class GenerationAccountingTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.output_dir = Path(self.tempdir.name) / "archivos-gen"
        self.output_dir.mkdir()
        self.root_patch = patch.object(app_module, "PROJECT_ROOT", Path(self.tempdir.name))
        self.root_patch.start()

        def generator(data, output_path):
            if data.get("fail"):
                raise RuntimeError("generation failed")
            output_path.write_bytes(b"docx")

        self.app = create_app({
            "TESTING": True,
            "DATABASE_URL": "sqlite+pysqlite:///:memory:",
            "DOCUMENT_GENERATOR": generator,
        })
        self.client = self.app.test_client()
        with self.app.extensions["db_session_factory"]() as database:
            database.add_all([
                User(username="member", password_hash=hash_password("member password secure")),
                User(username="other", password_hash=hash_password("other password secure")),
            ])
            database.commit()
        self.token = self.login("member", "member password secure")

    def tearDown(self):
        self.root_patch.stop()
        self.app.extensions["db_engine"].dispose()
        self.tempdir.cleanup()

    def login(self, username, password):
        self.client.get("/login")
        with self.client.session_transaction() as browser_session:
            token = browser_session["csrf_token"]
        self.client.post("/login", data={"csrf_token": token, "username": username, "password": password})
        with self.client.session_transaction() as browser_session:
            return browser_session["csrf_token"]

    def post_generation(self, request_id, **extra):
        payload = {"generation_request_id": request_id, "nombre_municipio": "Municipalidad"}
        payload.update(extra)
        return self.client.post("/generar", json=payload, headers={"X-CSRF-Token": self.token})

    def test_success_is_counted_once_and_retry_is_idempotent(self):
        request_id = str(uuid.uuid4())
        first = self.post_generation(request_id)
        second = self.post_generation(request_id)
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertTrue(second.get_json()["idempotent"])
        with self.app.extensions["db_session_factory"]() as database:
            rows = database.query(Generation).all()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].output_name, f"PEI_{request_id}.docx")

    def test_failure_is_not_billed_or_left_on_disk(self):
        request_id = str(uuid.uuid4())
        with self.assertRaises(RuntimeError):
            self.post_generation(request_id, fail=True)
        with self.app.extensions["db_session_factory"]() as database:
            self.assertEqual(database.query(Generation).count(), 0)
        self.assertEqual(list(self.output_dir.iterdir()), [])

    def test_generation_and_download_require_owner_authentication(self):
        anonymous = self.app.test_client()
        self.assertEqual(anonymous.post("/generar", json={}).status_code, 302)
        response = self.post_generation(str(uuid.uuid4()))
        download_url = response.get_json()["download_url"]
        self.assertEqual(self.client.get(download_url).status_code, 200)
        self.token = self.login("other", "other password secure")
        self.assertEqual(self.client.get(download_url).status_code, 404)

    def test_distinct_requests_have_distinct_outputs(self):
        first = self.post_generation(str(uuid.uuid4())).get_json()["download_url"]
        second = self.post_generation(str(uuid.uuid4())).get_json()["download_url"]
        self.assertNotEqual(first, second)


if __name__ == "__main__":
    unittest.main()
