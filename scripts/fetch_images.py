#!/usr/bin/env python3
"""
Aesthetic Lens Pipeline — 多图源抓取器 v4.0
运行在 GitHub Actions 环境，无沙箱限制
支持: Pixiv, Wallhaven, Danbooru, Minecraft像素图
"""
import json, os, sys, time, hashlib, subprocess, urllib.request, urllib.parse
from pathlib import Path
from datetime import datetime

# ─── 配置 ───────────────────────────────────────────
OUTPUT_DIR = Path("downloads")
OUTPUT_DIR.mkdir(exist_ok=True)
WALLPAPER_DIR = OUTPUT_DIR / "wallpaper"
AVATAR_DIR = OUTPUT_DIR / "avatar"
ANIME_WALLPAPER_DIR = OUTPUT_DIR / "anime_wallpaper"
MINECRAFT_DIR = OUTPUT_DIR / "minecraft"
for d in [WALLPAPER_DIR, AVATAR_DIR, ANIME_WALLPAPER_DIR, MINECRAFT_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ─── Pixiv 搜索词 ──────────────────────────────────

# 风景壁纸
PIXIV_WALLPAPER_TAGS = [
    "風景 背景",              # landscape background
    "scenic background",       # scenic background (English)
    "夕焼け 風景",             # sunset landscape
    "空 雲 風景",              # sky clouds landscape
    "森 光 風景",              # forest light landscape
    "新海誠風",                # Shinkai-style
    "ジブリ風 風景",           # Ghibli-style landscape
    "星空 風景",               # starry sky landscape
    "桜 風景",                 # cherry blossom landscape
    "海 夕日 風景",            # sea sunset landscape
]

# 动漫风壁纸
PIXIV_ANIME_WALLPAPER_TAGS = [
    "アニメ 風景 壁紙",         # anime landscape wallpaper
    "ジブリ 背景",              # Ghibli background
    "新海誠 風景",              # Shinkai landscape
    "幻想 風景 イラスト",       # fantasy landscape illustration
    "夜景 アニメ",              # night view anime
    "夕暮れ アニメ 風景",       # twilight anime landscape
    "水彩 風景",                # watercolor landscape
    "背景 アニメーション",      # background animation
]

# 头像
PIXIV_AVATAR_TAGS = [
    "オリジナル 女の子 アイコン",   # original girl icon
    "後ろ姿 風景",                  # back view landscape
    "アイコン イラスト",            # icon illustration
    "夕焼け 少女 後ろ姿",          # sunset girl back view
    "森 少女 風景",                 # forest girl landscape
    "水彩 少女",                    # watercolor girl
    "シルエット 夕日",              # silhouette sunset
    "男の子 アイコン",              # boy icon
    "猫 アイコン",                  # cat icon
    "オリジナル かっこいい",        # original cool
]

# ─── Wallhaven 搜索关键词 ──────────────────────────

WALLHAVEN_LANDSCAPE_SEARCHES = [
    "landscape nature",
    "sunset scenery",
    "mountain lake",
    "starry sky",
    "ocean waves",
]

WALLHAVEN_ANIME_SEARCHES = [
    "anime landscape",
    "anime scenery",
    "ghibli wallpaper",
    "anime sunset",
    "digital art landscape",
]

WALLHAVEN_AVATAR_SEARCHES = [
    "anime icon",
    "anime avatar",
    "anime profile",
    "anime girl portrait",
    "anime boy portrait",
]

WALLHAVEN_MINECRAFT_SEARCHES = [
    "minecraft landscape",
    "pixel art landscape",
    "voxel scenery",
    "minecraft sunset",
    "8-bit landscape",
]

# ─── Danbooru 标签 ─────────────────────────────────

DANBOORU_LANDSCAPE_TAGS = [
    "scenery landscape rating:safe",
    "scenery sky rating:safe",
    "scenery sunset rating:safe",
]

DANBOORU_ANIME_TAGS = [
    "scenery anime rating:safe",
    "ghibli scenery rating:safe",
    "shinkai makoto scenery rating:safe",
]

DANBOORU_AVATAR_TAGS = [
    "1girl solo rating:safe",
    "1boy solo rating:safe",
    "portrait rating:safe",
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
        "--no-part",
        "--abort", "3",
        "-q",
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
    encoded = urllib.parse.quote(tag)
    url = f"https://www.pixiv.net/tags/{encoded}/artworks"
    print(f"  🔍 Pixiv: \"{tag}\"")
    fetch_with_gallery_dl(url, target_dir, count)


def fetch_wallhaven_search(query, target_dir, count=10):
    """通过 gallery-dl 搜索 Wallhaven"""
    encoded = urllib.parse.quote(query)
    url = f"https://wallhaven.cc/search?q={encoded}"
    print(f"  🔍 Wallhaven: \"{query}\"")
    fetch_with_gallery_dl(url, target_dir, count)


def fetch_danbooru_tags(tags, target_dir, count=15):
    """通过 gallery-dl 搜索 Danbooru"""
    encoded = urllib.parse.quote(tags.replace(" ", "+"))
    url = f"https://danbooru.donmai.us/posts?tags={encoded}"
    print(f"  🔍 Danbooru: \"{tags}\"")
    fetch_with_gallery_dl(url, target_dir, count)


# ─── 结果收集 ────────────────────────────────────────

def collect_results():
    """扫描下载目录，生成 metadata JSON"""
    results = []

    dir_map = [
        (WALLPAPER_DIR, "wallpaper"),
        (ANIME_WALLPAPER_DIR, "anime_wallpaper"),
        (AVATAR_DIR, "avatar"),
        (MINECRAFT_DIR, "minecraft"),
    ]

    for dir_path, dir_type in dir_map:
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
                "local_path": str(img_file),
                "file_size": stat.st_size,
                "image_type": dir_type,
                "file_ext": suffix,
            })

    return results


# ─── 主流程 ──────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Aesthetic Lens Pipeline — 图片抓取器 v4.0")
    parser.add_argument("--wallpaper-count", type=int, default=20, help="风景壁纸数量")
    parser.add_argument("--anime-count", type=int, default=15, help="动漫风壁纸数量")
    parser.add_argument("--avatar-count", type=int, default=25, help="头像数量")
    parser.add_argument("--minecraft-count", type=int, default=8, help="像素风景数量")
    args = parser.parse_args()

    wp_count = args.wallpaper_count
    anime_count = args.anime_count
    av_count = args.avatar_count
    mc_count = args.minecraft_count

    print(f"\n{'='*60}")
    print(f"🎨 Aesthetic Lens Pipeline v4.0")
    print(f"   目标: 风景{wp_count} | 动漫{anime_count} | 头像{av_count} | 像素{mc_count}")
    print(f"{'='*60}\n")

    pixiv_ok = os.environ.get("PIXIV_COOKIE", "") or (
        os.environ.get("PIXIV_USERNAME", "") and os.environ.get("PIXIV_PASSWORD", "")
    )

    total_fetched = {"wallpaper": 0, "anime_wallpaper": 0, "avatar": 0, "minecraft": 0}

    # ── 阶段1: 风景壁纸 ──
    print("── 📷 风景壁纸 ──")
    per_query = max(3, wp_count // max(len(PIXIV_WALLPAPER_TAGS), 1))
    if pixiv_ok:
        for tag in PIXIV_WALLPAPER_TAGS[:6]:
            if total_fetched["wallpaper"] >= wp_count:
                break
            fetch_pixiv_search(tag, WALLPAPER_DIR, per_query)
            total_fetched["wallpaper"] += per_query
            time.sleep(2)

    for query in WALLHAVEN_LANDSCAPE_SEARCHES[:3]:
        if total_fetched["wallpaper"] >= wp_count:
            break
        fetch_wallhaven_search(query, WALLPAPER_DIR, max(3, wp_count // 5))
        total_fetched["wallpaper"] += max(3, wp_count // 5)
        time.sleep(2)

    for tags in DANBOORU_LANDSCAPE_TAGS[:2]:
        fetch_danbooru_tags(tags, WALLPAPER_DIR, per_query)
        time.sleep(2)
    print(f"   ✅ 风景壁纸: ~{total_fetched['wallpaper']}张\n")

    # ── 阶段2: 动漫风壁纸 ──
    print("── 🎨 动漫风壁纸 ──")
    per_query_anime = max(3, anime_count // max(len(PIXIV_ANIME_WALLPAPER_TAGS), 1))
    if pixiv_ok:
        for tag in PIXIV_ANIME_WALLPAPER_TAGS[:5]:
            if total_fetched["anime_wallpaper"] >= anime_count:
                break
            fetch_pixiv_search(tag, ANIME_WALLPAPER_DIR, per_query_anime)
            total_fetched["anime_wallpaper"] += per_query_anime
            time.sleep(2)

    for query in WALLHAVEN_ANIME_SEARCHES[:3]:
        if total_fetched["anime_wallpaper"] >= anime_count:
            break
        fetch_wallhaven_search(query, ANIME_WALLPAPER_DIR, max(3, anime_count // 5))
        total_fetched["anime_wallpaper"] += max(3, anime_count // 5)
        time.sleep(2)

    for tags in DANBOORU_ANIME_TAGS[:2]:
        fetch_danbooru_tags(tags, ANIME_WALLPAPER_DIR, per_query_anime)
        time.sleep(2)
    print(f"   ✅ 动漫风壁纸: ~{total_fetched['anime_wallpaper']}张\n")

    # ── 阶段3: 头像 ──
    print("── 😊 头像 ──")
    per_query_av = max(3, av_count // max(len(PIXIV_AVATAR_TAGS), 1))
    if pixiv_ok:
        for tag in PIXIV_AVATAR_TAGS[:5]:
            if total_fetched["avatar"] >= av_count:
                break
            fetch_pixiv_search(tag, AVATAR_DIR, per_query_av)
            total_fetched["avatar"] += per_query_av
            time.sleep(2)

    for query in WALLHAVEN_AVATAR_SEARCHES[:3]:
        if total_fetched["avatar"] >= av_count:
            break
        fetch_wallhaven_search(query, AVATAR_DIR, max(3, av_count // 5))
        total_fetched["avatar"] += max(3, av_count // 5)
        time.sleep(2)

    for tags in DANBOORU_AVATAR_TAGS[:2]:
        fetch_danbooru_tags(tags, AVATAR_DIR, per_query_av)
        time.sleep(2)
    print(f"   ✅ 头像: ~{total_fetched['avatar']}张\n")

    # ── 阶段4: Minecraft像素风景 ──
    print("── 🎮 Minecraft像素风景 ──")
    per_query_mc = max(2, mc_count // 3)
    for query in WALLHAVEN_MINECRAFT_SEARCHES[:3]:
        if total_fetched["minecraft"] >= mc_count:
            break
        fetch_wallhaven_search(query, MINECRAFT_DIR, per_query_mc)
        total_fetched["minecraft"] += per_query_mc
        time.sleep(2)

    # Danbooru像素风
    fetch_danbooru_tags("pixel_art scenery rating:safe", MINECRAFT_DIR, per_query_mc)
    time.sleep(2)

    # 从Planet Minecraft抓取（直接HTTP下载）
    try:
        fetch_planetminecraft(MINECRAFT_DIR, mc_count)
    except Exception as e:
        print(f"  ⚠️ PlanetMinecraft: {e}")
    print(f"   ✅ 像素风景: ~{total_fetched['minecraft']}张\n")

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


def fetch_planetminecraft(target_dir, count=5):
    """从Planet Minecraft抓取像素风景截图"""
    # Planet Minecraft 有风景截图分享
    # 用简单的HTTP请求获取
    print(f"  🔍 PlanetMinecraft: 像素风景")
    # 由于gallery-dl不支持PlanetMinecraft，这里用简单方式
    # 实际效果有限，主要依赖Wallhaven和Danbooru的像素标签
    pass


if __name__ == "__main__":
    main()
