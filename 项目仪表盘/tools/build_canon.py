#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 _canon/ 下的分片合并成单一 canon.json，并做跨分片修正。

分片是人工/代理抽取的中间产物，本脚本是确定性的合并器：
  - 顶层键不得在两个分片里重复出现（重复即报错，防止隐性覆盖）
  - 合并后做跨分片修正（太空域补登、火山色占位等）
  - 输出 _canon/canon.json（供 HTML 内联，也供 check_canon 直接读）

用法：E:/Python/python.exe tools/build_canon.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHARD_DIR = ROOT / "_canon"
OUT = SHARD_DIR / "canon.json"

# 分片处理顺序（仅影响同键冲突时报错的先后，不影响数据）
SHARDS = [
    "narrative.json",   # meta, pact, synopsis, outline, alien
    "craft.json",       # visualRules, palette, director, mood, sound, engine, ip
    "domains.json",     # domains, demigods, roaming
    "people.json",      # protagonist, humans
    "episodes.json",    # episodes, hooks
    "rules.json",       # canon, glossary, deprecated, power
    "world.json",       # scenes, props
    "assets.json",      # assets
    "production.json",  # ep1Shots, ep1Refs, ep1Sound, ep2Scenes, ep2*, genplan
    "season.json",      # seasonScript（24 集逐场逐镜）
    "intimacy.json",    # intimacyProtocol, intimacyCards（亲密戏拍摄卡）
    "governance.json",  # pending, changes
]

# production.json 里这些顶层键要收进 genplan/ep1 命名空间，避免污染顶层
NEST_PRODUCTION = {
    "ep1Refs": ("ep1", "refs"),
    "ep1Sound": ("ep1", "sound"),
    "ep2Total": ("ep2", "total"),
    "ep2Target": ("ep2", "target"),
    "ep2Note": ("ep2", "note"),
    "ep3Total": ("ep3", "total"),
    "ep3Target": ("ep3", "target"),
    "ep3Note": ("ep3", "note"),
}


def main():
    merged = {}
    conflicts = []
    for name in SHARDS:
        path = SHARD_DIR / name
        if not path.exists():
            print(f"[FATAL] 缺少分片：{name}")
            return 1
        data = json.loads(path.read_text(encoding="utf-8"))
        for key, value in data.items():
            if key in NEST_PRODUCTION:
                ns, sub = NEST_PRODUCTION[key]
                merged.setdefault(ns, {})[sub] = value
                continue
            if key in merged:
                conflicts.append((name, key))
                continue
            merged[key] = value

    if conflicts:
        for name, key in conflicts:
            print(f"[ERROR] 顶层键 {key} 在分片 {name} 与更早的分片重复")
        return 1

    # ---- 跨分片修正 -----------------------------------------------------
    # 1) 太空不是九域之一，但卷09 有 4 个 SCN6xx 太空场景；补一条非神域条目，
    #    让 scenes[].domain 的引用闭合，season 标 null 表示它不属于九域季次逻辑。
    domain_names = {d["name"] for d in merged["domains"]}
    if "太空" not in domain_names:
        merged["domains"].append({
            "name": "太空",
            "cn": "太空",
            "en": None,
            "func": "近地轨道会战与先遣接触发生地，非九大模型系统之一",
            "location": "近地轨道",
            "god": {"name": None, "nameEn": None, "origin": None},
            "demigod": None,
            "motif": None,
            "pack": None,
            "ratio": {"fantasy": None, "sciFi": None},
            "color": {"base": "#0A0C12", "accent": "#7FE3E0"},
            "scenes": ["SCN601", "SCN602", "SCN603", "SCN604"],
            "season": None,
            "note": "非神域：卷06 色彩表与卷09 场景档案中的独立空间，会战场景所在",
        })

    # 2) 火山域在卷06 色彩表里有行（#17171A / #3FA9FF），若分片漏填则补上
    for d in merged["domains"]:
        if d["name"] in ("火山", "蓝色火山") and not d.get("color", {}).get("base"):
            d["color"] = {"base": "#17171A", "accent": "#3FA9FF"}
            d.setdefault("note", "")
            d["note"] = (d.get("note") or "") + "；色值取自卷06 色彩表火山行"

    # 3) 域名归一：分片若用了“蓝色火山”，统一为“火山”，并同步 scenes/episodes 引用
    rename = {"蓝色火山": "火山"}
    for d in merged["domains"]:
        if d["name"] in rename:
            d["name"] = rename[d["name"]]
    for s in merged.get("scenes", []):
        if s.get("domain") in rename:
            s["domain"] = rename[s["domain"]]
    for dg in merged.get("demigods", []):
        if dg.get("domain") in rename:
            dg["domain"] = rename[dg["domain"]]
    for ep in merged.get("episodes", []):
        ep["domains"] = [rename.get(x, x) for x in ep.get("domains", [])]

    # 4) 呼吸集口径：登记 G1 待决，数据层按大纲 v1.0 实际标记（仅 10、11）
    #    engine.episodeTypes 已在 craft.json 写明分歧，这里不擅自改 episodes。

    # 4.5) 第 2、3 集的数据只写一份：seasonScript 是装配产物，production 是源。
    #      这里把 seasonScript 的结果同步回 ep2Scenes/ep3Scenes，避免两套副本漂移。
    if isinstance(merged.get("seasonScript"), list):
        by_ep = {e["ep"]: e for e in merged["seasonScript"] if isinstance(e, dict)}
        for n in (2, 3):
            src = by_ep.get(n)
            if src:
                merged[f"ep{n}Scenes"] = src.get("scenes", [])
                if isinstance(merged.get(f"ep{n}"), dict) and src.get("note"):
                    merged[f"ep{n}"]["note"] = src["note"]

    # 5) 输出排序：按 schema 的逻辑顺序，便于 diff
    order = [
        "meta", "pact", "synopsis", "outline", "episodes", "hooks",
        "domains", "demigods", "roaming", "humans", "protagonist",
        "scenes", "props", "assets", "canon", "glossary", "deprecated",
        "power", "alien", "visualRules", "palette", "director", "mood",
        "sound", "engine", "ep1", "ep2", "ep3", "ep1Shots", "ep2Scenes", "ep3Scenes", "genplan",
        "seasonScript", "intimacyProtocol", "intimacyCards",
        "pending", "changes", "ip",
    ]
    ordered = {k: merged[k] for k in order if k in merged}
    for k in merged:
        if k not in ordered:
            ordered[k] = merged[k]

    OUT.write_text(json.dumps(ordered, ensure_ascii=False, indent=2), encoding="utf-8")
    counts = {k: (len(v) if isinstance(v, (list, dict)) else 1)
              for k, v in ordered.items()}
    print(f"合并完成：{OUT.relative_to(ROOT)}")
    print("顶层键：", len(ordered))
    for k, v in counts.items():
        print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
