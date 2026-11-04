# Stage 1: Build React Client (Section 5.8)
FROM node:20-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json /app/
RUN npm ci --legacy-peer-deps

COPY . /app/
RUN npm run build

# Stage 2: Production Nginx Server (Section 5.8)
FROM nginx:alpine AS runner

# Remove default static files
RUN rm -rf /usr/share/nginx/html/*

# Copy built frontend assets from builder
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy Nginx main and virtual host configuration with security headers
COPY nginx/nginx.conf /etc/nginx/nginx.conf
COPY nginx/conf.d/default.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=15s --timeout=5s --start-period=5s --retries=3 \
    CMD wget -q --spider http://127.0.0.1/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
