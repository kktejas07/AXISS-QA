# --- Build the Expo web bundle ---------------------------------------------
FROM node:22-alpine AS build
WORKDIR /app

ENV CI=1

COPY package*.json ./
RUN npm ci

COPY . .

# Inlined into the bundle at build time. Pass it with:
#   docker build --build-arg EXPO_PUBLIC_API_URL=https://api.example.com .
ARG EXPO_PUBLIC_API_URL=http://localhost:3000
ENV EXPO_PUBLIC_API_URL=$EXPO_PUBLIC_API_URL

RUN npx expo export --platform web --output-dir dist

# --- Serve it ---------------------------------------------------------------
FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
