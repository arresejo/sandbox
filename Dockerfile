FROM node:24-slim

RUN mkdir /workspace

COPY deploy/.github /workspace/.github

WORKDIR /workspace

# # Keep container running
# CMD ["tail", "-f", "/dev/null"]