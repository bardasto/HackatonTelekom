# Stage 1: Build the React application
# >>> ВОТ ЗДЕСЬ БЫЛА ПРОПУЩЕНА СТРОКА FROM <<<
FROM node:18-alpine AS builder 
# Мы используем node:18-alpine как легковесный образ Node.js для сборки
# AS builder - даем имя этому этапу, чтобы потом ссылаться на него

WORKDIR /app

# Copy package.json and package-lock.json (or yarn.lock if you use yarn)
# This allows Docker to cache the npm install step if these files haven't changed
COPY package*.json ./

# Install dependencies
# --frozen-lockfile (for npm v7+) or npm ci is recommended for reproducible builds
RUN npm install --frozen-lockfile
# Если используешь yarn:
# COPY yarn.lock ./
# RUN yarn install --frozen-lockfile

# Copy the rest of the application source code
COPY . .

# (Optional) Set build-time environment variables if your app needs them during the build process
# ARG REACT_APP_API_BASE_URL
# ENV REACT_APP_API_BASE_URL=$REACT_APP_API_BASE_URL

# Build the production version of the app
RUN npm run build

# Stage 2: Serve static files with Nginx
FROM nginx:1.25-alpine

# Copy built static files from the 'builder' stage (where we ran npm run build)
# to Nginx's default web root directory
COPY --from=builder /app/build /usr/share/nginx/html

# (Optional) If you have a custom Nginx configuration, copy it here
# COPY nginx.conf /etc/nginx/conf.d/default.conf 
# By default, Nginx will serve index.html from /usr/share/nginx/html

# Expose port 80 (Nginx's default port)
EXPOSE 80

# Command to run Nginx in the foreground so the container stays running
CMD ["nginx", "-g", "daemon off;"]