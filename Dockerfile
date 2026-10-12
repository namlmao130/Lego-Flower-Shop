FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    REQUIRE_POSTGRES=true

WORKDIR /app

RUN groupadd --gid 1000 app && useradd --system --gid app --create-home app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . ./
RUN mkdir -p static/uploads/avatars && chown -R app:app /app

USER app

EXPOSE 10000

CMD ["sh", "-c", "exec gunicorn -c gunicorn.conf.py web:app --bind 0.0.0.0:${PORT:-10000} --access-logfile - --error-logfile -"]
