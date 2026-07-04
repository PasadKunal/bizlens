# Deploying BizLens for free

This hosts the whole app (dashboard + API) at $0 and keeps it up:

- **Database:** [Neon](https://neon.tech) free Postgres (has pgvector, does not expire)
- **Web:** [Render](https://render.com) free web services (deploy straight from GitHub)
- **Redis:** none needed. Caching is optional and falls back to recompute.

You need two free accounts (Neon, Render). No credit card, no charges.

Free-tier note: Render free web services sleep after ~15 min idle, so the first
visit after a nap takes ~50s to wake. Fine for a portfolio demo.

---

## 1. Create the database (Neon)

1. Sign up at neon.tech and create a project (any region).
2. Copy the connection string. It looks like:
   ```
   postgresql://myuser:mypass@ep-xxx-123.us-east-2.aws.neon.tech/neondb?sslmode=require
   ```
3. BizLens uses the psycopg driver, so change the scheme `postgresql://` to
   `postgresql+psycopg://`. That is your **DATABASE_URL**:
   ```
   postgresql+psycopg://myuser:mypass@ep-xxx-123.us-east-2.aws.neon.tech/neondb?sslmode=require
   ```
   Use Neon's **direct** endpoint (the host without `-pooler`) for correct
   session-level behaviour (the read-only role and RLS scope).

Also pick a **strong** password for the read-only role (managed hosts like Neon
reject weak ones). Call it `RO_PASSWORD`, e.g. `Bz7xQr2Lp9Km-2026`. Your
**ANALYST_DATABASE_URL** is the same host and db with the read-only user and that
password:
```
postgresql+psycopg://bizlens_readonly:RO_PASSWORD@ep-xxx-123.us-east-2.aws.neon.tech/neondb?sslmode=require
```
(The seed in Step 2 creates that `bizlens_readonly` role with that password.)

## 2. Seed the database once (from your machine)

The seed creates the read-only role, loads a synthetic dataset, applies
row-level security, and builds the NL-to-SQL embeddings. Run it locally pointed
at Neon (with `blvenv` active):

```bash
export DATABASE_URL="postgresql+psycopg://myuser:mypass@ep-xxx-123.us-east-2.aws.neon.tech/neondb?sslmode=require"
# strong password for the read-only role the seed creates (managed hosts
# reject weak ones); this must match ANALYST_DATABASE_URL below:
export ANALYST_DB_PASSWORD="Bz7xQr2Lp9Km-2026"
export ANALYST_DATABASE_URL="postgresql+psycopg://bizlens_readonly:Bz7xQr2Lp9Km-2026@ep-xxx-123.us-east-2.aws.neon.tech/neondb?sslmode=require"
export REDIS_URL=""

python -m scripts.deploy_seed
```

You should see it initialise the DB, load ~5k users / 49k events, apply RLS, and
index the query templates. Re-run this any time to reset the demo data.

> If Neon rejects `CREATE ROLE`, create the role once in the Neon SQL editor
> (use the same strong password), then re-run the seed:
> `CREATE ROLE bizlens_readonly LOGIN PASSWORD 'Bz7xQr2Lp9Km-2026';`

## 3. Deploy the web services (Render)

1. Sign up at render.com and click **New > Blueprint**.
2. Connect this GitHub repo. Render reads [`render.yaml`](render.yaml) and
   proposes two free web services: `bizlens-dashboard` and `bizlens-api`.
3. Before the first deploy, set the two secret env vars on **both** services
   (they are marked "sync: false", so Render asks you for them):
   - `DATABASE_URL` - the value from step 1
   - `ANALYST_DATABASE_URL` - the read-only value from step 2
4. Click **Apply** / **Deploy** and wait for the Docker build.

That's it. Your URLs will be:

- Dashboard: `https://bizlens-dashboard.onrender.com`
- API docs:  `https://bizlens-api.onrender.com/docs`

## 4. Try the live demo

- Open the dashboard URL. Use the NL-to-SQL box, e.g. *"revenue by segment"*.
- API: get a token and run a sandboxed query:
  ```bash
  API=https://bizlens-api.onrender.com
  TOKEN=$(curl -s -X POST $API/auth/token -d 'username=analyst&password=analyst' | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
  curl -s $API/kpi/cards | python3 -m json.tool
  ```
- Row-level security demo: log in as `analyst_br` instead of `analyst` and every
  query is filtered to Brazil only, enforced by Postgres.

## Notes

- **Security:** the demo login (`analyst`/`analyst`) and a read-only, sandboxed
  SQL box are internet-facing. That is intentional for a portfolio demo on
  throwaway synthetic data. Do not point this at real data as-is.
- **No Redis:** with `REDIS_URL` empty the app recomputes instead of caching.
  To add caching later, set `REDIS_URL` to a free [Upstash](https://upstash.com)
  Redis URL.
- **Custom README badge:** once live, add your dashboard link to the top of the
  README so recruiters can click straight through.
