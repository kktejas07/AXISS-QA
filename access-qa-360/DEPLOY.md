# Deploying Wiseflow

Everything runs from `docker-compose.prod.yml` in this folder: Postgres, Redis, the API, a background worker and the web app. One container (`web`) is the public entry point; it serves the app and forwards `/api` to the API, so the browser only ever talks to one address.

## What you need

- A Linux server with Docker and the Compose plugin, 4 GB RAM or more (scans run a headless browser)
- A domain pointing at the server
- An Anthropic API key (test cases, automation scripts and report summaries are written with it)

## First deploy

```bash
cd access-qa-360
cp .env.production.example .env.production
# fill in APP_URL, DOMAIN, POSTGRES_PASSWORD, both database URLs, SECRET_KEY,
# ANTHROPIC_API_KEY, SUPER_ADMIN_EMAILS and CORS_ORIGINS
./deploy.sh --tls        # on a plain server: Caddy gets an HTTPS certificate for DOMAIN
./deploy.sh              # behind a platform or proxy that already handles HTTPS
```

`deploy.sh` checks the settings, builds the images, applies database migrations, starts everything and waits for the API to report healthy. It prints the logs if that fails.

Then open the app, sign up with an address listed in `SUPER_ADMIN_EMAILS`, and you have the admin console.

## Updating

```bash
git pull
./deploy.sh        # add --tls if you used it before
```

Migrations run automatically before the new API starts.

## Dokploy, Coolify and similar platforms

These already route domains and handle HTTPS, so do not use `--tls`.

1. Create a **Compose** application pointing at this repository, compose path `access-qa-360/docker-compose.prod.yml`.
2. Paste the contents of your filled-in `.env.production` into the platform's environment settings. The compose file reads `.env.production`, so also save it as a file mount at `access-qa-360/.env.production` if the platform separates the two.
3. Add your domain to the `web` service, container port `80`.
4. Deploy.

To use a database the platform already provides instead of the bundled one, point `DATABASE_URL` and `SYNC_DATABASE_URL` at it. It must be Postgres with the `vector` extension available (the `pgvector/pgvector` image has it).

## What to back up

- The `pgdata` volume: every account, scan and result
- The `storage` volume: uploaded mobile builds and generated PDF reports

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml exec -T db \
  pg_dump -U wiseflow wiseflow | gzip > wiseflow-$(date +%F).sql.gz
```

## Settings worth knowing

| Setting | What it does |
| --- | --- |
| `APP_URL` | Public address. Password reset and invitation links are built from it. |
| `SUPER_ADMIN_EMAILS` | These accounts become super admin on sign-up or sign-in. |
| `SMTP_*` | Outgoing email. Without it, reset links are created by a super admin and invite links are copied by hand. |
| `WEB_PORT` | Port the app listens on when HTTPS is handled elsewhere. Default 8080. |
| `MAX_UPLOAD_MB` | Largest upload. If you raise it past 350, raise `client_max_body_size` in `frontend/nginx.conf` too. |

## Checking it is healthy

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml ps
curl -fsS http://localhost:8080/            # the web app, from the server
docker compose --env-file .env.production -f docker-compose.prod.yml logs -f api
```

## Known limits

- Scans run inside the API process. Restarting the API while a scan is running stops that scan; start it again from the app.
- Run one API container. Several would each work, but a scan belongs to the container that started it.
