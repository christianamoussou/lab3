#!/bin/sh
# Créer les fichiers de log réels pour Promtail
for f in /var/log/nginx/waf_access.log /var/log/nginx/waf_error.log /var/log/nginx/modsec_audit.log; do
    rm -f "$f"
    touch "$f"
    chmod 666 "$f"
done

exec /docker-entrypoint.sh "$@"
