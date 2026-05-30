#!/usr/bin/env python3
"""更新采集日志"""
import json, os
from pathlib import Path
from datetime import datetime

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

def update_log(scored_file):
    with open(scored_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    log_entry = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "total": data.get("total", 0),
        "s_count": data.get("grade_distribution", {}).get("S", 0),
        "a_count": data.get("grade_distribution", {}).get("A", 0),
        "b_count": data.get("grade_distribution", {}).get("B", 0),
        "top_score": data.get("top_score", 0),
        "sources": data.get("sources", {}),
    }
    
    log_file = LOG_DIR / "history.json"
    history = []
    if log_file.exists():
        with open(log_file, "r") as f:
            history = json.load(f)
    
    history.append(log_entry)
    
    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    
    # 生成 Markdown 摘要
    md_file = LOG_DIR / "README.md"
    lines = [
        "# 📊 Aesthetic Lens 采集日志\n",
        f"最后更新: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n",
        "| 日期 | 总数 | S级 | A级 | B级 | 最高分 |",
        "|------|------|-----|-----|-----|--------|",
    ]
    for entry in reversed(history[-20:]):
        lines.append(
            f"| {entry['date']} | {entry['total']} | {entry['s_count']} | "
            f"{entry['a_count']} | {entry['b_count']} | {entry['top_score']} |"
        )
    
    with open(md_file, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    
    print(f"📊 日志已更新: {log_file}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        update_log(sys.argv[1])
    else:
        print("用法: python3 update_log.py scored_results.json")
