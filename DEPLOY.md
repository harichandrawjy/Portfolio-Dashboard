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
git clone https://github.com/harichandrawjy/Portfolio-Dashboard.git arus && cd arus
```

Every command from here runs in that directory.

**2. Prepare the box, and the two things outside it**

A stock free-tier VM has no Docker, blocks 80/443, and — if it has 1 GB of RAM
— cannot complete the frontend build. `scripts/bootstrap-host.sh` fixes all
three and is safe to re-run:

```bash
sudo bash scripts/bootstrap-host.sh
```

It also asserts Compose ≥ 2.24, without which the `!override` / `!reset` tags
below are ignored silently, and it prints the provider-specific instructions
for whichever cloud it detects. Log out and back in afterwards so the `docker`
group applies and the remaining commands work without `sudo`.

Two things it cannot do from inside the box, both of which must be true before
step 4:

- **Open 80/443 at the provider level too.** Oracle: VCN → Security Lists →
  add ingress for TCP 80 and 443 from `0.0.0.0/0`. GCP: give the instance the
  `http-server` and `https-server` network tags. The host firewall is only
  half of it.
- **Point the hostname at the IP, and verify it.** Caddy asks Let's Encrypt
  for a certificate on first start; if DNS is not live yet the challenge
  fails, and repeated failures are rate-limited. This must print the box's
  public IP before you continue:

  ```bash
  getent hosts arus.duckdns.org
  ```

  (`getent` is on every image; `dig` needs `dnsutils` installed.)

**3. Configure**

```bash
cp .env.prod.example .env.prod
openssl rand -hex 32        # paste into SECRET_KEY
```

Fill in `SECRET_KEY`, `POSTGRES_PASSWORD` and `DOMAIN`. The compose file uses
`${VAR:?...}`, so a missing value stops the deploy with a readable error rather
than falling back to the development defaults.

**4. Start**

```bash
docker compose --env-file .env.prod \
  -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

That one command builds the frontend too — `frontend/Dockerfile` compiles the
SPA and bakes it into the Caddy image, so the server needs nothing but Docker.
No Node, and nothing to copy across.

Migrations run automatically — the backend's command is
`alembic upgrade head && uvicorn ...`, so the schema is current before the API
serves a single request.

The demo credentials in `.env.prod` are read at **build** time by Vite, so
changing them needs a rebuild (`up -d --build`), not just a restart. They are
also not free-form: `app/seed_demo.py` hardcodes the account it creates, so
they must be exactly the values shipped in `.env.prod.example` or the demo
button builds fine and then fails to log in. Blank both to ship without the
button at all.

**5. Seed the demo**

```bash
docker compose --env-file .env.prod \
  -f docker-compose.yml -f docker-compose.prod.yml \
  exec backend python -m app.seed_demo
```

This is the heaviest network step — it backfills five years of bars per ticker
through yfinance, which throttles datacenter IPs harder than home connections.
It is idempotent, so if it dies partway just run it again; the tickers already
backfilled are skipped.

**6. Check it**

```bash
curl -fsS https://$DOMAIN/api/health && echo OK
```

If that hangs or the certificate never arrives, Caddy says why:

```bash
docker compose --env-file .env.prod -f docker-compose.yml -f docker-compose.prod.yml logs caddy
```

Almost always one of: DNS not resolving to this box yet, or 80/443 still shut
at the provider level (see step 0 — the host firewall is not the whole story).
Fix the cause and `restart caddy`; it retries on its own too. If you end up
looping on failures, Let's Encrypt's rate limit is per hour — or point Caddy at
their staging CA while you debug by adding a global block to the top of the
`Caddyfile`:

```
{
	acme_ca https://acme-staging-v02.api.letsencrypt.org/directory
}
```

Staging certificates are untrusted by browsers, so remove it once the challenge
succeeds and `restart caddy` to get a real one.

## Why the override file, not a second stack

`docker-compose.prod.yml` is applied *on top of* the base file, and the merge
has one sharp edge that matters more than anything else here:

**Compose APPENDS list fields — it does not replace them.** `ports:` and
`volumes:` in an override are added to the base file's, not substituted for
them. Writing `ports: []` does nothing at all. Left unhandled that produced
three separate holes, every one of them silent:

- Postgres published on **every interface** — the base file's `5432:5432`
  survived alongside the loopback entry, putting the database on the internet
- the API published on `8000` directly, **bypassing Caddy and therefore TLS**
- the dev bind mount still shadowing `/app`, so the container ran whatever was
  on the server's disk instead of what was built

The fix is the `!override` and `!reset` tags (Compose 2.24+), which replace
instead of merging. They are load-bearing — remove one and the corresponding
hole comes back with no error and no warning.

**Verify the merge rather than trusting it.** `config` prints the fully
resolved stack, and this is the fastest way to catch a regression:

```bash
docker compose --env-file .env.prod -f docker-compose.yml -f docker-compose.prod.yml config
```

Expect: `db` published exactly once and bound to `127.0.0.1`, `backend` with no
published ports and no bind mount, `caddy` on 80 and 443.

## Operating it

**The scheduler only runs while the container does.** `restart: unless-stopped`
covers crashes and reboots. If the host sleeps anyway, the startup catch-up
(`app/sync/catchup.py`) appends missed daily bars and refreshes stale quotes on
the next boot — so the data self-heals on wake rather than staying stale.

**Yahoo throttles datacenter IPs** harder than home connections. Expect more
sync failures than on a laptop; the retry/backoff absorbs some of it.

**The demo account is shared and mutable.** Anyone who clicks the demo button
can add or delete portfolios, and a visitor who arrives after someone deleted
the demo portfolio sees an empty app. `seed_demo` is idempotent — it exits if
the portfolio is still there — so a nightly cron costs nothing and keeps the
link presentable:

```bash
sudo crontab -e
```

```cron
# 03:00 WIB — after the day's syncs, before anyone looks.
0 3 * * * cd /home/ubuntu/arus && /usr/bin/docker compose --env-file .env.prod -f docker-compose.yml -f docker-compose.prod.yml exec -T backend python -m app.seed_demo >> /var/log/arus-seed.log 2>&1
```

Note `exec -T`: cron has no TTY, and without it the command fails with "the
input device is not a TTY". Adjust the path if you cloned somewhere else.

**Backups.** Postgres lives in the `pgdata` volume. Nothing backs it up
automatically:

```bash
docker compose --env-file .env.prod \
  -f docker-compose.yml -f docker-compose.prod.yml \
  exec -T db pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip > backup-$(date +%F).sql.gz
```

## Before making it public

`PRODUCT.md` records this project as personal / non-commercial **by licensing
necessity**. That framing is right but incomplete, and the gap only matters
once the box is reachable from the internet.

**IDX** ([terms of use](https://www.idx.co.id/en/terms-of-use/), read
2026-08-06). Two separate clauses, and the second is the one that bites:

1. Disseminating IDX data to other parties **for commercial purpose** needs
   prior written consent. Non-commercial use is fine here — this is the
   restriction `PRODUCT.md` already accounts for.
2. Non-commercial use is *permitted* only on two conditions: citing the
   complete source together with the date of access, and not using the
   "web scrapping/crawling method".

`app/sync/idx.py` fetches idx.co.id's JSON endpoints on a schedule, which is
the collection method condition 2 excludes — regardless of commercial intent.
So non-commercial status alone does not carry the deployment.

What the code already supports, if that matters to you: `sync_universe()` falls
back to the bundled `app/data/idx_universe.csv` snapshot (insert-only, ~950
tickers) whenever the live fetch fails. A public deployment could drop the
`universe-sync` job and run off that snapshot instead, giving up automatic
pickup of new listings and nothing else. Attribution in the UI is the other
half. Neither is done — this is a note, not a completed decision.

**Yahoo.** yfinance reads undocumented endpoints, so the
[Yahoo Developer API terms](https://legal.yahoo.com/us/en/yahoo/terms/product-atos/apiforydn/index.html)
do not govern it — those cover the official YDN APIs. yfinance's own
documentation states it is not affiliated with Yahoo and is meant for research
and educational use, and that the underlying API is intended for personal use.
The realistic consequence of a public deployment is not legal but operational:
datacenter IPs get throttled, which is already noted above.

None of this is legal advice, and none of it is a reason the link cannot go on
a CV — a clearly-labelled non-commercial student project serving delayed,
cached data is ordinary. It is written down so the choice is made on the facts
rather than on the assumption that "non-commercial" settles it.
