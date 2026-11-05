FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends curl git \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -r nemesis && useradd -r -g nemesis -d /app -s /sbin/nologin nemesis
WORKDIR /app
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --upgrade pip && pip install -r /app/requirements.txt
COPY ring0_kernel /app/ring0_kernel
COPY backend /app/backend
RUN chown -R nemesis:nemesis /app && chmod -R 550 /app/ring0_kernel
USER nemesis
EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-server-header"]
