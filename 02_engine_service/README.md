# 02_engine_service — Backend service สำหรับรัน engine แบบ on-demand

ดู `06_web_platform/00_design_docs/ADR-005_engine_backend_service.md` สำหรับบริบท/เหตุผลทั้งหมด

## รันทดสอบในเครื่อง

```bash
cd 06_web_platform/02_engine_service
pip install -r requirements.txt
export SUPABASE_URL="https://khfixycxjwxcpayiwxap.supabase.co"
export SUPABASE_SERVICE_ROLE_KEY="<service_role key จาก Supabase dashboard > Project Settings > API>"
export ENGINE_TRIGGER_SECRET="<ตั้งค่าสุ่มยาว ๆ เอง>"
uvicorn main:app --reload --port 8000
```

ทดสอบเรียก:
```bash
curl -X POST http://localhost:8000/run-engine \
  -H "X-Engine-Secret: <ค่าเดียวกับ ENGINE_TRIGGER_SECRET>" \
  -H "Content-Type: application/json" \
  -d '{
    "tambon_id": "20451bd6-df9d-4214-b2f0-aca23f9f2d91",
    "province_th": "พิษณุโลก",
    "amphoe_th": "บางกระทุ่ม",
    "tambon_th": "นครป่าหมาก",
    "osm_geojson_filename": "nakhon_pa_mak_osm_waterways.geojson"
  }'
```

## Deploy บน Render (ขั้นตอนสำหรับ Ton)

1. Push repo `06_web_platform/` นี้ขึ้น GitHub ก่อน (ทีมพัฒนาเตรียม git commit ให้แล้ว รอ Ton สร้าง repo บน
   GitHub.com แล้ว push)
2. ที่ Render dashboard (โปรเจกต์ที่มีอยู่แล้ว หรือสร้างใหม่ก็ได้): **New > Web Service** > เลือก repo นี้
3. ตั้งค่า:
   - **Root Directory**: `06_web_platform/02_engine_service`
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Environment variables (Render dashboard > Environment):
   - `SUPABASE_URL` = `https://khfixycxjwxcpayiwxap.supabase.co`
   - `SUPABASE_SERVICE_ROLE_KEY` = คีย์ service_role จาก Supabase dashboard (**ห้ามใส่ในโค้ด/commit ลง git
     เด็ดขาด** ใส่เฉพาะใน Render environment variable เท่านั้น)
   - `ENGINE_TRIGGER_SECRET` = ตั้งค่าสุ่มยาว ๆ เอง (ใช้ป้องกันไม่ให้คนอื่นเรียก endpoint นี้เล่น ๆ)
5. Plan เลือก **Free** ก่อน (ดูเหตุผลใน ADR-005) — อัปเกรดเป็น Starter ($7/เดือน) ทีหลังได้ถ้าต้องการให้ตอบสนอง
   เร็วตลอด ไม่ต้องรอ cold start
6. Deploy แล้วทดสอบ `GET https://<service>.onrender.com/healthz` ควรได้ `{"status": "ok"}`

## ยังไม่ได้ทำ (งานต่อไป)

- หน้าเว็บ (`03_frontend/index.html`) ยังไม่มี UI เรียก endpoint นี้ — ต้องเพิ่ม session เลือกตำบลตามที่ Ton ขอ
  (แสดง loading state ระหว่างรอ engine ทำงาน)
- endpoint นี้ยังไม่เคยรันจริงเลยสักครั้ง (geopandas/pyogrio ไม่สามารถลงและทดสอบได้ใน sandbox ที่ใช้พัฒนาโค้ดนี้)
  — ต้องทดสอบจริงหลัง deploy ครั้งแรก อาจต้องแก้ dependency version ถ้ามีปัญหา build บน Render
- ยังรองรับเฉพาะตำบลที่เตรียมไฟล์ OSM ไว้ล่วงหน้าแล้วเท่านั้น (ดูข้อจำกัดใน main.py)
