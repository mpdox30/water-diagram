"""
06_web_platform/02_engine_service/main.py

Backend service (Phase 6, ตาม ADR-005) — ห่อ engine pipeline (01_engine/*.py) เป็น HTTP API เดียว เพื่อให้
หน้าเว็บเรียก "เลือกตำบล -> รัน engine -> publish เข้า Supabase" ได้จากปุ่มเดียว แทนที่จะต้องรันสคริปต์ด้วยมือ

ออกแบบให้รันบน Render (ดู ADR-005) เป็น Web Service ธรรมดา (ไม่ใช่ Docker) — ต้องมี Python ที่ลง
requirements.txt ในโฟลเดอร์นี้แล้ว

**สำคัญเรื่อง auth**: endpoint /run-engine รัน pipeline ที่หนัก (ใช้เวลาเป็นสิบวินาทีถึงหลักนาที + ใช้ CPU/RAM
พอสมควร) จึงไม่เปิดให้ใครก็เรียกได้ฟรี ๆ — ต้องแนบ header `X-Engine-Secret` ให้ตรงกับ env var
`ENGINE_TRIGGER_SECRET` ที่ตั้งไว้บน Render เท่านั้น (ตั้งเป็นค่าสุ่มยาว ๆ ที่ทีมพัฒนา/หน้าเว็บฝั่ง manager รู้
เท่านั้น ไม่ใช่รหัส villager_form ที่ชุมชนทั่วไปรู้)

การเขียนผลลัพธ์เข้า Supabase ใช้ `service_role` key (env var SUPABASE_SERVICE_ROLE_KEY) เรียก
`public.nw_save_diagram_engine()` ซึ่งเป็นฟังก์ชันที่ grant EXECUTE ให้เฉพาะ service_role เท่านั้น (ไม่ใช่
anon/authenticated) — ดู migration `create engine-only publish wrapper` ในโปรเจกต์ Supabase — เพื่อให้ผังที่
publish ทางนี้ติด source='engine' ให้ตรงกับความจริง (แยกจาก source='community' ที่มาจากฟอร์มชุมชน)

**ข้อจำกัดที่ยังคงอยู่ (v1)**: ไฟล์ OSM waterway GeoJSON ของแต่ละตำบลยังต้องเตรียมไว้ล่วงหน้า (วางไว้ที่
01_data_external/osm/<slug>_osm_waterways.geojson) ตามข้อจำกัดเดิมที่บันทึกไว้ใน 01_data_ingestion.py — ยังไม่
ได้ลองให้ service นี้ดึงจาก Overpass API สดเอง (เป็นไปได้ว่า Render จะเข้าถึง Overpass ได้ต่างจาก sandbox
พัฒนา แต่ยังไม่ได้ทดสอบจริง — ถือเป็นงานต่อยอด ไม่ใช่ v1)
"""

import json
import os
import re
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path
from typing import Optional

import requests
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent.parent  # 06_web_platform/
ENGINE_DIR = BASE_DIR / "01_engine"
DATA_RAW_DIR = BASE_DIR / "02_engine_data"
OSM_DIR = BASE_DIR / "01_data_external" / "osm"

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
ENGINE_TRIGGER_SECRET = os.environ.get("ENGINE_TRIGGER_SECRET", "")

app = FastAPI(title="Water Diagram Engine Service")


class RunEngineRequest(BaseModel):
    tambon_id: str
    province_th: str
    amphoe_th: str
    tambon_th: str
    # ทางเลือก (2026-08-30): ถ้าระบุมาและมีไฟล์นี้เตรียมไว้จริง (เตรียมมือ/คัดสรรไว้ล่วงหน้า) จะใช้ไฟล์นี้ตรง ๆ
    # ถ้าไม่ระบุ หรือไฟล์ไม่มีอยู่จริง จะดึงสดจาก Overpass API แทน (ดู 00_fetch_osm_waterways.py) — ทำให้
    # ตำบลที่ไม่เคยเตรียมข้อมูลไว้ล่วงหน้าเลยก็ยังสร้างผังได้จากหน้าเว็บโดยตรง (ถ้า Render เรียก Overpass ได้จริง)
    osm_geojson_filename: Optional[str] = None
    label: str = "เรียกใช้งานผ่าน engine service (Render)"
    entered_by: str = "engine-service"


def _slugify_th_filename_hint(tambon_th: str) -> str:
    """ใช้แค่ทำชื่อไฟล์ log อ่านง่าย ไม่ใช่ตัว lookup จริง (lookup ผ่าน osm_geojson_filename ที่ส่งมาตรง ๆ)"""
    s = unicodedata.normalize("NFKD", tambon_th)
    return re.sub(r"\s+", "_", s.strip())


def _run_step(args, cwd):
    result = subprocess.run(
        [sys.executable] + args,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=600,
    )
    if result.returncode != 0:
        raise HTTPException(
            status_code=500,
            detail=f"engine step ล้มเหลว: {' '.join(args)}\nstdout: {result.stdout[-4000:]}\n"
                   f"stderr: {result.stderr[-4000:]}",
        )
    return result.stdout


def _parse_js_elements_file(js_path: Path) -> list:
    text = js_path.read_text(encoding="utf-8")
    # ไฟล์หน้าตา: "const engineElements = [ ... ];" (มี comment บรรทัดแรกด้วย ดู export_frontend_data())
    match = re.search(r"=\s*(\[.*\])\s*;\s*$", text, re.DOTALL)
    if not match:
        raise HTTPException(status_code=500, detail=f"parse ไฟล์ output ของ engine ไม่ได้: {js_path}")
    return json.loads(match.group(1))


def _cytoscape_elements_to_nw_format(elements: list):
    nodes, edges = [], []
    for el in elements:
        data = el.get("data", {})
        if "source" in data and "target" in data:
            edges.append({
                "edge_key": data["id"],
                "source_node_key": data["source"],
                "target_node_key": data["target"],
                "label": data.get("label") or "",
                "edge_type": data.get("type"),
                "engine_straight": bool(data.get("engineStraight", False)),
                "engine_bend": bool(data.get("engineBend", False)),
                "seg_dist": data.get("segDist"),
                "seg_weight": data.get("segWeight"),
            })
        else:
            pos = el.get("position", {})
            nodes.append({
                "node_key": data["id"],
                "label": data.get("label") or "",
                "node_type": data.get("type"),
                "rotation": data.get("rotation", 0),
                "dir": data.get("dir", "h"),
                "pos_x": pos.get("x"),
                "pos_y": pos.get("y"),
            })
    return nodes, edges


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.post("/run-engine")
def run_engine(req: RunEngineRequest, x_engine_secret: str = Header(default="")):
    if not ENGINE_TRIGGER_SECRET or x_engine_secret != ENGINE_TRIGGER_SECRET:
        raise HTTPException(status_code=401, detail="ไม่ได้รับอนุญาต (X-Engine-Secret ไม่ถูกต้อง)")
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise HTTPException(status_code=500, detail="ยังไม่ได้ตั้งค่า SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY")

    osm_path = OSM_DIR / req.osm_geojson_filename if req.osm_geojson_filename else None
    if osm_path is not None and not osm_path.exists():
        osm_path = None  # ไฟล์ที่ระบุมาไม่มีจริง — ลองดึงสดแทนด้านล่าง เหมือนไม่ได้ระบุมา

    with tempfile.TemporaryDirectory(prefix="engine_run_") as tmp:
        tmp = Path(tmp)
        phase1_dir = tmp / "phase1"
        phase2_dir = tmp / "phase2"
        phase3_dir = tmp / "phase3"
        out_js = tmp / "output.js"

        if osm_path is None:
            # ไม่มีไฟล์ OSM เตรียมไว้ล่วงหน้า — ดึงสดจาก Overpass API (ตำบลใหม่ที่เลือกจากหน้าเว็บโดยตรง)
            fetched_osm_path = tmp / "osm_waterways_fetched.geojson"
            try:
                _run_step([
                    str(ENGINE_DIR / "00_fetch_osm_waterways.py"),
                    "--data-raw-dir", str(DATA_RAW_DIR),
                    "--province", req.province_th,
                    "--amphoe", req.amphoe_th,
                    "--tambon", req.tambon_th,
                    "--out-geojson", str(fetched_osm_path),
                ], cwd=ENGINE_DIR)
            except HTTPException as e:
                raise HTTPException(
                    status_code=502,
                    detail=f"ดึงข้อมูล OSM สดจาก Overpass API ไม่สำเร็จ สำหรับตำบล '{req.tambon_th}' "
                           f"({e.detail}) — ต้องให้ทีมพัฒนาเตรียมไฟล์ OSM waterway GeoJSON ให้ด้วยมือแทน "
                           f"(ผ่านเบราว์เซอร์จริงที่มีอินเทอร์เน็ต) แล้วค่อยลองใหม่",
                )
            osm_path = fetched_osm_path

        _run_step([
            str(ENGINE_DIR / "01_data_ingestion.py"),
            "--data-raw-dir", str(DATA_RAW_DIR),
            "--osm-geojson", str(osm_path),
            "--province", req.province_th,
            "--amphoe", req.amphoe_th,
            "--tambon", req.tambon_th,
            "--out-dir", str(phase1_dir),
        ], cwd=ENGINE_DIR)

        _run_step([
            str(ENGINE_DIR / "02_topology_graph.py"),
            "--phase1-dir", str(phase1_dir),
            "--out-dir", str(phase2_dir),
        ], cwd=ENGINE_DIR)

        _run_step([
            str(ENGINE_DIR / "03_schematic_layout.py"),
            "--phase2-dir", str(phase2_dir),
            "--out-dir", str(phase3_dir),
        ], cwd=ENGINE_DIR)

        _run_step([
            str(ENGINE_DIR / "04_export_frontend_data.py"),
            "--phase3-dir", str(phase3_dir),
            "--out-js", str(out_js),
        ], cwd=ENGINE_DIR)

        elements = _parse_js_elements_file(out_js)
        nodes, edges = _cytoscape_elements_to_nw_format(elements)

    resp = requests.post(
        f"{SUPABASE_URL}/rest/v1/rpc/nw_save_diagram_engine",
        headers={
            "apikey": SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "p_tambon_id": req.tambon_id,
            "p_label": req.label,
            "p_entered_by": req.entered_by,
            "p_nodes": nodes,
            "p_edges": edges,
        },
        timeout=30,
    )
    if resp.status_code >= 300:
        raise HTTPException(status_code=502, detail=f"Supabase publish ล้มเหลว: {resp.status_code} {resp.text}")

    return {
        "n_nodes": len(nodes),
        "n_edges": len(edges),
        "supabase_response": resp.json(),
    }
