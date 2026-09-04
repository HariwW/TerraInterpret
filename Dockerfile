FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    I2RSI_HOST=0.0.0.0 \
    I2RSI_PORT=8080

WORKDIR /app

ARG I2RSI_EXTRAS=""

COPY pyproject.toml README.md ./
COPY i2rsi ./i2rsi
COPY data_demo.zip ./data_demo.zip

RUN if [ -n "$I2RSI_EXTRAS" ]; then \
      pip install --no-cache-dir ".[${I2RSI_EXTRAS}]"; \
    else \
      pip install --no-cache-dir .; \
    fi

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/api/v1/health', timeout=2)"

CMD ["i2rsi"]
