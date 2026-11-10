#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 _canon/canon.json 内联回 HTML 的 canon 数据区。

canon 数据区是创作中枢网页的唯一事实源；分片合并后必须内联，页面才会显示最新数据。
本脚本只做一件事：把 <script id="canon" type="application/json"> 与 </script> 之间的内容
替换成 _canon/canon.json 的格式化 JSON（与网页内联格式完全一致：indent=2、不转义非 ASCII）。

用法：
    E:/Python/python.exe tools/inline_canon.py
退出码：0 = 已内联，1 = 失败
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HTML = ROOT / "大模型神明-创作中枢.html"
CANON = ROOT / "_canon" / "canon.json"

PAT = re.compile(r'(<script id="canon" type="application/json">)(.*?)(</script>)', re.S)


def main():
    if not HTML.exists():
        print(f"[FATAL] 找不到网页：{HTML}")
        return 1
    if not CANON.exists():
        print(f"[FATAL] 找不到合并产物：{CANON}（先运行 tools/build_canon.py）")
        return 1

    canon = json.loads(CANON.read_text(encoding="utf-8"))
    text = json.dumps(canon, ensure_ascii=False, indent=2)

    src = HTML.read_text(encoding="utf-8")
    m = PAT.search(src)
    if not m:
        print("[FATAL] 网页里找不到 <script id=\"canon\" type=\"application/json\"> 数据区")
        return 1

    new = src[:m.start(2)] + text + src[m.end(2):]
    HTML.write_text(new, encoding="utf-8")

    print(f"内联完成：{CANON.name} → {HTML.name}")
    print(f"  顶层键 {len(canon)} 个｜数据区 {len(text)} 字符")
    return 0


if __name__ == "__main__":
    sys.exit(main())
