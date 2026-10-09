"""
Kiểm tra lỗi "bán vượt kho" khi nhiều người đặt hàng cùng lúc.

Cách chạy (từ thư mục gốc project):   python test_checkout_race.py
Script tự tạo BẢN SAO tạm của shop.db nên KHÔNG ảnh hưởng dữ liệu thật.
Kỳ vọng: số đơn tạo ra <= tồn kho ban đầu, và tồn kho cuối = tồn kho đầu - số đơn.
"""
import os, sys, shutil, tempfile, threading

tmp_dir = tempfile.mkdtemp()
tmp_db = os.path.join(tmp_dir, 'race_test.db')
shutil.copy('shop.db', tmp_db)
os.environ['DATABASE_URL'] = 'sqlite:///' + tmp_db      # config.py đọc biến này
sys.path.insert(0, '.')

from web import app, db, limiter
from models import Product, Order

limiter.enabled = False   # tắt rate limit để chỉ kiểm tra logic tranh chấp kho
app.config['TESTING'] = True

STOCK, BUYERS = 5, 50
with app.app_context():
    p = Product.query.first()
    pid = p.id
    p.stock = STOCK
    db.session.commit()
    before = Order.query.count()

codes, barrier = [], threading.Barrier(BUYERS)

def buyer(i):
    c = app.test_client()
    c.post('/cart/add', data={'product_id': pid, 'quantity': 1})
    barrier.wait()                         # tất cả bấm "Đặt hàng" cùng lúc
    r = c.post('/checkout', data={'customer_name': f'Buyer{i}',
               'customer_phone': f'0912345{i:03d}', 'shipping_address': 'Hanoi'})
    codes.append(r.status_code)

ts = [threading.Thread(target=buyer, args=(i,)) for i in range(BUYERS)]
[t.start() for t in ts]; [t.join() for t in ts]

with app.app_context():
    created = Order.query.count() - before
    stock_left = db.session.get(Product, pid).stock

print(f"Tồn kho ban đầu: {STOCK} | Người mua đồng thời: {BUYERS}")
print(f"Đơn hàng được tạo: {created} (tối đa hợp lệ: {STOCK})")
print(f"Tồn kho còn lại: {stock_left} (kỳ vọng: {STOCK - created})")
print("Mã HTTP:", {c: codes.count(c) for c in set(codes)})
ok = created <= STOCK and stock_left == STOCK - created and 500 not in codes
print("KẾT QUẢ:", "PASS - không bán vượt kho" if ok else "FAIL - bán vượt kho / sai tồn kho")
shutil.rmtree(tmp_dir, ignore_errors=True)
sys.exit(0 if ok else 1)
