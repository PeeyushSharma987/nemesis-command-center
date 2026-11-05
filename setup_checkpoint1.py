import os
import secrets
import shutil
import subprocess
from pathlib import Path

# 1. Create the main project folder and all subfolders on Windows
BASE_DIR = Path("nemesis-core")
FOLDERS = [
    BASE_DIR / "ring0_kernel",
    BASE_DIR / "backend" / "auth",
    BASE_DIR / "backend" / "commander",
    BASE_DIR / "backend" / "memory",
    BASE_DIR / "backend" / "router",
    BASE_DIR / "backend" / "paypal_engine",
    BASE_DIR / "backend" / "agents",
    BASE_DIR / "backend" / "self_mutate",
    BASE_DIR / "device_bridge",
    BASE_DIR / "frontend_hud",
    BASE_DIR / "omniroute_docker",
]

print("[1/6] Creating N.E.M.E.S.I.S. folders...")
for folder in FOLDERS:
    folder.mkdir(parents=True, exist_ok=True)
    # Create empty __init__.py files for Python packages
    if "backend" in str(folder) or "ring0_kernel" in str(folder):
        (folder / "__init__.py").touch()
(BASE_DIR / "backend" / "__init__.py").touch()

# 2. Create .gitignore so secrets never leak
print("[2/6] Creating .gitignore...")
(BASE_DIR / ".gitignore").write_text(
    ".env\n*.pem\n*.key\n__pycache__/\n*.pyc\npgdata/\nredisdata/\nfreellmapi/\n",
    encoding="utf-8",
)

# 3. Generate 256-bit secret keys using Python (works on Windows without openssl)
print("[3/6] Generating encrypted .env keys...")
env_path = BASE_DIR / ".env"
if not env_path.exists():
    jwt_sec = secrets.token_hex(32)
    fla_enc = secrets.token_hex(32)
    db_pass = secrets.token_hex(24)
    redis_pass = secrets.token_hex(24)
    founder_key = secrets.token_hex(32)

    env_content = f"""APP_ENV=production
DEBUG=False

# Cryptographic Core Keys
JWT_SECRET_KEY={jwt_sec}
FOUNDER_GOD_KEY={founder_key}
ENCRYPTION_KEY={fla_enc}

# Database & Redis (Internal Docker Network)
POSTGRES_USER=nemesis_admin
POSTGRES_PASSWORD={db_pass}
POSTGRES_DB=nemesis_saas
DATABASE_URL=postgresql+asyncpg://nemesis_admin:{db_pass}@postgres:5432/nemesis_saas
REDIS_PASSWORD={redis_pass}
REDIS_URL=redis://:{redis_pass}@redis:6379/0

# 9-Billion Token Engine Endpoints
FREELLMAPI_URL=http://freellmapi:3001/v1
FREELLMAPI_MASTER_KEY=fla_local_master_key_change_after_dashboard_init
OMNIROUTE_URL=http://omniroute:4000/v1
OMNIROUTE_API_KEY=omni_local_master_key

# Flagship Reasoning & Live Camera Vision Node
GEMINI_ARGON_API_KEY=replace_with_your_gemini_api_key
GEMINI_ARGON_MODEL=gemini-4-argon

# PayPal SaaS & Agent Toolkit Credentials
PAYPAL_CLIENT_ID=replace_with_paypal_client_id
PAYPAL_CLIENT_SECRET=replace_with_paypal_client_secret
PAYPAL_WEBHOOK_ID=replace_with_paypal_webhook_id
PAYPAL_MODE=sandbox
"""
    env_path.write_text(env_content, encoding="utf-8")

# 4. Clone or move FreeLLMAPI into nemesis-core/freellmapi
print("[4/6] Setting up FreeLLMAPI (7.4B Token Pool)...")
target_freellm = BASE_DIR / "freellmapi"
old_freellm = Path.home() / "freellmapi"

if not target_freellm.exists():
    if old_freellm.exists():
        shutil.move(str(old_freellm), str(target_freellm))
        print("  -> Moved existing freellmapi folder from your user directory!")
    else:
        subprocess.run(
            ["git", "clone", "https://github.com/tashfeenahmed/freellmapi.git", str(target_freellm)],
            check=True,
        )

# 5. Write Dockerfiles, requirements.txt, and docker-compose.yml
print("[5/6] Writing Docker and backend configuration files...")

(BASE_DIR / "omniroute_docker" / "Dockerfile").write_text(
    """FROM node:20-alpine
RUN addgroup -S omni && adduser -S omni -G omni
RUN npm install -g omniroute@latest && npm cache clean --force
USER omni
WORKDIR /home/omni
EXPOSE 4000
CMD ["omniroute", "start", "--port", "4000", "--host", "0.0.0.0"]
""",
    encoding="utf-8",
)

(BASE_DIR / "backend" / "requirements.txt").write_text(
    """fastapi==0.115.6
uvicorn[standard]==0.34.0
pydantic==2.10.4
pydantic-settings==2.7.1
httpx==0.28.1
redis==5.2.1
sqlalchemy[asyncio]==2.0.36
asyncpg==0.30.0
pgvector==0.3.6
tenacity==9.0.0
argon2-cffi==23.1.0
pyjwt[crypto]==2.10.1
cryptography==44.0.0
python-multipart==0.0.20
""",
    encoding="utf-8",
)

(BASE_DIR / "backend" / "Dockerfile").write_text(
    """FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends curl git \\
    && rm -rf /var/lib/apt/lists/* \\
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
""",
    encoding="utf-8",
)

(BASE_DIR / "docker-compose.yml").write_text(
    """services:
  postgres:
    image: pgvector/pgvector:pg16
    container_name: nemesis_postgres
    restart: unless-stopped
    env_file: .env
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    volumes:
      - pgdata:/var/lib/postgresql/data
    networks:
      - nemesis_internal

  redis:
    image: redis:7-alpine
    container_name: nemesis_redis
    restart: unless-stopped
    command: ["redis-server", "--appendonly", "yes", "--requirepass", "${REDIS_PASSWORD}"]
    volumes:
      - redisdata:/data
    networks:
      - nemesis_internal

  freellmapi:
    build:
      context: ./freellmapi
    container_name: nemesis_freellmapi
    restart: unless-stopped
    environment:
      PORT: 3001
      ENCRYPTION_KEY: ${ENCRYPTION_KEY}
    ports:
      - "127.0.0.1:3001:3001"
    volumes:
      - freellm_data:/app/data
    networks:
      - nemesis_internal

  omniroute:
    build:
      context: ./omniroute_docker
    container_name: nemesis_omniroute
    restart: unless-stopped
    ports:
      - "127.0.0.1:4000:4000"
    volumes:
      - omniroute_data:/home/omni/.omniroute
    networks:
      - nemesis_internal

networks:
  nemesis_internal:
    driver: bridge

volumes:
  pgdata:
  redisdata:
  freellm_data:
  omniroute_data:
""",
    encoding="utf-8",
)

print("[6/6] Done! Checkpoint 1 workspace is ready inside the 'nemesis-core' folder.")
