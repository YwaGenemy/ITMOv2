"""Тесты на найденные уязвимости. На исходном сервисе они падают, после исправлений проходят."""

import unittest

from service import Shop


class SecurityTest(unittest.TestCase):
    def setUp(self):
        self.shop = Shop()
        self.addCleanup(self.shop.close)

    def request(self, method, path, body=None, headers=None):
        with self.shop.lock:
            return self.shop.dispatch(method, path, body or {}, headers or {})

    def login(self, username="alice", password="learn-alice"):
        status, result = self.request("POST", "/login", {"username": username, "password": password})
        self.assertEqual(status, 200)
        return {"X-Token": result["token"]}

    def test_sql_injection_in_profile_does_not_dump_table(self):
        auth = self.login()
        status, result = self.request("GET", "/profile?id=1 OR 1=1", headers=auth)
        # Инъекция не должна вернуть все профили; при строгой проверке типа это просто отказ.
        self.assertNotEqual(status, 200)

    def test_sql_injection_in_search_returns_no_rows(self):
        auth = self.login("staff", "learn-staff")
        status, rows = self.request("GET", "/search?q=%' OR '1'='1", headers=auth)
        self.assertEqual(status, 200)
        self.assertEqual(rows, [])

    def test_customer_cannot_read_other_profile(self):
        auth = self.login()
        status, _ = self.request("GET", "/profile?id=2", headers=auth)
        self.assertEqual(status, 403)

    def test_customer_cannot_read_other_user_file(self):
        auth = self.login()
        status, _ = self.request("GET", "/files?user=bob&path=receipt.txt", headers=auth)
        self.assertEqual(status, 403)

    def test_spoofed_role_header_cannot_export(self):
        auth = {**self.login(), "X-Role": "staff"}
        status, _ = self.request("GET", "/admin/export", headers=auth)
        self.assertEqual(status, 403)

    def test_client_cannot_set_own_price(self):
        auth = self.login()
        status, order = self.request("POST", "/orders", {"product": "chair", "price": 1}, auth)
        self.assertEqual(status, 201)
        self.assertEqual(order["price"], 5000)

    def test_debug_logs_need_staff_and_hide_secrets(self):
        auth = self.login()
        self.assertEqual(self.request("GET", "/debug/logs", headers=auth)[0], 403)
        staff = self.login("staff", "learn-staff")
        status, logs = self.request("GET", "/debug/logs", headers=staff)
        self.assertEqual(status, 200)
        dump = str(logs)
        self.assertNotIn("learn-alice", dump)
        self.assertNotIn(auth["X-Token"], dump)

    def test_review_html_is_escaped(self):
        auth = self.login()
        self.request("POST", "/reviews", {"product": "chair", "text": "<script>alert(1)</script>"}, auth)
        html = self.request("GET", "/reviews/view", headers=auth)[1]
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_assistant_execute_requires_login(self):
        status, _ = self.request("POST", "/assistant/execute", {
            "decision": {"tool": "export_profiles"}})
        self.assertEqual(status, 401)

    def test_customer_cannot_export_or_delete_via_assistant(self):
        auth = self.login()
        for tool in ("export_profiles", "delete_tree"):
            status, _ = self.request("POST", "/assistant/execute", {
                "decision": {"tool": tool, "arguments": {"path": "."}}}, auth)
            self.assertEqual(status, 403)

    def test_customer_cannot_read_private_note_via_assistant(self):
        auth = self.login()
        status, _ = self.request("POST", "/assistant/execute", {
            "decision": {"tool": "read_file", "arguments": {"path": "private/operator-note.txt"}}}, auth)
        self.assertEqual(status, 403)


if __name__ == "__main__":
    unittest.main()
