"""
06_web_platform/01_engine/02b_flow_direction.py

เอนจินใหม่ (ตาม ADR-002) — Phase 2b: Flow Direction จาก DEM point-elevation sampling
======================================================================================
**ขอบเขตงาน (Task #24, ตกลงกับ Ton 2026-08-31)**: Ton รายงานว่าทิศทางลูกศรที่แสดงในหน้าเว็บตอนนี้ "มั่วไปหมด" —
สาเหตุคือ Phase 2 (02_topology_graph.py) สร้างกราฟแบบ undirected (ดู docstring ของไฟล์นั้น) ทิศทาง u->v ที่ export
ออกไปเป็นแค่ artifact จากลำดับที่ NetworkX คืน edge มาเฉย ๆ ไม่ใช่ทิศทางการไหลจริง

พิจารณาแล้วเลือก **ไม่ทำ full DEM/PySheds hydrology pipeline** (fill sinks -> flow direction raster -> flow
accumulation -> threshold -> vectorize เครือข่ายใหม่จาก raster ล้วน ๆ ตามแผนเดิมใน
ARCHIVE_pilot_v1_offline_pipeline/00_docs/semi_auto_waterchart_concept.md) เพราะงานนั้นออกแบบไว้สำหรับตอนที่ยัง
ไม่มีเครือข่ายเวกเตอร์จริง (ต้อง "สร้าง" เครือข่ายจาก raster) — แต่ตอนนี้เรามีเครือข่ายเวกเตอร์จริงจาก OSM+mitrearth
อยู่แล้ว (Phase 1-2) โจทย์จริงมีแค่ "หาว่าเส้นที่มีอยู่แล้วควรไหลไปทางไหน" ซึ่งใช้แค่ **การสุ่มตัวอย่างความสูงที่จุด
node ที่มีอยู่แล้ว** (point elevation sampling) ก็พอ ไม่ต้องประมวลผล raster เต็มพื้นที่/ไม่ต้องใช้
PySheds/WhiteboxTools/RichDEM เลย — ความเสี่ยง/ความซับซ้อนต่ำกว่ามาก และ Ton เห็นด้วย ("แขวนไว้ก่อน ยังไม่ตัดทิ้ง"
full pipeline ไว้เป็นทางเลือกอนาคตถ้าผลลัพธ์วิธีนี้ไม่ดีพอ)

วิธีการ:
1. อ่านผลลัพธ์ Phase 2 (nodes.geojson, edges.geojson จาก --phase2-dir)
2. หา bounding box ของ node ทั้งหมด (+ buffer เล็กน้อย) แปลงเป็น EPSG:4326 แล้วเรียก OpenTopography Global DEM
   API (https://portal.opentopography.org/API/globaldem, demtype=COP30 = Copernicus GLO-30 ความละเอียด 30 ม.
   ครอบคลุมทั่วโลกรวมถึงไทยแน่นอน) **ครั้งเดียวต่อการรัน 1 ตำบล** ได้ GeoTIFF กลับมาเป็น bytes ใน memory (ไม่เขียน
   ไฟล์ลง disk เพราะใช้ครั้งเดียวทิ้ง) — API key อ่านจาก env var OPENTOPOGRAPHY_API_KEY (Ton ขอ API key ของตัวเอง
   จาก portal.opentopography.org เอง แล้วต้องไปตั้งเป็น Environment Variable บน Render ด้วย — ไฟล์ .txt ในเครื่อง
   Ton เองใช้ไม่ได้กับ Render โดยตรง)
3. ใช้ rasterio เปิด GeoTIFF จาก memory (MemoryFile) แล้วสุ่มตัวอย่างความสูงที่พิกัด (lon, lat) ของทุก node
4. กำหนดทิศทางเส้นเชื่อมแต่ละเส้น: ถ้าทราบความสูงทั้ง 2 ฝั่งและต่างกันเกิน ELEVATION_TOLERANCE_M ให้ u = node ที่
   สูงกว่า (ต้นน้ำ), v = node ที่ต่ำกว่า (ปลายน้ำ) — สลับ u/v เดิมถ้าจำเป็น ถ้าไม่ทราบความสูงฝั่งใดฝั่งหนึ่ง (DEM
   nodata) หรือต่างกันไม่เกิน tolerance (พื้นที่ราบ/อยู่ในช่วงคลาดเคลื่อนของ DEM เอง) **คง u/v เดิมไว้** — ไม่เดา
   ทิศทาง เท่ากับพฤติกรรมเดิมก่อนมี Phase นี้ ไม่ทำให้แย่ลงกว่าเดิม
5. เขียน nodes.geojson (เพิ่มคอลัมน์ elevation_m) และ edges.geojson (u/v อาจถูกสลับ + เพิ่มคอลัมน์
   flow_elevation_u_m, flow_elevation_v_m, flow_direction_known) ไปที่ --out-dir

**สำคัญ — ทำไมใช้วิธีสลับ u/v แทนการเพิ่มคอลัมน์ flow_u/flow_v แยก**: 03_schematic_layout.py และ
04_export_frontend_data.py (Phase 3-4 เดิม) ใช้ค่า u/v ของแต่ละเส้นตรง ๆ อยู่แล้วเพื่อสร้าง source/target ใน
Cytoscape JSON — 03_schematic_layout.py.to_geodataframes() ยัง subset คอลัมน์ผลลัพธ์ไว้ตายตัว (ไม่รวมคอลัมน์ใหม่ที่
ไม่รู้จัก) ดังนั้นถ้าเพิ่มคอลัมน์ใหม่แยกต่างหากจะถูกตัดทิ้งระหว่างทาง ไม่ไหลต่อไปถึง Phase 4 — การ "สลับค่าที่มีอยู่
แล้วในคอลัมน์ u/v เดิม" จึงทำให้ Phase 3/4 ใช้งานได้ทันทีโดยไม่ต้องแก้โค้ดทั้ง 2 ไฟล์นั้นเลย (สอดคล้องกับแนวทาง
incremental ของ ADR-002 — เพิ่มความสามารถใหม่กระทบโค้ดเดิมให้น้อยที่สุด)

**Graceful degradation**: ถ้ายังไม่ได้ตั้งค่า OPENTOPOGRAPHY_API_KEY หรือเรียก/อ่าน DEM ล้มเหลวไม่ว่าด้วยเหตุผลใด
(เช่น เครือข่าย, rate limit, bbox นอกขอบเขตข้อมูล) — Phase นี้จะ**ไม่ทำให้ pipeline ทั้งหมดล้มเหลว** แค่ print
คำเตือนไปที่ stderr แล้วคัดลอก nodes.geojson/edges.geojson จาก Phase 2 ผ่านไปเฉย ๆ (u/v เดิม เหมือนไม่มี Phase นี้
อยู่เลย) — เพราะฟีเจอร์นี้เป็นการ "ปรับปรุงเสริม" ไม่ใช่ dependency ที่ Phase 3/4 ต้องพึ่งพา
"""
import argparse
import os
import sys

import geopandas as gpd
import requests

OPENTOPOGRAPHY_URL = "https://portal.opentopography.org/API/globaldem"

# ~0.01 องศา ~ 1.1 กม. ที่เส้นศูนย์สูตร — กัน node ที่อยู่ริมขอบ bbox พอดีตกไปอยู่นอกภาพ/ติด nodata ที่ขอบ raster
BBOX_BUFFER_DEG = 0.01

# เหตุผล: ความแม่นยำแนวดิ่ง (vertical accuracy) ของ Copernicus DEM GLO-30 อยู่ราว ๆ ไม่กี่เมตร (LE90) ทั่วโลก
# ตามเอกสารของ Copernicus — ถ้าความสูงของ 2 node ต่างกันน้อยกว่าค่านี้ ถือว่าอยู่ในช่วง noise ของตัว DEM เอง ไม่ใช่
# ความลาดชันจริงที่เชื่อถือได้ จึงไม่ควรใช้ตัดสินทิศทาง (คง u/v เดิมไว้ ปลอดภัยกว่าเดาทิศทางผิดจาก noise ล้วน ๆ)
ELEVATION_TOLERANCE_M = 1.0


def _bbox_wgs84_from_nodes(nodes_gdf: gpd.GeoDataFrame, buffer_deg: float = BBOX_BUFFER_DEG):
    """คืนค่า (south, west, north, east) ครอบคลุม node ทั้งหมดใน nodes_gdf (CRS ใดก็ได้) + buffer_deg องศา
    แปลงเป็น EPSG:4326 เสมอ (bbox ที่ OpenTopography API ต้องการ)"""
    nodes_wgs84 = nodes_gdf.to_crs("EPSG:4326")
    west, south, east, north = nodes_wgs84.total_bounds
    return south - buffer_deg, west - buffer_deg, north + buffer_deg, east + buffer_deg


def fetch_node_elevations(nodes_gdf: gpd.GeoDataFrame, api_key: str, buffer_deg: float = BBOX_BUFFER_DEG) -> dict:
    """เรียก OpenTopography Global DEM API ครั้งเดียว (bbox ครอบคลุมทุก node +buffer) ดึง Copernicus GLO-30 มา
    เป็น GeoTIFF ใน memory แล้วสุ่มตัวอย่างความสูงที่ตำแหน่งแต่ละ node คืนค่า dict[node_id -> float เมตร หรือ None
    ถ้าเป็น nodata/NaN] — raise exception ถ้าเรียก API หรือเปิด/อ่าน GeoTIFF ไม่สำเร็จ (ให้ main() ตัดสินใจ
    fallback เอง ไม่กลืน error เงียบ ๆ ตรงนี้ เหมือน pattern ของ load_mitrearth_from_supabase() ใน
    01_data_ingestion.py)

    import rasterio แบบ local (ไม่ใช่ module-level) เพื่อให้ไฟล์นี้ import/ทดสอบ assign_flow_direction() ได้แม้ใน
    สภาพแวดล้อมที่ยังไม่ได้ลง rasterio (เช่น sandbox ที่ใช้พัฒนา/รัน unit test ส่วน logic ล้วน ๆ)"""
    import rasterio
    from rasterio.io import MemoryFile
    from rasterio.warp import transform as warp_transform

    south, west, north, east = _bbox_wgs84_from_nodes(nodes_gdf, buffer_deg)
    resp = requests.get(
        OPENTOPOGRAPHY_URL,
        params={
            "demtype": "COP30",
            "south": south, "west": west, "north": north, "east": east,
            "outputFormat": "GTiff",
            "API_Key": api_key,
        },
        timeout=60,
    )
    resp.raise_for_status()

    nodes_wgs84 = nodes_gdf.to_crs("EPSG:4326")
    node_ids = list(nodes_wgs84.node_id)
    lons = [geom.x for geom in nodes_wgs84.geometry]
    lats = [geom.y for geom in nodes_wgs84.geometry]

    with MemoryFile(resp.content) as memfile:
        with memfile.open() as dataset:
            if dataset.crs is not None and dataset.crs.to_epsg() != 4326:
                xs, ys = warp_transform("EPSG:4326", dataset.crs, lons, lats)
            else:
                xs, ys = lons, lats
            sampled = list(dataset.sample(list(zip(xs, ys))))
            nodata = dataset.nodata

    elevations = {}
    for node_id, val in zip(node_ids, sampled):
        v = float(val[0])
        if v != v:  # NaN check (v != v เป็นจริงเฉพาะ NaN เท่านั้น)
            elevations[node_id] = None
        elif nodata is not None and v == nodata:
            elevations[node_id] = None
        else:
            elevations[node_id] = v
    return elevations


def assign_flow_direction(edges_gdf: gpd.GeoDataFrame, elevations: dict, tolerance_m: float = ELEVATION_TOLERANCE_M):
    """คืนค่า (edges_out, stats) — edges_out คือสำเนาของ edges_gdf ที่ค่า u/v อาจถูกสลับกัน (u=node สูงกว่า =
    ต้นน้ำ, v=node ต่ำกว่า = ปลายน้ำ) เมื่อทราบความสูงของทั้ง 2 node และต่างกันเกิน tolerance_m — ถ้าไม่ทราบความสูง
    ฝั่งใดฝั่งหนึ่ง (ไม่มีใน elevations หรือเป็น None) หรือต่างกันไม่เกิน tolerance_m จะคง u/v เดิมไว้ทุกประการ (รวม
    self-loop ที่ u==v ซึ่งความสูงเท่ากันเสมอ จะเข้าเงื่อนไข "ต่างกันไม่เกิน tolerance" โดยอัตโนมัติ ไม่ต้องเช็คแยก)

    เพิ่ม 3 คอลัมน์ใหม่ต่อเส้น (ไว้ debug/ตรวจสอบย้อนกลับ — ไม่ได้ถูกใช้โดย Phase 3/4 ปัจจุบัน เพราะ Phase 3 subset
    คอลัมน์ผลลัพธ์ไว้ตายตัว): flow_elevation_u_m, flow_elevation_v_m (ความสูงของ node u/v หลังจัดเรียงแล้ว, None
    ถ้าไม่ทราบ), flow_direction_known (bool — True เฉพาะกรณีที่กำหนดทิศทางได้จริงจากความสูง)"""
    edges_out = edges_gdf.copy()
    new_u, new_v = [], []
    elev_u_col, elev_v_col, known_col = [], [], []
    n_flipped = n_kept_known = n_unknown_missing = n_unknown_flat = 0

    for row in edges_out.itertuples():
        eu, ev = elevations.get(row.u), elevations.get(row.v)
        if eu is None or ev is None:
            new_u.append(row.u); new_v.append(row.v)
            elev_u_col.append(eu); elev_v_col.append(ev)
            known_col.append(False)
            n_unknown_missing += 1
            continue
        if abs(eu - ev) <= tolerance_m:
            new_u.append(row.u); new_v.append(row.v)
            elev_u_col.append(eu); elev_v_col.append(ev)
            known_col.append(False)
            n_unknown_flat += 1
            continue
        if eu >= ev:
            new_u.append(row.u); new_v.append(row.v)
            elev_u_col.append(eu); elev_v_col.append(ev)
            n_kept_known += 1
        else:
            new_u.append(row.v); new_v.append(row.u)
            elev_u_col.append(ev); elev_v_col.append(eu)
            n_flipped += 1
        known_col.append(True)

    edges_out["u"] = new_u
    edges_out["v"] = new_v
    edges_out["flow_elevation_u_m"] = elev_u_col
    edges_out["flow_elevation_v_m"] = elev_v_col
    edges_out["flow_direction_known"] = known_col

    stats = {
        "n_edges": len(edges_out),
        "n_flipped": n_flipped,
        "n_kept_known_order": n_kept_known,
        "n_unknown_missing_elevation": n_unknown_missing,
        "n_unknown_flat_or_within_tolerance": n_unknown_flat,
    }
    return edges_out, stats


def _copy_through_unchanged(nodes_gdf, edges_gdf, out_dir):
    """ใช้เมื่อข้าม flow-direction (ไม่มี API key หรือ DEM ล้มเหลว) — เขียน nodes/edges เดิมออกไปเฉย ๆ ให้ Phase 3
    อ่านต่อได้ตามปกติ เสมือนไม่มี Phase 2b อยู่เลย"""
    nodes_gdf.to_file(os.path.join(out_dir, "nodes.geojson"), driver="GeoJSON")
    edges_gdf.to_file(os.path.join(out_dir, "edges.geojson"), driver="GeoJSON")


def main():
    ap = argparse.ArgumentParser(
        description="Phase 2b (Flow Direction จาก DEM point-elevation sampling) — รับผลลัพธ์ Phase 2 มากำหนด "
                     "ทิศทางการไหลของแต่ละเส้นเชื่อม (u=ต้นน้ำ/สูงกว่า, v=ปลายน้ำ/ต่ำกว่า) ถ้าทำไม่ได้ (ไม่มี "
                     "API key/DEM ล้มเหลว) จะส่งผลลัพธ์ Phase 2 ผ่านไปเฉย ๆ ไม่ทำให้ pipeline ล้มเหลว"
    )
    ap.add_argument("--phase2-dir", required=True, help="โฟลเดอร์ผลลัพธ์ Phase 2 (มี nodes.geojson, edges.geojson)")
    ap.add_argument("--out-dir", required=True, help="โฟลเดอร์สำหรับบันทึกผลลัพธ์ (nodes.geojson, edges.geojson)")
    ap.add_argument("--bbox-buffer-deg", type=float, default=BBOX_BUFFER_DEG)
    ap.add_argument("--elevation-tolerance-m", type=float, default=ELEVATION_TOLERANCE_M)
    args = ap.parse_args()

    nodes_gdf = gpd.read_file(os.path.join(args.phase2_dir, "nodes.geojson"))
    edges_gdf = gpd.read_file(os.path.join(args.phase2_dir, "edges.geojson"))
    os.makedirs(args.out_dir, exist_ok=True)

    api_key = os.environ.get("OPENTOPOGRAPHY_API_KEY", "")
    if not api_key:
        print("⚠️  ยังไม่ได้ตั้งค่า env var OPENTOPOGRAPHY_API_KEY บน Render — ข้าม Phase 2b (คำนวณทิศทางการไหล) "
              "กราฟจะยังคง u/v เดิมจาก Phase 2 (undirected) เหมือนก่อนมี Phase นี้", file=sys.stderr)
        _copy_through_unchanged(nodes_gdf, edges_gdf, args.out_dir)
        return

    try:
        elevations = fetch_node_elevations(nodes_gdf, api_key, args.bbox_buffer_deg)
    except Exception as e:
        print(f"⚠️  ดึง/อ่าน DEM จาก OpenTopography ไม่สำเร็จ ({type(e).__name__}: {e}) — ข้าม Phase 2b (คำนวณ"
              f"ทิศทางการไหล) กราฟจะยังคง u/v เดิมจาก Phase 2 (undirected)", file=sys.stderr)
        _copy_through_unchanged(nodes_gdf, edges_gdf, args.out_dir)
        return

    nodes_out = nodes_gdf.copy()
    nodes_out["elevation_m"] = nodes_out.node_id.map(elevations.get)
    edges_out, stats = assign_flow_direction(edges_gdf, elevations, args.elevation_tolerance_m)

    nodes_out.to_file(os.path.join(args.out_dir, "nodes.geojson"), driver="GeoJSON")
    edges_out.to_file(os.path.join(args.out_dir, "edges.geojson"), driver="GeoJSON")

    n_known_elev = sum(1 for v in elevations.values() if v is not None)
    print(f"สุ่มตัวอย่างความสูงจาก DEM (Copernicus GLO-30 ผ่าน OpenTopography API): {n_known_elev}/{len(nodes_gdf)} "
          f"โหนด")
    print(f"กำหนดทิศทางการไหล: กลับทิศทาง u/v {stats['n_flipped']} เส้น, คงทิศทางเดิม (ทราบความสูง h(u)>=h(v)) "
          f"{stats['n_kept_known_order']} เส้น, ไม่ทราบทิศทาง (ขาดความสูงฝั่งใดฝั่งหนึ่ง) "
          f"{stats['n_unknown_missing_elevation']} เส้น, ไม่ทราบทิศทาง (พื้นที่ราบ/ต่างกันไม่เกิน "
          f"{args.elevation_tolerance_m}m) {stats['n_unknown_flat_or_within_tolerance']} เส้น")


if __name__ == "__main__":
    main()
