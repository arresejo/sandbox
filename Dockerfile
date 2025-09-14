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
RUN python -m pip install --upgrade pip wheel && \
    pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt


#########################################
# Étape runtime : image finale légère    #
#########################################
FROM python:3.12-slim-bullseye AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive \
    PATH="/workspace/node_modules/.bin:${PATH}"

WORKDIR /workspace

# Outils runtime + GH CLI + ngrok
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
    # Installer ngrok binaire
    curl -sSL https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-stable-linux-amd64.zip -o /tmp/ngrok.zip; \
    unzip /tmp/ngrok.zip -d /usr/local/bin; \
    rm -f /tmp/ngrok.zip; \
    # Nettoyage APT
    apt-get clean; \
    rm -rf /var/lib/apt/lists/*

# Copier requirements et wheels depuis le builder et installer
COPY requirements.txt /workspace/requirements.txt
COPY --from=builder /wheels /wheels
RUN python -m pip install --upgrade pip && \
    pip install --no-cache-dir --no-index --find-links=/wheels -r /workspace/requirements.txt && \
    rm -rf /wheels

# (Optionnel) Installer Node.js + npm (décommente si nécessaire)
# RUN set -eux; \
#     apt-get update; \
#     apt-get install -y --no-install-recommends nodejs npm; \
#     apt-get clean; \
#     rm -rf /var/lib/apt/lists/*

# Créer un utilisateur non-root
RUN useradd --create-home --shell /bin/bash sandboxuser && \
    mkdir -p /workspace && chown -R sandboxuser:sandboxuser /workspace
USER sandboxuser

# Ports : serveur HTTP app + API ngrok
EXPOSE 8000 4040

# Commande par défaut
CMD ["bash"]