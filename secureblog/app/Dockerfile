FROM python:3.11-slim
WORKDIR /app
# Dépendances système
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# On copie tout ce qui est dans techmart/app/ vers /app/ du conteneur
COPY . . 
RUN mkdir -p /app/data
EXPOSE 5000
CMD ["python", "-c", "import app; app.init_db(); app.app.run(host='0.0.0.0', port=5000)"]