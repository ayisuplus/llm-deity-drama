#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""装配全季剧本与分镜：把第 1–3 集（已有）与第 4–24 集（分段草稿）合成单一分片。

输入：
  _canon/production.json      → ep1Shots（第 1 集分镜）、ep2Scenes（第 2 集）、ep3Scenes（第 3 集）
  _canon/_parts/s04_08.json   → 第 4–8 集
  _canon/_parts/s09_16.json   → 第 9–16 集
  _canon/_parts/s17_24.json   → 第 17–24 集
输出：
  _canon/season.json          → {"seasonScript": [ 24 集，逐场逐镜 ]}

第 1 集的分场由 ep1Shots 按镜号区间归组；第 2、3 集直接沿用 production.json 的场次表。
本脚本是确定性的装配器，不改写任何剧本内容。

用法：E:/Python/python.exe tools/build_season.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CANON = ROOT / "_canon"
PARTS = CANON / "_parts"
OUT = CANON / "season.json"

# 第 1 集：把 15 镜按场景归组（镜号区间，含端点）
EP1_SCENE_GROUPS = [
    (1, 2, {
        "no": 1,
        "name": "深海观景拱廊·黄金前15秒掉帧翻车",
        "place": "临街观景拱廊 LOC-03",
        "time": "日（开场倒叙提亮）",
        "duration": 15,
        "characters": ["程栖"],
        "props": ["噗噗 PROP101"],
        "vfx": "拉丁换装咒星纱图层、2 FPS掉帧卡顿红框、阿汐恶作剧小鲸鱼兜帽耳",
        "desc": "黄金前15秒：高定换装大片一秒掉帧成 2 FPS，礼服卡在原地，再叠加阿汐借噗噗投出的小鲸鱼兜帽耳恶作剧，瞬间立住世界观与喜剧反差。",
    }),
    (3, 3, {
        "no": 2,
        "name": "短租房清晨·15句配额与旧表",
        "place": "深海短租房 SCN102 / LOC-01",
        "time": "清晨",
        "duration": 30,
        "characters": ["程栖"],
        "props": ["噗噗 PROP101", "直播设备箱 PROP102", "福利院旧磁带与同伴旧表 PROP103"],
        "vfx": "配额通知面板",
        "desc": "闪回清晨短租房，展现今日剩余15句配额、04:17停摆旧表与二手设备箱，建立主角寄居攒钱的真实处境。",
    }),
    (4, 9, {
        "no": 3,
        "name": "深海市集与热食摊·三大省句整活名场面",
        "place": "下层市集与老陶热食摊 SCN104 / LOC-02",
        "time": "上午—中午",
        "duration": 250,
        "characters": ["程栖", "老陶", "阿豆", "沈雯璃（手部·不露脸）"],
        "props": ["噗噗 PROP101", "老陶明火灶 PROP108", "鲸纹碗勺"],
        "vfx": "排队第47位浮窗、神龛水母宝珠转圈深度思考12秒、直播双榜一界面",
        "desc": "路人念烘干咒排队挨冻 vs 程栖蹭老陶排风扇立省两句；神龛转圈12秒吐出「建议步行」；直播间榜一🐋与值班室冷白手指偷点收藏2秒快切。",
    }),
    (10, 11, {
        "no": 4,
        "name": "码头异响与观景廊双层世界",
        "place": "老陶热食摊 SCN104 → 观景廊 LOC-03",
        "time": "下午—傍晚",
        "duration": 90,
        "characters": ["程栖", "老陶"],
        "props": ["噗噗 PROP101", "直播设备箱 PROP102"],
        "vfx": "补光灯暖框与框外成排熄灭的暗时街区对比",
        "desc": "招牌动作「你们听一下」首次捕捉深处稳定低频嗡鸣，被老陶按灭红灯警告；傍晚补光灯内外形成冷暖两个世界的视觉反差。",
    }),
    (12, 15, {
        "no": 5,
        "name": "短租房深夜·三连视听暴击强钩",
        "place": "深海短租房 SCN102 / LOC-01",
        "time": "夜",
        "duration": 125,
        "characters": ["程栖"],
        "props": ["噗噗 PROP101", "陌生画面 MAT-01 / PROP106"],
        "vfx": "剪辑轴2帧整齐烧焦废墟、缺失Fiat音轨波形、噗噗黑豆豆眼骤变阿汐幽蓝竖瞳",
        "desc": "夜里拉时间轴剪片，掉帧处闪过2帧刀切般整齐的烧焦空地与无脸执行体，耳机传出无Fiat回车键的古闪喉音，删片瞬间床头噗噗骤亮幽蓝竖瞳切黑。",
    }),
]


def shot_from_ep1(s):
    return {
        "no": s["no"],
        "shot": s["shot"],
        "move": s["move"],
        "action": s["action"],
        "duration": s["duration"],
    }


def build_ep1(prod):
    shots = prod["ep1Shots"]
    scenes = []
    for start, end, meta in EP1_SCENE_GROUPS:
        grp = [s for s in shots if start <= int(s["no"].split("-")[1]) <= end]
        sc = dict(meta)
        sc["shots"] = [shot_from_ep1(s) for s in grp]
        sc["duration"] = sum(x["duration"] for x in sc["shots"])
        scenes.append(sc)
    total = sum(x["duration"] for x in scenes)
    return {
        "ep": 1,
        "title": "平常的一天",
        "total": total,
        "target": total,
        "note": "第 1 集 5 场 15 镜完整精修版（8分30秒）：黄金前 15 秒高定换装掉帧破功 + 三大省句整活名场面 + 结尾三连视听暴击强钩。",
        "scenes": scenes,
    }


def normalize(entry):
    """统一分片字段：每场补齐 shots，场时长按镜头合计校正。"""
    out = dict(entry)
    scenes = []
    for sc in out.get("scenes", []):
        s = dict(sc)
        shots = s.get("shots") or []
        s["shots"] = shots
        if shots:
            s["duration"] = sum(int(x.get("duration") or 0) for x in shots)
        scenes.append(s)
    out["scenes"] = scenes
    out["total"] = sum(int(x["duration"]) for x in scenes)
    out["target"] = out["total"]
    return out


def main():
    prod = json.loads((CANON / "production.json").read_text(encoding="utf-8"))

    episodes = []
    episodes.append(build_ep1(prod))
    episodes.append(normalize({
        "ep": 2, "title": "突然的乌云",
        "note": prod["ep2Note"], "scenes": prod["ep2Scenes"],
    }))
    episodes.append(normalize({
        "ep": 3, "title": "第二个声部",
        "note": prod["ep3Note"], "scenes": prod["ep3Scenes"],
    }))

    for fname in ("s04_08.json", "s09_16.json", "s17_24.json"):
        path = PARTS / fname
        if not path.exists():
            print(f"[FATAL] 缺少分段：{path}")
            return 1
        for e in json.loads(path.read_text(encoding="utf-8")):
            episodes.append(normalize(e))

    episodes.sort(key=lambda e: e["ep"])

    # 覆盖性检查：必须恰好 24 集，集号连续
    nos = [e["ep"] for e in episodes]
    if nos != list(range(1, 25)):
        print(f"[FATAL] 集号不连续或缺失：{nos}")
        return 1

    OUT.write_text(json.dumps({"seasonScript": episodes}, ensure_ascii=False, indent=2),
                   encoding="utf-8")

    total_shots = sum(len(s["shots"]) for e in episodes for s in e["scenes"])
    total_sec = sum(len(e["scenes"]) for e in episodes)
    print(f"装配完成：{OUT.relative_to(ROOT)}")
    print(f"  24 集｜{total_sec} 场｜{total_shots} 镜｜"
          f"全季 {sum(e['total'] for e in episodes)}″")
    for e in episodes:
        print(f"  第 {e['ep']:2d} 集《{e['title']}》 {e['total']:4d}″｜"
              f"{len(e['scenes'])} 场｜"
              f"{sum(len(s['shots']) for s in e['scenes'])} 镜")
    return 0


if __name__ == "__main__":
    sys.exit(main())
