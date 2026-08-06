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

# Vite inlines these at BUILD time, so they must be present here rather than in
# the container environment. They end up readable in the shipped JS by
# construction — hence a throwaway demo account, never anything private. Unset
# means the demo button is not rendered at all.
ARG VITE_DEMO_EMAIL=""
ARG VITE_DEMO_PASSWORD=""
ENV VITE_DEMO_EMAIL=$VITE_DEMO_EMAIL
ENV VITE_DEMO_PASSWORD=$VITE_DEMO_PASSWORD

RUN npm run build

# Serving stage. Caddy also reverse-proxies /api to the backend so the whole app
# is one origin — see Caddyfile, which stays bind-mounted so it can be edited
# without a rebuild.
FROM caddy:2-alpine
COPY --from=build /app/dist /srv
