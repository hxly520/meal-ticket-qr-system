FROM node:22-alpine AS build

WORKDIR /app
COPY package*.json ./
RUN npm ci && npm install --no-save @rollup/rollup-linux-x64-musl
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
