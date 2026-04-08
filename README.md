# TechMart — Lab Sécurité Web WAF

Application e-commerce **intentionnellement vulnérable** pour tester ModSecurity.  
Stack : Flask · PostgreSQL · Nginx · ModSecurity · Loki · Grafana

---

## 🚀 Démarrage

```bash
docker-compose up --build -d
docker-compose logs -f techmart_app   # attendre "[DB] Initialisation terminée"
```

| Service | URL | Usage |
|---|---|---|
| **TechMart (sans WAF)** | http://localhost:5000 | Toutes les attaques passent |
| **TechMart (via WAF)** | http://localhost:8080 | WAF en interception |
| **Grafana logs** | http://localhost:3000 | Dashboard (admin/admin) |

**Activer le blocage WAF** (DetectionOnly par défaut) :
```yaml
# docker-compose.yml
- MODSECURITY_SEC_RULE_ENGINE=On
```
Puis `docker-compose restart waf`

---

## 👤 Comptes

| User | Password | Rôle |
|---|---|---|
| `admin` | `Admin@1234` | admin |
| `alice` | `alice123` | user |
| `test` | `test` | user ← **cible brute-force** |

**Carte de test** : `4111 1111 1111 1111` · exp `12/26` · CVV `123`

---

## 📖 Guide complet des attaques → `techmart/README.md`

---

## 🗺️ Vulnérabilités

| Type | Endpoint | Paramètre |
|---|---|---|
| SQLi Bypass | `POST /login` | `username` |
| SQLi UNION | `GET /search?q=` | `q` |
| SQLi Coupon | `POST /cart/coupon` | `code` |
| SQLi API | `GET /api/v1/products/search?q=` | `q` |
| XSS Stocké | `POST /product/<id>/review` | `content` |
| XSS Réfléchi | `GET /search?q=` | `q` |
| XSS DOM | `GET /profile?tab=` | `tab` |
| CSRF | `POST /cart/add` | - |
| IDOR Web | `GET /orders/<id>` | URL |
| IDOR API | `GET /api/v1/orders/<id>` | Bearer |
| Auth Faible API | `POST /api/v1/auth/login` | token base64 |
| Brute-force | `POST /login` | `test`/`test` |
| MDP clair | `/admin/users` | BDD PostgreSQL |
