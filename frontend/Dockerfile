FROM node:22-bookworm-slim AS builder

WORKDIR /app

COPY package.json package-lock.json ./

RUN npm install -g npm@11.17.0 \
    && npm --version \
    && npm ci

COPY . .

ARG VITE_API_URL=/api

ENV VITE_API_URL=${VITE_API_URL}
ENV NITRO_PRESET=node-server

RUN npm run build


FROM node:22-bookworm-slim AS runtime

WORKDIR /app

ENV NODE_ENV=production
ENV HOST=0.0.0.0
ENV PORT=3000
ENV API_INTERNAL_URL=http://backend:8000

COPY --from=builder /app/.output ./.output

EXPOSE 3000

CMD ["node", ".output/server/index.mjs"]
