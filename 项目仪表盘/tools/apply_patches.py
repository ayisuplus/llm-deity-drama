#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 _canon/_patch/*.json 里的分镜修改应用到 _canon/_parts/*.json。

_patch 文件格式（由审稿/写作 worker 产出，合并器是确定性的执行器）：
  {
    "file": "s09_16.json",
    "shots": [
      {"ep": 16, "shot": "1-4", "action": "<完整替换文本>", "duration": 60},
      {"ep": 14, "insert_shot": {"after": "3-5", "shot": {"no": "3-6", "shot": "近景", "move": "固定", "action": "...", "duration": 30}}},
      {"ep": 16, "scene": 2, "characters": ["程栖", "Vesper", "塞拉"]}
    ],
    "scenes": [
      {"ep": 13, "insert_scene": {"before_scene": 3, "scene": {"name": "...", "place": "...", "time": "...", "duration": 0, "characters": [...], "props": [...], "vfx": "...", "desc": "...", "shots": [{"no": "3-1", "shot": "...", "move": "...", "action": "...", "duration": 8}]}}}
    ],
    "append_humans": [...]      # 写进 people.json 的 humans[]
  }

规则：
  * 镜号形如 "场号-序号"；插入镜后同一场内镜号顺序重排；插入场后其后场号整体后移，
    场内的镜号前缀同步改写（避免镜号与场号脱节）。
  * 场时长 = 该场各镜时长之和；集时长 = 各场时长之和（与 build_season.py 的口径一致）。

用法：
  E:/Python/python.exe tools/apply_patches.py
  E:/Python/python.exe tools/apply_patches.py --only fix_final.json people_gods.json

  --only <file...>  只应用指定的 patch 文件（分号或逗号分隔也可）。
  已有 patch 是一次性应用的：insert_scene / insert_shot 不幂等，
  重复跑会把新场新镜重复插进去。要再改剧本时，只用 --only 指定新 patch。
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CANON = ROOT / "_canon"
PARTS = CANON / "_parts"
PATCH = CANON / "_patch"

# 分片文件 → 该分片覆盖的集号
PART_EPS = {
    "s04_08.json": range(4, 9),
    "s09_16.json": range(9, 17),
    "s17_24.json": range(17, 25),
}


def split_no(no):
    """'3-5' → (3, 5)；'3' → (3, None)"""
    s = str(no)
    if "-" in s:
        a, b = s.split("-", 1)
        try:
            return int(a), int(b)
        except ValueError:
            return None, None
    return None, None


def renumber_scene(sc, new_scene_no):
    """把一场内的镜号前缀改成新场号，序号按顺序重排。"""
    for i, sh in enumerate(sc.get("shots", []), 1):
        sh["no"] = f"{new_scene_no}-{i}"


def apply_shots(ep_obj, changes, log):
    eps = ep_obj["ep"]
    for ch in changes:
        if "insert_shot" in ch:
            spec = ch["insert_shot"]
            after = str(spec["after"])
            new_shot = dict(spec["shot"])
            target_scene = None
            for sc in ep_obj["scenes"]:
                if any(str(sh.get("no")) == after for sh in sc.get("shots", [])):
                    target_scene = sc
                    break
            if target_scene is None:
                log.append(f"  [SKIP] ep{eps} insert_shot after={after} 找不到该镜")
                continue
            shots = target_scene["shots"]
            idx = next(i for i, sh in enumerate(shots) if str(sh.get("no")) == after)
            shots.insert(idx + 1, new_shot)
            renumber_scene(target_scene, target_scene["no"])
            log.append(f"  ep{eps} 场{target_scene['no']} 在 {after} 后插入 1 镜")
        else:
            sn = str(ch["shot"])
            hit = None
            for sc in ep_obj["scenes"]:
                for sh in sc.get("shots", []):
                    if str(sh.get("no")) == sn:
                        hit = sh
                        break
                if hit:
                    break
            if hit is None:
                log.append(f"  [SKIP] ep{eps} shot={sn} 不存在")
                continue
            for k in ("action", "duration", "shot", "move"):
                if k in ch:
                    hit[k] = ch[k]
            log.append(f"  ep{eps} 镜{sn} 已改写"
                       + (f"（duration={ch['duration']}）" if "duration" in ch else ""))


def apply_scene_meta(ep_obj, changes, log):
    eps = ep_obj["ep"]
    for ch in changes:
        if "scene" not in ch:
            continue
        sc = next((s for s in ep_obj["scenes"] if s.get("no") == ch["scene"]), None)
        if sc is None:
            log.append(f"  [SKIP] ep{eps} 场{ch['scene']} 不存在")
            continue
        for k in ("characters", "props", "place", "time", "vfx", "name", "desc"):
            if k in ch:
                sc[k] = ch[k]
        log.append(f"  ep{eps} 场{sc['no']} 元信息已更新（{','.join(k for k in ('characters','props','place','time','vfx','name','desc') if k in ch)}）")


def apply_insert_scene(ep_obj, changes, log):
    eps = ep_obj["ep"]
    for ch in changes:
        spec = ch["insert_scene"]
        before = spec.get("before_scene")
        new_scene = dict(spec["scene"])
        new_scene.setdefault("props", [])
        new_scene.setdefault("vfx", "")
        new_scene.setdefault("desc", "")
        new_scene.setdefault("characters", [])
        new_scene.setdefault("time", "")
        new_scene.setdefault("place", "")
        scenes = ep_obj["scenes"]
        if before is None:
            pos = len(scenes)
            new_no = (scenes[-1]["no"] + 1) if scenes else 1
        else:
            idx = next((i for i, s in enumerate(scenes) if s["no"] == before), None)
            if idx is None:
                log.append(f"  [SKIP] ep{eps} insert_scene before_scene={before} 不存在")
                continue
            pos = idx
            new_no = before
        scenes.insert(pos, new_scene)
        # 其后的场号整体后移，并同步各场镜号前缀
        for i, sc in enumerate(scenes, 1):
            if sc is new_scene:
                sc["no"] = new_no
                renumber_scene(sc, new_no)
            elif i - 1 >= pos and sc.get("no", 0) >= new_no:
                sc["no"] = sc["no"] + 1
                renumber_scene(sc, sc["no"])
        log.append(f"  ep{eps} 在场{before} 之前插入新场（新场号 {new_no}）")


def recompute(ep_obj):
    for sc in ep_obj["scenes"]:
        sc["duration"] = sum(int(sh.get("duration") or 0) for sh in sc.get("shots", []))
    ep_obj["total"] = sum(int(sc["duration"]) for sc in ep_obj["scenes"])
    ep_obj["target"] = ep_obj["total"]


def main():
    argv = sys.argv[1:]
    only = None
    if argv and argv[0] == "--only":
        only = set()
        for a in argv[1:]:
            for piece in a.replace(";", ",").split(","):
                piece = piece.strip()
                if piece:
                    only.add(piece)
    if not PATCH.exists():
        print(f"[FATAL] 没有 patch 目录：{PATCH}")
        return 1
    # 先改台词/时长，再插场：插入场会重排场号与镜号，
    # 若顺序颠倒，按旧镜号定位的改写会落到错误的镜头上。
    patch_files = sorted(PATCH.glob("*.json"),
                         key=lambda p: (0 if p.name.startswith("fix_") else
                                        1 if p.name.startswith("beats_") else 2,
                                        p.name))
    if only:
        patch_files = [p for p in patch_files if p.name in only]
        missing = only - {p.name for p in patch_files}
        if missing:
            print(f"[FATAL] --only 指定的文件不存在：{', '.join(sorted(missing))}")
            return 1
    if not patch_files:
        print("[FATAL] _patch 下没有可应用的 patch 文件")
        return 1

    # 载入分片
    parts = {}
    for fname in PART_EPS:
        parts[fname] = json.loads((PARTS / fname).read_text(encoding="utf-8"))

    log = []
    humans_extra = []
    for pf in patch_files:
        data = json.loads(pf.read_text(encoding="utf-8"))
        print(f"[PATCH] {pf.name}")
        default_file = data.get("file")
        # 单条 shot / scene 可以用 "file" 字段覆盖默认分片（一次 patch 跨多个分片时用）
        for ch in data.get("shots", []) + data.get("scenes", []):
            fname = ch.get("file") or default_file
            if fname and fname in parts:
                by_ep = {e["ep"]: e for e in parts[fname]}
                ep_obj = by_ep.get(ch.get("ep"))
                if ep_obj is None:
                    log.append(f"  [SKIP] {pf.name} ep{ch.get('ep')} 不在 {fname}")
                    continue
                if "insert_shot" in ch or "shot" in ch or "action" in ch or "duration" in ch:
                    apply_shots(ep_obj, [ch], log)
                if "scene" in ch:
                    apply_scene_meta(ep_obj, [ch], log)
                if "insert_scene" in ch:
                    apply_insert_scene(ep_obj, [ch], log)
            elif fname:
                print(f"  [WARN] 未知分片 {fname}")
        for h in data.get("append_humans", []):
            humans_extra.append(h)

    for fname, eps in parts.items():
        for e in eps:
            recompute(e)

    for fname, eps in parts.items():
        (PARTS / fname).write_text(
            json.dumps(parts[fname], ensure_ascii=False, indent=2), encoding="utf-8")
        tot = sum(e["total"] for e in parts[fname])
        print(f"  已写回 {fname}：{len(parts[fname])} 集 · {tot}″")

    if humans_extra:
        pp = CANON / "people.json"
        ppl = json.loads(pp.read_text(encoding="utf-8"))
        have = {h.get("name") for h in ppl.get("humans", [])}
        added = []
        for h in humans_extra:
            if h.get("name") in have:
                continue
            ppl.setdefault("humans", []).append(h)
            added.append(h.get("name"))
        pp.write_text(json.dumps(ppl, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  people.json：新增主档 {len(added)} 人 → {', '.join(added)}")

    print("---- 修改明细 ----")
    for line in log:
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
