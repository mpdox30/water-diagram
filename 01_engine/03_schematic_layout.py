"""
เอนจินเขียนใหม่ทั้งหมด (ADR-002) — Phase 3: Schematic Transformation (การดัดเส้นสร้างผังภาพ)

ตามสเปคใน 00_design_docs/Architecture.html Phase 3:
  1. แปลงเส้นทางน้ำธรรมชาติที่คดเคี้ยวให้เป็นแนวเส้นตรง ด้วย Orthogonal Graph Layout
  2. ปรับความหนาของเส้นเพื่อแยกขนาดเส้นน้ำหลักและเส้นสาขาอย่างชัดเจน
  3. จัดมุมการหักเลี้ยวของทิศทางน้ำให้ดูง่ายและเป็นระเบียบ

รับกราฟโครงข่าย (nodes.geojson, edges.geojson) จาก Phase 2 (พิกัดจริง UTM) มาคำนวณตำแหน่งใหม่ในพื้นที่ผัง
(schematic space) — ไม่ใช้อัลกอริทึม/โค้ดจาก pipeline เดิม 19 รอบ (ADR-002) เขียนใหม่จากหลักการ orthogonal
graph drawing มาตรฐาน ยังคง generic ไม่ hardcode ตำบลใด ๆ

=== ประวัติเวอร์ชันที่ลองแล้วไม่ได้ผล (บันทึกไว้กันลืม/กันทำซ้ำ) ===

v1 — บังคับทุกเส้นเชื่อมเป็น 1 ท่อนตรงเป๊ะด้วย constraint graph 2 แกน (union-find รวมกลุ่ม node ที่ต้อง X หรือ Y
เท่ากันตามเส้นเชื่อมจริง + จัดอันดับด้วย longest-path บน DAG): ทดสอบกับข้อมูลจริงพบ 104/162 เส้นยุบเหลือความยาว
ศูนย์ เพราะ node ถูกรวมกลุ่มแบบลูกโซ่ตามเส้นเชื่อมทั่วทั้งกราฟโดยไม่ได้ตั้งใจ (transitive collapse)

v2 — จัดอันดับตำแหน่งอิสระต่อกันทีละแกน โดยรวมกลุ่ม node ที่อยู่ในระยะ tolerance (35 ม.) ตามลำดับพิกัดที่เรียง
แล้ว: ยังพบปัญหาเดิมซ้ำอีกแบบ (60/162 เส้นยุบเหลือศูนย์ บางเส้นจริงยาวถึง 8.7 กม.) เพราะการไล่ merge ตามช่องว่างที่
เรียงต่อกันเป็น "single-linkage chaining"

v3 — จัดอันดับตำแหน่งแต่ละแกนแบบไม่ซ้ำกันเลย (unique rank ทั้งกราฟ, ไม่มีการ merge) แล้วให้ทุกเส้นหักมุมฉากเอง
(elbow routing): แก้ปัญหาเส้นยุบเหลือศูนย์ได้หมด (เหลือเฉพาะ self-loop จริงเท่านั้น) แต่ **Ton ตรวจสอบผลลัพธ์แล้ว
ชี้ว่าผังดูฟันปลา/หักมุมถี่เกินจริง** เทียบกับผังอ้างอิงที่ Ton วาดเส้นไกด์ให้ (คลองวังทอง, คลองโกรกเกรง,
คลองโกรกเกรงเล็ก ควรเป็นเส้นตรงยาวต่อเนื่อง หักมุมแค่จุดเดียวตรงที่ทิศทางจริงเปลี่ยนเท่านั้น) — สาเหตุคือ v3 จัด
อันดับตำแหน่งแต่ละ node "อิสระจากกันทั้งกราฟ" ตามลำดับพิกัดจริงทั้งหมด ทำให้ node ที่ควรอยู่แนวเดียวกัน (เพราะเป็น
ส่วนหนึ่งของลำน้ำสายเดียวกันที่ตรงต่อเนื่อง) ได้ rank ต่างกันเพราะมี node จากลำน้ำสาขาอื่นที่ไม่เกี่ยวข้องเลยแทรก
อยู่ระหว่างกลางในลำดับพิกัดจริง (โดยเฉพาะเมื่อ Phase 2 ไม่ได้ยุบ node ทางผ่านข้ามจุดที่ attribute ต่างกันเล็กน้อย
เช่น source/name ไม่ตรงกันพอดี แม้เส้นจะตรงต่อเนื่องกันจริงทางเรขาคณิต) ผลคือเกิดจุดหักมุมเล็ก ๆ ถี่ ๆ ตลอดเส้นที่
ควรจะตรง ไม่ตรงกับพฤติกรรมจริงของแม่น้ำ/คลอง

=== วิธีที่ใช้จริง (v4) — Spanning-tree position propagation ===

แก้ปัญหาของ v3 ด้วยการเลิก "จัดอันดับอิสระทั้งกราฟ" แล้วเปลี่ยนเป็น **ส่งต่อพิกัดตามเส้นทางที่เดินจริงในกราฟ**
(คล้ายวิธีวาง node ของต้นไม้/tree layout): เดินสำรวจกราฟแบบ DFS จาก node เริ่มต้น (เลือก node ที่มีพิกัดจริงอยู่
ทางเหนือสุดของแต่ละ component เป็นจุดเริ่ม เพราะน้ำไหลเข้าตำบลนี้จากทางเหนือลงใต้ตามที่ Ton อธิบาย) แล้ว "เดินต่อ
เป็นเส้นเดียวกัน" ไปเรื่อย ๆ ตราบใดที่ยังไม่เจอ node ที่ถูกกำหนดตำแหน่งไปแล้ว:

  สำหรับแต่ละเส้นเชื่อมที่เดินผ่านครั้งแรก (u กำหนดตำแหน่งแล้ว, v ยังไม่กำหนด) — คำนวณทิศทางจริง (dx, dy) ระหว่าง
  พิกัดจริงของ u กับ v แล้ว snap เข้าทิศที่ใกล้ที่สุด (|dx|>=|dy| → แนวนอน ไม่งั้นแนวตั้ง) เหมือนเดิม จากนั้น
  **สืบทอดพิกัดจาก u โดยตรง**: ถ้าเป็นแนวตั้ง v.x = u.x (คงพิกัด X เดิมไว้ ไม่จัดอันดับใหม่) แล้วขยับ v.y ตาม
  ทิศทางจริง (จำนวนก้าวของหน่วยกริดตามความยาวจริงของเส้นในแกนนั้น ปัดเป็นจำนวนเต็มอย่างน้อย 1 ก้าว) ถ้าเป็นแนวนอน
  ก็ทำแบบเดียวกันสลับแกน — วิธีนี้การันตีว่าตราบใดที่เดินต่อเนื่องไปในทิศเดิม (เช่น ลำน้ำสายตรงที่ไม่มีจุดหักจริง)
  พิกัดแกนตั้งฉากจะ**คงที่ตลอดทั้งสาย** เกิดเป็นเส้นตรงยาวต่อเนื่องจริง ไม่มีการหักมุมปลอมจากอิทธิพลของ node อื่น
  ที่ไม่เกี่ยวข้องเลย — เส้นจะหักมุมก็ต่อเมื่อทิศทางจริง (dx,dy) ของเส้นเชื่อมนั้นเปลี่ยนแกนจริง ๆ เท่านั้น ตรงตาม
  หลักที่ Ton อธิบาย (เช่น คลองโกรกเกรงเล็กไหลขนานลงมาแล้วเปลี่ยนทิศไปทางตะวันออกที่จุดหนึ่งจริงในภูมิประเทศ)

  ที่จุดแยก (junction, degree>=3) จะเดินสำรวจ "เส้นหลัก" (waterway_size=='main') และเส้นที่ยาวกว่าก่อนเสมอ (จัด
  ลำดับ neighbor ที่ยังไม่กำหนดตำแหน่งด้วย (main ก่อน, ความยาวจริงมากก่อน) ก่อนเดินสำรวจ) เพื่อให้ลำน้ำสายหลักที่
  ยาวต่อเนื่องได้เดินเป็น "เส้นตรง" ก่อน ส่วนสาขา/เส้นเชื่อมย่อยที่เดินสำรวจไปเจอ node ที่ถูกกำหนดตำแหน่งไปแล้ว
  (back-edge ของ spanning tree เช่น เส้นที่วนกลับมาบรรจบกับสายหลักอีกจุด — ข้อมูลจริงมีวงวนคลองบ้าง) จะวาดด้วยการ
  หักมุมฉาก (elbow) ไปหาตำแหน่งปลายทางที่ถูกกำหนดไว้แล้วโดยไม่ไปรบกวนตำแหน่งของสายหลัก — เป็นเทคนิคเดียวกับการวาง
  ผัง tree/dendrogram ทั่วไปที่ node จะได้ตำแหน่งจากเส้นทางที่ไปถึงก่อนเท่านั้น (ทำให้ทุกเส้นใน spanning tree เป็น
  เส้นตรงท่อนเดียวโดยอัตโนมัติจากวิธีคำนวณ ไม่ต้องเช็คแยกกรณี)

=== ข้อจำกัดที่ทราบ (v4 — รอปรับปรุงรอบถัดไปถ้าจำเป็น) ===
- เส้นเชื่อมที่เป็นวงวนจริง (ไม่ใช่ spanning-tree edge, เช่น สาขาที่แยกแล้ววนกลับมาบรรจบใหม่) ยังต้องหักมุมเพื่อไป
  หาตำแหน่งปลายทางที่ถูกกำหนดไว้แล้ว — เป็นข้อจำกัดที่หลีกเลี่ยงไม่ได้ของการวางผังกราฟที่มีวงวนจริงบนกริดตรง ๆ
  (ตัวเลขจริง: ส่วนใหญ่ของกราฟเป็นต้นไม้อยู่แล้ว มีวงวนจริงเป็นส่วนน้อย)
- ไม่มีการ "compact" พื้นที่ผังให้กระชับที่สุดหรือลด edge crossing (ตามหลัก orthogonal graph drawing เต็มรูปแบบ)
- ยังไม่รวมทิศทางการไหลของน้ำ (ลูกศร) เพราะ DEM/PySheds ยังไม่ได้ทำ (ตกลงไว้แล้วว่าเลื่อนไป incremental รอบถัดไป
  ตาม ADR-002)
- ให้ชุมชนปรับเส้น/ตำแหน่งเพิ่มเติมได้ใน Phase 4 (Interactive Canvas) ถ้าผังอัตโนมัติดูไม่เป็นระเบียบพอในบางจุด
"""
import argparse
import os

import geopandas as gpd
import networkx as nx
import numpy as np

# เส้นทางน้ำขนาด "หลัก" (main, เส้นหนา) เทียบกับ "สาขา" (branch, เส้นบาง) ตาม waterway_tag จริงที่พบในข้อมูล
# (ทั้งจาก mitrearth: major_river/minor_stream และจาก OSM: river/stream/canal/drain) — เป็นการจับคู่ความหมาย
# ของคำ (semantic) ไม่ใช่ threshold ตัวเลขที่ต้องเดา จึงไม่จำเป็นต้องทดสอบ distribution เหมือนพารามิเตอร์อื่น ๆ
# (สอดคล้องกับ type 'main'/'branch' ที่ใช้อยู่แล้วใน Final_Frontend.html ต้นแบบ Phase 4) — ใช้เป็นเกณฑ์เลือกลำดับ
# เดินสำรวจกราฟด้วย (เดินสาย 'main' ก่อนเสมอที่จุดแยก เพื่อให้สายหลักเดินเป็นเส้นตรงต่อเนื่อง)
MAIN_WATERWAY_TAGS = {"river", "major_river"}


def classify_waterway_size(waterway_tag):
    """คืนค่า 'main' หรือ 'branch' ตาม waterway_tag จริง (ไม่ fabricate ค่าเมื่อไม่มีข้อมูล -> ถือเป็น branch)"""
    if waterway_tag in MAIN_WATERWAY_TAGS:
        return "main"
    return "branch"


def _node_xy(nodes_gdf):
    return {row.node_id: (row.geometry.x, row.geometry.y) for row in nodes_gdf.itertuples()}


def classify_edge_direction(ux, uy, vx, vy):
    """คืน (axis, step) จากพิกัดจริงของปลายทั้งสอง — axis 'h'/'v' ตามที่ |dx| หรือ |dy| มากกว่ากัน,
    step = ทิศ(+1/-1) — ใช้ตัดสินทั้งการ snap ทิศและสืบทอดพิกัดต่อ (ดูหัวไฟล์)"""
    dx, dy = vx - ux, vy - uy
    if abs(dx) >= abs(dy):
        return "h", (1 if dx >= 0 else -1)
    return "v", (1 if dy >= 0 else -1)


def build_adjacency(nodes_gdf, edges_gdf):
    """สร้าง adjacency list {node_id: [(neighbor_id, edge_row), ...]} จาก edges_gdf (ข้าม self-loop เพราะ
    self-loop ไม่มีผลต่อการเดินสำรวจ/ตำแหน่ง — จัดการแยกตอน render เป็นเส้นความยาวศูนย์ตามธรรมชาติ)"""
    adjacency = {n: [] for n in nodes_gdf.node_id}
    for row in edges_gdf.itertuples():
        if row.u == row.v:
            continue
        adjacency[row.u].append((row.v, row))
        adjacency[row.v].append((row.u, row))
    return adjacency


def _pick_component_root(nodes_gdf, comp_node_ids):
    """เลือก node ที่มีพิกัดจริง Y มากที่สุด (อยู่ทางเหนือสุด) เป็นจุดเริ่มเดินสำรวจ เพราะบริบทจริงคือน้ำไหลเข้า
    ตำบลนี้จากทางเหนือลงใต้ (Ton ยืนยัน) — ทำให้ผังที่ได้เริ่มจากด้านบนลงล่างสอดคล้องกับสัญชาตญาณผังน้ำจริง"""
    xy = _node_xy(nodes_gdf)
    return max(comp_node_ids, key=lambda n: xy[n][1])


def compute_schematic_layout(nodes_gdf, edges_gdf):
    """คำนวณตำแหน่งใหม่ (schematic_x, schematic_y) ต่อ node_id ด้วยการเดินสำรวจกราฟ (DFS) แบบ spanning-tree
    position propagation ทีละ connected component (ดูหัวไฟล์สำหรับเหตุผล/อัลกอริทึมเต็ม)
    คืน (positions: {node_id: (x,y)}, tree_edge_ids: set, stats: dict)"""
    grid_unit = float(edges_gdf["length_m"].median())
    if not np.isfinite(grid_unit) or grid_unit <= 0:
        grid_unit = 1.0

    xy = _node_xy(nodes_gdf)
    adjacency = build_adjacency(nodes_gdf, edges_gdf)

    G = nx.Graph()
    G.add_nodes_from(nodes_gdf.node_id.tolist())
    for row in edges_gdf.itertuples():
        if row.u != row.v:
            G.add_edge(row.u, row.v)

    positions = {}
    tree_edge_ids = set()
    components = list(nx.connected_components(G))

    for comp_nodes in components:
        comp_node_ids = list(comp_nodes)
        root = _pick_component_root(nodes_gdf, comp_node_ids) if len(comp_node_ids) > 1 else comp_node_ids[0]

        rel_positions = {root: (0.0, 0.0)}
        visited = {root}
        stack = [root]

        while stack:
            u = stack.pop()
            ux, uy = xy[u]
            # เดินสำรวจ 'main' ก่อน แล้วเรียงตามความยาวจริงมากไปน้อย เพื่อให้สายหลักเดินต่อเนื่องเป็นเส้นตรงก่อน
            neighbors = sorted(
                adjacency[u],
                key=lambda nb: (
                    0 if classify_waterway_size(nb[1].waterway_tag) == "main" else 1,
                    -nb[1].length_m,
                ),
            )
            for v, row in neighbors:
                if v in visited:
                    continue
                visited.add(v)
                vx, vy = xy[v]
                axis, sign = classify_edge_direction(ux, uy, vx, vy)
                px, py = rel_positions[u]
                if axis == "v":
                    n_steps = max(1, round(abs(vy - uy) / grid_unit))
                    rel_positions[v] = (px, py + sign * n_steps)
                else:
                    n_steps = max(1, round(abs(vx - ux) / grid_unit))
                    rel_positions[v] = (px + sign * n_steps, py)
                tree_edge_ids.add(row.edge_id)
                stack.append(v)

        cx = float(np.mean([xy[n][0] for n in comp_node_ids]))
        cy = float(np.mean([xy[n][1] for n in comp_node_ids]))
        off_x, off_y = round(cx / grid_unit), round(cy / grid_unit)

        for n in comp_node_ids:
            rx, ry = rel_positions[n]
            positions[n] = ((off_x + rx) * grid_unit, (off_y + ry) * grid_unit)

    stats = {
        "grid_unit_m": grid_unit,
        "n_components": len(components),
        "n_tree_edges": len(tree_edge_ids),
    }
    return positions, tree_edge_ids, stats


def to_geodataframes(nodes_gdf, edges_gdf, positions):
    from shapely.geometry import Point, LineString

    xy = _node_xy(nodes_gdf)

    nodes_out = nodes_gdf.copy()
    nodes_out["schematic_x"] = nodes_out.node_id.map(lambda n: positions[n][0])
    nodes_out["schematic_y"] = nodes_out.node_id.map(lambda n: positions[n][1])
    nodes_out["geometry"] = nodes_out.apply(lambda r: Point(r.schematic_x, r.schematic_y), axis=1)
    nodes_out = gpd.GeoDataFrame(
        nodes_out[["node_id", "degree", "schematic_x", "schematic_y", "geometry"]], crs=None
    )

    edges_out = edges_gdf.copy()
    n_straight = 0
    n_elbow = 0
    n_zero_length = 0

    def _route(row):
        nonlocal n_straight, n_elbow, n_zero_length
        p1 = positions[row.u]
        p2 = positions[row.v]
        if p1 == p2:
            n_zero_length += 1
            return LineString([p1, p2])

        ux, uy = xy[row.u]
        vx, vy = xy[row.v]
        axis, _ = classify_edge_direction(ux, uy, vx, vy)
        bend = (p2[0], p1[1]) if axis == "h" else (p1[0], p2[1])

        if bend == p1 or bend == p2:
            n_straight += 1
            return LineString([p1, p2])
        n_elbow += 1
        return LineString([p1, bend, p2])

    edges_out["waterway_size"] = edges_out.waterway_tag.map(classify_waterway_size)
    edges_out["geometry"] = edges_out.apply(_route, axis=1)
    edges_out = gpd.GeoDataFrame(
        edges_out[
            ["edge_id", "u", "v", "length_m", "source", "waterway_tag", "waterway_size", "name", "geometry"]
        ],
        crs=None,
    )
    route_stats = {"n_straight": n_straight, "n_elbow": n_elbow, "n_zero_length": n_zero_length}
    return nodes_out, edges_out, route_stats


def filter_to_main_trunk(nodes_gdf, edges_gdf):
    """ตัด component ที่ไม่เชื่อมกับ "โครงหลัก" ออกจากดราฟผัง — ตาม feedback ของ Ton (v4): เส้นที่ไม่มี node
    เชื่อมกับโครงข่ายหลักทำให้ผังดูสับสน/รก ให้ตัดออกจากดราฟไปก่อน (ยังไม่ทิ้งข้อมูลจริง — Phase 2 ยัง export
    nodes.geojson/edges.geojson ครบทุก component ไว้ให้ชุมชนตรวจสอบเพิ่มได้ใน Phase 4 อยู่)

    นิยาม "โครงหลัก" = connected component ที่มีจำนวน node มากที่สุด (เดี่ยวไม่ต้องเดา/hardcode ชื่อเส้นใด ๆ —
    ทดสอบกับนครป่าหมากพบว่า component ใหญ่สุดมี 41 node ในขณะที่ component รองลงมามีแค่ 2-6 node เท่านั้น ต่างกัน
    ชัดเจนมาก ไม่กำกวม) คืนค่า (nodes_gdf, edges_gdf) เฉพาะ component หลัก พร้อมจำนวนที่ตัดออกสำหรับรายงาน"""
    import networkx as nx
    G = nx.Graph()
    G.add_nodes_from(nodes_gdf.node_id.tolist())
    for row in edges_gdf.itertuples():
        if row.u != row.v:
            G.add_edge(row.u, row.v)
    components = list(nx.connected_components(G))
    main_comp = max(components, key=len)
    n_dropped_components = len(components) - 1
    n_dropped_nodes = len(nodes_gdf) - len(main_comp)

    nodes_out = nodes_gdf[nodes_gdf.node_id.isin(main_comp)].reset_index(drop=True)
    edges_out = edges_gdf[edges_gdf.u.isin(main_comp) & edges_gdf.v.isin(main_comp)].reset_index(drop=True)
    return nodes_out, edges_out, {"n_dropped_components": n_dropped_components, "n_dropped_nodes": n_dropped_nodes,
                                   "n_kept_nodes": len(main_comp)}


def schematize(phase2_dir, trunk_only=True):
    nodes_gdf = gpd.read_file(os.path.join(phase2_dir, "nodes.geojson"))
    edges_gdf = gpd.read_file(os.path.join(phase2_dir, "edges.geojson"))

    trunk_stats = {}
    if trunk_only:
        nodes_gdf, edges_gdf, trunk_stats = filter_to_main_trunk(nodes_gdf, edges_gdf)

    positions, tree_edge_ids, stats = compute_schematic_layout(nodes_gdf, edges_gdf)
    nodes_out, edges_out, route_stats = to_geodataframes(nodes_gdf, edges_gdf, positions)
    stats.update(route_stats)
    stats.update(trunk_stats)
    return nodes_out, edges_out, stats


def main():
    ap = argparse.ArgumentParser(description="Phase 3: Schematic Transformation (spanning-tree propagation)")
    ap.add_argument("--phase2-dir", required=True, help="โฟลเดอร์ output ของ Phase 2 (มี nodes.geojson, edges.geojson)")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--keep-all-components", action="store_true",
                     help="ไม่ตัด component ที่ไม่เชื่อมกับโครงหลักออก (ค่าเริ่มต้นคือตัดออก ตาม feedback ของ Ton "
                          "รอบ v4 — ใช้ flag นี้เฉพาะตอนต้องการดูข้อมูลดิบทุก component เพื่อ debug)")
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    nodes_out, edges_out, stats = schematize(args.phase2_dir, trunk_only=not args.keep_all_components)

    nodes_path = os.path.join(args.out_dir, "nodes_schematic.geojson")
    edges_path = os.path.join(args.out_dir, "edges_schematic.geojson")
    nodes_out.to_file(nodes_path, driver="GeoJSON")
    edges_out.to_file(edges_path, driver="GeoJSON")

    print("=== Phase 3: Schematic Transformation (v4 — spanning-tree propagation) ===")
    if "n_dropped_components" in stats:
        print(f"ตัด component ที่ไม่เชื่อมกับโครงหลักออกจากดราฟ: {stats['n_dropped_components']} component "
              f"({stats['n_dropped_nodes']} node) เหลือโครงหลัก {stats['n_kept_nodes']} node "
              f"(ข้อมูลเต็มยังอยู่ครบใน Phase 2 output — ใช้ --keep-all-components เพื่อดูทั้งหมด)")
    print(f"หน่วยกริด (จากค่ามัธยฐานความยาวเส้นจริง): {stats['grid_unit_m']:.1f} เมตร")
    print(f"connected component: {stats['n_components']}")
    print(f"เส้นใน spanning tree (ตรงโดยอัตโนมัติ): {stats['n_tree_edges']}")
    print(f"เส้นตรงท่อนเดียว (รวม tree edges ทั้งหมด + back-edge ที่บังเอิญตรงอยู่แล้ว): {stats['n_straight']}")
    print(f"เส้นหักมุมฉาก 1 ครั้ง (back-edge ของวงวนจริง): {stats['n_elbow']}")
    print(f"เส้นความยาวศูนย์ (self-loop จริงเท่านั้น): {stats['n_zero_length']}")
    print(f"บันทึกที่: {nodes_path}, {edges_path}")


if __name__ == "__main__":
    main()
