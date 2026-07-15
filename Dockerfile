FROM python:3.13-slim

WORKDIR /app

RUN sed -i \
        -e 's|deb.debian.org/debian-security|mirrors.tuna.tsinghua.edu.cn/debian-security|g' \
        -e 's|deb.debian.org/debian|mirrors.tuna.tsinghua.edu.cn/debian|g' \
        /etc/apt/sources.list.d/debian.sources && \
    apt-get update && apt-get install -y --no-install-recommends \
    curl gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY . .
RUN pip install --no-cache-dir \
    --index-url https://pypi.tuna.tsinghua.edu.cn/simple \
    -e ".[test,dev]"

ENV PYTHONPATH=/app/backend
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
