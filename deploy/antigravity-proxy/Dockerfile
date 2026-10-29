FROM node:22-alpine
ARG PROXY_VERSION=2.9.1
RUN npm install -g antigravity-claude-proxy@${PROXY_VERSION} && npm cache clean --force
EXPOSE 8080
# --log keeps it in the foreground (the default `start` detaches, which would end the container)
CMD ["antigravity-claude-proxy", "start", "--log"]
