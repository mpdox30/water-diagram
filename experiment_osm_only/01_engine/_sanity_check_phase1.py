"""
สคริปต์ตรวจสอบภาพ (sanity check) ผลลัพธ์ Phase 1 Data Ingestion แบบรวดเร็ว
ใช้เทียบตำแหน่งเชิงพื้นที่ของขอบเขตตำบล / เส้นทางน้ำ / แหล่งน้ำ ว่าถูกต้องหรือไม่
(ไม่ใช่ script การผลิตผังน้ำจริง — เป็นเครื่องมือ debug/verify ระหว่างพัฒนาเอนจินเท่านั้น)

วิธีใช้:
    cd 06_web_platform/02_engine_output/<tambon_slug>/phase1_ingest
    python3 ../../../01_engine/_sanity_check_phase1.py

หมายเหตุ: ฟอนต์ที่ใช้ (DejaVu Sans ค่าเริ่มต้นของ matplotlib) ไม่รองรับตัวอักษรไทย
จึง title ภาษาไทยจะเห็นเป็นกล่องสี่เหลี่ยม (missing glyph) — ไม่กระทบการตรวจสอบตำแหน่งเชิงพื้นที่
ถ้าต้องการ title ภาษาไทยแสดงผลถูกต้อง ต้องโหลดฟอนต์ Sarabun เพิ่มเอง (ดูตัวอย่างใน 04_scripts เดิม)
"""
import geopandas as gpd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

boundary = gpd.read_file('boundary.geojson')
lines = gpd.read_file('waterway_lines_raw.geojson')
bodies = gpd.read_file('water_bodies_raw.geojson')

fig, ax = plt.subplots(figsize=(10, 10))
boundary.boundary.plot(ax=ax, color='red', linewidth=1.5, linestyle='--')
bodies.plot(ax=ax, color='#a8d8ff', edgecolor='#3399ff')
lines[lines.source_layer == 'minor_stream'].plot(ax=ax, color='#1565C0', linewidth=1)
lines[lines.source_layer == 'major_river'].plot(ax=ax, color='#0D47A1', linewidth=2.5)
ax.set_title('Phase 1 sanity check: raw ingest (generic engine)')
ax.set_aspect('equal')
plt.savefig('sanity_check.png', dpi=130, bbox_inches='tight')
print('saved sanity_check.png')
