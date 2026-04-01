"""
TechMart — Application E-commerce VOLONTAIREMENT VULNÉRABLE
Vulnérabilités : SQLi (Bypass, UNION), XSS (Réfléchi, Stocké, DOM),
                 CSRF, IDOR, Auth (plain-text passwords, no rate-limit)
Usage : Démonstration pédagogique UNIQUEMENT
NE PAS déployer en production
"""

from flask import (Flask, request, render_template, redirect,
                   url_for, session)
from functools import wraps
import sqlite3, os

from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)
app.secret_key = 'techmart_w3ak_s3cr3t_2024'
DB_PATH = '/app/data/techmart.db'

app.wsgi_app = ProxyFix(app.wsgi_app, x_prefix=1)
app.config['APPLICATION_ROOT'] = '/secureblog'


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    os.makedirs('/app/data', exist_ok=True)
    conn = get_db()
    c = conn.cursor()
    c.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL, password TEXT NOT NULL,
            role TEXT DEFAULT "user", phone TEXT DEFAULT "",
            address TEXT DEFAULT "", created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY, name TEXT NOT NULL, icon TEXT, color TEXT);
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY, name TEXT NOT NULL, description TEXT,
            price REAL NOT NULL, old_price REAL, category_id INTEGER,
            stock INTEGER DEFAULT 100, rating REAL DEFAULT 4.5,
            review_count INTEGER DEFAULT 0, icon TEXT, badge TEXT,
            FOREIGN KEY (category_id) REFERENCES categories(id));
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY, user_id INTEGER, total REAL,
            status TEXT DEFAULT "pending", shipping_address TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id));
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY, order_id INTEGER, product_id INTEGER,
            quantity INTEGER, price REAL,
            FOREIGN KEY (order_id) REFERENCES orders(id),
            FOREIGN KEY (product_id) REFERENCES products(id));
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY, product_id INTEGER, user_id INTEGER,
            username TEXT, rating INTEGER, title TEXT, content TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS coupons (
            id INTEGER PRIMARY KEY, code TEXT UNIQUE, discount INTEGER, active INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS secret_data (
            id INTEGER PRIMARY KEY, label TEXT, value TEXT);
    ''')

    cats = [(1,'Laptops','💻','#4A90E2'),(2,'Smartphones','📱','#7B68EE'),
            (3,'Tablets','📟','#50C878'),(4,'Audio','🎧','#FF6B6B'),
            (5,'Gaming','🎮','#F6AD55'),(6,'TV & Displays','📺','#20B2AA'),
            (7,'Cameras','📷','#FF8C69'),(8,'Wearables','⌚','#DA70D6'),
            (9,'Accessories','🖱️','#68D391')]
    c.executemany('INSERT OR IGNORE INTO categories VALUES(?,?,?,?)', cats)

    products = [
        (1,'MacBook Pro 16" M3 Max','Puce M3 Max, 36 Go RAM unifiée, SSD 1 To, Liquid Retina XDR 16". Performance professionnelle ultime.',3299,3499,1,45,4.9,128,'💻','Bestseller'),
        (2,'Dell XPS 15 OLED','Intel Core i9-13900H, RTX 4070, écran OLED 3.5K, 32 Go DDR5. Le meilleur laptop Windows.',2199,2499,1,30,4.7,89,'💻',None),
        (3,'ASUS ROG Zephyrus G14','AMD Ryzen 9, RTX 4090, QHD+ 165 Hz MiniLED, 32 Go DDR5. La bête en format compact.',1999,2199,1,25,4.8,156,'💻','Gaming'),
        (4,'Lenovo ThinkPad X1 Carbon','Intel Core Ultra 7, 32 Go, SSD 1 To PCIe 4, OLED 14" 2.8K. Le business laptop de référence.',1899,2099,1,60,4.8,203,'💻','Pro'),
        (5,'HP Spectre x360 14"','Intel Evo, 16 Go, OLED 2.8K tactile, 2-en-1 convertible. Design premium aluminium.',1499,1699,1,40,4.6,67,'💻',None),
        (6,'iPhone 15 Pro Max 256 Go','Puce A17 Pro, titane, 48 MP ProRes, USB-C Thunderbolt. Le meilleur iPhone jamais créé.',1299,1399,2,120,4.9,512,'📱','Top'),
        (7,'Samsung Galaxy S24 Ultra','Snapdragon 8 Gen 3, S Pen intégré, 200 MP, 12 Go RAM, titane. Le champion Android.',1199,1299,2,85,4.8,389,'📱','Bestseller'),
        (8,'Google Pixel 9 Pro','Tensor G4, IA générative native, photo computationnelle, 7 ans de mises à jour Android.',1099,None,2,70,4.7,178,'📱','New'),
        (9,'OnePlus 12 5G','Snapdragon 8 Gen 3, charge SuperVOOC 100 W, triple caméra Hasselblad, 16 Go RAM.',799,899,2,55,4.5,134,'📱','Promo'),
        (10,'iPad Pro 13" M4','Puce M4, écran Ultra Retina XDR OLED, Wi-Fi 6E, Face ID, Apple Pencil Pro compatible.',1399,1499,3,35,4.9,245,'📟','New'),
        (11,'Samsung Galaxy Tab S9 Ultra','Snapdragon 8 Gen 2, écran 14.6" AMOLED 120 Hz, S Pen inclus, IP68, 12 Go RAM.',1099,1199,3,28,4.7,167,'📟',None),
        (12,'Microsoft Surface Pro 10','Intel Core Ultra 5, Windows 11 Pro, PixelSense 13" tactile, Wi-Fi 7. PC tablette ultime.',1599,1799,3,20,4.6,89,'📟','Pro'),
        (13,'Sony WH-1000XM5','ANC leader incontesté, 8 microphones, 30 h autonomie, charge 3 min = 3 h, Hi-Res Audio.',349,399,4,90,4.9,892,'🎧','Bestseller'),
        (14,'AirPods Pro 2ème génération','Puce H2, ANC adaptatif, audio spatial avec head tracking, IP54, boîtier MagSafe.',279,299,4,200,4.8,654,'🎧',None),
        (15,'Bose QuietComfort Ultra','Immersion CustomTune, ANC ultra-efficace, confort légendaire, audio spatial, 24 h.',429,449,4,45,4.8,234,'🎧','Premium'),
        (16,'JBL Tour Pro 3','Écran tactile sur boîtier, True Adaptive ANC, Hi-Res Audio, 44 h autonomie totale.',199,229,4,75,4.5,123,'🎧',None),
        (17,'PS5 Slim Disc 1 To','GPU AMD RDNA 2, SSD NVMe ultra-rapide, ray-tracing, 4K 120 fps, DualSense haptique.',499,549,5,15,4.9,1203,'🎮','Hot'),
        (18,'Xbox Series X 1 To','QuickResume, Game Pass Ultimate, 4K 120 fps, SSD Velocity Architecture, rétro-compat totale.',499,None,5,20,4.8,876,'🎮',None),
        (19,'Nintendo Switch OLED','Écran OLED 7", station TV HD, Joy-Con détachables, 64 Go, 9 h autonomie.',349,None,5,55,4.7,987,'🎮',None),
        (20,'ASUS ROG Ally X','AMD Ryzen Z1 Extreme, 24 Go LPDDR5, SSD 1 To, 7" FHD 120 Hz, Windows 11.',799,899,5,18,4.5,234,'🎮','New'),
        (21,'LG OLED 65" evo C4 4K','OLED evo α9 Gen7, 120 Hz natif, G-Sync, Dolby Vision IQ & Atmos, webOS 24.',1899,2199,6,12,4.9,567,'📺','Bestseller'),
        (22,'LG UltraWide 34" QHD','IPS 144 Hz, G-Sync, HDR400, USB-C 65 W, courbe 1800R, KVM intégré.',699,799,6,35,4.7,289,'📺',None),
        (23,'Sony Alpha A7 IV','Capteur full-frame 33 MP, 4K 60 fps 10-bit, IBIS 5 axes, double slot SD, AF IA temps réel.',2799,2999,7,8,4.9,312,'📷','Pro'),
        (24,'GoPro Hero 12 Black','5.3K 60 fps, HyperSmooth 6.0, étanche 10 m, TimeWarp 3.0, HDR, live streaming.',399,449,7,65,4.6,456,'📷',None),
        (25,'Apple Watch Series 9 45mm','Puce S9, Always-On Retina, Double Tap, ECG, SpO2, détection de chute, GPS.',429,449,8,80,4.8,678,'⌚',None),
        (26,'Samsung Galaxy Watch 7 47mm','Exynos W1000 3 nm, BioActive Sensor, ECG, coaching IA, 40 h autonomie, LTE.',329,349,8,65,4.6,345,'⌚',None),
        (27,'Garmin Fenix 7X Solar Pro','Recharge solaire, GPS multi-bande, cartographie topo, plongée 100 m, 37 jours autonomie.',899,999,8,20,4.8,189,'⌚','Pro'),
        (28,'Logitech MX Master 3S','MagSpeed 8 000 DPI, Quiet Click, USB-C, multi-device 3 appareils, compatible Mac & PC.',99,119,9,150,4.8,789,'🖱️','Bestseller'),
        (29,'Keychron K2 Pro Mécanique','Switch Gateron G Pro hot-swap, QMK/VIA, triple mode 2.4G/BT/USB, rétroéclairage RVB.',119,139,9,85,4.7,456,'⌨️',None),
        (30,'Anker 778 USB-C Hub 12-en-1','4K HDMI, DisplayPort, 10 Gbps USB, charge 85 W, SD/MicroSD 312 Mo/s, Ethernet.',79,99,9,200,4.6,567,'🔌',None),
    ]
    c.executemany('INSERT OR IGNORE INTO products VALUES(?,?,?,?,?,?,?,?,?,?,?)', products)

    c.execute("INSERT OR IGNORE INTO users VALUES(1,'admin','admin@techmart.com','Admin@1234','admin','0600000001','1 rue Admin, 75001 Paris',CURRENT_TIMESTAMP)")
    c.execute("INSERT OR IGNORE INTO users VALUES(2,'alice','alice@example.com','alice123','user','0601020304','15 rue de la Paix, 69001 Lyon',CURRENT_TIMESTAMP)")
    c.execute("INSERT OR IGNORE INTO users VALUES(3,'bob','bob@example.com','bob456','user','0607080910','8 avenue des Fleurs, 13001 Marseille',CURRENT_TIMESTAMP)")
    c.execute("INSERT OR IGNORE INTO users VALUES(4,'charlie','charlie@example.com','charlie789','user','0611223344','42 bd Victor Hugo, 33000 Bordeaux',CURRENT_TIMESTAMP)")

    c.execute("INSERT OR IGNORE INTO coupons VALUES(1,'PROMO10',10,1)")
    c.execute("INSERT OR IGNORE INTO coupons VALUES(2,'SAVE20',20,1)")
    c.execute("INSERT OR IGNORE INTO coupons VALUES(3,'ADMIN50',50,0)")
    c.execute("INSERT OR IGNORE INTO coupons VALUES(4,'TECHMART',15,1)")

    c.execute("INSERT OR IGNORE INTO secret_data VALUES(1,'FLAG','FLAG{techmart_sqli_union_pwned_2024}')")
    c.execute("INSERT OR IGNORE INTO secret_data VALUES(2,'DB_PASSWORD','sup3r_s3cr3t_db_p@ss!')")
    c.execute("INSERT OR IGNORE INTO secret_data VALUES(3,'STRIPE_KEY','sk_live_TechMart_47f8a2c91b3d')")
    c.execute("INSERT OR IGNORE INTO secret_data VALUES(4,'ADMIN_JWT','eyJhbGciOiJIUzI1NiJ9.YWRtaW4.s3cr3t')")
    c.execute("INSERT OR IGNORE INTO secret_data VALUES(5,'SMTP_PASS','TechMart_Mail_2024!')")

    reviews_data = [
        (1,1,2,'alice',5,'Performance incroyable !','La puce M3 Max surpasse tout. Montage 4K en temps réel, compilation instantanée. Parfait !','2024-01-15'),
        (2,1,3,'bob',4,'Excellent mais prix élevé','Performances top, écran magnifique. Le rapport qualité/prix reste discutable.','2024-01-20'),
        (3,6,2,'alice',5,'Titanium + USB-C enfin !','Appareil photo révolutionnaire. L USB-C était vraiment attendu depuis longtemps.','2024-02-01'),
        (4,13,4,'charlie',5,'Meilleur casque de ma vie',"L ANC est impressionnant, on n entend plus rien. Confort parfait même après 8h.",'2024-02-10'),
        (5,17,3,'bob',5,'PS5 indispensable','Les temps de chargement sont bluffants. Le DualSense haptique révolutionne le ressenti.','2024-02-15'),
        (6,28,4,'charlie',4,'Excellente souris','Le scroll MagSpeed est addictif. Multi-device entre Mac et PC parfait.','2024-03-01'),
    ]
    c.executemany('INSERT OR IGNORE INTO reviews VALUES(?,?,?,?,?,?,?,?)', reviews_data)

    c.execute("INSERT OR IGNORE INTO orders VALUES(1,2,3299.0,'delivered','15 rue de la Paix, 69001 Lyon','2024-01-15')")
    c.execute("INSERT OR IGNORE INTO orders VALUES(2,3,628.0,'shipped','8 avenue des Fleurs, 13001 Marseille','2024-02-01')")
    c.execute("INSERT OR IGNORE INTO orders VALUES(3,4,499.0,'processing','42 bd Victor Hugo, 33000 Bordeaux','2024-02-20')")
    c.execute("INSERT OR IGNORE INTO orders VALUES(4,2,1578.0,'delivered','15 rue de la Paix, 69001 Lyon','2024-03-05')")
    c.execute("INSERT OR IGNORE INTO order_items VALUES(1,1,1,1,3299.0)")
    c.execute("INSERT OR IGNORE INTO order_items VALUES(2,2,13,1,349.0)")
    c.execute("INSERT OR IGNORE INTO order_items VALUES(3,2,28,1,99.0)")
    c.execute("INSERT OR IGNORE INTO order_items VALUES(4,2,30,1,79.0)")
    c.execute("INSERT OR IGNORE INTO order_items VALUES(5,3,17,1,499.0)")
    c.execute("INSERT OR IGNORE INTO order_items VALUES(6,4,6,1,1299.0)")
    c.execute("INSERT OR IGNORE INTO order_items VALUES(7,4,14,1,279.0)")

    conn.commit()
    conn.close()


@app.context_processor
def inject_globals():
    conn = get_db()
    categories = conn.execute('SELECT * FROM categories ORDER BY id').fetchall()
    conn.close()
    cart = session.get('cart', {})
    cart_count = sum(cart.values()) if cart else 0
    return dict(g_categories=categories, cart_count=cart_count,
                current_user=session.get('user'), current_user_id=session.get('user_id'),
                current_role=session.get('role'), coupon_msg=session.pop('coupon_msg', None))


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('role') != 'admin':
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


@app.route('/')
def home():
    conn = get_db()
    featured    = conn.execute("SELECT p.*,c.name as cat_name,c.color as cat_color FROM products p JOIN categories c ON p.category_id=c.id WHERE p.badge IS NOT NULL LIMIT 8").fetchall()
    bestsellers = conn.execute("SELECT p.*,c.name as cat_name,c.color as cat_color FROM products p JOIN categories c ON p.category_id=c.id ORDER BY p.review_count DESC LIMIT 6").fetchall()
    promo       = conn.execute("SELECT p.*,c.name as cat_name,c.color as cat_color FROM products p JOIN categories c ON p.category_id=c.id WHERE p.old_price IS NOT NULL ORDER BY (p.old_price-p.price) DESC LIMIT 4").fetchall()
    conn.close()
    return render_template('home.html', featured=featured, bestsellers=bestsellers, promo=promo)


@app.route('/products')
def products():
    conn = get_db()
    all_products = conn.execute("SELECT p.*,c.name as cat_name,c.color as cat_color FROM products p JOIN categories c ON p.category_id=c.id ORDER BY p.id").fetchall()
    conn.close()
    return render_template('products.html', products=all_products)


# ⚠️ SQLi sur l'ID produit
@app.route('/product/<product_id>')
def product_detail(product_id):
    conn = get_db()
    product = None; sql_error = None
    try:
        product = conn.execute(f"SELECT p.*,c.name as cat_name,c.color as cat_color FROM products p JOIN categories c ON p.category_id=c.id WHERE p.id={product_id}").fetchone()
    except Exception as e:
        sql_error = str(e)
    reviews = []; related = []
    if product:
        reviews = conn.execute("SELECT * FROM reviews WHERE product_id=? ORDER BY created_at DESC",(product['id'],)).fetchall()
        related = conn.execute(f"SELECT p.*,c.name as cat_name,c.color as cat_color FROM products p JOIN categories c ON p.category_id=c.id WHERE p.category_id={product['category_id']} AND p.id!={product['id']} LIMIT 4").fetchall()
    conn.close()
    return render_template('product.html', product=product, reviews=reviews, related=related, sql_error=sql_error)


# ⚠️ XSS Stocké — pas de sanitisation du content
@app.route('/product/<int:product_id>/review', methods=['POST'])
def add_review(product_id):
    if not session.get('user'):
        return redirect(url_for('login'))
    conn = get_db()
    conn.execute("INSERT INTO reviews (product_id,user_id,username,rating,title,content) VALUES(?,?,?,?,?,?)",
                 (product_id, session.get('user_id',0), session.get('user'),
                  request.form.get('rating','5'), request.form.get('title',''),
                  request.form.get('content','')))
    conn.commit(); conn.close()
    return redirect(url_for('product_detail', product_id=product_id))


# ⚠️ SQLi UNION + XSS Réfléchi
@app.route('/search')
def search():
    q = request.args.get('q','')
    results = []; error = None; raw_query = None
    if q:
        conn = get_db()
        raw_query = f"SELECT p.*,c.name as cat_name,c.color as cat_color FROM products p JOIN categories c ON p.category_id=c.id WHERE p.name LIKE '%{q}%' OR p.description LIKE '%{q}%'"
        try:
            results = conn.execute(raw_query).fetchall()
        except Exception as e:
            error = str(e)
        finally:
            conn.close()
    return render_template('search.html', results=results, query=q, error=error, raw_query=raw_query)


# ⚠️ XSS DOM via ?sort=
@app.route('/category/<int:cat_id>')
def category(cat_id):
    sort = request.args.get('sort','popular')
    conn = get_db()
    cat = conn.execute("SELECT * FROM categories WHERE id=?",(cat_id,)).fetchone()
    cat_products = conn.execute("SELECT p.*,c.name as cat_name,c.color as cat_color FROM products p JOIN categories c ON p.category_id=c.id WHERE p.category_id=?",(cat_id,)).fetchall()
    conn.close()
    return render_template('category.html', category=cat, products=cat_products, sort=sort)


@app.route('/cart')
def cart():
    cart_data = session.get('cart',{})
    items = []; total = 0
    if cart_data:
        conn = get_db()
        for pid,qty in cart_data.items():
            p = conn.execute("SELECT * FROM products WHERE id=?",(int(pid),)).fetchone()
            if p:
                sub = p['price']*qty; items.append({'product':p,'qty':qty,'subtotal':sub}); total+=sub
        conn.close()
    discount = session.get('discount',0); final = total*(1-discount/100)
    return render_template('cart.html', items=items, total=total, discount=discount, final_total=final)


# ⚠️ CSRF sur ajout panier
@app.route('/cart/add', methods=['POST'])
def cart_add():
    pid = str(request.form.get('product_id','')); qty = int(request.form.get('qty',1))
    if pid:
        cart = session.get('cart',{}); cart[pid] = cart.get(pid,0)+qty; session['cart'] = cart
    return redirect(request.referrer or url_for('cart'))


@app.route('/cart/remove', methods=['POST'])
def cart_remove():
    pid = str(request.form.get('product_id',''))
    cart = session.get('cart',{}); cart.pop(pid,None); session['cart'] = cart
    return redirect(url_for('cart'))


# ⚠️ SQLi sur code coupon
@app.route('/cart/coupon', methods=['POST'])
def apply_coupon():
    code = request.form.get('code','')
    conn = get_db()
    try:
        coupon = conn.execute(f"SELECT * FROM coupons WHERE code='{code}' AND active=1").fetchone()
        session['coupon_msg'] = f"✅ Code « {coupon['code']} » appliqué ! -{coupon['discount']}%" if coupon else "❌ Code invalide."
        if coupon: session['discount'] = coupon['discount']
    except Exception as e:
        session['coupon_msg'] = f"💥 Erreur SQL : {str(e)}"
    conn.close()
    return redirect(url_for('cart'))


# ⚠️ CSRF sur la commande
@app.route('/checkout', methods=['GET','POST'])
def checkout():
    if not session.get('user'): return redirect(url_for('login'))
    if request.method == 'POST':
        cart_data = session.get('cart',{})
        if not cart_data: return redirect(url_for('cart'))
        conn = get_db(); total = 0
        for pid,qty in cart_data.items():
            p = conn.execute("SELECT price FROM products WHERE id=?",(int(pid),)).fetchone()
            if p: total += p['price']*qty
        final = total*(1-session.get('discount',0)/100)
        cur = conn.execute("INSERT INTO orders (user_id,total,status,shipping_address) VALUES(?,?,?,?)",
                           (session['user_id'],final,'processing',request.form.get('address','')))
        oid = cur.lastrowid
        for pid,qty in cart_data.items():
            p = conn.execute("SELECT price FROM products WHERE id=?",(int(pid),)).fetchone()
            if p: conn.execute("INSERT INTO order_items (order_id,product_id,quantity,price) VALUES(?,?,?,?)",(oid,int(pid),qty,p['price']))
        conn.commit(); conn.close()
        session.pop('cart',None); session.pop('discount',None)
        return redirect(url_for('order_detail', order_id=oid))
    cart_data = session.get('cart',{}); items = []; total = 0
    if cart_data:
        conn = get_db()
        for pid,qty in cart_data.items():
            p = conn.execute("SELECT * FROM products WHERE id=?",(int(pid),)).fetchone()
            if p:
                sub=p['price']*qty; items.append({'product':p,'qty':qty,'subtotal':sub}); total+=sub
        conn.close()
    discount=session.get('discount',0); final=total*(1-discount/100)
    ua='';
    if session.get('user_id'):
        conn=get_db(); u=conn.execute("SELECT address FROM users WHERE id=?",(session['user_id'],)).fetchone(); conn.close()
        if u: ua=u['address']
    return render_template('checkout.html', items=items, total=total, discount=discount, final_total=final, user_address=ua)


@app.route('/orders')
def orders():
    if not session.get('user'): return redirect(url_for('login'))
    conn = get_db()
    user_orders = conn.execute("SELECT * FROM orders WHERE user_id=? ORDER BY created_at DESC",(session['user_id'],)).fetchall()
    conn.close()
    return render_template('orders.html', orders=user_orders)


# ⚠️ IDOR — pas de vérification user_id
@app.route('/orders/<int:order_id>')
def order_detail(order_id):
    if not session.get('user'): return redirect(url_for('login'))
    conn = get_db()
    order = conn.execute("SELECT o.*,u.username FROM orders o JOIN users u ON o.user_id=u.id WHERE o.id=?",(order_id,)).fetchone()
    items = conn.execute("SELECT oi.*,p.name,p.icon FROM order_items oi JOIN products p ON oi.product_id=p.id WHERE oi.order_id=?",(order_id,)).fetchall()
    conn.close()
    is_own = order and order['user_id']==session.get('user_id')
    return render_template('order_detail.html', order=order, items=items, is_own=is_own)


# ⚠️ SQLi Bypass sur login
@app.route('/login', methods=['GET','POST'])
def login():
    error=None; debug_query=None
    if request.method=='POST':
        username=request.form.get('username',''); password=request.form.get('password','')
        conn=get_db()
        query=f"SELECT * FROM users WHERE username='{username}' AND password='{password}'"
        debug_query=query
        try:
            user=conn.execute(query).fetchone()
        except Exception as e:
            conn.close(); return render_template('login.html',error=f"SQL Error: {str(e)}",debug_query=debug_query)
        conn.close()
        if user:
            session['user']=user['username']; session['user_id']=user['id']; session['role']=user['role']
            return redirect(url_for('home'))
        error="Identifiants incorrects."
    return render_template('login.html', error=error, debug_query=debug_query)


# ⚠️ Auth vuln — mots de passe en clair, pas de validation
@app.route('/register', methods=['GET','POST'])
def register():
    error=None
    if request.method=='POST':
        conn=get_db()
        try:
            conn.execute("INSERT INTO users (username,email,password) VALUES(?,?,?)",
                         (request.form.get('username',''), request.form.get('email',''), request.form.get('password','')))
            conn.commit(); conn.close(); return redirect(url_for('login'))
        except:
            error="Nom d'utilisateur ou email déjà utilisé."; conn.close()
    return render_template('register.html', error=error)


@app.route('/logout')
def logout():
    session.clear(); return redirect(url_for('home'))


# ⚠️ XSS DOM via ?tab=
@app.route('/profile', methods=['GET','POST'])
def profile():
    if not session.get('user'): return redirect(url_for('login'))
    tab=request.args.get('tab','info'); msg=None
    if request.method=='POST':
        conn=get_db()
        conn.execute("UPDATE users SET phone=?,address=? WHERE id=?",
                     (request.form.get('phone',''), request.form.get('address',''), session['user_id']))
        conn.commit(); conn.close(); msg="✅ Profil mis à jour."
    conn=get_db()
    user=conn.execute("SELECT * FROM users WHERE id=?",(session['user_id'],)).fetchone()
    user_orders=conn.execute("SELECT * FROM orders WHERE user_id=? ORDER BY created_at DESC LIMIT 5",(session['user_id'],)).fetchall()
    conn.close()
    return render_template('profile.html', user=user, user_orders=user_orders, tab=tab, msg=msg)


@app.route('/admin')
@admin_required
def admin_dashboard():
    conn=get_db()
    stats={'users':conn.execute("SELECT COUNT(*) as n FROM users").fetchone()['n'],
           'products':conn.execute("SELECT COUNT(*) as n FROM products").fetchone()['n'],
           'orders':conn.execute("SELECT COUNT(*) as n FROM orders").fetchone()['n'],
           'revenue':conn.execute("SELECT COALESCE(SUM(total),0) as n FROM orders WHERE status='delivered'").fetchone()['n']}
    recent_orders=conn.execute("SELECT o.*,u.username FROM orders o JOIN users u ON o.user_id=u.id ORDER BY o.created_at DESC LIMIT 10").fetchall()
    top_products=conn.execute("SELECT name,icon,price,review_count FROM products ORDER BY review_count DESC LIMIT 5").fetchall()
    conn.close()
    return render_template('admin/dashboard.html', stats=stats, recent_orders=recent_orders, top_products=top_products)


@app.route('/admin/products')
@admin_required
def admin_products():
    conn=get_db()
    prods=conn.execute("SELECT p.*,c.name as cat_name FROM products p JOIN categories c ON p.category_id=c.id ORDER BY p.id").fetchall()
    conn.close()
    return render_template('admin/products.html', products=prods)


@app.route('/admin/orders')
@admin_required
def admin_orders():
    conn=get_db()
    all_orders=conn.execute("SELECT o.*,u.username FROM orders o JOIN users u ON o.user_id=u.id ORDER BY o.created_at DESC").fetchall()
    conn.close()
    return render_template('admin/orders.html', orders=all_orders)


# ⚠️ Admin Users — mots de passe affichés en clair !
@app.route('/admin/users')
@admin_required
def admin_users():
    conn=get_db()
    users=conn.execute("SELECT * FROM users ORDER BY id").fetchall()
    conn.close()
    return render_template('admin/users.html', users=users)


@app.route('/admin/user/<int:uid>/delete', methods=['POST'])
@admin_required
def admin_delete_user(uid):
    if uid==1: return redirect(url_for('admin_users'))
    conn=get_db(); conn.execute("DELETE FROM users WHERE id=?",(uid,)); conn.commit(); conn.close()
    return redirect(url_for('admin_users'))


@app.route('/admin/order/<int:oid>/status', methods=['POST'])
@admin_required
def admin_update_order(oid):
    conn=get_db(); conn.execute("UPDATE orders SET status=? WHERE id=?",(request.form.get('status','processing'),oid)); conn.commit(); conn.close()
    return redirect(url_for('admin_orders'))


if __name__=='__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
