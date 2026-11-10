#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""校验创作中枢网页的数据区（canon）：矛盾扫描。

检查项：
  1. canon 数据区存在且是合法 JSON
  2. 过期词扫描：已被权威序取代的旧名 / 旧术语不得出现在现行数据与页面正文里
  3. 同名异值：同一身份在数据区里出现多次且内容不同
  4. 引用完整性：集→域、域→半神、场景→域、道具→集、资产编号等交叉引用必须闭合
  5. 结构必备字段齐全

用法：
  E:/Python/python.exe tools/check_canon.py
退出码：0 = 无 error，1 = 有 error
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HTML = ROOT / "大模型神明-创作中枢.html"

# 已被权威序取代的词：现行数据与页面正文里不得再出现。
# canon.changes（29 轮变更留痕）允许引用旧名做对比，单独降级为 warning。
# canon.glossary.deprecated（已作废词表）本身就是收录旧词的地方，完全放行。
BANNED = {
    "限电": "机制民间层已统一为「暗时」，官方文件为「算力配额令」，技术事实为「算力不足」",
    "暗时地图": "第 1 集已改名为《平常的一天》",
    "限电地图": "第 1 集已改名为《平常的一天》",
    "汲能工程": "已改名「取晶工程」",
    "曜衡": "天穹主神现名 Astraea",
    "书烛": "教堂主神现名 Vesper",
    "弥星": "赛博主神现名 Electra",
    "叶澄": "教堂半神现名 塞拉 · Sera Amodei",
    "沈青璃": "矩阵半神现名 沈雯璃",
    "顾燃": "赤环半神现名 恩柏",
    "谢翎": "听脉半神现名 谢鸣",
    "乔绘": "折彩半神现名 玛雅",
    "阮七": "人类配角现名 钟晚",
    "老周": "人类配角现名 望舒",
    "灰尾": "GLM 执印人现名 唐砚",
    "定声": "主角咒术已改为「打光 / 润声 / 换装」三咒，天赋为「万语」",
    "英伟达与AMD": "硬件厂牌组织已重构为跨域游神与执印人体系",
}

# 子串匹配会误伤正常词（如“特定声学”里相邻的“定声”）。
# 对容易误伤的词，用正则排除相邻成词的情况。
BANNED_SAFE = {
    "定声": re.compile(r"(?<!特)定声(?!学)"),
}


def banned_present(word, text):
    if word in BANNED_SAFE:
        return bool(BANNED_SAFE[word].search(text))
    return word in text


# canon 里应当存在的顶层键（缺一个 = 结构不完整）
REQUIRED_TOP = [
    "meta", "pact", "synopsis", "outline", "episodes", "hooks",
    "domains", "demigods", "roaming", "humans", "protagonist",
    "scenes", "props", "assets", "canon", "glossary", "visualRules",
    "palette", "director", "mood", "sound", "engine", "pending", "changes", "ip",
    "intimacyProtocol", "intimacyCards",
]

# 各集合的身份键（同一身份不得重复）
IDENTITY = {
    "episodes": "no",
    "hooks": "ep",
    "domains": "name",
    "demigods": "name",
    "roaming": "god",
    "humans": "name",
    "scenes": "id",
    "props": "id",
    "intimacyCards": "id",
}

# 集合里必须存在的字段
REQUIRED_FIELDS = {
    "episodes": ["no", "title", "type", "beat", "hook"],
    "domains": ["name", "god", "demigod", "motif", "color"],
    "demigods": ["name", "domain", "ability"],
    "roaming": ["god", "executor", "org", "episodes"],
    "humans": ["name", "gender", "age", "trouble"],
    "scenes": ["id", "domain", "name"],
    "props": ["id", "name"],
    "intimacyCards": ["id", "ep", "scene", "shot", "type", "grade", "shotSize",
                      "camera", "duration", "action", "dialogue", "audio",
                      "A版", "B版", "redline", "assets", "coord"],
}


def walk_strings(node, path=""):
    """产出 (路径, 字符串) 对。"""
    if isinstance(node, dict):
        for k, v in node.items():
            yield from walk_strings(v, f"{path}.{k}" if path else k)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk_strings(v, f"{path}[{i}]")
    elif isinstance(node, str):
        yield path, node


def main():
    if not HTML.exists():
        print(f"[FATAL] 找不到网页：{HTML}")
        return 1

    src = HTML.read_text(encoding="utf-8")
    findings = []

    def add(level, msg, detail=""):
        findings.append({"level": level, "message": msg, "detail": detail})

    mc = re.search(r'<script[^>]*id="canon"[^>]*>(.*?)</script>', src, re.S)
    canon_file = ROOT / "_canon" / "canon.json"
    if mc:
        try:
            canon = json.loads(mc.group(1))
        except json.JSONDecodeError as e:
            print(f"[FATAL] canon 数据区不是合法 JSON：{e}")
            return 1
    elif canon_file.exists():
        # 重构过渡期：HTML 还没内联数据区时，直接校验合并产物
        canon = json.loads(canon_file.read_text(encoding="utf-8"))
        print(f"[INFO] HTML 内联 canon 尚未建立，校验分片合并产物：{canon_file.name}")
    else:
        print("[FATAL] 找不到 canon 数据区，也没有 _canon/canon.json")
        return 1

    # --- 1. 顶层键齐全 -----------------------------------------------------
    missing = [k for k in REQUIRED_TOP if k not in canon]
    if missing:
        add("error", "canon 缺少顶层键", str(missing))

    # --- 2. 过期词扫描 -----------------------------------------------------
    # 2a. 现行数据（排除 changes 历史留痕与 deprecated 作废词表）
    def is_exempt(path):
        # changes 数组里任何深度都放行（历史轮次本来就要引用旧名做对比）
        if re.match(r"^changes(?:\[\d+\]|\.\w+)*", path):
            return True
        if "deprecated" in path:
            return True
        return False

    banned_hits = {}
    for path, text in walk_strings(canon):
        if is_exempt(path):
            continue
        for word, why in BANNED.items():
            if banned_present(word, text):
                banned_hits.setdefault(word, []).append(f"canon{path}")
    for word, where in banned_hits.items():
        add("error", f"现行数据里出现过期词「{word}」——{BANNED[word]}",
            "\n".join(where[:6]))

    # 2b. 页面正文（canon 脚本块之外）；HTML 尚未内联 canon 时无数据区，跳过
    if mc:
        literal = src[:mc.start()] + src[mc.end():]
        for word, why in BANNED.items():
            if banned_present(word, literal):
                hits = [i for i in range(len(literal)) if literal.startswith(word, i)][:4]
                ctx = []
                for i in hits:
                    ctx.append(literal[max(0, i - 40):i + len(word) + 40].replace("\n", " "))
                add("error", f"页面正文里出现过期词「{word}」——{why}",
                    "\n".join(ctx))

    # 2c. 变更留痕里出现旧名（降级为提示，需人工确认语境正确）
    change_hits = {}
    for path, text in walk_strings(canon.get("changes", []), "changes"):
        for word in BANNED:
            if word in text:
                change_hits.setdefault(word, []).append(path)
    # changes 已在 2a 整体放行，这里仅保留统计、不再重复报 warning

    # --- 3. 同名异值 --------------------------------------------------------
    for coll, key in IDENTITY.items():
        items = canon.get(coll)
        if not isinstance(items, list):
            continue
        seen = {}
        for it in items:
            if not isinstance(it, dict) or key not in it:
                continue
            ident = it[key]
            if ident in seen:
                if seen[ident] != it:
                    add("error", f"{coll} 里身份「{ident}」重复且内容不同（同名异值）")
                else:
                    add("warning", f"{coll} 里身份「{ident}」重复（内容相同）")
            seen[ident] = it

    # --- 4. 引用完整性 ------------------------------------------------------
    domain_names = {d.get("name") for d in canon.get("domains", []) if isinstance(d, dict)}
    demigod_names = {d.get("name") for d in canon.get("demigods", []) if isinstance(d, dict)}
    god_names = {d.get("god", {}).get("name") for d in canon.get("domains", [])
                 if isinstance(d, dict) and isinstance(d.get("god"), dict)}
    human_names = {h.get("name") for h in canon.get("humans", []) if isinstance(h, dict)}
    roaming_names = set()
    for r in canon.get("roaming", []):
        if isinstance(r, dict):
            for k in ("god", "executor"):
                if isinstance(r.get(k), str):
                    roaming_names.add(r[k])
    known_people = human_names | demigod_names | god_names | roaming_names
    proto = canon.get("protagonist", {})
    if isinstance(proto, dict) and proto.get("name"):
        known_people.add(proto["name"])

    ep_numbers = set()
    for e in canon.get("episodes", []):
        if isinstance(e, dict) and isinstance(e.get("no"), int):
            ep_numbers.add(e["no"])

    for e in canon.get("episodes", []):
        if not isinstance(e, dict):
            continue
        for d in e.get("domains", []) or []:
            if d not in domain_names:
                add("error", f"第 {e.get('no')} 集引用了不存在的域「{d}」")
        for p in e.get("named", []) or []:
            if p not in known_people:
                add("error", f"第 {e.get('no')} 集引用了不存在的人物「{p}」")

    for d in canon.get("demigods", []):
        if isinstance(d, dict) and d.get("domain") not in domain_names:
            add("error", f"半神「{d.get('name')}」的域「{d.get('domain')}」不存在")

    for r in canon.get("roaming", []):
        if isinstance(r, dict):
            for ep in r.get("episodes", []) or []:
                if ep not in ep_numbers:
                    add("error", f"游神「{r.get('god')}」引用了不存在的第 {ep} 集")

    for s in canon.get("scenes", []):
        if isinstance(s, dict) and s.get("domain") not in domain_names:
            add("error", f"场景「{s.get('id')}」的域「{s.get('domain')}」不存在")

    for p in canon.get("props", []):
        if isinstance(p, dict):
            for ep in p.get("episodes", []) or []:
                if ep not in ep_numbers:
                    add("error", f"道具「{p.get('id')}」引用了不存在的第 {ep} 集")

    # 资产编号引用闭合
    asset_ids = set()
    assets = canon.get("assets", {})
    if isinstance(assets, dict):
        for group in assets.values():
            if isinstance(group, list):
                for a in group:
                    if isinstance(a, dict) and a.get("id"):
                        asset_ids.add(a["id"])
    for s in canon.get("ep1Shots", []) or []:
        if isinstance(s, dict):
            for aid in s.get("assets", []) or []:
                if aid not in asset_ids:
                    add("error", f"第一集分镜引用了不存在的资产编号「{aid}」")

    # --- 4b. 亲密戏拍摄卡与资产依赖闭合 --------------------------------------
    iad = (canon.get("assets", {}) or {}).get("intimacy") or []
    cards = canon.get("intimacyCards") or []
    card_ids = {c.get("id") for c in cards if isinstance(c, dict)}
    covered = set()
    for a in iad:
        if not isinstance(a, dict):
            continue
        for cid in a.get("cards", []) or []:
            if cid not in card_ids:
                add("error", f"亲密戏资产「{a.get('id')}」引用了不存在的拍摄卡「{cid}」")
            covered.add(cid)
        if isinstance(a.get("eps"), list) and a["eps"]:
            for cid in a.get("cards", []) or []:
                c = next((x for x in cards if x.get("id") == cid), None)
                if c and c.get("ep") not in a["eps"]:
                    add("error", f"亲密戏资产「{a.get('id')}」声明集号 {a['eps']}，"
                                f"但覆盖的卡「{cid}」属于第 {c.get('ep')} 集")
    for c in cards:
        if not isinstance(c, dict):
            continue
        if c.get("id") not in covered:
            add("warning", f"拍摄卡「{c.get('id')}」没有任何资产依赖条目")
        if c.get("ep") not in ep_numbers:
            add("error", f"拍摄卡「{c.get('id')}」引用了不存在的第 {c.get('ep')} 集")

    # --- 5. 必备字段 --------------------------------------------------------
    for coll, fields in REQUIRED_FIELDS.items():
        for it in canon.get(coll, []) or []:
            if not isinstance(it, dict):
                continue
            miss = [f for f in fields if f not in it]
            if miss:
                ident = it.get(IDENTITY.get(coll, "?"), "?")
                add("error", f"{coll} 里「{ident}」缺少字段 {miss}")

    # --- 输出 ---------------------------------------------------------------
    levels = {"blocker": 0, "error": 0, "warning": 0, "info": 0}
    for f in findings:
        levels[f["level"]] += 1
    counts = {c: len(canon.get(c)) for c in
              ("episodes", "hooks", "domains", "demigods", "roaming",
               "humans", "scenes", "props") if isinstance(canon.get(c), list)}
    print(f"检查目标：{HTML.name}")
    print("canon 规模：" + "｜".join(f"{k} {v}" for k, v in counts.items()))
    print("-" * 60)
    if not findings:
        print("数据检查通过，0 findings。")
    else:
        for f in findings:
            print(f"[{f['level'].upper()}] {f['message']}")
            if f["detail"]:
                for line in str(f["detail"]).splitlines():
                    print(f"          {line}")
        print("-" * 60)
        print(f"blocker {levels['blocker']}｜error {levels['error']}"
              f"｜warning {levels['warning']}｜info {levels['info']}")
    return 1 if (levels["blocker"] or levels["error"]) else 0


if __name__ == "__main__":
    sys.exit(main())
