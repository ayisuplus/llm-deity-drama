#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""创作中枢网页的渲染体检：双视口截图 + lint + 结构指纹。

产出 _shots/report.json（沿用既有 schema），并给出分级 findings。

检查项：
  1. 桌面 1440×900 与移动 390×844 双视口渲染，页面加载无控制台错误
  2. 无横向溢出（移动端尤其）
  3. 无资源加载失败
  4. 运行时渲染检查：每个 [data-render] 挂载点都渲染出了非空内容
  5. DOM 结构指纹（section/h1/h2/img/links 等）

用法：
  E:/Python/python.exe tools/shot.py
退出码：0 = 无 blocker/error，1 = 有 error
"""

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HTML = ROOT / "大模型神明-创作中枢.html"
OUTDIR = ROOT / "_shots"

VIEWPORTS = [
    ("desktop", {"width": 1440, "height": 900}),
    ("mobile", {"width": 390, "height": 844}),
]

# 找不到时按此顺序找浏览器
CHROME_CANDIDATES = [
    Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright" / "chromium-1217" / "chrome-win64" / "chrome.exe",
    Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright" / "chromium_headless_shell-1217" / "chrome-headless-shell-win64" / "chrome-headless-shell.exe",
    Path("C:/Program Files/Google/Chrome/Application/chrome.exe"),
]

COLLECT_SCRIPT = """() => {
  const q = (s) => document.querySelectorAll(s).length;
  const el = document.querySelector('h1');
  const empties = [];
  document.querySelectorAll('[data-render]').forEach((n) => {
    if (!n.innerHTML.trim()) empties.push(n.getAttribute('data-render'));
  });
  const over = [];
  const vw = document.documentElement.clientWidth;
  document.querySelectorAll('body *').forEach((n) => {
    const r = n.getBoundingClientRect();
    if (r.width > 0 && r.right > vw + 2) {
      over.push((n.tagName + (n.className ? '.' + String(n.className).split(' ')[0] : ''))
        + ' right=' + Math.round(r.right));
    }
  });
  return {
    title: document.title,
    firstH1: el ? el.textContent.trim() : null,
    viewport: {w: window.innerWidth, h: window.innerHeight},
    fullpage: {w: document.documentElement.scrollWidth, h: document.documentElement.scrollHeight},
    counts: {
      section: q('section.view'), h1: q('h1'), h2: q('h2'), img: q('img'),
      canvas: q('canvas'), svg: q('svg'), links: q('a'), buttons: q('button')
    },
    emptyMounts: empties,
    overflow: over.slice(0, 12),
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth
  };
}"""


def main():
    if not HTML.exists():
        print(f"[FATAL] 找不到网页：{HTML}")
        return 1

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[FATAL] 未安装 playwright。"
              "请用 E:/Python/python.exe 运行（该解释器带 playwright 1.59）。")
        return 1

    OUTDIR.mkdir(exist_ok=True)
    url = HTML.resolve().as_uri()
    started = time.time()
    report = {
        "src": str(HTML),
        "url": url,
        "outdir": str(OUTDIR),
        "include": ["lint", "screenshots", "structure"],
        "shots": {},
    }
    findings = []

    def add(level, msg, detail=""):
        findings.append({"level": level, "message": msg, "detail": detail})

    with sync_playwright() as p:
        exe = None
        degraded = None
        try:
            browser = p.chromium.launch(headless=True)
            report["engine"] = "playwright"
        except Exception as e:  # pragma: no cover
            degraded = str(e)
            for cand in CHROME_CANDIDATES:
                if cand.exists():
                    exe = str(cand)
                    break
            if not exe:
                print(f"[FATAL] 找不到可用浏览器：{degraded}")
                return 1
            browser = p.chromium.launch(headless=True, executable_path=exe)
            report["engine"] = "playwright_explicit"

        report["chromiumExec"] = exe or "playwright-bundled"
        if degraded:
            report["engineDegraded"] = True
            report["engineDegradedReason"] = degraded

        for name, vp in VIEWPORTS:
            page = browser.new_page(viewport=vp, device_scale_factor=1,
                                    reduced_motion="reduce")
            console_errors, console_warnings, resource_errors = [], [], []
            page.on("console", lambda m: console_errors.append(m.text)
                    if m.type == "error" else console_warnings.append(m.text))
            page.on("pageerror", lambda e: console_errors.append(str(e)))
            page.on("requestfailed", lambda r: resource_errors.append(
                f"{r.url} :: {r.failure}"))
            page.goto(url, wait_until="load")
            page.wait_for_timeout(700)

            info = page.evaluate(COLLECT_SCRIPT)
            shot_path = OUTDIR / f"{HTML.stem}_{name}.jpg"
            page.screenshot(path=str(shot_path), full_page=True, type="jpeg",
                            quality=82)
            size = shot_path.stat().st_size

            overflow = []
            if info["scrollWidth"] > info["clientWidth"] + 2:
                overflow = info["overflow"]

            report["shots"][name] = {
                "screenshot": str(shot_path),
                "screenshotBytes": size,
                "truncated": False,
                "structure": {
                    "title": info["title"],
                    "firstH1": info["firstH1"],
                    "viewport": info["viewport"],
                    "fullpage": info["fullpage"],
                    "counts": info["counts"],
                },
                "consoleErrors": console_errors,
                "consoleWarnings": console_warnings,
                "horizontalOverflow": overflow,
                "resourceErrors": resource_errors,
                "emptyMounts": info["emptyMounts"],
                "reportSource": "playwright",
            }
            page.close()

        browser.close()

    # ---- 汇总 findings ----
    for name, shot in report["shots"].items():
        if shot["consoleErrors"]:
            add("error", f"{name} 视口有控制台错误",
                "\n".join(shot["consoleErrors"][:6]))
        if shot["resourceErrors"]:
            add("error", f"{name} 视口有资源加载失败",
                "\n".join(shot["resourceErrors"][:6]))
        if shot["horizontalOverflow"]:
            add("error", f"{name} 视口有横向溢出",
                "\n".join(shot["horizontalOverflow"][:6]))
        if shot["emptyMounts"]:
            add("error", f"{name} 视口有未渲染的挂载点",
                str(shot["emptyMounts"]))
        if shot["consoleWarnings"]:
            add("warning", f"{name} 视口有控制台警告",
                "\n".join(shot["consoleWarnings"][:6]))

    levels = {"blocker": 0, "error": 0, "warning": 0, "info": 0}
    for f in findings:
        levels[f["level"]] += 1

    report["schemaVersion"] = 2
    report["status"] = "pass" if not (levels["blocker"] or levels["error"]) else "fail"
    report["elapsedSec"] = round(time.time() - started, 2)
    report["input"] = {
        "original": str(HTML),
        "resolvedPath": str(HTML.resolve()),
        "baseUrl": url,
        "protocol": "file",
        "cwd": os.getcwd(),
        "mediaMode": {"reducedMotion": True},
    }
    report["artifacts"] = {
        "screenshots": [
            {
                "viewport": name,
                "path": shot["screenshot"],
                "size": shot["screenshotBytes"],
                "visualCoverage": {"complete": not shot["emptyMounts"],
                                   "reason": "" if not shot["emptyMounts"]
                                   else "存在未渲染挂载点"},
            }
            for name, shot in report["shots"].items()
        ]
    }
    report["summary"] = levels
    report["findings"] = findings
    report["prioritizedActions"] = [
        f["message"] for f in findings if f["level"] in ("blocker", "error")
    ]

    (OUTDIR / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"引擎：{report['engine']}（{report['chromiumExec']}）")
    for name, shot in report["shots"].items():
        s = shot["structure"]
        print(f"  {name} {s['viewport']['w']}×{s['viewport']['h']}"
              f"｜整页 {s['fullpage']['w']}×{s['fullpage']['h']}"
              f"｜section {s['counts']['section']}｜h2 {s['counts']['h2']}"
              f"｜截图 {shot['screenshotBytes'] // 1024}KB")
    print("-" * 60)
    if not findings:
        print("渲染体检通过，0 findings。")
    else:
        for f in findings:
            print(f"[{f['level'].upper()}] {f['message']}")
            if f["detail"]:
                for line in str(f["detail"]).splitlines():
                    print(f"          {line}")
        print("-" * 60)
        print(f"blocker {levels['blocker']}｜error {levels['error']}"
              f"｜warning {levels['warning']}｜info {levels['info']}")
    print(f"报告：{(OUTDIR / 'report.json')}")
    return 1 if (levels["blocker"] or levels["error"]) else 0


if __name__ == "__main__":
    sys.exit(main())
