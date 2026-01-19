CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    script_name TEXT NOT NULL,
    parameters TEXT,
    status TEXT,
    start_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    end_time DATETIME,
    output_path TEXT,
    -- 审计字段
    triggered_by TEXT DEFAULT 'system',
    result_status TEXT CHECK(result_status IN ('success', 'failure')), -- 结果状态
    failure_type TEXT CHECK(failure_type IN ('timeout', 'nonzero', 'exception')), -- 失败类型
    -- 元数据
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 创建索引优化查询性能
CREATE INDEX IF NOT EXISTS idx_runs_script_name ON runs(script_name);
CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status);
CREATE INDEX IF NOT EXISTS idx_runs_triggered_by ON runs(triggered_by);
CREATE INDEX IF NOT EXISTS idx_runs_failure_type ON runs(failure_type);