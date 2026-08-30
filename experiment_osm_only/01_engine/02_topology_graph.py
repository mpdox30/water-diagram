"""
06_web_platform/01_engine/02_topology_graph.py

เอนจินใหม่ (ตาม ADR-002) — Phase 2: Topology Snapping + Graph Construction
==========================================================================
เขียนใหม่ทั้งหมด (ไม่นำโค้ดจาก ARCHIVE_pilot_v1_offline_pipeline/04_scripts/ มาใช้) รับผลลัพธ์จาก Phase 1
(waterway_lines_raw.geojson — เส้นทางน้ำผสาน OSM หลัก + mitrearth เติมเฉพาะที่ขาด ตาม ADR-003) มาสร้างเป็น
กราฟโครงข่าย (NetworkX) สำหรับขั้นตอนถัดไป (Phase 3: Schematic Transformation) — **ไม่มีการ hardcode ชื่อ
เฉพาะตำบล/เส้นทางน้ำใด ๆ ในไฟล์นี้เลย** ใช้ได้กับผลลัพธ์ Phase 1 ของตำบลใดก็ได้

วิธีการ (2 ขั้นตอนหลัก):

1. **Noding (แบ่งเส้นที่จุดตัดจริง)**: ใช้ `shapely.ops.unary_union()` กับเส้นทั้งหมดพร้อมกัน — เป็นเทคนิค
   มาตรฐานของ GIS ที่ทำให้ทุกจุดที่เส้น 2 เส้นตัด/สัมผัสกันจริง (ไม่ว่าจะเป็นจุดปลายเส้นหรือกลางเส้น) กลายเป็น
   จุดร่วม (node) โดยอัตโนมัติ ผลลัพธ์คือชุดเส้นย่อย ("piece") ที่ไม่มีจุดตัดกลางเส้นเหลืออยู่แล้ว — จากนั้นโอน
   attribute (source/waterway_tag/name) จากเส้นต้นฉบับกลับมาใส่แต่ละ piece (จับคู่ด้วยตำแหน่งจุดกึ่งกลาง piece
   ว่าอยู่บนเส้นต้นฉบับเส้นไหน)

2. **Endpoint snapping (เชื่อมจุดปลายที่ใกล้กันแต่ไม่ทับกันพอดี)**: เนื่องจากข้อมูลมาจาก 2 แหล่ง (OSM + mitrearth)
   ที่ทำแผนที่/digitize แยกกันคนละครั้ง จุดที่ควรเป็นจุดบรรจบเดียวกันจริงอาจไม่ตรงกันเป๊ะ (คลาดเคลื่อนไม่กี่เมตร
   ถึงหลายสิบเมตร) — ทดสอบกับข้อมูลจริงของนครป่าหมากพบว่าระยะห่างระหว่างจุดปลายที่ "ควรเป็นจุดเดียวกัน" อยู่ในช่วง
   0.3-33.8 เมตรทั้งหมด (8 คู่) ส่วนจุดปลายอื่นที่ห่างมากกว่านั้นกระโดดไปที่ 149 เมตรขึ้นไปทันที (คือจุดปลายตัน
   จริงของโครงข่าย ไม่ควรเชื่อมมั่ว) — ช่องว่างนี้ชัดเจนมาก จึงเลือกค่า SNAP_TOLERANCE_M = 35.0 (ครอบคลุมทุกคู่ที่
   ควรเชื่อม ไม่แตะกลุ่มที่ควรแยก) ถ้าทดสอบตำบลอื่นแล้วไม่มีช่องว่างชัดเจนแบบนี้ ต้องดูข้อมูลจริงแล้วปรับค่าใหม่
   ไม่ใช่ตรึงไว้ตายตัว — ใช้ union-find บนคู่จุดปลายที่ห่างกันไม่เกิน SNAP_TOLERANCE_M รวมกลุ่มจุดที่ควรเป็น node
   เดียวกัน แล้วใช้จุดศูนย์กลาง (centroid) ของกลุ่มเป็นตำแหน่ง node สุดท้าย

จุดปลายที่ไม่ถูกเชื่อมกับอะไรเลย (ห่างมากกว่า SNAP_TOLERANCE_M จากจุดปลายอื่นทั้งหมด) จะเป็น "จุดปลายตัน" ในกราฟ
ตามธรรมชาติ — อาจหมายถึงต้นน้ำจริง หรือข้อมูลขาดหายที่ต้องให้ชุมชนตรวจสอบเพิ่มใน Phase 4 (Human-in-the-Loop) ไม่ใช่
สิ่งที่เอนจินควรเดา/เชื่อมเอาเอง

**ขั้นตอนที่ 3 (เพิ่มหลังทดสอบจริง): ยุบ node ทางผ่าน (simplify_topology)** — พบว่าข้อมูล mitrearth minor stream
ต้นฉบับถูกแบ่งเป็น record ย่อยระดับไม่กี่เมตรต่อเส้นอยู่แล้ว (ไม่ใช่บั๊ก เป็นลักษณะข้อมูลต้นทาง) ทำให้กราฟดิบจาก
ขั้นตอน noding มี node/edge เยอะเกินจำเป็นมาก (เช่น นครป่าหมาก: 111 เส้นต้นฉบับ -> 1482 piece หลัง noding) จึงเพิ่ม
ขั้นตอนยุบ node ที่ degree เท่ากับ 2 พอดี (จุดผ่านธรรมดา ไม่ใช่จุดแยก/จุดปลายตัน) ให้เหลือเฉพาะ node ที่มีความหมาย
จริงในกราฟ — ยุบเฉพาะกรณีที่ทั้ง 2 เส้นที่ต่อกันมาจาก source/waterway_tag/name เดียวกันเท่านั้น เพื่อไม่ให้เผลอ
ยุบข้ามขอบเขตข้อมูลที่ต่างกัน (เช่น จุดต่อระหว่าง OSM กับ mitrearth supplement ยังคงเป็น node เสมอ)

หมายเหตุ: Phase นี้ยังไม่แตะ DEM/PySheds (ทิศทางการไหลของน้ำ) ตามแนวทาง incremental ที่ตกลงไว้ใน ADR-002 —
กราฟที่ได้ยังเป็น undirected (ไม่ทราบทิศทางการไหล) จะเพิ่มทิศทางในขั้นตอนถัดไป
"""
import argparse
import os

import geopandas as gpd
import networkx as nx
import numpy as np
from scipy.spatial import cKDTree
from shapely.geometry import Point
from shapely.ops import unary_union
from shapely.strtree import STRtree

# ดูเหตุผลของค่านี้ในหัวไฟล์ (ทดสอบจริงกับนครป่าหมาก: ช่องว่างชัดเจนระหว่าง 33.8m กับ 149m)
SNAP_TOLERANCE_M = 35.0


def node_lines(lines_gdf: gpd.GeoDataFrame):
    """ขั้นตอน 1: ใช้ unary_union แบ่งเส้นทุกเส้นที่จุดตัด/สัมผัสกันจริง แล้วโอน attribute จากเส้นต้นฉบับกลับมา
    คืนค่าเป็น GeoDataFrame ของ piece ที่มี attribute ครบ (source, waterway_tag, name)"""
    geoms = list(lines_gdf.geometry)
    merged = unary_union(geoms)
    pieces = list(merged.geoms) if merged.geom_type == "MultiLineString" else [merged]

    # สร้าง spatial index ของเส้นต้นฉบับ เพื่อจับคู่ piece กลับไปยังเส้นต้นฉบับที่มันเป็นส่วนหนึ่งอยู่
    orig_geoms = list(lines_gdf.geometry)
    tree = STRtree(orig_geoms)

    rows = []
    for piece in pieces:
        if piece.length == 0:
            continue
        mid = piece.interpolate(0.5, normalized=True)
        candidate_idx = tree.query(mid.buffer(1.0))
        best_idx, best_dist = None, None
        for i in candidate_idx:
            d = orig_geoms[i].distance(mid)
            if best_dist is None or d < best_dist:
                best_idx, best_dist = i, d
        if best_idx is None or best_dist > 1.0:
            # ไม่ควรเกิดขึ้น (piece มาจากเส้นต้นฉบับเสมอ) — ถ้าเกิดขึ้นจริงให้ flag ไว้ตรวจสอบ แทนการเดา attribute
            rows.append({"geometry": piece, "source": "unknown_split_error", "waterway_tag": None, "name": None})
            continue
        orig_row = lines_gdf.iloc[best_idx]
        rows.append({
            "geometry": piece,
            "source": orig_row.get("source"),
            "waterway_tag": orig_row.get("waterway_tag"),
            "name": orig_row.get("name"),
        })

    return gpd.GeoDataFrame(rows, geometry="geometry", crs=lines_gdf.crs)


def _union_find_find(parent: dict, x):
    while parent[x] != x:
        parent[x] = parent[parent[x]]
        x = parent[x]
    return x


def _union_find_union(parent: dict, a, b):
    ra, rb = _union_find_find(parent, a), _union_find_find(parent, b)
    if ra != rb:
        parent[ra] = rb


def snap_endpoints(pieces_gdf: gpd.GeoDataFrame, tolerance_m: float = SNAP_TOLERANCE_M):
    """ขั้นตอน 2: จับกลุ่มจุดปลายเส้นที่ห่างกันไม่เกิน tolerance_m ให้เป็น node เดียวกัน (union-find) คืนค่า
    (node_positions: dict[node_id -> (x,y)], edge_records: list of dict พร้อม u/v node_id)"""
    endpoints = []
    piece_endpoint_idx = []  # (piece_i, 'start'|'end') -> index in endpoints list
    for i, geom in enumerate(pieces_gdf.geometry):
        coords = list(geom.coords)
        endpoints.append(coords[0])
        piece_endpoint_idx.append((i, "start"))
        endpoints.append(coords[-1])
        piece_endpoint_idx.append((i, "end"))

    endpoints_arr = np.array(endpoints)
    n = len(endpoints_arr)
    parent = {i: i for i in range(n)}

    tree = cKDTree(endpoints_arr)
    pairs = tree.query_pairs(r=tolerance_m)
    for a, b in pairs:
        _union_find_union(parent, a, b)

    # หา representative node สำหรับแต่ละกลุ่ม (centroid ของจุดในกลุ่ม)
    groups = {}
    for i in range(n):
        root = _union_find_find(parent, i)
        groups.setdefault(root, []).append(i)

    node_positions = {}
    endpoint_to_node = {}
    for node_id, (root, members) in enumerate(groups.items()):
        pts = endpoints_arr[members]
        centroid = pts.mean(axis=0)
        node_positions[node_id] = (float(centroid[0]), float(centroid[1]))
        for m in members:
            endpoint_to_node[m] = node_id

    edge_records = []
    for i, geom in enumerate(pieces_gdf.geometry):
        start_idx = 2 * i
        end_idx = 2 * i + 1
        u = endpoint_to_node[start_idx]
        v = endpoint_to_node[end_idx]
        row = pieces_gdf.iloc[i]
        edge_records.append({
            "u": u, "v": v, "geometry": geom, "length_m": geom.length,
            "source": row.get("source"), "waterway_tag": row.get("waterway_tag"), "name": row.get("name"),
        })

    return node_positions, edge_records


def build_graph(node_positions: dict, edge_records: list):
    """สร้าง NetworkX MultiGraph (undirected — ยังไม่ทราบทิศทางการไหล ตาม incremental scope ของ ADR-002)"""
    G = nx.MultiGraph()
    for node_id, (x, y) in node_positions.items():
        G.add_node(node_id, x=x, y=y)
    for i, e in enumerate(edge_records):
        G.add_edge(e["u"], e["v"], key=i, edge_id=i, length_m=e["length_m"], source=e["source"],
                   waterway_tag=e["waterway_tag"], name=e["name"], geometry=e["geometry"])
    return G


DEDUP_HAUSDORFF_M = 50.0  # ดูเหตุผลที่มาของค่านี้ใน docstring ของ drop_duplicate_parallel_edges ด้านล่าง


def drop_duplicate_parallel_edges(G: nx.MultiGraph) -> nx.MultiGraph:
    """ลบเส้นเชื่อมซ้ำ (parallel duplicate edge) ระหว่าง node คู่เดียวกัน ที่จริงแล้วเป็นเส้นทางน้ำเส้นเดียวกัน
    แต่ถูกนับซ้ำเพราะมาจาก 2 แหล่งข้อมูล (OSM + mitrearth supplement) — ค้นพบระหว่างวิเคราะห์ feedback ของ Ton
    (v4 รอบ Phase 3) ว่าคลองสายหลัก (river/major_river) ไม่ออกมาเป็นเส้นเดียวต่อเนื่อง: ตรวจสอบจริงพบว่าที่จุดแยก
    เกือบทุกจุดตลอดสายหลัก มีเส้นเชื่อม 2 เส้นไปยัง node ปลายทางเดียวกัน ทิศทาง(bearing)และความยาวใกล้เคียงกันมาก
    (ต่างกัน <5%) เส้นหนึ่งมาจาก OSM (tag=river) อีกเส้นมาจาก mitrearth supplement (tag=major_river) — สาเหตุคือ
    classify_waterway_sources() ใน 01_data_ingestion.py ตัดสินใจ "เก็บ/ทิ้งทั้งเส้น" จากสัดส่วนความยาวรวมทั้งเส้น
    ที่ทับกับ OSM (เส้นน้ำสายหลัก 2 สายของนครป่าหมากมีอยู่ใน OSM แค่บางช่วง ทำให้ coverage รวมทั้งเส้นต่ำกว่า
    threshold แม้ว่าช่วงที่ทับกับ OSM จริงจะเยอะพอสมควร) เส้น mitrearth ทั้งเส้นเลยถูกเก็บมาด้วย ซ้อนทับเส้น OSM
    เกือบตลอดสาย ทำให้จุดแยกปลอม (degree เกินจริง) เกิดขึ้นถี่ตลอดสายหลัก นี่คือสาเหตุหลักที่คลองโกรงเกรงไม่ออกมา
    เป็นเส้นเดียวต่อเนื่องอย่างที่ควรจะเป็น

    ลองแก้ที่ต้นตอ (ตัด geometry เฉพาะส่วนที่ทับ OSM ออกจากเส้น mitrearth ก่อนเข้า noding) แต่พบว่าทำให้แย่ลง
    (component จาก 12 เป็น 83, dead-end จาก 42 เป็น 178) เพราะจุดตัดตามขอบ buffer ไม่ตรงกับ node ใด ๆ ในกราฟ
    กลายเป็นปลายเส้นลอย — จึงย้ายมาแก้ที่ระดับกราฟแทน (หลัง noding/snap_endpoints เสร็จแล้ว มี node จริงรองรับ
    อยู่ก่อน ปลอดภัยกว่า): สำหรับ node คู่ใดที่มีเส้นเชื่อมมากกว่า 1 เส้นระหว่างกัน ถ้า Hausdorff distance ระหว่าง
    geometry ของเส้นเหล่านั้น <= DEDUP_HAUSDORFF_M (หมายถึงเป็นเส้นทางเดียวกันในทางปฏิบัติ ไม่ใช่คนละเส้นที่บังเอิญ
    ต่อ node เดียวกัน) ให้เก็บไว้เส้นเดียว โดยให้ความสำคัญ OSM ก่อน (ตาม ADR-003: OSM เป็นแหล่งหลัก) ถ้าเป็นแหล่ง
    เดียวกันทั้งคู่ให้เก็บเส้นที่ยาวกว่า (ถือว่าสมบูรณ์กว่า) — ทดสอบกับนครป่าหมากพบ 15 คู่ node ที่ซ้ำแบบนี้
    (ทุกคู่เป็น osm vs mitrearth_supplement, ความยาวต่างกัน <5% ทุกคู่ — ไม่มีกรณีกำกวม)"""
    G = G.copy()
    from collections import defaultdict
    pair_edges = defaultdict(list)
    for u, v, k, d in G.edges(keys=True, data=True):
        if u == v:
            continue
        key = (min(u, v), max(u, v))
        pair_edges[key].append((u, v, k))

    def _priority(uvk):
        u, v, k = uvk
        d = G.edges[u, v, k]
        return (0 if d.get("source") == "osm" else 1, -(d.get("length_m") or 0))

    n_dropped = 0
    for key, edges in pair_edges.items():
        if len(edges) < 2:
            continue
        ordered = sorted(edges, key=_priority)
        kept = []  # list of (geom, source) already kept for this node-pair
        for uvk in ordered:
            u, v, k = uvk
            d = G.edges[u, v, k]
            geom, src = d["geometry"], d.get("source")
            is_dup = False
            for kg, ksrc in kept:
                if src != ksrc:
                    # node คู่เดียวกันเป๊ะ (ผ่าน snap_endpoints มาแล้ว) แต่มาจาก 2 แหล่งต่างกัน — ทดสอบกับข้อมูลจริง
                    # (นครป่าหมาก 18 คู่) พบว่าเป็นเส้นทางเดียวกันทุกคู่ไม่มีข้อยกเว้น (ความยาวต่างกัน <21% เสมอ แม้
                    # ระยะ Hausdorff จะสูงถึง 100 ม.ในเส้นยาว ๆ ก็ตาม เพราะเป็นการสะสมความคลาดเคลื่อนจากการ digitize
                    # คนละครั้งตลอดเส้นทางยาว ไม่ใช่คนละเส้นจริง) — จึงถือว่าคู่ node เดียวกันจากคนละแหล่งคือเส้น
                    # เดียวกันเสมอ ไม่ต้องเช็ค Hausdorff
                    is_dup = True
                else:
                    # แหล่งเดียวกันทั้งคู่ — อาจเป็นคลองขนานจริง (braided channel) จึงเช็คแบบเดิม (Hausdorff ใกล้)
                    if geom.hausdorff_distance(kg) <= DEDUP_HAUSDORFF_M:
                        is_dup = True
                if is_dup:
                    break
            if is_dup:
                G.remove_edge(u, v, key=k)
                n_dropped += 1
            else:
                kept.append((geom, src))
    return G, n_dropped


def _end_closest_to(coords, xy):
    d_start = (coords[0][0] - xy[0]) ** 2 + (coords[0][1] - xy[1]) ** 2
    d_end = (coords[-1][0] - xy[0]) ** 2 + (coords[-1][1] - xy[1]) ** 2
    return "start" if d_start <= d_end else "end"


def _join_linestrings_at_point(geom1, geom2, xy):
    """ต่อ LineString 2 เส้นเข้าด้วยกันที่จุด xy (ใช้ตอนยุบ node ทางผ่านออก) — เรียงทิศทางของแต่ละเส้นให้ปลายที่
    อยู่ใกล้ xy ที่สุดมาต่อกันตรงกลาง"""
    from shapely.geometry import LineString
    c1 = list(geom1.coords)
    c2 = list(geom2.coords)
    if _end_closest_to(c1, xy) == "start":
        c1 = c1[::-1]
    if _end_closest_to(c2, xy) == "end":
        c2 = c2[::-1]
    return LineString(c1 + c2[1:])


def simplify_topology(G: nx.MultiGraph) -> nx.MultiGraph:
    """ยุบ node ที่เป็นแค่ "จุดผ่าน" (degree เท่ากับ 2 พอดี ไม่ใช่จุดแยก/จุดบรรจบ/จุดปลายตันจริง) ให้เหลือแค่
    node ที่เป็นจุดแยกจริง (degree>=3), จุดปลายตัน (degree==1), หรือจุดต่อระหว่างแหล่งข้อมูลที่ต่างกัน — เหตุผล:
    เส้นทางน้ำต้นฉบับ (โดยเฉพาะ mitrearth minor stream) ถูกแบ่งเป็นชิ้นเล็ก ๆ ระดับไม่กี่เมตรต่อ record อยู่แล้วใน
    shapefile ต้นทาง (ไม่ใช่ความผิดพลาดของเอนจิน) ทำให้กราฟดิบมี node/edge เยอะเกินความจำเป็นสำหรับใช้ทำผังสคีมา
    ติก (Phase 3) — ยุบเฉพาะ node ที่ทั้ง 2 เส้นที่ต่อกันมาจาก source/waterway_tag เดียวกันเท่านั้น (ถ้าต่างกันจะ
    ไม่ยุบ เพื่อรักษาขอบเขตการตรวจสอบย้อนกลับไว้ เช่น จุดต่อระหว่าง OSM กับ mitrearth supplement)

    หมายเหตุ (แก้ไข 2 จุดหลัง feedback ของ Ton รอบ v4):
    1) เดิมเงื่อนไขยุบต้องให้ "name" ตรงกันด้วย (นอกเหนือจาก source/waterway_tag) — Ton ทักท้วงว่าการพึ่งพาชื่อ
       เส้นน้ำมีความเสี่ยง (ตำบลใหม่ที่ไม่มีชื่อใน OSM เลยจะพัง) จึงตัดเงื่อนไข name ออก เหลือเช็คเฉพาะ
       source/waterway_tag ซึ่งเป็นข้อเท็จจริงเชิงประเภทข้อมูล ไม่ใช่ชื่อเฉพาะที่อาจไม่มีอยู่
    2) เดิมเช็ค G.degree(n) != 2 ตรง ๆ ซึ่งนับ self-loop เป็น +2 เสมอ (พบ node จริงที่มี self-loop เล็ก ๆ ติดอยู่
       เช่น จุดคดโค้งเล็กที่เกิดจากการ snap ปลายเส้น) ทำให้ degree รายงานเป็น 4 ทั้งที่จริงเป็นจุดผ่านธรรมดา
       (degree 2 ถ้าไม่นับ self-loop) — บล็อกการยุบ node ที่ควรยุบได้ (พบ 11 จุดในนครป่าหมาก กระจายอยู่บนคลอง
       สายหลักด้วย) แก้โดยเช็คจาก "degree ที่ไม่นับ self-loop" แทน แล้ว reattach self-loop เดิมไปไว้ที่ node
       ปลายทางใดปลายทางหนึ่งหลังยุบ (self-loop เป็นแค่ artifact เล็ก ๆ ไม่กระทบทิศทาง/โครงสร้างหลัก)"""
    G = G.copy()
    progressed = True
    while progressed:
        progressed = False
        for n in list(G.nodes()):
            if n not in G:
                continue
            all_edges = list(G.edges(n, keys=True, data=True))
            self_loops = [e for e in all_edges if e[0] == e[1]]
            non_loop_edges = [e for e in all_edges if e[0] != e[1]]
            if len(non_loop_edges) != 2:
                continue  # จุดแยกจริง/จุดปลายตัน/multi-edge ซ้ำคู่เดิม (parallel channel) ไม่ยุบ
            (u1, v1, k1, d1), (u2, v2, k2, d2) = non_loop_edges
            other1 = v1 if u1 == n else u1
            other2 = v2 if u2 == n else u2
            if other1 == other2:
                continue  # ทั้ง 2 เส้นไปยัง node เดียวกัน (loop คู่ขนาน) ไม่ยุบ กันสร้างโครงสร้างกราฟผิดเพี้ยน
            if d1.get("source") != d2.get("source") or d1.get("waterway_tag") != d2.get("waterway_tag"):
                continue  # คนละแหล่ง/ประเภท — เก็บ node นี้ไว้เป็นจุดแบ่งเขตข้อมูลเพื่อตรวจสอบย้อนกลับได้
            xy = (G.nodes[n]["x"], G.nodes[n]["y"])
            merged_geom = _join_linestrings_at_point(d1["geometry"], d2["geometry"], xy)
            merged_name = d1.get("name") if d1.get("name") == d2.get("name") else (d1.get("name") or d2.get("name"))
            for sl_u, sl_v, sl_k, sl_d in self_loops:
                G.remove_edge(sl_u, sl_v, key=sl_k)
            G.remove_node(n)
            G.add_edge(other1, other2, edge_id=min(d1["edge_id"], d2["edge_id"]),
                       length_m=d1["length_m"] + d2["length_m"], source=d1["source"],
                       waterway_tag=d1["waterway_tag"], name=merged_name, geometry=merged_geom)
            for sl_u, sl_v, sl_k, sl_d in self_loops:
                G.add_edge(other1, other1, edge_id=sl_d["edge_id"], length_m=sl_d["length_m"],
                           source=sl_d["source"], waterway_tag=sl_d["waterway_tag"], name=sl_d.get("name"),
                           geometry=sl_d["geometry"])
            progressed = True
            break
    return G


def to_geodataframes(G: nx.MultiGraph, crs):
    """แปลงกราฟ (อ่าน edge attribute จากตัวกราฟ G โดยตรง — ใช้ได้ทั้งก่อน/หลัง simplify_topology) กลับเป็น
    GeoDataFrame 2 ชุด (nodes, edges) สำหรับ export/visualize"""
    node_rows = []
    for node_id, data in G.nodes(data=True):
        node_rows.append({
            "node_id": node_id, "degree": G.degree(node_id),
            "geometry": Point(data["x"], data["y"]),
        })
    nodes_gdf = gpd.GeoDataFrame(node_rows, geometry="geometry", crs=crs)

    edge_rows = []
    for new_id, (u, v, data) in enumerate(G.edges(data=True)):
        edge_rows.append({
            "edge_id": new_id, "u": u, "v": v, "length_m": data.get("length_m"),
            "source": data.get("source"), "waterway_tag": data.get("waterway_tag"), "name": data.get("name"),
            "geometry": data.get("geometry"),
        })
    edges_gdf = gpd.GeoDataFrame(edge_rows, geometry="geometry", crs=crs)
    return nodes_gdf, edges_gdf


def _sanitize_for_graphml(G: nx.MultiGraph) -> nx.MultiGraph:
    """GraphML ไม่รองรับค่า None เป็น attribute (เช่น name ที่ไม่มีชื่อเส้นทางน้ำ) และไม่รองรับ object ที่ไม่ใช่
    ชนิดข้อมูลพื้นฐาน (เช่น shapely geometry) — ทำสำเนากราฟ ตัด attribute "geometry" ออก (เก็บ geometry เต็มไว้ใน
    edges.geojson/nodes.geojson แยกต่างหากอยู่แล้ว .graphml มีไว้สำหรับโครงสร้างกราฟล้วน ๆ) แล้วแทนที่ None ด้วย
    "" เฉพาะตอน export เท่านั้น (กราฟที่ใช้งานจริงในเอนจินยังคงเก็บ None/geometry ตามปกติ)"""
    H = G.copy()
    for _, data in H.nodes(data=True):
        data.pop("geometry", None)
        for k, v in list(data.items()):
            if v is None:
                data[k] = ""
    for _, _, data in H.edges(data=True):
        data.pop("geometry", None)
        for k, v in list(data.items()):
            if v is None:
                data[k] = ""
    return H


def build_topology(waterway_lines_path: str, snap_tolerance_m: float = SNAP_TOLERANCE_M):
    """ขั้นตอนหลักรวม: โหลดเส้นทางน้ำที่ผสานแล้วจาก Phase 1 -> node (unary_union) -> snap endpoints ที่ใกล้กัน
    -> สร้างกราฟดิบ -> ตัดเส้นซ้ำระหว่าง 2 แหล่งข้อมูล (drop_duplicate_parallel_edges) -> ยุบ node ทางผ่าน
    (simplify_topology) -> คืนค่า (G_raw, G, nodes_gdf, edges_gdf, n_dedup_dropped) โดย G_raw คือกราฟก่อนยุบ/ก่อน
    ตัดซ้ำ (ไว้เทียบขนาด/debug), G คือกราฟสุดท้ายที่ตัดซ้ำ+ยุบแล้ว (ใช้ต่อ Phase 3)"""
    lines_gdf = gpd.read_file(waterway_lines_path)
    pieces_gdf = node_lines(lines_gdf)
    node_positions, edge_records = snap_endpoints(pieces_gdf, snap_tolerance_m)
    G_raw = build_graph(node_positions, edge_records)
    G_dedup, n_dedup_dropped = drop_duplicate_parallel_edges(G_raw)
    G = simplify_topology(G_dedup)
    nodes_gdf, edges_gdf = to_geodataframes(G, lines_gdf.crs)
    return G_raw, G, nodes_gdf, edges_gdf, n_dedup_dropped


def main():
    ap = argparse.ArgumentParser(description="Phase 2 (Topology Snapping + Graph Construction) ของเอนจินใหม่ — "
                                              "รับผลลัพธ์ Phase 1 (waterway_lines_raw.geojson) มาสร้างกราฟ "
                                              "NetworkX (generic ทุกตำบล ไม่ hardcode)")
    ap.add_argument("--phase1-dir", required=True, help="โฟลเดอร์ผลลัพธ์ Phase 1 (มี waterway_lines_raw.geojson)")
    ap.add_argument("--snap-tolerance-m", type=float, default=SNAP_TOLERANCE_M,
                     help=f"ระยะเชื่อมจุดปลายเส้น (เมตร) ดูที่มาในหัวไฟล์ (ค่าเริ่มต้น {SNAP_TOLERANCE_M})")
    ap.add_argument("--out-dir", required=True, help="โฟลเดอร์สำหรับบันทึกผลลัพธ์ (nodes.geojson, edges.geojson)")
    args = ap.parse_args()

    waterway_path = os.path.join(args.phase1_dir, "waterway_lines_raw.geojson")
    G_raw, G, nodes_gdf, edges_gdf, n_dedup_dropped = build_topology(waterway_path, args.snap_tolerance_m)

    os.makedirs(args.out_dir, exist_ok=True)
    nodes_gdf.to_file(os.path.join(args.out_dir, "nodes.geojson"), driver="GeoJSON")
    edges_gdf.to_file(os.path.join(args.out_dir, "edges.geojson"), driver="GeoJSON")
    nx.write_graphml(_sanitize_for_graphml(G), os.path.join(args.out_dir, "topology_graph.graphml"))

    print(f"ก่อนยุบ node ทางผ่าน: {G_raw.number_of_nodes()} โหนด, {G_raw.number_of_edges()} เส้นเชื่อม "
          f"(กระจัดกระจายเพราะ mitrearth minor stream ถูกแบ่งเป็น record ย่อยระดับไม่กี่เมตรในข้อมูลต้นฉบับ)")
    print(f"ตัดเส้นซ้ำระหว่าง OSM/mitrearth ทิ้ง (เส้นทางเดียวกัน มาจาก 2 แหล่ง): {n_dedup_dropped} เส้น")
    components = sorted(nx.connected_components(G), key=len, reverse=True)
    print(f"หลังยุบ node ทางผ่าน (simplify_topology): {G.number_of_nodes()} โหนด  {G.number_of_edges()} เส้นเชื่อม")
    print(f"จำนวน connected component: {len(components)}")
    for i, comp in enumerate(components[:10]):
        n_osm = sum(1 for u, v, d in G.edges(comp, data=True) if d.get("source") == "osm")
        n_supp = sum(1 for u, v, d in G.edges(comp, data=True) if d.get("source") == "mitrearth_supplement")
        print(f"  component #{i+1}: {len(comp)} โหนด, OSM edges~{n_osm}, mitrearth-supplement edges~{n_supp}")
    if len(components) > 10:
        print(f"  ... อีก {len(components) - 10} component ย่อย (ส่วนใหญ่น่าจะเป็นจุดปลายตัน/ข้อมูลขาดหายเดี่ยว ๆ)")
    print(f"บันทึกผลลัพธ์ที่: {args.out_dir}")


if __name__ == "__main__":
    main()
