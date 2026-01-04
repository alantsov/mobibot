FROM node:23-slim

WORKDIR /app

RUN npm install express @mozilla/readability jsdom

COPY server.js .

EXPOSE 3000

CMD ["node", "server.js"]
