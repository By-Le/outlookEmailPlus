import unittest
import uuid

from tests._import_app import clear_login_attempts, import_web_app_module


class ExternalPoolApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = import_web_app_module()
        cls.app = cls.module.app

    def setUp(self):
        with self.app.app_context():
            clear_login_attempts()
            from outlook_web.db import get_db
            from outlook_web.repositories import settings as settings_repo

            db = get_db()
            db.execute("DELETE FROM audit_logs WHERE resource_type = 'external_api'")
            db.execute("DELETE FROM external_api_keys")
            db.execute("DELETE FROM external_api_consumer_usage_daily")
            db.execute(
                "DELETE FROM account_claim_logs WHERE account_id IN (SELECT id FROM accounts WHERE email LIKE '%@extpool.test')"
            )
            db.execute("DELETE FROM accounts WHERE email LIKE '%@extpool.test'")
            db.commit()
            settings_repo.set_setting("external_api_key", "")
            settings_repo.set_setting("external_api_public_mode", "0")
            settings_repo.set_setting("pool_external_enabled", "false")

    @staticmethod
    def _auth_headers(value: str = "abc123"):
        return {"X-API-Key": value}

    def _set_external_api_key(self, value: str):
        with self.app.app_context():
            from outlook_web.repositories import settings as settings_repo

            settings_repo.set_setting("external_api_key", value)

    def _insert_pool_account(
        self, *, provider: str = "outlook", pool_status: str = "available"
    ) -> int:
        email_addr = f"{uuid.uuid4().hex}@extpool.test"
        with self.app.app_context():
            from outlook_web.db import get_db

            db = get_db()
            db.execute(
                """
                INSERT INTO accounts (
                    email, password, client_id, refresh_token,
                    group_id, status, account_type, provider, pool_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    email_addr,
                    "pw",
                    "cid-test",
                    "rt-test",
                    1,
                    "active",
                    "outlook",
                    provider,
                    pool_status,
                ),
            )
            db.commit()
            row = db.execute(
                "SELECT id FROM accounts WHERE email = ?", (email_addr,)
            ).fetchone()
            return int(row["id"])

    def test_external_pool_stats_requires_api_key(self):
        client = self.app.test_client()
        self._set_external_api_key("abc123")

        resp = client.get("/api/external/pool/stats")

        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.get_json().get("code"), "UNAUTHORIZED")

    def test_external_pool_claim_random_success(self):
        client = self.app.test_client()
        self._set_external_api_key("abc123")
        with self.app.app_context():
            from outlook_web.repositories import settings as settings_repo

            settings_repo.set_setting("pool_external_enabled", "true")
        self._insert_pool_account(provider="outlook")

        resp = client.post(
            "/api/external/pool/claim-random",
            headers=self._auth_headers(),
            json={
                "caller_id": "ext-worker-01",
                "task_id": "task-ext-001",
                "provider": "outlook",
            },
        )

        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("code"), "OK")
        payload = data.get("data", {})
        self.assertIn("account_id", payload)
        self.assertIn("claim_token", payload)
        self.assertIn("lease_expires_at", payload)

    def test_external_pool_claim_release_caller_mismatch(self):
        client = self.app.test_client()
        self._set_external_api_key("abc123")
        with self.app.app_context():
            from outlook_web.repositories import settings as settings_repo

            settings_repo.set_setting("pool_external_enabled", "true")
        self._insert_pool_account(provider="outlook")

        claim_resp = client.post(
            "/api/external/pool/claim-random",
            headers=self._auth_headers(),
            json={
                "caller_id": "ext-worker-01",
                "task_id": "task-ext-002",
                "provider": "outlook",
            },
        )
        self.assertEqual(claim_resp.status_code, 200)
        claim_data = claim_resp.get_json()["data"]

        release_resp = client.post(
            "/api/external/pool/claim-release",
            headers=self._auth_headers(),
            json={
                "account_id": claim_data["account_id"],
                "claim_token": claim_data["claim_token"],
                "caller_id": "ext-worker-02",
                "task_id": "task-ext-002",
            },
        )

        self.assertEqual(release_resp.status_code, 403)
        data = release_resp.get_json()
        self.assertFalse(data.get("success"))
        self.assertEqual(data.get("code"), "CALLER_MISMATCH")

    def test_external_pool_stats_success(self):
        client = self.app.test_client()
        self._set_external_api_key("abc123")
        with self.app.app_context():
            from outlook_web.repositories import settings as settings_repo

            settings_repo.set_setting("pool_external_enabled", "true")
        self._insert_pool_account(pool_status="available")
        self._insert_pool_account(pool_status="used")

        resp = client.get("/api/external/pool/stats", headers=self._auth_headers())

        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("code"), "OK")
        self.assertIn("pool_counts", data.get("data", {}))

    def test_external_pool_stats_returns_feature_disabled_when_switch_off(self):
        client = self.app.test_client()
        self._set_external_api_key("abc123")

        resp = client.get("/api/external/pool/stats", headers=self._auth_headers())

        self.assertEqual(resp.status_code, 403)
        data = resp.get_json()
        self.assertFalse(data.get("success"))
        self.assertEqual(data.get("code"), "FEATURE_DISABLED")
