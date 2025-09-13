# syntax = docker/dockerfile:1.4

########################################
# Étape de build : compiler / installer #
########################################
FROM python:3.12-slim-bullseye AS builder

# Variables d'environnement pour Python
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /build

# Installer dépendances système pour build
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
       build-essential \
       gcc \
       libffi-dev \
       libssl-dev \
       libxml2-dev \
       libxslt1-dev \
       zlib1g-dev \
       libjpeg-dev \
       curl \
       git \
       ca-certificates && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Installer Node.js + npm pour builder ou usage
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
       nodejs \
       npm && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Copier le fichier des deps Python
COPY requirements.txt .

# Construire / installer toutes les librairies Python
RUN python3 -m pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

#########################################
# Étape runtime : image finale plus légère #
#########################################
FROM python:3.12-slim-bullseye AS runtime

# Variables d'environnement
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/workspace/node_modules/.bin:${PATH}"

WORKDIR /workspace

# Installer les dépendances runtime nécessaires (non-builder)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
       ffmpeg \
       curl \
       git && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Copier les dépendances Python déjà construites depuis builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# (Optionnel) installer Node.js runtime si besoin
# Si tu veux une version plus récente de Node, tu peux l’installer ici
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
       nodejs \
       npm && \
    apt-get clean && rm -rf /var/lib/apt/lists/*


# Créer un utilisateur non-root
RUN useradd --create-home --shell /bin/bash sandboxuser && \
    chown -R sandboxuser /workspace

USER sandboxuser

# Commande par défaut (tu pourras override)
CMD ["bash"]
