FROM node:22-alpine
WORKDIR /app
COPY package.json server.js ./
USER node
EXPOSE 3005
CMD ["node", "server.js"]
