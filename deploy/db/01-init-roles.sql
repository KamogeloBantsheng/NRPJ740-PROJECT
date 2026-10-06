-- 01-init-roles.sql
-- Initializes owner and application runtime roles for NPRJ740 Maintenance System

-- 1. Create owner role (runs migrations, owns tables and schema)
DO
$$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'nrpj_owner') THEN
        CREATE ROLE nrpj_owner WITH LOGIN PASSWORD 'change-me-owner-secret';
    END IF;
END
$$;

-- 2. Create application runtime role (restricted privileges)
DO
$$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'nrpj_app') THEN
        CREATE ROLE nrpj_app WITH LOGIN PASSWORD 'change-me-app-secret';
    END IF;
END
$$;

-- 3. Database connection and schema ownership grants
GRANT CONNECT ON DATABASE nrpj740_dev TO nrpj_owner;
GRANT CONNECT ON DATABASE nrpj740_dev TO nrpj_app;

-- Grant schema privileges
GRANT USAGE, CREATE ON SCHEMA public TO nrpj_owner;
GRANT USAGE ON SCHEMA public TO nrpj_app;

-- Ensure owner owns the public schema
ALTER SCHEMA public OWNER TO nrpj_owner;

-- 4. Default privileges for future tables and sequences created by owner
ALTER DEFAULT PRIVILEGES FOR ROLE nrpj_owner IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO nrpj_app;

ALTER DEFAULT PRIVILEGES FOR ROLE nrpj_owner IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO nrpj_app;
