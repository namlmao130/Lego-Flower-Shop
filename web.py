import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename

from config import Config
from models import db, Product, Category, Admin, ProductMedia

app = Flask(__name__)
app.config.from_object(Config)

# Tự động tạo thư mục uploads nếu chưa tồn tại (tránh lỗi FileNotFoundError khi upload ảnh)
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Khởi tạo database
db.init_app(app)

# Khởi tạo Flask-Login (chỉ dùng cho trang admin)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'admin_login'  # nếu chưa login mà vào trang admin -> đá về đây


@login_manager.user_loader
def load_user(user_id):
    return Admin.query.get(int(user_id))


@app.context_processor
def inject_nav_categories():
    # Giúp mọi trang (kể cả sidebar trong base.html) đều lấy được danh sách danh mục
    return dict(nav_categories=Category.query.all())


@app.after_request
def add_header(response):
    # Ngăn trình duyệt lưu cache trang HTML, đảm bảo xóa/sửa là trang web cập nhật ngay khi F5 hoặc quay lại
    if response.content_type and 'text/html' in response.content_type:
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response


def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


def get_media_type(filename):
    ext = filename.rsplit('.', 1)[1].lower()
    return 'video' if ext in app.config['ALLOWED_VIDEO_EXTENSIONS'] else 'image'


def save_media_files(files, product_id):
    """Lưu nhiều file ảnh/video, trả về danh sách ProductMedia đã tạo (chưa commit)."""
    saved = []
    for file in files:
        if file and file.filename and allowed_file(file.filename):
            filename = secure_filename(f"{product_id}_{file.filename}")
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            saved.append(ProductMedia(
                product_id=product_id,
                filename=filename,
                media_type=get_media_type(filename)
            ))
    return saved


# ============================================
#   TRANG PUBLIC (không cần login)
# ============================================

@app.route('/')
def index():
    # Trang chủ: hỗ trợ tìm kiếm sản phẩm và lọc theo danh mục
    q = request.args.get('q', '').strip()
    category_id = request.args.get('category', type=int)

    # Carousel phía trên: cố định các sản phẩm nổi bật mới nhất, hoàn toàn không bị ảnh hưởng bởi tìm kiếm
    carousel_products = Product.query.order_by(Product.id.desc()).limit(6).all()

    query = Product.query
    if category_id:
        query = query.filter_by(category_id=category_id)
    if q:
        query = query.filter(Product.name.ilike(f'%{q}%'))

    if q or category_id:
        products = query.order_by(Product.id.desc()).all()
    else:
        products = query.order_by(Product.id.desc()).limit(8).all()

    # Nếu là yêu cầu AJAX (chỉ load lại phần sản phẩm bên dưới)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.args.get('ajax') == '1':
        return render_template(
            '_product_list_partial.html',
            products=products,
            search_query=q,
            selected_category=category_id
        )

    categories = Category.query.all()
    return render_template(
        'index.html',
        products=products,
        carousel_products=carousel_products,
        categories=categories,
        search_query=q,
        selected_category=category_id
    )


@app.route('/products')
def products():
    # Danh sách toàn bộ sản phẩm, có thể lọc theo category và từ khóa tìm kiếm
    q = request.args.get('q', '').strip()
    category_id = request.args.get('category', type=int)
    query = Product.query
    if category_id:
        query = query.filter_by(category_id=category_id)
    if q:
        query = query.filter(Product.name.ilike(f'%{q}%'))
    products = query.order_by(Product.id.desc()).all()
    categories = Category.query.all()

    # Hỗ trợ AJAX load nhanh không reload cả trang
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.args.get('ajax') == '1':
        return render_template(
            '_product_list_partial.html',
            products=products,
            search_query=q,
            selected_category=category_id
        )

    return render_template('products.html', products=products, categories=categories,
                            selected_category=category_id, search_query=q)


@app.route('/product/<int:product_id>')
def product_detail(product_id):
    product = Product.query.get_or_404(product_id)
    # Lấy tối đa 4 sản phẩm cùng danh mục gợi ý thêm (loại trừ sản phẩm hiện tại)
    related_products = []
    if product.category_id:
        related_products = Product.query.filter(
            Product.category_id == product.category_id,
            Product.id != product.id
        ).order_by(Product.id.desc()).limit(4).all()
    if not related_products:
        # Nếu danh mục này không còn sp khác, lấy 4 sp mới nhất khác
        related_products = Product.query.filter(Product.id != product.id).order_by(Product.id.desc()).limit(4).all()

    return render_template('product_detail.html', product=product, related_products=related_products)


# ============================================
#   ADMIN - LOGIN / LOGOUT
# ============================================

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        admin = Admin.query.filter_by(username=username).first()

        if admin and admin.check_password(password):
            login_user(admin)
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Sai tên đăng nhập hoặc mật khẩu!', 'error')

    return render_template('admin/login.html')


@app.route('/admin/logout')
@login_required
def admin_logout():
    logout_user()
    return redirect(url_for('admin_login'))


# ============================================
#   ADMIN - QUẢN LÝ SẢN PHẨM (CRUD)
# ============================================

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    q = request.args.get('q', '').strip()
    category_id = request.args.get('category', type=int)

    query = Product.query
    if category_id:
        query = query.filter_by(category_id=category_id)
    if q:
        query = query.filter(Product.name.ilike(f'%{q}%'))

    products = query.order_by(Product.id.desc()).all()
    categories = Category.query.all()
    return render_template(
        'admin/dashboard.html',
        products=products,
        categories=categories,
        search_query=q,
        selected_category=category_id
    )


@app.route('/admin/add', methods=['GET', 'POST'])
@login_required
def admin_add_product():
    categories = Category.query.all()

    if request.method == 'POST':
        name = request.form.get('name')
        price = request.form.get('price')
        description = request.form.get('description')
        stock = request.form.get('stock', 0)
        category_id = request.form.get('category_id') or None

        new_product = Product(
            name=name,
            price=float(price),
            description=description,
            stock=int(stock),
            category_id=category_id
        )
        db.session.add(new_product)
        db.session.flush()  # để có new_product.id trước khi lưu file

        # Lưu nhiều ảnh/video cùng lúc
        media_files = request.files.getlist('media')
        for media in save_media_files(media_files, new_product.id):
            db.session.add(media)

        db.session.commit()
        flash('Đã thêm sản phẩm thành công!', 'success')
        return redirect(url_for('admin_dashboard'))

    return render_template('admin/add_product.html', categories=categories)


@app.route('/admin/edit/<int:product_id>', methods=['GET', 'POST'])
@login_required
def admin_edit_product(product_id):
    product = Product.query.get_or_404(product_id)
    categories = Category.query.all()

    if request.method == 'POST':
        product.name = request.form.get('name')
        product.price = float(request.form.get('price'))
        product.description = request.form.get('description')
        product.stock = int(request.form.get('stock', 0))
        product.category_id = request.form.get('category_id') or None

        # Thêm ảnh/video mới (không xóa ảnh cũ, xóa riêng qua nút Xóa ở từng ảnh)
        media_files = request.files.getlist('media')
        for media in save_media_files(media_files, product.id):
            db.session.add(media)

        db.session.commit()
        flash('Đã cập nhật sản phẩm!', 'success')
        return redirect(url_for('admin_dashboard'))

    return render_template('admin/edit_product.html', product=product, categories=categories)


@app.route('/admin/media/delete/<int:media_id>', methods=['POST'])
@login_required
def admin_delete_media(media_id):
    media = ProductMedia.query.get_or_404(media_id)
    product_id = media.product_id
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], media.filename)
    if os.path.exists(filepath):
        os.remove(filepath)
    db.session.delete(media)
    db.session.commit()
    flash('Đã xóa ảnh/video!', 'success')
    return redirect(url_for('admin_edit_product', product_id=product_id))


@app.route('/admin/delete/<int:product_id>', methods=['POST'])
@login_required
def admin_delete_product(product_id):
    product = Product.query.get_or_404(product_id)

    # 1. Xóa toàn bộ file ảnh / video liên quan trong thư mục static/uploads
    for m in product.media:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], m.filename)
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except OSError:
                pass

    if product.image:
        old_filepath = os.path.join(app.config['UPLOAD_FOLDER'], product.image)
        if os.path.exists(old_filepath):
            try:
                os.remove(old_filepath)
            except OSError:
                pass

    # 2. Xóa bản ghi trong database
    db.session.delete(product)
    db.session.commit()
    flash('Đã xóa sản phẩm thành công!', 'success')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/delete_multiple', methods=['POST'])
@login_required
def admin_delete_multiple():
    product_ids = request.form.getlist('product_ids')
    if not product_ids:
        flash('Chưa chọn sản phẩm nào để xóa!', 'error')
        return redirect(url_for('admin_dashboard'))

    deleted_count = 0
    for pid in product_ids:
        try:
            product = Product.query.get(int(pid))
            if product:
                # Xóa toàn bộ file ảnh / video liên quan trong thư mục static/uploads
                for m in product.media:
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], m.filename)
                    if os.path.exists(filepath):
                        try:
                            os.remove(filepath)
                        except OSError:
                            pass

                if product.image:
                    old_filepath = os.path.join(app.config['UPLOAD_FOLDER'], product.image)
                    if os.path.exists(old_filepath):
                        try:
                            os.remove(old_filepath)
                        except OSError:
                            pass

                db.session.delete(product)
                deleted_count += 1
        except Exception as e:
            print(f"Lỗi khi xóa sản phẩm {pid}: {e}")

    db.session.commit()
    flash(f'Đã xóa thành công {deleted_count} sản phẩm!', 'success')
    return redirect(url_for('admin_dashboard'))


# ============================================
#   ADMIN - QUẢN LÝ DANH MỤC (CRUD)
# ============================================

@app.route('/admin/categories')
@login_required
def admin_categories():
    categories = Category.query.all()
    return render_template('admin/categories.html', categories=categories)


@app.route('/admin/categories/add', methods=['GET', 'POST'])
@login_required
def admin_add_category():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if name:
            db.session.add(Category(name=name))
            db.session.commit()
            flash('Đã thêm danh mục!', 'success')
        else:
            flash('Tên danh mục không được để trống!', 'error')
        return redirect(url_for('admin_categories'))
    return render_template('admin/add_category.html')


@app.route('/admin/categories/edit/<int:category_id>', methods=['GET', 'POST'])
@login_required
def admin_edit_category(category_id):
    category = Category.query.get_or_404(category_id)
    if request.method == 'POST':
        category.name = request.form.get('name', '').strip()
        db.session.commit()
        flash('Đã cập nhật danh mục!', 'success')
        return redirect(url_for('admin_categories'))
    return render_template('admin/edit_category.html', category=category)


@app.route('/admin/categories/delete/<int:category_id>', methods=['POST'])
@login_required
def admin_delete_category(category_id):
    category = Category.query.get_or_404(category_id)
    # Sản phẩm thuộc danh mục này sẽ chuyển về "không có danh mục" thay vì bị xóa theo
    for product in category.products:
        product.category_id = None
    db.session.delete(category)
    db.session.commit()
    flash('Đã xóa danh mục!', 'success')
    return redirect(url_for('admin_categories'))


# ============================================
#   TẠO DATABASE + TÀI KHOẢN ADMIN MẶC ĐỊNH
# ============================================

def create_default_admin():
    """Tạo sẵn 1 tài khoản admin nếu chưa có, để bạn login lần đầu."""
    if not Admin.query.filter_by(username='admin').first():
        admin = Admin(username='admin')
        admin.set_password('admin123')  # NHỚ đổi mật khẩu này sau khi login lần đầu
        db.session.add(admin)
        db.session.commit()
        print(">>> Đã tạo tài khoản admin mặc định: username=admin, password=admin123")


with app.app_context():
    db.create_all()          # tạo các bảng nếu chưa có
    create_default_admin()   # tạo tài khoản admin mặc định


if __name__ == '__main__':
    app.run(debug=True)

