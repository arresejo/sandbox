FROM node:24-slim

RUN mkdir /workspace

COPY deploy/.github /workspace/.github
