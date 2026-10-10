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
from app.models import Admin, Category, ChatMessage, Customer, Order, Product
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

    def test_vietnamese_search_ranking_and_fields(self):
        from app.services.search_service import search_products

        with self.app.app_context():
            category = Category(name="Quà tặng")
            exact = Product(name="Hoa Hồng Đỏ", price=100, stock=1)
            phrase = Product(name="Bó Hoa Hồng Đỏ Lego", price=100, stock=1)
            description = Product(name="Mẫu đặc biệt", description="hoa hồng đỏ", price=100)
            categorized = Product(name="Tulip", category=category, price=100)
            literal = Product(name="Sale 50%_", price=100)
            db.session.add_all([exact, phrase, description, categorized, literal])
            db.session.commit()

            def matches(q):
                return [p.id for p in search_products(Product.query, q).all()]

            self.assertEqual(matches("HOA hong do"), [exact.id, phrase.id, description.id])
            self.assertEqual(set(matches("đỏ hồng")), {exact.id, phrase.id, description.id})
            self.assertEqual(matches("qua tang tulip"), [categorized.id])
            self.assertEqual(matches("50%_"), [literal.id])
            self.assertEqual(matches("hong nonexistent"), [])
            self.assertEqual(
                matches("ho\u0061 ho\u0302\u0300ng đo\u0309"), [exact.id, phrase.id, description.id]
            )
            category_id = category.id
        for path in ("/", "/products"):
            response = self.client.get(
                path, query_string={"q": "  qua   tang ", "ajax": 1, "category": category_id}
            )
            self.assertEqual(response.status_code, 200)
            self.assertIn("Tulip", response.get_data(as_text=True))
            self.assertNotIn("Mẫu đặc biệt", response.get_data(as_text=True))

    def test_search_keeps_pagination(self):
        with self.app.app_context():
            db.session.add_all([Product(name=f"Hoa Đào {n}", price=100) for n in range(30)])
            db.session.commit()
        first = self.client.get("/products?q=hoa+dao&ajax=1")
        second = self.client.get("/products?q=hoa+dao&page=2&ajax=1")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertIn("Hoa Đào 29", first.get_data(as_text=True))
        self.assertNotIn("Hoa Đào 0</", first.get_data(as_text=True))
        self.assertIn("Hoa Đào 0", second.get_data(as_text=True))

    def test_product_search_uses_shared_frontend_component(self):
        for path in ("/", "/products"):
            with self.subTest(path=path):
                html = self.client.get(path).get_data(as_text=True)
                self.assertIn("data-product-search", html)
                self.assertIn("data-products-container", html)
                self.assertIn("js/components/product-search.js", html)
                self.assertEqual(html.count("data-product-search"), 1)

    def test_base_layout_uses_external_shell_assets(self):
        html = self.client.get("/").get_data(as_text=True)
        self.assertIn("css/app-shell.css", html)
        self.assertIn("js/app-shell.js", html)
        self.assertIn("data-chat-session-id=", html)
        self.assertNotIn("const chatSessionId =", html)

        shell_js = (Path(self.app.static_folder) / "js" / "app-shell.js").read_text(
            encoding="utf-8"
        )
        self.assertIn("const POLL_CLOSED = 60000", shell_js)
        self.assertIn("visibilitychange", shell_js)
        self.assertIn("_pollInFlight", shell_js)

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

    def test_guest_chat_session_is_server_owned_and_isolated(self):
        guest = self.app.test_client()
        response = guest.post(
            "/api/chat/send",
            json={"message": "Tôi cần tư vấn", "session_id": "session-do-trinh-duyet-chon"},
        )
        self.assertEqual(response.status_code, 200)
        session_id = response.json["message"]["session_id"]
        self.assertTrue(session_id.startswith("guest_"))
        self.assertNotEqual(session_id, "session-do-trinh-duyet-chon")

        other_guest = self.app.test_client()
        stolen = other_guest.get("/api/chat/messages", query_string={"session_id": session_id})
        self.assertEqual(stolen.status_code, 200)
        self.assertEqual(stolen.json["messages"], [])
        self.assertNotEqual(stolen.json["session_id"], session_id)

        own = guest.get("/api/chat/messages")
        self.assertEqual([item["message"] for item in own.json["messages"]], ["Tôi cần tư vấn"])

    def test_chat_delivery_and_read_receipts(self):
        guest = self.app.test_client()
        sent = guest.post("/api/chat/send", json={"message": "Shop còn hàng không?"}).json
        session_id = sent["message"]["session_id"]

        admin = self.app.test_client()
        with admin.session_transaction() as session:
            session["_user_id"] = f"admin-{self.aid}"
            session["_fresh"] = True

        opened = admin.get(f"/api/admin/chat/messages/{session_id}")
        self.assertEqual(opened.status_code, 200)
        self.assertTrue(opened.json["messages"][0]["is_read"])

        reply = admin.post(
            "/api/admin/chat/reply",
            json={"session_id": session_id, "message": "Dạ sản phẩm vẫn còn ạ."},
        )
        self.assertEqual(reply.status_code, 200)
        self.assertFalse(reply.json["message"]["is_read"])

        received = guest.get("/api/chat/messages")
        self.assertEqual(received.status_code, 200)
        self.assertEqual(received.json["customer_read_through_id"], sent["message"]["id"])
        self.assertEqual(received.json["messages"][-1]["message"], "Dạ sản phẩm vẫn còn ạ.")
        with self.app.app_context():
            self.assertTrue(db.session.get(ChatMessage, reply.json["message"]["id"]).is_read)

        self.assertEqual(
            admin.post(
                "/api/admin/chat/reply",
                json={"session_id": "missing", "message": "Không tồn tại"},
            ).status_code,
            404,
        )
        self.assertEqual(
            admin.post(
                "/api/admin/chat/reply",
                json={"session_id": session_id, "message": "x" * 2001},
            ).status_code,
            400,
        )

    def test_guest_chat_merges_after_customer_login(self):
        guest = self.app.test_client()
        original = guest.post("/api/chat/send", json={"message": "Tin nhắn trước đăng nhập"})
        guest_session_id = original.json["message"]["session_id"]
        with guest.session_transaction() as session:
            session["_user_id"] = f"customer-{self.cid}"
            session["_fresh"] = True

        messages = guest.get("/api/chat/messages")
        self.assertEqual(messages.status_code, 200)
        self.assertEqual(messages.json["session_id"], f"cust_{self.cid}")
        with self.app.app_context():
            merged = ChatMessage.query.one()
            self.assertEqual(merged.session_id, f"cust_{self.cid}")
            self.assertEqual(merged.customer_id, self.cid)
            self.assertNotEqual(merged.session_id, guest_session_id)

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

    def test_password_reset_brevo_route(self):
        self.app.config.update(
            MAIL_PROVIDER="brevo",
            BREVO_API_KEY="test-only",
            BREVO_SENDER_EMAIL="shop@example.test",
        )
        with patch("app.services.email_service.build_opener") as build:
            reply = build.return_value.open.return_value.__enter__.return_value
            reply.status = 201
            reply.read.return_value = b'{"messageId":"test-id"}'
            response = self.client.post("/forgot-password", data={"email": "customer@example.test"})
            self.assertEqual(response.status_code, 302)
            reply.read.return_value = b"{}"
            response = self.client.post("/forgot-password", data={"email": "customer@example.test"})
            self.assertEqual(response.status_code, 200)
            self.assertIn("Hệ thống chưa thể gửi", response.get_data(as_text=True))
            build.return_value.open.reset_mock()
            self.client.post("/forgot-password", data={"email": "unknown@example.test"})
            build.return_value.open.assert_not_called()

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
