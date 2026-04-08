FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir \
    flask==3.0.0 \
    psycopg2-binary==2.9.9
COPY app/ /app/
EXPOSE 5000
CMD ["python", "-c", "import app; app.init_db(); app.app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)"]
