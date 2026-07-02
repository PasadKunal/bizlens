-- Read-only analyst role + row-level security scaffolding.
-- Runs automatically on first container start (docker-entrypoint-initdb.d).
--
-- The core safety guarantee of BizLens: every analytics query executes under a
-- role that can only SELECT. No analytical path can mutate or drop data.

-- 1. Read-only analyst role used by ANALYST_DATABASE_URL.
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'bizlens_readonly') THEN
        CREATE ROLE bizlens_readonly LOGIN PASSWORD 'readonly';
    END IF;
END
$$;

GRANT CONNECT ON DATABASE bizlens TO bizlens_readonly;
GRANT USAGE ON SCHEMA public TO bizlens_readonly;

-- SELECT on all existing and future tables; nothing else.
GRANT SELECT ON ALL TABLES IN SCHEMA public TO bizlens_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO bizlens_readonly;

-- Explicitly ensure no write privileges leak in.
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA public FROM bizlens_readonly;

-- 2. Enable pgvector for the NL-to-SQL embedding store.
CREATE EXTENSION IF NOT EXISTS vector;

-- 3. Row-level security example (per-tenant isolation).
-- Enable and define policies per table once tenant columns exist, e.g.:
--   ALTER TABLE events ENABLE ROW LEVEL SECURITY;
--   CREATE POLICY tenant_isolation ON events
--       USING (tenant_id = current_setting('bizlens.tenant_id')::text);
