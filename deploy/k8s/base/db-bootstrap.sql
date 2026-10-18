-- Idempotent role bootstrap for scheduler-service (ADR-007 §3). Runs as the RDS master user in the
-- db-bootstrap init container of job/scheduler-db-migrate, before Flyway, on every deploy.
-- psql variables (-v): owner_user owner_password app_user app_password dbname
\set ON_ERROR_STOP on

-- 1. roles exist (CREATE ROLE has no IF NOT EXISTS → \gexec)
SELECT format('CREATE ROLE %I LOGIN', :'owner_user')
 WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'owner_user') \gexec
SELECT format('CREATE ROLE %I LOGIN', :'app_user')
 WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'app_user') \gexec

-- 2. passwords always match Secrets Manager (rotation = new random_password + redeploy)
ALTER ROLE :"owner_user" WITH LOGIN PASSWORD :'owner_password';
ALTER ROLE :"app_user"   WITH LOGIN PASSWORD :'app_password';   -- created without CREATEDB/CREATEROLE

-- 3. master may act as the owner (needed for schema ownership + default privileges; PG16 semantics)
SELECT format('GRANT %I TO CURRENT_USER WITH INHERIT TRUE, SET TRUE', :'owner_user')
 WHERE NOT pg_has_role(current_user, :'owner_user', 'SET') \gexec

-- 4. database and schema privileges
GRANT CONNECT ON DATABASE :"dbname" TO :"owner_user", :"app_user";
GRANT CREATE  ON DATABASE :"dbname" TO :"owner_user";        -- CREATE EXTENSION btree_gist (trusted)
ALTER SCHEMA public OWNER TO :"owner_user";
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO :"app_user";

-- 5. API role: DML only, on existing and future tables (NFR-08 least privilege)
SET ROLE :"owner_user";
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO :"app_user";
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE ON TABLES TO :"app_user";
RESET ROLE;

SELECT 'db-bootstrap complete' AS status;
