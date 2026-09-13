from __future__ import annotations

import hmac
import os
import time
from datetime import date, datetime, time as day_time
from pathlib import Path

import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

import database as db
from core import NETWORKS, match_cdr, parse_ids, prepare_cdr, prepare_gmon, read_table
from maps import build_map

st.set_page_config(page_title="INTEL | ศูนย์วิเคราะห์พิกัด", page_icon="◈", layout="wide")
st.markdown('<style>' + Path(__file__).with_name('fonts.css').read_text(encoding='utf-8') + '</style>', unsafe_allow_html=True)
st.markdown('<style>' + Path(__file__).with_name('style.css').read_text(encoding='utf-8') + '</style>', unsafe_allow_html=True)
DEMO = os.getenv("INTEL_DEMO") == "1"


def reset_cdr():
    for key in ("cdr_events", "cdr_rows", "cdr_errors"):
        st.session_state.pop(key, None)
    st.session_state["cdr_generation"] = st.session_state.get("cdr_generation", 0) + 1
    if st.session_state.get("active") == "CDR":
        st.session_state["rows"] = []
        st.session_state["related"] = []
        st.session_state["active"] = "ค้นหา"
        st.session_state.pop("result_notice", None)
    st.session_state["map_revision"] = st.session_state.get("map_revision", 0) + 1
    for key in list(st.session_state):
        if key.startswith("viewport_"):
            del st.session_state[key]


def logout():
    # All session analysis is dropped, including any parsed uploads.
    for key in list(st.session_state):
        del st.session_state[key]


try:
    secret_password = st.secrets.get("APP_PASSWORD", "")
except (FileNotFoundError, st.errors.StreamlitSecretNotFoundError):
    secret_password = ""

if not DEMO and not st.session_state.get("authenticated"):
    _, middle, _ = st.columns([1, 1.2, 1])
    with middle:
        st.markdown('<div class="login-brand"><div class="eyebrow">INTELLIGENCE WORKSPACE</div><h1>INTEL<span> / </span>เข้าสู่ระบบ</h1><p>ศูนย์วิเคราะห์พิกัดสัญญาณและลำดับเหตุการณ์</p></div>', unsafe_allow_html=True)
        if not secret_password:
            st.info("พร้อมติดตั้ง — กรุณาตั้งค่า APP_PASSWORD และ database ใน Streamlit Secrets ตามคู่มือ")
        with st.form("login"):
            password = st.text_input("รหัสผ่านองค์กร", type="password")
            submitted = st.form_submit_button("เข้าสู่พื้นที่วิเคราะห์ →", type="primary", width="stretch")
        if submitted:
            if secret_password and hmac.compare_digest(password.encode(), str(secret_password).encode()):
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("เข้าสู่ระบบไม่สำเร็จ กรุณาตรวจรหัสผ่านและการตั้งค่า")
    st.stop()


@st.cache_resource
def get_engine():
    return db.connect(dict(st.secrets["database"]))


@st.cache_data(ttl=30)
def check_database(_engine):
    return db.health(_engine)


engine, ready, connection_label = None, False, "ยังไม่เชื่อมต่อ"
if not DEMO:
    try:
        engine = get_engine()
        ready = check_database(engine)
        connection_label = "Cloud SQL พร้อมใช้งาน" if ready else "เชื่อมต่อแล้ว · รอติดตั้งตาราง"
    except Exception:
        connection_label = "Cloud SQL ยังไม่พร้อม"
else:
    connection_label = "ตัวอย่างสังเคราะห์ · ไม่เชื่อมฐานข้อมูล"

for key, default in {"rows": [], "related": [], "active": "ค้นหา", "map_revision": 0,
                     "cdr_generation": 0, "elapsed": None}.items():
    if key not in st.session_state:
        st.session_state[key] = default

top_left, top_right = st.columns([5, 2])
with top_left:
    st.markdown('<div class="eyebrow">TACTICAL CELL ANALYSIS SYSTEM</div><div class="brand">INTEL <span>/</span> ศูนย์วิเคราะห์พิกัด</div>', unsafe_allow_html=True)
with top_right:
    st.caption(("● " if ready else "○ ") + connection_label)
    if not DEMO:
        st.button("ออกจากระบบ", on_click=logout, width="stretch")

st.markdown('<div class="hero"><div><div class="eyebrow">พื้นที่ปฏิบัติงาน / 01</div><h1>เชื่อมข้อมูล เห็นลำดับเหตุการณ์</h1><p>ค้นหาพิกัดจากการสำรวจภาคสนาม และตรวจสอบเหตุการณ์ CDR ในพื้นที่เดียว</p></div><div class="hero-tag">G-MON เป็นหลัก<br><span>CDR เป็นพิกัดสำรอง</span></div></div>', unsafe_allow_html=True)
if DEMO:
    st.info("โหมดตัวอย่าง: ทุกจุดเป็นข้อมูลสังเคราะห์สำหรับตรวจหน้าตาเท่านั้น ไม่มีการเขียนฐานข้อมูล")
elif not ready:
    st.warning("ยังค้นหาหรือนำเข้าฐานข้อมูลไม่ได้ กรุณาตรวจ Secrets, การเชื่อมต่อ และติดตั้ง schema.sql ตามคู่มือ")


def demo_rows():
    return [dict(plmn="52003", xci=str(70000000 + i), lac="55000", xnbid="273437",
                 lat=7.01 + .009 * i, lon=100.47 + .012 * i, observed_at=datetime(2026, 8, 30, 10, i),
                 source="G-Mon", rsrp=-85-i*3) for i in range(5)]


def do_search(cells, lacs, nbids, plmns, bounds=None):
    if DEMO:
        rows = demo_rows()
        return [r for r in rows if (not cells or r["xci"] in cells) and (not lacs or r["lac"] in lacs)
                and (not nbids or r["xnbid"] in nbids) and (not plmns or r["plmn"] in plmns)
                and (not bounds or bounds["south"] <= r["lat"] <= bounds["north"] and bounds["west"] <= r["lon"] <= bounds["east"])], False
    return db.search(engine, cells, lacs, nbids, plmns, bounds)


with st.container(border=True):
    st.markdown('<div class="section-title">01 <span>ค้นหาพิกัดภาคสนาม</span></div>', unsafe_allow_html=True)
    with st.form("search"):
        c1, c2, c3, c4 = st.columns([2, 2, 2, 1.6])
        cell_text = c1.text_input("CELL / XCI", placeholder="เช่น 30020114")
        lac_text = c2.text_input("LAC / TAC", placeholder="เช่น 55653")
        nbid_text = c3.text_input("xNBID", placeholder="ค้นหาเสาหลัก")
        network = c4.selectbox("PLMN", ["ทุกเครือข่าย"] + list(NETWORKS), format_func=lambda x: f"{NETWORKS[x]} · {x}" if x in NETWORKS else x)
        st.caption("กรอกอย่างน้อยหนึ่งช่อง · หลายรหัสคั่นด้วยจุลภาค · หลายช่องใช้เงื่อนไขร่วมกัน · เลือกพิกัดล่าสุดของแต่ละ PLMN/CELL/LAC")
        scan = st.form_submit_button("ค้นหาพิกัด →", type="primary", disabled=not (ready or DEMO), width="stretch")
    if scan:
        try:
            cells, lacs, nbids = parse_ids(cell_text), parse_ids(lac_text), parse_ids(nbid_text)
            if not any([cells, lacs, nbids]):
                raise ValueError("กรุณากรอก CELL, LAC หรือ xNBID อย่างน้อยหนึ่งช่อง")
            begin = time.perf_counter()
            with st.spinner("กำลังค้นหาพิกัดล่าสุด…"):
                rows, limited = do_search(cells, lacs, nbids, [] if network == "ทุกเครือข่าย" else [network])
            st.session_state.update(rows=rows, related=[], active="ค้นหา", elapsed=time.perf_counter()-begin)
            st.session_state.result_notice = ("warning", "ผลเกิน 2,000 จุด แสดงเฉพาะ 2,000 จุดล่าสุด กรุณาระบุเงื่อนไขให้แคบลง") if limited else ("info", f"ผลค้นหา {len(rows):,} จุด")
            st.session_state.map_revision += 1
            if limited:
                st.warning("ผลเกิน 2,000 จุด แสดงเฉพาะ 2,000 จุดล่าสุด กรุณาระบุเงื่อนไขให้แคบลง")
            if not rows:
                st.info("ไม่พบข้อมูลที่ตรงกับเงื่อนไข")
        except ValueError as exc:
            st.error(str(exc))
        except Exception:
            st.error("ค้นหาไม่สำเร็จ กรุณาตรวจการเชื่อมต่อฐานข้อมูลแล้วลองใหม่")

workspace = st.container()

with st.expander("ค้นหาพื้นที่ด้วยกรอบพิกัด"):
    st.caption("ใช้ขอบเขตละติจูด/ลองจิจูดของพื้นที่ที่ทราบ ไม่ส่งพิกัดไปบริการค้นหาที่อยู่ภายนอก")
    with st.form("area"):
        a, b, c, d = st.columns(4)
        south = a.number_input("ใต้", -90., 90., 6.9, format="%.5f")
        north = b.number_input("เหนือ", -90., 90., 7.2, format="%.5f")
        west = c.number_input("ตะวันตก", -180., 180., 100.3, format="%.5f")
        east = d.number_input("ตะวันออก", -180., 180., 100.7, format="%.5f")
        area_scan = st.form_submit_button("ค้นหาภายในพื้นที่", disabled=not (ready or DEMO))
    if area_scan:
        if south >= north or west >= east:
            st.error("ขอบเขตพื้นที่ไม่ถูกต้อง")
        else:
            try:
                rows, limited = do_search([], [], [], [], dict(south=south, north=north, west=west, east=east))
                st.session_state.update(rows=rows, related=[], active="พื้นที่")
                st.session_state.result_notice = ("warning", "แสดงไม่เกิน 2,000 จุด กรุณาลดขอบเขตพื้นที่") if limited else ("info", f"ผลค้นหาพื้นที่ {len(rows):,} จุด")
                st.session_state.map_revision += 1
                if limited:
                    st.warning("แสดงไม่เกิน 2,000 จุด กรุณาลดขอบเขตพื้นที่")
            except Exception:
                st.error("ค้นหาพื้นที่ไม่สำเร็จ กรุณาตรวจการเชื่อมต่อ")

with st.expander("เพิ่มข้อมูล G-Mon Pro · เก็บถาวรในฐานข้อมูล"):
    st.caption("ทุกคนที่เข้าสู่ระบบเพิ่มข้อมูลได้ · รักษา PLMN จริงในไฟล์ · ข้อมูลเก่ายังคงอยู่")
    upload = st.file_uploader("เลือกไฟล์ G-Mon Pro", type=["csv", "txt"], key="gmon_upload")
    if upload:
        try:
            records, issues = prepare_gmon(read_table(upload.getvalue(), upload.name))
            st.caption(f"ใช้ได้ {len(records):,} แถว · ผิดรูปแบบ {len(issues):,} แถว")
            if records:
                preview = pd.DataFrame(records).drop(columns=["raw", "fingerprint"])
                st.dataframe(preview.head(20), hide_index=True, width="stretch")
            if not issues.empty:
                st.dataframe(issues, hide_index=True, width="stretch")
            accept_partial = st.checkbox("ยืนยันบันทึกเฉพาะแถวที่ผ่านการตรวจ", value=False) if not issues.empty else True
            if st.button("บันทึก G-Mon เข้าฐานข้อมูล", type="primary", disabled=not (ready and records and accept_partial)):
                with st.spinner("กำลังบันทึกข้อมูล…"):
                    added, duplicate = db.save_gmon(engine, records)
                st.session_state.upload_notice = f"เพิ่ม {added:,} แถว · ข้ามรายการซ้ำ {duplicate:,} แถว · พร้อมค้นหาใหม่ทันที"
        except ValueError as exc:
            st.error(str(exc))
        except Exception:
            st.error("อ่านหรือบันทึกไฟล์ไม่สำเร็จ ไม่มีการบันทึกบางส่วน กรุณาตรวจรูปแบบไฟล์และฐานข้อมูล")
    if st.session_state.get("upload_notice"):
        st.success(st.session_state.upload_notice)
    if ready and st.secrets.get("ENABLE_LEGACY_MIGRATION", False):
        st.divider()
        st.caption("งานติดตั้ง: คัดลอกข้อมูลจากตารางเดิมโดยไม่แก้ไขหรือลบต้นฉบับ")
        if st.button("ย้ายข้อมูล G-Mon เดิมเข้าระบบใหม่"):
            from sqlalchemy import text
            try:
                progress = st.empty()
                total = added = skipped = invalid = 0
                with engine.connect().execution_options(stream_results=True) as conn:
                    for chunk in pd.read_sql(text("SELECT * FROM gmon_survey_logs"), conn, chunksize=2000):
                        chunk.columns = [str(c).strip().lower() for c in chunk.columns]
                        records, issues = prepare_gmon(chunk.reset_index(drop=True))
                        count_added, count_skipped = db.save_gmon(engine, records)
                        total += len(chunk)
                        added += count_added
                        skipped += count_skipped
                        invalid += len(issues)
                        progress.info(f"ตรวจแล้ว {total:,} แถว · เพิ่ม {added:,} · ซ้ำ {skipped:,} · ใช้ไม่ได้ {invalid:,}")
                st.session_state.upload_notice = f"ย้ายข้อมูลเสร็จ: ตรวจ {total:,} แถว · เพิ่ม {added:,} · ซ้ำ {skipped:,} · ใช้ไม่ได้ {invalid:,}"
                st.success(st.session_state.upload_notice)
            except Exception:
                st.error("ย้ายข้อมูลยังไม่ครบ ตารางเดิมไม่เปลี่ยน สามารถรันซ้ำเพื่อทำต่อได้")

with st.expander("วิเคราะห์ CDR · ใช้ชั่วคราว ไม่บันทึกฐานข้อมูล", expanded=False):
    st.caption("เก็บเฉพาะข้อมูลวิเคราะห์ในเซสชันนี้ · เวลาเหตุการณ์ใช้ Start Date · ไม่เก็บเบอร์โทร IMSI หรือ IMEI ในผลวิเคราะห์")
    cdr = st.file_uploader("เลือกไฟล์ CDR", type=["csv", "txt", "xlsx"], key=f"cdr_upload_{st.session_state.cdr_generation}")
    with st.form("cdr_options"):
        cdr_network = st.selectbox("เครือข่ายของ CDR (ถ้าทราบ)", ["ไม่ระบุ"] + list(NETWORKS), format_func=lambda x: f"{NETWORKS[x]} · {x}" if x in NETWORKS else x)
        filter_time = st.checkbox("กรองช่วงเวลาเหตุการณ์", value=False)
        a, b, c, d = st.columns(4)
        start_day = a.date_input("วันที่เริ่ม", date.today())
        start_time = b.time_input("เวลาเริ่ม", day_time(0, 0))
        end_day = c.date_input("วันที่สิ้นสุด", date.today())
        end_time = d.time_input("เวลาสิ้นสุด", day_time(23, 59, 59))
        analyze = st.form_submit_button("วิเคราะห์บนแผนที่ →", type="primary", disabled=not (ready or DEMO))
    st.button("ล้างไฟล์และผล CDR", on_click=reset_cdr)
    if analyze:
        if cdr is None:
            st.warning("กรุณาเลือกไฟล์ CDR")
        else:
            try:
                events, errors = prepare_cdr(read_table(cdr.getvalue(), cdr.name))
                if filter_time:
                    start, end = datetime.combine(start_day, start_time), datetime.combine(end_day, end_time)
                    if start > end:
                        raise ValueError("เวลาเริ่มต้องไม่เกินเวลาสิ้นสุด")
                    if not events.empty:
                        events = events[events.event_at.between(start, end)]
                if events.empty:
                    raise ValueError("ไม่มีเหตุการณ์ที่อ่านได้ในช่วงเวลานี้")
                if len(events) > 5000:
                    raise ValueError("มีเกิน 5,000 เหตุการณ์ กรุณากรองช่วงเวลาให้แคบลง")
                with st.spinner("กำลังจับคู่ CELL/LAC กับ G-Mon…"):
                    candidates = demo_rows() if DEMO else db.lookup_pairs(engine, list(zip(events.xci, events.lac)), [] if cdr_network == "ไม่ระบุ" else [cdr_network])
                    if DEMO and cdr_network != "ไม่ระบุ":
                        candidates = [r for r in candidates if r["plmn"] == cdr_network]
                    result = match_cdr(events, candidates)
                st.session_state.update(rows=result, related=[], active="CDR", cdr_rows=result, cdr_errors=errors)
                st.session_state.result_notice = ("success", f"วิเคราะห์ {len(events):,} เหตุการณ์ · แถวที่อ่านไม่ได้ {len(errors):,}")
                st.session_state.map_revision += 1
                st.success(f"วิเคราะห์ {len(events):,} เหตุการณ์ · แถวที่อ่านไม่ได้ {len(errors):,}")
            except ValueError as exc:
                st.error(str(exc))
            except Exception:
                st.error("วิเคราะห์ไม่สำเร็จ กรุณาตรวจไฟล์และการเชื่อมต่อ ไม่มีการบันทึก CDR ลงฐานข้อมูล")
    if "cdr_errors" in st.session_state and not st.session_state.cdr_errors.empty:
        st.dataframe(st.session_state.cdr_errors, hide_index=True, width="stretch")

with workspace:
    if st.session_state.get("result_notice"):
        notice_type, notice_text = st.session_state.result_notice
        getattr(st, notice_type)(notice_text)
    rows = st.session_state.rows
    if DEMO and not rows and st.session_state.map_revision == 0:
        rows = demo_rows()
        st.session_state.rows = rows
    valid_count = sum(r.get("lat") is not None for r in rows)
    fallback_count = sum(r.get("source") == "CDR สำรอง" for r in rows)
    ambiguous_count = len({r.get("event_id") for r in rows if r.get("ambiguous")})
    metrics = st.columns(4)
    metrics[0].metric("พิกัดที่แสดง", f"{valid_count:,}")
    metrics[1].metric("G-Mon ภาคสนาม", f"{sum(r.get('source', 'G-Mon') == 'G-Mon' for r in rows):,}")
    metrics[2].metric("CDR สำรอง", f"{fallback_count:,}")
    metrics[3].metric("เหตุการณ์รอเลือก PLMN", f"{ambiguous_count:,}")
    
    map_col, details_col = st.columns([3.4, 1.2], gap="medium")
    with map_col:
        st.markdown('<div class="section-title">02 <span>แผนที่วิเคราะห์</span><small> FIELD INTELLIGENCE</small></div>', unsafe_allow_html=True)
        st.caption("● G-Mon สีเขียวฟ้า  ·  ● CDR สำรองสีอำพัน  ·  ● หลาย PLMN สีม่วง")
        with st.expander("ตั้งค่าการแสดงผลแผนที่"):
            a, b = st.columns(2)
            draw_path = a.checkbox("เส้นเชื่อมและเล่นเหตุการณ์ CDR", value=True, disabled=st.session_state.active != "CDR")
            draw_sector = b.checkbox("เปิด Sector จำลอง", value=False)
            a, b, c = st.columns(3)
            azimuth = a.text_input("ทิศจำลอง (0–359°)", placeholder="กรอกเอง เช่น 90")
            radius = b.number_input("รัศมีจำลอง (เมตร)", 10, 20000, 1000, 100)
            beam = c.number_input("ความกว้าง (องศา)", 1, 360, 90)
            bearing = None
            if azimuth.strip():
                try:
                    bearing = float(azimuth)
                    if not 0 <= bearing < 360:
                        raise ValueError()
                except ValueError:
                    st.warning("ทิศต้องเป็นตัวเลขตั้งแต่ 0 ถึงน้อยกว่า 360")
                    bearing = None
            if draw_sector:
                st.caption("ใช้ทิศเดียวตามที่กรอกกับจุดที่แสดง เป็นภาพจำลอง ไม่ใช่ทิศเสาจริง")
                if bearing is None:
                    st.info("กรอกทิศก่อนจึงจะแสดงรูปพัด")
            related_on = st.checkbox("แสดง CELL อื่นร่วม PLMN/xNBID (ไม่ทราบทิศ Sector)")
            if st.button("โหลด CELL ร่วม NBID", disabled=not (ready and rows and related_on)):
                try:
                    groups = {(r.get("plmn"), r.get("xnbid")) for r in rows if r.get("xnbid") and r.get("plmn")}
                    if len(groups) > 30:
                        st.warning("กรุณาลดผลค้นหาให้เหลือไม่เกิน 30 NBID ก่อนโหลดจุดเพิ่มเติม")
                    else:
                        main_keys = {(r.get("plmn"), r.get("xci"), r.get("lac")) for r in rows}
                        found, clipped = {}, False
                        for plmn, nbid in sorted(groups):
                            extra, limited = db.search(engine, nbids=[nbid], plmns=[plmn], limit=1000)
                            clipped |= limited
                            for r in extra:
                                key = (r["plmn"], r["xci"], r["lac"])
                                if key not in main_keys:
                                    found[key] = r
                        st.session_state.related = list(found.values())[:2000]
                        if clipped or len(found) > 2000:
                            st.warning("จำกัดจุดเพิ่มเติมไว้ไม่เกิน 2,000 จุด บางกลุ่มอาจแสดงไม่ครบ")
                except Exception:
                    st.error("โหลดจุดร่วม NBID ไม่สำเร็จ")
        revision = st.session_state.map_revision
        state_key = f"viewport_{revision}"
        for old_key in list(st.session_state):
            if old_key.startswith("viewport_") and old_key != state_key:
                del st.session_state[old_key]
        viewport = st.session_state.get(state_key, {})
        center = viewport.get("center")
        center = [center["lat"], center["lng"]] if isinstance(center, dict) else None
        map_obj = build_map(rows, center=center, zoom=viewport.get("zoom", 7), fit=center is None,
                            sector=draw_sector, bearing=bearing, radius=radius, beam=beam,
                            path=draw_path and st.session_state.active == "CDR",
                            related=st.session_state.related if related_on else [])
        interaction = st_folium(map_obj, height=570, use_container_width=True, key=f"map_{revision}",
                                returned_objects=["center", "zoom"])
        if interaction and interaction.get("center"):
            st.session_state[state_key] = interaction
        st.caption("พิกัด G-Mon คือจุดเก็บสัญญาณภาคสนาม · เส้นแสดงลำดับเหตุการณ์ ไม่ยืนยันเส้นทางเดินทางจริง")
    
    with details_col:
        st.markdown('<div class="section-title">03 <span>ผลวิเคราะห์</span></div>', unsafe_allow_html=True)
        st.caption("โหมด: " + st.session_state.active)
        if not DEMO and st.session_state.elapsed is not None and st.session_state.active == "ค้นหา":
            st.caption(f"ค้นหาฐานข้อมูล {st.session_state.elapsed:.2f} วินาที")
        if not rows:
            st.markdown('<div class="empty-state"><b>เริ่มจากรหัสที่คุณมี</b><p>ค้นหา CELL, LAC หรือ xNBID<br>หรืออัปโหลด CDR เพื่อเรียงเหตุการณ์</p></div>', unsafe_allow_html=True)
        else:
            if ambiguous_count:
                st.warning("มีหลาย PLMN ตรงกัน เหตุการณ์เหล่านี้ไม่ถูกนำไปเชื่อมเส้น กรุณาเลือกเครือข่ายแล้ววิเคราะห์ใหม่")
            event_rows = rows[:40]
            with st.container(height=590, border=False):
                for i, row in enumerate(event_rows):
                    with st.container(border=True):
                        st.caption(f"{i+1:02d} / {row.get('source', 'G-Mon')}")
                        st.write(f"CELL {row['xci']}")
                        st.caption(f"LAC {row['lac']} · PLMN {row.get('plmn') or 'ไม่ระบุ'}")
                        st.caption(str(row.get("event_at", row.get("observed_at", ""))))
            if len(rows) > 40:
                st.caption("แสดงการ์ด 40 รายการแรก ดูรายการทั้งหมดในตารางด้านล่าง")
    
    if rows:
        with st.expander("ตารางผลทั้งหมด", expanded=False):
            table = pd.DataFrame(rows)
            columns = [c for c in ["event_id", "event_at", "source", "plmn", "xci", "lac", "xnbid", "lat", "lon", "observed_at", "status"] if c in table.columns]
            st.dataframe(table[columns], hide_index=True, width="stretch")
    

st.markdown('<div class="footer">INTEL / พื้นที่วิเคราะห์ภายในองค์กร <span>G-Mon เก็บถาวร · CDR ใช้เฉพาะเซสชัน</span></div>', unsafe_allow_html=True)
