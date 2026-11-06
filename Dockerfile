FROM python:3.13-slim

RUN pip install --no-cache-dir uv==0.9.5

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY app ./app
COPY sites ./sites

ENV PATH="/app/.venv/bin:$PATH"

# Railway가 PORT를 정해 준다. 프록시 뒤에서 원래 Host/스킴을 신뢰한다.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
