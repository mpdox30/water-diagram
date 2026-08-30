"""
สคริปต์ตรวจสอบภาพ (sanity check) ผลลัพธ์ Phase 1 Data Ingestion เวอร์ชัน 2 (หลัง ADR-003: OSM หลัก + mitrearth
เติมเฉพาะที่ขาด) — แยกสีตามแหล่งที่มาของแต่ละเส้น เพื่อดูว่าการผสาน OSM + mitrearth สมเหตุสมผลหรือไม่
(ไม่ใช่ script การผลิตผังน้ำจริง — เป็นเครื่องมือ debug/verify ระหว่างพัฒนาเอนจินเท่านั้น)

วิธีใช้:
    cd 06_web_platform/02_engine_output/<tambon_slug>/phase1_ingest_v2
    python3 ../../../01_engine/_sanity_check_phase1_v2.py
"""
import geopandas as gpd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

boundary = gpd.read_file('boundary.geojson')
lines = gpd.read_file('waterway_lines_raw.geojson')
bodies = gpd.read_file('water_bodies_raw.geojson')

fig, ax = plt.subplots(figsize=(11, 11))
boundary.boundary.plot(ax=ax, color='red', linewidth=1.5, linestyle='--')
bodies.plot(ax=ax, color='#a8d8ff', edgecolor='#3399ff')
osm_lines = lines[lines.source == 'osm']
supp_lines = lines[lines.source == 'mitrearth_supplement']
osm_lines.plot(ax=ax, color='#0D47A1', linewidth=2.2, label=f'OSM (หลัก, {len(osm_lines)} เส้น)')
supp_lines.plot(ax=ax, color='#E65100', linewidth=1.0, linestyle=(0, (4, 2)),
                label=f'mitrearth supplement (เติมเฉพาะที่ขาด, {len(supp_lines)} เส้น)')
ax.set_title('Phase 1 v2 sanity check: OSM (primary) + mitrearth supplement (ADR-003)')
ax.set_aspect('equal')
ax.legend(loc='upper left', fontsize=9)
plt.savefig('sanity_check_v2.png', dpi=130, bbox_inches='tight')
print('saved sanity_check_v2.png')
