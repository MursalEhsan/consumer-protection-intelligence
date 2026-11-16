FROM python:3.12-slim

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends make && rm -rf /var/lib/apt/lists/*

COPY requirements.lock ./requirements.lock
RUN pip install --no-cache-dir -r requirements.lock

COPY . /app

EXPOSE 8501

CMD ["streamlit", "run", "src/public_app.py", "--server.port=8501", "--server.address=127.0.0.1"]
