# AXISS QA — Coming Soon

A minimal, deployable skeleton for AXISS QA: **React Native (Expo) frontend + Express API + PostgreSQL**, with a live "coming soon" page and an email waitlist that actually writes to the database.

- **Frontend** — Expo / React Native (TypeScript). Runs on iOS, Android and the web from one codebase.
- **Backend** — Express 5 REST API with a health check.
- **Database** — PostgreSQL. Schema is applied automatically on boot (idempotent).
- **Deploy** — One `Dockerfile` per service, ready for Dokploy/Dockply, Coolify, Render, Fly.io, etc.

---

## Project structure

```
AXISS-QA/
├── backend/
│   ├── src/
│   │   ├── config.js          # env parsing
│   │   ├── db.js              # pg pool + helpers
│   │   ├── index.js           # express app, graceful shutdown
│   │   ├── migrate.js         # applies schema.sql on boot
│   │   ├── schema.sql         # waitlist + app_meta tables
│   │   └── routes/
│   │       ├── health.js      # GET /api/health
│   │       └── waitlist.js    # POST /api/waitlist, GET /api/waitlist/count
│   ├── Dockerfile
│   └── .env.example
├── frontend/
│   ├── App.tsx
│   ├── src/
│   │   ├── screens/ComingSoonScreen.tsx
│   │   ├── components/WaitlistForm.tsx
│   │   ├── lib/api.ts         # typed API client
│   │   └── theme.ts           # colors / spacing tokens
│   ├── nginx.conf             # SPA + asset caching
│   └── Dockerfile             # Expo web export -> nginx
└── docker-compose.yml         # local full stack
```

---

## API

| Method | Route                  | Description                                   |
| ------ | ---------------------- | --------------------------------------------- |
| GET    | `/api/health`          | `{ status, db, uptime }` — 503 if DB is down  |
| POST   | `/api/waitlist`        | `{ email }` → adds to waitlist (idempotent)   |
| GET    | `/api/waitlist/count`  | `{ count }` — number of signups               |

```bash
curl -X POST http://localhost:3000/api/waitlist \
  -H 'Content-Type: application/json' \
  -d '{"email":"you@company.com"}'
```

---

## Local development

### Option A — everything in Docker

```bash
docker compose up --build
```

- Web: http://localhost:8080
- API: http://localhost:3000/api/health
- Postgres: `localhost:5432` (`postgres` / `postgres`, db `axiss_qa`)

### Option B — run each piece with Node

```bash
# 1. Backend
cd backend
cp .env.example .env        # then set DATABASE_URL
npm install
npm run dev                 # http://localhost:3000

# 2. Frontend (new terminal)
cd frontend
cp .env.example .env        # EXPO_PUBLIC_API_URL=http://localhost:3000
npm install
npm run web                 # http://localhost:8081
```

`npm run ios` / `npm run android` open the same app in a simulator or Expo Go.

> `EXPO_PUBLIC_API_URL` is inlined at build time. Change it → rebuild/restart Expo.

---

## Environment variables

### Backend

| Variable        | Required | Default       | Notes                                              |
| --------------- | -------- | ------------- | -------------------------------------------------- |
| `DATABASE_URL`  | yes      | —             | `postgresql://user:pass@host:5432/db`              |
| `DATABASE_SSL`  | no       | `false`       | Set `true` for managed Postgres that requires TLS   |
| `PORT`          | no       | `3000`        |                                                    |
| `CORS_ORIGIN`   | no       | `*`           | Comma separated origins, e.g. `https://app.site.com` |

### Frontend

| Variable               | Required | Default                 | Notes                          |
| ---------------------- | -------- | ----------------------- | ------------------------------ |
| `EXPO_PUBLIC_API_URL`  | no       | `http://localhost:3000` | Public base URL of the API     |

---

## Deploying on Dokploy / Dockply

Two apps, one repository. Both use the Dockerfile inside their own subdirectory.

> Dokploy joins **Build Path + Docker File** to locate the Dockerfile, but resolves **Docker Context Path** from the repo root. So the values below are not the same for every field.

### 1. API

| Setting            | Value                |
| ------------------ | -------------------- |
| Build Type         | Dockerfile           |
| Build Path         | `backend`            |
| Docker File        | `Dockerfile`         |
| Docker Context Path| `backend`            |
| Watch Paths        | `backend/**`         |
| Trigger Type       | On Push              |
| Container port     | `3000`               |
| Health check       | `/api/health`        |

Environment (runtime):

```env
DATABASE_URL=postgresql://postgres:<password>@<db-service-host>:5432/<database>
DATABASE_SSL=false
CORS_ORIGIN=https://<your-frontend-domain>
```

The schema is created on boot, so no manual migration step is needed. To run it by hand: `npm run db:init`.

### 2. Web (coming soon page)

| Setting            | Value                |
| ------------------ | -------------------- |
| Build Type         | Dockerfile           |
| Build Path         | `frontend`           |
| Docker File        | `Dockerfile`         |
| Docker Context Path| `frontend`           |
| Watch Paths        | `frontend/**`        |
| Trigger Type       | On Push              |
| Container port     | `80`                 |

**Environment tab → Build Time Arguments** (not runtime variables):

```env
EXPO_PUBLIC_API_URL=https://<your-api-domain>
```

> The API URL is baked into the static bundle. If you change it, trigger a rebuild.
> If you'd rather avoid a public API domain, point `EXPO_PUBLIC_API_URL` at a path on the same domain and proxy `/api` from the web container to the API container.

### 3. Database

The database in Dokploy is already provisioned. Copy its **internal** connection string into `DATABASE_URL` on the API app. The hostname (`axissqa-...`) only resolves inside the platform network — it will not connect from your laptop.

---

## Notes / next steps

- **Secrets**: `backend/.env` is gitignored. Set the real values in the platform dashboard, not in the repo.
- **Migrations**: `schema.sql` is idempotent (`IF NOT EXISTS`). Bring a real migration tool (Drizzle, Prisma, node-pg-migrate) when the schema grows.
- **Rate limiting**: the public `POST /api/waitlist` has no throttling yet — add `express-rate-limit` before launch.
- **CORS**: set `CORS_ORIGIN` to your frontend domain in production instead of `*`.
- **Mobile builds**: `npx expo prebuild` + EAS for real App Store / Play Store binaries.
