"""
Kiểm tra chống tranh chấp tài nguyên (Race Condition):
1. Bán vượt kho khi nhiều người cùng đặt hàng (Checkout Race).
2. Tự nhân đôi/thổi phồng kho khi gửi nhiều yêu cầu hủy đơn đồng thời (Cancel Race).

Cách chạy (từ thư mục shop_website):
    python test_checkout_race.py
"""
import os
import shutil
import sys
import tempfile
import threading

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

tmp_dir = tempfile.mkdtemp()
tmp_db = os.path.join(tmp_dir, "race_test.db")
shutil.copy("shop.db", tmp_db)
os.environ["DATABASE_URL"] = "sqlite:///" + tmp_db

sys.path.insert(0, ".")

from models import Order, Product
from web import app, db, limiter

limiter.enabled = False
app.config["TESTING"] = True
app.config["CSRF_ENABLED"] = False

# -------------------------------------------------------------
# PHẦN 1: KIỂM TRA TRANH CHẤP KHI ĐẶT HÀNG (CHECKOUT RACE)
# -------------------------------------------------------------
STOCK, BUYERS = 5, 50
with app.app_context():
    p = Product.query.first()
    pid = p.id
    p.stock = STOCK
    db_session = p.query.session
    db_session.commit()
    before_orders = Order.query.count()

codes = []
barrier = threading.Barrier(BUYERS)


def buyer(i):
    c = app.test_client()
    c.post("/cart/add", data={"product_id": pid, "quantity": 1})
    barrier.wait()
    r = c.post(
        "/checkout",
        data={
            "customer_name": f"Buyer{i}",
            "customer_phone": f"0912345{i:03d}",
            "shipping_address": "Hanoi",
        },
    )
    codes.append(r.status_code)


ts = [threading.Thread(target=buyer, args=(i,)) for i in range(BUYERS)]
for t in ts:
    t.start()
for t in ts:
    t.join()

with app.app_context():
    created = Order.query.count() - before_orders
    stock_left = db.session.get(Product, pid).stock
    sample_order = Order.query.order_by(Order.id.desc()).first()
    sample_order_code = sample_order.order_code if sample_order else None

print("\n" + "=" * 60)
print("TEST 1: TRANH CHẤP KHO KHI MUA HÀNG (CHECKOUT RACE)")
print("=" * 60)
print(f"Tồn kho ban đầu: {STOCK} | Người mua đồng thời: {BUYERS}")
print(f"Đơn hàng được tạo: {created} (kỳ vọng: {STOCK})")
print(f"Tồn kho còn lại: {stock_left} (kỳ vọng: {STOCK - created})")
print("Mã HTTP nhận được:", {c: codes.count(c) for c in set(codes)})

checkout_ok = created == STOCK and stock_left == 0 and 500 not in codes
print("KẾT QUẢ TEST 1:", "PASS - Chống bán vượt kho thành công!" if checkout_ok else "FAIL - Lỗi tranh chấp tồn kho!")

# -------------------------------------------------------------
# PHẦN 2: KIỂM TRA TRANH CHẤP KHI HỦY ĐƠN HÀNG (CANCEL RACE)
# -------------------------------------------------------------
print("\n" + "=" * 60)
print("TEST 2: TRANH CHẤP HOÀN KHO KHI HỦY ĐƠN HÀNG (CANCEL RACE)")
print("=" * 60)

cancel_ok = False
if sample_order_code:
    CANCEL_ATTEMPTS = 20
    cancel_codes = []
    cancel_barrier = threading.Barrier(CANCEL_ATTEMPTS)

    with app.app_context():
        stock_before_cancel = db.session.get(Product, pid).stock

    def canceller():
        c = app.test_client()
        with c.session_transaction() as sess:
            sess["guest_orders"] = [sample_order_code]
        cancel_barrier.wait()
        r = c.post(
            f"/order/{sample_order_code}/cancel",
            data={"cancel_reason": "Thử nghiệm hủy song song"},
        )
        cancel_codes.append(r.status_code)

    cts = [threading.Thread(target=canceller) for _ in range(CANCEL_ATTEMPTS)]
    for t in cts:
        t.start()
    for t in cts:
        t.join()

    with app.app_context():
        stock_after_cancel = db.session.get(Product, pid).stock
        final_order = Order.query.filter_by(order_code=sample_order_code).first()

    expected_stock = stock_before_cancel + 1
    print(f"Số luồng yêu cầu hủy đồng thời cho cùng 1 đơn: {CANCEL_ATTEMPTS}")
    print(f"Tồn kho trước hủy: {stock_before_cancel} | Tồn kho sau hủy: {stock_after_cancel} (kỳ vọng: {expected_stock})")
    print(f"Trạng thái cuối của đơn hàng: {final_order.status}")
    cancel_ok = stock_after_cancel == expected_stock and final_order.status == "cancelled"
    print("KẾT QUẢ TEST 2:", "PASS - Hoàn tồn kho đúng 1 lần duy nhất, không bị nhân đôi!" if cancel_ok else "FAIL - Lỗi nhân đôi tồn kho!")
else:
    print("Bỏ qua Test 2 do không có đơn hàng mẫu.")

shutil.rmtree(tmp_dir, ignore_errors=True)
all_pass = checkout_ok and cancel_ok
print("\n" + "=" * 60)
print("TỔNG KẾT:", "TẤT CẢ TEST ĐỀU ĐẠT CHUẨN AN TOÀN (ALL PASS)!" if all_pass else "CÓ TEST THẤT BẠI!")
print("=" * 60 + "\n")

sys.exit(0 if all_pass else 1)
