from flask import jsonify
import pyodbc  # Thay sqlite3 bằng pyodbc cho SQL Server
from flask import render_template, request, session, redirect, url_for, flash
from flask import Flask, render_template, request, redirect, url_for, session, flash
import hashlib
from datetime import datetime
import pyodbc
import smtplib
from email.mime.text import MIMEText
import os
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
from vnpay import VNPay
import logging


load_dotenv()

EMAIL_USER = os.environ.get('EMAIL_USER')
EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD')

VNPAY_TMN_CODE = os.environ.get('VNPAY_TMN_CODE')
VNPAY_HASH_SECRET_KEY = os.environ.get('VNPAY_HASH_SECRET_KEY')
VNPAY_RETURN_URL = os.environ.get('VNPAY_RETURN_URL')

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Thay bằng khóa bí mật an toàn
app.config['UPLOAD_FOLDER'] = 'static/images'  # Thư mục lưu ảnh

# Cấu hình logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Kết nối SQL Server


def get_db_connection():
    conn_str = (
        'DRIVER={SQL Server};'
        'SERVER=DESKTOP-F9FPDIL;'
        'DATABASE=HemaShopDB;'
        'Trusted_Connection=yes;'
    )
    conn = pyodbc.connect(conn_str)
    return conn

# Hàm gửi email


def send_confirmation_email(to_email, full_name, order_date, delivery_date, total_amount, status="Xác nhận"):
    from_email = "EMAIL_USER"  # Thay bằng email của bạn
    password = "EMAIL_PASSWORD"  # Thay bằng mật khẩu email hoặc app password
    subject = f"{status} đơn hàng từ HEMA Shop"
    if status == "Xác nhận":
        body = f"""
        Chào {full_name},

        Đơn hàng của bạn đã được xác nhận thành công. Dưới đây là chi tiết:

        - Ngày đặt: {order_date}
        - Ngày giao hàng dự kiến: {delivery_date}
        - Tổng tiền: {total_amount:,} VND

        Chúng tôi sẽ liên hệ để giao hàng sớm nhất. Cảm ơn bạn!
        Trân trọng,
        HEMA Shop
        """
    else:  # Trường hợp hết hàng
        body = f"""
        Chào {full_name},

        Rất tiếc, chúng tôi gặp sự cố với đơn hàng của bạn do một số sản phẩm đã hết hàng. Dưới đây là chi tiết:

        - Ngày đặt: {order_date}
        - Tổng tiền: {total_amount:,} VND

        Vui lòng liên hệ để được hỗ trợ hoặc hủy đơn hàng.
        Trân trọng,
        HEMA Shop
        """
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = from_email
    msg['To'] = to_email

    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(from_email, password)
            server.sendmail(from_email, to_email, msg.as_string())
    except Exception as e:
        print(f"Failed to send email: {e}")


@app.route('/')
def index():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Lấy danh sách type và brand với is_active
    cursor.execute('SELECT type_id, type, is_active FROM types')
    types = [{'id': row[0], 'type': row[1], 'is_active': row[2]}
             for row in cursor.fetchall()]
    cursor.execute('SELECT brand_id, name, logo, is_active FROM brands')
    brands = [{'id': row[0], 'name': row[1], 'logo': row[2],
               'is_active': row[3]} for row in cursor.fetchall()]

    # Lấy tham số lọc và phân trang
    page = request.args.get('page', 1, type=int)
    selected_type_name = request.args.get(
        'type', session.get('selected_type', ''))
    selected_brand_name = request.args.get(
        'brand', session.get('selected_brand', ''))
    per_page = 6

    # Ánh xạ từ tên type/brand sang id
    type_id = next((t['id'] for t in types if t['type'] ==
                   selected_type_name), None) if selected_type_name else None
    brand_id = next((b['id'] for b in brands if b['name'] ==
                    selected_brand_name), None) if selected_brand_name else None

    # Lọc sản phẩm dựa trên type_id và brand_id có is_active = 1
    query = '''
        SELECT p.product_id, p.name, t.type, b.name AS brand, p.price, p.url_image_0, p.url_image_1, p.description 
        FROM products p 
        JOIN types t ON p.type_id = t.type_id 
        JOIN brands b ON p.brand_id = b.brand_id 
        WHERE t.is_active = 1 AND b.is_active = 1
    '''
    params = []
    if type_id:
        query += ' AND t.type_id = ?'
        params.append(type_id)
    if brand_id:
        query += ' AND b.brand_id = ?'
        params.append(brand_id)

    # Đếm tổng số sản phẩm
    cursor.execute(query, params)
    total_products = cursor.fetchall()
    total_items = len(total_products)
    total_pages = (total_items + per_page - 1) // per_page

    # Phân trang với TOP
    start_idx = (page - 1) * per_page
    if start_idx >= total_items:
        page = 1
        start_idx = 0
    query += ' ORDER BY p.product_id'
    cursor.execute(query, params)
    all_products = cursor.fetchall()
    products = all_products[start_idx:start_idx + per_page]

    # Lấy danh sách best-sellers (5 sản phẩm bán chạy nhất)
    cursor.execute('''
        SELECT TOP 5 p.product_id, p.name, p.price, p.url_image_0, bs.sales_count
        FROM products p
        JOIN best_sellers bs ON p.product_id = bs.product_id
        ORDER BY bs.sales_count DESC
    ''')  # Sử dụng LIMIT cho SQLite, với SQL Server dùng TOP 5
    best_sellers = cursor.fetchall()

    # Lấy full_name nếu đã đăng nhập
    full_name = None
    if 'username' in session:
        cursor.execute(
            'SELECT full_name FROM users WHERE username = ?', (session['username'],))
        full_name_result = cursor.fetchone()
        full_name = full_name_result[0] if full_name_result else session['username']
    elif 'admin_session' in session:
        cursor.execute(
            'SELECT account FROM admin WHERE account = ?', (session['admin_session'],))
        full_name_result = cursor.fetchone()
        full_name = f'admin {full_name_result[0]}' if full_name_result else session['admin_session']

    conn.close()

    session['selected_type'] = selected_type_name
    session['selected_brand'] = selected_brand_name

    return render_template('index.html',
                           products=products,
                           types=[t for t in types if t['is_active']],
                           brands=[b for b in brands if b['is_active']],
                           selected_type=selected_type_name,
                           selected_brand=selected_brand_name,
                           page=page,
                           full_name=full_name,
                           total_pages=total_pages,
                           best_sellers=best_sellers)


@app.route('/product_detail/<int:product_id>')
def product_detail(product_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    # Lấy thông tin sản phẩm
    cursor.execute('''
        SELECT p.product_id, p.name, t.type, b.name AS brand, p.price, p.url_image_0, p.url_image_1, p.description 
        FROM products p 
        JOIN types t ON p.type_id = t.type_id 
        JOIN brands b ON p.brand_id = b.brand_id 
        WHERE p.product_id = ?
    ''', (product_id,))
    product = cursor.fetchone()

    if not product:
        conn.close()
        return redirect(url_for('index'))

    # Chuyển đổi tuple thành dict
    product = {
        'id': product[0], 'name': product[1], 'type': product[2], 'brand': product[3],
        'price': float(product[4]), 'url_image_0': product[5], 'url_image_1': product[6],
        'description': product[7]
    }

    # Lấy thông tin khuyến mãi (nếu có)
    cursor.execute(
        'SELECT discount FROM discounts WHERE product_id = ? AND discount > 0', (product_id,))
    discount_row = cursor.fetchone()
    # Chuyển đổi Decimal thành float
    discount = float(discount_row[0]) if discount_row else 0.0

    # Tính giá đã giảm
    if discount > 0:
        discounted_price = product['price'] * (1 - discount / 100)
    else:
        discounted_price = product['price']

    # Thêm thông tin khuyến mãi và giá đã giảm vào product
    product['discount'] = discount
    product['discounted_price'] = round(discounted_price, 2)

    conn.close()
    return render_template('product_detail.html', product=product)


@app.route('/add_to_cart/<int:product_id>', methods=['POST'])
def add_to_cart(product_id):
    if 'username' not in session:
        return render_template('login.html')

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Lấy thông tin người dùng
        cursor.execute(
            'SELECT user_id FROM users WHERE username = ?', (session['username'],))
        user = cursor.fetchone()
        if not user:
            return jsonify({'error': 'Không tìm thấy thông tin người dùng!'}), 400
        user_id = user[0]

        # Lấy thông tin sản phẩm từ bảng products
        cursor.execute(
            'SELECT price FROM products WHERE product_id = ?', (product_id,))
        product = cursor.fetchone()
        if not product:
            return jsonify({'error': 'Sản phẩm không tồn tại!'}), 404
        unit_price = product[0]

        # Mặc định quantity = 1 nếu không có
        quantity = int(request.form.get('quantity', 1))

        # Lấy giảm giá từ bảng discounts
        cursor.execute(
            'SELECT discount FROM discounts WHERE product_id = ?', (product_id,))
        discount_row = cursor.fetchone()
        discount = float(discount_row[0]) if discount_row else 0.00

        total_price = float(unit_price) * quantity * \
            (1 - float(discount) / 100)

        # Kiểm tra xem sản phẩm đã có trong giỏ hàng chưa
        cursor.execute(
            'SELECT cart_id, quantity FROM cart WHERE user_id = ? AND product_id = ?', (user_id, product_id))
        cart_item = cursor.fetchone()
        if cart_item:
            new_quantity = cart_item[1] + quantity
            cursor.execute('UPDATE cart SET quantity = ?, total_price = ? WHERE cart_id = ?',
                           (new_quantity, float(unit_price) * new_quantity * (1 - float(discount) / 100), cart_item[0]))
        else:
            cursor.execute('INSERT INTO cart (user_id, product_id, quantity, discount, total_price) VALUES (?, ?, ?, ?, ?)',
                           (user_id, product_id, quantity, float(discount), total_price))

        conn.commit()

        # Trả về số lượng sản phẩm trong giỏ hàng
        cursor.execute(
            'SELECT COUNT(*) FROM cart WHERE user_id = ?', (user_id,))
        cart_count = cursor.fetchone()[0]
        return jsonify({'success': True, 'cart_count': cart_count})
    except Exception as e:
        conn.rollback()
        print(f"Error in add_to_cart: {e}")
        return jsonify({'error': 'Đã xảy ra lỗi khi thêm vào giỏ hàng!'}), 500
    finally:
        conn.close()


@app.route('/update_cart/<int:cart_id>', methods=['POST'])
def update_cart(cart_id):
    if 'username' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    # Lấy thông tin người dùng
    cursor.execute('SELECT user_id FROM users WHERE username = ?',
                   (session['username'],))
    user = cursor.fetchone()
    user_id = user[0]

    # Lấy thông tin giỏ hàng
    cursor.execute(
        'SELECT p.price, c.discount FROM cart c JOIN products p ON c.product_id = p.product_id WHERE cart_id = ? AND user_id = ?', (cart_id, user_id))
    cart_item = cursor.fetchone()
    if not cart_item:
        conn.close()
        return redirect(url_for('cart'))

    unit_price, discount = cart_item
    # Đảm bảo số lượng không âm
    new_quantity = max(1, int(request.form['quantity']))

    total_price = float(unit_price) * new_quantity * \
        (1 - float(discount) / 100)

    cursor.execute('UPDATE cart SET quantity = ?, total_price = ? WHERE cart_id = ?',
                   (new_quantity, total_price, cart_id))
    conn.commit()
    conn.close()
    return redirect(url_for('cart'))


@app.route('/cart')
def cart():
    if 'username' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    # Lấy thông tin người dùng
    cursor.execute('SELECT user_id FROM users WHERE username = ?',
                   (session['username'],))
    user = cursor.fetchone()
    user_id = user[0]

    # Lấy giỏ hàng
    cursor.execute(
        'SELECT c.cart_id ,p.product_id, p.name, p.url_image_0, c.quantity, p.price, c.discount, c.total_price FROM cart c JOIN products p ON c.product_id = p.product_id WHERE user_id = ?', (user_id,))
    cart_items = [{'cart_id': row[0], 'product_id': row[1], 'name': row[2], 'url_image_0': row[3], 'quantity': row[4], 'unit_price': float(
        row[5]), 'discount': float(row[6]), 'total_price': float(row[7])} for row in cursor.fetchall()]

    # Tính lại total_price cho từng item dựa trên discount
    for item in cart_items:
        item['total_price'] = item['unit_price'] * \
            item['quantity'] * (1 - item['discount'] / 100)

    total_quantity = sum(item['quantity'] for item in cart_items)
    total_amount = sum(item['total_price'] for item in cart_items)

    conn.close()
    return render_template('cart.html', cart_items=cart_items, total_quantity=total_quantity, total_amount=total_amount)


@app.route('/remove_from_cart/<int:cart_id>')
def remove_from_cart(cart_id):
    if 'username' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    # Lấy thông tin người dùng
    cursor.execute('SELECT user_id FROM users WHERE username = ?',
                   (session['username'],))
    user = cursor.fetchone()
    user_id = user[0]

    # Xóa sản phẩm khỏi giỏ hàng
    cursor.execute(
        'DELETE FROM cart WHERE cart_id = ? AND user_id = ?', (cart_id, user_id))
    conn.commit()
    conn.close()
    return redirect(url_for('cart'))


@app.route('/order', methods=['GET', 'POST'])
def order():
    if 'username' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Lấy thông tin người dùng
        cursor.execute(
            'SELECT user_id, full_name, address, phone, email FROM users WHERE username = ?', (session['username'],))
        user_info = cursor.fetchone()
        if not user_info:
            conn.close()
            return redirect(url_for('login'))

        user_id = user_info[0]
        user_info = {'id': user_id, 'full_name': user_info[1], 'address': user_info[2] or '',
                     'phone': user_info[3] or '', 'email': user_info[4] or ''}
        order_date = datetime.now().strftime('%Y-%m-%d %H:%M')

        if request.method == 'POST':
            # Lấy thông tin từ form
            full_name = request.form['full_name']
            address = request.form['address']
            phone = request.form['phone']
            email = request.form['email']
            delivery_date = datetime.strptime(
                request.form['delivery_date'], '%Y-%m-%d')
            delivery_date_str = delivery_date.strftime('%Y-%m-%d')

            # Lấy tổng tiền từ giỏ hàng
            cursor.execute(
                'SELECT SUM(total_price) FROM cart WHERE user_id = ?', (user_id,))
            total_amount = cursor.fetchone()[0] or 0.00

            # Lưu đơn hàng với trạng thái ban đầu (0 = đã xác nhận)
            query = '''
                INSERT INTO orders (user_id, full_name, address, phone, email, order_date, delivery_date, total_amount, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
            '''
            cursor.execute(query, (user_id, full_name, address, phone,
                           email, order_date, delivery_date, total_amount))
            cursor.execute('SELECT SCOPE_IDENTITY() AS id')
            order_id = cursor.fetchone()[0]

            # Lấy tất cả sản phẩm trong giỏ hàng
            cursor.execute(
                'SELECT c.cart_id ,p.product_id, p.name, p.url_image_0, c.quantity, p.price, c.discount, c.total_price FROM cart c JOIN products p ON c.product_id = p.product_id WHERE user_id = ?', (user_id,))
            cart_items = [{'cart_id': row[0], 'product_id': row[1], 'name': row[2], 'url_image_0': row[3], 'quantity': row[4], 'unit_price': float(
                row[5]), 'discount': float(row[6]), 'total_price': float(row[7])} for row in cursor.fetchall()]

            # Lưu chi tiết đơn hàng vào order_details
            for item in cart_items:
                query = '''
                    INSERT INTO order_details (order_id, product_id, name, url_image_0, quantity, unit_price, discount, total_price)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                '''
                cursor.execute(query, (order_id, item['product_id'], item['name'], item['url_image_0'],
                                       item['quantity'], item['unit_price'], item['discount'], item['total_price']))

            conn.commit()

            # Xóa giỏ hàng sau khi đặt hàng
            cursor.execute('DELETE FROM cart WHERE user_id = ?', (user_id,))
            conn.commit()

            flash('Đơn hàng đã được gửi thành công! Vui lòng chờ admin duyệt.')
            return redirect(url_for('order_status'))

        return render_template('place_order.html', user_info=user_info, order_date=order_date)

    except Exception as e:
        conn.rollback()
        print(f"Error in checkout: {e}")
        flash('Đã xảy ra lỗi khi đặt hàng. Vui lòng thử lại!')
        return redirect(url_for('cart'))

    finally:
        conn.close()


@app.route('/processing_order', methods=['POST'])
def processing_order():
    if 'username' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Lấy thông tin người dùng
        cursor.execute(
            'SELECT user_id FROM users WHERE username = ?', (session['username'],))
        user_info = cursor.fetchone()
        if not user_info:
            flash('Không tìm thấy thông tin người dùng!')
            return redirect(url_for('login'))
        user_id = user_info[0]

        # Lấy thông tin từ form
        full_name = request.form['full_name']
        address = request.form['address']
        phone = request.form['phone']
        email = request.form['email']
        order_date = datetime.now()
        delivery_date = datetime.strptime(
            request.form['delivery_date'], '%Y-%m-%d')
        order_date_str = order_date.strftime('%Y-%m-%d %H:%M:%S')
        delivery_date_str = delivery_date.strftime('%Y-%m-%d')

        # Lấy tổng tiền từ giỏ hàng
        cursor.execute(
            'SELECT SUM(total_price) FROM cart WHERE user_id = ?', (user_id,))
        total_amount = cursor.fetchone()[0] or 0.00

        # Kiểm tra giỏ hàng có trống không
        if total_amount == 0:
            flash('Giỏ hàng trống! Vui lòng thêm sản phẩm trước khi đặt hàng.')
            return redirect(url_for('cart'))

        # Kiểm tra dữ liệu trong cart
        cursor.execute('''
            SELECT c.product_id, c.quantity, p.price, c.discount, c.total_price
            FROM cart c JOIN products p ON c.product_id = p.product_id WHERE c.user_id = ?
        ''', (user_id,))
        cart_items = cursor.fetchall()
        if not cart_items:
            raise Exception("Không có sản phẩm hợp lệ trong giỏ hàng.")

        # Gọi stored procedure
        query = "EXEC sp_CreateOrder ?, ?, ?, ?, ?, ?, ?, ?"
        params = (user_id, full_name, address, phone, email,
                  order_date, delivery_date, total_amount)
        cursor.execute(query, params)

        # Lấy OrderId từ result set
        order_id = None
        while True:
            result = cursor.fetchone()
            if result:
                order_id = result[0]
                break
            if not cursor.nextset():  # Thoát nếu không còn result set
                break

        if not order_id:
            raise Exception("Không thể lấy order_id từ stored procedure.")

        conn.commit()

        # Gửi email xác nhận
        send_confirmation_email(
            email, full_name, order_date_str, delivery_date_str, total_amount)

        flash('Đơn hàng đã được đặt thành công! Vui lòng chờ xác nhận.')
        return redirect(url_for('order_status'))

    except pyodbc.Error as e:
        conn.rollback()
        error_msg = str(e).split('\n')[0] if str(
            e) else "Lỗi không xác định từ SQL Server"
        print(f"SQL Error in processing_order: {error_msg}")
        if e.args and len(e.args) > 1:
            print(f"Chi tiết lỗi: {e.args}")
        flash(
            f'Đã xảy ra lỗi khi xử lý đơn hàng: {error_msg}. Vui lòng thử lại!')
        return redirect(url_for('cart'))
    except Exception as e:
        conn.rollback()
        print(f"Error in processing_order: {e}")
        flash('Đã xảy ra lỗi khi xử lý đơn hàng. Vui lòng thử lại!')
        return redirect(url_for('cart'))
    finally:
        conn.close()


@app.route('/order_status')
def order_status():
    if 'username' not in session:
        flash('Vui lòng đăng nhập để xem trạng thái đơn hàng!', 'warning')
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            'SELECT user_id FROM users WHERE username = ?', (session['username'],))
        user = cursor.fetchone()
        if not user:
            flash('Không tìm thấy thông tin người dùng!', 'danger')
            logger.error(f"User not found for username: {session['username']}")
            return redirect(url_for('index'))
        user_id = user[0]

        trang_thai = request.args.get('trangThai', default=0, type=int)
        query = '''
            SELECT order_id, full_name, order_date, delivery_date, total_amount, status
            FROM orders WHERE user_id = ?
        '''
        params = (user_id,)
        if trang_thai > 0:
            query += ' AND status = ?'
            # Sửa lại: trang_thai trực tiếp là status, không trừ 1
            params += (trang_thai,)
        query += ' ORDER BY order_date DESC'
        cursor.execute(query, params)
        orders = cursor.fetchall()

        order_details = {}
        for order in orders:
            cursor.execute('''
                SELECT od.product_id, od.quantity, od.unit_price, od.discount, od.total_price, p.url_image_0
                FROM order_details od
                JOIN products p ON od.product_id = p.product_id
                WHERE od.order_id = ?
            ''', (order[0],))
            order_details[order[0]] = cursor.fetchall()

        status_mapping = {
            0: 'Đang chờ admin xác nhận',
            1: 'Admin đã duyệt và đang giao',
            2: 'Chờ thanh toán nhận hàng',
            3: 'Đã thanh toán nhưng chưa nhận hàng',
            4: 'Đã nhận hàng',
            5: 'Đã huỷ'
        }

        logger.info(
            f"Loaded {len(orders)} orders for user_id: {user_id} with filter: {trang_thai}")

    except pyodbc.Error as e:
        logger.error(f"Database error in order_status: {e}")
        flash('Đã xảy ra lỗi khi tải trạng thái đơn hàng!', 'danger')
        return redirect(url_for('index'))
    except Exception as e:
        logger.error(f"Unexpected error in order_status: {e}")
        flash('Đã xảy ra lỗi không mong muốn!', 'danger')
        return redirect(url_for('index'))
    finally:
        conn.close()

    return render_template('order_status.html', orders=orders, order_details=order_details, status_mapping=status_mapping)


@app.route('/cancel_order', methods=['POST'])
def cancel_order():
    if 'username' not in session:
        return jsonify({'error': 'Vui lòng đăng nhập!'}), 401

    order_id = request.form.get('order_id')
    if not order_id:
        return jsonify({'error': 'Mã đơn hàng không hợp lệ!'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            'SELECT user_id, status FROM orders WHERE order_id = ?', (order_id,))
        order = cursor.fetchone()
        if not order:
            return jsonify({'error': 'Đơn hàng không tồn tại!'}), 404
        user_id, status = order

        cursor.execute(
            'SELECT user_id FROM users WHERE username = ?', (session['username'],))
        current_user_id = cursor.fetchone()[0]
        if user_id != current_user_id:
            return jsonify({'error': 'Bạn không có quyền hủy đơn hàng này!'}), 403

        if status not in (0, 1):  # Chỉ cho hủy khi chờ xác nhận hoặc đang giao
            return jsonify({'error': 'Đơn hàng không thể hủy ở trạng thái hiện tại!'}), 400

        cursor.execute(
            'UPDATE orders SET status = 5 WHERE order_id = ?', (order_id,))
        conn.commit()
        flash('Đơn hàng #{} đã được hủy thành công!'.format(order_id), 'success')
        logger.info(f"Order {order_id} canceled by user {session['username']}")
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        logger.error(f"Error in cancel_order for order_id {order_id}: {e}")
        return jsonify({'error': 'Đã xảy ra lỗi khi hủy đơn hàng!'}), 500
    finally:
        conn.close()


@app.route('/pay_order', methods=['POST'])
def pay_order():
    if 'username' not in session:
        return jsonify({'error': 'Vui lòng đăng nhập!'}), 401

    order_id = request.form.get('order_id')
    if not order_id:
        return jsonify({'error': 'Mã đơn hàng không hợp lệ!'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            'SELECT user_id, status FROM orders WHERE order_id = ?', (order_id,))
        order = cursor.fetchone()
        if not order:
            return jsonify({'error': 'Đơn hàng không tồn tại!'}), 404
        user_id, status = order

        cursor.execute(
            'SELECT user_id FROM users WHERE username = ?', (session['username'],))
        current_user_id = cursor.fetchone()[0]
        if user_id != current_user_id:
            return jsonify({'error': 'Bạn không có quyền thanh toán đơn hàng này!'}), 403

        if status not in (1, 2):  # Chỉ cho thanh toán khi đang giao hoặc chờ thanh toán
            return jsonify({'error': 'Đơn hàng không thể thanh toán ở trạng thái hiện tại!'}), 400

        # Chuyển sang Đã nhận hàng
        cursor.execute(
            'UPDATE orders SET status = 4 WHERE order_id = ?', (order_id,))
        conn.commit()
        flash('Đơn hàng #{} đã thanh toán thành công (demo)!'.format(
            order_id), 'success')
        logger.info(
            f"Order {order_id} paid by user {session['username']} (demo)")
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        logger.error(f"Error in pay_order for order_id {order_id}: {e}")
        return jsonify({'error': 'Đã xảy ra lỗi khi thanh toán!'}), 500
    finally:
        conn.close()


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        full_name = request.form['full_name']
        username = request.form.get('username')
        password = request.form['password']
        email = request.form.get('email')
        address = request.form.get('address')
        phone = request.form.get('phone')
        birth_date = request.form.get('birth_date') or None

        # Băm mật khẩu với chuỗi "khaegar"
        password_to_hash = password + "khaegar"
        hashed_password = hashlib.sha256(
            password_to_hash.encode('utf-8')).hexdigest()

        conn = get_db_connection()
        cursor = conn.cursor()

        # Kiểm tra xem username đã tồn tại chưa
        cursor.execute(
            'SELECT user_id FROM users WHERE username = ?', (username,))
        if cursor.fetchone():
            conn.close()
            return render_template('register.html', error='Tên tài khoản đã tồn tại')

        cursor.execute(
            'SELECT admin_id FROM admin WHERE account = ?', (username,))
        if cursor.fetchone():
            conn.close()
            return render_template('register.html', error='Tên tài khoản đã tồn tại')
        # Chèn người dùng mới
        query = '''
            INSERT INTO users (full_name, username, password, email, address, phone, birth_date)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        '''
        cursor.execute(query, (full_name, username, hashed_password,
                       email, address, phone, birth_date))
        conn.commit()
        conn.close()

        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        account = request.form.get('account')
        password = request.form.get('password')

        if not account or not password:
            return render_template('login.html', error='Vui lòng điền đầy đủ thông tin')

        conn = get_db_connection()
        cursor = conn.cursor()

        # Kiểm tra đăng nhập admin
        cursor.execute(
            'SELECT admin_id, account, password FROM admin WHERE account = ?', (account,))
        admin = cursor.fetchone()
        if admin and admin.password == password:
            session['admin_session'] = admin.account
            conn.close()
            return redirect(url_for('index'))
        # Băm mật khẩu với chuỗi "khaegar"
        password_to_hash = password + "khaegar"
        hashed_password = hashlib.sha256(
            password_to_hash.encode('utf-8')).hexdigest()

        # Kiểm tra đăng nhập người dùng
        cursor.execute(
            'SELECT user_id, username, password FROM users WHERE username = ?', (account,))
        user = cursor.fetchone()
        if user and user.password == hashed_password:
            session['username'] = user.username
            conn.close()
            return redirect(url_for('index'))

        conn.close()
        return render_template('login.html', error='Tên tài khoản hoặc mật khẩu không đúng')

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('index'))


@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')

        if not email:
            return render_template('forgot_password.html', error='Vui lòng nhập email!')

        conn = get_db_connection()
        cursor = conn.cursor()

        # Kiểm tra email trong bảng users
        cursor.execute(
            'SELECT user_id, full_name, email FROM users WHERE email = ?', (email,))
        user = cursor.fetchone()
        conn.close()

        if user:
            user_id, full_name, user_email = user
            # Gửi email với liên kết đặt lại (giả định dùng token đơn giản, ví dụ: user_id)
            # Thay bằng domain thực tế
            reset_link = f"http://localhost:5000/reset_password/{user_id}"
            subject = "Yêu cầu đặt lại mật khẩu"
            body = f"""
            Chào {full_name},

            Chúng tôi đã nhận được yêu cầu đặt lại mật khẩu cho tài khoản của bạn. Vui lòng nhấp vào liên kết sau để đặt lại mật khẩu:
            {reset_link}

            Nếu bạn không yêu cầu điều này, vui lòng bỏ qua email này.

            Trân trọng,
            HEMA Shop
            """
            msg = MIMEText(body)
            msg['Subject'] = subject
            msg['From'] = "quockhanh2002bd@gmail.com"
            msg['To'] = email

            try:
                with smtplib.SMTP('smtp.gmail.com', 587) as server:
                    server.starttls()
                    # Thay bằng mật khẩu/app password
                    server.login("EMAIL_USER",
                                 "EMAIL_PASSWORD")
                    server.sendmail("your_email@example.com",
                                    email, msg.as_string())
                flash('Một liên kết đặt lại mật khẩu đã được gửi đến email của bạn!')
            except Exception as e:
                flash(f'Có lỗi khi gửi email: {e}')
        else:
            flash('Email không tồn tại trong hệ thống!')

        return redirect(url_for('forgot_password'))

    return render_template('forgot_password.html')


@app.route('/reset_password/<int:user_id>', methods=['GET', 'POST'])
def reset_password(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        'SELECT user_id, username FROM users WHERE id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()

    if not user:
        flash('Người dùng không tồn tại!')
        return redirect(url_for('login'))

    if request.method == 'POST':
        new_password = request.form.get('new_password')
        if new_password:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE users SET password = ? WHERE id = ?', (new_password, user_id))
            conn.commit()
            conn.close()
            flash('Mật khẩu đã được đặt lại thành công! Vui lòng đăng nhập lại.')
            return redirect(url_for('login'))
        else:
            flash('Vui lòng nhập mật khẩu mới!')

    return render_template('reset_password.html', user_id=user_id)


@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'username' not in session:
        flash('Vui lòng đăng nhập để xem trang profile!')
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    # Lấy thông tin người dùng hiện tại
    cursor.execute(
        'SELECT user_id, full_name, username, email, address, phone, birth_date FROM users WHERE username = ?', (session['username'],))
    user = cursor.fetchone()
    user_info = {
        'id': user[0],
        'full_name': user[1],
        'username': user[2],
        'email': user[3] or '',
        'address': user[4] or '',
        'phone': user[5] or '',
        'birth_date': user[6].strftime('%Y-%m-%d') if user[6] else ''
    }

    if request.method == 'POST':
        full_name = request.form.get('full_name')
        email = request.form.get('email')
        address = request.form.get('address')
        phone = request.form.get('phone')
        birth_date = request.form.get('birth_date') or None

        # Cập nhật thông tin người dùng
        cursor.execute('''
            UPDATE users 
            SET full_name = ?, email = ?, address = ?, phone = ?, birth_date = ?
            WHERE id = ?
        ''', (full_name, email, address, phone, birth_date, user_info['id']))
        conn.commit()
        flash('Thông tin đã được cập nhật thành công!')
        return redirect(url_for('profile'))

    conn.close()
    return render_template('profile.html', user=user_info)


@app.route('/admin_logout')
def admin_logout():
    session.pop('admin_session', None)
    return redirect(url_for('login'))


@app.route('/manage_products')
def manage_products():
    if 'admin_session' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    # Lấy tất cả sản phẩm
    cursor.execute('''
        SELECT p.product_id, p.name, p.price, p.description, d.discount, p.url_image_0, t.type, b.name 
        FROM products p 
        LEFT JOIN discounts d ON p.product_id = d.product_id 
        JOIN types t ON p.type_id = t.type_id 
        JOIN brands b ON p.brand_id = b.brand_id
    ''')
    products = [{'id': row[0], 'name': row[1], 'price': float(row[2]), 'description': row[3], 'discount': float(
        row[4]) if row[4] else 0.00, 'url_image_0': row[5], 'type': row[6], 'brand': row[7]} for row in cursor.fetchall()]
    conn.close()

    return render_template('admin/manage_products.html', products=products)


@app.route('/update_product/<int:product_id>', methods=['POST'])
def update_product(product_id):
    if 'admin_session' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    # Lấy dữ liệu từ form
    price = float(request.form.get('price', 0.00))
    discount = float(request.form.get('discount', 0.00))
    description = request.form.get('description', '')

    # Cập nhật sản phẩm
    cursor.execute('UPDATE products SET price = ?, description = ? WHERE id = ?',
                   (price, description, product_id))
    conn.commit()

    # Cập nhật hoặc thêm khuyến mãi
    cursor.execute(
        'SELECT id FROM discounts WHERE product_id = ?', (product_id,))
    discount_row = cursor.fetchone()
    if discount_row:
        cursor.execute(
            'UPDATE discounts SET discount = ? WHERE product_id = ?', (discount, product_id))
    elif discount > 0:
        cursor.execute(
            'INSERT INTO discounts (product_id, discount) VALUES (?, ?)', (product_id, discount))
    conn.commit()
    conn.close()

    return redirect(url_for('manage_products'))


@app.route('/manage_filters')
def manage_filters():
    if 'admin_session' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    # Lấy tất cả loại và thương hiệu
    cursor.execute('SELECT type_id, type, is_active FROM types')
    types = [{'id': row[0], 'type': row[1], 'is_active': row[2]}
             for row in cursor.fetchall()]
    cursor.execute('SELECT brand_id, name, logo, is_active FROM brands')
    brands = [{'id': row[0], 'name': row[1], 'logo': row[2],
               'is_active': row[3]} for row in cursor.fetchall()]

    conn.close()
    return render_template('admin/manage_filters.html', types=types, brands=brands)


@app.route('/update_filters', methods=['POST'])
def update_filters():
    if 'admin_session' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    # Lấy loại và thương hiệu từ form
    selected_types = request.form.getlist('types')
    selected_brands = request.form.getlist('brands')

    # Cập nhật is_active cho types
    cursor.execute('SELECT id FROM types')
    all_types = [row[0] for row in cursor.fetchall()]
    for type_id in all_types:
        is_active = 1 if str(type_id) in selected_types else 0
        cursor.execute(
            'UPDATE types SET is_active = ? WHERE id = ?', (is_active, type_id))

    # Cập nhật is_active cho brands
    cursor.execute('SELECT id FROM brands')
    all_brands = [row[0] for row in cursor.fetchall()]
    for brand_id in all_brands:
        is_active = 1 if str(brand_id) in selected_brands else 0
        cursor.execute(
            'UPDATE brands SET is_active = ? WHERE id = ?', (is_active, brand_id))

    conn.commit()
    conn.close()
    return redirect(url_for('manage_filters'))


@app.route('/manage_orders')
def manage_orders():
    if 'admin_session' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    trang_thai = request.args.get('trangThai', default=0, type=int)
    query = 'SELECT o.order_id, o.full_name, o.address, o.phone, o.email, o.order_date, o.delivery_date, o.total_amount, o.status FROM orders o'
    params = ()
    if trang_thai == 1:
        query += ' WHERE o.status = 0'  # Đang chờ duyệt
    elif trang_thai == 2:
        query += ' WHERE o.status = 1'  # Đã duyệt
    else:
        query += ' WHERE o.status IN (0, 1)'  # Mặc định cả hai trạng thái
    cursor.execute(query, params)
    orders = [{'id': row[0], 'full_name': row[1], 'address': row[2], 'phone': row[3], 'email': row[4], 'order_date': row[5],
               'delivery_date': row[6], 'total_amount': float(row[7]), 'status': row[8]} for row in cursor.fetchall()]
    conn.close()

    return render_template('admin/manage_orders.html', orders=orders)


@app.route('/approve_order/<int:order_id>')
def approve_order(order_id):
    if 'admin_session' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        'SELECT full_name, email, order_date, delivery_date, total_amount FROM orders WHERE order_id = ? AND status = 0', (order_id,))
    order = cursor.fetchone()
    if order:
        full_name, email, order_date, delivery_date, total_amount = order
        order_date_str = order_date.strftime(
            '%Y-%m-%d %H:%M') if order_date else ''
        delivery_date_str = delivery_date.strftime(
            '%Y-%m-%d') if delivery_date else ''
        send_confirmation_email(
            email, full_name, order_date_str, delivery_date_str, total_amount, "Xác nhận")
        cursor.execute(
            'UPDATE orders SET status = 1 WHERE order_id = ?', (order_id,))
        conn.commit()
        flash('Đơn hàng đã được duyệt và email xác nhận đã gửi.')
    else:
        flash('Đơn hàng không tồn tại hoặc đã được duyệt.')

    conn.close()
    return redirect(url_for('manage_orders'))


@app.route('/reject_order/<int:order_id>')
def reject_order(order_id):
    if 'admin_session' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        'SELECT full_name, email, order_date, total_amount FROM orders WHERE order_id = ? AND status = 0', (order_id,))
    order = cursor.fetchone()
    if order:
        full_name, email, order_date, total_amount = order
        order_date_str = order_date.strftime(
            '%Y-%m-%d %H:%M') if order_date else ''
        send_confirmation_email(
            email, full_name, order_date_str, None, total_amount, "Thông báo hết hàng")
        # 2 = từ chối
        cursor.execute(
            'UPDATE orders SET status = 2 WHERE order_id = ?', (order_id,))
        conn.commit()
        flash('Đơn hàng đã bị từ chối và email thông báo đã gửi.')
    else:
        flash('Đơn hàng không tồn tại hoặc đã được xử lý.')

    conn.close()
    return redirect(url_for('manage_orders'))


@app.route('/cancel_admin_order/<int:order_id>', methods=['POST'])
def cancel_admin_order(order_id):
    if 'admin_session' not in session:
        return jsonify({'error': 'Vui lòng đăng nhập với tư cách admin!'}), 401

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            'SELECT status FROM orders WHERE order_id = ?', (order_id,))
        order = cursor.fetchone()
        if not order or order[0] != 1:  # Chỉ hủy khi đã duyệt
            return jsonify({'error': 'Đơn hàng không thể hủy ở trạng thái hiện tại!'}), 400

        cursor.execute(
            'SELECT full_name, email FROM orders WHERE order_id = ?', (order_id,))
        full_name, email = cursor.fetchone()
        send_confirmation_email(email, full_name, '',
                                None, 0, "Thông báo hủy đơn hàng")
        # 5 = đã hủy
        cursor.execute(
            'UPDATE orders SET status = 5 WHERE order_id = ?', (order_id,))
        conn.commit()
        flash('Đơn hàng #{} đã bị hủy bởi admin và email thông báo đã gửi.'.format(
            order_id), 'warning')
        logger.info(f"Order {order_id} canceled by admin")
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        logger.error(
            f"Error in cancel_admin_order for order_id {order_id}: {e}")
        return jsonify({'error': 'Đã xảy ra lỗi khi hủy đơn hàng!'}), 500
    finally:
        conn.close()


@app.route('/add_product', methods=['GET', 'POST'])
def add_product():
    if 'admin_session' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        'SELECT type_id, type, is_active FROM types WHERE is_active = 1')
    types = [{'id': row[0], 'type': row[1]} for row in cursor.fetchall()]
    cursor.execute(
        'SELECT brand_id, name, is_active FROM brands WHERE is_active = 1')
    brands = [{'id': row[0], 'name': row[1]} for row in cursor.fetchall()]

    if request.method == 'POST':
        name = request.form['name']
        type_id = request.form['type_id']
        brand_id = request.form['brand_id']
        price = float(request.form['price'])
        description = request.form['description']

        # Kiểm tra trùng tên
        cursor.execute('SELECT id FROM products WHERE name = ?', (name,))
        if cursor.fetchone():
            flash('Tên sản phẩm đã tồn tại!')
            return render_template('admin/add_product.html', types=types, brands=brands)

        # Xử lý upload ảnh
        image_0 = request.files['image_0']
        image_1 = request.files['image_1']
        if image_0 and image_1:
            filename_0 = secure_filename(image_0.filename)
            filename_1 = secure_filename(image_1.filename)
            # Lưu ảnh vào static/images/
            image_0.save(os.path.join(
                app.config['UPLOAD_FOLDER'], filename_0.replace('\\', '/')))
            image_1.save(os.path.join(
                app.config['UPLOAD_FOLDER'], filename_1.replace('\\', '/')))
            # Sử dụng 'static/images/' với '/'
            print(filename_0)
            url_image_0 = f'{filename_0}'
            url_image_1 = f'{filename_1}'

            # Thêm sản phẩm vào database
            cursor.execute('''
                INSERT INTO products (name, type_id, brand_id, price, url_image_0, url_image_1, description)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (name, type_id, brand_id, price, url_image_0, url_image_1, description))
            conn.commit()
            flash('Sản phẩm đã được thêm thành công!')
            return redirect(url_for('manage_products'))
        else:
            flash('Vui lòng tải lên cả hai ảnh!')

    conn.close()
    return render_template('admin/add_product.html', types=types, brands=brands)

# Thanh toán online
# Hàm lấy IP client (giả định đơn giản)


def get_client_ip(request):
    return request.remote_addr or '127.0.0.1'


@app.route('/payment', methods=['GET', 'POST'])
def payment():
    if request.method == 'POST':
        # Lấy dữ liệu từ form
        order_type = request.form.get('order_type')
        order_id = request.form.get('order_id')
        amount = int(request.form.get('amount'))  # Đảm bảo là số nguyên
        order_desc = request.form.get('order_desc')
        bank_code = request.form.get('bank_code')
        language = request.form.get('language')

        # Khởi tạo VNPay
        vnp = VNPay()
        vnp.requestData['vnp_Version'] = '2.1.0'
        vnp.requestData['vnp_Command'] = 'pay'
        vnp.requestData['vnp_TmnCode'] = os.environ.get('VNPAY_TMN_CODE')
        vnp.requestData['vnp_Amount'] = amount * \
            100  # VNPay yêu cầu đơn vị nhỏ (VND)
        vnp.requestData['vnp_CurrCode'] = 'VND'
        vnp.requestData['vnp_TxnRef'] = order_id
        vnp.requestData['vnp_OrderInfo'] = order_desc
        vnp.requestData['vnp_OrderType'] = order_type
        vnp.requestData['vnp_Locale'] = language or 'vn'
        if bank_code and bank_code != "":
            vnp.requestData['vnp_BankCode'] = bank_code
        vnp.requestData['vnp_CreateDate'] = datetime.now().strftime(
            '%Y%m%d%H%M%S')
        vnp.requestData['vnp_IpAddr'] = get_client_ip(request)
        vnp.requestData['vnp_ReturnUrl'] = os.environ.get('VNPAY_RETURN_URL')

        # Tạo URL thanh toán
        vnpay_payment_url = vnp.get_payment_url(
            'https://sandbox.vnpayment.vn/paymentv2/vpcpay.html',  # URL sandbox
            os.environ.get('VNPAY_HASH_SECRET_KEY')
        )
        print(vnpay_payment_url)
        return redirect(vnpay_payment_url)
    return render_template("payment.html", title="Thanh toán")


@app.route('/payment_return', methods=['GET'])
def payment_return():
    vnp_response = request.args.to_dict()
    vnp_SecureHash = vnp_response.pop('vnp_SecureHash', None)
    vnp_TxnRef = vnp_response.get('vnp_TxnRef')
    vnp_TransactionStatus = vnp_response.get('vnp_TransactionStatus')

    # Xác thực chữ ký
    vnp = VNPay()
    vnp.requestData = vnp_response
    sign_data = "|".join([f"{k}={v}" for k, v in sorted(
        vnp_response.items())]) + "|" + os.environ.get('VNPAY_HASH_SECRET_KEY')
    calculated_hash = hmac.new(
        os.environ.get('VNPAY_HASH_SECRET_KEY').encode(),
        sign_data.encode(),
        hashlib.sha512
    ).hexdigest()

    if calculated_hash == vnp_SecureHash and vnp_TransactionStatus == '00':
        return f"Thanh toán thành công! Mã giao dịch: {vnp_TxnRef}"
    else:
        return "Thanh toán thất bại hoặc không hợp lệ!"


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
