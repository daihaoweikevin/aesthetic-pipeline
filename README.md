# 🎨 Aesthetic Lens Pipeline

> 绝美图片自动采集、评分、展示 — 运行在 GitHub Actions 云端

## 架构

```
GitHub Actions (每周定时)
  ├── Pixiv (gallery-dl)    ──→ 日系动漫风景/头像
  ├── Wallhaven (gallery-dl) ──→ 高质量数字艺术壁纸
  └── Danbooru (gallery-dl)  ──→ 动漫插画补充
        │
        ▼
  aesthetic-lens v4.0 评分引擎
        │
        ▼
  GitHub Pages 画廊展示
```

## 快速开始

### 1. Fork 仓库

```bash
gh repo fork --clone
cd aesthetic-pipeline
```

### 2. 配置 Pixiv Cookie（可选但推荐）

Pixiv 是日系动漫风景的主要来源，配置后可获得最佳效果：

1. 浏览器登录 [pixiv.net](https://www.pixiv.net)
2. 用浏览器扩展导出 Cookie（JSON 格式的 PHPSESSID）
3. 在仓库 Settings → Secrets and variables → Actions 添加：
   - `PIXIV_COOKIE` = 你的 cookie 值

### 3. 配置 Wallhaven API Key（可选）

1. 注册 [Wallhaven](https://wallhaven.cc/settings/account)
2. 在 Settings → Secrets 添加：
   - `WALLHAVEN_API_KEY` = 你的 API key

### 4. 手动触发首次运行

进入 Actions → "绝美图片自动采集与筛选" → Run workflow

## 定时规则

- 每周一、周四 UTC 0:00（北京早8点）自动运行
- 可在 `.github/workflows/weekly-fetch.yml` 中修改 cron

## 查看结果

运行后访问：`https://<你的用户名>.github.io/aesthetic-pipeline/`

## 评分标准 (v4.0)

| 级别 | 分数线 | 含义 |
|------|--------|------|
| S | ≥88 | 绝美 — "这是一个我想住进去的世界" |
| A | ≥80 | 优秀 — 可推送 |
| B | 70-79 | 良好 — 备用 |
| C | 60-69 | 一般 |
| D | <60 | 不合格 |

## 自定义

- 修改 `scripts/fetch_images.py` 中的搜索词来匹配你的审美
- 修改 `scripts/score_and_filter.py` 调整评分逻辑
- 修改 `scripts/generate_gallery.py` 自定义画廊样式
