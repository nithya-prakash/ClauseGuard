FROM node:22-slim AS deps
WORKDIR /srv
COPY frontend/package.json ./
RUN npm install

FROM node:22-slim AS build
WORKDIR /srv
COPY --from=deps /srv/node_modules ./node_modules
COPY frontend ./
# Backend URL the BROWSER (not this build) will call - baked in at build
# time since Next.js inlines NEXT_PUBLIC_* vars into the client bundle.
ARG NEXT_PUBLIC_API_BASE_URL=http://localhost:8004
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL
RUN npm run build

FROM node:22-slim AS run
WORKDIR /srv
ENV NODE_ENV=production
# Docker auto-sets HOSTNAME to the container ID; Next.js standalone's
# server.js binds to process.env.HOSTNAME when set, which would make it
# listen only on that hostname's resolved address, not all interfaces -
# breaking both the healthcheck below (which connects via 127.0.0.1) and
# any other loopback access, even though the docker-compose port mapping
# (which routes to the container's bridge IP, not through loopback) still
# appears to work. Found and fixed in Milestone 12 while verifying the
# stack - explicitly overriding it to bind everywhere.
ENV HOSTNAME=0.0.0.0
COPY --from=build /srv/.next/standalone ./
COPY --from=build /srv/.next/static ./.next/static
COPY --from=build /srv/public ./public

EXPOSE 3000

HEALTHCHECK --interval=10s --timeout=5s --retries=10 \
    CMD node -e "require('http').get('http://localhost:3000', r => process.exit(r.statusCode < 500 ? 0 : 1)).on('error', () => process.exit(1))"

CMD ["node", "server.js"]
