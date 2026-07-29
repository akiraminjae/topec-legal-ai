FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Seoul

RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice \
    fonts-nanum \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .

EXPOSE 2004
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "2004"]
