FROM owasp/modsecurity-crs:nginx-alpine

USER root

COPY custom-rules.conf /etc/modsecurity.d/owasp-crs/rules/RESPONSE-999-CUSTOM.conf

# Désactiver le glob CRS et ne garder que le fichier custom
RUN sed -i 's|Include /etc/modsecurity.d/owasp-crs/rules/\*\.conf|Include /etc/modsecurity.d/owasp-crs/rules/RESPONSE-999-CUSTOM.conf|' \
    /etc/nginx/templates/modsecurity.d/setup.conf.template

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]