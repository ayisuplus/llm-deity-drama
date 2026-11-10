"""把 canon 里的第一集场／镜目录生成为 OpenCut 原生工程需要的 story 编辑批次。

数据源（只读，不改）：
  项目仪表盘/_canon/season.json   → 第一集 5 场、每场镜头顺序与时长
  项目仪表盘/_canon/production.json → ep1Shots 的景别／运镜／动作／首尾帧／声音／引用资产

输出：
  work/opencut/02-story.json   准备提交给 opencut project edit.prepare/apply 的请求体
  work/opencut/02-story.md     同一批东西的人读视图，便于逐镜核对
"""

import json
import re
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CANON = ROOT / "项目仪表盘" / "_canon"
OUT = Path(__file__).resolve().parent

REVISION = "R1"  # 由调用方替换成实际 expected_revision
NS = uuid.UUID("6f9619ff-8b86-d011-b42d-00c04fc964ff")  # 固定命名空间，重跑得到同一批 ID


def stable_id(kind: str, key: str) -> str:
    return str(uuid.uuid5(NS, f"damoshen-ep1:{kind}:{key}"))


def shot_title(action: str, shot: str) -> str:
    """优先用动作里的【…】标记当标题，没有就退回景别。"""
    m = re.search(r"【([^】]{2,20})】", action)
    return m.group(1) if m else shot


def build() -> dict:
    season = json.loads((CANON / "season.json").read_text(encoding="utf-8"))["seasonScript"]
    prod = json.loads((CANON / "production.json").read_text(encoding="utf-8"))
    ep1 = season[0]
    by_no = {s["no"]: s for s in prod["ep1Shots"]}

    edits = []
    doc = ["# 第一集《平常的一天》· 逐场逐镜（OpenCut 目录批次）", ""]
    for scene in ep1["scenes"]:
        act_id = stable_id("act", str(scene["no"]))
        edits.append({
            "type": "story.act.add",
            "id": act_id,
            "number": int(scene["no"]),
            "title": scene["name"],
        })
        doc.append(f"## 场 {scene['no']} · {scene['name']}（{scene.get('duration')}″）")
        doc.append("")
        doc.append(scene.get("desc", ""))
        doc.append("")
        for idx, s in enumerate(scene["shots"], start=1):
            p = by_no[s["no"]]
            notes = "\n".join([
                f"场：{scene['name']}",
                f"集内镜号：{s['no']}",
                f"景别：{p['shot']}",
                f"运镜：{p['move']}",
                f"时长：{p['duration']}″",
                f"引用资产：{' / '.join(p['assets'])}",
                f"首帧：{p['firstFrame']}",
                f"尾帧：{p['lastFrame']}",
                f"声音：{p['sound']}",
            ])
            edits.append({
                "type": "story.shot.add",
                "id": stable_id("shot", str(s["no"])),
                "act_id": act_id,
                "number": idx,
                "title": shot_title(p["action"], p["shot"]),
            })
            edits.append({
                "type": "story.shot.update",
                "id": stable_id("shot", str(s["no"])),
                "patch": {"notes": notes},
            })
            doc.append(f"### {s['no']}（{p['shot']}／{p['move']}／{p['duration']}″）")
            doc.append("")
            doc.append(p["action"])
            doc.append("")

    (OUT / "02-story.md").write_text("\n".join(doc), encoding="utf-8")
    return {
        "expected_revision": REVISION,
        "operation_id": str(uuid.uuid5(NS, "damoshen-ep1:op:02-story")),
        "edits": edits,
    }


if __name__ == "__main__":
    batch = build()
    (OUT / "02-story.json").write_text(
        json.dumps(batch, ensure_ascii=False, indent=1), encoding="utf-8")
    adds = sum(1 for e in batch["edits"] if e["type"].endswith(".add"))
    notes = sum(1 for e in batch["edits"] if e.get("patch", {}).get("notes"))
    print(f"edits={len(batch['edits'])} adds={adds} notes={notes} op={batch['operation_id']}")
