# Builds the SPA and bakes it into the Caddy image that serves it.
#
# The alternative was building on a dev machine and copying `frontend/dist` to
# the server on every deploy — but `dist/` is gitignored, so a fresh clone has
# nothing to serve and the site comes up blank with no error anywhere. This
# makes the server need nothing but Docker.

FROM node:20-alpine AS build
WORKDIR /app

# Lockfile first: this layer only rebuilds when dependencies actually change.
COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# No build args. There used to be VITE_DEMO_EMAIL/PASSWORD here, inlined by
# Vite into the bundle — which meant the demo credentials were public by
# construction, had to match values hardcoded in app/seed_demo.py, and could
# only be corrected by a full rebuild rather than a restart. The server now
# mints a private demo account per visitor, so the build takes no secrets and
# no configuration at all.
RUN npm run build

# Serving stage. Caddy also reverse-proxies /api to the backend so the whole app
# is one origin — see Caddyfile, which stays bind-mounted so it can be edited
# without a rebuild.
FROM caddy:2-alpine
COPY --from=build /app/dist /srv
