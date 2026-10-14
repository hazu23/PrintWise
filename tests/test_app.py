"""Automated tests for PrintWise.

Run them from the project folder with:   python -m unittest discover -s tests -v

They use a temporary SQLite database, so they never touch your MySQL data.
"""
import io
import os
import re
import sys
import tempfile
import unittest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app  # noqa: E402
from app.db import db  # noqa: E402
from app.models import (Admin, Customer, InventoryItem, Notification, Order, PrintShop,  # noqa: E402
                        SalesReport, Service, ShopOwner, Transaction, User)
from config import TestConfig  # noqa: E402

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
PASSWORD = "Passw0rd!"


class PrintWiseTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = self.tmp.name

        class Config(TestConfig):
            SQLITE_PATH = os.path.join(base, "test.sqlite3")
            UPLOAD_DIR = os.path.join(base, "uploads")
            AVATAR_DIR = os.path.join(base, "avatars")

        self.app = create_app(Config)
        with self.app.app_context():
            db.create_schema()
        self.client = self.app.test_client()

    def tearDown(self):
        self.tmp.cleanup()

    # ----- helpers -----------------------------------------------------------------
    def in_app(self, function):
        with self.app.app_context():
            return function()

    def csrf(self, client=None):
        client = client or self.client
        with client.session_transaction() as session:
            return session.setdefault("_csrf", "test-token")

    def post(self, url, data=None, client=None, **kwargs):
        client = client or self.client
        payload = dict(data or {})
        payload["_csrf"] = self.csrf(client)
        return client.post(url, data=payload, **kwargs)

    def make_shop(self, name="Test Print Shop", username="owner1"):
        def create():
            shop = PrintShop(name=name, address="1 Test Street, Sta. Cruz").save()
            owner = ShopOwner(full_name="Olivia Owner", username=username, email=f"{username}@example.com",
                              shop_id=shop.id, email_verified=1)
            owner.set_password(PASSWORD)
            owner.save()
            service = Service(shop_id=shop.id, name="Document printing",
                              paper_sizes="Short (8.5 x 11 in),A4 (8.3 x 11.7 in)",
                              paper_types="Bond paper,Cartolina", color_modes="bw,color").save()
            return shop.id, owner.id, service.id
        return self.in_app(create)

    def make_customer(self, username="juan", name="Juan Dela Cruz"):
        def create():
            customer = Customer(full_name=name, username=username, email=f"{username}@example.com", email_verified=1)
            customer.set_password(PASSWORD)
            return customer.save().id
        return self.in_app(create)

    def make_admin(self):
        def create():
            admin = Admin(full_name="Ada Admin", username="admin", email="admin@example.com", email_verified=1)
            admin.set_password(PASSWORD)
            return admin.save().id
        return self.in_app(create)

    def login(self, username, password=PASSWORD, client=None):
        return self.post("/login", {"identifier": username, "password": password}, client=client)

    def logged_in_client(self, username):
        client = self.app.test_client()
        response = self.login(username, client=client)
        self.assertEqual(response.status_code, 302, f"login failed for {username}")
        return client

    def order_data(self, service_id, /, **overrides):
        data = {"service_id": str(service_id), "paper_size": "Short (8.5 x 11 in)", "paper_type": "Bond paper",
                "color_mode": "bw", "sides": "double", "copies": "2", "pages": "10", "notes": "Staple please",
                "file": (io.BytesIO(PDF), "report.pdf")}
        data.update(overrides)
        return data

    def place_order(self, client, shop_id, service_id, /, **overrides):
        return self.post(f"/customer/orders/new?shop={shop_id}", self.order_data(service_id, **overrides),
                         client=client, content_type="multipart/form-data")

    def outbox(self):
        return self.app.extensions.get("outbox", [])


# =============================================================================
class PublicAndSecurityTests(PrintWiseTestCase):
    def test_public_pages_load(self):
        self.make_shop()
        for url in ("/", "/shops", "/shops/1", "/login", "/register", "/forgot-password"):
            self.assertEqual(self.client.get(url).status_code, 200, url)
        page = self.client.get("/").get_data(as_text=True)
        self.assertIn("PrintWise", page)
        self.assertIn("Test Print Shop", page)

    def test_unknown_page_shows_friendly_404(self):
        response = self.client.get("/does-not-exist")
        self.assertEqual(response.status_code, 404)
        self.assertIn("We could not find that page", response.get_data(as_text=True))
        self.assertNotIn("Traceback", response.get_data(as_text=True))

    def test_security_headers_present(self):
        headers = self.client.get("/").headers
        self.assertIn("default-src 'self'", headers["Content-Security-Policy"])
        self.assertEqual(headers["X-Frame-Options"], "DENY")
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")

    def test_forms_contain_csrf_token(self):
        self.assertRegex(self.client.get("/login").get_data(as_text=True), r'name="_csrf" value="[\w-]{20,}"')

    def test_post_without_csrf_token_is_rejected(self):
        response = self.client.post("/login", data={"identifier": "x", "password": "y"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("form expired", response.get_data(as_text=True))

    def test_post_with_wrong_csrf_token_is_rejected(self):
        self.client.get("/login")
        response = self.client.post("/login", data={"identifier": "x", "password": "y", "_csrf": "wrong"})
        self.assertEqual(response.status_code, 400)

    def test_protected_pages_redirect_to_login(self):
        for url in ("/customer/", "/shop/", "/admin/", "/profile", "/notifications"):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302, url)
            self.assertIn("/login", response.headers["Location"])

    def test_roles_cannot_open_each_others_areas(self):
        self.make_shop()
        self.make_customer()
        self.make_admin()
        customer = self.logged_in_client("juan")
        self.assertEqual(customer.get("/shop/").status_code, 403)
        self.assertEqual(customer.get("/admin/").status_code, 403)
        shop = self.logged_in_client("owner1")
        self.assertEqual(shop.get("/customer/").status_code, 403)
        self.assertEqual(shop.get("/admin/").status_code, 403)
        admin = self.logged_in_client("admin")
        self.assertEqual(admin.get("/shop/").status_code, 403)
        self.assertEqual(admin.get("/customer/").status_code, 403)

    def test_logout_ends_session(self):
        self.make_customer()
        client = self.logged_in_client("juan")
        self.assertEqual(client.get("/customer/").status_code, 200)
        self.post("/logout", client=client)
        self.assertEqual(client.get("/customer/").status_code, 302)

    def test_logout_needs_post(self):
        self.make_customer()
        client = self.logged_in_client("juan")
        self.assertEqual(client.get("/logout").status_code, 405)


class RegistrationAndLoginTests(PrintWiseTestCase):
    def register(self, **overrides):
        data = {"full_name": "Maria Santos", "username": "Maria_S", "email": "Maria@Example.com",
                "phone": "0917 123 4567", "password": PASSWORD, "confirm_password": PASSWORD}
        data.update(overrides)
        return self.post("/register", data)

    def test_register_success_hashes_password_and_sends_email(self):
        response = self.register()
        self.assertEqual(response.status_code, 302)
        user = self.in_app(lambda: User.find_by_login("maria_s"))
        self.assertIsNotNone(user)
        self.assertEqual(user.role, "customer")
        self.assertEqual(user.username, "maria_s")           # stored lower-case
        self.assertEqual(user.email, "maria@example.com")
        self.assertNotIn(PASSWORD, user.password_hash)        # never stored in plain text
        self.assertTrue(user.password_hash.startswith("pbkdf2:sha256"))
        self.assertFalse(user.email_verified)
        self.assertEqual(len(self.outbox()), 1)
        self.assertIn("/verify/", self.outbox()[0]["url"])
        self.assertEqual(self.client.get("/customer/").status_code, 200)  # logged in right away

    def test_register_validation_messages(self):
        cases = {
            "full_name": ("", "Full name is required."),
            "username": ("a!", "Use 3 to 30 letters, numbers, dots or underscores."),
            "email": ("not-an-email", "Enter a valid email address"),
            "password": ("short", "Use at least 8 characters."),
        }
        for field, (value, expected) in cases.items():
            response = self.register(**{field: value})
            self.assertEqual(response.status_code, 200, field)
            self.assertIn(expected, response.get_data(as_text=True), field)
        self.assertEqual(self.in_app(lambda: User.count()), 0)

    def test_password_rules_and_mismatch(self):
        self.assertIn("letter and one number", self.register(password="onlyletters", confirm_password="onlyletters").get_data(as_text=True))
        self.assertIn("do not match", self.register(confirm_password="Different1").get_data(as_text=True))

    def test_duplicate_username_and_email(self):
        self.make_customer("maria_s")
        self.assertIn("already taken", self.register().get_data(as_text=True))
        self.assertIn("already exists", self.register(username="other", email="maria_s@example.com").get_data(as_text=True))

    def test_form_keeps_what_user_typed(self):
        page = self.register(email="bad").get_data(as_text=True)
        self.assertIn('value="Maria Santos"', page)
        self.assertNotIn(PASSWORD, page)

    def test_login_with_username_or_email(self):
        self.make_customer()
        self.assertEqual(self.login("juan", client=self.app.test_client()).status_code, 302)
        self.assertEqual(self.login("JUAN@example.com", client=self.app.test_client()).status_code, 302)

    def test_wrong_password_gives_generic_message(self):
        self.make_customer()
        page = self.login("juan", "WrongPass1").get_data(as_text=True)
        self.assertIn("That username or password is not right", page)
        missing = self.login("nobody", "WrongPass1").get_data(as_text=True)
        self.assertIn("That username or password is not right", missing)

    def test_sql_injection_attempts_fail(self):
        self.make_customer()
        for attack in ("' OR '1'='1", "juan' --", "x'; DROP TABLE users; --"):
            self.assertEqual(self.login(attack, attack).status_code, 200, attack)
        self.assertEqual(self.in_app(lambda: User.count()), 1)

    def test_account_locks_after_repeated_failures(self):
        self.make_customer()
        for _ in range(3):
            self.login("juan", "WrongPass1")
        page = self.login("juan", PASSWORD).get_data(as_text=True)   # correct password, but locked
        self.assertIn("Too many wrong attempts", page)
        def unlock():
            user = User.find_by_login("juan")
            user.locked_until = datetime.now() - timedelta(minutes=1)
            user.save()
        self.in_app(unlock)
        self.assertEqual(self.login("juan").status_code, 302)

    def test_disabled_account_cannot_log_in(self):
        self.make_customer()
        def disable():
            user = User.find_by_login("juan")
            user.is_active = 0
            user.save()
        self.in_app(disable)
        self.assertIn("turned off", self.login("juan").get_data(as_text=True))

    def test_open_redirect_is_blocked(self):
        self.make_customer()
        for target in ("https://evil.example.com", "//evil.example.com", "/\\evil.example.com"):
            response = self.post(f"/login?next={target}", {"identifier": "juan", "password": PASSWORD})
            self.assertEqual(response.status_code, 302)
            self.assertNotIn("evil", response.headers["Location"], target)
            self.client.cookie_jar.clear() if hasattr(self.client, "cookie_jar") else None
            self.post("/logout")

    def test_next_redirect_to_own_page_works(self):
        self.make_customer()
        response = self.post("/login?next=/profile", {"identifier": "juan", "password": PASSWORD})
        self.assertTrue(response.headers["Location"].endswith("/profile"))

    def test_session_cookie_flags(self):
        self.make_customer()
        response = self.login("juan")
        cookie = response.headers.get("Set-Cookie", "")
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Lax", cookie)


class EmailFlowTests(PrintWiseTestCase):
    def test_verify_email_link_works_once_for_right_user(self):
        self.make_customer()
        def unverify():
            user = User.find_by_login("juan")
            user.email_verified = 0
            user.save()
        self.in_app(unverify)
        client = self.logged_in_client("juan")
        self.post("/verify/resend", client=client)
        link = self.outbox()[-1]["url"]
        client.get(link.replace("http://127.0.0.1:5000", ""))
        self.assertTrue(self.in_app(lambda: User.find_by_login("juan").email_verified))

    def test_bad_verification_token_is_refused(self):
        response = self.client.get("/verify/not-a-real-token", follow_redirects=True)
        self.assertIn("not valid or has expired", response.get_data(as_text=True))

    def test_password_reset_full_flow(self):
        self.make_customer()
        self.post("/forgot-password", {"email": "juan@example.com"})
        self.assertEqual(len(self.outbox()), 1)
        link = self.outbox()[0]["url"].replace("http://127.0.0.1:5000", "")
        self.assertEqual(self.client.get(link).status_code, 200)
        response = self.post(link, {"password": "NewPassw0rd", "confirm_password": "NewPassw0rd"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.login("juan", PASSWORD).status_code, 200)            # old password fails
        self.assertEqual(self.login("juan", "NewPassw0rd", client=self.app.test_client()).status_code, 302)
        # The link works only once.
        again = self.client.get(link, follow_redirects=True)
        self.assertIn("already used", again.get_data(as_text=True))

    def test_reset_does_not_reveal_whether_email_exists(self):
        response = self.post("/forgot-password", {"email": "ghost@example.com"}, follow_redirects=True)
        self.assertIn("If that email belongs to an account", response.get_data(as_text=True))
        self.assertEqual(len(self.outbox()), 0)


class ProfileTests(PrintWiseTestCase):
    def setUp(self):
        super().setUp()
        self.make_customer()
        self.client = self.logged_in_client("juan")

    def test_update_details(self):
        response = self.post("/profile/details", {"full_name": "Juan D. Cruz", "username": "juan2",
                                                  "email": "juan@example.com", "phone": "09171234567"})
        self.assertEqual(response.status_code, 302)
        user = self.in_app(lambda: User.find_by_login("juan2"))
        self.assertEqual(user.full_name, "Juan D. Cruz")

    def test_changing_email_requires_new_confirmation(self):
        self.post("/profile/details", {"full_name": "Juan", "username": "juan", "email": "new@example.com", "phone": ""})
        user = self.in_app(lambda: User.find_by_login("juan"))
        self.assertEqual(user.email, "new@example.com")
        self.assertFalse(user.email_verified)
        self.assertEqual(self.outbox()[-1]["to"], "new@example.com")

    def test_cannot_take_someone_elses_username(self):
        self.make_customer("maria", "Maria Santos")
        page = self.post("/profile/details", {"full_name": "Juan", "username": "maria", "email": "juan@example.com",
                                              "phone": ""}).get_data(as_text=True)
        self.assertIn("already taken", page)

    def test_change_password_needs_current_password(self):
        bad = self.post("/profile/password", {"current_password": "nope", "password": "NewPassw0rd", "confirm_password": "NewPassw0rd"})
        self.assertIn("not your current password", bad.get_data(as_text=True))
        ok = self.post("/profile/password", {"current_password": PASSWORD, "password": "NewPassw0rd", "confirm_password": "NewPassw0rd"})
        self.assertEqual(ok.status_code, 302)
        self.assertEqual(self.login("juan", "NewPassw0rd", client=self.app.test_client()).status_code, 302)

    def test_profile_photo_upload_and_remove(self):
        png = b"\x89PNG\r\n\x1a\n" + b"0" * 64
        response = self.post("/profile/photo", {"photo": (io.BytesIO(png), "me.png")}, content_type="multipart/form-data")
        self.assertEqual(response.status_code, 302)
        user = self.in_app(lambda: User.find_by_login("juan"))
        self.assertTrue(user.avatar_filename.endswith(".png"))
        self.assertEqual(self.client.get(f"/media/avatar/{user.avatar_filename}").status_code, 200)
        self.post("/profile/photo/remove")
        self.assertIsNone(self.in_app(lambda: User.find_by_login("juan").avatar_filename))

    def test_fake_image_is_rejected(self):
        response = self.post("/profile/photo", {"photo": (io.BytesIO(b"<?php evil ?>"), "me.png")}, content_type="multipart/form-data")
        self.assertIn("does not look like a real", response.get_data(as_text=True))
        response = self.post("/profile/photo", {"photo": (io.BytesIO(b"GIF89a"), "me.gif")}, content_type="multipart/form-data")
        self.assertIn("not allowed", response.get_data(as_text=True))


# =============================================================================
class OrderFlowTests(PrintWiseTestCase):
    def setUp(self):
        super().setUp()
        self.shop_id, self.owner_id, self.service_id = self.make_shop()
        self.customer_id = self.make_customer()
        self.customer = self.logged_in_client("juan")
        self.owner = self.logged_in_client("owner1")

    def test_full_order_lifecycle(self):
        # 1. customer places an order
        response = self.place_order(self.customer, self.shop_id, self.service_id)
        self.assertEqual(response.status_code, 302, response.get_data(as_text=True)[:500])
        order = self.in_app(lambda: Order.get(1))
        self.assertEqual(order.status, "pending")
        self.assertRegex(order.order_no, r"^PW-\d{4}-00001$")
        self.assertEqual((order.copies, order.sides, order.color_mode), (2, "double", "bw"))
        self.assertTrue(os.path.isfile(os.path.join(self.app.config["UPLOAD_DIR"], order.file_stored)))
        self.assertNotIn("report", order.file_stored)  # stored under a random name

        # the shop owner is told
        self.assertTrue(any("New order" in m["subject"] for m in self.outbox()))
        self.assertEqual(self.in_app(lambda: Notification.count(user_id=self.owner_id)), 1)

        # 2. customer sees the order but no price anywhere
        page = self.customer.get("/customer/orders/1").get_data(as_text=True)
        self.assertIn("Submitted", page)
        self.assertNotIn("₱", page)
        self.assertNotIn("Amount", page)

        # 3. shop accepts, prints, marks ready
        for status in ("accepted", "printing", "ready"):
            self.assertEqual(self.post("/shop/orders/1/status", {"status": status}, client=self.owner).status_code, 302)
            self.assertEqual(self.in_app(lambda: Order.get(1).status), status)
        subjects = [m["subject"] for m in self.outbox()]
        self.assertTrue(any("Ready for pickup" in s for s in subjects))
        self.assertIn("Ready", self.customer.get("/customer/").get_data(as_text=True))

        # 4. payment at the counter completes the order
        response = self.post("/shop/orders/1/pay", {"amount": "85.50", "method": "gcash", "note": "paid in full"}, client=self.owner)
        self.assertEqual(response.status_code, 302)
        def check():
            order = Order.get(1)
            payment = Transaction.find_by(order_id=1)
            return order.status, order.completed_at, payment.receipt_no, str(payment.amount), payment.method
        status, completed_at, receipt, amount, method = self.in_app(check)
        self.assertEqual(status, "completed")
        self.assertIsNotNone(completed_at)
        self.assertEqual(receipt, "OR-000001")
        self.assertEqual(float(amount), 85.5)
        self.assertEqual(method, "gcash")
        self.assertEqual(len(self.in_app(lambda: Order.get(1).history())), 5)

        # 5. the customer now sees completed; sales page and CSV include the payment
        self.assertIn("Completed", self.customer.get("/customer/orders/1").get_data(as_text=True))
        sales = self.owner.get("/shop/sales").get_data(as_text=True)
        self.assertIn("85.50", sales)
        csv_response = self.owner.get("/shop/sales/export.csv")
        self.assertEqual(csv_response.mimetype, "text/csv")
        self.assertIn("OR-000001", csv_response.get_data(as_text=True))

    def test_illegal_status_jumps_are_refused(self):
        self.place_order(self.customer, self.shop_id, self.service_id)
        self.post("/shop/orders/1/status", {"status": "ready"}, client=self.owner)   # pending -> ready not allowed
        self.assertEqual(self.in_app(lambda: Order.get(1).status), "pending")
        self.post("/shop/orders/1/status", {"status": "completed"}, client=self.owner)
        self.assertEqual(self.in_app(lambda: Order.get(1).status), "pending")
        response = self.post("/shop/orders/1/pay", {"amount": "10", "method": "cash"}, client=self.owner)
        self.assertEqual(self.in_app(lambda: Transaction.count()), 0)

    def test_payment_validation(self):
        self.place_order(self.customer, self.shop_id, self.service_id)
        for status in ("accepted", "ready"):
            self.post("/shop/orders/1/status", {"status": status}, client=self.owner)
        for amount in ("", "abc", "-5", "99999999"):
            page = self.post("/shop/orders/1/pay", {"amount": amount, "method": "cash"}, client=self.owner)
            self.assertEqual(page.status_code, 200, amount)
        self.assertEqual(self.post("/shop/orders/1/pay", {"amount": "5", "method": "bitcoin"}, client=self.owner).status_code, 200)
        self.assertEqual(self.in_app(lambda: Transaction.count()), 0)

    def test_decline_needs_reason_and_notifies_customer(self):
        self.place_order(self.customer, self.shop_id, self.service_id)
        self.post("/shop/orders/1/status", {"status": "rejected", "note": ""}, client=self.owner)
        self.assertEqual(self.in_app(lambda: Order.get(1).status), "pending")
        self.post("/shop/orders/1/status", {"status": "rejected", "note": "File will not open"}, client=self.owner)
        self.assertEqual(self.in_app(lambda: Order.get(1).status), "rejected")
        page = self.customer.get("/customer/orders/1").get_data(as_text=True)
        self.assertIn("File will not open", page)

    def test_order_form_validation(self):
        bad_cases = [
            ({"copies": "0"}, "Copies must be 1 or more."),
            ({"copies": "9999"}, "Copies must be 500 or less."),
            ({"copies": "abc"}, "whole number"),
            ({"paper_size": "Giant"}, "Choose a valid option"),
            ({"paper_type": "Glossy photo paper"}, "does not offer that paper type"),
            ({"paper_size": "A3 (11.7 x 16.5 in)"}, "does not offer that size"),
            ({"service_id": "999"}, "Choose one of the services"),
            ({"pages": "-3"}, "Number of pages must be 1 or more."),
            ({"notes": "x" * 501}, "500 characters or fewer"),
            ({"paper_size": "Custom size"}, "Custom size is required."),
        ]
        for overrides, expected in bad_cases:
            page = self.place_order(self.customer, self.shop_id, self.service_id, **overrides).get_data(as_text=True)
            self.assertIn(expected, page, overrides)
        self.assertEqual(self.in_app(lambda: Order.count()), 0)

    def test_service_options_are_enforced_server_side(self):
        # The shop's service offers only black and white; color must be refused even if the form is tampered with.
        def restrict():
            service = Service.get(self.service_id)
            service.color_modes = "bw"
            service.save()
        self.in_app(restrict)
        page = self.place_order(self.customer, self.shop_id, self.service_id, color_mode="color").get_data(as_text=True)
        self.assertIn("does not offer that color option", page)

    def test_file_is_required_and_type_checked(self):
        no_file = self.order_data(self.service_id)
        no_file.pop("file")
        page = self.post(f"/customer/orders/new?shop={self.shop_id}", no_file, client=self.customer,
                         content_type="multipart/form-data").get_data(as_text=True)
        self.assertIn("Attach the file you want printed.", page)
        for name, content, message in (("virus.exe", b"MZ" + b"0" * 50, "not allowed"),
                                       ("fake.pdf", b"this is not a pdf", "does not look like a real .pdf"),
                                       ("empty.pdf", b"", "empty")):
            page = self.place_order(self.customer, self.shop_id, self.service_id,
                                    file=(io.BytesIO(content), name)).get_data(as_text=True)
            self.assertIn(message, page, name)
        self.assertEqual(self.in_app(lambda: Order.count()), 0)
        self.assertEqual(len(os.listdir(self.app.config["UPLOAD_DIR"])) if os.path.isdir(self.app.config["UPLOAD_DIR"]) else 0, 0)

    def test_custom_size_and_type(self):
        def widen():
            service = Service.get(self.service_id)
            service.paper_sizes += ",Custom size"
            service.paper_types += ",Other (specify)"
            service.save()
        self.in_app(widen)
        self.place_order(self.customer, self.shop_id, self.service_id, paper_size="Custom size", custom_size="6 x 9 in",
                         paper_type="Other (specify)", custom_type="200 gsm board")
        order = self.in_app(lambda: Order.get(1))
        self.assertEqual(order.paper_size, "Custom: 6 x 9 in")
        self.assertEqual(order.paper_type, "Other: 200 gsm board")

    def test_customer_edit_cancel_delete_rules(self):
        self.place_order(self.customer, self.shop_id, self.service_id)
        # edit while pending
        response = self.post("/customer/orders/1/edit", self.order_data(self.service_id, copies="5", file=(io.BytesIO(b""), "")),
                             client=self.customer, content_type="multipart/form-data")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.in_app(lambda: Order.get(1).copies), 5)
        # pending orders cannot be deleted directly
        self.post("/customer/orders/1/delete", client=self.customer)
        self.assertEqual(self.in_app(lambda: Order.count()), 1)
        # cancel, then delete
        self.post("/customer/orders/1/cancel", client=self.customer)
        self.assertEqual(self.in_app(lambda: Order.get(1).status), "cancelled")
        stored = self.in_app(lambda: Order.get(1).file_stored)
        self.post("/customer/orders/1/delete", client=self.customer)
        self.assertEqual(self.in_app(lambda: Order.count()), 0)
        self.assertFalse(os.path.exists(os.path.join(self.app.config["UPLOAD_DIR"], stored)))

    def test_cannot_edit_or_cancel_after_shop_accepts(self):
        self.place_order(self.customer, self.shop_id, self.service_id)
        self.post("/shop/orders/1/status", {"status": "accepted"}, client=self.owner)
        self.post("/customer/orders/1/cancel", client=self.customer)
        self.assertEqual(self.in_app(lambda: Order.get(1).status), "accepted")
        response = self.customer.get("/customer/orders/1/edit", follow_redirects=True)
        self.assertIn("can no longer be changed", response.get_data(as_text=True))

    def test_replacing_file_removes_the_old_one(self):
        self.place_order(self.customer, self.shop_id, self.service_id)
        old = self.in_app(lambda: Order.get(1).file_stored)
        self.post("/customer/orders/1/edit", self.order_data(self.service_id, file=(io.BytesIO(PDF + b"v2"), "new.pdf")),
                  client=self.customer, content_type="multipart/form-data")
        new = self.in_app(lambda: Order.get(1).file_stored)
        self.assertNotEqual(old, new)
        self.assertFalse(os.path.exists(os.path.join(self.app.config["UPLOAD_DIR"], old)))
        self.assertTrue(os.path.exists(os.path.join(self.app.config["UPLOAD_DIR"], new)))

    def test_shop_not_accepting_orders(self):
        def pause():
            shop = PrintShop.get(self.shop_id)
            shop.accepting_orders = 0
            shop.save()
        self.in_app(pause)
        response = self.customer.get(f"/customer/orders/new?shop={self.shop_id}", follow_redirects=True)
        self.assertIn("not taking new orders", response.get_data(as_text=True))
        self.place_order(self.customer, self.shop_id, self.service_id)
        self.assertEqual(self.in_app(lambda: Order.count()), 0)

    def test_order_list_filters_and_search(self):
        self.place_order(self.customer, self.shop_id, self.service_id)
        self.place_order(self.customer, self.shop_id, self.service_id)
        self.post("/customer/orders/2/cancel", client=self.customer)
        page = self.customer.get("/customer/orders?status=cancelled").get_data(as_text=True)
        self.assertIn('href="/customer/orders/2"', page)
        self.assertNotIn('href="/customer/orders/1"', page)
        self.assertIn('href="/customer/orders/1"', self.customer.get("/customer/orders?q=00001").get_data(as_text=True))
        self.assertIn('href="/shop/orders/1"', self.owner.get("/shop/orders?status=pending&q=Juan").get_data(as_text=True))


class AccessControlOnOrdersTests(PrintWiseTestCase):
    def setUp(self):
        super().setUp()
        self.shop1, _, self.service1 = self.make_shop("Shop One", "owner1")
        self.shop2, _, self.service2 = self.make_shop("Shop Two", "owner2")
        self.make_customer("juan", "Juan Dela Cruz")
        self.make_customer("maria", "Maria Santos")
        self.juan = self.logged_in_client("juan")
        self.maria = self.logged_in_client("maria")
        self.owner1 = self.logged_in_client("owner1")
        self.owner2 = self.logged_in_client("owner2")
        self.place_order(self.juan, self.shop1, self.service1)

    def test_other_customer_cannot_see_or_change_the_order(self):
        self.assertEqual(self.maria.get("/customer/orders/1").status_code, 404)
        self.assertEqual(self.maria.get("/customer/orders/1/edit").status_code, 404)
        self.assertEqual(self.post("/customer/orders/1/cancel", client=self.maria).status_code, 404)
        self.assertEqual(self.post("/customer/orders/1/delete", client=self.maria).status_code, 404)
        self.assertEqual(self.in_app(lambda: Order.get(1).status), "pending")

    def test_other_shop_cannot_see_or_change_the_order(self):
        self.assertEqual(self.owner2.get("/shop/orders/1").status_code, 404)
        self.assertEqual(self.post("/shop/orders/1/status", {"status": "accepted"}, client=self.owner2).status_code, 404)
        self.assertEqual(self.post("/shop/orders/1/pay", {"amount": "5", "method": "cash"}, client=self.owner2).status_code, 404)
        self.assertEqual(self.in_app(lambda: Order.get(1).status), "pending")

    def test_file_download_permissions(self):
        self.assertEqual(self.juan.get("/orders/1/file").status_code, 200)
        self.assertEqual(self.owner1.get("/orders/1/file").status_code, 200)
        self.assertEqual(self.maria.get("/orders/1/file").status_code, 403)
        self.assertEqual(self.owner2.get("/orders/1/file").status_code, 403)
        self.assertEqual(self.client.get("/orders/1/file").status_code, 302)
        self.assertEqual(self.juan.get("/orders/999/file").status_code, 404)
        download = self.juan.get("/orders/1/file")
        self.assertIn("attachment", download.headers["Content-Disposition"])

    def test_other_shops_services_and_inventory_are_off_limits(self):
        def make():
            item = InventoryItem(shop_id=self.shop1, name="A4 paper", quantity=0).save()
            return item.id
        item_id = self.in_app(make)
        self.assertEqual(self.owner2.get(f"/shop/inventory/{item_id}").status_code, 404)
        self.assertEqual(self.post(f"/shop/inventory/{item_id}/delete", client=self.owner2).status_code, 404)
        self.assertEqual(self.owner2.get(f"/shop/services/{self.service1}/edit").status_code, 404)
        self.assertEqual(self.post(f"/shop/services/{self.service1}/delete", client=self.owner2).status_code, 404)

    def test_user_text_is_escaped_not_run_as_html(self):
        def rename():
            user = User.find_by_login("juan")
            user.full_name = "<script>alert(1)</script>"
            user.save()
        self.in_app(rename)
        page = self.owner1.get("/shop/orders/1").get_data(as_text=True)
        self.assertNotIn("<script>alert(1)</script>", page)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", page)


# =============================================================================
class ShopManagementTests(PrintWiseTestCase):
    def setUp(self):
        super().setUp()
        self.shop_id, self.owner_id, self.service_id = self.make_shop()
        self.owner = self.logged_in_client("owner1")

    def test_service_crud(self):
        data = {"name": "Photo printing", "description": "Glossy photos", "paper_sizes": ["Photo 4R (4 x 6 in)", "Photo 5R (5 x 7 in)"],
                "paper_types": ["Glossy photo paper"], "color_modes": ["color"], "is_active": "1"}
        self.assertEqual(self.post("/shop/services/new", data, client=self.owner).status_code, 302)
        service = self.in_app(lambda: Service.find_by(name="Photo printing"))
        self.assertEqual(service.size_options, ["Photo 4R (4 x 6 in)", "Photo 5R (5 x 7 in)"])
        self.assertEqual(service.color_options, ["color"])
        data["name"] = "Photo prints"
        data["color_modes"] = ["bw", "color"]
        self.post(f"/shop/services/{service.id}/edit", data, client=self.owner)
        self.assertEqual(self.in_app(lambda: Service.get(service.id).name), "Photo prints")
        self.post(f"/shop/services/{service.id}/delete", client=self.owner)
        self.assertIsNone(self.in_app(lambda: Service.get(service.id)))

    def test_service_validation(self):
        page = self.post("/shop/services/new", {"name": "X"}, client=self.owner).get_data(as_text=True)
        self.assertIn("at least 2 characters", page)
        self.assertIn("Choose at least one paper size.", page)
        self.assertIn("Choose at least one paper type.", page)
        self.assertIn("Choose at least one color option.", page)

    def test_inventory_crud_and_manual_adjustments(self):
        data = {"name": "Short bond paper", "category": "paper", "unit": "reams", "quantity": "10", "low_stock_level": "3", "notes": ""}
        self.assertEqual(self.post("/shop/inventory/new", data, client=self.owner).status_code, 302)
        item = self.in_app(lambda: InventoryItem.find_by(name="Short bond paper"))
        self.assertEqual(item.quantity, 10)
        self.assertEqual(len(self.in_app(lambda: InventoryItem.get(item.id).logs())), 1)   # starting stock logged
        # remove some by hand
        self.post(f"/shop/inventory/{item.id}/adjust", {"direction": "remove", "amount": "8", "reason": "weekend rush"}, client=self.owner)
        item = self.in_app(lambda: InventoryItem.get(item.id))
        self.assertEqual(item.quantity, 2)
        self.assertTrue(item.is_low)
        self.assertIn("running low", self.owner.get("/shop/inventory").get_data(as_text=True))
        self.assertIn("Short bond paper", self.owner.get("/shop/").get_data(as_text=True))   # low-stock card on dashboard
        # cannot go below zero
        page = self.post(f"/shop/inventory/{item.id}/adjust", {"direction": "remove", "amount": "50"}, client=self.owner).get_data(as_text=True)
        self.assertIn("not enough stock", page)
        self.assertEqual(self.in_app(lambda: InventoryItem.get(item.id).quantity), 2)
        # add stock, edit, delete
        self.post(f"/shop/inventory/{item.id}/adjust", {"direction": "add", "amount": "20"}, client=self.owner)
        self.assertEqual(self.in_app(lambda: InventoryItem.get(item.id).quantity), 22)
        data.update(name="Short bond (500 sheets)", quantity="22")
        self.post(f"/shop/inventory/{item.id}/edit", data, client=self.owner)
        self.assertEqual(self.in_app(lambda: InventoryItem.get(item.id).name), "Short bond (500 sheets)")
        self.post(f"/shop/inventory/{item.id}/delete", client=self.owner)
        self.assertIsNone(self.in_app(lambda: InventoryItem.get(item.id)))

    def test_inventory_validation(self):
        page = self.post("/shop/inventory/new", {"name": "", "category": "nope", "unit": "kg", "quantity": "-1", "low_stock_level": "x"},
                         client=self.owner).get_data(as_text=True)
        for message in ("Item name is required.", "Choose a valid option for category.", "Choose a valid option for unit.",
                        "Quantity must be 0 or more.", "Low stock level must be a whole number."):
            self.assertIn(message, page)

    def test_shop_settings(self):
        data = {"name": "Renamed Shop", "address": "99 New Road, Sta. Cruz", "contact_phone": "0917 000 1111",
                "contact_email": "shop@example.com", "hours": "Daily 9-5", "description": "Hello"}
        self.post("/shop/settings", data, client=self.owner)     # accepting_orders unchecked -> paused
        shop = self.in_app(lambda: PrintShop.get(self.shop_id))
        self.assertEqual(shop.name, "Renamed Shop")
        self.assertFalse(shop.accepting_orders)
        bad = self.post("/shop/settings", dict(data, contact_email="nope"), client=self.owner).get_data(as_text=True)
        self.assertIn("Enter a valid email address", bad)

    def test_sales_report_math(self):
        customer_id = self.make_customer()
        def create():
            now = datetime.now().replace(microsecond=0)
            for index, amount in enumerate((100, 50.5, 25)):
                order = Order(customer_id=customer_id, shop_id=self.shop_id, service_id=self.service_id, service_name="Doc",
                              paper_size="A4", paper_type="Bond paper", color_mode="bw", file_name="a.pdf",
                              file_stored="a.pdf", status="completed").save()
                Transaction(order_id=order.id, shop_id=self.shop_id, amount=amount, method="cash" if index < 2 else "gcash",
                            created_at=now - timedelta(days=index)).save()
            report = SalesReport(self.shop_id, now - timedelta(days=3), now + timedelta(days=1))
            return float(report.total), report.count, float(report.average), [(n, float(v)) for n, v in report.by_method()]
        total, count, average, methods = self.in_app(create)
        self.assertEqual((total, count, average), (175.5, 3, 58.5))
        self.assertEqual(methods[0], ("Cash", 150.5))
        self.assertEqual(self.owner.get("/shop/sales").status_code, 200)

    def test_csv_export_neutralises_formulas(self):
        customer_id = self.make_customer("evil", "=HYPERLINK(\"http://x\")")
        def create():
            order = Order(customer_id=customer_id, shop_id=self.shop_id, service_name="Doc", paper_size="A4", paper_type="Bond paper",
                          color_mode="bw", file_name="a.pdf", file_stored="a.pdf", status="completed").save()
            Transaction(order_id=order.id, shop_id=self.shop_id, amount=10, receipt_no="OR-000001").save()
        self.in_app(create)
        body = self.owner.get("/shop/sales/export.csv").get_data(as_text=True)
        self.assertIn("'=HYPERLINK", body)

    def test_dashboard_pages_load(self):
        for url in ("/shop/", "/shop/orders", "/shop/services", "/shop/inventory", "/shop/sales", "/shop/settings",
                    "/shop/services/new", "/shop/inventory/new", "/notifications", "/profile"):
            self.assertEqual(self.owner.get(url).status_code, 200, url)


# =============================================================================
class AdminTests(PrintWiseTestCase):
    def setUp(self):
        super().setUp()
        self.make_admin()
        self.admin = self.logged_in_client("admin")

    def shop_data(self, **overrides):
        data = {"name": "New Client Print", "address": "5 Client Street, Sta. Cruz", "contact_phone": "0917 555 1234",
                "contact_email": "", "hours": "", "description": "", "owner_name": "Pedro Owner",
                "owner_username": "pedro", "owner_email": "pedro@example.com", "owner_phone": "",
                "temporary_password": "Temp1234"}
        data.update(overrides)
        return data

    def test_admin_creates_shop_then_owner_sets_own_credentials(self):
        response = self.post("/admin/shops/new", self.shop_data(), client=self.admin)
        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        self.assertIn("Temp1234", page)               # shown once so the admin can pass it on
        self.assertIn("pedro", page)
        self.assertEqual(self.in_app(lambda: PrintShop.count()), 1)
        self.assertEqual(self.in_app(lambda: Service.count(shop_id=1)), 2)    # starter services
        self.assertTrue(any("shop account is ready" in m["subject"] for m in self.outbox()))
        self.assertNotIn("Temp1234", "".join(m["body"] for m in self.outbox()))  # password never emailed

        owner = self.app.test_client()
        self.assertEqual(self.login("pedro", "Temp1234", client=owner).status_code, 302)
        # everything is blocked until the owner picks their own username and password
        self.assertIn("/welcome/setup", owner.get("/shop/").headers["Location"])
        self.assertEqual(owner.get("/welcome/setup").status_code, 200)
        weak = self.post("/welcome/setup", {"username": "pedro_print", "password": "Temp1234", "confirm_password": "Temp1234"}, client=owner)
        self.assertIn("different from the temporary one", weak.get_data(as_text=True))
        done = self.post("/welcome/setup", {"username": "pedro_print", "password": "MyOwnPass1", "confirm_password": "MyOwnPass1"}, client=owner)
        self.assertEqual(done.status_code, 302)
        self.assertEqual(owner.get("/shop/").status_code, 200)
        # old credentials no longer work, new ones do
        self.assertEqual(self.login("pedro", "Temp1234", client=self.app.test_client()).status_code, 200)
        self.assertEqual(self.login("pedro_print", "MyOwnPass1", client=self.app.test_client()).status_code, 302)

    def test_admin_shop_form_validation_and_duplicates(self):
        self.post("/admin/shops/new", self.shop_data(), client=self.admin)
        page = self.post("/admin/shops/new", self.shop_data(), client=self.admin).get_data(as_text=True)
        self.assertIn("already taken", page)
        self.assertIn("already uses this email", page)
        bad = self.post("/admin/shops/new", self.shop_data(name="", owner_email="x", temporary_password="short", owner_username="a b"),
                        client=self.admin).get_data(as_text=True)
        for message in ("Shop name is required.", "Enter a valid email address", "Use at least 8 characters.", "Use 3 to 30 letters"):
            self.assertIn(message, bad)
        self.assertEqual(self.in_app(lambda: PrintShop.count()), 1)

    def test_edit_hide_and_delete_shop(self):
        self.post("/admin/shops/new", self.shop_data(), client=self.admin)
        self.post("/admin/shops/1/toggle", client=self.admin)
        self.assertFalse(self.in_app(lambda: PrintShop.get(1).is_active))
        self.assertEqual(self.client.get("/shops/1").status_code, 404)           # hidden from the public
        data = self.shop_data(is_active="1", name="Renamed Client")
        self.post("/admin/shops/1/edit", data, client=self.admin)
        self.assertEqual(self.in_app(lambda: PrintShop.get(1).name), "Renamed Client")
        self.post("/admin/shops/1/delete", client=self.admin)
        self.assertEqual(self.in_app(lambda: (PrintShop.count(), ShopOwner.count())), (0, 0))

    def test_shop_with_orders_cannot_be_deleted(self):
        shop_id, _, service_id = self.make_shop()
        self.make_customer()
        juan = self.logged_in_client("juan")
        self.place_order(juan, shop_id, service_id)
        self.post(f"/admin/shops/{shop_id}/delete", client=self.admin)
        self.assertEqual(self.in_app(lambda: PrintShop.count()), 1)

    def test_user_management(self):
        customer_id = self.make_customer()
        self.assertIn("Juan Dela Cruz", self.admin.get("/admin/users?role=customer").get_data(as_text=True))
        self.assertNotIn("Juan Dela Cruz", self.admin.get("/admin/users?q=zzz").get_data(as_text=True))
        self.post(f"/admin/users/{customer_id}/toggle", client=self.admin)
        self.assertFalse(self.in_app(lambda: User.get(customer_id).is_active))
        self.assertIn("turned off", self.login("juan").get_data(as_text=True))
        # reset password gives a temporary one and forces a change
        page = self.post(f"/admin/users/{customer_id}/reset-password", client=self.admin).get_data(as_text=True)
        temporary = re.search(r'id="cred-pass">([^<]+)<', page).group(1)
        self.post(f"/admin/users/{customer_id}/toggle", client=self.admin)
        client = self.app.test_client()
        self.assertEqual(self.login("juan", temporary, client=client).status_code, 302)
        self.assertIn("/welcome/setup", client.get("/customer/").headers["Location"])
        # admin cannot lock or delete themselves
        admin_id = self.in_app(lambda: User.find_by_login("admin").id)
        self.post(f"/admin/users/{admin_id}/toggle", client=self.admin)
        self.post(f"/admin/users/{admin_id}/delete", client=self.admin)
        self.assertTrue(self.in_app(lambda: User.get(admin_id).is_active))
        # deleting a customer without orders works
        self.post(f"/admin/users/{customer_id}/delete", client=self.admin)
        self.assertIsNone(self.in_app(lambda: User.get(customer_id)))

    def test_customer_with_orders_cannot_be_deleted(self):
        shop_id, _, service_id = self.make_shop()
        customer_id = self.make_customer()
        self.place_order(self.logged_in_client("juan"), shop_id, service_id)
        self.post(f"/admin/users/{customer_id}/delete", client=self.admin)
        self.assertIsNotNone(self.in_app(lambda: User.get(customer_id)))

    def test_admin_pages_load(self):
        shop_id, _, service_id = self.make_shop()
        self.make_customer()
        self.place_order(self.logged_in_client("juan"), shop_id, service_id)
        for url in ("/admin/", "/admin/shops", "/admin/shops/new", f"/admin/shops/{shop_id}", f"/admin/shops/{shop_id}/edit",
                    "/admin/users", "/admin/orders", f"/admin/orders?shop={shop_id}&status=pending", "/profile"):
            self.assertEqual(self.admin.get(url).status_code, 200, url)


# =============================================================================
class ModelTests(PrintWiseTestCase):
    def test_inheritance_and_polymorphism(self):
        self.make_shop()
        self.make_customer()
        self.make_admin()
        def check():
            users = {u.username: u for u in User.filter()}
            return (type(users["juan"]).__name__, type(users["owner1"]).__name__, type(users["admin"]).__name__,
                    users["juan"].home_endpoint(), users["owner1"].home_endpoint(), users["admin"].home_endpoint(),
                    Customer.count(), ShopOwner.count(), Admin.count())
        self.assertEqual(self.in_app(check), ("Customer", "ShopOwner", "Admin", "customer.dashboard", "shop.dashboard",
                                              "admin.dashboard", 1, 1, 1))

    def test_subclass_queries_only_return_their_own_role(self):
        self.make_shop()
        self.make_customer()
        self.assertIsNone(self.in_app(lambda: Customer.find_by(username="owner1")))
        self.assertIsNotNone(self.in_app(lambda: Customer.find_by(username="juan")))

    def test_password_is_encapsulated(self):
        def check():
            user = Customer(full_name="A B", username="ab", email="ab@example.com")
            user.set_password("Secret123")
            return user.check_password("Secret123"), user.check_password("secret123"), "password_hash" in user.to_dict()
        self.assertEqual(self.in_app(check), (True, False, False))

    def test_unknown_columns_and_orderings_are_rejected(self):
        def attempt(call):
            try:
                call()
            except ValueError:
                return True
            return False
        self.assertTrue(self.in_app(lambda: attempt(lambda: User.filter(**{"id; DROP TABLE users": 1}))))
        self.assertTrue(self.in_app(lambda: attempt(lambda: User.filter(order_by="id; DROP TABLE users"))))
        self.assertTrue(self.in_app(lambda: attempt(lambda: User.filter(order_by="id SIDEWAYS"))))

    def test_order_status_rules_live_in_the_model(self):
        self.make_shop()
        customer_id = self.make_customer()
        def check():
            order = Order(customer_id=customer_id, shop_id=1, service_name="Doc", paper_size="A4", paper_type="Bond paper",
                          color_mode="bw", file_name="a.pdf", file_stored="a.pdf").place(customer_id)
            outcomes = [order.order_no, order.stage_index, order.customer_can_edit]
            try:
                order.change_status("ready", 1)
            except ValueError:
                outcomes.append("refused")
            order.change_status("accepted", 1)
            outcomes += [order.customer_can_edit, order.stage_index]
            return outcomes
        self.assertEqual(self.in_app(check), ["PW-" + datetime.now().strftime("%y%m") + "-00001", 0, True, "refused", False, 1])

    def test_transaction_rolls_back_on_error(self):
        def check():
            try:
                with db.transaction():
                    PrintShop(name="Ghost", address="Nowhere Street").save()
                    raise RuntimeError("boom")
            except RuntimeError:
                pass
            return PrintShop.count()
        self.assertEqual(self.in_app(check), 0)


class DemoDataTests(PrintWiseTestCase):
    def test_seed_demo_creates_usable_data(self):
        from app.seed import seed_demo
        def seed():
            return seed_demo(), seed_demo()
        first, second = self.in_app(seed)
        self.assertTrue(any("admin" in line for line in first))
        self.assertTrue(any("already exist" in line for line in second))
        self.assertEqual(self.in_app(lambda: PrintShop.count()), 4)
        passwords = {"admin": "Admin@1234", "inkwell": "Shop@1234", "juan": "Customer@1234"}
        for username in ("admin", "inkwell", "juan"):
            client = self.app.test_client()
            self.assertEqual(self.login(username, passwords[username], client=client).status_code, 302, username)
            for url in ("/", "/profile") + {"admin": ("/admin/", "/admin/shops", "/admin/users", "/admin/orders"),
                                             "inkwell": ("/shop/", "/shop/orders", "/shop/sales", "/shop/inventory", "/shop/services"),
                                             "juan": ("/customer/", "/customer/orders", "/customer/orders/new")}[username]:
                self.assertEqual(client.get(url).status_code, 200, f"{username} {url}")
        self.assertGreater(self.in_app(lambda: Transaction.count()), 5)


if __name__ == "__main__":
    unittest.main()
