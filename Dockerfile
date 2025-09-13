FROM node:24-slim

RUN mkdir /workspace

# Increase the number of inotify watches to avoid ENOSPC error (can be useful in a dev environment with a lot of files)
# RUN echo "fs.inotify.max_user_watches=524288" >> /etc/sysctl.conf
