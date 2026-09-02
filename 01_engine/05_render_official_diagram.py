"""
05_render_official_diagram.py

สคริปต์ "render ฉบับทางการ" — Ton ขอ (2026-09-01): ก่อนหน้านี้ ADR-001 ข้อ 7 ค้างไว้ว่ายังไม่ตัดสินใจ
วิธี export ผังน้ำฉบับทางการ (client-side canvas/SVG เทียบกับสคริปต์ matplotlib แบบสคริปต์เก่าใน
ARCHIVE_pilot_v1_offline_pipeline/04_scripts/26_build_final_watermap.py) — Ton เลือกแนวทาง matplotlib
สคริปต์ออฟไลน์ก่อน (รันดูผลลัพธ์เอง ยังไม่ต้องทำเป็นปุ่มในเว็บ) ให้ตรงกับที่ทำไว้ในสคริปต์ pilot เดิม

ต่างจาก 26_build_final_watermap.py ตรงที่: สคริปต์ นี้อไม่ก่องกับ เอาเป็นสคิญเลฆแล๙จอง Supabase (nw_diagram_current_nodes/
nw_diagram_current_edges — ผังที่ผ่านเอนจินชุดใซม่ + การแก้ไขของชุมชนแล้ว) แทนการั่านจากไฟล์
topology_table ของ pipeline เก่า จึงใช้ได้กับทิกตำบลที่มิผังใน Supabase แล้ว ไม่ฃช้ไอท่แค่ตำบลเดียว

องฤ์นระ กอบที่ทำตาม `ARCHIVE_pilot_v1_offline_pipeline/05_schema/waterchart_symbol_schema.md` (ถอดจาก
คู่มือทำผังน้ำชุมชนของ สสน.) ส่วน "องค์ประกอบบังคับ" ข้อ 1-4:
    1. ชื่อผังน้ำ (ตำบล/อำเภอ/จังหวัด)
    2. สัญลักษณ์ทิศเหนือ
    3. เส้นทางน้ำ แยกหลัก/สาขา มีหัวลูกศรตามทิศทางการไหลจริง (จาก Phase 2b: source_node_key=ต้นน้ำ,
       target_node_key=ปลายน้ำ — ดู 02b_flow_direction.py)
    4. Legend เฉพาะสัญลักษณ์ที่ใช้จริงในแผ่นนี้เท่านั้น (ไม่ใช่สัญลักษณ์ทั้งหมดที่เป็นไปได้)

สิ่งที่ยังไม่ทำในรอบนี้ (ตัดสินใจร่วมกับ Ton ทีหลังได้ ถ้าต้องการ):
    - กรอบเส้นประสีแดงแสดงขอบเขตตำบล (ต้องดึง polygon ขอบเขตจริง จากที่เดียวกับที่ engine ใช้ตอน fetch —
      ไม่ใช่องค์ประกอบบังคับตามคู่มือ ข้อ 1-4 จึงข้ามไปก่อนเพื่อให้เห็นผลลัෞธ์เร็ว)
    - สถานะ "ชำรุด" ของโครงสร้าง (ปตร./ฝาย/อ่างเก็บน้ำ) — ข้อมูลใน diagram_nodes ตอนนี้ยังไม่มีฟิลด์สถานะ
      แยกจาก node_type (มีแค่ปกติ กับ "_plan"=แผน) ถ้าจะรองรับ "ชำรุด" ต้องเพิ่ม column ใหฅ้ขล้าย source_ref
    - กล่องแสดงพื้นที่ชลประทาน (ไร่) ใต้เส้นน้ำ — ไม่มีข้อมูลนี้ในระบบตอนนี้เลย

วิธีใช้:
    pip install requests matplotlib
    python 05_render_official_diagram.py --province-th พิษณุโลก --amphoe-th บางกระทุ่ม --tambon-th นครป่าหมาก
    # หรือถ้ารู้ tambon_id (uuid) อยู่แล้ว:
    python 05_render_official_diagram.py --tambon-id 25756676-79a7-4df2-bed4-ddc80868ae15
    # ผลลัพธ์: ไฟล์ .png ในโฟลเดอร์เดียวกัน (ตั้งชื่อ output เองได้ด้วย --out)
"""
import argparse
import sys

import matplotlib
matplotlib.use("Agg")  # ไม่ต้องมีจอ/display ก็รันได้ (เผื่อรันบน server ทีหลังตามที่ Ton บอกว่าจะทำเป็นปุ่ม)
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, Patch, Polygon, Rectangle, RegularPolygon
from matplotlib.lines import Line2D
import requests

# ค่าเชื่อมต่อ Supabase สาธารณะ (publishable/anon key เดียวกับที่ฝัง client-side ใน
# 06_web_platform/03_frontend/index.html อยู่แล้ว — ไม่ฃช่ความลับ อ่านได้แค่ view ที่เปิดสาธารณะเท่านั้น)
SUPABASE_URL = "https://khfixycxjwxcpayiwxap.supabase.co"
SUPABASE_PUBLISHABLE_KEY = "sb_publishable_1Iju7_QORaqhtYE4HryrGQ_KzYGx_1i"

# รายชื่อฟอนต์ที่รองรับภาษาไทย เรียงจากที่มักมีอยู่แล้วบน Windows (Tahoma/Leelawadee UI มีมาให้ในเครื่อง
# ทุกเครื่องตั้งแต่ Windows 7/8 ขึ้นไป) ไปจนถึงฟอนต์โอเพนซอร์สที่มักมีบน Linux (Noto Sans Thai/Garuda/Waree)
# — matplotlib จะไล่ใช้ตัวแรกที่หาเจอในเครื่องจริง ถ้าไม่ตั้งค่านี้ ฟอนต์ default (DejaVu Sans) จะไม่มี
# ตัวอักษรไทยเลย ทำให้ข้อความบนผังทั้งหมดหายไปเป็นช่องว่าง/กล่องขาดหาย (เจอบั๊กนี้จริงตอนทดสอบครั้งแรก)
FONT_TH_CANDIDATES = ["Tahoma", "Leelawadee UI", "TH Sarabun New", "Noto Sans Thai", "Garuda", "Waree", "sans-serif"]
matplotlib.rcParams["font.family"] = FONT_TH_CANDIDATES
matplotlib.rcParams["axes.unicode_minus"] = False


def _headers():
    return {"apikey": SUPABASE_PUBLISHABLE_KEY, "Authorization": f"Bearer {SUPABASE_PUBLISHABLE_KEY}"}


def find_tambon_id(province_th, amphoe_th, tambon_th):
    resp = requests.post(
        f"{SUPABASE_URL}/rest/v1/rpc/nw_find_tambon_id",
        headers={**_headers(), "Content-Type": "application/json"},
        json={"p_province_th": province_th, "p_amphoe_th": amphoe_th, "p_tambon_th": tambon_th},
        timeout=30,
    )
    resp.raise_for_status()
    tambon_id = resp.json()
    if not tambon_id:
        raise SystemExit(
            f"ไม่พบตำบล '{tambon_th}' อำเภอ '{amphoe_th}' จังหวัด '{province_th}' ใน Supabase "
            f"— ตรวจการสะกดชื่อ หรือระบุ --tambon-id ตรง ๆ แทน"
        )
    return tambon_id


def fetch_diagram(tambon_id):
    nodes = requests.get(
        f"{SUPABASE_URL}/rest/v1/nw_diagram_current_nodes",
        headers=_headers(), params={"tambon_id": f"eq.{tambon_id}", "select": "*"}, timeout=30,
    )
    edges = requests.get(
        f"{SUPABASE_URL}/rest/v1/nw_diagram_current_edges",
        headers=_headers(), params={"tambon_id": f"eq.{tambon_id}", "select": "*"}, timeout=30,
    )
    nodes.raise_for_status()
    edges.raise_for_status()
    nodes_data, edges_data = nodes.json(), edges.json()
    if not nodes_data:
        raise SystemExit(f"ตำบลนี้ (tambon_id={tambon_id}) ยังไม่มีผังน้ำใน Supabase เลา (version ปัจจุบันว่าง)")
    return nodes_data, edges_data


# ---------------------------------------------------------------------------
# สัญลักษณ์โครงสร้าง — อ้างอิงตาราง waterchart_symbol_schema.md ข้อ 2 (ให้ตรงกับ stylesheet ของ
# Cytoscape.js ใน 03_frontend/index.html ไบชรกักทางการหน้าตาตรงกับที่เห็นตอนแก้ไขนเว็บ'
# แต่ละ entry: (label ที่โชท์ใน legend, ฟังก์ชันวาด)
# ---------------------------------------------------------------------------

# สถานะ "ชำรุด" (Task, Ton 2026-09-02) — ตามคู่มือ สสน. หน้า 16-17: ปตร./ฝาย ชำรุด ใช้ลายเส้นทแยง (hatch)
# ในตัวสัญลักษณ์เดียวกับสถานะปกติ แทนสีทึบ/สีขาว — matplotlib รองรับผ่านพารามิเตอร์ hatch ของ Patch โดยตรง
# ไม่ต้องพึ่งรูปภาพเหมือนฝั่ง Cytoscape.js (ดู STATUS_BROKEN_HATCH ใน 03_frontend/index.html ที่ใช้ลายเดียวกัน)
# — อ่างเก็บน้ำ/สถานีสูบน้ำ/สถานีโทรมาตรไม่มีสัญลักษณ์ชำรุดกำหนดไว้ในคู่มือ จึงออกแบบเพิ่มให้เข้าธีมเดียวกัน
# (ลายเส้นทแยงเหมือนกันหมด) ตามที่ Ton เลือกไว้
_BROKEN_HATCH = "///"


def _draw_gate(ax, x, y, filled, broken=False):
    size = 9
    diamond = RegularPolygon(
        (x, y), numVertices=4, radius=size, orientation=0.785398,  # หมุน 45 องศา = ข้าวหลามตัด
        facecolor="white" if broken else ("black" if filled else "white"),
        edgecolor="black", linewidth=1.3, hatch=_BROKEN_HATCH if broken else None, zorder=5,
    )
    ax.add_patch(diamond)


def _draw_weir(ax, x, y, filled, vertical, broken=False):
    w, h = (12, 32) if vertical else (32, 12)
    rect = Rectangle(
        (x - w / 2, y - h / 2), w, h,
        facecolor="white" if broken else ("black" if filled else "white"),
        edgecolor="black", linewidth=1.3, hatch=_BROKEN_HATCH if broken else None, zorder=5,
    )
    ax.add_patch(rect)


def _draw_reservoir(ax, x, y, filled, broken=False):
    size = 11
    tri = RegularPolygon(
        (x, y), numVertices=3, radius=size,
        facecolor="white" if broken else ("black" if filled else "white"),
        edgecolor="black", linewidth=1.3, hatch=_BROKEN_HATCH if broken else None, zorder=5,
    )
    ax.add_patch(tri)


def _draw_telemetry(ax, x, y, broken=False):
    hatch = _BROKEN_HATCH if broken else None
    ax.add_patch(plt.Circle((x, y), 9, facecolor="white", edgecolor="black", linewidth=1.8, hatch=hatch, zorder=5))
    ax.add_patch(plt.Circle((x, y), 4, facecolor="white", edgecolor="black", linewidth=1.2, zorder=5))


def _draw_pump(ax, x, y, broken=False):
    hatch = _BROKEN_HATCH if broken else None
    ax.add_patch(plt.Circle((x, y), 11, facecolor="white", edgecolor="black", linewidth=1.3, hatch=hatch, zorder=5))
    ax.text(x, y, "P", ha="center", va="center", fontsize=10, fontweight="bold", zorder=6)


def _draw_waterbody(ax, x, y, label, vertical, source_ref):
    w, h = (26, 44) if vertical else (44, 26)
    rect = Rectangle(
        (x - w / 2, y - h / 2), w, h, facecolor="#99ccff", edgecolor="#0056b3", linewidth=1.2, zorder=4,
    )
    ax.add_patch(rect)
    text = label or ""
    if source_ref:
        text = f"{text}\n[sp{source_ref}]" if text else f"[{source_ref}]"
    if text:
        ax.text(x, y, text, ha="center", va="center", fontsize=6.5, color="#003366",
                 fontweight="bold", zorder=6)


def _draw_generic(ax, x, y):
    ax.add_patch(plt.Circle((x, y), 3.5, facecolor="#6c757d", edgecolor="none", zorder=5))


NODE_LEGEND_LABEL = {
    "gate": "ประตูระบายน้ำ/ปตร. (ปัจจุบัน)",
    "gate_plan": "ประตูระบายน้ำ/ปตร. (แผน)",
    "weir": "ฝาย (ปัจจุบัน)",
    "weir_plan": "ฝาย (แผน)",
    "reservoir": "อ่างเก็บน้ำ (ปัจจุบัน)",
    "reservoir_plan": "อ่างเก็บน้ำ (แผน)",
    "telemetry": "สถานีโทรมาตร",
    "pump": "สถานีสูบน้ำ",
    "waterbody": "แหล่งน้ำ (หนอง/บึง/สระน้ำ)",
}

# สถานะ "ชำรุด" ใช้กับโครงสร้าง "ปัจจุบัน" 5 ชนิดเท่านั้น (ดู draw_node) — ไม่ใช้กับ _plan เพราะโครงสร้างที่
# ยังเป็นแผน ยังไม่สร้างจริง จึงชำรุดไม่ได้ กุญแจ dict นี้เป็น pseudo-type "<node_type>_broken" ใช้เฉพาะตอน
# สร้าง legend (ดู render()) ไม่ใช่ค่าจริงของ node_type ในฐานข้อมูล
NODE_LEGEND_LABEL_BROKEN = {
    "gate_broken": "ประตูระบายน้ำ/ปตร. (ชำรุด)",
    "weir_broken": "ฝาย (ชำรุด)",
    "reservoir_broken": "อ่างเก็บน้ำ (ชำรุด)",
    "telemetry_broken": "สถานีโทรมาตร (ชำรุด)",
    "pump_broken": "สถานีสูบน้ำ (ชำรุด)",
}
STATUS_BROKEN_ELIGIBLE_TYPES = {"gate", "weir", "reservoir", "telemetry", "pump"}


def draw_node(ax, node):
    x, y = node["pos_x"], node["pos_y"]
    node_type = node.get("node_type")
    vertical = (node.get("dir") == "v")
    label = node.get("label") or ""
    broken = node.get("status") == "ชำรุด" and node_type in STATUS_BROKEN_ELIGIBLE_TYPES

    if node_type == "gate":
        _draw_gate(ax, x, y, filled=True, broken=broken)
    elif node_type == "gate_plan":
        _draw_gate(ax, x, y, filled=False)
    elif node_type == "weir":
        _draw_weir(ax, x, y, filled=True, vertical=vertical, broken=broken)
    elif node_type == "weir_plan":
        _draw_weir(ax, x, y, filled=False, vertical=vertical)
    elif node_type == "reservoir":
        _draw_reservoir(ax, x, y, filled=True, broken=broken)
    elif node_type == "reservoir_plan":
        _draw_reservoir(ax, x, y, filled=False)
    elif node_type == "telemetry":
        _draw_telemetry(ax, x, y, broken=broken)
    elif node_type == "pump":
        _draw_pump(ax, x, y, broken=broken)
    elif node_type == "waterbody":
        _draw_waterbody(ax, x, y, label, vertical, node.get("source_ref"))
        return  # label วาดในกล่องไปแล้ว ไม่ต้องวาดซ้ำด้านล่างนี้
    elif node_type == "text_box":
        ax.text(x, y, label, ha="center", va="center", fontsize=8, fontweight="bold",
                 color="#d9534f", zorder=6)
        return
    else:
        _draw_generic(ax, x, y)

    if label and node_type != "generic_node":
        ax.text(x, y - 13, label, ha="center", va="top", fontsize=6.5, zorder=6, wrap=True)


def draw_edge(ax, edge, node_by_key):
    u = node_by_key.get(edge["source_node_key"])
    v = node_by_key.get(edge["target_node_key"])
    if u is None or v is None:
        return  # กันกรณีข้อมุลไม่ตรงกัน (ไม่ควรเกิด แต่กันไว้ไม่กให้สคริปต์ล้ว)
    is_main = edge.get("edge_type") == "main"
    color = "#0056b3" if is_main else "#4da6ff"
    width = 2.6 if is_main else 1.4
    arrow = FancyArrowPatch(
        (u["pos_x"], u["pos_y"]), (v["pos_x"], v["pos_y"]),
        arrowstyle="-|>", mutation_scale=14, color=color, linewidth=width,
        shrinkA=10, shrinkB=10, zorder=2,
    )
    ax.add_patch(arrow)
    if edge.get("label"):
        mx, my = (u["pos_x"] + v["pos_x"]) / 2, (u["pos_y"] + v["pos_y"]) / 2
        ax.text(mx, my, edge["label"], ha="center", va="center", fontsize=6,
                 color=color, backgroundcolor="white", zorder=3)


def draw_north_arrow(ax, x, y, size=28):
    # วาดหลังจาก invert_yaxis() แล้ว ดังนั้น "ขึ้น" ในหน้าจอก = ทิศเหนือจริง ตรงกับที่ผังบนเว็บแสดงผล
    ax.add_patch(Polygon(
        [(x, y + size), (x - size * 0.35, y - size * 0.4), (x + size * 0.35, y - size * 0.4)],
        closed=True, facecolor="#0066FF", edgecolor="none", zorder=10,
    ))
    ax.text(x, y - size * 0.75, "เหนือ", ha="center", va="top", fontsize=9, fontweight="bold", zorder=10)


def render(nodes, edges, title, out_path):
    node_by_key = {n["node_key"]: n for n in nodes}

    fig, ax = plt.subplots(figsize=(14, 10), dpi=150)

    for edge in edges:
        draw_edge(ax, edge, node_by_key)
    for node in nodes:
        draw_node(ax, node)

    xs = [n["pos_x"] for n in nodes]
    ys = [n["pos_y"] for n in nodes]
    pad_x = max((max(xs) - min(xs)) * 0.08, 40)
    pad_y = max((max(ys) - min(ys)) * 0.08, 40)
    ax.set_xlim(min(xs) - pad_x, max(xs) + pad_x)
    ax.set_ylim(min(ys) - pad_y, max(ys) + pad_y)

    # สณคัญ: pos_x/pos_y มาจาก 04_export_frontend_data.py's to_screen_xy() ซึ่งกลับแกน Y ไว้แล้วให้เป็น
    # "พิกัดหน้าจอ" แบบเดียวกับที่ Cytoscape.js/เว็บ (y เพิ่ม = ลงล่าง, เหนือ=ค่า y น้อย/บนสุด) — matplotlib
    # ปกติแกน y ชี้ขึ้น (ตรงข้าม) ถ้าไม่ invert ตรงนี้ ทิศเหนือจะไปโผล่ด้านล่างภาพแทน กลับหัวกับผังบนเว็บ
    ax.invert_yaxis()
    ax.set_aspect("equal")
    ax.axis("off")

    # 1) ชื่อผังน้ำ
    ax.set_title(title, fontsize=18, fontweight="bold", pad=20)

    # 2) ทิศเหนือ — วางไว้มุมซ้ายบนของกรอบข้อมูลจริง (ก่อน invert, ล่างสุดของแกน y ในเชิงค่าคือบนสุดของภาพ)
    corner_x = min(xs) - pad_x * 0.4
    corner_y = min(ys) - pad_y * 0.4
    draw_north_arrow(ax, corner_x, corner_y)

    # 4) Legend เฉพาะสัญลักษณ์ที่ใช้จริงในแผ่นนี้ (ข้อบังคับข้อ 4 ของคู่มือ สสน.)
    used_node_types = {n.get("node_type") for n in nodes if n.get("node_type")}
    used_broken_types = {
        n.get("node_type") + "_broken" for n in nodes
        if n.get("status") == "ชำรุด" and n.get("node_type") in STATUS_BROKEN_ELIGIBLE_TYPES
    }
    used_edge_types_main = any(e.get("edge_type") == "main" for e in edges)
    used_edge_types_branch = any(e.get("edge_type") != "main" for e in edges)

    legend_handles = []
    if used_edge_types_main:
        legend_handles.append(Line2D([0], [0], color="#0056b3", lw=2.6, label="ลำน้ำหลัก"))
    if used_edge_types_branch:
        legend_handles.append(Line2D([0], [0], color="#4da6ff", lw=1.4, label="ลำน้ำสาขา"))
    for nt in sorted(used_node_types):
        if nt in NODE_LEGEND_LABEL:
            legend_handles.append(Line2D([0], [0], marker="s", color="w",
                                          markerfacecolor="black" if "plan" not in nt else "white",
                                          markeredgecolor="black", markersize=9,
                                          label=NODE_LEGEND_LABEL[nt]))
    for bt in sorted(used_broken_types):
        if bt in NODE_LEGEND_LABEL_BROKEN:
            legend_handles.append(Patch(facecolor="white", edgecolor="black", hatch=_BROKEN_HATCH,
                                         label=NODE_LEGEND_LABEL_BROKEN[bt]))
    if legend_handles:
        ax.legend(handles=legend_handles, loc="upper left", bbox_to_anchor=(1.0, 1.0),
                    fontsize=9, frameon=True, title="สัญลักษณ์")

    fig.tight_layout()
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    print(f"บันทึกผังน้ำฉบับทางการ (preview): {out_path}")
    print(f"  โหนดทั้งหมด {len(nodes)} จุด, เส้นเชื่อม {len(edges)} เส้น, "
          f"มีข้อมูลตรวจวัดจริงผูกไว้ {sum(1 for n in nodes if n.get('source_ref'))} จุด")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--tambon-id", help="uuid ของตำบล (ถ้าไม่ระบุ ต้องระบุ 3 ชื่อด้านล่างแทน)")
    p.add_argument("--province-th")
    p.add_argument("--amphoe-th")
    p.add_argument("--tambon-th")
    p.add_argument("--title", help="ข้อความหัวเรื่อง (ถ้าไม่ระบุ จะสร้างจาก 3 ชื่อด้านบนให้อัตโนมัติ)")
    p.add_argument("--out", default=None, help="path ไฟล์ผลลัพธ์ (.png) ค่าเริ่มต้น: official_watermap_<tambon-th>.png")
    args = p.parse_args()

    if args.tambon_id:
        tambon_id = args.tambon_id
    else:
        if not (args.province_th and args.amphoe_th and args.tambon_th):
            sys.exit("ต้องระบุ --tambon-id หรือครบทั้ง --province-th --amphoe-th --tambon-th")
        tambon_id = find_tambon_id(args.province_th, args.amphoe_th, args.tambon_th)

    nodes, edges = fetch_diagram(tambon_id)

    title = args.title or "ผังน้ำ" + "".join(
        f" {v}" for v in [
            f"ตำบล{args.tambon_th}" if args.tambon_th else None,
            f"อำเภอ{args.amphoe_th}" if args.amphoe_th else None,
            f"จังหวัด{args.province_th}" if args.province_th else None,
        ] if v
    )
    if not args.tambon_th and not args.title:
        title = f"ผังน้ำ (tambon_id={tambon_id})"

    out_path = args.out or f"official_watermap_{(args.tambon_th or tambon_id)}.png"
    render(nodes, edges, title, out_path)


if __name__ == "__main__":
    main()
