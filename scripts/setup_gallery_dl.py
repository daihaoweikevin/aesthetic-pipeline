#!/usr/bin/env python3
"""
配置 gallery-dl 用于 Pixiv 认证
支持: 用户名+密码 (推荐) / Cookie (备选)
"""
import json, os, sys
from pathlib import Path

def main():
    pixiv_user = os.environ.get("PIXIV_USERNAME", "")
    pixiv_pass = os.environ.get("PIXIV_PASSWORD", "")
    pixiv_cookie = os.environ.get("PIXIV_COOKIE", "")

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

    # 方式1: 用户名+密码（推荐，最简单）
    if pixiv_user and pixiv_pass:
        config["extractor"]["pixiv"] = {
            "username": pixiv_user,
            "password": pixiv_pass,
            "metadata": True,
            "tags": "japanese",
        }
        print(f"✅ Pixiv: 用户名+密码认证 ({pixiv_user})")

    # 方式2: Cookie（备选）
    elif pixiv_cookie:
        config["extractor"]["pixiv"] = {
            "cookies": pixiv_cookie,
            "metadata": True,
            "tags": "japanese",
        }
        print(f"✅ Pixiv: Cookie 认证 ({len(pixiv_cookie)} 字符)")

    else:
        print("⚠️  未配置 Pixiv 认证，跳过 Pixiv")

    print("✅ Wallhaven: 已启用")
    print("✅ Danbooru: 已启用")

    config_path = Path.home() / ".gallery-dl" / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    print(f"📁 配置已写入 {config_path}")


if __name__ == "__main__":
    main()
