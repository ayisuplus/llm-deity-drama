"""补全 OpenCut CLI 目录：把 store/cli 实际接受的每个 action 与已迁移意图写进 cli_help.json。

背景：`opencut project edit.apply` 之外，`document.save`、`story.*`、`project.settings`
等早已能调用，但目录（cli_help.json）里没有条目，agent 只能读 Rust 源码才能发现。
本脚本只补缺失条目，不改已有条目。用 --check 只报告缺口不写盘。
"""

import json
import sys
from pathlib import Path

HELP = next(
    p
    for p in (
        Path("/mnt/e/projects/内容创作/OpenCut/rust/crates/creative/src/workbench/cli_help.json"),
        Path("E:/projects/内容创作/OpenCut/rust/crates/creative/src/workbench/cli_help.json"),
    )
    if p.exists()
)

# 新增命令条目：键去掉 "project " 前缀是 action 名。
ADDED = {
    "asset.reference.plan": (
        "只读规划资产引用到拍摄素材的挂载关系，返回来源修订；不产生修订",
        {"revision": "r3-..."},
    ),
    "audio.analysis.request": (
        "为已有音频入队分析任务，需要 expected_revision 与唯一 operation_id；返回 job_id，不产生修订",
        {"expected_revision": "r3-...", "operation_id": "audio-1", "media_id": "source-1"},
    ),
    "backup.list": ("列出本工程的持久化备份", {}),
    "backup.request": (
        "入队一次工程备份，需要 expected_revision 与唯一 operation_id；返回 job_id，不产生修订",
        {"expected_revision": "r3-...", "operation_id": "backup-1"},
    ),
    "catalog": (
        "读取幕／镜头／文稿／资产目录（剧情-分镜的共同身份来源），可指定 revision",
        {"revision": "r3-..."},
    ),
    "create": (
        "在已登记 root_id 下新建 local- 空工程；写入需要唯一 operation_id",
        {"root_id": "sandbox", "width": 1920, "height": 1080, "fps": {"numerator": 30, "denominator": 1}, "name": "新项目", "operation_id": "create-1"},
    ),
    "import-copy": (
        "把既有工程按导入方式复制成新的 local- 工程，参数与 create 相同",
        {"root_id": "sandbox", "name": "副本", "operation_id": "copy-1"},
    ),
    "document.save": (
        "保存或新建一份文稿；必须带读取时的 base_document 做 CAS。正文变化会把引用该文稿的节点标为 needs_review，不自动改时间线",
        {
            "expected_revision": "r3-...",
            "operation_id": "doc-1",
            "document_id": "ep1-script",
            "base_document": {"id": "ep1-script", "title": "", "content": {"kind": "text", "body": ""}},
            "document": {
                "id": "ep1-script",
                "title": "第一集剧本",
                "category": "script",
                "source": "canon",
                "content": {"kind": "text", "body": "正文"},
            },
        },
    ),
    "draft.archive": (
        "归档客户端草稿队列（drafts），供离线恢复；不产生可编辑修订",
        {"drafts": []},
    ),
    "handoff.export": (
        "为冻结修订导出交接包，并校验源媒体；不修改工程",
        {"revision": "r3-...", "path": "E:/作品/交接"},
    ),
    "handoff.validate": (
        "检查冻结版本是否具备审片／交接条件",
        {"revision": "r3-..."},
    ),
    "preview.validate": (
        "只读校验冻结修订能否出预览，返回与渲染一致的规划",
        {"revision": "r3-..."},
    ),
    "history.compare": (
        "比较 revision_a 与 revision_b（缺省为当前修订），可用 clip_id/node_id 限定到单个对象",
        {"revision_a": "r2-...", "revision_b": "r3-..."},
    ),
    "history.compare-draft": (
        "用未提交的 snapshot 与 revision_a 比较；expected_revision 必须等于当前修订，否则 409",
        {"expected_revision": "r3-...", "revision_a": "r2-...", "snapshot": {}},
    ),
    "history.object": (
        "单个片段或节点的变更历史，跳过与该对象无关的保存",
        {"clip_id": "clip-1", "node_id": "node-1"},
    ),
    "history.prepare": (
        "准备局部恢复，返回 prepared_revision 与 prepared_hash；不产生修订",
        {"revision": "r2-...", "selections": []},
    ),
    "history.restore": (
        "携带 prepared_revision 与 prepared_hash 应用局部恢复；准备后工程变化则 409",
        {"expected_revision": "r3-...", "operation_id": "restore-1", "prepared_revision": "r3-...", "prepared_hash": "hash", "revision": "r2-...", "selections": []},
    ),
    "import.get": ("读取媒体导入请求状态", {"upload_id": "upload-1"}),
    "import.request": (
        "登记一次媒体导入请求，返回 job_id；接受已暂存 upload_id，不接受任意磁盘路径",
        {"expected_revision": "r3-...", "operation_id": "import-1", "upload_id": "upload-1"},
    ),
    "jobs.cancel": (
        "取消任务，返回 changed:false 回执，不产生修订",
        {"job_id": "job-1", "expected_revision": "r3-...", "operation_id": "cancel-1"},
    ),
    "jobs.resume": (
        "继续被中断的任务；Web 会唤醒同一 worker，CLI 仍需 jobs.run",
        {"job_id": "job-1", "expected_revision": "r3-...", "operation_id": "resume-1"},
    ),
    "jobs.retry": (
        "重试失败或已取消的任务，沿用原身份并重新校验冻结来源",
        {"job_id": "job-1", "expected_revision": "r3-...", "operation_id": "retry-1"},
    ),
    "media.import": (
        "把已暂存 upload_id 登记进素材索引；不能登记任意磁盘根",
        {"upload_id": "upload-1", "media": {"name": "镜头.mp4"}},
    ),
    "media.remove": (
        "删除未使用素材索引（不改归档文件）。移除已被引用的素材用 edit.apply 的 media.remove 意图",
        {"media_id": "source-1"},
    ),
    "media.resolve": (
        "解析修订内素材的磁盘路径与元数据，只读",
        {"revision": "r3-...", "media_id": "source-1"},
    ),
    "name": ("给修订起名，便于历史阅读；不改工程内容", {"revision": "r3-...", "name": "第一集定稿"}),
    "proxy.list": ("列出各视频的原始／代理状态与 Rust 校验后的 selected", {}),
    "proxy.request": (
        "为某素材请求视频代理，返回 job_id；代理只用于时间线预览，音频与正式输出仍用原片",
        {"expected_revision": "r3-...", "operation_id": "proxy-1", "media_id": "source-1"},
    ),
    "restore": ("把工程快照恢复到指定修订（保留版本名表）", {"expected_revision": "r3-...", "operation_id": "restore-1", "revision": "r2-..."}),
    "save": (
        "用完整 project 快照覆盖工程，供 Web 宿主兼容使用；局部修改请走 edit.apply",
        {"expected_revision": "r3-...", "operation_id": "save-1", "project": {}},
    ),
}

RECIPES = {
    "story": {
        "note": "目录编辑同样走 edit.apply 的 edits 批次：幕与镜头是身份，编号与 label 只供显示；不因建镜改时间线",
        "edits": [
            {"type": "story.act.add", "id": "act-id", "number": 1, "title": "第一场"},
            {"type": "story.act.update", "id": "act-id", "patch": {"title": "改后的场名"}},
            {"type": "story.shot.add", "id": "shot-id", "act_id": "act-id", "number": 1, "title": "开场"},
            {"type": "story.shot.update", "id": "shot-id", "patch": {"notes": "景别／运镜／时长／资产", "document_ids": ["ep1-script"]}},
        ],
    },
    "settings": {
        "note": "工程设置只支持局部 patch；不支持通过 CLI 直接写入 index，注释以外的键会被拒绝",
        "edits": [
            {"type": "project.settings", "patch": {"fps": {"numerator": 30, "denominator": 1}}},
            {"type": "project.settings", "patch": {"canvasSize": {"width": 1920, "height": 1080}}},
        ],
    },
    "document": {
        "note": "文稿内容改动不自动改时间线；引用它的文字卡会被标记 needs_review",
        "action": "document.save",
        "expected_revision": "r3-...",
        "operation_id": "doc-1",
        "document_id": "ep1-script",
        "base_document": {"id": "ep1-script", "content": {"kind": "text", "body": ""}},
        "document": {"id": "ep1-script", "title": "第一集剧本", "category": "script", "content": {"kind": "text", "body": "正文"}},
    },
}


def main() -> int:
    check = "--check" in sys.argv
    catalog = json.loads(HELP.read_text(encoding="utf-8"))
    commands = catalog["commands"]
    missing = []
    for action, (description, example) in ADDED.items():
        key = f"project {action}"
        if key in commands:
            continue
        missing.append(key)
        commands[key] = {"description": description, "example": example}
    missing_recipes = [k for k in RECIPES if k not in catalog["recipes"]]
    for k in missing_recipes:
        catalog["recipes"][k] = RECIPES[k]
    print(f"commands+{len(missing)} recipes+{len(missing_recipes)}")
    if not check and (missing or missing_recipes):
        HELP.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
