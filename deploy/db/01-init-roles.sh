#!/bin/sh
# Creates the owner and application database roles on first start (Section 5.8).
# The official PostgreSQL image runs this once, when the data volume is empty. Passwords and
# the database name come from the environment, so changing them in .env keeps everything in step.
set -eu

psql -v ON_ERROR_STOP=1 \
     --username "$POSTGRES_USER" \
     --dbname "$POSTGRES_DB" \
     --set=db_name="$POSTGRES_DB" \
     --set=owner_password="$DB_OWNER_PASSWORD" \
     --set=app_password="$DB_APP_PASSWORD" <<'SQL'
-- 1. Owner role (runs migrations, owns tables and schema)
SELECT format('CREATE ROLE nrpj_owner WITH LOGIN PASSWORD %L', :'owner_password')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'nrpj_owner')
\gexec

-- 2. Application runtime role (restricted privileges)
SELECT format('CREATE ROLE nrpj_app WITH LOGIN PASSWORD %L', :'app_password')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'nrpj_app')
\gexec

-- 3. Database connection and schema grants
GRANT CONNECT ON DATABASE :"db_name" TO nrpj_owner;
GRANT CONNECT ON DATABASE :"db_name" TO nrpj_app;
GRANT USAGE, CREATE ON SCHEMA public TO nrpj_owner;
GRANT USAGE ON SCHEMA public TO nrpj_app;
ALTER SCHEMA public OWNER TO nrpj_owner;

-- 4. Default privileges for tables and sequences the owner creates later
ALTER DEFAULT PRIVILEGES FOR ROLE nrpj_owner IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO nrpj_app;
ALTER DEFAULT PRIVILEGES FOR ROLE nrpj_owner IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO nrpj_app;
SQL
