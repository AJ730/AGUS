FROM node:20-alpine AS build
ARG VITE_API_BASE=/api
ARG VITE_GOOGLE_MAPS_API_KEY
ARG VITE_CESIUM_ION_TOKEN
ENV VITE_API_BASE=$VITE_API_BASE
ENV VITE_GOOGLE_MAPS_API_KEY=$VITE_GOOGLE_MAPS_API_KEY
ENV VITE_CESIUM_ION_TOKEN=$VITE_CESIUM_ION_TOKEN
WORKDIR /app
COPY package.json ./
RUN npm install
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
ARG NGINX_CONF=nginx.conf
COPY ${NGINX_CONF} /etc/nginx/conf.d/default.conf
EXPOSE 80
