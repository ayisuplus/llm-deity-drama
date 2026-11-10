#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全篇一致性审计：查 check_canon 覆盖不到的逻辑矛盾。

check_canon 管的是「引用闭合」与「过期词」；本脚本管的是**跨字段的逻辑矛盾**：
  1. 节奏指标：登场神域数、有专名角色数、事件点上限（A1 / engine.metrics）
  2. 出场对账：人物档案声明的出场集 vs 分集 named（双向差集）
  3. 集型分布与 episodeTypes 登记是否一致
  4. 时间线数字：同一人物/事件的年龄与年数是否自洽（十 / 十一 / 二十年前 + 岁数）
  5. 打戏覆盖：全季是否至少 3 场会战、且集中在中段之后
  6. 钩子与 beat 不同源（钩子文本不应直接复制 beat 长句）

用法：
  E:/Python/python.exe tools/check_consistency.py
退出码：0 = 无 error，1 = 有 error
"""

import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HTML = ROOT / "大模型神明-创作中枢.html"

# A1：事件点上限。第 1 集从宽；幕末/真相/高潮/会战/收束集 ≤9，其余 ≤6。
EP_CAP9 = {14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24}
EP_CAP_UNLIMITED = {1}
# 登场神域数：默认 ≤2；群像集 3 域；第 1 集 1 域
DOMAIN_3 = {12, 13}
# 有专名角色数：默认从 engine.metrics 读（limit + exempt）；旧版常量只做兜底
NAMED_CAP = 6
NAMED_EXEMPT = {14, 19, 22, 23, 24}

RE_NUM = re.compile(r"\d+")


def load_canon():
    src = HTML.read_text(encoding="utf-8")
    m = re.search(r'<script[^>]*id="canon"[^>]*>(.*?)</script>', src, re.S)
    if m:
        return json.loads(m.group(1))
    return json.loads((ROOT / "_canon" / "canon.json").read_text(encoding="utf-8"))


def nums(s):
    """从「2、5、11（远景）、19」这类字符串里取出集号。"""
    if isinstance(s, list):
        return {x for x in s if isinstance(x, int)}
    if not isinstance(s, str):
        return set()
    return {int(x) for x in RE_NUM.findall(s) if 1 <= int(x) <= 24}


def main():
    canon = load_canon()
    findings = []

    def add(level, msg, detail=""):
        findings.append({"level": level, "message": msg, "detail": detail})

    episodes = canon.get("episodes", [])
    by_no = {e["no"]: e for e in episodes if isinstance(e.get("no"), int)}

    # 专名角色上限与豁免：优先读 engine.metrics（数据层是唯一口径）
    named_cap = NAMED_CAP
    named_exempt = set(NAMED_EXEMPT)
    for m in (canon.get("engine") or {}).get("metrics") or []:
        if isinstance(m, dict) and m.get("no") == 2:
            mm = re.search(r"(\d+)", str(m.get("limit") or ""))
            if mm:
                named_cap = int(mm.group(1))
            if isinstance(m.get("exempt"), list):
                named_exempt = {int(x) for x in m["exempt"]}

    # ── 1. 节奏指标 ──────────────────────────────────────────────
    for e in episodes:
        no = e["no"]
        if no in EP_CAP_UNLIMITED:
            cap = None
        else:
            cap = 9 if no in EP_CAP9 else 6
        ev = e.get("events")
        if ev is None:
            add("error", f"第 {no} 集 events 为空", "A1 要求每集有事件点计数")
        elif cap is not None and ev > cap:
            add("error", f"第 {no} 集事件点 {ev} 超过上限 {cap}")

        dn = len(e.get("domains") or [])
        dcap = 3 if no in DOMAIN_3 else (1 if no == 1 else 2)
        if dn > dcap:
            add("error", f"第 {no} 集登场神域 {dn} 个，超过上限 {dcap}")

        nn = len(e.get("named") or [])
        if no not in named_exempt and nn > named_cap:
            add("warning", f"第 {no} 集有专名角色 {nn} 人，超过常规上限 {named_cap}",
                "、".join(e.get("named") or []))

    # ── 2. 出场对账 ──────────────────────────────────────────────
    appear = {}
    for e in episodes:
        for n in e.get("named") or []:
            appear.setdefault(n, set()).add(e["no"])

    def cmp(name, declared, kind):
        dec = nums(declared)
        act = appear.get(name, set())
        miss = sorted(dec - act)   # 档案声明出场，但分集没列
        extra = sorted(act - dec)  # 分集列了，但档案没声明
        if miss:
            add("warning", f"[{kind}]「{name}」档案声明出场第 {miss} 集，但分集 named 里没有")
        if extra:
            add("warning", f"[{kind}]「{name}」在第 {extra} 集 named 里出现，但档案没声明出场")

    for h in canon.get("humans", []):
        cmp(h.get("name"), h.get("episodes"), "人类")
    for d in canon.get("demigods", []):
        cmp(d.get("name"), (d.get("profile") or {}).get("出场"), "半神")
    for d in canon.get("domains", []):
        gp = d.get("godProfile") or {}
        cmp((d.get("god") or {}).get("name"), gp.get("出场"), "主神")
    for r in canon.get("roaming", []):
        cmp(r.get("god"), r.get("episodes"), "游神")

    # ── 3. 集型分布 ──────────────────────────────────────────────
    types = Counter(e.get("type") for e in episodes)
    reg = {(x["name"] or "").replace("集", ""): x
           for x in (canon.get("engine", {}).get("episodeTypes") or [])}
    for t, n in types.items():
        if t not in reg:
            add("error", f"集型「{t}」未在 engine.episodeTypes 登记")
        elif reg[t].get("count") != n:
            add("warning", f"集型「{t}」实际 {n} 集，engine 登记 {reg[t].get('count')} 集")

    # ── 4. 时间线自洽：程栖年龄 ───────────────────────────────────
    proto = canon.get("protagonist", {})
    age_now = proto.get("age")
    childhood = proto.get("childhood") or ""
    m = re.search(r"十一年前她(\d+)岁", childhood)
    if m and isinstance(age_now, int):
        claimed = int(m.group(1))
        if claimed + 11 != age_now:
            add("error", f"程栖年龄不自洽：childhood 说十一年前 {claimed} 岁，但当前年龄是 {age_now}")
    # 全站扫描「十年前程栖十岁」这类与上面对冲的写法
    def walk(node, path=""):
        if isinstance(node, dict):
            for k, v in node.items():
                walk(v, f"{path}.{k}" if path else k)
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{path}[{i}]")
        elif isinstance(node, str):
            if path.startswith("changes"):
                return
            if re.search(r"十年前.{0,6}程栖.{0,3}十岁", node):
                add("error", "时间线矛盾：出现「十年前…程栖…十岁」",
                    f"canon.{path}：{node[:80]}")
            if re.search(r"今天仍是十六七岁", node):
                add("error", "半神外貌口径回归旧版：沈雯璃不能看着比程栖小",
                    f"canon.{path}：{node[:80]}")
    walk(canon)

    # ── 5. 打戏覆盖 ──────────────────────────────────────────────
    combat = (canon.get("canon") or {}).get("combat") or {}
    fights = combat.get("五场打戏") or []
    if len(fights) < 3:
        add("error", f"打戏不足 3 场（现 {len(fights)} 场）——史诗战争题材不能只有气氛")
    fight_eps = sorted(f.get("集") for f in fights if isinstance(f.get("集"), int))
    if fight_eps and all(ep <= 12 for ep in fight_eps):
        add("warning", "所有打戏都在前 12 集，后段缺会战", str(fight_eps))

    # ── 6. 钩子与 beat 不同源 ────────────────────────────────────
    for e in episodes:
        hook = (e.get("hook") or "").strip()
        beat = (e.get("beat") or "").strip()
        if hook and len(hook) > 30 and hook in beat:
            add("warning", f"第 {e['no']} 集钩子直接复制了 beat 长句（钩子应短、应切黑）")

    # ── 输出 ────────────────────────────────────────────────────
    levels = {"blocker": 0, "error": 0, "warning": 0, "info": 0}
    for f in findings:
        levels[f["level"]] += 1
    print(f"检查目标：{HTML.name}")
    print(f"24 集｜集型 {dict(types)}｜打戏 {len(fights)} 场 {fight_eps}")
    print("-" * 60)
    if not findings:
        print("一致性检查通过，0 findings。")
    else:
        for f in findings:
            print(f"[{f['level'].upper()}] {f['message']}")
            if f["detail"]:
                print(f"          {f['detail']}")
        print("-" * 60)
        print(f"blocker {levels['blocker']}｜error {levels['error']}"
              f"｜warning {levels['warning']}｜info {levels['info']}")
    return 1 if (levels["blocker"] or levels["error"]) else 0


if __name__ == "__main__":
    sys.exit(main())
