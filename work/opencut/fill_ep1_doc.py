"""把第一集剧本正文写进 OpenCut 文稿，并把 15 个镜头绑定到该文稿。

前置：work/opencut/build_ep1.py 已跑过（目录批次已 apply），且 05-read.json 是当前修订的读取结果。
用法：python3 work/opencut/fill_ep1_doc.py
输出：work/opencut/06-doc.json（document.save 请求）、work/opencut/07-bind.json（edit 批次）
"""

import json
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CANON = ROOT / "项目仪表盘" / "_canon"
NS = uuid.UUID("6f9619ff-8b86-d011-b42d-00c04fc964ff")
DOC_ID = "ep1-script"


def stable_id(kind: str, key: str) -> str:
    return str(uuid.uuid5(NS, f"damoshen-ep1:{kind}:{key}"))


def body() -> str:
    season = json.loads((CANON / "season.json").read_text(encoding="utf-8"))["seasonScript"]
    prod = json.loads((CANON / "production.json").read_text(encoding="utf-8"))
    ep1 = season[0]
    by_no = {s["no"]: s for s in prod["ep1Shots"]}

    lines = [f"# 第一集 · {ep1['title']}", "", f"> 时长 {ep1['total']}″｜{ep1['note']}", ""]
    for scene in ep1["scenes"]:
        lines += [f"## 场 {scene['no']}　{scene['name']}　（{scene.get('duration')}″）", ""]
        if scene.get("desc"):
            lines += [scene["desc"], ""]
        for s in scene["shots"]:
            p = by_no[s["no"]]
            lines += [f"**【{s['no']}】{p['shot']}／{p['move']}／{p['duration']}″**", "", p["action"], ""]
    return "\n".join(lines)


def main() -> None:
    read = json.loads((HERE / "05-read.json").read_text(encoding="utf-8"))["value"]
    rev = read["revision"]
    base = read["snapshot"]["documents"][DOC_ID]

    doc = {
        "expected_revision": rev,
        "operation_id": str(uuid.uuid5(NS, "damoshen-ep1:op:06-doc")),
        "document_id": DOC_ID,
        "base_document": base,
        "document": {
            "id": DOC_ID,
            "title": "第一集《平常的一天》剧本",
            "category": "script",
            "source": "damoshen-canon",
            "content": {"kind": "text", "body": body()},
        },
    }
    (HERE / "06-doc.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")

    shots = json.loads((HERE / "02-story.json").read_text(encoding="utf-8"))["edits"]
    bind = {
        "expected_revision": "R3",  # 由调用方填入 document.save 之后的修订
        "operation_id": str(uuid.uuid5(NS, "damoshen-ep1:op:07-bind")),
        "edits": [
            {"type": "story.shot.update", "id": e["id"], "patch": {"document_ids": [DOC_ID]}}
            for e in shots
            if e["type"] == "story.shot.add"
        ],
    }
    (HERE / "07-bind.json").write_text(json.dumps(bind, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"doc body={len(doc['document']['content']['body'])}字 base_rev={rev} bind_shots={len(bind['edits'])}")


if __name__ == "__main__":
    main()
