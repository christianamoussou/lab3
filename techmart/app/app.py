"""
TechMart — Application E-commerce
Backend Flask + PostgreSQL
"""

import os, time, base64, secrets, string
from datetime import datetime
from functools import wraps
import psycopg2
import psycopg2.extras
from flask import (Flask, request, render_template, redirect,
                   url_for, session, jsonify)

app = Flask(__name__)
app.secret_key = 'techmart_w3ak_s3cr3t_2024'
app.config['SESSION_COOKIE_PATH'] = '/'

@app.template_filter('dt')
def dateformat(v):
    """Format datetime or string to YYYY-MM-DD."""
    if hasattr(v, 'strftime'):
        return v.strftime('%Y-%m-%d')
    return str(v)[:10] if v else ''

DB_CONFIG = {
    'host':     os.getenv('DB_HOST', 'db'),
    'port':     int(os.getenv('DB_PORT', 5432)),
    'dbname':   os.getenv('DB_NAME', 'techmart'),
    'user':     os.getenv('DB_USER', 'techmart'),
    'password': os.getenv('DB_PASS', 'techmart123'),
}

VALID_CARD = {'number': '4111111111111111', 'expiry': '12/26', 'cvv': '123'}
TC_RATE    = 1.0


def get_db():
    return psycopg2.connect(**DB_CONFIG, cursor_factory=psycopg2.extras.RealDictCursor)


def wait_for_db(retries=15, delay=2):
    for i in range(retries):
        try:
            conn = get_db(); conn.close(); return
        except Exception:
            print(f"[DB] Attente PostgreSQL… ({i+1}/{retries})"); time.sleep(delay)
    raise RuntimeError("PostgreSQL inaccessible")


def gen_order_number():
    year = datetime.now().year
    suffix = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
    return f"TM-{year}-{suffix}"


# Token API intentionnellement faible : base64(user_id:role)
def gen_api_token(user_id, role):
    return base64.b64encode(f"{user_id}:{role}".encode()).decode()


def decode_api_token(token):
    try:
        uid, role = base64.b64decode(token).decode().split(':', 1)
        return int(uid), role
    except Exception:
        return None, None


def api_auth_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get('Authorization', '')
        if not auth.startswith('Bearer '):
            return jsonify({'error': 'Unauthorized'}), 401
        uid, role = decode_api_token(auth[7:])
        if uid is None:
            return jsonify({'error': 'Invalid token'}), 401
        request.api_user_id = uid
        request.api_role = role
        return f(*args, **kwargs)
    return decorated


def init_db():
    wait_for_db()
    conn = get_db(); c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY, username VARCHAR(100) UNIQUE NOT NULL,
        email VARCHAR(200) UNIQUE NOT NULL, password TEXT NOT NULL,
        role VARCHAR(20) DEFAULT 'user', phone VARCHAR(50) DEFAULT '',
        address TEXT DEFAULT '', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

    c.execute('''CREATE TABLE IF NOT EXISTS categories (
        id SERIAL PRIMARY KEY, name VARCHAR(100) NOT NULL,
        icon VARCHAR(20), color VARCHAR(20))''')

    c.execute('''CREATE TABLE IF NOT EXISTS products (
        id SERIAL PRIMARY KEY, name TEXT NOT NULL, description TEXT,
        price DECIMAL(10,2) NOT NULL, old_price DECIMAL(10,2),
        category_id INTEGER REFERENCES categories(id), stock INTEGER DEFAULT 100,
        rating DECIMAL(3,1) DEFAULT 4.5, review_count INTEGER DEFAULT 0,
        icon VARCHAR(20), badge VARCHAR(30))''')

    c.execute('''CREATE TABLE IF NOT EXISTS orders (
        id SERIAL PRIMARY KEY, user_id INTEGER REFERENCES users(id),
        total DECIMAL(10,2), status VARCHAR(30) DEFAULT 'pending',
        shipping_address TEXT, payment_method VARCHAR(20) DEFAULT 'card',
        order_number VARCHAR(30) UNIQUE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

    c.execute('''CREATE TABLE IF NOT EXISTS order_items (
        id SERIAL PRIMARY KEY, order_id INTEGER REFERENCES orders(id),
        product_id INTEGER REFERENCES products(id), quantity INTEGER, price DECIMAL(10,2))''')

    c.execute('''CREATE TABLE IF NOT EXISTS reviews (
        id SERIAL PRIMARY KEY, product_id INTEGER REFERENCES products(id),
        user_id INTEGER REFERENCES users(id), username VARCHAR(100),
        rating INTEGER, title TEXT, content TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

    c.execute('''CREATE TABLE IF NOT EXISTS coupons (
        id SERIAL PRIMARY KEY, code VARCHAR(50) UNIQUE, discount INTEGER, active INTEGER DEFAULT 1)''')

    c.execute('''CREATE TABLE IF NOT EXISTS virtual_wallet (
        id SERIAL PRIMARY KEY, user_id INTEGER UNIQUE REFERENCES users(id),
        balance DECIMAL(10,2) DEFAULT 0.00)''')

    c.execute('''CREATE TABLE IF NOT EXISTS password_resets (
        id SERIAL PRIMARY KEY, user_id INTEGER REFERENCES users(id),
        token VARCHAR(200) UNIQUE NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        used BOOLEAN DEFAULT FALSE)''')

    c.execute('''CREATE TABLE IF NOT EXISTS secret_data (
        id SERIAL PRIMARY KEY, label TEXT, value TEXT)''')

    cats = [(1,'Laptops','💻','#4A90E2'),(2,'Smartphones','📱','#7B68EE'),
            (3,'Tablets','📟','#50C878'),(4,'Audio','🎧','#FF6B6B'),
            (5,'Gaming','🎮','#F6AD55'),(6,'TV & Displays','📺','#20B2AA'),
            (7,'Cameras','📷','#FF8C69'),(8,'Wearables','⌚','#DA70D6'),
            (9,'Accessories','🖱️','#68D391')]
    for cat in cats:
        c.execute('INSERT INTO categories(id,name,icon,color) VALUES(%s,%s,%s,%s) ON CONFLICT(id) DO NOTHING', cat)
    c.execute("SELECT SETVAL('categories_id_seq',9,true)")

    products = [
        (1,'MacBook Pro 16" M3 Max','Puce M3 Max, 36 Go RAM unifiée, SSD 1 To, Liquid Retina XDR 16". Performance professionnelle ultime.',3299,3499,1,45,4.9,128,'💻','Bestseller'),
        (2,'Dell XPS 15 OLED','Intel Core i9-13900H, RTX 4070, écran OLED 3.5K, 32 Go DDR5.',2199,2499,1,30,4.7,89,'💻',None),
        (3,'ASUS ROG Zephyrus G14','AMD Ryzen 9, RTX 4090, QHD+ 165 Hz MiniLED, 32 Go DDR5.',1999,2199,1,25,4.8,156,'💻','Gaming'),
        (4,'Lenovo ThinkPad X1 Carbon','Intel Core Ultra 7, 32 Go, SSD 1 To PCIe 4, OLED 14" 2.8K.',1899,2099,1,60,4.8,203,'💻','Pro'),
        (5,'HP Spectre x360 14"','Intel Evo, 16 Go, OLED 2.8K tactile, 2-en-1 convertible.',1499,1699,1,40,4.6,67,'💻',None),
        (6,'iPhone 15 Pro Max 256 Go','Puce A17 Pro, titane, 48 MP ProRes, USB-C Thunderbolt.',1299,1399,2,120,4.9,512,'📱','Top'),
        (7,'Samsung Galaxy S24 Ultra','Snapdragon 8 Gen 3, S Pen intégré, 200 MP, 12 Go RAM.',1199,1299,2,85,4.8,389,'📱','Bestseller'),
        (8,'Google Pixel 9 Pro','Tensor G4, IA générative native, 7 ans de mises à jour Android.',1099,None,2,70,4.7,178,'📱','New'),
        (9,'OnePlus 12 5G','Snapdragon 8 Gen 3, charge SuperVOOC 100 W, triple caméra Hasselblad.',799,899,2,55,4.5,134,'📱','Promo'),
        (10,'iPad Pro 13" M4','Puce M4, écran Ultra Retina XDR OLED, Wi-Fi 6E, Apple Pencil Pro.',1399,1499,3,35,4.9,245,'📟','New'),
        (11,'Samsung Galaxy Tab S9 Ultra','Snapdragon 8 Gen 2, 14.6" AMOLED 120 Hz, S Pen inclus, IP68.',1099,1199,3,28,4.7,167,'📟',None),
        (12,'Microsoft Surface Pro 10','Intel Core Ultra 5, Windows 11 Pro, PixelSense 13" tactile, Wi-Fi 7.',1599,1799,3,20,4.6,89,'📟','Pro'),
        (13,'Sony WH-1000XM5','ANC leader, 8 microphones, 30 h autonomie, Hi-Res Audio.',349,399,4,90,4.9,892,'🎧','Bestseller'),
        (14,'AirPods Pro 2ème génération','Puce H2, ANC adaptatif, audio spatial, IP54, boîtier MagSafe.',279,299,4,200,4.8,654,'🎧',None),
        (15,'Bose QuietComfort Ultra','ANC ultra-efficace, confort légendaire, audio spatial, 24 h.',429,449,4,45,4.8,234,'🎧','Premium'),
        (16,'JBL Tour Pro 3','Écran tactile sur boîtier, True Adaptive ANC, 44 h autonomie.',199,229,4,75,4.5,123,'🎧',None),
        (17,'PS5 Slim Disc 1 To','GPU AMD RDNA 2, ray-tracing, 4K 120 fps, DualSense haptique.',499,549,5,15,4.9,1203,'🎮','Hot'),
        (18,'Xbox Series X 1 To','QuickResume, Game Pass Ultimate, 4K 120 fps, rétro-compat totale.',499,None,5,20,4.8,876,'🎮',None),
        (19,'Nintendo Switch OLED','Écran OLED 7", station TV HD, Joy-Con détachables, 64 Go.',349,None,5,55,4.7,987,'🎮',None),
        (20,'ASUS ROG Ally X','AMD Ryzen Z1 Extreme, 24 Go LPDDR5, SSD 1 To, 7" FHD 120 Hz.',799,899,5,18,4.5,234,'🎮','New'),
        (21,'LG OLED 65" evo C4 4K','OLED evo α9 Gen7, 120 Hz natif, G-Sync, Dolby Vision IQ.',1899,2199,6,12,4.9,567,'📺','Bestseller'),
        (22,'LG UltraWide 34" QHD','IPS 144 Hz, G-Sync, HDR400, USB-C 65 W, courbe 1800R.',699,799,6,35,4.7,289,'📺',None),
        (23,'Sony Alpha A7 IV','Capteur full-frame 33 MP, 4K 60 fps 10-bit, IBIS 5 axes.',2799,2999,7,8,4.9,312,'📷','Pro'),
        (24,'GoPro Hero 12 Black','5.3K 60 fps, HyperSmooth 6.0, étanche 10 m, TimeWarp 3.0.',399,449,7,65,4.6,456,'📷',None),
        (25,'Apple Watch Series 9 45mm','Puce S9, Always-On Retina, Double Tap, ECG, SpO2, GPS.',429,449,8,80,4.8,678,'⌚',None),
        (26,'Samsung Galaxy Watch 7 47mm','Exynos W1000 3 nm, BioActive Sensor, ECG, coaching IA.',329,349,8,65,4.6,345,'⌚',None),
        (27,'Garmin Fenix 7X Solar Pro','GPS multi-bande, cartographie topo, 100 m, 37 jours autonomie.',899,999,8,20,4.8,189,'⌚','Pro'),
        (28,'Logitech MX Master 3S','MagSpeed 8 000 DPI, USB-C, multi-device 3 appareils.',99,119,9,150,4.8,789,'🖱️','Bestseller'),
        (29,'Keychron K2 Pro Mécanique','Switch Gateron hot-swap, QMK/VIA, triple mode, rétroéclairage RVB.',119,139,9,85,4.7,456,'⌨️',None),
        (30,'Anker 778 USB-C Hub 12-en-1','4K HDMI, 10 Gbps USB, charge 85 W, SD/MicroSD, Ethernet.',79,99,9,200,4.6,567,'🔌',None),
    ]
    for p in products:
        c.execute('INSERT INTO products(id,name,description,price,old_price,category_id,stock,rating,review_count,icon,badge) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(id) DO NOTHING', p)
    c.execute("SELECT SETVAL('products_id_seq',30,true)")

    users = [
        (1,'admin','admin@techmart.com','Admin@1234','admin','0600000001','1 rue Admin, 75001 Paris'),
        (2,'alice','alice@example.com','alice123','user','0601020304','15 rue de la Paix, 69001 Lyon'),
        (3,'bob','bob@example.com','bob456','user','0607080910','8 avenue des Fleurs, 13001 Marseille'),
        (4,'charlie','charlie@example.com','charlie789','user','0611223344','42 bd Victor Hugo, 33000 Bordeaux'),
        (5,'test','test@techmart.com','test','user','',''),
    ]
    for u in users:
        c.execute('INSERT INTO users(id,username,email,password,role,phone,address) VALUES(%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(id) DO NOTHING', u)
    c.execute("SELECT SETVAL('users_id_seq',5,true)")

    for cp in [(1,'PROMO10',10,1),(2,'SAVE20',20,1),(3,'ADMIN50',50,0),(4,'TECHMART',15,1)]:
        c.execute('INSERT INTO coupons(id,code,discount,active) VALUES(%s,%s,%s,%s) ON CONFLICT(id) DO NOTHING', cp)
    c.execute("SELECT SETVAL('coupons_id_seq',4,true)")

    for s in [(1,'FLAG','FLAG{techmart_sqli_union_pwned_2024}'),(2,'DB_PASSWORD','sup3r_s3cr3t_db_p@ss!'),(3,'API_KEY','sk_live_TechMart_47f8a2c91b3d'),(4,'ADMIN_JWT','eyJhbGciOiJIUzI1NiJ9.YWRtaW4.s3cr3t'),(5,'SMTP_PASS','TechMart_Mail_2024!')]:
        c.execute('INSERT INTO secret_data(id,label,value) VALUES(%s,%s,%s) ON CONFLICT(id) DO NOTHING', s)

    for uid, bal in [(1,150.0),(2,80.0),(3,45.0),(4,120.0),(5,0.0)]:
        c.execute('INSERT INTO virtual_wallet(user_id,balance) VALUES(%s,%s) ON CONFLICT(user_id) DO NOTHING', (uid, bal))

    orders_seed = [
        (1,2,3299.0,'delivered','15 rue de la Paix, 69001 Lyon','card','TM-2024-AA0001','2024-01-15'),
        (2,3,628.0,'shipped','8 avenue des Fleurs, 13001 Marseille','card','TM-2024-AA0002','2024-02-01'),
        (3,4,499.0,'processing','42 bd Victor Hugo, 33000 Bordeaux','techcoins','TM-2024-AA0003','2024-02-20'),
        (4,2,1578.0,'delivered','15 rue de la Paix, 69001 Lyon','card','TM-2024-AA0004','2024-03-05'),
    ]
    for o in orders_seed:
        c.execute('INSERT INTO orders(id,user_id,total,status,shipping_address,payment_method,order_number,created_at) VALUES(%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(id) DO NOTHING', o)
    c.execute("SELECT SETVAL('orders_id_seq',4,true)")

    for oi in [(1,1,1,1,3299.0),(2,2,13,1,349.0),(3,2,28,1,99.0),(4,2,30,1,79.0),(5,3,17,1,499.0),(6,4,6,1,1299.0),(7,4,14,1,279.0)]:
        c.execute('INSERT INTO order_items VALUES(%s,%s,%s,%s,%s) ON CONFLICT(id) DO NOTHING', oi)
    c.execute("SELECT SETVAL('order_items_id_seq',7,true)")

    reviews_data = [
        (1,1,2,'alice',5,'Performance incroyable !','La puce M3 Max surpasse tout. Montage 4K en temps réel. Parfait !','2024-01-15'),
        (2,1,3,'bob',4,'Excellent mais prix élevé','Performances top, écran magnifique. Le rapport qualité/prix reste discutable.','2024-01-20'),
        (3,6,2,'alice',5,'Titanium + USB-C enfin !','Appareil photo révolutionnaire. USB-C attendu depuis longtemps.','2024-02-01'),
        (4,13,4,'charlie',5,'Meilleur casque de ma vie',"L'ANC est impressionnant. Confort parfait même après 8h.",'2024-02-10'),
        (5,17,3,'bob',5,'PS5 indispensable','Les temps de chargement sont bluffants. DualSense haptique exceptionnel.','2024-02-15'),
        (6,28,4,'charlie',4,'Excellente souris','MagSpeed addictif. Multi-device parfait.','2024-03-01'),
    ]
    for r in reviews_data:
        c.execute('INSERT INTO reviews(id,product_id,user_id,username,rating,title,content,created_at) VALUES(%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(id) DO NOTHING', r)

    # Fix all sequences to avoid PK conflicts on INSERT
    for tbl in ['users','categories','products','orders','order_items','reviews','coupons','secret_data','virtual_wallet','password_resets']:
        c.execute(f"SELECT SETVAL('{tbl}_id_seq', COALESCE((SELECT MAX(id) FROM {tbl}), 1), true)")

    conn.commit(); conn.close()
    print("[DB] Initialisation terminée.")


# ── Context / Decorators ────────────────────────────────────
@app.context_processor
def inject_globals():
    conn = get_db(); c = conn.cursor()
    c.execute('SELECT * FROM categories ORDER BY id')
    categories = c.fetchall(); conn.close()
    cart = session.get('cart', {})
    cart_count = sum(cart.values()) if cart else 0
    wallet_balance = None
    if session.get('user_id'):
        try:
            conn2 = get_db(); c2 = conn2.cursor()
            c2.execute('SELECT balance FROM virtual_wallet WHERE user_id=%s', (session['user_id'],))
            row = c2.fetchone(); conn2.close()
            wallet_balance = float(row['balance']) if row else 0.0
        except Exception:
            wallet_balance = 0.0
    return dict(g_categories=categories, cart_count=cart_count,
                current_user=session.get('user'), current_user_id=session.get('user_id'),
                current_role=session.get('role'), coupon_msg=session.pop('coupon_msg', None),
                wallet_balance=wallet_balance)


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('role') != 'admin': return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user'): return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


# ── Routes ──────────────────────────────────────────────────
@app.route('/')
def home():
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT p.*,ca.name as cat_name,ca.color as cat_color FROM products p JOIN categories ca ON p.category_id=ca.id WHERE p.badge IS NOT NULL LIMIT 8")
    featured = c.fetchall()
    c.execute("SELECT p.*,ca.name as cat_name,ca.color as cat_color FROM products p JOIN categories ca ON p.category_id=ca.id ORDER BY p.review_count DESC LIMIT 6")
    bestsellers = c.fetchall()
    c.execute("SELECT p.*,ca.name as cat_name,ca.color as cat_color FROM products p JOIN categories ca ON p.category_id=ca.id WHERE p.old_price IS NOT NULL ORDER BY (p.old_price-p.price) DESC LIMIT 4")
    promo = c.fetchall(); conn.close()
    return render_template('home.html', featured=featured, bestsellers=bestsellers, promo=promo)


@app.route('/products')
def products():
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT p.*,ca.name as cat_name,ca.color as cat_color FROM products p JOIN categories ca ON p.category_id=ca.id ORDER BY p.id")
    all_products = c.fetchall(); conn.close()
    return render_template('products.html', products=all_products)


@app.route('/product/<product_id>')
def product_detail(product_id):
    conn = get_db(); c = conn.cursor()
    product = None
    try:
        c.execute(f"SELECT p.*,ca.name as cat_name,ca.color as cat_color FROM products p JOIN categories ca ON p.category_id=ca.id WHERE p.id={product_id}")
        product = c.fetchone()
    except Exception:
        pass
    reviews = []; related = []
    if product:
        c.execute("SELECT * FROM reviews WHERE product_id=%s ORDER BY created_at DESC", (product['id'],))
        reviews = c.fetchall()
        c.execute(f"SELECT p.*,ca.name as cat_name,ca.color as cat_color FROM products p JOIN categories ca ON p.category_id=ca.id WHERE p.category_id={product['category_id']} AND p.id!={product['id']} LIMIT 4")
        related = c.fetchall()
    conn.close()
    return render_template('product.html', product=product, reviews=reviews, related=related)


@app.route('/product/<int:product_id>/review', methods=['POST'])
@login_required
def add_review(product_id):
    conn = get_db(); c = conn.cursor()
    c.execute("INSERT INTO reviews(product_id,user_id,username,rating,title,content) VALUES(%s,%s,%s,%s,%s,%s)",
              (product_id, session.get('user_id',0), session.get('user'),
               request.form.get('rating','5'), request.form.get('title',''), request.form.get('content','')))
    conn.commit(); conn.close()
    return redirect(url_for('product_detail', product_id=product_id))


@app.route('/search')
def search():
    q = request.args.get('q',''); results = []; error = None
    if q:
        conn = get_db(); c = conn.cursor()
        try:
            c.execute(f"SELECT p.*,ca.name as cat_name,ca.color as cat_color FROM products p JOIN categories ca ON p.category_id=ca.id WHERE p.name ILIKE '%{q}%' OR p.description ILIKE '%{q}%'")
            results = c.fetchall()
        except Exception as e:
            error = str(e)
        finally:
            conn.close()
    return render_template('search.html', results=results, query=q, error=error)


@app.route('/category/<int:cat_id>')
def category(cat_id):
    sort = request.args.get('sort','popular')
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT * FROM categories WHERE id=%s",(cat_id,)); cat = c.fetchone()
    c.execute("SELECT p.*,ca.name as cat_name,ca.color as cat_color FROM products p JOIN categories ca ON p.category_id=ca.id WHERE p.category_id=%s",(cat_id,))
    cat_products = c.fetchall(); conn.close()
    return render_template('category.html', category=cat, products=cat_products, sort=sort)


@app.route('/cart')
def cart():
    cart_data = session.get('cart',{}); items=[]; total=0
    if cart_data:
        conn=get_db(); c=conn.cursor()
        for pid,qty in cart_data.items():
            c.execute("SELECT * FROM products WHERE id=%s",(int(pid),)); p=c.fetchone()
            if p:
                sub=float(p['price'])*qty; items.append({'product':p,'qty':qty,'subtotal':sub}); total+=sub
        conn.close()
    discount=session.get('discount',0); final=total*(1-discount/100)
    return render_template('cart.html', items=items, total=total, discount=discount, final_total=final)


@app.route('/cart/add', methods=['POST'])
def cart_add():
    pid=str(request.form.get('product_id','')); qty=int(request.form.get('qty',1))
    if pid:
        cart=session.get('cart',{}); cart[pid]=cart.get(pid,0)+qty; session['cart']=cart
    return redirect(request.referrer or url_for('cart'))


@app.route('/cart/remove', methods=['POST'])
def cart_remove():
    pid=str(request.form.get('product_id',''))
    cart=session.get('cart',{}); cart.pop(pid,None); session['cart']=cart
    return redirect(url_for('cart'))


@app.route('/cart/coupon', methods=['POST'])
def apply_coupon():
    code=request.form.get('code','')
    conn=get_db(); c=conn.cursor()
    try:
        c.execute(f"SELECT * FROM coupons WHERE code='{code}' AND active=1"); coupon=c.fetchone()
        if coupon:
            session['coupon_msg']=f"✅ Code « {coupon['code']} » appliqué ! -{coupon['discount']}%"
            session['discount']=coupon['discount']
        else:
            session['coupon_msg']="❌ Code promotionnel invalide."
    except Exception:
        session['coupon_msg']="❌ Code promotionnel invalide."
    conn.close()
    return redirect(url_for('cart'))


@app.route('/checkout', methods=['GET','POST'])
@login_required
def checkout():
    def compute_totals(total, discount):
        after_disc = total * (1 - discount / 100)
        shipping = 0 if after_disc >= 50 else 5.99
        tva = after_disc * 0.20
        final = after_disc + shipping + tva
        return after_disc, shipping, tva, final

    if request.method == 'POST':
        cart_data = session.get('cart', {})
        if not cart_data: return redirect(url_for('cart'))
        conn = get_db(); c = conn.cursor()
        total = 0; items_details = []
        for pid, qty in cart_data.items():
            c.execute("SELECT * FROM products WHERE id=%s",(int(pid),)); p = c.fetchone()
            if p:
                sub = float(p['price']) * qty; total += sub
                items_details.append({'product': p, 'qty': qty, 'subtotal': sub})
        discount = session.get('discount', 0)
        after_disc, shipping, tva, final_total = compute_totals(total, discount)
        payment_method = request.form.get('payment_method','card')
        address = request.form.get('address','')

        def render_error(msg):
            conn.close()
            return render_template('checkout.html', items=items_details, total=total,
                                   discount=discount, final_total=final_total,
                                   shipping=shipping, tva=tva,
                                   subtotal_after_discount=after_disc,
                                   user_address=address, error=msg)

        if payment_method == 'card':
            cn = request.form.get('card_number','').replace(' ','').replace('-','')
            exp = request.form.get('card_expiry','')
            cvv = request.form.get('card_cvv','')
            if cn != VALID_CARD['number']:
                return render_error("Carte refusée. Vérifiez vos informations bancaires.")
            if exp != VALID_CARD['expiry']:
                return render_error("Date d'expiration invalide.")
            if cvv != VALID_CARD['cvv']:
                return render_error("Code CVV invalide.")

        elif payment_method == 'techcoins':
            c.execute("SELECT balance FROM virtual_wallet WHERE user_id=%s",(session['user_id'],))
            row = c.fetchone(); balance = float(row['balance']) if row else 0.0
            if balance < final_total:
                return render_error(f"Solde TechCoins insuffisant ({balance:.2f} TC disponibles, {final_total:.2f} TC requis).")

        # Vérification stock disponible
        stock_error = None
        conn2 = get_db(); c2 = conn2.cursor()
        for pid, qty in cart_data.items():
            c2.execute("SELECT name, stock FROM products WHERE id=%s", (int(pid),))
            p2 = c2.fetchone()
            if p2 and p2['stock'] < qty:
                stock_error = f"Stock insuffisant pour « {p2['name']} » ({p2['stock']} disponibles, {qty} demandés)."
                break
        conn2.close()
        if stock_error:
            conn.close()
            return render_template('checkout.html', items=items_details, total=total,
                                   discount=discount, final_total=final_total,
                                   shipping=shipping, tva=tva,
                                   subtotal_after_discount=after_disc,
                                   user_address=address, error=stock_error)

        order_number = gen_order_number()
        c.execute('INSERT INTO orders(user_id,total,status,shipping_address,payment_method,order_number) VALUES(%s,%s,%s,%s,%s,%s) RETURNING id',
                  (session['user_id'], round(final_total,2), 'processing', address, payment_method, order_number))
        oid = c.fetchone()['id']
        for pid, qty in cart_data.items():
            c.execute("SELECT price,stock FROM products WHERE id=%s",(int(pid),)); p = c.fetchone()
            if p:
                c.execute("INSERT INTO order_items(order_id,product_id,quantity,price) VALUES(%s,%s,%s,%s)",(oid,int(pid),qty,float(p['price'])))
                c.execute("UPDATE products SET stock=GREATEST(0,stock-%s) WHERE id=%s",(qty,int(pid)))
        if payment_method == 'techcoins':
            c.execute("UPDATE virtual_wallet SET balance=balance-%s WHERE user_id=%s",(round(final_total,2),session['user_id']))
        conn.commit(); conn.close()
        session.pop('cart',None); session.pop('discount',None)
        return redirect(url_for('order_detail', order_id=oid))

    cart_data=session.get('cart',{}); items=[]; total=0
    if cart_data:
        conn=get_db(); c=conn.cursor()
        for pid,qty in cart_data.items():
            c.execute("SELECT * FROM products WHERE id=%s",(int(pid),)); p=c.fetchone()
            if p:
                sub=float(p['price'])*qty; items.append({'product':p,'qty':qty,'subtotal':sub}); total+=sub
        conn.close()
    discount=session.get('discount',0)
    after_disc,shipping,tva,final_total=compute_totals(total,discount)
    ua=''
    if session.get('user_id'):
        conn=get_db(); c=conn.cursor()
        c.execute("SELECT address FROM users WHERE id=%s",(session['user_id'],)); u=c.fetchone(); conn.close()
        if u: ua=u['address']
    return render_template('checkout.html', items=items, total=total, discount=discount,
                           final_total=final_total, shipping=shipping, tva=tva,
                           subtotal_after_discount=after_disc, user_address=ua, error=None)


@app.route('/wallet')
@login_required
def wallet():
    conn=get_db(); c=conn.cursor()
    c.execute("SELECT balance FROM virtual_wallet WHERE user_id=%s",(session['user_id'],))
    row=c.fetchone(); balance=float(row['balance']) if row else 0.0; conn.close()
    return render_template('wallet.html', balance=balance, tc_rate=TC_RATE)


@app.route('/wallet/buy', methods=['POST'])
@login_required
def wallet_buy():
    error=None; success=None
    try:
        amount=float(request.form.get('amount','0'))
        cn=request.form.get('card_number','').replace(' ','').replace('-','')
        exp=request.form.get('card_expiry','')
        cvv=request.form.get('card_cvv','')
        if amount<10 or amount>500:
            error="Montant invalide. Minimum 10 TC, maximum 500 TC."
        elif cn!=VALID_CARD['number']: error="Carte refusée. Numéro invalide."
        elif exp!=VALID_CARD['expiry']: error="Date d'expiration invalide."
        elif cvv!=VALID_CARD['cvv']: error="CVV invalide."
        else:
            conn=get_db(); c=conn.cursor()
            c.execute("UPDATE virtual_wallet SET balance=balance+%s WHERE user_id=%s",(amount,session['user_id']))
            c.execute("SELECT balance FROM virtual_wallet WHERE user_id=%s",(session['user_id'],))
            new_bal=float(c.fetchone()['balance']); conn.commit(); conn.close()
            success=f"✅ {amount:.0f} TechCoins crédités avec succès ! Nouveau solde : {new_bal:.2f} TC"
    except ValueError:
        error="Montant invalide."
    conn=get_db(); c=conn.cursor()
    c.execute("SELECT balance FROM virtual_wallet WHERE user_id=%s",(session['user_id'],))
    row=c.fetchone(); balance=float(row['balance']) if row else 0.0; conn.close()
    return render_template('wallet.html', balance=balance, tc_rate=TC_RATE, error=error, success=success)


@app.route('/orders')
@login_required
def orders():
    conn=get_db(); c=conn.cursor()
    c.execute("SELECT * FROM orders WHERE user_id=%s ORDER BY created_at DESC",(session['user_id'],))
    user_orders=c.fetchall(); conn.close()
    return render_template('orders.html', orders=user_orders)


@app.route('/orders/<int:order_id>')
@login_required
def order_detail(order_id):
    conn=get_db(); c=conn.cursor()
    c.execute("SELECT o.*,u.username FROM orders o JOIN users u ON o.user_id=u.id WHERE o.id=%s",(order_id,))
    order=c.fetchone(); items=[]
    if order:
        c.execute("SELECT oi.*,p.name,p.icon FROM order_items oi JOIN products p ON oi.product_id=p.id WHERE oi.order_id=%s",(order_id,))
        items=c.fetchall()
    conn.close()
    is_own=order and order['user_id']==session.get('user_id')
    return render_template('order_detail.html', order=order, items=items, is_own=is_own)


@app.route('/login', methods=['GET','POST'])
def login():
    error=None
    if request.method=='POST':
        username=request.form.get('username',''); password=request.form.get('password','')
        conn=get_db(); c=conn.cursor()
        try:
            c.execute(f"SELECT * FROM users WHERE username='{username}' AND password='{password}'")
            user=c.fetchone()
        except Exception:
            conn.close(); error="Identifiants incorrects."; return render_template('login.html',error=error)
        conn.close()
        if user:
            session['user']=user['username']; session['user_id']=user['id']; session['role']=user['role']
            return redirect(url_for('home'))
        error="Identifiants incorrects."
    return render_template('login.html', error=error)


@app.route('/register', methods=['GET','POST'])
def register():
    error=None
    if request.method=='POST':
        username=request.form.get('username','').strip()
        email=request.form.get('email','').strip()
        password=request.form.get('password','')
        confirm=request.form.get('confirm_password','')
        if password!=confirm:
            return render_template('register.html', error="Les mots de passe ne correspondent pas.")
        conn=get_db(); c=conn.cursor()
        try:
            c.execute("INSERT INTO users(username,email,password) VALUES(%s,%s,%s) RETURNING id",(username,email,password))
            uid=c.fetchone()['id']
            c.execute("INSERT INTO virtual_wallet(user_id,balance) VALUES(%s,0.00)",(uid,))
            conn.commit(); conn.close(); return redirect(url_for('login'))
        except Exception:
            conn.close(); error="Nom d'utilisateur ou email déjà utilisé."
    return render_template('register.html', error=error)


@app.route('/logout')
def logout():
    session.clear(); return redirect(url_for('home'))


@app.route('/profile', methods=['GET','POST'])
@login_required
def profile():
    tab=request.args.get('tab','info'); msg=None
    if request.method=='POST':
        conn=get_db(); c=conn.cursor()
        c.execute("UPDATE users SET phone=%s,address=%s WHERE id=%s",
                  (request.form.get('phone',''),request.form.get('address',''),session['user_id']))
        conn.commit(); conn.close(); msg="✅ Profil mis à jour."
    conn=get_db(); c=conn.cursor()
    c.execute("SELECT * FROM users WHERE id=%s",(session['user_id'],)); user=c.fetchone()
    c.execute("SELECT * FROM orders WHERE user_id=%s ORDER BY created_at DESC LIMIT 5",(session['user_id'],)); user_orders=c.fetchall()
    conn.close()
    return render_template('profile.html', user=user, user_orders=user_orders, tab=tab, msg=msg)




@app.route('/orders/<int:order_id>/cancel', methods=['POST'])
@login_required
def cancel_order(order_id):
    conn=get_db(); c=conn.cursor()
    c.execute("SELECT * FROM orders WHERE id=%s AND user_id=%s",(order_id,session['user_id']))
    order=c.fetchone()
    if not order:
        conn.close(); return redirect(url_for('orders'))
    if order['status'] not in ('pending','processing'):
        conn.close()
        return redirect(url_for('order_detail', order_id=order_id))
    # Rembourser TechCoins si applicable
    if order['payment_method']=='techcoins':
        c.execute("UPDATE virtual_wallet SET balance=balance+%s WHERE user_id=%s",(order['total'],session['user_id']))
    # Remettre le stock
    c.execute("SELECT product_id,quantity FROM order_items WHERE order_id=%s",(order_id,))
    for item in c.fetchall():
        c.execute("UPDATE products SET stock=stock+%s WHERE id=%s",(item['quantity'],item['product_id']))
    c.execute("UPDATE orders SET status='cancelled' WHERE id=%s",(order_id,))
    conn.commit(); conn.close()
    return redirect(url_for('order_detail', order_id=order_id))


@app.route('/profile/change-password', methods=['POST'])
@login_required
def change_password():
    current=request.form.get('current_password','')
    new_pwd=request.form.get('new_password','')
    confirm=request.form.get('confirm_password','')
    tab='security'
    conn=get_db(); c=conn.cursor()
    c.execute("SELECT * FROM users WHERE id=%s",(session['user_id'],)); user=c.fetchone()
    c.execute("SELECT * FROM orders WHERE user_id=%s ORDER BY created_at DESC LIMIT 5",(session['user_id'],))
    user_orders=c.fetchall()
    conn.close()
    if user['password']!=current:
        return render_template('profile.html', user=user, user_orders=user_orders, tab=tab,
                               msg=None, pwd_error="❌ Mot de passe actuel incorrect.")
    if len(new_pwd)<4:
        return render_template('profile.html', user=user, user_orders=user_orders, tab=tab,
                               msg=None, pwd_error="❌ Le nouveau mot de passe est trop court (4 caractères min).")
    if new_pwd!=confirm:
        return render_template('profile.html', user=user, user_orders=user_orders, tab=tab,
                               msg=None, pwd_error="❌ Les mots de passe ne correspondent pas.")
    conn=get_db(); c=conn.cursor()
    c.execute("UPDATE users SET password=%s WHERE id=%s",(new_pwd,session['user_id']))
    conn.commit(); conn.close()
    return render_template('profile.html', user=user, user_orders=user_orders, tab=tab,
                           msg="✅ Mot de passe modifié avec succès.", pwd_error=None)


@app.route('/forgot-password', methods=['GET','POST'])
def forgot_password():
    msg=None; reset_link=None; error=None
    if request.method=='POST':
        identifier=request.form.get('identifier','').strip()
        conn=get_db(); c=conn.cursor()
        c.execute("SELECT * FROM users WHERE username=%s OR email=%s",(identifier,identifier))
        user=c.fetchone()
        if user:
            import base64 as _b64, time as _t
            raw=f"{user['id']}:{user['username']}:{int(_t.time())}"
            token=_b64.urlsafe_b64encode(raw.encode()).decode()
            try:
                c.execute("DELETE FROM password_resets WHERE user_id=%s",(user['id'],))
                c.execute("INSERT INTO password_resets(user_id,token) VALUES(%s,%s)",(user['id'],token))
                conn.commit()
                reset_link=f"/reset-password/{token}"
                msg=f"Un lien de réinitialisation a été généré pour « {user['username']} »."
            except Exception:
                conn.rollback()
                error="Erreur lors de la génération du lien."
        else:
            msg="Si ce compte existe, un lien a été envoyé."
        conn.close()
    return render_template('forgot_password.html', msg=msg, reset_link=reset_link, error=error)


@app.route('/reset-password/<token>', methods=['GET','POST'])
def reset_password(token):
    conn=get_db(); c=conn.cursor()
    c.execute("SELECT pr.*,u.username FROM password_resets pr JOIN users u ON pr.user_id=u.id WHERE pr.token=%s AND pr.used=FALSE",(token,))
    reset=c.fetchone()
    conn.close()
    if not reset:
        return render_template('reset_password.html', token=token, error="Lien invalide ou expiré.", valid=False)
    # Vérifier expiration (15 minutes)
    from datetime import timezone
    delta=(datetime.now()-reset['created_at'].replace(tzinfo=None)).total_seconds()
    if delta>900:
        return render_template('reset_password.html', token=token, error="Ce lien a expiré (15 minutes). Faites une nouvelle demande.", valid=False)
    error=None; success=None
    if request.method=='POST':
        new_pwd=request.form.get('new_password','')
        confirm=request.form.get('confirm_password','')
        if len(new_pwd)<4:
            error="Mot de passe trop court (4 caractères min)."
        elif new_pwd!=confirm:
            error="Les mots de passe ne correspondent pas."
        else:
            conn=get_db(); c=conn.cursor()
            c.execute("UPDATE users SET password=%s WHERE id=%s",(new_pwd,reset['user_id']))
            c.execute("UPDATE password_resets SET used=TRUE WHERE token=%s",(token,))
            conn.commit(); conn.close()
            return render_template('reset_password.html', token=token, valid=True, done=True)
    return render_template('reset_password.html', token=token, valid=True, done=False,
                           username=reset['username'], error=error)

# ── Admin ────────────────────────────────────────────────────
@app.route('/admin')
@admin_required
def admin_dashboard():
    conn=get_db(); c=conn.cursor()
    c.execute("SELECT COUNT(*) as n FROM users"); u=c.fetchone()['n']
    c.execute("SELECT COUNT(*) as n FROM products"); p=c.fetchone()['n']
    c.execute("SELECT COUNT(*) as n FROM orders"); o=c.fetchone()['n']
    c.execute("SELECT COALESCE(SUM(total),0) as n FROM orders WHERE status='delivered'"); r=float(c.fetchone()['n'])
    stats={'users':u,'products':p,'orders':o,'revenue':r}
    c.execute("SELECT o.*,u.username FROM orders o JOIN users u ON o.user_id=u.id ORDER BY o.created_at DESC LIMIT 10"); recent_orders=c.fetchall()
    c.execute("SELECT name,icon,price,review_count FROM products ORDER BY review_count DESC LIMIT 5"); top_products=c.fetchall()
    conn.close()
    return render_template('admin/dashboard.html', stats=stats, recent_orders=recent_orders, top_products=top_products)


@app.route('/admin/products')
@admin_required
def admin_products():
    conn=get_db(); c=conn.cursor()
    c.execute("SELECT p.*,ca.name as cat_name FROM products p JOIN categories ca ON p.category_id=ca.id ORDER BY p.id")
    prods=c.fetchall(); conn.close()
    return render_template('admin/products.html', products=prods)


@app.route('/admin/orders')
@admin_required
def admin_orders():
    conn=get_db(); c=conn.cursor()
    c.execute("SELECT o.*,u.username FROM orders o JOIN users u ON o.user_id=u.id ORDER BY o.created_at DESC")
    all_orders=c.fetchall(); conn.close()
    return render_template('admin/orders.html', orders=all_orders)


@app.route('/admin/users')
@admin_required
def admin_users():
    conn=get_db(); c=conn.cursor()
    c.execute("SELECT * FROM users ORDER BY id"); users=c.fetchall(); conn.close()
    return render_template('admin/users.html', users=users)


@app.route('/admin/user/<int:uid>/delete', methods=['POST'])
@admin_required
def admin_delete_user(uid):
    if uid==1: return redirect(url_for('admin_users'))
    conn=get_db(); c=conn.cursor()
    c.execute("DELETE FROM users WHERE id=%s",(uid,)); conn.commit(); conn.close()
    return redirect(url_for('admin_users'))


@app.route('/admin/order/<int:oid>/status', methods=['POST'])
@admin_required
def admin_update_order(oid):
    conn=get_db(); c=conn.cursor()
    c.execute("UPDATE orders SET status=%s WHERE id=%s",(request.form.get('status','processing'),oid))
    conn.commit(); conn.close()
    return redirect(url_for('admin_orders'))


# ── API v1 ───────────────────────────────────────────────────
@app.route('/api/v1/auth/login', methods=['POST'])
def api_login():
    data=request.get_json(silent=True) or {}
    username=data.get('username',''); password=data.get('password','')
    conn=get_db(); c=conn.cursor()
    try:
        c.execute(f"SELECT * FROM users WHERE username='{username}' AND password='{password}'")
        user=c.fetchone()
    except Exception as e:
        conn.close(); return jsonify({'error':str(e)}),400
    conn.close()
    if not user: return jsonify({'error':'Invalid credentials'}),401
    return jsonify({'token':gen_api_token(user['id'],user['role']),'user_id':user['id'],'username':user['username'],'role':user['role']})


@app.route('/api/v1/products', methods=['GET'])
def api_products():
    conn=get_db(); c=conn.cursor()
    c.execute("SELECT id,name,price,old_price,category_id,stock,rating,icon,badge FROM products ORDER BY id")
    items=c.fetchall(); conn.close()
    return jsonify([dict(i) for i in items])


@app.route('/api/v1/products/search', methods=['GET'])
def api_products_search():
    q=request.args.get('q','')
    conn=get_db(); c=conn.cursor()
    try:
        c.execute(f"SELECT id,name,description,price,icon FROM products WHERE name ILIKE '%{q}%' OR description ILIKE '%{q}%'")
        results=c.fetchall()
    except Exception as e:
        conn.close(); return jsonify({'error':str(e)}),400
    conn.close()
    return jsonify([dict(r) for r in results])


@app.route('/api/v1/orders', methods=['GET'])
@api_auth_required
def api_orders():
    conn=get_db(); c=conn.cursor()
    c.execute("SELECT * FROM orders WHERE user_id=%s ORDER BY created_at DESC",(request.api_user_id,))
    items=c.fetchall(); conn.close()
    return jsonify([dict(i) for i in items])


# IDOR : aucune vérification de propriété
@app.route('/api/v1/orders/<int:order_id>', methods=['GET'])
@api_auth_required
def api_order_detail(order_id):
    conn=get_db(); c=conn.cursor()
    c.execute("SELECT o.*,u.username FROM orders o JOIN users u ON o.user_id=u.id WHERE o.id=%s",(order_id,))
    order=c.fetchone()
    if not order: conn.close(); return jsonify({'error':'Not found'}),404
    c.execute("SELECT oi.*,p.name FROM order_items oi JOIN products p ON oi.product_id=p.id WHERE oi.order_id=%s",(order_id,))
    items=c.fetchall(); conn.close()
    return jsonify({'order':dict(order),'items':[dict(i) for i in items]})


@app.route('/api/v1/wallet/balance', methods=['GET'])
@api_auth_required
def api_wallet_balance():
    conn=get_db(); c=conn.cursor()
    c.execute("SELECT balance FROM virtual_wallet WHERE user_id=%s",(request.api_user_id,))
    row=c.fetchone(); conn.close()
    return jsonify({'user_id':request.api_user_id,'balance':float(row['balance']) if row else 0.0,'currency':'TC'})


@app.route('/api/v1/wallet/balance-web', methods=['GET'])
def api_wallet_balance_web():
    if not session.get('user_id'): return jsonify({'balance':0}),401
    conn=get_db(); c=conn.cursor()
    c.execute("SELECT balance FROM virtual_wallet WHERE user_id=%s",(session['user_id'],))
    row=c.fetchone(); conn.close()
    return jsonify({'balance':float(row['balance']) if row else 0.0})


if __name__=='__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)
