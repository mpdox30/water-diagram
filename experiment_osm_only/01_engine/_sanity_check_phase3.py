"""
สคริปต์ตรวจสอบภาพ (sanity check) ผลลัพธ์ Phase 3 Schematic Transformation — แสดงผังหลังจัดวางแบบ orthogonal
(elbow routing) แยกความหนาเส้นตาม waterway_size (main หนา / branch บาง) และแยกสีตามแหล่งที่มา (OSM / mitrearth
supplement) เหมือน sanity check ของ Phase 1/2 เพื่อตรวจสอบว่าโครงสร้างยังสมเหตุสมผลหลังแปลงเป็นผังเส้นตรงมุมฉาก
(ไม่ใช่ script การผลิตผังน้ำจริง — เป็นเครื่องมือ debug/verify ระหว่างพัฒนาเอนจินเท่านั้น)

วิธีใช้:
    cd 06_web_platform/02_engine_output/<tambon_slug>/phase3_schematic
    python3 ../../../01_engine/_sanity_check_phase3.py
"""
import geopandas as gpd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

nodes = gpd.read_file('nodes_schematic.geojson')
edges = gpd.read_file('edges_schematic.geojson')

fig, ax = plt.subplots(figsize=(13, 13))

for size, width in [('branch', 1.2), ('main', 4.0)]:
    for src, color, style in [('osm', '#0D47A1', 'solid'), ('mitrearth_supplement', '#E65100', (0, (4, 2)))]:
        subset = edges[(edges.waterway_size == size) & (edges.source == src)]
        if len(subset) == 0:
            continue
        label = f"{'หลัก (main)' if size == 'main' else 'สาขา (branch)'} - {'OSM' if src == 'osm' else 'mitrearth เติม'} ({len(subset)})"
        subset.plot(ax=ax, color=color, linewidth=width, linestyle=style, label=label, zorder=2 if size == 'main' else 1)

junctions = nodes[nodes.degree >= 3]
deadends = nodes[nodes.degree == 1]
junctions.plot(ax=ax, color='green', markersize=30, zorder=5, label=f'จุดแยก degree>=3 ({len(junctions)})')
deadends.plot(ax=ax, color='black', markersize=15, zorder=5, label=f'จุดปลายตัน degree=1 ({len(deadends)})')

ax.set_title('Phase 3 sanity check: orthogonal schematic layout (elbow routing)')
ax.set_aspect('equal')
ax.legend(loc='upper left', fontsize=8)
plt.savefig('sanity_check_phase3.png', dpi=130, bbox_inches='tight')
print('saved sanity_check_phase3.png')
print('nodes:', len(nodes), 'edges:', len(edges))
