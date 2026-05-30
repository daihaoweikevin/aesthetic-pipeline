#!/usr/bin/env python3
"""
Aesthetic Lens Pipeline — 微信公众号发布器
支持两种模式:
  - api:  认证账号全自动发布（上传素材 → 创建草稿 → 发布）
  - manual: 个人号半自动模式（生成预览页 + 素材包 + 操作指南）
"""
import json, os, sys, argparse, zipfile, shutil, hashlib
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
        """获取 access_token"""
        import requests
        url = f"{WECHAT_API_BASE}/stable_token"
        payload = {
            "grant_type": "client_credential",
            "appid": self.appid,
            "secret": self.secret,
        }
        resp = requests.post(url, json=payload, timeout=10)
        data = resp.json()
        if "access_token" in data:
            self.token = data["access_token"]
            print(f"✅ 获取 access_token 成功 ({self.token[:10]}...)")
            return self.token
        else:
            raise Exception(f"获取token失败: {data}")

    def upload_material_image(self, file_path):
        """上传永久素材图片（封面用）→ 返回 media_id + url"""
        import requests
        if not self.token:
            self.get_token()

        url = f"{WECHAT_API_BASE}/material/add_material?access_token={self.token}&type=image"
        with open(file_path, "rb") as f:
            files = {"media": (Path(file_path).name, f, "image/jpeg")}
            resp = requests.post(url, files=files, timeout=30)

        data = resp.json()
        if "media_id" in data:
            print(f"  📎 永久素材上传成功: {data['media_id'][:20]}...")
            return data["media_id"], data.get("url", "")
        else:
            raise Exception(f"上传永久素材失败: {data}")

    def upload_body_image(self, file_path):
        """上传文章内图片 → 返回微信CDN URL"""
        import requests
        if not self.token:
            self.get_token()

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
        """创建草稿 → 返回 media_id"""
        import requests
        if not self.token:
            self.get_token()

        url = f"{WECHAT_API_BASE}/draft/add?access_token={self.token}"
        payload = {
            "articles": [{
                "title": title,
                "author": "Aesthetic Lens",
                "digest": digest or "每周精选绝美图片",
                "content": content_html,
                "thumb_media_id": thumb_media_id,
                "need_open_comment": 1,
                "only_fans_can_comment": 0,
            }]
        }
        resp = requests.post(url, json=payload, timeout=30)
        data = resp.json()
        if "media_id" in data:
            print(f"📝 草稿创建成功: {data['media_id'][:20]}...")
            return data["media_id"]
        else:
            raise Exception(f"创建草稿失败: {data}")

    def publish_draft(self, media_id):
        """发布草稿 → 返回 publish_id"""
        import requests
        if not self.token:
            self.get_token()

        url = f"{WECHAT_API_BASE}/freepublish/submit?access_token={self.token}"
        payload = {"media_id": media_id}
        resp = requests.post(url, json=payload, timeout=30)
        data = resp.json()
        if data.get("errcode") == 0:
            print(f"🚀 发布提交成功: {data.get('publish_id', '')}")
            return data.get("publish_id", "")
        else:
            raise Exception(f"发布失败: {data}")


def publish_via_api(selection_data, article_html_path, appid, secret):
    """路径A: 全自动API发布"""
    print("\n" + "=" * 50)
    print("📡 路径A: API 全自动发布")
    print("=" * 50)

    publisher = WeChatPublisher(appid, secret)

    # 1. 获取token
    publisher.get_token()

    # 2. 上传封面图
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
        print(f"❌ 封面图文件不存在: {cover_path}")
        return False

    thumb_media_id, cover_url = publisher.upload_material_image(cover_path)

    # 3. 上传文章内图片并替换URL
    with open(article_html_path, "r", encoding="utf-8") as f:
        html = f.read()

    uploaded_count = 0
    for cat in ["landscape", "anime_wallpaper", "minecraft", "avatar"]:
        for img in cats.get(cat, []):
            local = img.get("local_path", "")
            if not local or not os.path.exists(local):
                continue

            wechat_url = publisher.upload_body_image(local)
            if wechat_url:
                # 替换文章中的图片src
                gallery_url = img.get("gallery_url", "")
                if gallery_url and gallery_url in html:
                    html = html.replace(gallery_url, wechat_url)
                # 也替换base64数据
                import re
                base64_pattern = r'data:image/[^;]+;base64,[A-Za-z0-9+/=]+'
                if re.search(base64_pattern, html):
                    html = re.sub(base64_pattern, wechat_url, html, count=1)
                uploaded_count += 1

    print(f"\n📊 已上传 {uploaded_count} 张图片到微信CDN")

    # 4. 创建草稿
    issue = selection_data.get("issue_number", 1)
    title = f"绝美图片周刊 · 第{issue}期"
    digest = f"本期精选{selection_data.get('total', 50)}张绝美图片：风景·动漫·头像·像素"

    draft_media_id = publisher.create_draft(title, html, thumb_media_id, digest)

    # 5. 发布
    publish_id = publisher.publish_draft(draft_media_id)

    print(f"\n✅ 发布完成!")
    print(f"   标题: {title}")
    print(f"   草稿ID: {draft_media_id[:20]}...")
    print(f"   发布ID: {publish_id}")

    return True


# ─── 路径B: 个人号半自动模式 ──────────────────────────

def publish_manual(selection_data, article_html_path, output_dir="docs/wechat-preview"):
    """路径B: 生成预览页 + 素材包 + 操作指南"""
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

    # 1. 复制图片到assets目录（用分类+序号重命名避免冲突）
    cats = selection_data.get("categories", {})
    asset_list = []
    seen_names = set()
    for cat in ["landscape", "anime_wallpaper", "minecraft", "avatar"]:
        for idx, img in enumerate(cats.get(cat, []), 1):
            local = img.get("local_path", "")
            if not local or not os.path.exists(local):
                continue

            # 用分类+序号重命名，避免文件名冲突
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

    # 2. 生成预览HTML（带实际图片路径）
    with open(article_html_path, "r", encoding="utf-8") as f:
        article_html = f.read()

    # 替换图片路径为相对路径
    for img in asset_list:
        gallery_url = img.get("gallery_url", "")
        asset_url = img.get("asset_url", "")
        if gallery_url and asset_url:
            article_html = article_html.replace(gallery_url, asset_url)

    preview_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>绝美图片周刊 · 第{issue}期 — 预览</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ background: #f5f0eb; font-family: -apple-system, sans-serif; }}
  .toolbar {{
    position: sticky; top: 0; z-index: 100;
    background: #fff; border-bottom: 1px solid #e8e4dc;
    padding: 12px 20px; display: flex; gap: 12px; align-items: center;
    box-shadow: 0 2px 8px rgba(0,0,0,0.04);
  }}
  .toolbar h2 {{ font-size: 14px; font-weight: 500; color: #333; flex: 1; }}
  .btn {{
    padding: 6px 16px; border-radius: 6px; border: none; cursor: pointer;
    font-size: 13px; font-weight: 500;
  }}
  .btn-primary {{ background: #07c160; color: #fff; }}
  .btn-secondary {{ background: #f5f0eb; color: #666; }}
  .phone-frame {{
    max-width: 375px; margin: 20px auto; background: #fff;
    border-radius: 20px; box-shadow: 0 4px 20px rgba(0,0,0,0.1);
    overflow: hidden; min-height: 600px;
  }}
  .instructions {{
    max-width: 600px; margin: 20px auto; padding: 20px;
    background: #fff; border-radius: 12px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.04);
  }}
  .instructions h3 {{ font-size: 16px; color: #333; margin-bottom: 12px; }}
  .instructions ol {{ padding-left: 20px; }}
  .instructions li {{ margin: 8px 0; font-size: 14px; color: #555; line-height: 1.8; }}
  .instructions code {{ background: #f5f0eb; padding: 2px 6px; border-radius: 3px; font-size: 13px; }}
</style>
</head>
<body>

<div class="toolbar">
  <h2>📱 微信公众号文章预览 · 第{issue}期</h2>
  <button class="btn btn-secondary" onclick="copyArticle()">📋 复制文章</button>
</div>

<div class="phone-frame" id="article-frame">
  {article_html}
</div>

<div class="instructions">
  <h3>📝 发布操作指南</h3>
  <ol>
    <li>点击上方 <strong>「复制文章」</strong> 按钮</li>
    <li>打开 <strong>微信公众号后台</strong> → 新建图文</li>
    <li>在编辑器中 <strong>粘贴</strong> 文章内容</li>
    <li>上传封面图（assets文件夹中评分最高的那张）</li>
    <li>检查排版，确认无误后 <strong>发布</strong></li>
  </ol>
  <p style="margin-top:12px;font-size:13px;color:#999;">💡 图片素材已打包到 <code>assets/</code> 文件夹，可在公众号编辑器中手动上传替换</p>
</div>

<script>
function copyArticle() {{
  const article = document.getElementById('article-frame');
  const range = document.createRange();
  range.selectNodeContents(article);
  const selection = window.getSelection();
  selection.removeAllRanges();
  selection.addRange(range);
  document.execCommand('copy');
  selection.removeAllRanges();
  alert('✅ 文章已复制！\\n请在微信公众号编辑器中粘贴');
}}
</script>

</body>
</html>"""

    preview_path = output_dir / "index.html"
    with open(preview_path, "w", encoding="utf-8") as f:
        f.write(preview_html)

    # 3. 打包素材ZIP
    zip_path = output_dir / f"wechat_issue_{issue}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for img in asset_list:
            local = img.get("local_path", "")
            asset_url = img.get("asset_url", "")
            if local and os.path.exists(local) and asset_url:
                zf.write(local, arcname=asset_url)

        # 也包含文章HTML
        zf.write(article_html_path, f"article_issue_{issue}.html")

    # 4. 生成操作指南
    guide_path = output_dir / "README.md"
    guide_content = f"""# 绝美图片周刊 · 第{issue}期 — 发布指南

## 📅 {date_str}

## 📦 素材清单

| 分类 | 数量 |
|------|------|
| 📷 风景壁纸 | {len(cats.get('landscape', []))} |
| 🎨 动漫风壁纸 | {len(cats.get('anime_wallpaper', []))} |
| 😊 精选头像 | {len(cats.get('avatar', []))} |
| 🎮 像素风景 | {len(cats.get('minecraft', []))} |

## 📝 发布步骤

1. 打开 [微信公众号后台](https://mp.weixin.qq.com)
2. 点击「创作管理」→「图文消息」→「新建」
3. 打开预览页面: {preview_path.name}
4. 点击「复制文章」按钮
5. 在公众号编辑器中粘贴
6. 上传封面图
7. 检查排版 → 发布

## 📎 文件说明

- `index.html` — 文章预览页面
- `assets/` — 图片素材文件夹
- `wechat_issue_{issue}.zip` — 全部素材打包
"""

    with open(guide_path, "w", encoding="utf-8") as f:
        f.write(guide_content)

    print(f"\n✅ 预览页面已生成: {preview_path}")
    print(f"📦 素材包: {zip_path}")
    print(f"📋 操作指南: {guide_path}")
    print(f"🖼️  图片素材: {len(asset_list)} 张")

    return True


def main():
    parser = argparse.ArgumentParser(description="微信公众号发布器")
    parser.add_argument("--selection", required=True, help="wechat_selection.json 路径")
    parser.add_argument("--article", required=True, help="文章HTML路径")
    parser.add_argument("--mode", choices=["api", "manual"], default="manual", help="发布模式")
    parser.add_argument("--output-dir", default="docs/wechat-preview", help="输出目录（manual模式）")
    parser.add_argument("--appid", default="", help="微信公众号 AppID（api模式）")
    parser.add_argument("--secret", default="", help="微信公众号 AppSecret（api模式）")
    args = parser.parse_args()

    with open(args.selection, "r", encoding="utf-8") as f:
        selection_data = json.load(f)

    if args.mode == "api":
        if not args.appid or not args.secret:
            # 从环境变量读取
            args.appid = args.appid or os.environ.get("WECHAT_APPID", "")
            args.secret = args.secret or os.environ.get("WECHAT_APPSECRET", "")
        if not args.appid or not args.secret:
            print("❌ API模式需要提供 AppID 和 AppSecret")
            print("   通过参数 --appid / --secret 或环境变量 WECHAT_APPID / WECHAT_APPSECRET")
            sys.exit(1)
        publish_via_api(selection_data, args.article, args.appid, args.secret)
    else:
        publish_manual(selection_data, args.article, args.output_dir)


if __name__ == "__main__":
    main()
