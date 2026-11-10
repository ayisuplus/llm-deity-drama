#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""集末结构体检：钩子位置、卡点切黑、时长上限、签名镜头与四城四阶重头床戏的落位（已全面撤除余温镜）。

检查项：
  1. 每集最后一镜必须以「卡点切黑」收尾（真收尾，不许伪切黑）
  2. 全季内不许出现"伪卡点切黑"（写了卡点切黑但后面还有内容）
  3. 单集时长 ≤ 960 秒（16 分钟）
  4. 六格签名镜头（第 12/15/18/20/23/24 集）与四场重头床戏（第 12/16/19/21 集）必须存在且位置正确
  5. 全季严禁残留任何「余温镜」场次
  6. 第 16/19/21 集三场新增重头床戏严禁出现嘴对嘴亲吻（全季唇吻只留第 12/24 集两次）

用法：
  E:/Python/python.exe tools/check_tail.py
退出码：0 = 无 error，1 = 有 error
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEASON = ROOT / "_canon" / "season.json"

MAX_EP = 960
SIGNATURE = {12, 15, 18, 20, 23, 24}
BED_SCENES = {12, 16, 19, 21}
# 六格签名镜头在各集里可能独立成场，也可能并入主线场；用关键词判定它的存在
SIGNATURE_KEYS = {
    12: ["先吻后做", "吻是没有条款的"],
    15: ["剧末签名镜头", "把她的领口理好", "把领口理正"],
    18: ["动作停在了半途", "离得很近"],
    20: ["嘴唇几乎碰到程栖的耳朵"],
    23: ["额头抵着她的额头"],
    24: ["程栖抬手，主动吻了上去"],
}
BED_KEYS = {
    12: ["先吻后做", "吻是没有条款的"],
    16: ["床戏二", "解开的军装立领"],
    19: ["床戏三", "失声哑剧"],
    21: ["床戏四", "值班室百叶窗拉下"],
}
HOOK_MARK = "卡点切黑"
WARM_MARK = "余温镜"

errors = []
warnings = []


def shot_text(sc, sh):
    return f"{sc.get('name','')}|{sh.get('action','')}"


def main():
    data = json.loads(SEASON.read_text(encoding="utf-8"))
    eps = data["seasonScript"]

    for e in eps:
        ep = e["ep"]
        scenes = e["scenes"]
        shots = [(sc, sh) for sc in scenes for sh in sc.get("shots", [])]

        # 3) 时长
        total = sum(int(sh.get("duration") or 0) for _, sh in shots)
        if total > MAX_EP:
            errors.append(f"ep{ep} 时长 {total}s 超上限 {MAX_EP}s（{total/60:.1f} 分钟）")

        # 2) 伪切黑
        for i, (sc, sh) in enumerate(shots):
            if HOOK_MARK in sh.get("action", ""):
                rest = sum(int(s2.get("duration") or 0) for _, s2 in shots[i + 1:])
                if rest > 0:
                    errors.append(
                        f"ep{ep} 场{sc['no']} 镜{sh['no']} 写了「{HOOK_MARK}」但其后还有 {rest}s 内容（伪切黑）")

        # 1) 真收尾
        if not shots:
            errors.append(f"ep{ep} 没有镜头")
            continue
        last_sc, last_sh = shots[-1]
        if HOOK_MARK not in last_sh.get("action", ""):
            errors.append(f"ep{ep} 最后一镜（场{last_sc['no']} 镜{last_sh['no']}）没有「{HOOK_MARK}」")

        # 4/5/6) 严禁残留余温镜 + 检查四场重头床戏与六格签名镜头
        warm_scenes = [sc for sc in scenes if WARM_MARK in sc.get("name", "")]
        if warm_scenes:
            errors.append(f"ep{ep} 残留了已废除的「{WARM_MARK}」场（共 {len(warm_scenes)} 场）")

        if ep in BED_SCENES:
            bkeys = BED_KEYS.get(ep, [])
            bhit = any(k in shot_text(sc, sh) for sc, sh in shots for k in bkeys)
            if not bhit:
                errors.append(f"ep{ep} 找不到四城四阶重头床戏（关键词 {bkeys}）")
            if ep in {16, 19, 21}:
                bed_sc = [sc for sc in scenes if "床戏" in sc.get("name", "")]
                for bsc in bed_sc:
                    for bsh in bsc.get("shots", []):
                        act = bsh.get("action", "")
                        for bad in ("先吻", "亲吻", "接吻", "吻上去"):
                            if bad in act:
                                errors.append(f"ep{ep} 床戏出现唇吻词「{bad}」——全季嘴对嘴真吻只留第 12/24 集两次")

        if ep in SIGNATURE:
            keys = SIGNATURE_KEYS.get(ep, [])
            hit = any(k in shot_text(sc, sh) for sc, sh in shots for k in keys)
            if not hit:
                errors.append(f"ep{ep} 找不到六格签名镜头（关键词 {keys}）")

    print("=" * 60)
    if errors:
        print(f"ERROR ({len(errors)})：")
        for x in errors:
            print("  ✗", x)
    if warnings:
        print(f"WARN ({len(warnings)})：")
        for x in warnings:
            print("  !", x)
    if not errors:
        print("集末结构体检：全部通过")
    print("=" * 60)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
