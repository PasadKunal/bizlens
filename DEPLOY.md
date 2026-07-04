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

## 2. Seed the database once (from your machine)

The seed creates the read-only role, loads a synthetic dataset, applies
row-level security, and builds the NL-to-SQL embeddings. Run it locally pointed
at Neon (with `blvenv` active):

```bash
export DATABASE_URL="postgresql+psycopg://myuser:mypass@ep-xxx-123.us-east-2.aws.neon.tech/neondb?sslmode=require"
# same host + db, but the read-only role that the seed creates:
export ANALYST_DATABASE_URL="postgresql+psycopg://bizlens_readonly:readonly@ep-xxx-123.us-east-2.aws.neon.tech/neondb?sslmode=require"
export REDIS_URL=""

python -m scripts.deploy_seed
```

You should see it initialise the DB, load ~5k users / 49k events, apply RLS, and
index the query templates. Re-run this any time to reset the demo data.

> If Neon rejects `CREATE ROLE`, create the role once in the Neon SQL editor:
> `CREATE ROLE bizlens_readonly LOGIN PASSWORD 'readonly';` then re-run the seed.

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
