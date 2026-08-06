# Deploying Arus

One box runs everything: Caddy (TLS + routing), the FastAPI backend, and
Postgres. The built frontend is static files Caddy serves directly.

This works identically on a free VM (Oracle Cloud Always Free, GCP `e2-micro`)
and on a paid VPS — nothing here is provider-specific.

## Why one box

The frontend hardcodes `BASE = "/api"` (`frontend/src/api/client.ts`). That
path only exists in development because `vite.config.ts` invents it with a dev
proxy. Serving the static build and the API from **one origin** keeps `/api`
working with no code change, and means there is no CORS to configure.

Splitting the frontend onto a separate host is possible but is not free: it
requires CORS middleware (the app has none today) and an environment-driven
absolute API URL.

The backend must also stay **awake**. APScheduler runs in-process, so quotes
(every 15 min, 09:00–16:00 WIB) and daily bars (18:30 WIB) only fire while the
container is up. There is no separate worker to host — and no way to schedule
anything if the box sleeps.

## Requirements

- A machine with Docker and the Compose plugin
- ~1 GB RAM is enough; the database is small and grows only with tickers
  someone actually opens (backfill is lazy)
- A domain pointed at the box, if you want HTTPS. Without one, set `DOMAIN=:80`
  and it serves plain HTTP.

## Steps

**1. Get the code onto the box**

```bash
git clone <your-repo> arus && cd arus
```

**2. Configure**

```bash
cp .env.prod.example .env.prod
openssl rand -hex 32        # paste into SECRET_KEY
```

Fill in `SECRET_KEY`, `POSTGRES_PASSWORD` and `DOMAIN`. The compose file uses
`${VAR:?...}`, so a missing value stops the deploy with a readable error rather
than falling back to the development defaults.

**3. Build the frontend**

There is no Node on the server and no reason for one — build wherever you
develop, then copy `frontend/dist` to the box (or build in CI and copy the
artifact). The demo credentials are compile-time, so they must be present for
that build:

```bash
cd frontend
VITE_DEMO_EMAIL=demo@arus.id VITE_DEMO_PASSWORD=... npm run build
```

Leave both unset to ship without the demo button entirely. They end up in the
JS bundle either way, so the demo account must be a throwaway.

**4. Start**

```bash
docker compose --env-file .env.prod \
  -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

Migrations run automatically — the backend's command is
`alembic upgrade head && uvicorn ...`, so the schema is current before the API
serves a single request.

**5. Seed the demo (optional)**

```bash
docker compose --env-file .env.prod \
  -f docker-compose.yml -f docker-compose.prod.yml \
  exec backend python -m app.seed_demo
```

**6. Check it**

```bash
curl -fsS https://$DOMAIN/api/health && echo OK
```

## Why the override file, not a second stack

`docker-compose.prod.yml` is applied *on top of* the base file. Compose merges
them, and the merge has two sharp edges worth knowing:

- **`ports` cannot be un-published by an override.** The base file publishes
  Postgres on `5432`, which on a public box would be the whole database on the
  internet. The override re-declares it as `127.0.0.1:5432:5432` — rebinding to
  loopback is what actually closes it.
- **`volumes` lists are appended, not replaced.** The base file bind-mounts
  `./backend:/app` for hot reload. That mount survives the override, which is
  why the deploy uses `--build`: the image contains the same code at the same
  path, so the mount is a no-op rather than a stale-source hazard. Keep the
  repo on the box in sync with what you build.

## Operating it

**The scheduler only runs while the container does.** `restart: unless-stopped`
covers crashes and reboots. If the host sleeps anyway, the startup catch-up
(`app/sync/catchup.py`) appends missed daily bars and refreshes stale quotes on
the next boot — so the data self-heals on wake rather than staying stale.

**Yahoo throttles datacenter IPs** harder than home connections. Expect more
sync failures than on a laptop; the retry/backoff absorbs some of it.

**The demo account is shared and mutable.** Anyone who clicks the demo button
can add or delete portfolios. Re-run `app.seed_demo` periodically if you care
what a visitor sees.

**Backups.** Postgres lives in the `pgdata` volume. Nothing backs it up
automatically:

```bash
docker compose --env-file .env.prod \
  -f docker-compose.yml -f docker-compose.prod.yml \
  exec -T db pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip > backup-$(date +%F).sql.gz
```

## Before making it public

`PRODUCT.md` records that this project is personal / non-commercial **by
licensing necessity** — IDX terms restrict commercial redistribution, and Yahoo
Finance data carries its own usage limits. Serving cached IDX/Yahoo data to the
public is a different posture from local personal use. Worth checking those
terms before the link goes on a CV; this file cannot settle it for you.
