"""
สคริปต์ตรวจสอบภาพ (sanity check) ผลลัพธ์ Phase 2 Topology Graph — แสดงกราฟที่ยุบ node ทางผ่านแล้ว แยกสีตาม
แหล่งที่มา (OSM / mitrearth supplement) และไฮไลต์ node ที่เป็นจุดแยกจริง (degree>=3) กับจุดปลายตัน (degree==1)
เทียบกับขอบเขตตำบล — เพื่อดูว่าโครงสร้างกราฟสมเหตุสมผลหรือไม่
(ไม่ใช่ script การผลิตผังน้ำจริง — เป็นเครื่องมือ debug/verify ระหว่างพัฒนาเอนจินเท่านั้น)

วิธีใช้:
    cd 06_web_platform/02_engine_output/<tambon_slug>/phase2_topology
    python3 ../../../01_engine/_sanity_check_phase2.py
"""
import geopandas as gpd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

boundary = gpd.read_file('../phase1_ingest_v2/boundary.geojson')
nodes = gpd.read_file('nodes.geojson')
edges = gpd.read_file('edges.geojson')

fig, ax = plt.subplots(figsize=(11, 11))
boundary.boundary.plot(ax=ax, color='red', linewidth=1.5, linestyle='--')

osm_edges = edges[edges.source == 'osm']
supp_edges = edges[edges.source == 'mitrearth_supplement']
osm_edges.plot(ax=ax, color='#0D47A1', linewidth=2.0, label=f'OSM ({len(osm_edges)} เส้น)')
supp_edges.plot(ax=ax, color='#E65100', linewidth=1.0, linestyle=(0, (4, 2)),
                label=f'mitrearth supplement ({len(supp_edges)} เส้น)')

junctions = nodes[nodes.degree >= 3]
deadends = nodes[nodes.degree == 1]
junctions.plot(ax=ax, color='green', markersize=25, zorder=5, label=f'จุดแยก degree>=3 ({len(junctions)})')
deadends.plot(ax=ax, color='black', markersize=10, zorder=5, label=f'จุดปลายตัน degree=1 ({len(deadends)})')

ax.set_title('Phase 2 sanity check: topology graph (after simplify)')
ax.set_aspect('equal')
ax.legend(loc='upper left', fontsize=8)
plt.savefig('sanity_check_phase2.png', dpi=130, bbox_inches='tight')
print('saved sanity_check_phase2.png')
print('nodes:', len(nodes), 'edges:', len(edges))
