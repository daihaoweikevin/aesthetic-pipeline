#!/usr/bin/env python3
"""
Aesthetic Lens Pipeline — 评分与筛选
内联 v4.0 评分引擎，无外部依赖
"""
import json, sys, os, math
from datetime import datetime

# ─── 权重配置 ────────────────────────────────────────

DEFAULT_WEIGHTS = {
    "color_harmony": 0.30,
    "light_atmosphere": 0.25,
    "narrative_quality": 0.15,
    "style_alignment": 0.15,
    "composition_space": 0.10,
    "detail_texture": 0.05
}

GRADE_THRESHOLDS = [
    (88, "S", "绝美"),
    (80, "A", "优秀"),
    (70, "B", "良好"),
    (60, "C", "一般"),
    (0,  "D", "不合格")
]


def calculate_score(dimension_scores, weights=None, comfort_modifier=0):
    if weights is None:
        weights = DEFAULT_WEIGHTS

    total = 0.0
    for dim, weight in weights.items():
        score = dimension_scores.get(dim, 0)
        total += score * weight

    base_score = total * 10
    adjusted_score = round(base_score + comfort_modifier * 3, 1)
    return adjusted_score


def get_grade(score):
    for threshold, grade, label in GRADE_THRESHOLDS:
        if score >= threshold:
            return grade, label
    return "D", "不合格"


def is_exquisite(score, dimension_scores):
    if score < 88:
        return False, "总分未达绝美线（需≥88）"

    color_ok = dimension_scores.get("color_harmony", 0) >= 8
    light_ok = dimension_scores.get("light_atmosphere", 0) >= 8
    if not (color_ok and light_ok):
        return False, "色彩和光影是核心，需均≥8分"

    style_ok = dimension_scores.get("style_alignment", 0) >= 7
    if not style_ok:
        return False, "风格匹配需≥7分"

    narrative_ok = dimension_scores.get("narrative_quality", 0) >= 7
    if not narrative_ok:
        return False, "世界观感需≥7分"

    if any(v < 5 for v in dimension_scores.values()):
        return False, "存在维度低于5分（有硬伤）"

    return True, "达到绝美标准"


# ─── 启发式评分 ─────────────────────────────────────

def heuristic_score(image_info):
    tags = image_info.get("tags", [])
    source = image_info.get("source", "unknown")
    tag_str = " ".join(tags).lower()

    scores = {}

    # 色彩和谐度
    if source in ("pixiv", "danbooru"):
        scores["color_harmony"] = 8.5
    elif source == "wallhaven":
        scores["color_harmony"] = 7.5
    else:
        scores["color_harmony"] = 7.0

    # 光影氛围
    light_keywords = ["夕焼け", "sunset", "sunrise", "光", "light", "star", "golden", "twilight", "sun"]
    light_hits = sum(1 for k in light_keywords if k in tag_str)
    scores["light_atmosphere"] = min(10, 7.0 + light_hits * 0.8)

    # 世界观/故事感
    narrative_keywords = ["風景", "scenery", "landscape", "background", "scene", "world", "mountain", "forest", "ocean", "lake"]
    narrative_hits = sum(1 for k in narrative_keywords if k in tag_str)
    scores["narrative_quality"] = min(10, 6.5 + narrative_hits * 0.7)

    # 风格匹配
    if source == "pixiv":
        scores["style_alignment"] = 9.0
    elif source == "danbooru":
        scores["style_alignment"] = 8.5
    else:
        scores["style_alignment"] = 7.0

    # 构图
    comp_keywords = ["panorama", "wide", "landscape", "scenic", "view"]
    comp_hits = sum(1 for k in comp_keywords if k in tag_str)
    scores["composition_space"] = min(10, 6.5 + comp_hits * 0.7)

    # 细节
    scores["detail_texture"] = 7.5

    comfort = 0.3 if source in ("pixiv", "danbooru") else 0
    return scores, comfort


# ─── 主流程 ──────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", default="scored_results.json")
    parser.add_argument("--threshold", type=float, default=70)
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        data = json.load(f)

    images = data.get("images", [])

    print(f"\n🎯 审美评分 (Aesthetic Lens v4.0)")
    print(f"{'='*50}")
    print(f"   待评分: {len(images)} 张")

    scored = []
    for img in images:
        dims, comfort = heuristic_score(img)
        total = calculate_score(dims, DEFAULT_WEIGHTS, comfort)
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

    scored.sort(key=lambda x: x["total_score"], reverse=True)

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

    output = {**summary, "images": scored}
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"📊 评分完成:")
    print(f"   有效: {len(scored)} 张")
    for g in ["S", "A", "B", "C", "D"]:
        if g in grades:
            print(f"   {g}级: {grades[g]} 张")
    print(f"   达标 (≥{args.threshold}): {len(passed)} 张 ({summary['pass_rate']})")
    print(f"📁 {args.output}\n")


if __name__ == "__main__":
    main()
