# syntax = docker/dockerfile:1.4

########################################
# Étape build : construire les wheels   #
########################################
FROM python:3.12-slim-bullseye AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /build

# Déps système nécessaires pour compiler les libs Python
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
       build-essential gcc \
       libffi-dev libssl-dev \
       libxml2-dev libxslt1-dev \
       zlib1g-dev libjpeg-dev \
       curl git ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Copier le fichier des deps Python
COPY requirements.txt .

# Construire des wheels (binaries réutilisables) pour toutes les deps
# Assurez-vous que requirements.txt inclut: fastapi, uvicorn, pydantic (et vos autres deps)
RUN python -m pip install --upgrade pip wheel && \
    pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt


#########################################
# Étape runtime : image finale légère    #
#########################################
FROM python:3.12-slim-bullseye AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive

# Répertoire de travail (racine du "sandbox")
WORKDIR /workspace

# Outils runtime + GH CLI (conservés). Ngrok supprimé (inutile sur Railway).
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        unzip jq ffmpeg curl git wget ca-certificates gnupg; \
    # Installer GitHub CLI (dépôt officiel)
    mkdir -p -m 755 /etc/apt/keyrings; \
    wget -qO /etc/apt/keyrings/githubcli-archive-keyring.gpg https://cli.github.com/packages/githubcli-archive-keyring.gpg; \
    chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg; \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" > /etc/apt/sources.list.d/github-cli.list; \
    apt-get update; \
    apt-get install -y --no-install-recommends gh; \
    # Nettoyage APT
    apt-get clean; \
    rm -rf /var/lib/apt/lists/*

# Installer les wheels construits
COPY requirements.txt /workspace/requirements.txt
COPY --from=builder /wheels /wheels
RUN python -m pip install --upgrade pip && \
    pip install --no-cache-dir --no-index --find-links=/wheels -r /workspace/requirements.txt && \
    rm -rf /wheels

# Copier votre code (incluant sandbox_api.py)
COPY . /workspace

# Créer un utilisateur non-root
RUN useradd --create-home --shell /bin/bash sandboxuser && \
    mkdir -p /workspace && chown -R sandboxuser:sandboxuser /workspace
USER sandboxuser

# Exposer le port applicatif (Railway fournit $PORT dynamiquement)
EXPOSE 8000

# Santé basique (optionnel)
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import socket,os; s=socket.socket(); s.settimeout(2); s.connect(('127.0.0.1', int(os.environ.get('PORT','8000')))); s.close()"

# Lancer l'API sandbox (FastAPI via uvicorn) en écoutant sur $PORT
# Assurez-vous que sandbox_api.py contient: app = FastAPI()
ENV PORT=8000
CMD ["python", "-m", "uvicorn", "sandbox_api:app", "--host", "0.0.0.0", "--port", "%PORT%"]