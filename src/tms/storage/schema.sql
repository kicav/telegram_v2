PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phone TEXT NOT NULL UNIQUE,
    telegram_user_id INTEGER,
    username TEXT,
    display_name TEXT,
    session_path TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'DISCONNECTED',
    enabled INTEGER NOT NULL DEFAULT 1,
    last_connected_at TEXT,
    last_error TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS peer_cache (
    account_id INTEGER NOT NULL,
    peer_id INTEGER NOT NULL,
    peer_type TEXT NOT NULL,
    access_hash INTEGER,
    username TEXT,
    title TEXT,
    cached_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (account_id, peer_id),
    FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_peer_id INTEGER NOT NULL UNIQUE,
    type TEXT NOT NULL,
    username TEXT,
    title TEXT NOT NULL,
    last_known_member_count INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_user_id INTEGER UNIQUE,
    username TEXT,
    first_name TEXT,
    last_name TEXT,
    phone TEXT,
    bot INTEGER NOT NULL DEFAULT 0,
    deleted INTEGER NOT NULL DEFAULT 0,
    activity_status TEXT,
    last_seen TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_members_username_fallback_unique
ON members(lower(username))
WHERE telegram_user_id IS NULL AND username IS NOT NULL AND trim(username) <> '';

CREATE TABLE IF NOT EXISTS datasets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_reference TEXT,
    status TEXT NOT NULL DEFAULT 'READY',
    member_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS dataset_members (
    dataset_id INTEGER NOT NULL,
    member_id INTEGER NOT NULL,
    source_group_id INTEGER,
    collected_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (dataset_id, member_id),
    FOREIGN KEY (dataset_id) REFERENCES datasets(id) ON DELETE CASCADE,
    FOREIGN KEY (member_id) REFERENCES members(id) ON DELETE CASCADE,
    FOREIGN KEY (source_group_id) REFERENCES groups(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS dataset_provenance (
    dataset_id INTEGER NOT NULL,
    member_id INTEGER NOT NULL,
    source_dataset_id INTEGER,
    source_group_id INTEGER,
    source_label TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(dataset_id, member_id, source_dataset_id, source_group_id, source_label),
    FOREIGN KEY (dataset_id) REFERENCES datasets(id) ON DELETE CASCADE,
    FOREIGN KEY (member_id) REFERENCES members(id) ON DELETE CASCADE,
    FOREIGN KEY (source_dataset_id) REFERENCES datasets(id) ON DELETE SET NULL,
    FOREIGN KEY (source_group_id) REFERENCES groups(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_type TEXT NOT NULL,
    state TEXT NOT NULL,
    account_id INTEGER,
    source_dataset_id INTEGER,
    target_group_id INTEGER,
    total INTEGER NOT NULL DEFAULT 0,
    processed INTEGER NOT NULL DEFAULT 0,
    success INTEGER NOT NULL DEFAULT 0,
    skipped INTEGER NOT NULL DEFAULT 0,
    failed INTEGER NOT NULL DEFAULT 0,
    waiting_until TEXT,
    checkpoint_json TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at TEXT,
    finished_at TEXT,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES accounts(id),
    FOREIGN KEY (source_dataset_id) REFERENCES datasets(id),
    FOREIGN KEY (target_group_id) REFERENCES groups(id)
);

CREATE TABLE IF NOT EXISTS migration_items (
    job_id INTEGER NOT NULL,
    ordinal INTEGER NOT NULL,
    member_id INTEGER NOT NULL,
    target_state TEXT NOT NULL DEFAULT 'KNOWN_ABSENT',
    state TEXT NOT NULL DEFAULT 'READY',
    attempt_count INTEGER NOT NULL DEFAULT 0,
    last_error_code TEXT,
    last_error_text TEXT,
    next_retry_at TEXT,
    processed_at TEXT,
    PRIMARY KEY (job_id, ordinal),
    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE,
    FOREIGN KEY (member_id) REFERENCES members(id)
);

CREATE TABLE IF NOT EXISTS job_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    timestamp TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    level TEXT NOT NULL,
    event_code TEXT NOT NULL,
    member_id INTEGER,
    message TEXT,
    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_members_telegram_user_id ON members(telegram_user_id);
CREATE INDEX IF NOT EXISTS idx_dataset_members_dataset_member ON dataset_members(dataset_id, member_id);
CREATE INDEX IF NOT EXISTS idx_dataset_provenance_dataset_member ON dataset_provenance(dataset_id, member_id);
CREATE INDEX IF NOT EXISTS idx_peer_cache_account_peer ON peer_cache(account_id, peer_id);
CREATE INDEX IF NOT EXISTS idx_jobs_state_updated ON jobs(state, updated_at);
CREATE INDEX IF NOT EXISTS idx_migration_items_job_state_ordinal ON migration_items(job_id, state, ordinal);
CREATE INDEX IF NOT EXISTS idx_job_events_job_timestamp ON job_events(job_id, timestamp);
