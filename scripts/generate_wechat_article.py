#!/usr/bin/env python3
"""
Aesthetic Lens Pipeline — 微信公众号文章生成器
生成 WeChat 兼容的 HTML 文章（内联样式，无外部CSS）
支持两种输出模式:
  - api: 用于 API 自动发布（图片需后续替换为微信CDN链接）
  - manual: 用于手动复制发布（图片为相对路径，配合素材包使用）
"""
import json, os, sys, argparse, base64, hashlib
from pathlib import Path
from datetime import datetime


# ─── 文章模板 ────────────────────────────────────────

def render_article(issue_data, mode="manual", image_base_url=""):
    """
    生成微信公众号文章 HTML
    mode: "api" | "manual"
    image_base_url: 图片基础URL（manual模式用相对路径，api模式用临时URL）
    """
    issue = issue_data.get("issue_number", 1)
    date_str = datetime.now().strftime("%Y年%m月%d日")
    total = issue_data.get("total", 50)

    cat_config = {
        "landscape": {
            "emoji": "📷",
            "title": "风景壁纸",
            "subtitle": "自然与光影的对话",
        },
        "anime_wallpaper": {
            "emoji": "🎨",
            "title": "动漫风壁纸",
            "subtitle": "穿越到画中的世界",
        },
        "avatar": {
            "emoji": "😊",
            "title": "精选头像",
            "subtitle": "你的数字分身",
        },
        "minecraft": {
            "emoji": "🎮",
            "title": "像素风景",
            "subtitle": "方块世界的诗意",
        },
    }

    sections_html = ""

    for cat_key, config in cat_config.items():
        images = issue_data.get("categories", {}).get(cat_key, [])
        if not images:
            continue

        count = len(images)

        # 分类标题
        sections_html += f"""
<section style="margin: 30px 0 15px; padding: 12px 16px; background: linear-gradient(135deg, #faf9f7 0%, #f5f0eb 100%); border-left: 4px solid #c9b99a; border-radius: 0 8px 8px 0;">
  <p style="margin:0; font-size: 18px; font-weight: 600; color: #2c2c2c; letter-spacing: 0.05em;">
    {config['emoji']} {config['title']} <span style="font-size: 13px; color: #999; font-weight: 300;">（{count}张）</span>
  </p>
  <p style="margin: 4px 0 0; font-size: 13px; color: #aaa;">{config['subtitle']}</p>
</section>
"""

        # 图片列表
        for img in images:
            idx = img.get("index_in_category", 0)
            desc = img.get("description", "精选图片")
            score = img.get("total_score", 0)
            grade = img.get("grade", "B")
            local_path = img.get("local_path", "")
            gallery_url = img.get("gallery_url", "")

            # 图片URL
            if mode == "api" and image_base_url:
                img_src = f"{image_base_url}/{gallery_url}" if gallery_url else ""
            else:
                # manual模式：使用gallery_url相对路径（不内嵌base64，文件太大）
                img_src = gallery_url or ""

            # 卡片样式
            is_wallpaper = cat_key in ("landscape", "anime_wallpaper", "minecraft")
            img_height = "auto" if is_wallpaper else "200px"
            max_width = "100%" if is_wallpaper else "48%"

            # 头像用双列布局
            if cat_key == "avatar":
                sections_html += f"""
<section style="display: inline-block; width: 48%; vertical-align: top; margin: 1%; box-sizing: border-box;">
  <section style="background: #fff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.06);">
    <img src="{img_src}" style="width: 100%; height: 180px; object-fit: cover; display: block;" />
    <section style="padding: 8px 10px;">
      <p style="margin: 0; font-size: 11px; color: #999;">{idx:02d}. {desc}</p>
    </section>
  </section>
</section>
"""
            else:
                # 壁纸/像素风景用全宽
                grade_colors = {"S": "#92400e", "A": "#1e40af", "B": "#6b7280", "C": "#9ca3af"}
                grade_color = grade_colors.get(grade, "#999")

                sections_html += f"""
<section style="margin: 12px 0; background: #fff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 12px rgba(0,0,0,0.04);">
  <img src="{img_src}" style="width: 100%; display: block;" />
  <section style="padding: 10px 14px; display: flex; align-items: center; justify-content: space-between;">
    <p style="margin: 0; font-size: 13px; color: #555;">{idx:02d}. {desc}</p>
    <span style="font-size: 10px; color: {grade_color}; background: #f8f6f2; padding: 2px 8px; border-radius: 10px;">{grade} · {score}</span>
  </section>
</section>
"""

    # 拼装完整文章
    html = f"""
<section style="max-width: 677px; margin: 0 auto; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'PingFang SC', 'Microsoft YaHei', sans-serif; color: #2c2c2c; line-height: 1.8; font-size: 15px;">

  <!-- 头部 -->
  <section style="text-align: center; padding: 30px 20px 20px; background: linear-gradient(180deg, #fffdf8 0%, #faf8f4 100%);">
    <p style="margin: 0 0 6px; font-size: 12px; color: #c9b99a; letter-spacing: 0.2em; text-transform: uppercase;">AESTHETIC LENS</p>
    <h1 style="margin: 0; font-size: 24px; font-weight: 300; color: #1a1a1a; letter-spacing: 0.08em;">绝美图片周刊 · 第{issue}期</h1>
    <p style="margin: 8px 0 0; font-size: 13px; color: #bbb;">{date_str} · 本期精选 {total} 张</p>
  </section>

  <!-- 分割线 -->
  <section style="margin: 0 20px; height: 1px; background: linear-gradient(90deg, transparent, #e8e4dc, transparent);"></section>

  <!-- 导语 -->
  <section style="padding: 20px; text-align: center;">
    <p style="margin: 0; font-size: 14px; color: #888; line-height: 2;">
      每周六，为你精选世间绝美图片<br/>
      风景 · 动漫 · 头像 · 像素 · 一期一会
    </p>
  </section>

  <!-- 图片内容 -->
  {sections_html}

  <!-- 结尾 -->
  <section style="margin: 30px 20px 0; height: 1px; background: linear-gradient(90deg, transparent, #e8e4dc, transparent);"></section>
  <section style="text-align: center; padding: 25px 20px 30px;">
    <p style="margin: 0 0 6px; font-size: 18px; color: #c9b99a;">✦</p>
    <p style="margin: 0; font-size: 14px; color: #999;">下周六见</p>
    <p style="margin: 6px 0 0; font-size: 12px; color: #ccc;">关注我们，每周分享绝美图片</p>
  </section>

</section>
"""

    return html


def get_base64_image(file_path):
    """将图片转为 base64 data URI"""
    try:
        ext = Path(file_path).suffix.lower()
        mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
        mime = mime_map.get(ext, "image/jpeg")

        with open(file_path, "rb") as f:
            data = base64.b64encode(f.read()).decode("utf-8")

        return f"data:{mime};base64,{data}"
    except Exception:
        return ""


def select_cover_image(issue_data):
    """选取封面图（风景壁纸中分数最高的）"""
    landscapes = issue_data.get("categories", {}).get("landscape", [])
    if landscapes:
        return landscapes[0]  # 已按分数排序
    # 备选：任意分类的第一张
    for cat in ["anime_wallpaper", "minecraft", "avatar"]:
        imgs = issue_data.get("categories", {}).get(cat, [])
        if imgs:
            return imgs[0]
    return None


def main():
    parser = argparse.ArgumentParser(description="微信公众号文章生成器")
    parser.add_argument("--input", required=True, help="wechat_selection.json 路径")
    parser.add_argument("--output", default="wechat_article.html", help="输出HTML路径")
    parser.add_argument("--mode", choices=["api", "manual"], default="manual", help="输出模式")
    parser.add_argument("--image-base-url", default="", help="图片基础URL（api模式用）")
    parser.add_argument("--issue-number", type=int, default=None, help="期号（覆盖JSON中的值）")
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        data = json.load(f)

    if args.issue_number:
        data["issue_number"] = args.issue_number

    # 自动计算期号（基于日期）
    if data.get("issue_number", 0) <= 0:
        now = datetime.now()
        week_num = (now.timetuple().tm_yday // 7) + 1
        data["issue_number"] = week_num

    html = render_article(data, mode=args.mode, image_base_url=args.image_base_url)

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(html)

    # 选取封面图
    cover = select_cover_image(data)
    cover_info = ""
    if cover:
        cover_info = f"\n📸 封面图: {cover.get('local_path', 'N/A')} (分数: {cover.get('total_score', 0)})"

    print(f"\n✅ 文章已生成: {args.output}")
    print(f"   期号: 第{data.get('issue_number', 1)}期")
    print(f"   模式: {args.mode}")
    print(f"   总图片: {data.get('total', 0)} 张{cover_info}\n")


if __name__ == "__main__":
    main()
