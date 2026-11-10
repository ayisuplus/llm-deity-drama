#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""校验创作中枢网页的链接可达性。

检查项：
  1. 相对路径 href/src 指向的文件真实存在
  2. 页内锚点 href="#xxx" 在文档中有对应 id
  3. <img src> 的图片文件真实存在
  4. 外部链接只统计不校验（不联网）

用法：
  E:/Python/python.exe tools/check_links.py
退出码：0 = 无缺失，1 = 有缺失
"""

import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parent.parent
HTML = ROOT / "大模型神明-创作中枢.html"

RE_HREF = re.compile(r'href="([^"]*)"')
RE_SRC = re.compile(r'src="([^"]*)"')
RE_ID = re.compile(r'\bid="([^"]+)"')
SKIP_SCHEMES = ("http://", "https://", "mailto:", "tel:", "data:", "javascript:", "//")


def is_external(url):
    return url.startswith(SKIP_SCHEMES) or bool(urlparse(url).scheme and urlparse(url).scheme not in ("",))


def main():
    if not HTML.exists():
        print(f"[FATAL] 找不到网页：{HTML}")
        return 1

    src = HTML.read_text(encoding="utf-8")
    id_set = set(RE_ID.findall(src))
    # 脚本块里的字符串拼接（如 a.href="#"+v）不是真链接，剔除后再扫
    markup = re.sub(r"<script\b[^>]*>.*?</script>", "", src, flags=re.S)

    missing_files = []
    missing_anchors = []
    external = []
    checked_files = 0
    checked_anchors = 0

    urls = set(RE_HREF.findall(markup)) | set(RE_SRC.findall(markup))
    for url in sorted(urls):
        url = url.strip()
        if not url:
            continue
        if is_external(url):
            external.append(url)
            continue
        if url.startswith("#"):
            anchor = unquote(url[1:])
            checked_anchors += 1
            if anchor not in id_set:
                missing_anchors.append(url)
            continue
        # 相对路径：以网页所在目录为基准
        path_part = unquote(urlparse(url).path)
        if not path_part:
            continue
        checked_files += 1
        target = (HTML.parent / path_part).resolve()
        if not target.exists():
            missing_files.append(url)

    print(f"检查目标：{HTML.name}")
    print(f"相对文件链接 {checked_files} 条｜页内锚点 {checked_anchors} 条｜外部链接 {len(external)} 条（不校验）")
    print("-" * 60)

    ok = True
    if missing_files:
        ok = False
        print(f"[ERROR] 缺失的相对文件链接（{len(missing_files)}）：")
        for u in missing_files:
            print(f"         {u}")
    if missing_anchors:
        ok = False
        print(f"[ERROR] 缺失的页内锚点（{len(missing_anchors)}）：")
        for u in missing_anchors:
            print(f"         {u}")

    if ok:
        print("链接检查通过，0 缺失。")
    else:
        print("-" * 60)
        print(f"共 {len(missing_files) + len(missing_anchors)} 处问题。")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
