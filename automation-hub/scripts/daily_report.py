from __future__ import annotations

import argparse
import os
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = os.environ.get("DATABASE_PATH", "/data/automation_hub.sqlite3")


def fetch_recent_runs(limit: int = 10):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.execute(
            "SELECT id, script_id, status, created_at, started_at, finished_at, exit_code FROM runs ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def disk_usage(path: str = "/data"):
    p = Path(path)
    usage = os.statvfs(str(p))
    total = usage.f_frsize * usage.f_blocks
    free = usage.f_frsize * usage.f_bfree
    used = total - free
    return {"path": str(p), "total": total, "used": used, "free": free}


def fmt_bytes(n: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    x = float(n)
    for u in units:
        if x < 1024 or u == units[-1]:
            return f"{x:.2f}{u}"
        x /= 1024
    return f"{x:.2f}B"


def main():
    p = argparse.ArgumentParser(description="Generate a daily Markdown report under /data/reports")
    p.add_argument("--out-dir", default="/data/reports", help="Output directory")
    p.add_argument("--limit", type=int, default=10, help="Recent runs to include")
    args = p.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d")
    report_path = out_dir / f"{today}.md"

    runs = fetch_recent_runs(args.limit)
    du = disk_usage("/data")

    lines = []
    lines.append(f"# Automation Hub 日报 - {today}")
    lines.append("")
    lines.append("## 磁盘使用（/data）")
    lines.append(f"- total: {fmt_bytes(du['total'])}")
    lines.append(f"- used:  {fmt_bytes(du['used'])}")
    lines.append(f"- free:  {fmt_bytes(du['free'])}")
    lines.append("")
    lines.append("## 最近执行记录")
    if not runs:
        lines.append("- 暂无执行记录")
    else:
        lines.append("| time | script | status | exit |")
        lines.append("|---|---|---|---|")
        for r in runs:
            t = (r.get("created_at") or "")[:19]
            lines.append(f"| {t} | {r['script_id']} | {r['status']} | {r.get('exit_code','')} |")

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"OK: wrote {report_path}")


if __name__ == "__main__":
    main()
