#!/usr/bin/env python3
"""
配置 gallery-dl 用于 Pixiv 认证
从 GitHub Secrets 读取 cookie，生成 gallery-dl 配置文件
"""
import json, os, sys
from pathlib import Path

def main():
    pixiv_cookie = os.environ.get("PIXIV_COOKIE", "")
    
    if not pixiv_cookie:
        print("⚠️  PIXIV_COOKIE 未设置，无法配置 Pixiv")
        # 生成最小配置文件（仅 Wallhaven + Danbooru）
        config = {
            "extractor": {
                "wallhaven": {
                    "metadata": True,
                },
                "danbooru": {
                    "metadata": True,
                },
            },
            "downloader": {
                "part": False,
                "rate": "2M",
            }
        }
    else:
        config = {
            "extractor": {
                "pixiv": {
                    "cookies": pixiv_cookie,
                    "metadata": True,
                    "tags": "japanese",
                },
                "wallhaven": {
                    "metadata": True,
                },
                "danbooru": {
                    "metadata": True,
                },
            },
            "downloader": {
                "part": False,
                "rate": "2M",
            }
        }
    
    config_path = Path.home() / ".gallery-dl" / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    
    print(f"✅ gallery-dl 配置已写入 {config_path}")
    if pixiv_cookie:
        print(f"   Pixiv: 已配置 Cookie ({len(pixiv_cookie)} 字符)")
    print(f"   Wallhaven: 已启用")
    print(f"   Danbooru: 已启用")


if __name__ == "__main__":
    main()
