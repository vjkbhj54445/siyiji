"""模块说明：RSS 抓取脚本。"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import feedparser
import requests


def main():
    p = argparse.ArgumentParser(description="Fetch an RSS feed and save JSON + Markdown summary")
    p.add_argument("--url", default="https://www.people.com.cn/rss/politics.xml", help="RSS URL")
    p.add_argument("--limit", type=int, default=10, help="Max items")
    p.add_argument("--out-dir", default="/data/rss", help="Output dir")
    args = p.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    resp = requests.get(args.url, timeout=15, headers={"User-Agent": "automation-hub/0.1"})
    resp.raise_for_status()

    feed = feedparser.parse(resp.content)

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    json_path = out_dir / f"rss-{ts}.json"
    md_path = out_dir / f"rss-{ts}.md"

    items = []
    for e in feed.entries[: args.limit]:
        item = {
            "title": getattr(e, "title", ""),
            "link": getattr(e, "link", ""),
            "published": getattr(e, "published", ""),
            "summary": getattr(e, "summary", "")[:300],
        }
        items.append(item)

    json_path.write_text(
        json.dumps(
            {
                "feed_title": getattr(feed.feed, "title", ""),
                "feed_link": getattr(feed.feed, "link", ""),
                "url": args.url,
                "items": items,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    lines = []
    lines.append(f"# RSS 摘要 - {getattr(feed.feed, 'title', '')}")
    lines.append(f"- source: {args.url}")
    lines.append("")
    for i, it in enumerate(items, 1):
        lines.append(f"## {i}. {it['title']}")
        if it["published"]:
            lines.append(f"- published: {it['published']}")
        if it["link"]:
            lines.append(f"- link: {it['link']}")
        lines.append("")

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"OK: wrote {json_path}")
    print(f"OK: wrote {md_path}")
    
    # 打印RSS条目摘要到标准输出
    print("\n--- RSS 内容摘要 ---")
    print(f"Feed Title: {getattr(feed.feed, 'title', '')}")
    print(f"Feed Link: {getattr(feed.feed, 'link', '')}")
    print(f"Total Entries: {len(feed.entries)}")
    print(f"Fetched {len(items)} entries (limited by --limit={args.limit}):")
    print()
    for i, item in enumerate(items, 1):
        print(f"{i}. {item['title']}")
        if item['published']:
            print(f"   发布时间: {item['published']}")
        if item['link']:
            print(f"   链接: {item['link']}")
        if item['summary']:
            print(f"   摘要: {item['summary'][:100]}...")
        print()


if __name__ == "__main__":
    main()