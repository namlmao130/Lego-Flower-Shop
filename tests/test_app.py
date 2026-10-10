"""Regression tests using disposable databases and mocked email delivery."""

import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from werkzeug.datastructures import FileStorage

# These values are set before config.py reads local .env settings.
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "test-only-secret"
os.environ["REQUIRE_POSTGRES"] = "false"

from app import create_app
from app.extensions import db
from app.models import Admin, Category, Customer, Order, Product
from app.services.email_service import get_reset_serializer
from app.services.image_service import process_and_save_avatar
from app.services.order_service import StockUnavailable, place_order


class AppTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="shop-tests-")
        self.addCleanup(self.directory.cleanup)
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "SQLALCHEMY_ENGINE_OPTIONS": {},
                "SECRET_KEY": "test-only-secret",
                "RATELIMIT_ENABLED": False,
                "CACHE_TYPE": "NullCache",
                "UPLOAD_FOLDER": self.directory.name,
                "AVATAR_UPLOAD_FOLDER": str(Path(self.directory.name) / "avatars"),
            },
            initialize_database=False,
        )
        with self.app.app_context():
            db.create_all()
            category = Category(name="Test flowers")
            product = Product(name="Test bouquet", price=120000, stock=5, category=category)
            customer = Customer(
                phone="0912345678", email="customer@example.test", full_name="Test Customer"
            )
            customer.set_password("original-password")
            admin = Admin(username="admin")
            admin.set_password("test-admin-password")
            db.session.add_all([category, product, customer, admin])
            db.session.commit()
            self.pid, self.cid, self.aid = product.id, customer.id, admin.id
        self.client = self.app.test_client()
        self.addCleanup(self.dispose)

    def dispose(self):
        with self.app.app_context():
            db.session.remove()
            db.engine.dispose()

    def sign_in(self, role):
        with self.client.session_transaction() as session:
            session["_user_id"] = f"{role}-{self.cid if role == 'customer' else self.aid}"
            session["_fresh"] = True

    def test_public_pages_and_error_handlers(self):
        for path in [
            "/",
            "/products",
            "/products?ajax=1",
            f"/product/{self.pid}",
            "/cart",
            "/login",
            "/register",
            "/forgot-password",
            "/orders",
        ]:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(self.client.get("/missing").status_code, 404)
        self.assertEqual(
            self.client.get("/api/missing").json, {"error": "Tài nguyên không tồn tại"}
        )
        self.assertEqual(self.client.get("/health").json["status"], "ok")

    def test_admin_access_is_preserved(self):
        self.assertEqual(self.client.get("/admin/dashboard").status_code, 302)
        self.sign_in("customer")
        self.assertEqual(self.client.get("/admin/dashboard").status_code, 403)
        self.sign_in("admin")
        for path in ["/admin/dashboard", "/admin/categories", "/admin/orders", "/admin/chat"]:
            self.assertEqual(self.client.get(path).status_code, 200, path)

    def test_customer_login_and_settings(self):
        response = self.client.post(
            "/login",
            data={"login_identifier": "CUSTOMER@example.test", "password": "original-password"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.get("/settings").status_code, 200)
        self.client.get("/logout")
        self.assertEqual(self.client.get("/settings").status_code, 302)

    def test_registration(self):
        response = self.client.post(
            "/register",
            data={
                "full_name": "New Customer",
                "phone": "0987654321",
                "email": "new@example.test",
                "password": "new-password",
                "password2": "new-password",
            },
        )
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            self.assertTrue(
                Customer.query.filter_by(email="new@example.test")
                .one()
                .check_password("new-password")
            )

    def test_cart_checkout_and_order_details(self):
        self.client.post("/cart/add", data={"product_id": self.pid, "quantity": 2})
        self.assertEqual(self.client.get("/checkout").status_code, 200)
        response = self.client.post(
            "/checkout",
            data={
                "customer_name": "Guest",
                "customer_phone": "0912345678",
                "shipping_address": "Test address",
            },
        )
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            order = Order.query.one()
            self.assertEqual(order.total_price, 240000)
            self.assertEqual(order.items[0].quantity, 2)
            self.assertEqual(db.session.get(Product, self.pid).stock, 3)
            order_code = order.order_code
        self.assertEqual(self.client.get(response.location).status_code, 200)
        self.assertEqual(self.client.get(f"/order/{order_code}").status_code, 200)
        with self.client.session_transaction() as session:
            self.assertNotIn("cart", session)

    def test_stock_failure_rolls_back_entire_order(self):
        with self.app.app_context():
            first = db.session.get(Product, self.pid)
            second = Product(name="Sold out", price=10, stock=0)
            db.session.add(second)
            db.session.commit()
            with self.assertRaises(StockUnavailable):
                place_order(
                    [
                        {"product": first, "quantity": 1, "subtotal": first.price},
                        {"product": second, "quantity": 1, "subtotal": second.price},
                    ],
                    first.price + second.price,
                    customer_id=None,
                    customer_name="Test",
                    customer_phone="0912345678",
                    shipping_address="Test",
                    delivery_time="Test",
                    customer_note="",
                )
            self.assertEqual(Order.query.count(), 0)
            self.assertEqual(db.session.get(Product, self.pid).stock, 5)

    def test_password_reset_mail_recipient_and_otp(self):
        with patch(
            "app.routes.auth.send_password_reset_email", return_value=(True, "sent")
        ) as send:
            response = self.client.post("/forgot-password", data={"email": "CUSTOMER@example.test"})
            self.assertEqual(response.status_code, 302)
            recipient, link, code = send.call_args.args
            self.assertEqual(recipient, "customer@example.test")
            self.assertEqual(len(code), 6)
        path = "/reset-password/" + link.rsplit("/", 1)[1]
        self.assertEqual(self.client.get(path).status_code, 200)
        wrong = self.client.post(
            path,
            data={
                "verification_code": "invalid",
                "password": "changed-password",
                "password2": "changed-password",
            },
        )
        self.assertEqual(wrong.status_code, 200)
        with self.app.app_context():
            self.assertTrue(db.session.get(Customer, self.cid).check_password("original-password"))
        success = self.client.post(
            path,
            data={
                "verification_code": code,
                "password": "changed-password",
                "password2": "changed-password",
            },
        )
        self.assertEqual(success.status_code, 302)
        with self.app.app_context():
            self.assertTrue(db.session.get(Customer, self.cid).check_password("changed-password"))

    def test_invalid_and_expired_reset_links(self):
        for token in ["invalid", "bad.signature.value"]:
            self.assertEqual(
                self.client.get(f"/reset-password/{token}").location, "/forgot-password"
            )
        with self.app.app_context(), patch("itsdangerous.timed.time.time", return_value=1):
            token = get_reset_serializer().dumps(
                {"email": "customer@example.test", "code": "123456"}, salt="password-reset-salt"
            )
        self.assertEqual(self.client.get(f"/reset-password/{token}").location, "/forgot-password")

    def test_csrf_origin_and_rate_limits(self):
        response = self.client.post(
            "/cart/add", data={"product_id": self.pid}, headers={"Origin": "https://other.example"}
        )
        self.assertEqual(response.status_code, 403)
        limited_app = create_app(
            {**self.app.config, "RATELIMIT_ENABLED": True}, initialize_database=False
        )
        with limited_app.app_context():
            db.create_all()
        limited_client = limited_app.test_client()
        statuses = [limited_client.post("/login", data={}).status_code for _ in range(6)]
        with limited_app.app_context():
            db.session.remove()
            db.engine.dispose()
        self.assertEqual(statuses, [200] * 5 + [429])

    def test_image_service_and_multiple_app_instances(self):
        buffer = io.BytesIO()
        Image.new("RGB", (500, 400), "red").save(buffer, "PNG")
        buffer.seek(0)
        with self.app.app_context():
            filename, error = process_and_save_avatar(
                FileStorage(buffer, filename="avatar.png"), self.cid
            )
        self.assertIsNone(error)
        with Image.open(Path(self.app.config["AVATAR_UPLOAD_FOLDER"]) / filename) as image:
            self.assertEqual(image.size, (320, 320))
        other = create_app(
            {**self.app.config, "SECRET_KEY": "different-test-key"}, initialize_database=False
        )
        with other.app_context():
            db.create_all()
            self.assertEqual(Product.query.count(), 0)
            db.session.remove()
            db.engine.dispose()
        with self.app.app_context():
            self.assertEqual(Product.query.count(), 1)


if __name__ == "__main__":
    unittest.main()
