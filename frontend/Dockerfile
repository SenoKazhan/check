FROM node:20-alpine AS base

WORKDIR /app

# Копируем package.json и устанавливаем зависимости
COPY package*.json ./
RUN npm ci

# Копируем остальной код
COPY . .

# Запускаем сервер разработки
CMD ["npm", "run", "dev"]