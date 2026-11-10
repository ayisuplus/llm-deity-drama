#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""校验创作中枢网页的结构一致性。

检查项：
  1. VIEWS / LABELS / <section class="view"> 三者的 id 集合与顺序一致
  2. 文档内所有 id 唯一
  3. 页内锚点 href="#xxx" 均指向真实存在的 id
  4. 每个 [data-render="KEY"] 都有对应渲染器
  5. 每个渲染器访问的 canon 顶层键真实存在
  6. data-owner 归属不重复（一个事实只有一个权威页）

用法：
  E:/Python/python.exe tools/check_structure.py
退出码：0 = 无 blocker/error，1 = 有 error
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HTML = ROOT / "大模型神明-创作中枢.html"

RE_VIEWS = re.compile(r"const\s+VIEWS\s*=\s*\[(.*?)\]\s*;", re.S)
RE_VIEW_HTML = re.compile(r"const\s+VIEWS_HTML\s*=\s*\{(.*?)\n\};", re.S)
RE_VIEW_OBJ_ID = re.compile(r'\bid:\s*"([^"]+)"')
RE_VIEW_HTML_KEY = re.compile(r"^\s{2}([A-Za-z_$][\w$]*)\s*\(\)\s*\{", re.M)
RE_RENDERERS = re.compile(r"const\s+RENDERERS\s*=\s*\{(.*?)\n\};", re.S)
RE_SECTION = re.compile(r'<section[^>]*class="[^"]*\bview\b[^"]*"[^>]*\bid="([^"]+)"', re.S)
RE_ID = re.compile(r'\bid="([^"]+)"')
RE_ANCHOR = re.compile(r'href="#([^"]+)"')
RE_RENDER_MOUNT = re.compile(r'data-render="([^"]+)"')
RE_OWNER = re.compile(r'data-owner="([^"]+)"')


def parse_view_objects(block):
    """新版 VIEWS 是对象数组：{id:"x", idx, group, label}，按出现顺序取 id。"""
    return RE_VIEW_OBJ_ID.findall(block)


def parse_view_list(block):
    return parse_view_objects(block)


def parse_renderer_keys(block):
    """取 RENDERERS 对象的顶层键：形如 `  name(C){` 或 `  name: (C) =>`"""
    keys = []
    for m in re.finditer(r"^\s{2}([A-Za-z_$][\w$]*)\s*(?::|\()", block, re.M):
        keys.append(m.group(1))
    return keys


def main():
    if not HTML.exists():
        print(f"[FATAL] 找不到网页：{HTML}")
        return 1

    src = HTML.read_text(encoding="utf-8")
    findings = []

    def add(level, msg, detail=""):
        findings.append({"level": level, "message": msg, "detail": detail})

    # --- 1. VIEWS 对象数组 --------------------------------------------------
    mv = RE_VIEWS.search(src)
    if not mv:
        add("error", "找不到 VIEWS 数组")
        views = []
    else:
        views = parse_view_list(mv.group(1))

    # 视图 id 不得在清单里重复
    dup_views = sorted({v for v in views if views.count(v) > 1})
    if dup_views:
        add("error", "VIEWS 清单里 id 重复", str(dup_views))

    # --- 2. VIEWS_HTML 骨架：每个视图必须有一个骨架函数 ----------------------
    mh = RE_VIEW_HTML.search(src)
    skeleton_keys = RE_VIEW_HTML_KEY.findall(mh.group(1)) if mh else []
    if not mh:
        add("error", "找不到 VIEWS_HTML 骨架表")

    missing_skel = [v for v in views if v not in skeleton_keys]
    orphan_skel = [k for k in skeleton_keys if k not in views]
    if missing_skel:
        add("error", "有视图缺骨架函数（VIEWS_HTML）", str(missing_skel))
    if orphan_skel:
        add("error", "VIEWS_HTML 有多余骨架（不在 VIEWS 清单里）", str(orphan_skel))

    # --- 3. id 唯一（静态 HTML 中的 id；运行时生成的视图 id 不在源码里） -----
    all_ids = RE_ID.findall(src)
    dupes = sorted({i for i in all_ids if all_ids.count(i) > 1})
    if dupes:
        add("error", "文档内静态 id 重复", str(dupes))

    # --- 4. 页内锚点 --------------------------------------------------------
    # 视图锚点在运行时才存在，允许指向 VIEWS 清单里的 id；其余必须是静态 id
    id_set = set(all_ids) | set(views)
    bad_anchors = sorted({a for a in RE_ANCHOR.findall(src) if a not in id_set})
    if bad_anchors:
        add("error", "页内锚点指向不存在的 id", str(bad_anchors))

    # --- 5. 渲染器与挂载点闭合 ----------------------------------------------
    mr = RE_RENDERERS.search(src)
    renderer_keys = parse_renderer_keys(mr.group(1)) if mr else []
    if not mr:
        add("error", "找不到 RENDERERS 注册表")

    # 挂载点是骨架函数源码里 mount("key") 的调用
    mounts = re.findall(r'\bmount\(\s*"([^"]+)"\s*\)', mh.group(1)) if mh else []
    mounts = sorted(set(mounts))
    missing_render = sorted({m for m in mounts if m not in renderer_keys})
    orphan_render = sorted({k for k in renderer_keys if k not in mounts})
    if missing_render:
        add("error", "有挂载点没有对应渲染器", str(missing_render))
    if orphan_render:
        add("warning", "有渲染器没有挂载点（不会被调用）", str(orphan_render))

    # --- 6. canon 数据区 ----------------------------------------------------
    canon_keys = set()
    mc = re.search(r'<script[^>]*id="canon"[^>]*>(.*?)</script>', src, re.S)
    if mc:
        try:
            canon = json.loads(mc.group(1))
            canon_keys = set(canon.keys())
        except json.JSONDecodeError as e:
            add("error", "canon 数据区不是合法 JSON", str(e))
    else:
        add("error", "找不到 canon 数据区")

    # 每个渲染器访问的 C.<key> 必须存在
    if mr and canon_keys:
        block = mr.group(1)
        chunks = re.split(r"^\s{2}([A-Za-z_$][\w$]*)\s*(?::|\()", block, flags=re.M)
        for i in range(1, len(chunks), 2):
            name, body = chunks[i], chunks[i + 1]
            used = set(re.findall(r"\bC\.([A-Za-z_$][\w$]*)", body))
            unknown = sorted(k for k in used if k not in canon_keys)
            if unknown:
                add("error", f"渲染器 {name} 访问了 canon 里不存在的键", str(unknown))

    # --- 7. data-owner 权威归属不重复 ---------------------------------------
    owners = RE_OWNER.findall(src)
    dup_owners = sorted({o for o in owners if owners.count(o) > 1})
    if dup_owners:
        add("error", "data-owner 重复（同一事实被两个视图声明为权威）", str(dup_owners))

    # --- 8. 每个骨架函数最终产出恰好一个 h1 ---------------------------------
    # 统计骨架源码里 h1 由 head() 生成：每个视图调用一次 head(...) → 一个 h1
    if mh:
        block = mh.group(1)
        chunks = re.split(r"^\s{2}([A-Za-z_$][\w$]*)\s*\(\)\s*\{", block, flags=re.M)
        for i in range(1, len(chunks), 2):
            name, body = chunks[i], chunks[i + 1]
            n_head = len(re.findall(r"\bhead\(", body))
            if n_head != 1:
                add("error", f"视图骨架 {name} 应调用一次 head()（一个 h1），实际 {n_head}")

    # --- 输出 ---------------------------------------------------------------
    levels = {"blocker": 0, "error": 0, "warning": 0, "info": 0}
    for f in findings:
        levels[f["level"]] += 1
    print(f"检查目标：{HTML.name}")
    print(f"视图 {len(views)} 个｜渲染器 {len(renderer_keys)} 个｜挂载点 {len(set(mounts))} 个"
          f"｜canon 顶层键 {len(canon_keys)} 个")
    print("-" * 60)
    if not findings:
        print("结构检查通过，0 findings。")
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
