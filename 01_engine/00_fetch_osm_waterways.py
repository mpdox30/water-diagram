"""
06_web_platform/01_engine/00_fetch_osm_waterways.py

ขั้นตอน "Fetch" ตาม ADR-003 — ดึงเส้นทางน้ำจาก OpenStreetMap (ผ่าน Overpass API) สำหรับตำบลที่ระบุ (ใช้ขอบเขต
จาก admin_boundary/THA_Tambon.shp ซึ่ง bundle มาแล้วครบทุกตำบลทั่วประเทศ) แล้วบันทึกเป็น GeoJSON ที่
01_data_ingestion.py (ขั้นตอน "Process") อ่านต่อได้ทันที

**เพิ่มเข้ามาเมื่อ 2026-08-30** เพื่อรองรับฟีเจอร์ "เลือกสร้างผังน้ำตำบลใหม่" จากหน้าเว็บ (ตำบลที่ไม่เคยเตรียม
ไฟล์ OSM ไว้ล่วงหน้ามาก่อน) — ตาม ADR-003 เดิมพบว่า cloud sandbox และเครื่อง Ton (device_bash) เรียก Overpass
API ตรง ๆ ไม่ได้ (บล็อกด้วย allowlist เครือข่ายระดับองค์กร) แต่ **ยังไม่เคยทดสอบว่า Render เรียกได้หรือไม่** —
สคริปต์นี้ถูกเรียกจาก 02_engine_service/main.py (ที่รันบน Render) เมื่อยังไม่มีไฟล์ OSM เตรียมไว้ล่วงหน้า
ถ้า Render เรียก Overpass ไม่ได้เช่นกัน สคริปต์จะ exit ด้วย error ชัดเจน (ไม่ใช่ค้างเงียบ ๆ) ให้ main.py ส่ง
ข้อความแจ้งผู้ใช้ว่าต้องเตรียมไฟล์ OSM ให้ด้วยมือแทน (เหมือนขั้นตอนเดิมที่ทำให้ตำบลนครป่าหมาก)

ใช้ tag waterway เดียวกับที่ตรวจสอบไว้ใน ADR-003 (river/canal/stream/drain) — ไม่ได้เพิ่ม tag ใหม่โดยพลการ
เพื่อให้ผลลัพธ์เทียบเคียงได้กับตัวเลขที่บันทึกไว้ตอนสำรวจ (นครป่าหมาก: 57 เส้น river 17 + canal 26 + stream 2
+ drain 11)
"""

import argparse
import json
import socket
import sys

import geopandas as gpd
import requests
import urllib3.util.connection as _urllib3_cn

# --- แก้ "Network is unreachable" (errno 101) เมื่อเรียก overpass-api.de จาก Render ---
# ยืนยันจาก Render log จริง: การเชื่อมต่อ overpass-api.de ล้มเหลวทันที (ไม่ใช่ timeout) ด้วย
# "[Errno 101] Network is unreachable" — เป็นอาการมาตรฐานของ container ที่ไม่มี IPv6 route
# แต่ DNS ของโดเมนคืนทั้ง A (IPv4) และ AAAA (IPv6) record มาด้วย ทำให้ urllib3 (ที่ requests ใช้
# ข้างใน) พยายามต่อผ่าน IPv6 ก่อนตามลำดับที่ getaddrinfo() คืนมา แล้วล้มเหลวทันทีโดยไม่ retry เป็น
# IPv4 เอง — บังคับให้ resolve เป็น IPv4 (AF_INET) อย่างเดียวเพื่อเลี่ยงปัญหานี้
def _allowed_gai_family_ipv4_only():
    return socket.AF_INET


_urllib3_cn.allowed_gai_family = _allowed_gai_family_ipv4_only

OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

WATERWAY_TAGS = ["river", "canal", "stream", "drain"]


# ดู 01_data_ingestion.py::_normalize_thai_admin_name — แหล่งข้อมูลชื่อตำบล/อำเภอที่ต่างกันใส่คำนำหน้าไม่ตรงกัน
# (เช่น "ตำบลนครป่าหมาก" ในตาราง tambons ของ Supabase vs "นครป่าหมาก" ล้วน ๆ ใน THA_Tambon.dbf) จึงตัดคำนำหน้า
# ออกก่อนเทียบเสมอ ทำซ้ำ logic เดียวกันไว้ที่นี่ (ไฟล์นี้เป็น standalone CLI script แยกจาก 01_data_ingestion.py)
_THAI_ADMIN_PREFIXES = ["ตำบล", "ต.", "แขวง", "อำเภอ", "อ.", "เขต"]


def _normalize_thai_admin_name(name: str) -> str:
    name = (name or "").strip()
    for prefix in _THAI_ADMIN_PREFIXES:
        if name.startswith(prefix):
            return name[len(prefix):].strip()
    return name


def _sql_escape(s: str) -> str:
    return s.replace("'", "''")


def get_tambon_bbox_wgs84(data_raw_dir: str, province_th: str, amphoe_th: str, tambon_th: str, buffer_m: float):
    """คืนค่า (south, west, north, east) ของขอบเขตตำบล+buffer แปลงเป็น EPSG:4326 (lat/lon) สำหรับ query Overpass
    ใช้ where= (pushdown filter ระดับ GDAL/OGR) แทนการโหลดทั้งไฟล์แล้วกรองด้วย pandas — กัน OOM บน container
    RAM น้อย (ดูรายละเอียดใน 01_data_ingestion.py::load_tambon_boundary ที่เจอปัญหานี้จริงบน Render free tier)"""
    tambon_shp = f"{data_raw_dir}/admin_boundary/THA_Tambon.shp"
    norm_province, norm_amphoe, norm_tambon = (
        _normalize_thai_admin_name(province_th),
        _normalize_thai_admin_name(amphoe_th),
        _normalize_thai_admin_name(tambon_th),
    )
    where_clause = (
        f"P_NAME_T = '{_sql_escape(norm_province)}' AND A_NAME_T = '{_sql_escape(norm_amphoe)}' "
        f"AND T_NAME_T = '{_sql_escape(norm_tambon)}'"
    )
    match = gpd.read_file(tambon_shp, where=where_clause)
    if len(match) == 0:
        raise ValueError(f"ไม่พบตำบล '{tambon_th}' อำเภอ '{amphoe_th}' จังหวัด '{province_th}' ใน THA_Tambon.shp "
                          f"— ตรวจสอบว่าสะกดชื่อตรงกับที่อยู่ในชุดข้อมูลขอบเขตทางการหรือไม่")
    geom = match.iloc[0].geometry
    boundary = gpd.GeoSeries([geom], crs=match.crs).buffer(buffer_m)
    minx, miny, maxx, maxy = boundary.to_crs("EPSG:4326").total_bounds
    return miny, minx, maxy, maxx  # south, west, north, east


def build_overpass_query(bbox):
    south, west, north, east = bbox
    tag_regex = "|".join(WATERWAY_TAGS)
    return f"""
    [out:json][timeout:60];
    (
      way["waterway"~"^({tag_regex})$"]({south},{west},{north},{east});
    );
    out geom;
    """


def fetch_overpass(query: str):
    errors = []
    for endpoint in OVERPASS_ENDPOINTS:
        resp = None
        try:
            resp = requests.post(endpoint, data={"data": query}, timeout=90)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:  # noqa: BLE001 — ตั้งใจดักทุก error เพื่อลอง endpoint ถัดไป
            body_snippet = ""
            if resp is not None:
                try:
                    body_snippet = resp.text[:500].replace("\n", " ")
                except Exception:
                    pass
            detail = f"{endpoint} -> {e}" + (f" | response body (500 ตัวอักษรแรก): {body_snippet}" if body_snippet else "")
            print(f"[fetch_overpass] endpoint นี้ล้มเหลว: {detail}", file=sys.stderr)
            errors.append(detail)
            continue
    raise RuntimeError(
        f"เรียก Overpass API ไม่สำเร็จทั้ง {len(OVERPASS_ENDPOINTS)} endpoint ที่ลอง:\n" + "\n".join(errors)
    )


def overpass_to_geojson(overpass_json: dict) -> dict:
    features = []
    for el in overpass_json.get("elements", []):
        if el.get("type") != "way" or "geometry" not in el:
            continue
        coords = [[pt["lon"], pt["lat"]] for pt in el["geometry"]]
        if len(coords) < 2:
            continue
        features.append({
            "type": "Feature",
            "properties": {"waterway": el.get("tags", {}).get("waterway"), "osm_id": el.get("id")},
            "geometry": {"type": "LineString", "coordinates": coords},
        })
    return {"type": "FeatureCollection", "features": features}


def main():
    ap = argparse.ArgumentParser(description="ดึงเส้นทางน้ำจาก OSM (Overpass API) สำหรับตำบลที่ระบุ")
    ap.add_argument("--data-raw-dir", required=True)
    ap.add_argument("--province", required=True)
    ap.add_argument("--amphoe", required=True)
    ap.add_argument("--tambon", required=True)
    ap.add_argument("--out-geojson", required=True)
    ap.add_argument("--buffer-m", type=float, default=300.0)
    args = ap.parse_args()

    bbox = get_tambon_bbox_wgs84(args.data_raw_dir, args.province, args.amphoe, args.tambon, args.buffer_m)
    query = build_overpass_query(bbox)
    overpass_json = fetch_overpass(query)
    geojson = overpass_to_geojson(overpass_json)

    n = len(geojson["features"])
    if n == 0:
        print(f"⚠️  Overpass คืนเส้นทางน้ำ 0 เส้นสำหรับตำบล '{args.tambon}' — อาจเป็นเพราะพื้นที่นี้ OSM ยังสำรวจไม่"
              f"ครอบคลุม (ไม่ใช่ error แต่ผลลัพธ์ diagram จะว่างเปล่า)", file=sys.stderr)

    with open(args.out_geojson, "w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False)

    print(f"บันทึก {n} เส้นทางน้ำจาก OSM ไปที่ {args.out_geojson}")


if __name__ == "__main__":
    main()
