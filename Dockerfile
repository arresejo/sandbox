FROM ubuntu:24.04

# Install Node.js
# RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
RUN apt update
RUN apt install -y nodejs npm
RUN node --version
RUN npm --version

# Increase the number of inotify watches to avoid ENOSPC error
RUN echo "fs.inotify.max_user_watches=524288" >> /etc/sysctl.conf

