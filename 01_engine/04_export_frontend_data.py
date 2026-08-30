"""
06_web_platform/01_engine/04_export_frontend_data.py

เอนจินใหม่ (ตาม ADR-002) — Phase 4 (ส่วนเตรียมข้อมูล): แปลงผลลัพธ์ Phase 3 (nodes_schematic.geojson,
edges_schematic.geojson) ให้เป็นไฟล์ JavaScript ที่ Final_Frontend.html (Cytoscape.js) โหลดใช้ได้ตรง ๆ
แทนข้อมูลตัวอย่าง (initialElements) ที่ hardcode ไว้ในไฟล์ต้นแบบ

ทำไมต้องเป็นไฟล์ .js (ไม่ใช่ fetch() ไฟล์ .json ตรง ๆ): ตอนนี้ยังไม่มี backend/เว็บเซิร์ฟเวอร์ (Phase 5 ยังไม่ทำ)
การเปิดไฟล์ HTML ตรง ๆ จาก disk (file://) ผ่าน fetch() ไปอ่านไฟล์ .json อื่นจะโดนบล็อกด้วย CORS policy ของ
เบราว์เซอร์ (ทดสอบแล้วเป็นปัญหาจริงกับ Chrome/Firefox เวลาเปิดไฟล์ local ตรง ๆ ไม่ผ่าน server) — ไฟล์ .js ที่มี
`const engineElements = [...]` เป็น script ธรรมดา โหลดผ่าน <script src=...> ได้เสมอไม่ว่าจะเปิดจาก disk ตรง ๆ
หรือผ่าน server ก็ตาม เหมาะกับช่วงที่ยังไม่มี backend

การแปลงพิกัด: nodes_schematic.geojson เก็บพิกัดเป็นเมตรจริงในระบบ UTM (EPSG:32647, แกน Y ทิศเหนือเป็นบวก) —
Cytoscape.js ใช้พิกัดหน้าจอ (แกน Y ทิศลงเป็นบวก ตามธรรมเนียม screen-space) จึงต้อง (1) กลับแกน Y (เหนือ=บนจอ
สอดคล้องกับที่ Ton ยืนยันว่าน้ำไหลเข้าตำบลจากบนลงล่าง) (2) ปรับสเกลให้พอดีกับพื้นที่แสดงผลที่อ่านง่าย (ค่าพิกัด
จริงเป็นหลักหมื่นเมตร ถ้าใช้ตรง ๆ เป็น pixel จะทำให้ผังกว้างเกินจอมาก) — ใช้สเกลเดียวกันทั้ง 2 แกน (uniform scale)
เพื่อไม่ให้มุมฉากที่ Phase 3 จัดไว้บิดเบี้ยว

หมายเหตุ: node จาก engine เป็นแค่ "จุดต่อ/จุดแยกทางโทโพโลยี" ไม่ใช่โครงสร้างจริง (ปตร./ฝาย/ฯลฯ) — จึงไม่ใส่ type
ให้ (ปล่อยเป็น node เปล่า ๆ สีเทาตาม default style) ให้ชุมชนเป็นผู้ระบุประเภทโครงสร้างจริงเองผ่านเครื่องมือแก้ไขใน
Final_Frontend.html (สอดคล้องกับ Phase 4 ตาม Architecture.html: Human-in-the-Loop Verification) — เส้นเชื่อมที่
เป็น self-loop (u==v, ความยาวศูนย์ — เป็น artifact จากข้อมูล ไม่ใช่เส้นทางน้ำจริง ดู README) ถูกกรองออกจากการ
ส่งออกนี้เพราะไม่มีประโยชน์ในการแสดงผล (จุดเดียวกันไปกลับ มองไม่เห็นเป็นเส้นอยู่แล้วเพราะความยาวศูนย์)

**ไม่ hardcode ชื่อ/พิกัดตำบลใด ๆ ในไฟล์นี้** ใช้ได้กับผลลัพธ์ Phase 3 ของตำบลใดก็ได้
"""
import argparse
import json
import os

import geopandas as gpd

TARGET_CANVAS_PX = 2400.0  # ด้านที่ยาวที่สุดของผังจะสเกลให้พอดีกับขนาดนี้ (พิกเซล) ปรับดูจริงแล้วอ่านง่ายบนจอทั่วไป


def _segment_dist_weight(p1, p2, bend):
    """คำนวณ (segment-distance, segment-weight) ของจุดหักมุม `bend` เทียบกับเส้นตรง p1->p2 — ใช้ค่านี้กับ
    Cytoscape.js curve-style: 'segments' (segment-distances/segment-weights) เพื่อบังคับให้เส้นเชื่อมหักมุม
    ตรงจุดเป๊ะตามที่ Phase 3 คำนวณไว้จริง (ไม่ปล่อยให้ Cytoscape คำนวณเส้นทางเอง) — สูตรมาตรฐานการ project จุดลง
    บนเส้นตรง (weight = ระยะที่ project ลงบนเส้น หารความยาวเส้นยกกำลังสอง, distance = ระยะตั้งฉากจากเส้น มีเครื่อง
    หมายบอกด้านซ้าย/ขวาตามทิศจาก p1->p2)"""
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    len_sq = dx * dx + dy * dy
    if len_sq == 0:
        return 0.0, 0.5
    bx, by = bend[0] - p1[0], bend[1] - p1[1]
    weight = (bx * dx + by * dy) / len_sq
    distance = (bx * dy - by * dx) / (len_sq ** 0.5)
    return distance, weight


def build_elements(nodes_gdf: gpd.GeoDataFrame, edges_gdf: gpd.GeoDataFrame):
    """สร้าง list ของ element dict ตามฟอร์แมตที่ Cytoscape.js ใช้ (เหมือน initialElements ใน
    Final_Frontend.html) — คืนค่า (elements, scale_stats) สำหรับรายงาน

    หมายเหตุสำคัญ (แก้ไขหลัง Ton ทักท้วงว่าผังใน frontend ไม่ตรงกับภาพ sanity check ของ Phase 3 เลย): เดิม
    ส่งออกแค่ตำแหน่ง node กับ source/target ของแต่ละเส้น ปล่อยให้ Cytoscape.js เลือกวิธีวาดเส้นเอง (สไตล์ 'taxi'
    ที่ Final_Frontend.html ตั้งค่า taxi-direction เป็น 'downward' ตายตัวทั้งกราฟ) ผลคือแม้เส้นจะตรงอยู่แล้วจริง
    ๆ ตามที่ Phase 3 คำนวณไว้ (นครป่าหมาก 43 จาก 46 เส้นตรงเป๊ะ มีแค่ 3 เส้นที่หักมุมจริง) Cytoscape ก็ยังบังคับ
    หักมุมเพิ่มเองแทบทุกเส้นอยู่ดี ทำให้ผังดูเป็นตารางกริดซับซ้อนเกินจริงมาก ไม่ตรงกับที่ engine คำนวณไว้เลย —
    แก้ไขโดยอ่าน geometry จริงของแต่ละเส้นเชื่อม (LineString 2 หรือ 3 จุด ที่ Phase 3 คำนวณไว้แล้ว) แล้วส่งข้อมูล
    การหักมุมที่แท้จริงไปด้วย: เส้นตรง (2 จุด) ได้ flag `engineStraight` ให้ frontend บังคับ curve-style เป็น
    'straight' ตรง ๆ, เส้นหักมุม (3 จุดจริง ไม่ใช่จุดกลางที่ซ้ำกับปลายใดปลายหนึ่ง) ได้ flag `engineBend` พร้อมค่า
    `segDist`/`segWeight` ที่คำนวณจากจุดหักมุมจริง ให้ frontend ใช้ curve-style: 'segments' วาดเส้นหักมุมตรงจุด
    เป๊ะตามที่ engine คำนวณ — เส้นที่ชุมชนวาดเพิ่มเองภายหลัง (ไม่มี field พวกนี้) ยังใช้สไตล์ taxi/downward เดิม
    ตามที่ Ton ออกแบบไว้"""
    xs = nodes_gdf.geometry.x.tolist()
    ys = nodes_gdf.geometry.y.tolist()
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    width = max_x - min_x or 1.0
    height = max_y - min_y or 1.0
    scale = TARGET_CANVAS_PX / max(width, height)
    margin = 40

    def to_screen_xy(x, y):
        # กลับแกน Y (เหนือ=บนจอ) + สเกลเดียวกันทั้ง 2 แกน (ไม่บิดมุมฉาก) + เว้นขอบเล็กน้อย
        return (round((x - min_x) * scale) + margin, round((max_y - y) * scale) + margin)

    elements = []
    for row in nodes_gdf.itertuples():
        sx, sy = to_screen_xy(row.geometry.x, row.geometry.y)
        elements.append({
            "data": {"id": f"n{row.node_id}", "label": "", "rotation": 0, "dir": "h"},
            "position": {"x": sx, "y": sy},
        })

    n_self_loop_skipped = 0
    n_straight = 0
    n_bend = 0
    for row in edges_gdf.itertuples():
        if row.u == row.v:
            n_self_loop_skipped += 1
            continue  # self-loop = artifact ข้อมูล ไม่ใช่เส้นทางน้ำจริง (ดู README) ไม่ส่งออกไปแสดงผล

        data = {
            "id": f"e{row.edge_id}",
            "source": f"n{row.u}",
            "target": f"n{row.v}",
            "label": row.name if getattr(row, "name", None) else "",
            "type": row.waterway_size,
        }

        coords = list(row.geometry.coords)
        screen_coords = [to_screen_xy(x, y) for x, y, *_ in coords]
        p1, p2 = screen_coords[0], screen_coords[-1]
        bend = screen_coords[1] if len(screen_coords) == 3 else None
        if bend is not None and bend != p1 and bend != p2:
            dist, weight = _segment_dist_weight(p1, p2, bend)
            data["engineBend"] = True
            data["segDist"] = round(dist, 2)
            data["segWeight"] = round(weight, 4)
            n_bend += 1
        else:
            data["engineStraight"] = True
            n_straight += 1

        elements.append({"data": data})

    stats = {
        "n_nodes": len(nodes_gdf), "n_edges_kept": len(edges_gdf) - n_self_loop_skipped,
        "n_self_loop_skipped": n_self_loop_skipped, "n_straight": n_straight, "n_bend": n_bend,
        "scale_m_per_px": 1.0 / scale if scale else None,
    }
    return elements, stats


def export_frontend_data(phase3_dir: str, out_js_path: str, var_name: str = "engineElements"):
    nodes_gdf = gpd.read_file(os.path.join(phase3_dir, "nodes_schematic.geojson"))
    edges_gdf = gpd.read_file(os.path.join(phase3_dir, "edges_schematic.geojson"))
    elements, stats = build_elements(nodes_gdf, edges_gdf)

    os.makedirs(os.path.dirname(out_js_path) or ".", exist_ok=True)
    with open(out_js_path, "w", encoding="utf-8") as f:
        f.write("// ไฟล์นี้สร้างอัตโนมัติจาก 01_engine/04_export_frontend_data.py — ห้ามแก้ไขตรง ๆ "
                "(รันสคริปต์ใหม่แทนถ้าต้องการอัปเดตข้อมูล)\n")
        f.write(f"const {var_name} = ")
        json.dump(elements, f, ensure_ascii=False, indent=2)
        f.write(";\n")

    return stats


def main():
    ap = argparse.ArgumentParser(description="Phase 4 (เตรียมข้อมูล): แปลงผลลัพธ์ Phase 3 เป็นไฟล์ .js "
                                              "สำหรับ Final_Frontend.html (Cytoscape.js)")
    ap.add_argument("--phase3-dir", required=True, help="โฟลเดอร์ output ของ Phase 3 (มี nodes_schematic.geojson, "
                                                          "edges_schematic.geojson)")
    ap.add_argument("--out-js", required=True, help="path ไฟล์ .js ที่จะสร้าง")
    ap.add_argument("--var-name", default="engineElements", help="ชื่อตัวแปร JS ที่ประกาศ (ค่าเริ่มต้น "
                                                                   "engineElements)")
    args = ap.parse_args()

    stats = export_frontend_data(args.phase3_dir, args.out_js, args.var_name)
    print(f"ส่งออก {stats['n_nodes']} node, {stats['n_edges_kept']} เส้นเชื่อม "
          f"(ข้าม self-loop {stats['n_self_loop_skipped']} เส้น) ไปที่ {args.out_js}")
    print(f"เส้นตรง (engineStraight): {stats['n_straight']}, เส้นหักมุมจริง (engineBend): {stats['n_bend']}")
    print(f"สเกล: 1 พิกเซล ≈ {stats['scale_m_per_px']:.1f} เมตร")


if __name__ == "__main__":
    main()
