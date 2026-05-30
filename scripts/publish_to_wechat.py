#!/usr/bin/env python3
"""
Aesthetic Lens Pipeline — 微信公众号发布器
支持三种模式:
  - api:    认证账号全自动发布（上传素材 → 创建草稿 → 发布）
  - manual: 个人号半自动模式（手机预览页 + 图片可长按保存）
  - email:  邮件自动发送（文章+图片直接发到邮箱，打开即用）
"""
import json, os, sys, argparse, shutil, hashlib
from pathlib import Path
from datetime import datetime

# ─── 微信API常量 ────────────────────────────────────

WECHAT_API_BASE = "https://api.weixin.qq.com/cgi-bin"


# ─── 路径A: API全自动发布 ────────────────────────────

class WeChatPublisher:
    """微信公众号API发布器（需认证账号）"""

    def __init__(self, appid, secret):
        self.appid = appid
        self.secret = secret
        self.token = None
        self.session = None

    def _get_session(self):
        if self.session is None:
            import requests
            self.session = requests.Session()
        return self.session

    def get_token(self):
        import requests
        url = f"{WECHAT_API_BASE}/stable_token"
        payload = {"grant_type": "client_credential", "appid": self.appid, "secret": self.secret}
        resp = requests.post(url, json=payload, timeout=10)
        data = resp.json()
        if "access_token" in data:
            self.token = data["access_token"]
            print(f"✅ 获取 access_token 成功")
            return self.token
        else:
            raise Exception(f"获取token失败: {data}")

    def upload_material_image(self, file_path):
        import requests
        if not self.token: self.get_token()
        url = f"{WECHAT_API_BASE}/material/add_material?access_token={self.token}&type=image"
        with open(file_path, "rb") as f:
            files = {"media": (Path(file_path).name, f, "image/jpeg")}
            resp = requests.post(url, files=files, timeout=30)
        data = resp.json()
        if "media_id" in data:
            print(f"  📎 永久素材上传成功")
            return data["media_id"], data.get("url", "")
        else:
            raise Exception(f"上传永久素材失败: {data}")

    def upload_body_image(self, file_path):
        import requests
        if not self.token: self.get_token()
        url = f"{WECHAT_API_BASE}/media/uploadimg?access_token={self.token}"
        with open(file_path, "rb") as f:
            files = {"media": (Path(file_path).name, f, "image/jpeg")}
            resp = requests.post(url, files=files, timeout=30)
        data = resp.json()
        if "url" in data:
            return data["url"]
        else:
            print(f"  ⚠️ 上传文章图片失败: {data}")
            return ""

    def create_draft(self, title, content_html, thumb_media_id, digest=""):
        import requests
        if not self.token: self.get_token()
        url = f"{WECHAT_API_BASE}/draft/add?access_token={self.token}"
        payload = {"articles": [{
            "title": title, "author": "Aesthetic Lens",
            "digest": digest or "每周精选绝美图片",
            "content": content_html, "thumb_media_id": thumb_media_id,
            "need_open_comment": 1, "only_fans_can_comment": 0,
        }]}
        resp = requests.post(url, json=payload, timeout=30)
        data = resp.json()
        if "media_id" in data:
            print(f"📝 草稿创建成功")
            return data["media_id"]
        else:
            raise Exception(f"创建草稿失败: {data}")

    def publish_draft(self, media_id):
        import requests
        if not self.token: self.get_token()
        url = f"{WECHAT_API_BASE}/freepublish/submit?access_token={self.token}"
        resp = requests.post(url, json={"media_id": media_id}, timeout=30)
        data = resp.json()
        if data.get("errcode") == 0:
            print(f"🚀 发布提交成功")
            return data.get("publish_id", "")
        else:
            raise Exception(f"发布失败: {data}")


def publish_via_api(selection_data, article_html_path, appid, secret):
    """路径A: 全自动API发布"""
    print("\n" + "=" * 50)
    print("📡 路径A: API 全自动发布")
    print("=" * 50)

    publisher = WeChatPublisher(appid, secret)
    publisher.get_token()

    # 上传封面图
    cover = None
    cats = selection_data.get("categories", {})
    for cat in ["landscape", "anime_wallpaper", "minecraft", "avatar"]:
        if cats.get(cat):
            cover = cats[cat][0]
            break
    if not cover:
        print("❌ 无可用封面图")
        return False
    cover_path = cover.get("local_path", "")
    if not cover_path or not os.path.exists(cover_path):
        print(f"❌ 封面图不存在: {cover_path}")
        return False
    thumb_media_id, cover_url = publisher.upload_material_image(cover_path)

    # 上传文章图片并替换URL
    with open(article_html_path, "r", encoding="utf-8") as f:
        html = f.read()
    uploaded = 0
    for cat in ["landscape", "anime_wallpaper", "minecraft", "avatar"]:
        for img in cats.get(cat, []):
            local = img.get("local_path", "")
            if not local or not os.path.exists(local):
                continue
            wechat_url = publisher.upload_body_image(local)
            if wechat_url:
                gallery_url = img.get("gallery_url", "")
                if gallery_url and gallery_url in html:
                    html = html.replace(gallery_url, wechat_url)
                uploaded += 1
    print(f"\n📊 已上传 {uploaded} 张图片到微信CDN")

    # 创建草稿+发布
    issue = selection_data.get("issue_number", 1)
    title = f"绝美图片周刊 · 第{issue}期"
    digest = f"本期精选{selection_data.get('total', 50)}张绝美图片"
    draft_media_id = publisher.create_draft(title, html, thumb_media_id, digest)
    publish_id = publisher.publish_draft(draft_media_id)
    print(f"\n✅ 发布完成! 标题: {title}")
    return True


# ─── 路径B: 个人号半自动模式 ──────────────────────────

def publish_manual(selection_data, article_html_path, output_dir="docs/wechat-preview"):
    """
    生成手机友好的预览页
    - 所有图片可见，可长按保存到手机相册
    - 文字内容一键复制
    - 适配微信公众后台编辑器
    """
    print("\n" + "=" * 50)
    print("📋 路径B: 个人号半自动模式")
    print("=" * 50)

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    assets_dir = output_dir / "assets"
    assets_dir.mkdir(exist_ok=True)

    issue = selection_data.get("issue_number", 1)
    total = selection_data.get("total", 50)
    date_str = datetime.now().strftime("%Y年%m月%d日")

    # 1. 复制图片到assets（用分类+序号重命名）
    cats = selection_data.get("categories", {})
    asset_list = []
    seen_names = set()
    for cat in ["landscape", "anime_wallpaper", "minecraft", "avatar"]:
        for idx, img in enumerate(cats.get(cat, []), 1):
            local = img.get("local_path", "")
            if not local or not os.path.exists(local):
                continue
            ext = Path(local).suffix
            new_name = f"{cat}_{idx:02d}{ext}"
            while new_name in seen_names:
                new_name = f"{cat}_{idx:02d}_{hashlib.md5(local.encode()).hexdigest()[:4]}{ext}"
            seen_names.add(new_name)
            dest = assets_dir / new_name
            if not dest.exists():
                shutil.copy2(local, dest)
            img["asset_url"] = f"assets/{new_name}"
            asset_list.append(img)

    # 2. 构建手机友好的预览页
    cat_config = {
        "landscape": {"emoji": "📷", "title": "风景壁纸"},
        "anime_wallpaper": {"emoji": "🎨", "title": "动漫风壁纸"},
        "avatar": {"emoji": "😊", "title": "精选头像"},
        "minecraft": {"emoji": "🎮", "title": "像素风景"},
    }

    # 生成图片区块
    image_blocks = ""
    copy_text_parts = []  # 用于复制的纯文本

    copy_text_parts.append(f"绝美图片周刊 · 第{issue}期")
    copy_text_parts.append(f"{date_str} · 本期精选 {total} 张")
    copy_text_parts.append("")
    copy_text_parts.append("每周六，为你精选世间绝美图片")
    copy_text_parts.append("风景 · 动漫 · 头像 · 像素 · 一期一会")
    copy_text_parts.append("")

    for cat_key, config in cat_config.items():
        images = cats.get(cat_key, [])
        if not images:
            continue

        count = len(images)
        emoji = config["emoji"]
        title = config["title"]

        image_blocks += f"""
<div class="cat-header">
  <span class="cat-emoji">{emoji}</span>
  <span class="cat-title">{title}</span>
  <span class="cat-count">{count}张</span>
</div>
"""

        copy_text_parts.append(f"{emoji} {title}（{count}张）")

        # 头像用双列，壁纸用单列
        if cat_key == "avatar":
            image_blocks += '<div class="avatar-grid">'
            for img in images:
                idx = img.get("index_in_category", 0)
                desc = img.get("description", "")
                asset_url = img.get("asset_url", "")
                image_blocks += f"""
<div class="avatar-card">
  <img src="{asset_url}" loading="lazy" />
  <div class="avatar-label">{idx:02d}. {desc}</div>
</div>
"""
                copy_text_parts.append(f"  {idx:02d}. {desc}")
            image_blocks += '</div>'
        else:
            for img in images:
                idx = img.get("index_in_category", 0)
                desc = img.get("description", "")
                grade = img.get("grade", "B")
                score = img.get("total_score", 0)
                asset_url = img.get("asset_url", "")
                image_blocks += f"""
<div class="wallpaper-card">
  <img src="{asset_url}" loading="lazy" />
  <div class="wallpaper-info">
    <span class="wp-desc">{idx:02d}. {desc}</span>
    <span class="wp-grade">{grade} · {score}</span>
  </div>
</div>
"""
                copy_text_parts.append(f"  {idx:02d}. {desc}")

        copy_text_parts.append("")

    copy_text_parts.append("✦ 下周六见")
    copy_text = "\n".join(copy_text_parts)

    # 构建完整HTML
    preview_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>绝美图片周刊 · 第{issue}期</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; -webkit-tap-highlight-color: transparent; }}
  body {{ background: #f5f0eb; color: #2c2c2c; font-family: -apple-system, BlinkMacSystemFont, sans-serif; padding-bottom: 80px; }}

  .header {{
    text-align: center; padding: 30px 20px 20px;
    background: linear-gradient(180deg, #fffdf8 0%, #faf8f4 100%);
    border-bottom: 1px solid #e8e4dc;
  }}
  .header .brand {{ font-size: 11px; color: #c9b99a; letter-spacing: 0.2em; }}
  .header h1 {{ font-size: 22px; font-weight: 300; color: #1a1a1a; letter-spacing: 0.06em; margin-top: 6px; }}
  .header .date {{ font-size: 12px; color: #bbb; margin-top: 6px; }}
  .header .intro {{ font-size: 13px; color: #999; margin-top: 10px; line-height: 1.8; }}

  .cat-header {{
    display: flex; align-items: center; gap: 8px;
    padding: 16px 16px 8px; position: sticky; top: 0; z-index: 10;
    background: #f5f0eb;
  }}
  .cat-emoji {{ font-size: 18px; }}
  .cat-title {{ font-size: 16px; font-weight: 600; color: #2c2c2c; flex: 1; }}
  .cat-count {{ font-size: 12px; color: #aaa; }}

  .wallpaper-card {{
    margin: 8px 12px; background: #fff; border-radius: 10px;
    overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.04);
  }}
  .wallpaper-card img {{
    width: 100%; display: block;
  }}
  .wallpaper-info {{
    padding: 10px 14px; display: flex; align-items: center; justify-content: space-between;
  }}
  .wp-desc {{ font-size: 13px; color: #555; }}
  .wp-grade {{ font-size: 10px; color: #999; background: #f8f6f2; padding: 2px 8px; border-radius: 10px; }}

  .avatar-grid {{
    display: grid; grid-template-columns: 1fr 1fr;
    gap: 8px; padding: 8px 12px;
  }}
  .avatar-card {{
    background: #fff; border-radius: 10px; overflow: hidden;
    box-shadow: 0 2px 8px rgba(0,0,0,0.04);
  }}
  .avatar-card img {{
    width: 100%; height: 0; padding-bottom: 100%; object-fit: cover; display: block;
  }}
  .avatar-label {{
    padding: 6px 10px; font-size: 11px; color: #999; white-space: nowrap;
    overflow: hidden; text-overflow: ellipsis;
  }}

  .footer {{
    text-align: center; padding: 24px; color: #ccc;
  }}
  .footer .icon {{ font-size: 16px; color: #c9b99a; }}
  .footer p {{ font-size: 13px; margin-top: 4px; }}
  .footer .sub {{ font-size: 11px; color: #ddd; margin-top: 4px; }}

  .bottom-bar {{
    position: fixed; bottom: 0; left: 0; right: 0; z-index: 100;
    background: #fff; border-top: 1px solid #e8e4dc;
    padding: 10px 16px; display: flex; gap: 10px;
    box-shadow: 0 -2px 10px rgba(0,0,0,0.06);
  }}
  .bottom-bar .btn {{
    flex: 1; padding: 12px; border-radius: 10px; border: none;
    font-size: 14px; font-weight: 500; cursor: pointer; text-align: center;
  }}
  .btn-copy {{ background: #07c160; color: #fff; }}
  .btn-guide {{ background: #f5f0eb; color: #666; }}

  .guide-modal {{
    display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(0,0,0,0.5); z-index: 200; align-items: center; justify-content: center;
  }}
  .guide-modal.show {{ display: flex; }}
  .guide-content {{
    background: #fff; border-radius: 16px; padding: 24px; margin: 20px;
    max-width: 340px; width: 100%;
  }}
  .guide-content h3 {{ font-size: 16px; margin-bottom: 16px; }}
  .guide-content ol {{ padding-left: 20px; }}
  .guide-content li {{ margin: 10px 0; font-size: 14px; color: #555; line-height: 1.8; }}
  .guide-close {{ margin-top: 16px; width: 100%; padding: 12px; border: none;
    border-radius: 10px; background: #f5f0eb; font-size: 14px; color: #666; cursor: pointer; }}

  .toast {{
    display: none; position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%);
    background: rgba(0,0,0,0.75); color: #fff; padding: 12px 24px; border-radius: 10px;
    font-size: 14px; z-index: 300; pointer-events: none;
  }}
  .toast.show {{ display: block; }}
</style>
</head>
<body>

<div class="header">
  <div class="brand">AESTHETIC LENS</div>
  <h1>绝美图片周刊 · 第{issue}期</h1>
  <div class="date">{date_str} · 本期精选 {total} 张</div>
  <div class="intro">每周六，为你精选世间绝美图片<br/>风景 · 动漫 · 头像 · 像素 · 一期一会</div>
</div>

{image_blocks}

<div class="footer">
  <div class="icon">✦</div>
  <p>下周六见</p>
  <p class="sub">长按图片可保存到手机相册</p>
</div>

<div class="bottom-bar">
  <button class="btn btn-copy" onclick="copyText()">📋 复制文字</button>
  <button class="btn btn-guide" onclick="showGuide()">📖 发布指南</button>
</div>

<div class="guide-modal" id="guideModal">
  <div class="guide-content">
    <h3>📝 发布步骤（个人订阅号）</h3>
    <ol>
      <li>点「复制文字」复制文章内容</li>
      <li>长按图片保存到手机相册</li>
      <li>打开 <strong>微信公众号</strong> App</li>
      <li>新建图文 → 粘贴文字</li>
      <li>在对应位置插入图片</li>
      <li>设置封面图 → 发布</li>
    </ol>
    <button class="guide-close" onclick="hideGuide()">知道了</button>
  </div>
</div>

<div class="toast" id="toast"></div>

<script>
const copyData = {json.dumps(copy_text, ensure_ascii=False)};

function copyText() {{
  if (navigator.clipboard) {{
    navigator.clipboard.writeText(copyData).then(() => showToast('✅ 文字已复制'));
  }} else {{
    const ta = document.createElement('textarea');
    ta.value = copyData;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    document.body.removeChild(ta);
    showToast('✅ 文字已复制');
  }}
}}

function showGuide() {{ document.getElementById('guideModal').classList.add('show'); }}
function hideGuide() {{ document.getElementById('guideModal').classList.remove('show'); }}

function showToast(msg) {{
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 2000);
}}
</script>

</body>
</html>"""

    preview_path = output_dir / "index.html"
    with open(preview_path, "w", encoding="utf-8") as f:
        f.write(preview_html)

    # 3. 生成操作指南Markdown
    guide_path = output_dir / "README.md"
    guide_content = f"""# 绝美图片周刊 · 第{issue}期

## 📅 {date_str} · 本期精选 {total} 张

| 分类 | 数量 |
|------|------|
| 📷 风景壁纸 | {len(cats.get('landscape', []))} |
| 🎨 动漫风壁纸 | {len(cats.get('anime_wallpaper', []))} |
| 😊 精选头像 | {len(cats.get('avatar', []))} |
| 🎮 像素风景 | {len(cats.get('minecraft', []))} |

## 📱 发布步骤（个人订阅号）

1. 打开本预览页 → 点「复制文字」
2. 长按每张图片 → 保存到手机相册
3. 打开微信公众号 App → 新建图文
4. 粘贴文字 → 在对应位置插入图片
5. 选一张风景壁纸做封面 → 发布
"""

    with open(guide_path, "w", encoding="utf-8") as f:
        f.write(guide_content)

    print(f"\n✅ 预览页面已生成: {preview_path}")
    print(f"🖼️  图片素材: {len(asset_list)} 张")
    print(f"\n📱 手机操作: 打开预览页 → 长按保存图片 → 复制文字 → 粘贴到公众号")

    return True


# ─── 路径C: 邮件自动发送 ─────────────────────────────

def publish_via_email(selection_data, smtp_server, smtp_port, sender_email, sender_password, recipient_email):
    """生成邮件内容并发送：文章HTML+图片内嵌"""
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from email.mime.image import MIMEImage

    print("\n" + "=" * 50)
    print("📧 邮件自动发送模式")
    print("=" * 50)

    issue = selection_data.get("issue_number", 1)
    total = selection_data.get("total", 50)
    date_str = datetime.now().strftime("%Y年%m月%d日")
    cats = selection_data.get("categories", {})

    # ── 构建邮件HTML内容 ──
    cat_config = {
        "landscape": {"emoji": "📷", "title": "风景壁纸"},
        "anime_wallpaper": {"emoji": "🎨", "title": "动漫风壁纸"},
        "avatar": {"emoji": "😊", "title": "精选头像"},
        "minecraft": {"emoji": "🎮", "title": "像素风景"},
    }

    # 收集所有图片（按顺序编号，用于内嵌cid）
    all_images = []
    for cat_key in ["landscape", "anime_wallpaper", "minecraft", "avatar"]:
        for img in cats.get(cat_key, []):
            all_images.append((cat_key, img))

    # 构建HTML body
    body_parts = []
    body_parts.append(f"""<div style="text-align:center;padding:20px;background:linear-gradient(180deg,#fffdf8,#faf8f4);border-bottom:1px solid #e8e4dc;">
  <p style="font-size:11px;color:#c9b99a;letter-spacing:0.2em;">AESTHETIC LENS</p>
  <h1 style="font-size:22px;font-weight:300;color:#1a1a1a;letter-spacing:0.06em;">绝美图片周刊 · 第{issue}期</h1>
  <p style="font-size:12px;color:#bbb;margin-top:6px;">{date_str} · 本期精选 {total} 张</p>
  <p style="font-size:13px;color:#999;margin-top:10px;line-height:1.8;">每周六，为你精选世间绝美图片<br/>风景 · 动漫 · 头像 · 像素 · 一期一会</p>
</div>""")

    img_idx = 0
    for cat_key, config in cat_config.items():
        images = cats.get(cat_key, [])
        if not images:
            continue
        count = len(images)

        body_parts.append(f"""<div style="margin:20px 0 8px;padding:10px 14px;background:linear-gradient(135deg,#faf9f7,#f5f0eb);border-left:4px solid #c9b99a;border-radius:0 8px 8px 0;">
  <span style="font-size:16px;font-weight:600;color:#2c2c2c;">{config['emoji']} {config['title']}</span>
  <span style="font-size:12px;color:#999;">（{count}张）</span>
</div>""")

        if cat_key == "avatar":
            # 头像双列
            row_open = False
            for i, img in enumerate(images):
                if i % 2 == 0:
                    body_parts.append('<div style="display:flex;gap:8px;margin:6px 0;">')
                    row_open = True
                desc = img.get("description", "")
                idx_num = img.get("index_in_category", 0)
                cid = f"img_{img_idx}"
                body_parts.append(f"""<div style="flex:1;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 2px 6px rgba(0,0,0,0.05);">
  <img src="cid:{cid}" style="width:100%;display:block;"/>
  <div style="padding:5px 8px;font-size:11px;color:#999;">{idx_num:02d}. {desc}</div>
</div>""")
                img_idx += 1
                if i % 2 == 1 or i == len(images) - 1:
                    body_parts.append('</div>')
                    row_open = False
        else:
            for img in images:
                desc = img.get("description", "")
                idx_num = img.get("index_in_category", 0)
                grade = img.get("grade", "B")
                score = img.get("total_score", 0)
                grade_colors = {"S": "#92400e", "A": "#1e40af", "B": "#6b7280", "C": "#9ca3af"}
                gc = grade_colors.get(grade, "#999")
                cid = f"img_{img_idx}"
                body_parts.append(f"""<div style="margin:8px 0;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.04);">
  <img src="cid:{cid}" style="width:100%;display:block;"/>
  <div style="padding:8px 12px;display:flex;align-items:center;justify-content:space-between;">
    <span style="font-size:13px;color:#555;">{idx_num:02d}. {desc}</span>
    <span style="font-size:10px;color:{gc};background:#f8f6f2;padding:2px 8px;border-radius:10px;">{grade} · {score}</span>
  </div>
</div>""")
                img_idx += 1

    body_parts.append(f"""<div style="text-align:center;padding:20px;color:#ccc;border-top:1px solid #e8e4dc;margin-top:16px;">
  <p style="font-size:16px;color:#c9b99a;">✦</p>
  <p style="font-size:13px;color:#999;">下周六见</p>
  <p style="font-size:11px;color:#ccc;margin-top:4px;">图片长按可保存 → 公众号后台粘贴发布</p>
</div>""")

    html_body = f"""<div style="max-width:677px;margin:0 auto;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'PingFang SC','Microsoft YaHei',sans-serif;color:#2c2c2c;line-height:1.8;font-size:15px;">
{"".join(body_parts)}
</div>"""

    # ── 构建邮件 ──
    msg = MIMEMultipart("related")
    msg["Subject"] = f"绝美图片周刊 · 第{issue}期 | {date_str}"
    msg["From"] = sender_email
    msg["To"] = recipient_email

    # HTML正文
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    # 内嵌图片
    attached = 0
    skipped = 0
    for idx, (cat_key, img) in enumerate(all_images):
        local = img.get("local_path", "")
        if not local or not os.path.exists(local):
            skipped += 1
            continue

        # 限制单张图片大小（邮件不宜太大）
        file_size = os.path.getsize(local)
        if file_size > 5 * 1024 * 1024:  # 超过5MB的压缩或跳过
            try:
                from PIL import Image
                import io
                pil_img = Image.open(local)
                # 缩小到合理尺寸
                pil_img.thumbnail((1200, 1200), Image.LANCZOS)
                buf = io.BytesIO()
                pil_img.save(buf, format="JPEG", quality=85)
                img_data = buf.getvalue()
            except Exception:
                skipped += 1
                continue
        else:
            with open(local, "rb") as f:
                img_data = f.read()

        cid = f"img_{idx}"
        mime_img = MIMEImage(img_data)
        ext = Path(local).suffix.lower()
        if ext == ".png":
            mime_img.set_type("image/png")
        elif ext == ".webp":
            mime_img.set_type("image/webp")
        else:
            mime_img.set_type("image/jpeg")
        mime_img.add_header("Content-ID", f"<{cid}>")
        mime_img.add_header("Content-Disposition", "inline", filename=f"{cid}{ext}")
        msg.attach(mime_img)
        attached += 1

    print(f"  📎 内嵌图片: {attached} 张 (跳过: {skipped})")

    # ── 发送邮件 ──
    print(f"  📤 连接SMTP: {smtp_server}:{smtp_port}")
    try:
        if smtp_port == 465:
            server = smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=30)
        else:
            server = smtplib.SMTP(smtp_server, smtp_port, timeout=30)
            server.starttls()

        server.login(sender_email, sender_password)
        server.sendmail(sender_email, [recipient_email], msg.as_string())
        server.quit()

        print(f"\n✅ 邮件发送成功!")
        print(f"   收件人: {recipient_email}")
        print(f"   主题: {msg['Subject']}")
        print(f"   图片: {attached} 张内嵌")
        return True

    except Exception as e:
        print(f"\n❌ 邮件发送失败: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="微信公众号发布器")
    parser.add_argument("--selection", required=True, help="wechat_selection.json 路径")
    parser.add_argument("--article", required=True, help="文章HTML路径")
    parser.add_argument("--mode", choices=["api", "manual", "email"], default="manual", help="发布模式")
    parser.add_argument("--output-dir", default="docs/wechat-preview", help="输出目录")
    parser.add_argument("--appid", default="", help="微信公众号 AppID（api模式）")
    parser.add_argument("--secret", default="", help="微信公众号 AppSecret（api模式）")
    args = parser.parse_args()

    with open(args.selection, "r", encoding="utf-8") as f:
        selection_data = json.load(f)

    if args.mode == "api":
        if not args.appid or not args.secret:
            args.appid = args.appid or os.environ.get("WECHAT_APPID", "")
            args.secret = args.secret or os.environ.get("WECHAT_APPSECRET", "")
        if not args.appid or not args.secret:
            print("❌ API模式需要提供 AppID 和 AppSecret")
            sys.exit(1)
        publish_via_api(selection_data, args.article, args.appid, args.secret)

    elif args.mode == "email":
        smtp_server = os.environ.get("SMTP_SERVER", "smtp.163.com")
        smtp_port = int(os.environ.get("SMTP_PORT", "465"))
        sender_email = os.environ.get("SENDER_EMAIL", "")
        sender_password = os.environ.get("SENDER_PASSWORD", "")
        recipient_email = os.environ.get("RECIPIENT_EMAIL", "dhwjln923@163.com")

        if not sender_email or not sender_password:
            print("❌ 邮件模式需要配置 SMTP 凭证")
            print("   请设置 GitHub Secrets:")
            print("   SENDER_EMAIL    = 发件邮箱地址")
            print("   SENDER_PASSWORD = 邮箱SMTP授权码")
            print("   RECIPIENT_EMAIL = 收件邮箱（默认 dhwjln923@163.com）")
            sys.exit(1)

        publish_via_email(selection_data, smtp_server, smtp_port,
                          sender_email, sender_password, recipient_email)

    else:
        publish_manual(selection_data, args.article, args.output_dir)


if __name__ == "__main__":
    main()
