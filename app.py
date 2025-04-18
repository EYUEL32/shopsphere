import os
from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.utils import secure_filename
import sqlite3

app = Flask(__name__)
app.secret_key = 'secretkey'
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Initialize database
def init_db():
    with sqlite3.connect('shop.db') as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS products (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT,
                        description TEXT,
                        price REAL,
                        image TEXT
                    )''')
        c.execute('''CREATE TABLE IF NOT EXISTS orders (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        product_id INTEGER,
                        customer_name TEXT,
                        phone TEXT,
                        status TEXT
                    )''')
        conn.commit()

init_db()

# Admin credentials
ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = 'password'

# Check if file is allowed
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Home page for buyers
@app.route('/')
def index():
    message = request.args.get('message')
    order_status = None

    if 'user_phone' in session:
        with sqlite3.connect('shop.db') as conn:
            c = conn.cursor()
            c.execute('SELECT status FROM orders WHERE phone = ? ORDER BY id DESC LIMIT 1', (session['user_phone'],))
            result = c.fetchone()
            if result:
                order_status = result[0]

    with sqlite3.connect('shop.db') as conn:
        c = conn.cursor()
        c.execute('SELECT * FROM products')
        products = c.fetchall()

    return render_template('index.html', products=products, message=message, order_status=order_status)

# Place order (modified to handle status checks and allow reordering)
@app.route('/order/<int:product_id>', methods=['POST'])
def order(product_id):
    name = request.form['name']
    phone = request.form['phone']

    session['user_phone'] = phone  # Store phone in session to check status later

    with sqlite3.connect('shop.db') as conn:
        c = conn.cursor()

        # Check if the user has previously ordered this product
        c.execute('SELECT * FROM orders WHERE phone = ? AND product_id = ? AND status != "Rejected"', (phone, product_id))
        existing_order = c.fetchone()

        if existing_order:
            message = "You have already ordered this product, and it is not rejected. Please check the status of your previous order."
            return redirect(url_for('index', message=message))

        # If no previous order or previous order was rejected, proceed with new order
        c.execute('INSERT INTO orders (product_id, customer_name, phone, status) VALUES (?, ?, ?, ?)',
                  (product_id, name, phone, 'Pending'))
        conn.commit()

    return redirect(url_for('index', message="Order placed successfully!"))

# Admin login
@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['admin'] = True
            return redirect(url_for('dashboard'))
    return render_template('admin_login.html')

# Admin dashboard
@app.route('/admin/dashboard')
def dashboard():
    if 'admin' not in session:
        return redirect(url_for('admin_login'))

    with sqlite3.connect('shop.db') as conn:
        c = conn.cursor()
        c.execute('''SELECT orders.id, orders.product_id, orders.customer_name, orders.phone, orders.status, products.name AS product_name
                     FROM orders
                     JOIN products ON orders.product_id = products.id''')
        orders = c.fetchall()

        orders = [{
            'id': order[0],
            'product_name': order[5],
            'customer_name': order[2],
            'customer_phone': order[3],
            'status': order[4]
        } for order in orders]

        c.execute('SELECT * FROM products')
        products = c.fetchall()

    return render_template('dashboard.html', orders=orders, products=products)

# Add product (admin only)
@app.route('/add_product', methods=['POST'])
def add_product():
    if 'admin' not in session:
        return redirect(url_for('admin_login'))

    name = request.form['name']
    description = request.form['description']
    price = request.form['price']
    image = request.files['image']

    if image and allowed_file(image.filename):
        filename = secure_filename(image.filename)
        image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        image.save(image_path)

        with sqlite3.connect('shop.db') as conn:
            c = conn.cursor()
            c.execute('INSERT INTO products (name, description, price, image) VALUES (?, ?, ?, ?)',
                      (name, description, price, filename))
            conn.commit()

    return redirect(url_for('dashboard'))

# Update order status (Accept/Reject)
@app.route('/update_order/<int:order_id>/<status>', methods=['POST'])
def update_order(order_id, status):
    if 'admin' not in session:
        return redirect(url_for('admin_login'))

    with sqlite3.connect('shop.db') as conn:
        c = conn.cursor()
        c.execute('UPDATE orders SET status = ? WHERE id = ?', (status, order_id))
        conn.commit()

        if status == 'Rejected':
            # Notify user they can reorder
            c.execute('SELECT phone FROM orders WHERE id = ?', (order_id,))
            phone = c.fetchone()[0]
            # You can add logic here to send a notification to the user, for example via email or SMS.
    
    return redirect(url_for('dashboard'))

# Delete product (admin only)
@app.route('/delete_product/<int:product_id>', methods=['POST'])
def delete_product(product_id):
    if 'admin' not in session:
        return redirect(url_for('admin_login'))

    with sqlite3.connect('shop.db') as conn:
        c = conn.cursor()
        c.execute('SELECT image FROM products WHERE id = ?', (product_id,))
        product = c.fetchone()

        if product:
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], product[0].split('/')[-1])
            if os.path.exists(image_path):
                os.remove(image_path)

            c.execute('DELETE FROM products WHERE id = ?', (product_id,))
            conn.commit()

    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    app.run(debug=True)
