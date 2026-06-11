# Build React app
# --platform=$BUILDPLATFORM: run the node build stage natively on the build
# host even when targeting arm64 — the build output is static files, so it's
# architecture-independent. Without this, the arm64 image build runs webpack
# under QEMU emulation (~10x slower).
FROM --platform=$BUILDPLATFORM node:20-alpine AS build
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

# Serve with nginx
FROM nginx:1.27-alpine

# SPA routing + caching defaults
COPY nginx.conf /etc/nginx/conf.d/default.conf

COPY --from=build /app/build /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
