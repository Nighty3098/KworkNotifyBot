DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'kwork_user') THEN
        CREATE USER kwork_user WITH PASSWORD 'password';
        GRANT ALL PRIVILEGES ON DATABASE kwork_bot TO kwork_user;
        ALTER USER kwork_user WITH SUPERUSER;
    END IF;
END
$$;

GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO kwork_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO kwork_user;
