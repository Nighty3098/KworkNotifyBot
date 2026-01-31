CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    user_id BIGINT UNIQUE NOT NULL,
    username VARCHAR(100),
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    is_admin BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
);

CREATE TABLE IF NOT EXISTS processed_projects (
    id SERIAL PRIMARY KEY,
    project_id VARCHAR(100) UNIQUE NOT NULL,
    title VARCHAR(500),
    price VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS monitoring_settings (
    id SERIAL PRIMARY KEY,
    chat_id BIGINT UNIQUE NOT NULL,
    is_active BOOLEAN DEFAULT FALSE,
    last_check TIMESTAMP,
    check_interval INTEGER DEFAULT 120,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_pp_created ON processed_projects(created_at);
CREATE INDEX IF NOT EXISTS idx_users_id ON users(user_id);
CREATE INDEX IF NOT EXISTS idx_monitoring_chat ON monitoring_settings(chat_id);
