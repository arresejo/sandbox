FROM node:24-slim

RUN apt-get update \
	&& apt-get install -y curl git \
	&& curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg \
	&& chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg \
	&& echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | tee /etc/apt/sources.list.d/github-cli.list > /dev/null \
	&& apt-get update \
	&& apt-get install -y gh \
	&& rm -rf /var/lib/apt/lists/*

RUN mkdir /workspace

COPY deploy/.github /workspace/.github

WORKDIR /workspace

# # Keep container running
# CMD ["tail", "-f", "/dev/null"]