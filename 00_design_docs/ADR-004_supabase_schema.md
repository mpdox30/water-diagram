# ADR-004: Schema Supabase สำหรับ Phase 5 (Export & Sync ผังน้ำชุมชน)

**สถานะ**: ร่าง (Draft) — รอ Ton ยืนยันก่อน apply จริง
**วันที่**: 30 ส.ค. 2569
**ผู้ตัดสินใจ**: Ton
**อ้างอิง**: ADR-001 (สถาปัตยกรรม Serverless: GitHub Pages + Supabase), ADR-002 (เอนจินเขียนใหม่),
`SHARED_SUPABASE_PROJECT_RULES.md` (กติกาการใช้ project ร่วมกับระบบติดตามน้ำตำบลแม่นาเรือที่มีอยู่แล้ว)

## บริบท (Context)

Phase 4 (frontend เชื่อม engine เสร็จแล้ว, Ton ทดสอบใช้งานผ่านแล้ว) — ขั้นต่อไปตาม ADR-001 action item
2/3/5 คือทำให้ `03_frontend/index.html` โหลด/บันทึกข้อมูลจริงผ่าน Supabase แทนไฟล์ `.js` local และ
ปุ่ม "บันทึกผังน้ำชุมชน" ที่ตอนนี้ดาวน์โหลดเป็นไฟล์ .json ลงเครื่องเท่านั้น

Project Supabase ที่ใช้ (`khfixycxjwxcpayiwxap`) เป็น project ที่ใช้ร่วมกับระบบติดตามสถานการณ์น้ำของตำบล
แม่นาเรือที่มีผู้ใช้จริงอยู่แล้ว (ตรวจสอบ schema จริงแล้วตรงกับ `SHARED_SUPABASE_PROJECT_RULES.md` ทุก
ตาราง/ฟังก์ชัน/extension — postgis **ยังไม่ได้ติดตั้ง**, มีตำบลเดียวคือ "แม่นาเรือ" ใน `public.tambons`)
งานผังน้ำ (โปรเจกต์ที่สอง) ต้องสร้างของใหม่แยกจากของเดิมทั้งหมดตามกติกาในเอกสารนั้น

พบด้วยว่าระบบเดิมมีกลไก "รหัสผ่านต่อตำบล" อยู่แล้ว: `tambons.villager_form_password_hash` /
`manager_tab_password_hash` ตรวจสอบผ่านฟังก์ชัน `public.check_gate_password(tambon_id, gate, password)`
(SECURITY DEFINER, ใช้ `pgcrypto.crypt()`) — Ton ยืนยันให้ใช้รหัส `villager_form` ร่วมกับแบบฟอร์มกรอก
ระดับน้ำเดิมสำหรับสิทธิ์แก้ไขผังน้ำของชุมชนเลย (ไม่ต้องเพิ่มคอลัมน์รหัสผ่านใหม่)

**ประเด็นที่ยังไม่ปิด**: `นครป่าหมาก` (ตำบลต้นแบบของงานผังน้ำ) ยังไม่มีแถวใน `public.tambons` — ตารางนี้
อยู่ในรายการ "ห้ามแตะ" (หัวข้อ A) ต้องขอความยินยอมเป็นลายลักษณ์อักษรก่อน insert แถวใหม่ (Ton กำลังจะถาม
เพิ่มเติมก่อนตัดสินใจ — ยังไม่ apply อะไรจนกว่าจะได้คำตอบ)

## การตัดสินใจ (Decision — ร่าง)

สร้าง schema ใหม่ชื่อ `nw` (water network) แยกจาก `public` ทั้งหมด อ้างอิงตำบลด้วย FK
`tambon_id uuid references public.tambons(tambon_id)` เท่านั้น (ไม่ copy ข้อมูลตำบลซ้ำ) เก็บผังน้ำแบบ
**append-only version log** (ทุกครั้งที่ publish จาก engine หรือชุมชนบันทึกแก้ไข = สร้าง version ใหม่
เสมอ ไม่ overwrite ของเดิม — ตรงกับหลักการ "ห้ามทับไฟล์เดิม" ที่ Ton วางไว้ตั้งแต่ Phase 3)

### ตาราง

```sql
create schema if not exists nw;

-- 1 แถวต่อการ publish/บันทึกผังน้ำ 1 ครั้ง (จาก engine หรือจากชุมชนกดปุ่มบันทึก)
create table nw.diagram_versions (
    version_id     uuid primary key default gen_random_uuid(),
    tambon_id      uuid not null references public.tambons(tambon_id),
    source         text not null check (source in ('engine', 'community')),
    label          text,                    -- เช่น "phase3_schematic_v2" หรือ note จากชุมชน
    entered_by     text,                    -- ชื่อ/หมายเหตุผู้บันทึก (จากชุมชน) — engine เว้นว่างได้
    is_current     boolean not null default false,  -- ตัวที่ frontend โหลดตอนเปิดหน้าเว็บ
    created_at     timestamptz not null default now()
);

-- จุดต่อของผัง ณ version นั้น ๆ (mirror ฟอร์แมต element ของ Cytoscape.js)
create table nw.diagram_nodes (
    version_id     uuid not null references nw.diagram_versions(version_id) on delete cascade,
    node_key       text not null,           -- id ฝั่ง Cytoscape เช่น "n0", "n_new_12"
    label          text default '',
    node_type      text,                    -- gate/weir/reservoir/waterbody/generic_node/... หรือ null
    rotation       integer default 0,
    dir            text default 'h',
    pos_x          double precision not null,
    pos_y          double precision not null,
    primary key (version_id, node_key)
);

-- เส้นเชื่อมของผัง ณ version นั้น ๆ
create table nw.diagram_edges (
    version_id       uuid not null references nw.diagram_versions(version_id) on delete cascade,
    edge_key         text not null,         -- id ฝั่ง Cytoscape เช่น "e0", "e_new_5"
    source_node_key  text not null,
    target_node_key  text not null,
    label            text default '',
    edge_type        text,                  -- 'main' / 'branch'
    engine_straight  boolean,
    engine_bend      boolean,
    seg_dist         double precision,
    seg_weight       double precision,
    primary key (version_id, edge_key),
    foreign key (version_id, source_node_key) references nw.diagram_nodes(version_id, node_key),
    foreign key (version_id, target_node_key) references nw.diagram_nodes(version_id, node_key)
);

create index on nw.diagram_versions (tambon_id, is_current);
```

### RLS (บังคับตามหัวข้อ C ของกติกา)

- `nw.diagram_versions` / `nw.diagram_nodes` / `nw.diagram_edges`: **เปิด RLS + policy `select` ให้
  `anon`/`authenticated` อ่านได้** (ผังน้ำเป็นข้อมูลสาธารณะที่ชุมชนต้องดูได้โดยไม่ต้อง login) — แต่
  **ไม่มี policy สำหรับ insert/update/delete เลย** (default-deny ฝั่งเขียน) การเขียนทุกครั้งต้องผ่าน
  ฟังก์ชัน `SECURITY DEFINER` ด้านล่างเท่านั้น ตรงกับ pattern เดียวกับ `submit_water_level_reading`

### ฟังก์ชัน (SECURITY DEFINER, ตรวจรหัสผ่านผ่าน `check_gate_password` เดิม)

```sql
create or replace function nw.save_diagram(
    p_tambon_id  uuid,
    p_password   text,
    p_source     text,      -- 'engine' หรือ 'community'
    p_label      text,
    p_entered_by text,
    p_nodes      jsonb,     -- [{node_key,label,node_type,rotation,dir,pos_x,pos_y}, ...]
    p_edges      jsonb      -- [{edge_key,source_node_key,target_node_key,label,edge_type,
                             --   engine_straight,engine_bend,seg_dist,seg_weight}, ...]
) returns jsonb
language plpgsql security definer set search_path = public, nw, extensions as $$
declare
    v_ok boolean;
    v_version_id uuid;
begin
    if p_source = 'community' then
        select public.check_gate_password(p_tambon_id, 'villager_form', p_password) into v_ok;
        if not v_ok then
            return jsonb_build_object('success', false, 'error', 'invalid_password');
        end if;
    elsif p_source != 'engine' then
        return jsonb_build_object('success', false, 'error', 'invalid_source');
    end if;
    -- p_source = 'engine' เรียกผ่าน script ฝั่งผู้ดูแล (service_role) เท่านั้น ไม่ต้องเช็ครหัสผ่าน

    insert into nw.diagram_versions (tambon_id, source, label, entered_by)
    values (p_tambon_id, p_source, p_label, p_entered_by)
    returning version_id into v_version_id;

    insert into nw.diagram_nodes (version_id, node_key, label, node_type, rotation, dir, pos_x, pos_y)
    select v_version_id, x.node_key, x.label, x.node_type, x.rotation, x.dir, x.pos_x, x.pos_y
    from jsonb_to_recordset(p_nodes) as x(
        node_key text, label text, node_type text, rotation int, dir text,
        pos_x double precision, pos_y double precision);

    insert into nw.diagram_edges (version_id, edge_key, source_node_key, target_node_key, label,
        edge_type, engine_straight, engine_bend, seg_dist, seg_weight)
    select v_version_id, x.edge_key, x.source_node_key, x.target_node_key, x.label, x.edge_type,
        x.engine_straight, x.engine_bend, x.seg_dist, x.seg_weight
    from jsonb_to_recordset(p_edges) as x(
        edge_key text, source_node_key text, target_node_key text, label text, edge_type text,
        engine_straight boolean, engine_bend boolean, seg_dist double precision,
        seg_weight double precision);

    update nw.diagram_versions set is_current = false where tambon_id = p_tambon_id;
    update nw.diagram_versions set is_current = true where version_id = v_version_id;

    return jsonb_build_object('success', true, 'version_id', v_version_id);
end;
$$;

revoke execute on function nw.save_diagram from anon, authenticated;
grant execute on function nw.save_diagram to anon;  -- เรียกผ่าน RPC ตรง ตรวจรหัสผ่านในฟังก์ชันเอง
```

*(หมายเหตุ: `grant ... to anon` ดูขัดกับสัญชาตญาณ แต่เป็น pattern เดียวกับ `submit_water_level_reading`
ที่มีอยู่แล้ว — ฟังก์ชันเป็น public แต่ตรวจรหัสผ่านเองข้างในก่อนเขียนข้อมูลเสมอ ปลอดภัยเพราะไม่มีทางเขียน
ผ่านทางอื่นได้เลยจาก RLS ข้างบน)*

### Frontend (`03_frontend/index.html`)

- โหลดตอนเปิดหน้า: query `nw.diagram_nodes`/`nw.diagram_edges` ของ version ที่ `is_current = true`
  ของ `tambon_id` นั้น ผ่าน Supabase JS client (`select` ตรง อ่านได้เพราะ RLS อนุญาต) แทนการอ่านไฟล์
  `data/nakhon_pa_mak.js`
- ปุ่ม "บันทึกผังน้ำชุมชน" (`exportData()`): เปลี่ยนจากดาวน์โหลดไฟล์ .json เป็นเรียก
  `supabase.rpc('save_diagram', {...})` พร้อม prompt ถามรหัสผ่าน (`villager_form`) ก่อนส่ง
- Engine publish (`04_export_frontend_data.py`): เพิ่มโหมด `--publish-to-supabase` เรียก
  `save_diagram` ด้วย `source='engine'` ผ่าน `service_role` key (รันจากเครื่อง ไม่ฝัง key ใน
  frontend) แทน/เพิ่มเติมจากการเขียนไฟล์ `.js` local (คงไฟล์ local ไว้เป็น fallback/offline ก่อน internet)

## ทางเลือกที่พิจารณา

### ทางเลือก A: เก็บผัง "ปัจจุบัน" แถวเดียวต่อตำบล (UPDATE ทับ)
ง่ายกว่า แต่ขัดกับหลักการ "ห้ามทับไฟล์เดิม" ที่ Ton วางไว้ชัดเจนตั้งแต่ Phase 3 (ทุกผลลัพธ์ต้องกู้คืนย้อนหลังได้)
และเสี่ยงข้อมูลหายถ้าชุมชนบันทึกผิดพลาด — **ไม่เลือก**

### ทางเลือก B (แนะนำ): Append-only version log ต่อ tambon (ตามดีไซน์ข้างบน)
ตรงกับหลักการเดิมของโปรเจกต์ทุกจุด (versioning ที่ใช้กับไฟล์ output ของเอนจินอยู่แล้ว) แลกมาด้วยตาราง
โตขึ้นเรื่อย ๆ ตามจำนวนครั้งที่บันทึก — แต่ข้อมูลผังน้ำ 1 ตำบลมีขนาดเล็กมาก (41 node/46 edge ระดับ
กิโลไบต์) ไม่ใช่ปัญหาจริงในสเกลนี้

### ทางเลือก C: ใช้ Supabase Storage เก็บไฟล์ .json ทั้งไฟล์ (ไม่แยกตาราง node/edge)
ง่ายกว่ามาก (ไม่ต้อง parse/normalize) แต่ query/join ยาก (เช่นถ้าอนาคตอยากดูสถิติ "เส้นไหนถูกแก้บ่อย
ที่สุด" ทำไม่ได้) และไม่ใช้ประโยชน์จาก Postgres/RLS ที่มีอยู่แล้วเต็มที่ — เก็บไว้เป็นทางเลือกสำรองถ้า
ทางเลือก B ซับซ้อนเกินไปในทางปฏิบัติ

## ผลที่ตามมา

**ง่ายขึ้น**: ชุมชนหลายคนดู/แก้ผังพร้อมกันได้จริง (ไม่ต้องส่งไฟล์กันเอง), มีประวัติย้อนหลังทุกเวอร์ชัน,
ใช้ระบบรหัสผ่านต่อตำบลที่มีอยู่แล้วโดยไม่ต้องสร้างระบบ auth ใหม่

**ยากขึ้น**: ต้องมี logic กู้คืน version เก่า/ดู diff (ยังไม่ทำในรอบนี้ — เก็บเป็นงานอนาคต), ปุ่ม
"บันทึก" ต้อง prompt รหัสผ่านทุกครั้ง (ต่างจากเดิมที่บันทึกลงเครื่องได้เลยไม่ต้องมีรหัส)

## รายการงานถัดไป

1. [ ] **รอ Ton ตอบเรื่อง insert แถวนครป่าหมากใน `public.tambons`** (คำถามที่ Ton บอกว่าจะถามก่อน)
2. [ ] Ton ยืนยันดีไซน์ schema ข้างบน (หรือแก้ไข) ก่อน apply
3. [ ] `apply_migration`: สร้าง schema `nw` + ตาราง 3 ตัว + RLS + ฟังก์ชัน `save_diagram`
4. [ ] เพิ่ม `--publish-to-supabase` ใน `04_export_frontend_data.py`
5. [ ] แก้ `03_frontend/index.html`: โหลด/บันทึกผ่าน Supabase JS client
6. [ ] ทดสอบ end-to-end ผ่าน Playwright (โหลดผัง, บันทึกด้วยรหัสทดสอบ, โหลดใหม่แล้วเห็นของที่บันทึกไป)
7. [ ] อัปเดต README + แจ้ง Ton ตามข้อ H ของ `SHARED_SUPABASE_PROJECT_RULES.md` (บันทึกว่าเพิ่ม
   อะไรไปบ้างหลัง apply จริง)
