FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install --no-install-recommends -y postgresql-client \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 --shell /usr/sbin/nologin appuser

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=appuser:appuser . .
RUN chmod 0555 /app/docker-entrypoint.sh \
    && mkdir -p /exports \
    && chown appuser:appuser /exports

USER appuser

EXPOSE 8000

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
