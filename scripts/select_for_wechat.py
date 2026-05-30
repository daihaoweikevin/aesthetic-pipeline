#!/usr/bin/env python3
"""
Aesthetic Lens Pipeline — 微信公众号精选器
从评分结果中精选 50 张图片:
  - 15 风景壁纸
  - 10 动漫风壁纸
  - 20 各种类型头像
  - 5  我的世界像素风景图
"""
import json, os, sys, argparse, random
from datetime import datetime
from pathlib import Path


# ─── 分类关键词 ─────────────────────────────────────

ANIME_KEYWORDS = [
    "anime", "manga", "漫画", "アニメ", "二次元", "動畫",
    "ghibli", "ジブリ", "吉卜力", "宫崎駿", "宮崎駿",
    "shinkai", "新海誠", "新海诚", "makoto",
    "illustration", "digital art", "イラスト",
    "cartoon", "アニメ風", "anime style",
    "pixel", "像素", "ドット絵",
]

AVATAR_KEYWORDS = [
    "avatar", "icon", "profile", "头像", "アイコン",
    "portrait", "face", "bust", "character",
    "girl solo", "boy solo", "1girl", "1boy",
    "後ろ姿", "背影", "silhouette",
]

MINECRAFT_KEYWORDS = [
    "minecraft", "我的世界", "マインクラフト",
    "pixel art", "voxel", "像素", "ドット",
    "block", "8-bit", "retro game",
]

LANDSCAPE_KEYWORDS = [
    "landscape", "scenery", "風景", "风景", "背景",
    "sunset", "夕焼け", "夕日", "落日",
    "mountain", "山", "森", "forest",
    "ocean", "海", "lake", "湖",
    "sky", "空", "cloud", "雲",
    "star", "星空", "桜", "cherry",
    "新海誠風", "ジブリ風 風景",
]


def classify_image(img):
    """根据来源和路径信息推断图片类别"""
    path = img.get("local_path", "").lower()
    image_type = img.get("image_type", "")
    source = img.get("source", "")
    tags = " ".join(img.get("tags", [])).lower()
    combined = f"{path} {tags} {source}".lower()

    # 我的世界/像素风优先判断
    if any(k in combined for k in MINECRAFT_KEYWORDS):
        return "minecraft"

    # 头像类
    if image_type == "avatar":
        return "avatar"
    if any(k in combined for k in AVATAR_KEYWORDS):
        return "avatar"

    # 动漫风壁纸
    if any(k in combined for k in ANIME_KEYWORDS):
        return "anime_wallpaper"

    # 风景壁纸（默认壁纸类型）
    if image_type == "wallpaper":
        return "landscape"

    # 无法判断的按分数归入风景
    return "landscape"


def select_images(images, counts=None):
    """
    精选图片
    counts: {"landscape": 15, "anime_wallpaper": 10, "avatar": 20, "minecraft": 5}
    """
    if counts is None:
        counts = {
            "landscape": 15,
            "anime_wallpaper": 10,
            "avatar": 20,
            "minecraft": 5,
        }

    # 分类
    classified = {
        "landscape": [],
        "anime_wallpaper": [],
        "avatar": [],
        "minecraft": [],
    }

    for img in images:
        cat = classify_image(img)
        if cat in classified:
            classified[cat].append(img)

    # 每类按分数排序
    for cat in classified:
        classified[cat].sort(key=lambda x: x.get("total_score", 0), reverse=True)

    # 精选
    selected = {}
    total_selected = 0

    for cat, count in counts.items():
        pool = classified[cat]
        taken = pool[:count]
        selected[cat] = taken
        total_selected += len(taken)

        # 如果不够，从风景壁纸中补充
        if len(taken) < count and cat != "landscape":
            deficit = count - len(taken)
            extra_from_landscape = [x for x in classified["landscape"]
                                    if x not in taken and x not in selected.get("landscape", [])]
            extra = extra_from_landscape[:deficit]
            selected[cat] = taken + extra
            total_selected += len(extra)

    return selected, total_selected


def generate_descriptions(selected):
    """为每张图片生成简短描述"""
    # 风景描述模板
    landscape_descs = [
        "落日余晖中的静谧世界",
        "云层之上，光与影的对话",
        "被时间遗忘的角落",
        "光穿透云层的那一刻",
        "宁静如诗的远方",
        "天地之间的辽阔",
        "山间云雾如梦似幻",
        "海天一色的温柔",
        "星辰低语，风在倾听",
        "被暖光拥抱的风景",
        "林间斑驳，光落如诗",
        "晚霞铺满天际的瞬间",
        "大自然的调色盘",
        "晨光中的第一缕温柔",
        "寂静而壮美的远方",
    ]

    anime_descs = [
        "穿越到画中的世界",
        "笔触间的温柔与光",
        "色彩绽放的幻想乡",
        "一笔一世界，一色一星辰",
        "在画布上呼吸的风景",
        "数字画笔编织的梦境",
        "二次元世界的浪漫瞬间",
        "如同动画截图般的美",
        "色彩碰撞出的奇境",
        "渲染出一个温柔的梦",
    ]

    avatar_descs = [
        "你的数字分身",
        "今日份的可爱头像",
        "换一个心情，换一个头像",
        "独一无二的你",
        "用这张图代表自己",
        "清新脱俗的头像之选",
        "一眼就心动的头像",
        "每天都是新的自己",
        "做最独特的那个",
        "头像也要绝美的",
    ]

    minecraft_descs = [
        "方块世界里的诗意",
        "像素风也能如此绝美",
        "8-bit 美学的极致",
        "在方块中建造的梦境",
        "像素之下的浪漫风景",
    ]

    desc_map = {
        "landscape": landscape_descs,
        "anime_wallpaper": anime_descs,
        "avatar": avatar_descs,
        "minecraft": minecraft_descs,
    }

    result = {}
    for cat, imgs in selected.items():
        descs = desc_map.get(cat, ["精选图片"])
        random.seed(42)  # 固定种子保持一致性
        shuffled = descs.copy()
        random.shuffle(shuffled)

        result[cat] = []
        for i, img in enumerate(imgs):
            desc = shuffled[i % len(shuffled)]
            result[cat].append({
                **img,
                "description": desc,
                "index_in_category": i + 1,
            })

    return result


def main():
    parser = argparse.ArgumentParser(description="微信公众号精选器")
    parser.add_argument("--input", required=True, help="scored_results.json 路径")
    parser.add_argument("--output", default="wechat_selection.json", help="输出路径")
    parser.add_argument("--landscape", type=int, default=15, help="风景壁纸数量")
    parser.add_argument("--anime", type=int, default=10, help="动漫风壁纸数量")
    parser.add_argument("--avatar", type=int, default=20, help="头像数量")
    parser.add_argument("--minecraft", type=int, default=5, help="像素风景数量")
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        data = json.load(f)

    images = data.get("images", [])
    print(f"\n📋 精选器输入: {len(images)} 张图片")

    counts = {
        "landscape": args.landscape,
        "anime_wallpaper": args.anime,
        "avatar": args.avatar,
        "minecraft": args.minecraft,
    }

    selected, total = select_images(images, counts)
    described = generate_descriptions(selected)

    # 统计
    output = {
        "selected_at": datetime.now().isoformat(),
        "issue_number": 1,  # 后续自动递增
        "total": total,
        "counts": {k: len(v) for k, v in described.items()},
        "categories": described,
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 精选完成: {total} 张")
    for cat, imgs in described.items():
        cat_names = {
            "landscape": "📷 风景壁纸",
            "anime_wallpaper": "🎨 动漫风壁纸",
            "avatar": "😊 精选头像",
            "minecraft": "🎮 像素风景",
        }
        print(f"   {cat_names.get(cat, cat)}: {len(imgs)} 张")
    print(f"📁 输出: {args.output}\n")


if __name__ == "__main__":
    main()
