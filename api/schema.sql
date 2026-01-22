-- 模块说明：API 数据库表结构定义。
-- 数据库表结构定义

-- 脚本表
CREATE TABLE IF NOT EXISTS scripts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 任务表
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    script_name TEXT NOT NULL,
    parameters TEXT,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    scheduled_time TIMESTAMP,
    completed_at TIMESTAMP,
    FOREIGN KEY (script_name) REFERENCES scripts (name)
);

-- 运行记录表
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT UNIQUE NOT NULL,
    script_name TEXT NOT NULL,
    parameters TEXT,
    status TEXT DEFAULT 'queued',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    log_file_path TEXT,
    result TEXT,
    error_msg TEXT,
    FOREIGN KEY (script_name) REFERENCES scripts (name)
);

-- 新增：认证、工具、审批、审计、提案与仓库索引相关表

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS devices (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    name TEXT NOT NULL,
    platform TEXT NOT NULL,
    created_at TEXT NOT NULL,
    last_seen_at TEXT,
    FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS api_tokens (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    device_id TEXT,
    token_hash TEXT NOT NULL,
    scopes TEXT NOT NULL DEFAULT '[]',
    expires_at TEXT,
    created_at TEXT NOT NULL,
    revoked_at TEXT,
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(device_id) REFERENCES devices(id)
);

CREATE INDEX IF NOT EXISTS idx_tokens_user ON api_tokens(user_id);

CREATE TABLE IF NOT EXISTS tools (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    risk_level TEXT NOT NULL,
    executor TEXT NOT NULL,
    args_schema_json TEXT NOT NULL,
    command_json TEXT NOT NULL,
    cwd TEXT,
    timeout_sec INTEGER NOT NULL DEFAULT 120,
    allowed_paths_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    is_enabled INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS tool_versions (
    id TEXT PRIMARY KEY,
    tool_id TEXT NOT NULL,
    version TEXT NOT NULL,
    spec_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(tool_id) REFERENCES tools(id)
);

CREATE INDEX IF NOT EXISTS idx_tools_enabled ON tools(is_enabled);

-- 工具运行表（Tool Runs）：记录基于 tools 表的每次工具执行
CREATE TABLE IF NOT EXISTS tool_runs (
    id TEXT PRIMARY KEY,                  -- run_id
    tool_id TEXT NOT NULL,
    args_json TEXT NOT NULL,              -- JSON
    status TEXT NOT NULL,                 -- queued/pending_approval/running/succeeded/failed/denied/blocked
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    exit_code INTEGER,
    stdout_path TEXT,
    stderr_path TEXT,
    result_json TEXT,
    error_msg TEXT,
    created_by_user_id TEXT,
    approval_request_id TEXT,
    FOREIGN KEY(tool_id) REFERENCES tools(id),
    FOREIGN KEY(created_by_user_id) REFERENCES users(id),
    FOREIGN KEY(approval_request_id) REFERENCES approval_requests(id)
);

CREATE INDEX IF NOT EXISTS idx_tool_runs_tool ON tool_runs(tool_id);
CREATE INDEX IF NOT EXISTS idx_tool_runs_status ON tool_runs(status);
CREATE INDEX IF NOT EXISTS idx_tool_runs_created_at ON tool_runs(created_at);

CREATE TABLE IF NOT EXISTS approval_requests (
    id TEXT PRIMARY KEY,
    created_by_user_id TEXT NOT NULL,
    created_by_device_id TEXT,
    resource_type TEXT NOT NULL,
    resource_id TEXT NOT NULL,
    action TEXT NOT NULL,
    risk_level TEXT NOT NULL,
    request_reason TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    decided_at TEXT,
    decided_by_user_id TEXT,
    decision_note TEXT,
    FOREIGN KEY(created_by_user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_approvals_status ON approval_requests(status);

CREATE TABLE IF NOT EXISTS audit_events (
    id TEXT PRIMARY KEY,
    actor_user_id TEXT,
    actor_device_id TEXT,
    event_type TEXT NOT NULL,
    resource_type TEXT,
    resource_id TEXT,
    action TEXT NOT NULL,
    status TEXT NOT NULL,
    message TEXT,
    meta_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_audit_time ON audit_events(created_at);

CREATE TABLE IF NOT EXISTS proposals (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    plan_md TEXT NOT NULL,
    patch_diff TEXT,
    verify_commands_json TEXT NOT NULL DEFAULT '[]',
    risk_level TEXT NOT NULL,
    status TEXT NOT NULL,
    target_repo_id TEXT,
    created_by_user_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    applied_at TEXT,
    FOREIGN KEY(created_by_user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_proposals_status ON proposals(status);

CREATE TABLE IF NOT EXISTS repos (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    root_path TEXT NOT NULL,
    created_at TEXT NOT NULL,
    last_indexed_at TEXT
);

CREATE TABLE IF NOT EXISTS repo_files (
    id TEXT PRIMARY KEY,
    repo_id TEXT NOT NULL,
    path TEXT NOT NULL,
    mtime INTEGER NOT NULL,
    size INTEGER NOT NULL,
    sha256 TEXT NOT NULL,
    FOREIGN KEY(repo_id) REFERENCES repos(id)
);

CREATE INDEX IF NOT EXISTS idx_repo_files_repo ON repo_files(repo_id);