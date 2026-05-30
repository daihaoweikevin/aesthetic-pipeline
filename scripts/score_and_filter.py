#!/usr/bin/env python3
"""
Aesthetic Lens Pipeline — 评分与筛选
复用 aesthetic-lens v4.0 评分引擎
"""
import json, sys, os
from pathlib import Path
from datetime import datetime

# 导入评分引擎
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "aesthetic-lens" / "scripts"))
sys.path.insert(0, "/root/.codebuddy/skills/aesthetic-lens/scripts")

from image_scorer import (
    calculate_score, get_grade, is_exquisite, check_veto,
    load_weights, DIMENSION_NAMES_CN
)

# ─── AI辅助评分（模拟，GitHub Actions 中用启发式规则） ──

def heuristic_score(image_info):
    """
    基于图片元信息进行启发式评分
    在本地可以接入 GPT-4V 等视觉模型做精确评分
    这里先用规则兜底
    """
    tags = image_info.get("tags", [])
    source = image_info.get("source", "unknown")
    desc = image_info.get("description", "").lower()
    tag_str = " ".join(tags).lower()
    
    scores = {}
    
    # 色彩和谐度: Pixiv/Danbooru 动漫图默认为高
    if source in ("pixiv", "danbooru"):
        scores["color_harmony"] = 8.5
    elif source == "wallhaven":
        scores["color_harmony"] = 7.5
    else:
        scores["color_harmony"] = 7.0
    
    # 光影氛围
    light_keywords = ["夕焼け", "sunset", "sunrise", "光", "light", "星", "star", "golden hour", "twilight"]
    light_hits = sum(1 for k in light_keywords if k in tag_str)
    scores["light_atmosphere"] = min(10, 7.0 + light_hits * 0.8)
    
    # 世界观/故事感
    narrative_keywords = ["風景", "scenery", "landscape", "background", "scene", "world"]
    narrative_hits = sum(1 for k in narrative_keywords if k in tag_str)
    scores["narrative_quality"] = min(10, 6.5 + narrative_hits * 0.7)
    
    # 风格匹配: Pixiv = 高
    if source == "pixiv":
        scores["style_alignment"] = 9.0
    elif source == "danbooru":
        scores["style_alignment"] = 8.5
    else:
        scores["style_alignment"] = 7.0
    
    # 构图空间
    comp_keywords = ["panorama", "wide", "landscape", "scenic", "view"]
    comp_hits = sum(1 for k in comp_keywords if k in tag_str)
    scores["composition_space"] = min(10, 6.5 + comp_hits * 0.7)
    
    # 细节质感
    scores["detail_texture"] = 7.5
    
    # 舒适度修正
    comfort_modifier = 0
    if source == "pixiv":
        comfort_modifier = 0.3
    
    return scores, comfort_modifier


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="fetch_results.json")
    parser.add_argument("--output", default="scored_results.json")
    parser.add_argument("--threshold", type=float, default=70)
    args = parser.parse_args()
    
    with open(args.input, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    images = data.get("images", [])
    weights, meta = load_weights()
    
    print(f"\n🎯 审美评分 (Aesthetic Lens v4.0)")
    print(f"{'='*50}")
    print(f"   待评分: {len(images)} 张")
    print(f"   分数线: ≥{args.threshold} 分\n")
    
    scored = []
    for i, img in enumerate(images):
        dims, comfort = heuristic_score(img)
        total, details = calculate_score(dims, weights, comfort)
        grade, grade_label = get_grade(total)
        is_exq, exq_reason = is_exquisite(total, dims)
        
        scored.append({
            **img,
            "total_score": round(total, 1),
            "grade": grade,
            "grade_label": grade_label,
            "is_exquisite": is_exq,
            "dimensions": {k: round(v, 1) for k, v in dims.items()},
        })
    
    # 排序
    scored.sort(key=lambda x: x["total_score"], reverse=True)
    
    # 统计
    grades = {}
    for s in scored:
        grades[s["grade"]] = grades.get(s["grade"], 0) + 1
    
    passed = [s for s in scored if s["total_score"] >= args.threshold]
    
    summary = {
        "scored_at": datetime.now().isoformat(),
        "total": len(scored),
        "grade_distribution": grades,
        "pass_threshold": args.threshold,
        "pass_count": len(passed),
        "pass_rate": f"{len(passed)/len(scored)*100:.1f}%" if scored else "0%",
        "top_score": scored[0]["total_score"] if scored else 0,
        "exquisite_count": sum(1 for s in scored if s["is_exquisite"]),
    }
    
    output = {
        **summary,
        "images": scored,
    }
    
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"📊 评分完成:")
    print(f"   有效: {len(scored)} 张")
    for g in ["S", "A", "B", "C", "D"]:
        if g in grades:
            print(f"   {g}级: {grades[g]} 张")
    print(f"   达标 (≥{args.threshold}): {len(passed)} 张 ({summary['pass_rate']})")
    print(f"   绝美 (S级): {summary['exquisite_count']} 张")
    print(f"📁 结果: {args.output}\n")


if __name__ == "__main__":
    main()
