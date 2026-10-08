r"""
Script kiem tra suc khoe he thong (Health Check) cho Shop Hoa Lego.
Chay bang: .\venv\Scripts\python.exe .agents/skills/lego-shop-specialist/scripts/health_check.py
"""
import sys
import os

# Them thu muc goc vao sys.path de import web & models
current_dir = os.path.dirname(os.path.abspath(__file__))
# current_dir: .agents/skills/lego-shop-specialist/scripts -> 4 levels up to shop_website
project_root = os.path.abspath(os.path.join(current_dir, '..', '..', '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

from web import app, db
from models import Product, Category, Customer, Order, ChatMessage, Admin

def run_health_check():
    print("=" * 55)
    print("🏥 KIỂM TRA SỨC KHỎE HỆ THỐNG - TIỆM HOA LEGO")
    print("=" * 55)

    with app.app_context():
        # 1. Kiem tra Database
        try:
            db_engine = db.session.get_bind()
            with db_engine.connect() as conn:
                journal_mode = conn.exec_driver_sql("PRAGMA journal_mode;").scalar()
            print(f"[OK] Database ket noi thanh cong! SQLite Journal Mode: {journal_mode.upper()}")
        except Exception as e:
            print(f"[ERROR] Loi ket noi co so du lieu: {e}")
            return

        # 2. Thong so san pham & danh muc
        total_products = Product.query.count()
        in_stock_products = Product.query.filter(Product.stock > 0).count()
        total_cats = Category.query.count()
        print(f"[OK] San pham: {total_products} (Con hang: {in_stock_products}) | Danh muc: {total_cats}")

        # 3. Thong so khach hang & admin
        total_customers = Customer.query.count()
        total_admins = Admin.query.count()
        print(f"[OK] Khach hang thanh vien: {total_customers} | Tai khoan Admin: {total_admins}")

        # 4. Don hang
        total_orders = Order.query.count()
        pending_orders = Order.query.filter_by(status='pending').count()
        print(f"[OK] Tong don hang: {total_orders} (Don cho xu ly: {pending_orders})")

        # 5. Live Chat
        total_chat_msgs = ChatMessage.query.count()
        unread_chat = ChatMessage.query.filter_by(sender_type='customer', is_read=False).count()
        print(f"[OK] Tin nhan Live Chat: {total_chat_msgs} (Tin chua doc: {unread_chat})")

        print("=" * 55)
        print("-> HE THONG HOAT DONG BINH THUONG & ON DINH!")
        print("=" * 55)

if __name__ == '__main__':
    run_health_check()
