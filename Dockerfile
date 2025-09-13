FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    ffmpeg \
    git \
    jq \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Install yt-dlp (via pip so it's always up to date)
RUN pip install --no-cache-dir -U yt-dlp

# Install ngrok
RUN curl -s https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-stable-linux-amd64.zip -o ngrok.zip \
    && unzip ngrok.zip \
    && mv ngrok /usr/local/bin/ \
    && rm ngrok.zip

# Set working directory inside container
WORKDIR /workspace

# Expose the HTTP server port and ngrok API port
EXPOSE 8000 4040
