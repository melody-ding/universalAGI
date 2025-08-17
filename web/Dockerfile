FROM node:18-alpine

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .

# Use the no-lint build command
RUN npm run build:nolint

EXPOSE 3000

CMD ["npm", "start"]