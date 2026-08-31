"""
06_web_platform/01_engine/01_data_ingestion.py

เอนจินใหม่ (ตาม ADR-002) — Phase 1: Data Ingestion
==================================================
เขียนใหม่ทั้งหมด ไม่นำโค้ด/อัลกอริทึมจาก ARCHIVE_pilot_v1_offline_pipeline/04_scripts/ มาใช้ (ตามที่ Ton สั่ง
ในรอบ 20) — ใช้เฉพาะ "ข้อมูลดิบ" ชุดเดิมที่ยังถือเป็นข้อมูล ไม่ใช่วิธีการ (ตาม ADR-002 หัวข้อ "สิ่งที่ยังคงไว้ได้")

**อัปเดตตาม ADR-003 (แหล่งข้อมูลเส้นทางน้ำ)**: เดิมไฟล์นี้ใช้ shapefile ระดับจังหวัด (mitrearth) เป็นแหล่ง
เส้นทางน้ำหลัก — Ton ทักท้วงว่าขัดกับ Architecture.html ที่ระบุให้ใช้ HydroRIVERS/OpenStreetMap (OSM) เป็นข้อมูล
เส้นน้ำตั้งต้น ตอนนี้จึงเปลี่ยนเป็น: **OSM เป็นแหล่งหลัก + mitrearth ใช้เติมเฉพาะเส้นทางที่ขาดหายจาก OSM
โดยอัตโนมัติ** (ทุกเส้นที่มาจาก mitrearth จะติด source="mitrearth_supplement" ให้ตรวจสอบย้อนกลับได้ ส่วนที่มา
จาก OSM ติด source="osm") — รายละเอียดเหตุผล/การทดสอบ ดู `06_web_platform/ADR-003_waterway_source_strategy.md`

**ข้อจำกัดสำคัญที่ต้องรู้**: ไฟล์นี้ **ไม่ได้ดึงข้อมูล OSM เองแบบ live** เพราะสภาพแวดล้อมที่รันเอนจิน
(device_bash / cloud sandbox) ถูกบล็อกเครือข่ายไปยัง Overpass API ด้วยนโยบายองค์กร (ตรวจสอบแล้ว: บล็อกจริง
ทั้งสองฝั่ง) — ต้อง**เตรียมไฟล์ GeoJSON ของ OSM ไว้ล่วงหน้า** (พารามิเตอร์ --osm-geojson) โดยดึงผ่านช่องทางอื่นที่
มีอินเทอร์เน็ต (ระหว่างพัฒนา: browser จริงของ Ton ผ่าน Overpass API แล้วดาวน์โหลดไฟล์ลงเครื่อง; ในระบบจริงควรทำ
เป็นขั้นตอนแยกที่รันบน GitHub Actions หรือเครื่องที่มีอินเทอร์เน็ต แล้ว commit ไฟล์ผลลัพธ์เข้าโปรเจกต์) — ไฟล์
GeoJSON ของ OSM ต้องมี geometry เป็น LineString ในระบบพิกัด EPSG:4326 (ค่ามาตรฐานของ OSM/GeoJSON) และควรมี
property "waterway" เก็บ tag เดิมจาก OSM (river/canal/stream/drain ฯลฯ) ไว้ด้วย

หน้าที่ของไฟล์นี้: รับชื่อ (จังหวัด, อำเภอ, ตำบล) + ไฟล์ OSM waterway ที่เตรียมไว้ แล้วรวมกับข้อมูลทางน้ำดิบระดับ
จังหวัด (จาก mitrearth surface water package, ใช้เป็นตัวเติมเสริมเท่านั้น) ที่อยู่ในเขต/รอบขอบเขตตำบลนั้น
ออกมาเป็น GeoDataFrame พร้อมสำหรับขั้นตอนถัดไป (Phase 2: topology graph construction) — **ไม่มีการ hardcode
ชื่อเฉพาะตำบล/เส้นทางน้ำใด ๆ ในไฟล์นี้เลย** ใช้ได้กับทุกตำบลในประเทศไทยที่มีข้อมูล mitrearth อยู่ (ส่วนไฟล์ OSM
ต้องเตรียมแยกทีละตำบลตามข้อจำกัดด้านบน)

**อัปเดต Task #21 (2026-08-31)**: ข้อมูลเสริม mitrearth ตอนนี้ดึงจาก **Supabase** เป็นหลัก (ตาราง
nw.mitrearth_waterways/nw.mitrearth_water_bodies ผ่าน RPC nw_mitrearth_waterways_in_bbox/
nw_mitrearth_water_bodies_in_bbox — นำเข้าครบทั้ง 77 จังหวัดแล้วผ่าน import_mitrearth_all_provinces.py ที่ Ton
รันเองบนเครื่อง) แทนการอ่าน provincial_gis/<n>_<slug>/surface_water/ ในเครื่อง ซึ่งเดิม bundle ไว้ในโปรเจกต์ได้
แค่บางจังหวัดเท่านั้น (ข้อมูลทั้งประเทศใหญ่เกินจะ commit เข้า repo ไหว) — โฟลเดอร์ provincial_gis ในเครื่อง (ที่
อธิบายไว้ด้านล่าง) ตอนนี้เป็นแค่ fallback เผื่อไม่ได้ตั้งค่า SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY หรือเรียก
Supabase ไม่สำเร็จเท่านั้น (ดูฟังก์ชัน load_mitrearth_from_supabase() และ ingest())

ข้อมูลดิบที่ใช้ (ทั้งหมดอยู่ใน ARCHIVE_pilot_v1_offline_pipeline/01_data_raw/ ยกเว้น OSM):
- admin_boundary/THA_Tambon.shp   — ขอบเขตตำบลทั่วประเทศ (CRS: EPSG:32647, มี .prj ถูกต้อง)
- admin_boundary/THA_Province.shp — ใช้จับคู่ชื่อจังหวัด (ภาษาอังกฤษ) กับชื่อโฟลเดอร์ provincial_gis/<n>_<slug>/
- provincial_gis/<n>_<slug>/surface_water/ (ใช้เป็นตัวเติมเสริม/ตรวจสอบเท่านั้น ไม่ใช่แหล่งหลักอีกต่อไป)
    "<n> Major River.shp"   — แม่น้ำสายหลัก (ไม่มี .prj ในไฟล์ที่ตรวจสอบ → พิกัดจริงเป็น lon/lat จึงกำหนด
                              CRS=EPSG:4326 เอง แล้ว reproject เป็น EPSG:32647 ให้ตรงกับขอบเขตตำบล)
    "<n> minor stream.shp"  — คลอง/ลำธารสาขา (เช่นเดียวกัน: ไม่มี .prj, ไม่มี .cpg → encoding เป็น utf-8 จริง
                              แม้ไม่มีไฟล์ .cpg ระบุไว้ก็ตาม ตรวจสอบแล้วด้วยการลองถอดรหัสหลายแบบเทียบชื่อสถานที่
                              จริงที่อ่านออก)
    "<n> water body.shp"    — แหล่งน้ำ/บึง/หนอง (เช่นเดียวกัน: ไม่มี .prj/.cpg → EPSG:4326 + utf-8; ยังใช้เป็น
                              แหล่งหลักของ water body ต่อไป เพราะ ADR-003 ครอบคลุมเฉพาะ "เส้นทางน้ำ")
- 01_data_external/osm/<tambon_slug>_osm_waterways.geojson — เส้นทางน้ำจาก OpenStreetMap (ผ่าน Overpass API)
  ดึงมาล่วงหน้าตามข้อจำกัดด้านบน

หมายเหตุสำคัญเรื่อง encoding: shapefile ระดับจังหวัดชุดนี้ไม่มีไฟล์ .cpg กำกับ (ยกเว้น Major River ที่มี .cpg
ระบุ UTF-8) แต่ทดสอบถอดรหัสจริงแล้วพบว่าทั้ง 3 ไฟล์เป็น UTF-8 จริง (ทดสอบ cp874/tis-620/utf-8 เทียบกับชื่อ
สถานที่จริงที่อ่านออกมาได้ความหมาย) จึงกำหนด encoding="utf-8" ตรง ๆ ในฟังก์ชัน read — ถ้าในอนาคตพบจังหวัดอื่นที่
ใช้ encoding ต่างออกไป (เช่น cp874 จริง ๆ) ต้องปรับ logic ตรงนี้ให้ตรวจสอบอัตโนมัติแทนการ hardcode "utf-8" เสมอ
"""
import argparse
import json
import os
import sys
import unicodedata

import geopandas as gpd
import pandas as pd
import requests
import shapely.geometry

DATA_RAW_ENCODING = "utf-8"  # ดูหมายเหตุ encoding ด้านบน

# Task #21 (2026-08-31): อ่านข้อมูลเสริม mitrearth จาก Supabase (ตาราง nw.mitrearth_waterways/water_bodies ที่
# นำเข้าครบทั้ง 77 จังหวัดแล้ว ผ่าน import_mitrearth_all_provinces.py) แทนการอ่าน shapefile ที่ bundle ไว้ใน
# เครื่อง (ซึ่งมีแค่บางจังหวัด เพราะข้อมูลทั้งประเทศใหญ่เกินจะ commit เข้า repo ได้จริง — ดู ADR-003/ADR-004)
# อ่านค่าจาก env var เดียวกับที่ 02_engine_service/main.py ใช้อยู่แล้ว (subprocess สืบทอด env จาก process แม่
# โดย default จึงเห็นค่าเดียวกันอัตโนมัติเวลารันจริงบน Render) ถ้ายังไม่ตั้งค่าไว้ (เช่น รันทดสอบในเครื่อง dev ที่
# ไม่มี Supabase credential พร้อม) จะ fallback ไปอ่านจากโฟลเดอร์ provincial_gis ในเครื่องแทนโดยอัตโนมัติ (ดู ingest())
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

# ค่าพารามิเตอร์ตรวจจับ "เส้น mitrearth ที่ซ้ำกับ OSM แล้ว" — เลือกจากการทดสอบจริงกับตำบลนำร่อง (นครป่าหมาก):
# ที่ D=30ม./threshold=0.7 ได้ผลแบ่งกลุ่มชัดเจนที่สุด (47 เส้นถือว่า "มีใน OSM แล้ว" คลุมมากกว่า 70% ของความยาว,
# 70 เส้นถือว่า "ขาดหายไป" คลุมน้อยกว่า 20%, เหลือกำกวมกลาง ๆ แค่ 12 เส้นจาก 129) — ดู ADR-003 สำหรับตัวเลขเต็ม
# หากทดสอบกับตำบลอื่นแล้วพบว่าการแบ่งกลุ่มไม่ชัดเจนแบบนี้ ควรปรับค่านี้ใหม่ตามข้อมูลจริง ไม่ใช่ตรึงไว้ตายตัว
OSM_COVERAGE_BUFFER_M = 30.0
OSM_COVERAGE_THRESHOLD = 0.7

# บั๊กที่ Ton รายงาน (2026-08-30): เส้นน้ำจาก mitrearth บางเส้นมีชื่อถูก "ตัดคำ" เช่น "คลองบางกระท" ที่จริง
# ควรเป็น "คลองบางกระทุ่ม" — ตรวจสอบแล้วว่า **ไม่ใช่บั๊กของสคริปต์นี้** แต่เป็นข้อจำกัดของไฟล์ต้นฉบับเอง:
# shapefile "<n> minor stream.shp"/"<n> Major River.shp" ของ mitrearth เก็บชื่อในฟิลด์ DBF ชนิด Character
# ความกว้างคงที่แค่ 35 ไบต์ (ตรวจด้วยการอ่าน field descriptor ของ .dbf โดยตรง — ดูรอบแก้บั๊กนี้) ชื่อไทยยาว ๆ
# ใช้ 3 ไบต์ต่อ 1 ตัวอักษร เช่น "คลองบางกระทุ่ม" ยาว 42 ไบต์ > 35 ไบต์ จึงถูกตัดตั้งแต่ตอนที่ไฟล์ .dbf ถูกสร้าง
# ขึ้นมาครั้งแรก (ก่อนที่โปรเจกต์นี้จะมาอ่านข้อมูลด้วยซ้ำ) — ตรวจสอบตรงกับข้อมูลดิบในไฟล์ .dbf จริงแล้ว: ค่าที่
# เก็บไว้คือ "คลองบางกระท" (11 ตัวอักษร = 33 ไบต์ พอดีกับที่ตัดได้โดยไม่ผ่ากลางตัวอักษร) ไม่มีทางกู้ชื่อเต็มคืน
# จากไฟล์นี้ได้เลย
#
# ทางแก้ที่เลือก: แทนที่จะปล่อยชื่อที่ถูกตัดคำ (ผิด/ไม่ครบ) ออกไปเป็นชื่อเริ่มต้นของเส้นนั้นเงียบ ๆ ให้ตรวจจับ
# กรณีที่ "น่าสงสัยว่าถูกตัดคำ" (ความยาวของชื่อเมื่อเข้ารหัส UTF-8 ชนกับความกว้างฟิลด์เป๊ะ ๆ พอดี ไม่มีช่องว่าง
# เหลือเลย — สัญญาณที่ชัดเจนว่าเนื้อหาที่แท้จริงยาวกว่าฟิลด์รองรับได้) แล้วเคลียร์ชื่อนั้นเป็นค่าว่างแทน ให้เส้น
# ไม่มีชื่อ default (ตรงกับพฤติกรรมเส้นใหม่ที่ผู้ใช้ลากเองในหน้าเว็บ — ไม่แสดงชื่อจนกว่าจะมีคนใส่ชื่อที่ถูกต้อง
# เข้าไปเอง) ดีกว่าแสดงชื่อผิด/ไม่ครบให้ดูเหมือนเป็นข้อมูลที่ถูกต้อง
MITREARTH_NAME_FIELD_MAX_BYTES = 35


def _clean_possibly_truncated_mitrearth_name(name):
    """คืนชื่อเดิมถ้าดูสมบูรณ์ หรือ None ถ้าดูเหมือนถูกตัดคำจากข้อจำกัดฟิลด์ DBF 35 ไบต์ของ mitrearth
    (ดูคำอธิบายที่ MITREARTH_NAME_FIELD_MAX_BYTES ด้านบน)"""
    if not name:
        return name
    name = name.strip()
    if not name:
        return None
    if len(name.encode("utf-8")) >= MITREARTH_NAME_FIELD_MAX_BYTES:
        return None
    return name

# ชื่อโฟลเดอร์ provincial_gis บางจังหวัดสะกดต่างจากชื่อทางการใน THA_Province.P_NAME_E เล็กน้อย (คนละเรื่องกับ
# บั๊ก field-width truncation ที่เจอใน pilot รอบก่อน — นี่คือความต่างของการสะกดชื่อจริง ๆ) พบระหว่างทดสอบรันกับ
# ทั้ง 77 จังหวัด: โฟลเดอร์ใช้ "beung_kan" แต่ชื่อทางการสะกด "BUENG KAN" — เก็บเป็นตารางเทียบชัดเจนตรงนี้แทนการ
# เดา/fuzzy-match แบบเงียบ ๆ เพื่อให้ตรวจสอบและแก้ไขได้ง่ายถ้าพบจังหวัดอื่นที่สะกดต่างในอนาคต
PROVINCE_SLUG_ALIASES = {
    "bueng_kan": "beung_kan",
}


def _slugify_province_en(name_en: str) -> str:
    """แปลงชื่อจังหวัดภาษาอังกฤษ (จาก THA_Province.P_NAME_E) ให้เป็นรูปแบบเดียวกับชื่อโฟลเดอร์ provincial_gis
    เช่น "KAMPHAENG PHET" -> "kamphaeng_phet", "Chiang Mai" -> "chiang_mai" """
    s = unicodedata.normalize("NFKD", name_en).encode("ascii", "ignore").decode()
    s = s.strip().lower()
    s = "_".join(s.split())
    return s


def build_province_folder_map(data_raw_dir: str) -> dict:
    """สร้าง mapping ชื่อจังหวัด (ไทย) -> path โฟลเดอร์ provincial_gis/<n>_<slug>/ โดยจับคู่ slug อัตโนมัติ
    (ไม่ hardcode รายชื่อจังหวัดใด ๆ ไว้ล่วงหน้า) — คืนค่า dict {P_NAME_T: full_folder_path}"""
    admin_shp = os.path.join(data_raw_dir, "admin_boundary", "THA_Province.shp")
    prov = gpd.read_file(admin_shp)

    gis_root = os.path.join(data_raw_dir, "provincial_gis")
    folder_by_slug = {}
    for entry in os.listdir(gis_root):
        full = os.path.join(gis_root, entry)
        if not os.path.isdir(full):
            continue
        if "_" not in entry:
            continue
        slug = entry.split("_", 1)[1]
        folder_by_slug[slug] = full

    name_to_folder = {}
    unmatched = []
    for _, row in prov.iterrows():
        slug = _slugify_province_en(row["P_NAME_E"])
        folder = folder_by_slug.get(slug) or folder_by_slug.get(PROVINCE_SLUG_ALIASES.get(slug, ""))
        if folder is None:
            unmatched.append((row["P_NAME_T"], row["P_NAME_E"], slug))
            continue
        name_to_folder[row["P_NAME_T"]] = folder

    if unmatched:
        print(f"⚠️  จับคู่โฟลเดอร์ provincial_gis ไม่ได้ {len(unmatched)} จังหวัด (จากทั้งหมด {len(prov)}):",
              file=sys.stderr)
        for th, en, slug in unmatched:
            print(f"    - {th} ({en}) -> คาดว่า slug '{slug}' แต่ไม่พบโฟลเดอร์นี้", file=sys.stderr)

    return name_to_folder


# แหล่งข้อมูลชื่อตำบล/อำเภอต่าง ๆ ที่ระบบนี้เชื่อมด้วย (ตาราง tambons ของ Supabase ที่มีอยู่ก่อน, ชุด
# THA_Tambon.shp ทั่วประเทศ, หน้าเว็บที่ผู้ใช้พิมพ์เอง) มีธรรมเนียมใส่คำนำหน้าชื่อ ("ตำบล", "ต.", "อำเภอ", "อ.")
# ไม่ตรงกัน (พบระหว่างทำฟีเจอร์เลือกตำบลใหม่ 2026-08-30: THA_Tambon.dbf เก็บชื่อล้วน ๆ "นครป่าหมาก" แต่แถวเดิม
# ในตาราง tambons ของ Supabase เก็บเป็น "ตำบลนครป่าหมาก" มีคำนำหน้า) — ตัดคำนำหน้าออกทั้งสองฝั่งก่อนเทียบเสมอ
# กันปัญหาจับคู่ไม่เจอ/เจอผิดเงียบ ๆ
_THAI_ADMIN_PREFIXES = ["ตำบล", "ต.", "แขวง", "อำเภอ", "อ.", "เขต"]


def _normalize_thai_admin_name(name: str) -> str:
    name = (name or "").strip()
    for prefix in _THAI_ADMIN_PREFIXES:
        if name.startswith(prefix):
            return name[len(prefix):].strip()
    return name


def _sql_escape(s: str) -> str:
    return s.replace("'", "''")


def load_tambon_boundary(data_raw_dir: str, province_th: str, amphoe_th: str, tambon_th: str):
    """โหลดขอบเขตตำบลที่ต้องการจาก THA_Tambon.shp (ระบุครบ 3 ระดับเพื่อกันชื่อตำบลซ้ำกันข้ามอำเภอ/จังหวัด)
    เทียบชื่อแบบตัดคำนำหน้าออกก่อนเสมอ (ดู _normalize_thai_admin_name) เพราะแหล่งข้อมูลแต่ละที่ใส่คำนำหน้าไม่
    ตรงกัน — ค่าในไฟล์ THA_Tambon.dbf เองไม่มีคำนำหน้าอยู่แล้ว (ตรวจสอบแล้ว) จึงตัดคำนำหน้าแค่ฝั่งค่าที่รับเข้ามา

    **สำคัญเรื่อง memory (เพิ่มเมื่อ 2026-08-30 หลังเจอ 502 Bad Gateway บน Render free tier 512MB)**: ห้ามใช้
    gpd.read_file(tambon_shp) เฉย ๆ แล้วค่อยกรองด้วย pandas — วิธีนั้นโหลดทั้ง 8,105 ตำบลทั่วประเทศ (พร้อม
    geometry เต็ม) เข้า memory ก่อนเสมอ ซึ่งกิน RAM มากเกินไปสำหรับ container ขนาดเล็ก ใช้ where= (pushdown
    filter ระดับ GDAL/OGR ผ่าน pyogrio) แทน เพื่อให้โหลดเข้ามาแค่แถวที่ตรงจริง ๆ (ปกติ 0-1 แถว)"""
    tambon_shp = os.path.join(data_raw_dir, "admin_boundary", "THA_Tambon.shp")
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
        raise ValueError(f"ไม่พบตำบล '{tambon_th}' อำเภอ '{amphoe_th}' จังหวัด '{province_th}' ใน THA_Tambon.shp")
    if len(match) > 1:
        raise ValueError(f"พบมากกว่า 1 รายการตรงกับ '{province_th}/{amphoe_th}/{tambon_th}' — ข้อมูลซ้ำซ้อน "
                          f"ต้องตรวจสอบ THA_Tambon.shp เอง (ไม่ควรเกิดขึ้น)")
    return match.iloc[0]


def load_surface_water(province_folder: str, province_code_prefix: str):
    """โหลด Major River / minor stream / water body ของจังหวัดหนึ่ง ๆ พร้อมกำหนด CRS ที่ถูกต้อง (EPSG:4326 —
    ไฟล์เหล่านี้ไม่มี .prj กำกับ แต่พิกัดดิบเป็น lon/lat จริง ตรวจสอบแล้วในขั้นสำรวจข้อมูล) แล้วแปลงเป็น
    EPSG:32647 ให้ตรงกับขอบเขตตำบล คืนค่าเป็น (major_river_gdf, minor_stream_gdf, water_body_gdf)"""
    sw_dir = os.path.join(province_folder, "surface_water")

    def _read(fname):
        path = os.path.join(sw_dir, fname)
        gdf = gpd.read_file(path, encoding=DATA_RAW_ENCODING)
        if gdf.crs is None:
            gdf = gdf.set_crs("EPSG:4326")
        return gdf.to_crs("EPSG:32647")

    major = _read(f"{province_code_prefix} Major River.shp")
    minor = _read(f"{province_code_prefix} minor stream.shp")
    body = _read(f"{province_code_prefix} water body.shp")
    return major, minor, body


def _bbox_wgs84_from_boundary(boundary_buffered: gpd.GeoSeries):
    """คืนค่า (south, west, north, east) ของขอบเขต boundary_buffered (EPSG:32647) แปลงเป็น EPSG:4326 —
    RPC bbox ฝั่ง Supabase ใช้ ST_MakeEnvelope กับพิกัด lon/lat (EPSG:4326) เสมอ"""
    wgs84 = boundary_buffered.to_crs("EPSG:4326")
    west, south, east, north = wgs84.total_bounds
    return south, west, north, east


def _call_mitrearth_rpc(rpc_name: str, bbox):
    south, west, north, east = bbox
    resp = requests.post(
        f"{SUPABASE_URL}/rest/v1/rpc/{rpc_name}",
        headers={
            "apikey": SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
            "Content-Type": "application/json",
        },
        json={"p_south": south, "p_west": west, "p_north": north, "p_east": east},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def load_mitrearth_from_supabase(boundary_buffered: gpd.GeoSeries):
    """ดึงข้อมูลเสริม mitrearth (waterway/water body) จาก Supabase แทนการอ่าน shapefile ในเครื่อง — ใช้ RPC
    nw_mitrearth_waterways_in_bbox / nw_mitrearth_water_bodies_in_bbox (bbox-filtered, SECURITY DEFINER จำกัด
    สิทธิ์ไว้เฉพาะ service_role เท่านั้น — ดู migration add_source_attrs_to_mitrearth_bbox_rpcs_v2) ดึงเฉพาะข้อมูล
    ในกรอบ bbox ของตำบล (+buffer) ที่กำลังประมวลผลอยู่ ไม่ใช่ทั้งจังหวัด — คืนค่ารูปแบบเดียวกับ load_surface_water():
    (major_river_gdf, minor_stream_gdf, water_body_gdf) ทั้งหมดใน EPSG:32647 พร้อม source_attrs (HY_LNAME,
    str_name_t ฯลฯ) แตกเป็นคอลัมน์ระดับบนให้ classify_waterway_sources()/_clean_possibly_truncated_mitrearth_name()
    เดิมใช้งานได้ทันทีโดยไม่ต้องแก้โค้ดส่วนนั้นเลย — raise exception ถ้าเรียก Supabase ไม่สำเร็จ (ให้ ingest()
    เป็นคนตัดสินใจ fallback เอง ไม่กลืน error เงียบ ๆ ตรงนี้)"""
    bbox = _bbox_wgs84_from_boundary(boundary_buffered)

    waterway_rows = _call_mitrearth_rpc("nw_mitrearth_waterways_in_bbox", bbox)
    major_rows, minor_rows = [], []
    for r in waterway_rows:
        geom = shapely.geometry.shape(json.loads(r["geom_geojson"]))
        row = dict(r.get("source_attrs") or {})
        row["geometry"] = geom
        if r["feature_type"] == "major_river":
            major_rows.append(row)
        elif r["feature_type"] == "minor_stream":
            minor_rows.append(row)

    body_rows_raw = _call_mitrearth_rpc("nw_mitrearth_water_bodies_in_bbox", bbox)
    body_rows = []
    for r in body_rows_raw:
        geom = shapely.geometry.shape(json.loads(r["geom_geojson"]))
        row = dict(r.get("source_attrs") or {})
        row["geometry"] = geom
        body_rows.append(row)

    def _to_gdf(rows):
        if not rows:
            return gpd.GeoDataFrame({"geometry": []}, geometry="geometry", crs="EPSG:4326").to_crs("EPSG:32647")
        gdf = gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:4326")
        return gdf.to_crs("EPSG:32647")

    return _to_gdf(major_rows), _to_gdf(minor_rows), _to_gdf(body_rows)


def load_osm_waterways(osm_geojson_path: str):
    """โหลดเส้นทางน้ำจาก OSM (ไฟล์ GeoJSON ที่เตรียมไว้ล่วงหน้า — ดูหมายเหตุข้อจำกัดเครือข่ายด้านบนไฟล์)
    คาดว่า geometry เป็น LineString ใน EPSG:4326 (ค่ามาตรฐาน GeoJSON/OSM) — แปลงเป็น EPSG:32647"""
    gdf = gpd.read_file(osm_geojson_path)
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    return gdf.to_crs("EPSG:32647")


def drop_minor_stream_duplicated_by_major_river(mitrearth_lines: gpd.GeoDataFrame,
                                                 buffer_m: float = 15.0, coverage_threshold: float = 0.9):
    """ล้างข้อมูลซ้ำภายใน mitrearth เอง (พบระหว่างตรวจสอบ Phase 2): shapefile "minor stream" ของบางจังหวัดมี
    บาง record ที่เป็นเส้นทางเดียวกับ "Major River" ซ้ำอีกชั้น (ไม่ใช่ปัญหาจาก OSM เลย เป็นความซ้ำซ้อนในชุดข้อมูล
    ดิบเอง) — ทดสอบกับนครป่าหมากพบว่า 15/77 เส้น minor_stream ถูกครอบคลุมโดย major_river ถึง 100% พอดี (ส่วนที่
    เหลือครอบคลุมแทบ 0%) แบ่งกลุ่มชัดเจนมาก จึงตัดเส้น minor_stream ที่ถูกครอบคลุมโดย major_river (รวมกันเป็น
    เส้นเดียว, buffer 15 ม.) เกิน coverage_threshold ทิ้ง — เก็บเฉพาะเวอร์ชัน major_river ไว้ (ถือเป็นชั้นข้อมูล
    ที่แม่นยำกว่าเพราะเป็นการจำแนกที่ตั้งใจไว้ระดับจังหวัด) การซ้ำซ้อนแบบนี้ถ้าไม่กรองออกจะทำให้กราฟโครงข่ายใน
    Phase 2 มี node ปลอมจำนวนมาก (เส้นซ้ำตัดกันเองซ้ำ ๆ ตอน noding) — ถ้าทดสอบจังหวัดอื่นแล้วสัดส่วนไม่ชัดเจนแบบนี้
    ต้องตรวจข้อมูลจริงแล้วปรับ ไม่ใช่ตรึงค่าไว้ตายตัว"""
    major = mitrearth_lines[mitrearth_lines["source_layer"] == "major_river"]
    minor = mitrearth_lines[mitrearth_lines["source_layer"] == "minor_stream"]
    if len(major) == 0 or len(minor) == 0:
        return mitrearth_lines

    major_union = major.geometry.union_all() if hasattr(major.geometry, "union_all") else major.geometry.unary_union
    buf = major_union.buffer(buffer_m)

    keep_idx = []
    for idx, row in minor.iterrows():
        geom = row.geometry
        if geom is None or geom.length == 0:
            keep_idx.append(idx)
            continue
        frac = geom.intersection(buf).length / geom.length
        if frac < coverage_threshold:
            keep_idx.append(idx)

    minor_clean = minor.loc[keep_idx]
    return gpd.GeoDataFrame(pd.concat([major, minor_clean], ignore_index=True),
                             geometry="geometry", crs=mitrearth_lines.crs)


def classify_waterway_sources(osm_lines, mitrearth_lines,
                               buffer_m: float = OSM_COVERAGE_BUFFER_M,
                               coverage_threshold: float = OSM_COVERAGE_THRESHOLD):
    """รวมเส้นทางน้ำจาก 2 แหล่งตาม ADR-003: OSM เป็นหลัก, mitrearth เติมเฉพาะเส้นที่ "ยังไม่มีอยู่แล้วใน OSM"

    วิธีตรวจ: สร้าง buffer รอบเส้นทาง OSM ทั้งหมด (ระยะ buffer_m) แล้วดูว่าแต่ละเส้น mitrearth มีความยาวเท่าไหร่
    ที่ตกอยู่ใน buffer นี้ (fraction ของความยาวทั้งเส้น) — ถ้า fraction >= coverage_threshold ถือว่า "ซ้ำกับ
    OSM แล้ว" (ตัดทิ้ง ไม่เอามาเติม) มิฉะนั้นถือว่า "ขาดหายจาก OSM" (เติมเข้าไปทั้งเส้น พร้อม flag source ชัดเจน)

    หมายเหตุ: เคยลองเปลี่ยนเป็น "ตัดเฉพาะส่วนที่ทับ OSM ออกด้วย geometry difference (partial clip)" เพื่อแก้ปัญหา
    เส้นซ้ำตามที่อธิบายด้านล่าง แต่พบว่าทำให้แย่ลง (component จาก 12 กลายเป็น 83, dead-end จาก 42 เป็น 178) เพราะ
    จุดตัด (คำนวณจากขอบ buffer) ไม่ตรงกับ node ใด ๆ ในกราฟเดิม กลายเป็นปลายเส้นลอยที่ไม่เชื่อมกับอะไรเลย —
    ย้อนกลับมาใช้วิธี all-or-nothing ตามเดิม แล้วไปแก้ปัญหาเส้นซ้ำที่ระดับกราฟแทน (ดู
    drop_duplicate_parallel_edges ใน 02_topology_graph.py) ซึ่งปลอดภัยกว่า เพราะทำงานหลัง noding/snapping
    เสร็จแล้ว (มี node จริงรองรับอยู่ก่อน ไม่มีปัญหาปลายเส้นลอย)

    คืนค่า GeoDataFrame รวม พร้อมคอลัมน์: source ('osm' | 'mitrearth_supplement'), waterway_tag (ค่า tag เดิม:
    river/canal/stream/drain สำหรับ osm, major_river/minor_stream สำหรับ mitrearth), name (ถ้ามี),
    mitrearth_osm_coverage_frac (เฉพาะแถวที่มาจาก mitrearth — สัดส่วนที่ซ้อนทับ OSM อยู่แล้ว เก็บไว้ตรวจสอบย้อนกลับ)
    """
    osm_out = osm_lines.copy()
    osm_out["source"] = "osm"
    osm_out["waterway_tag"] = osm_out.get("waterway")
    if "name" not in osm_out.columns:
        osm_out["name"] = None
    osm_out["mitrearth_osm_coverage_frac"] = None

    if len(osm_lines) == 0:
        osm_union = None
    else:
        osm_union = osm_lines.geometry.union_all() if hasattr(osm_lines.geometry, "union_all") \
            else osm_lines.geometry.unary_union

    supplement_rows = []
    for idx, row in mitrearth_lines.iterrows():
        geom = row.geometry
        if geom is None or geom.length == 0:
            continue
        if osm_union is None:
            frac = 0.0
        else:
            buf = osm_union.buffer(buffer_m)
            inter = geom.intersection(buf)
            frac = inter.length / geom.length
        if frac < coverage_threshold:
            new_row = row.to_dict()
            new_row["source"] = "mitrearth_supplement"
            new_row["waterway_tag"] = row.get("source_layer")
            raw_name = row.get("HY_LNAME") or row.get("str_name_t") or row.get("str_name_e")
            new_row["name"] = _clean_possibly_truncated_mitrearth_name(raw_name)
            new_row["mitrearth_osm_coverage_frac"] = round(frac, 3)
            supplement_rows.append(new_row)

    keep_cols = ["geometry", "source", "waterway_tag", "name", "mitrearth_osm_coverage_frac"]
    osm_slim = osm_out[[c for c in keep_cols if c in osm_out.columns]]
    if supplement_rows:
        supp_gdf = gpd.GeoDataFrame(supplement_rows, geometry="geometry", crs=mitrearth_lines.crs)
        supp_slim = supp_gdf[[c for c in keep_cols if c in supp_gdf.columns]]
        combined = pd.concat([osm_slim, supp_slim], ignore_index=True)
    else:
        combined = osm_slim.copy()

    return gpd.GeoDataFrame(combined, geometry="geometry", crs=mitrearth_lines.crs)


def drop_closed_ring_lines(lines_gdf: gpd.GeoDataFrame):
    """ตัดเส้นทางน้ำที่เป็น "วงปิด" ออก (จุดเริ่มต้นของเส้น == จุดสิ้นสุดพอดี) — พบระหว่างตรวจสอบ Phase 2
    (self-loop node จำนวนมากผิดปกติ, 54 จาก 162 เส้นเชื่อมของนครป่าหมาก บางเส้นยาวถึง 8.7 กม.!) ตรวจสอบจริงพบว่า
    ทุกเส้นที่เป็นวงปิดคือขอบเขต/รูปร่างของแหล่งน้ำ (บึง/หนอง เช่น "บึงสะลุ", "หนองแฝก", "หนองหัวไผ่") ที่ปนเข้ามา
    ในชั้นข้อมูล "minor stream" ของ mitrearth โดยไม่ตั้งใจ (การสำรวจดิจิไทซ์รูปร่างแหล่งน้ำเป็นเส้นวงปิดแทนที่จะ
    เป็น polygon) ไม่ใช่เส้นทางการไหลของน้ำจริง (เส้นทางน้ำจริงไม่มีทางเริ่มและจบที่จุดเดียวกันได้ในทางภูมิศาสตร์)
    ยืนยันแล้วว่าตัดออกได้โดยไม่เสียข้อมูล เพราะแหล่งน้ำเหล่านี้มีอยู่ใน water_bodies (จาก mitrearth water-body
    polygon layer โดยตรง) อยู่แล้วทุกชื่อ — เป็นกฎเชิงหลักการ (ไม่ใช่ threshold ตัวเลขที่ต้องเดา/ทดสอบ distribution)
    เพราะ "เส้นวงปิดพอดี" เป็นข้อเท็จจริงทางเรขาคณิตที่ตรวจสอบได้แน่นอน ใช้ได้กับทุกตำบล/ทุกแหล่งข้อมูล (OSM ก็ตรวจ
    ด้วยเผื่อไว้ แม้ยังไม่เคยพบปัญหานี้จาก OSM ก็ตาม)"""
    def _is_ring(geom):
        if geom is None or geom.is_empty:
            return False
        coords = list(geom.coords)
        return len(coords) >= 2 and coords[0] == coords[-1]

    is_ring = lines_gdf.geometry.apply(_is_ring)
    n_dropped = int(is_ring.sum())
    return lines_gdf[~is_ring].reset_index(drop=True), n_dropped


def ingest(data_raw_dir: str, osm_geojson_path: str, province_th: str, amphoe_th: str, tambon_th: str,
           buffer_m: float = 300.0):
    """ขั้นตอนหลัก: คืนค่า dict ที่มี boundary (ขอบเขตตำบล), boundary_buffered (ขอบเขต+buffer สำหรับตัด
    เผื่อเส้นน้ำที่พาดผ่านขอบตำบลพอดี), waterway_lines (OSM หลัก + mitrearth เติมเฉพาะที่ขาด ตัดแล้ว, ตาม
    ADR-003), water_bodies (water body จาก mitrearth ที่ตัดแล้ว) — ทุกชั้นข้อมูลอยู่ใน EPSG:32647 ตรงกัน"""
    tambon_row = load_tambon_boundary(data_raw_dir, province_th, amphoe_th, tambon_th)
    boundary = gpd.GeoSeries([tambon_row.geometry], crs="EPSG:32647")
    boundary_buffered = boundary.buffer(buffer_m)

    # หมายเหตุ (2026-08-30, เพิ่มรองรับตำบล/จังหวัดใหม่แบบ on-demand จากหน้าเว็บ): ตาม ADR-003 mitrearth
    # เป็นแค่ "ข้อมูลเสริม" ของ OSM ไม่ใช่แหล่งหลัก — ถ้ายังไม่ได้ bundle ข้อมูล provincial_gis ของจังหวัดนี้ไว้
    # (เช่น เพิ่งเลือกตำบลใหม่ในจังหวัดที่ยังไม่เคยเตรียมข้อมูล mitrearth) ให้ "ข้ามการเติม mitrearth" แทนการ
    # ล้มทั้ง pipeline — ผลลัพธ์จะได้ผังจาก OSM ล้วน ๆ (ยังใช้งานได้จริง เพียงแต่ยังไม่มีการเติมเส้นที่ OSM
    # สำรวจไม่ครบ) ผู้ดูแลระบบเพิ่มข้อมูล provincial_gis ของจังหวัดนั้นทีหลังได้ตามที่อธิบายไว้ใน
    # 02_engine_data/README.md แล้วรัน engine ใหม่อีกครั้งเพื่อให้ได้ผังที่สมบูรณ์ขึ้น
    major = minor = body = None
    if SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY:
        try:
            major, minor, body = load_mitrearth_from_supabase(boundary_buffered)
            print(f"  mitrearth (เสริม, จาก Supabase): major_river {len(major)}, minor_stream {len(minor)}, "
                  f"water_body {len(body)} รูป (ในกรอบ bbox ของตำบล+buffer)", file=sys.stderr)
        except Exception as e:
            print(f"⚠️  ดึงข้อมูล mitrearth จาก Supabase ไม่สำเร็จ ({type(e).__name__}: {e}) — ลอง fallback ไปใช้ "
                  f"shapefile ในเครื่องแทน (ถ้ามี bundled ไว้)", file=sys.stderr)
            major = minor = body = None

    if major is None:
        folder_map = build_province_folder_map(data_raw_dir)
        province_folder = folder_map.get(province_th)
        if province_folder is None:
            prefix = ("ยังไม่ได้ตั้งค่า SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY และ"
                      if not (SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY) else "Supabase เรียกไม่สำเร็จ และ")
            print(f"⚠️  {prefix}ไม่พบโฟลเดอร์ provincial_gis สำหรับจังหวัด '{province_th}' ในเครื่อง — ข้ามการเติม"
                  f"ข้อมูลเสริม mitrearth (ใช้ OSM เป็นแหล่งเดียว ตาม ADR-003 ข้อมูล mitrearth เป็นแค่ส่วนเสริม"
                  f"อยู่แล้ว ไม่ใช่แหล่งหลัก)", file=sys.stderr)
            empty_geom = gpd.GeoDataFrame({"geometry": []}, geometry="geometry", crs="EPSG:32647")
            major, minor, body = empty_geom.copy(), empty_geom.copy(), empty_geom.copy()
        else:
            code_prefix = os.path.basename(province_folder).split("_", 1)[0]
            major, minor, body = load_surface_water(province_folder, code_prefix)

    osm_raw = load_osm_waterways(osm_geojson_path)

    clip_mask = boundary_buffered.union_all() if hasattr(boundary_buffered, "union_all") \
        else boundary_buffered.unary_union

    major_clip = major[major.intersects(clip_mask)].copy()
    minor_clip = minor[minor.intersects(clip_mask)].copy()
    mitrearth_lines = pd.concat([
        major_clip.assign(source_layer="major_river"),
        minor_clip.assign(source_layer="minor_stream"),
    ], ignore_index=True)
    mitrearth_lines = gpd.GeoDataFrame(mitrearth_lines, geometry="geometry", crs="EPSG:32647")
    mitrearth_lines = drop_minor_stream_duplicated_by_major_river(mitrearth_lines)

    osm_clip = osm_raw[osm_raw.intersects(clip_mask)].copy()

    combined_lines = classify_waterway_sources(osm_clip, mitrearth_lines)
    combined_lines, n_ring_dropped = drop_closed_ring_lines(combined_lines)

    body_clip = body[body.intersects(clip_mask)].copy()
    body_clip = gpd.GeoDataFrame(body_clip, geometry="geometry", crs="EPSG:32647")

    return {
        "tambon_row": tambon_row,
        "boundary": boundary,
        "boundary_buffered": boundary_buffered,
        "waterway_lines": combined_lines,
        "water_bodies": body_clip,
        "n_closed_ring_lines_dropped": n_ring_dropped,
    }


def main():
    ap = argparse.ArgumentParser(description="Phase 1 (Data Ingestion) ของเอนจินใหม่ — ดึงเส้นน้ำ (OSM หลัก + "
                                              "mitrearth เติมเฉพาะที่ขาด ตาม ADR-003) และแหล่งน้ำดิบระดับจังหวัด "
                                              "ที่อยู่ในเขตตำบลที่ระบุ (generic ทุกตำบล ไม่ hardcode)")
    ap.add_argument("--data-raw-dir", required=True, help="path ไปยัง ARCHIVE_pilot_v1_offline_pipeline/01_data_raw")
    ap.add_argument("--osm-geojson", required=True, help="path ไปยังไฟล์ OSM waterway GeoJSON ที่เตรียมไว้ล่วงหน้า "
                                                          "สำหรับตำบลนี้ (ดูหมายเหตุข้อจำกัดเครือข่ายในไฟล์นี้)")
    ap.add_argument("--province", required=True, help="ชื่อจังหวัดภาษาไทย เช่น พิษณุโลก")
    ap.add_argument("--amphoe", required=True, help="ชื่ออำเภอภาษาไทย เช่น บางกระทุ่ม")
    ap.add_argument("--tambon", required=True, help="ชื่อตำบลภาษาไทย เช่น นครป่าหมาก")
    ap.add_argument("--buffer-m", type=float, default=300.0, help="ระยะ buffer รอบขอบเขตตำบล (เมตร) ก่อนตัด "
                                                                   "เผื่อเส้นน้ำที่พาดผ่านขอบพอดี (ค่าเริ่มต้น 300)")
    ap.add_argument("--out-dir", required=True, help="โฟลเดอร์สำหรับบันทึกผลลัพธ์ (GeoJSON)")
    args = ap.parse_args()

    result = ingest(args.data_raw_dir, args.osm_geojson, args.province, args.amphoe, args.tambon, args.buffer_m)

    os.makedirs(args.out_dir, exist_ok=True)
    boundary_gdf = gpd.GeoDataFrame({"tambon": [args.tambon], "amphoe": [args.amphoe], "province": [args.province]},
                                     geometry=result["boundary"].values, crs="EPSG:32647")
    boundary_gdf.to_file(os.path.join(args.out_dir, "boundary.geojson"), driver="GeoJSON")
    result["waterway_lines"].to_file(os.path.join(args.out_dir, "waterway_lines_raw.geojson"), driver="GeoJSON")
    result["water_bodies"].to_file(os.path.join(args.out_dir, "water_bodies_raw.geojson"), driver="GeoJSON")

    n_osm = (result["waterway_lines"]["source"] == "osm").sum()
    n_supp = (result["waterway_lines"]["source"] == "mitrearth_supplement").sum()
    print(f"ตำบล{args.tambon} อำเภอ{args.amphoe} จังหวัด{args.province}")
    print(f"  พื้นที่ตำบล: {result['tambon_row'].geometry.area / 1e6:.2f} ตร.กม.")
    print(f"  เส้นน้ำรวม (ตัดด้วย buffer {args.buffer_m} ม.): {len(result['waterway_lines'])} เส้น")
    print(f"    - จาก OSM (แหล่งหลัก): {n_osm} เส้น")
    print(f"    - จาก mitrearth (เติมเฉพาะที่ขาดจาก OSM, ADR-003): {n_supp} เส้น")
    print(f"    - ตัดเส้นวงปิดทิ้ง (ขอบเขตแหล่งน้ำที่ปนมาในชั้น minor_stream): {result['n_closed_ring_lines_dropped']} เส้น")
    print(f"  water body ที่ตัดได้ (จาก mitrearth): {len(result['water_bodies'])} รูปหลายเหลี่ยม")
    print(f"  บันทึกผลลัพธ์ที่: {args.out_dir}")


if __name__ == "__main__":
    main()
