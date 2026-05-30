#!/usr/bin/env python3
"""
Aesthetic Lens Pipeline — 多图源抓取器 v3.0
运行在 GitHub Actions 环境，无沙箱限制
支持: Pixiv, Wallhaven, Danbooru
"""
import json, os, sys, time, hashlib, subprocess
from pathlib import Path
from datetime import datetime

# ─── 配置 ───────────────────────────────────────────
OUTPUT_DIR = Path("downloads")
OUTPUT_DIR.mkdir(exist_ok=True)
WALLPAPER_DIR = OUTPUT_DIR / "wallpaper"
AVATAR_DIR = OUTPUT_DIR / "avatar"
WALLPAPER_DIR.mkdir(exist_ok=True)
AVATAR_DIR.mkdir(exist_ok=True)

# ─── Pixiv 搜索词（日文/英文混合） ─────────────────
PIXIV_WALLPAPER_TAGS = [
    "風景 背景",              # landscape background
    " scenic background",      # scenic background (English)
    "夕焼け 風景",             # sunset landscape
    "空 雲 風景",              # sky clouds landscape
    "森 光 風景",              # forest light landscape
    "新海誠風",                # Shinkai-style
    "ジブリ風 風景",           # Ghibli-style landscape
    "星空 風景",               # starry sky landscape
    "桜 風景",                 # cherry blossom landscape
    "海 夕日 風景",            # sea sunset landscape
]

PIXIV_AVATAR_TAGS = [
    "オリジナル 風景 女の子",  # original landscape girl
    "後ろ姿 風景",             # back view landscape
    " scenic background girl solo",
    "夕焼け 少女 後ろ姿",      # sunset girl back view
    "森 少女 風景",            # forest girl landscape
]

# Wallhaven 搜索关键词
WALLHAVEN_SEARCHES = [
    "anime landscape",
    "anime scenery",
    "digital art landscape",
    "fantasy landscape illustration",
    "scenic wallpaper",
]

# ─── gallery-dl 抓取 ─────────────────────────────────

def fetch_with_gallery_dl(url, target_dir, max_count=20):
    """使用 gallery-dl 抓取"""
    target_dir = Path(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    
    cmd = [
        "gallery-dl",
        "--directory", str(target_dir),
        "--range", f"1-{max_count}",
        "--no-part",  # don't save .part files
        "--abort", "3",  # abort after 3 consecutive skips
        "-q",  # quiet
        url
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0 and "NotFoundError" not in result.stderr:
            print(f"  ⚠️ gallery-dl: {result.stderr[:200]}")
        return True
    except subprocess.TimeoutExpired:
        print(f"  ⏰ 超时: {url}")
        return False
    except Exception as e:
        print(f"  ❌ {e}")
        return False


def fetch_pixiv_search(tag, target_dir, count=15):
    """通过 gallery-dl 搜索 Pixiv"""
    import urllib.parse
    encoded = urllib.parse.quote(tag)
    url = f"https://www.pixiv.net/tags/{encoded}/artworks"
    print(f"  🔍 Pixiv: \"{tag}\"")
    fetch_with_gallery_dl(url, target_dir, count)


def fetch_wallhaven_search(query, target_dir, count=10, api_key=None):
    """通过 gallery-dl 搜索 Wallhaven"""
    import urllib.parse
    encoded = urllib.parse.quote(query)
    url = f"https://wallhaven.cc/search?q={encoded}"
    print(f"  🔍 Wallhaven: \"{query}\"")
    fetch_with_gallery_dl(url, target_dir, count)


def fetch_danbooru_tags(tags, target_dir, count=15):
    """通过 gallery-dl 搜索 Danbooru"""
    import urllib.parse
    encoded = urllib.parse.quote(tags.replace(" ", "+"))
    url = f"https://danbooru.donmai.us/posts?tags={encoded}"
    print(f"  🔍 Danbooru: \"{tags}\"")
    fetch_with_gallery_dl(url, target_dir, count)


# ─── 结果收集 ────────────────────────────────────────

def collect_results():
    """扫描下载目录，生成 metadata JSON"""
    results = []
    
    for dir_path, dir_type in [(WALLPAPER_DIR, "wallpaper"), (AVATAR_DIR, "avatar")]:
        if not dir_path.exists():
            continue
        
        for img_file in dir_path.rglob("*"):
            if not img_file.is_file():
                continue
            suffix = img_file.suffix.lower()
            if suffix not in ('.jpg', '.jpeg', '.png', '.webp'):
                continue
            
            stat = img_file.stat()
            if stat.st_size < 10 * 1024:  # 跳过小于10KB
                continue
            
            # 推断来源
            path_str = str(img_file)
            if "pixiv" in path_str.lower():
                source = "pixiv"
            elif "wallhaven" in path_str.lower():
                source = "wallhaven"
            elif "danbooru" in path_str.lower():
                source = "danbooru"
            else:
                source = "unknown"
            
            results.append({
                "source": source,
                "id": img_file.stem,
                "local_path": str(img_file),  # 绝对路径
                "file_size": stat.st_size,
                "image_type": dir_type,
                "file_ext": suffix,
            })
    
    return results


# ─── 主流程 ──────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Aesthetic Lens Pipeline — 图片抓取器")
    parser.add_argument("--wallpaper-count", type=int, default=30, help="壁纸数量")
    parser.add_argument("--avatar-count", type=int, default=30, help="头像数量")
    args = parser.parse_args()
    
    wp_count = args.wallpaper_count
    av_count = args.avatar_count
    per_query_wp = max(3, wp_count // len(PIXIV_WALLPAPER_TAGS))
    per_query_av = max(3, av_count // len(PIXIV_AVATAR_TAGS))
    per_query_wh = max(2, wp_count // len(WALLHAVEN_SEARCHES))
    
    print(f"\n{'='*60}")
    print(f"🎨 Aesthetic Lens Pipeline v3.0")
    print(f"   目标: 壁纸 {wp_count}张 | 头像 {av_count}张")
    print(f"{'='*60}\n")
    
    total_fetched = {"wallpaper": 0, "avatar": 0}
    
    # ── 阶段1: Pixiv 壁纸 ──
    print("── 📌 Pixiv 壁纸 ──")
    pixiv_ok = os.environ.get("PIXIV_COOKIE", "") or (os.environ.get("PIXIV_USERNAME", "") and os.environ.get("PIXIV_PASSWORD", ""))
    if pixiv_ok:
        for tag in PIXIV_WALLPAPER_TAGS[:8]:
            if total_fetched["wallpaper"] >= wp_count:
                break
            fetch_pixiv_search(tag, WALLPAPER_DIR, per_query_wp)
            total_fetched["wallpaper"] += per_query_wp
            time.sleep(2)
        print(f"   ✅ Pixiv 壁纸: ~{total_fetched['wallpaper']}张\n")
    else:
        print("   ⚠️ 未配置 PIXIV_COOKIE，跳过 Pixiv\n")
    
    # ── 阶段2: Pixiv 头像 ──
    print("── 📌 Pixiv 头像 ──")
    if pixiv_ok:
        for tag in PIXIV_AVATAR_TAGS[:5]:
            if total_fetched["avatar"] >= av_count:
                break
            fetch_pixiv_search(tag, AVATAR_DIR, per_query_av)
            total_fetched["avatar"] += per_query_av
            time.sleep(2)
        print(f"   ✅ Pixiv 头像: ~{total_fetched['avatar']}张\n")
    
    # ── 阶段3: Wallhaven ──
    print("── 📌 Wallhaven ──")
    wh_key = os.environ.get("WALLHAVEN_API_KEY", "")
    for query in WALLHAVEN_SEARCHES[:4]:
        if total_fetched["wallpaper"] >= wp_count + 10:
            break
        fetch_wallhaven_search(query, WALLPAPER_DIR, per_query_wh, wh_key)
        total_fetched["wallpaper"] += per_query_wh
        time.sleep(2)
    print(f"   ✅ Wallhaven: ~{per_query_wh * 4}张\n")
    
    # ── 阶段4: Danbooru ──
    print("── 📌 Danbooru 动漫 ──")
    danbooru_tags = [
        "scenery landscape rating:safe",
        "scenery sky rating:safe",
        "scenery sunset rating:safe",
    ]
    for tag in danbooru_tags[:2]:
        fetch_danbooru_tags(tag, WALLPAPER_DIR, per_query_wp)
        time.sleep(2)
    print()
    
    # ── 收集结果 ──
    print(f"{'='*60}")
    results = collect_results()
    
    export = {
        "fetched_at": datetime.now().isoformat(),
        "total": len(results),
        "sources": {},
        "images": results
    }
    
    for r in results:
        src = r["source"]
        export["sources"][src] = export["sources"].get(src, 0) + 1
    
    with open("fetch_results.json", "w", encoding="utf-8") as f:
        json.dump(export, f, ensure_ascii=False, indent=2)
    
    print(f"\n📸 抓取完成: {len(results)} 张")
    for src, cnt in sorted(export["sources"].items()):
        print(f"   {src}: {cnt}张")
    print(f"📁 结果: fetch_results.json\n")


if __name__ == "__main__":
    main()
