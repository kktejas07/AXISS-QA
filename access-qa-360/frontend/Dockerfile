# Production image: builds the web app and serves it with nginx.
# nginx also forwards /api to the API container, so the browser talks to one address.
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci || npm install
# Same-origin by default. Set to a full URL only when the API is on another domain.
ARG VITE_API_URL=/api/v1
ENV VITE_API_URL=$VITE_API_URL
# The site's public address, written into the sitemap, robots.txt, llms.txt and the page's canonical link.
ARG SITE_URL=https://qa.vatax360.com
ENV SITE_URL=$SITE_URL
# Optional: the codes Google Search Console and Bing Webmaster Tools give you to prove the site is yours.
ARG GOOGLE_SITE_VERIFICATION=
ARG BING_SITE_VERIFICATION=
ENV GOOGLE_SITE_VERIFICATION=$GOOGLE_SITE_VERIFICATION BING_SITE_VERIFICATION=$BING_SITE_VERIFICATION
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=5s CMD wget -qO- http://127.0.0.1/ >/dev/null || exit 1
CMD ["nginx", "-g", "daemon off;"]
