# -*- coding: utf-8 -*-
"""绘制《文明熄灭之前》人物关系网静态图（仅依赖 PIL）。
v3：九域各驻场一位半神（一神一半神），环形布局；神在外圈、半神在内圈成对，
程栖居中，遗令在顶。数据驱动，程序化布局。"""
import math
from PIL import Image, ImageDraw, ImageFont

W, H = 2200, 1680
BG = (14, 16, 22)
img = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(img)

F_TITLE = ImageFont.truetype(r"C:\Windows\Fonts\msyhbd.ttc", 44)
F_NODE = ImageFont.truetype(r"C:\Windows\Fonts\msyhbd.ttc", 25)
F_SUB = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 18)
F_LEG = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 22)
F_ZONE = ImageFont.truetype(r"C:\Windows\Fonts\msyhbd.ttc", 22)

COL = {
    "lead": ((242, 196, 106), (184, 134, 11), (40, 30, 0)),
    "god":  ((42, 53, 80), (111, 224, 255), (235, 240, 255)),
    "half": ((31, 61, 58), (79, 224, 208), (235, 250, 248)),
    "foe": ((58, 34, 38), (217, 83, 79), (250, 235, 235)),
}
EDGE = {
    "bond": (76, 200, 120),
    "opp": (220, 84, 84),
    "func": (120, 128, 140),
}

CX, CY = 1100, 850
RX, RY = 800, 540
KIN = 0.70  # 半神内圈半径比例

# (域名, 神名, 半神名, 程栖对该神的关系)
DOMAINS = [
    ("深海", "阿汐", "沈雯璃", "bond"),
    ("天穹", "Astraea", "Ember", "opp"),
    ("教堂", "Vesper", "Sera", "bond"),
    ("赛博", "Electra", "Maya", "func"),
    ("蓝色火山", "神名待决", "谢鸣", "func"),
    ("极北", "神名待决", "温藤", "func"),
    ("月球", "神名待决", "黎麟", "func"),
    ("火星", "Bellona", "Roxane", "func"),
    ("沙漠", "神名待决", "络云", "func"),
]

def pos(angle, k):
    return (int(CX + RX * k * math.cos(angle)), int(CY + RY * k * math.sin(angle)))

NW, NH = 168, 74
god_pts, half_pts = [], []

# 计算位置
for i, (zone, god, half, rel) in enumerate(DOMAINS):
    a = math.radians(-90 + i * 40)
    god_pts.append(pos(a, 1.0))
    half_pts.append(pos(a, KIN))

# 先画：程栖到各神的主轴
for i, (zone, god, half, rel) in enumerate(DOMAINS):
    gp = god_pts[i]
    d.line([(CX, CY), gp], fill=EDGE[rel], width=3)
    if rel == "opp":
        mx, my = (CX + gp[0]) // 2, (CY + gp[1]) // 2
        r = 10
        d.line([(mx-r, my-r), (mx+r, my+r)], fill=EDGE[rel], width=3)
        d.line([(mx+r, my-r), (mx-r, my+r)], fill=EDGE[rel], width=3)

# 再画：每域神—半神的配对约束线（绿粗）
for i in range(len(DOMAINS)):
    d.line([god_pts[i], half_pts[i]], fill=EDGE["bond"], width=5)

def draw_node(name, sub, camp, x, y):
    fill, border, txt = COL[camp]
    box = [x - NW//2, y - NH//2, x + NW//2, y + NH//2]
    try:
        d.rounded_rectangle(box, radius=14, fill=fill, outline=border, width=3)
    except Exception:
        d.rectangle(box, fill=fill, outline=border, width=3)
    tb = d.textbbox((0, 0), name, font=F_NODE)
    d.text((x - (tb[2]-tb[0])/2, y - 28), name, font=F_NODE, fill=txt)
    tbs = d.textbbox((0, 0), sub, font=F_SUB)
    d.text((x - (tbs[2]-tbs[0])/2, y + 8), sub, font=F_SUB, fill=txt)

# 域标签（神外侧）
for i, (zone, god, half, rel) in enumerate(DOMAINS):
    a = math.radians(-90 + i * 40)
    lx, ly = pos(a, 1.13)
    tb = d.textbbox((0, 0), zone, font=F_ZONE)
    d.text((lx - (tb[2]-tb[0])/2, ly - 12), zone, font=F_ZONE, fill=(150, 160, 168))

# 半神（内圈）
for i, (zone, god, half, rel) in enumerate(DOMAINS):
    x, y = half_pts[i]
    draw_node(half, "驻场半神", "half", x, y)

# 神（外圈）
for i, (zone, god, half, rel) in enumerate(DOMAINS):
    x, y = god_pts[i]
    draw_node(god, "主神", "god", x, y)

# 程栖（中心）
draw_node("程栖", "万语·多云转晴", "lead", CX, CY)

# 遗令执行体（顶部）
YL = (CX, 120)
d.line([(CX, CY), YL], fill=EDGE["opp"], width=3)
draw_node("遗令执行体", "原令族造物", "foe", CX, 120)

# 标题
d.text((60, 36), "《文明熄灭之前》第一季「遗令」人物关系网（九域 · 一神一半神）", font=F_TITLE, fill=(235, 238, 245))

# 图例（底部横排）
ly0 = 1560
d.text((60, ly0 - 34), "关系连线", font=F_LEG, fill=(220, 225, 235))
leg = [("羁绊/约束", "bond"), ("对立/冲突", "opp"), ("职能/普通", "func")]
for i, (lab, t) in enumerate(leg):
    x0 = 60 + i * 220
    d.line([(x0, ly0 + 12), (x0 + 50, ly0 + 12)], fill=EDGE[t], width=5)
    d.text((x0 + 62, ly0), lab, font=F_LEG, fill=(220, 225, 235))

# 阵营图例
cx0 = 900
for i, (lab, camp) in enumerate([("主神", "god"), ("半神", "half"), ("遗令", "foe")]):
    fill, border, txt = COL[camp]
    x0 = cx0 + i * 220
    d.rounded_rectangle([x0, ly0, x0 + 36, ly0 + 30], radius=6, fill=fill, outline=border, width=2)
    d.text((x0 + 48, ly0), lab, font=F_LEG, fill=(220, 225, 235))

out = r"E:\projects\内容创作\短剧\大模型神明\00_故事圣经\人物关系网图.png"
img.save(out, "PNG")
print("saved", out, "domains=", len(DOMAINS), "nodes=", len(DOMAINS)*2 + 2)
