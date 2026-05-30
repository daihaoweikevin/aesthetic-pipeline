#!/usr/bin/env python3
"""
Aesthetic Lens Pipeline — 画廊生成器
拷贝图片到 docs/images/，生成 HTML 画廊
"""
import json, sys, os, shutil, hashlib
from pathlib import Path
from datetime import datetime

GALLERY_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>绝美图片库 — Aesthetic Lens</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ 
    background: #f8f6f2; color: #2c2c2c; font-family: "Noto Serif SC", "Source Han Serif SC", "Songti SC", Georgia, serif;
    min-height: 100vh;
  }}
  .hero {{
    padding: 80px 30px 60px; text-align: center;
    background: linear-gradient(180deg, #fff 0%, #f8f6f2 100%);
    border-bottom: 1px solid #e8e4dc;
  }}
  .hero h1 {{ font-size: 2.8rem; font-weight: 300; letter-spacing: 0.08em; color: #1a1a1a; }}
  .hero .subtitle {{ font-size: 1rem; color: #999; margin-top: 12px; font-weight: 300; }}
  .hero .date {{ font-size: 0.8rem; color: #bbb; margin-top: 8px; }}
  .stats {{
    display: flex; justify-content: center; gap: 40px; margin-top: 30px; flex-wrap: wrap;
  }}
  .stat {{ text-align: center; }}
  .stat .num {{ font-size: 2rem; font-weight: 300; color: #1a1a1a; }}
  .stat .label {{ font-size: 0.7rem; color: #bbb; text-transform: uppercase; letter-spacing: 0.12em; margin-top: 4px; }}

  .section-header {{
    max-width: 1200px; margin: 50px auto 20px; padding: 0 20px;
    font-size: 1.3rem; font-weight: 300; color: #555; letter-spacing: 0.05em;
    border-bottom: 1px solid #e8e4dc; padding-bottom: 10px;
  }}

  .gallery {{
    max-width: 1200px; margin: 0 auto; padding: 0 16px 40px;
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
    gap: 20px;
  }}
  .card {{
    background: #fff; border-radius: 6px; overflow: hidden;
    box-shadow: 0 2px 12px rgba(0,0,0,0.04);
    transition: transform 0.25s, box-shadow 0.25s;
  }}
  .card:hover {{ transform: translateY(-3px); box-shadow: 0 8px 30px rgba(0,0,0,0.08); }}
  .card-img {{
    width: 100%; height: 220px; object-fit: cover; display: block;
    background: #f0ece6;
  }}
  .card-body {{ padding: 14px 16px; }}
  .card-badge {{
    display: inline-block; font-size: 0.6rem; padding: 2px 8px; border-radius: 3px;
    text-transform: uppercase; letter-spacing: 0.1em; font-weight: 600; margin-bottom: 8px;
  }}
  .badge-S {{ background: #fef3c7; color: #92400e; }}
  .badge-A {{ background: #dbeafe; color: #1e40af; }}
  .badge-B {{ background: #f3f4f6; color: #6b7280; }}
  .badge-C {{ background: #f3f4f6; color: #9ca3af; }}
  .card-source {{ font-size: 0.7rem; color: #bbb; text-transform: capitalize; }}
  .card-dims {{ font-size: 0.65rem; color: #ccc; margin-top: 2px; }}

  .empty {{ 
    max-width: 1200px; margin: 60px auto; text-align: center; color: #ccc;
    font-size: 1.2rem; font-weight: 300;
  }}

  .footer {{
    text-align: center; padding: 40px; color: #ccc; font-size: 0.8rem;
    border-top: 1px solid #e8e4dc;
  }}

  @media (max-width: 600px) {{
    .hero h1 {{ font-size: 1.8rem; }}
    .gallery {{ grid-template-columns: 1fr; padding: 0 12px; }}
    .stats {{ gap: 20px; }}
  }}
</style>
</head>
<body>
<div class="hero">
  <h1>绝美图片库</h1>
  <div class="subtitle">Aesthetic Lens · 自动采集 · 审美筛选</div>
  <div class="date">{date}</div>
  <div class="stats">
    <div class="stat"><div class="num">{total}</div><div class="label">收录</div></div>
    <div class="stat"><div class="num">{top_score}</div><div class="label">最高分</div></div>
    <div class="stat"><div class="num">{s_count}</div><div class="label">S级·绝美</div></div>
    <div class="stat"><div class="num">{a_count}</div><div class="label">A级·优秀</div></div>
  </div>
</div>

{sections}

<div class="footer">
  <p>由 Aesthetic Lens Pipeline 自动生成 · 每周更新</p>
  <p style="margin-top:4px;font-size:0.7rem;">图片版权归原作者所有 · 仅供欣赏</p>
</div>
</body>
</html>"""


def generate_gallery(scored_data, output_path):
    images = scored_data.get("images", [])
    summary = scored_data

    # 创建 docs/images/ 目录
    docs_dir = Path(output_path).parent
    images_dir = docs_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    # 拷贝图片到 docs/images/
    for img in images:
        local = img.get("local_path", "")
        if not local or not os.path.exists(local):
            continue

        # 生成唯一文件名
        src = img.get("source", "unknown")
        iid = img.get("id", "0")
        key = hashlib.md5(f"{src}_{iid}".encode()).hexdigest()[:10]
        ext = os.path.splitext(local)[1] or ".jpg"
        dest_name = f"{key}{ext}"
        dest_path = images_dir / dest_name

        if not dest_path.exists():
            shutil.copy2(local, dest_path)

        img["gallery_url"] = f"images/{dest_name}"

    # 分级分组
    s_imgs = [img for img in images if img["grade"] == "S"]
    a_imgs = [img for img in images if img["grade"] == "A"]
    b_imgs = [img for img in images if img["grade"] == "B"]

    def render_section(title, imgs):
        if not imgs:
            return ""
        cards = []
        for img in imgs:
            url = img.get("gallery_url", "")
            if not url:
                continue
            score = img["total_score"]
            grade = img["grade"]
            source = img.get("source", "?")
            w = img.get("width", "?")
            h = img.get("height", "?")

            cards.append(f"""<div class="card">
    <img class="card-img" src="{url}" alt="" loading="lazy" onerror="this.style.display='none'">
    <div class="card-body">
      <div class="card-badge badge-{grade}">{grade} · {score}分</div>
      <div class="card-source">{source}</div>
      <div class="card-dims">{w}×{h}</div>
    </div>
  </div>""")

        return f"""<div class="section-header">{title}</div>
<div class="gallery">
{''.join(cards)}
</div>"""

    sections = ""
    if s_imgs:
        sections += render_section("✦ S级 · 绝美", s_imgs)
    if a_imgs:
        sections += render_section("◆ A级 · 优秀", a_imgs)
    if b_imgs:
        sections += render_section("◇ B级 · 良好", b_imgs)

    if not sections:
        sections = '<div class="empty">暂无符合标准的图片，请等待下次采集。</div>'

    html = GALLERY_TEMPLATE.format(
        date=datetime.now().strftime("%Y年%m月%d日"),
        total=summary.get("total", 0),
        top_score=summary.get("top_score", 0),
        s_count=summary.get("grade_distribution", {}).get("S", 0),
        a_count=summary.get("grade_distribution", {}).get("A", 0),
        sections=sections,
    )

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    img_count = len(list(images_dir.glob("*")))
    print(f"📁 已拷贝 {img_count} 张图片到 {images_dir}")

    return output_path


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", default="docs/index.html")
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        data = json.load(f)

    path = generate_gallery(data, args.output)
    print(f"🖼️  画廊已生成: {path}")

    s_count = sum(1 for img in data.get("images", []) if img["grade"] == "S")
    a_count = sum(1 for img in data.get("images", []) if img["grade"] == "A")
    print(f"   S级: {s_count}张 | A级: {a_count}张 | 总计: {data.get('total',0)}张")


if __name__ == "__main__":
    main()
