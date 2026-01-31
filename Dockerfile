FROM python:3.11-alpine

WORKDIR /app

RUN apk add --no-cache \
    gcc \
    musl-dev \
    postgresql-dev \
    libffi-dev \
    make \
    curl \
    libxml2-dev \
    libxslt-dev

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/logs

CMD ["python", "bot.py"]
