from __future__ import annotations
import hmac
import os
import time
from datetime import datetime, date, time as day_time
from pathlib import Path
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium
import survey_database as db
from core import NETWORKS, network_label, paired_ids, parse_ids, prepare_cdr, prepare_gmon, read_table, match_cdr, display_time, coordinates
try:
    from core import prepare_camera
except ImportError:
    prepare_camera = None
from survey_maps import build_map

ROOT = Path(__file__).parent
st.set_page_config(page_title="วิเคราะห์พิกัด", page_icon=str(ROOT/"logo-transparent.png") if (ROOT/"logo-transparent.png").exists() else "📍", layout="wide")
for name in ("fonts.css", "style.css"):
    st.markdown('<style>' + (ROOT/name).read_text(encoding="utf-8") + '</style>', unsafe_allow_html=True)
DEMO = os.getenv("INTEL_DEMO") == "1"
if st.session_state.get("workspace_version") != 2:
    for old_key in list(st.session_state):
        if old_key != "authenticated":
            del st.session_state[old_key]
    st.session_state.workspace_version = 2


def logout():
    for key in list(st.session_state):
        del st.session_state[key]


def clear_search():
    for key in ("cell_input", "lac_input", "nbid_input"):
        st.session_state[key] = ""
    st.session_state.plmn_input = "ทุกเครือข่าย"
    st.session_state.update(rows=[], mode="ค้นหา", notice="", elapsed=None)
    st.session_state.revision += 1


def clear_cdr():
    st.session_state.cdr_generation += 1
    st.session_state.pop("cdr_errors", None)
    if st.session_state.mode == "CDR":
        st.session_state.update(rows=[], mode="ค้นหา", notice="", elapsed=None)
    st.session_state.revision += 1


try:
    password_expected = st.secrets.get("APP_PASSWORD", "")
except (FileNotFoundError, st.errors.StreamlitSecretNotFoundError):
    password_expected = ""
if not DEMO and not st.session_state.get("authenticated"):
    _, middle, _ = st.columns([1, 1.3, 1])
    with middle:
        if (ROOT/"logo-transparent.png").exists():
            st.image(str(ROOT/"logo-transparent.png"), width=110)
        st.title("วิเคราะห์พิกัด")
        st.caption("เข้าสู่พื้นที่วิเคราะห์ภายในองค์กร")
        with st.form("login"):
            password = st.text_input("รหัสผ่านองค์กร", type="password")
            login = st.form_submit_button("เข้าสู่ระบบ", type="primary", width="stretch")
        if login:
            if password_expected and hmac.compare_digest(password.encode(), str(password_expected).encode()):
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("เข้าสู่ระบบไม่สำเร็จ กรุณาตรวจรหัสผ่าน")
    st.stop()


@st.cache_resource
def engine_resource():
    return db.connect(dict(st.secrets["database"]))


@st.cache_data(ttl=30)
def health(_engine):
    return db.health(_engine)


engine, ready = None, False
if not DEMO:
    try:
        engine = engine_resource()
        ready = health(engine)
    except Exception:
        pass
for key, default in {"rows": [], "mode": "ค้นหา", "revision": 0, "cdr_generation": 0, "notice": "", "elapsed": None}.items():
    if key not in st.session_state:
        st.session_state[key] = default

left, right = st.columns([5, 2])
with left:
    if (ROOT/"logo-transparent.png").exists():
        st.image(str(ROOT/"logo-transparent.png"), width=72)
    st.markdown('<div class="eyebrow">FIELD INTELLIGENCE</div><div class="brand">วิเคราะห์พิกัด</div>', unsafe_allow_html=True)
with right:
    st.caption("● Cloud SQL พร้อมใช้งาน" if ready else "○ ตัวอย่างสังเคราะห์" if DEMO else "○ Cloud SQL ยังไม่พร้อม")
    st.button("ออกจากระบบ", on_click=logout, width="stretch")
if DEMO:
    st.info("ข้อมูลสังเคราะห์สำหรับทดสอบ · ไม่บันทึกฐานข้อมูล")
elif not ready:
    st.warning("ยังค้นหาหรือเพิ่มข้อมูลไม่ได้ กรุณาตรวจการเชื่อมต่อและติดตั้ง schema_all_points.sql")

# Upload is visible near the top, not hidden in an expander.
with st.container(border=True, key="survey_upload"):
    st.markdown("### 📥 อัปโหลดข้อมูล G-Mon Pro")
    st.caption("ทุกคนเพิ่มข้อมูลได้ · เก็บทุกแถวรวมรายการซ้ำ · CSV/TXT ไม่เกิน 20 MB")
    upload = st.file_uploader("เลือกไฟล์ G-Mon Pro", type=["csv", "txt"], key="gmon_upload")
    if upload:
        try:
            frame = read_table(upload.getvalue(), upload.name)
            records, issues = prepare_gmon(frame)
            st.caption(f"ข้อมูลทั้งหมด {len(frame):,} แถว · ผ่านการตรวจ {len(records):,} แถว · ต้องตรวจสอบ {len(issues):,} แถว")
            with st.expander("ตรวจข้อมูลก่อนบันทึก"):
                st.dataframe(frame.head(20), hide_index=True)
                if not issues.empty:
                    st.dataframe(issues, hide_index=True)
            if not issues.empty:
                st.warning("บันทึกต้นฉบับครบทุกแถว แต่แถวที่ไม่มีพิกัดใช้ได้จะแสดงเฉพาะในตารางผลค้นหา")
            if st.button("บันทึก G-Mon เข้าฐานข้อมูล", type="primary", disabled=not ready):
                with st.spinner("กำลังบันทึกทุกแถว…"):
                    count = db.save_raw(engine, frame)
                st.success(f"บันทึก {count:,} แถว รวมรายการซ้ำเรียบร้อย กดซ้ำจะเพิ่มข้อมูลอีกรอบ")
        except ValueError as exc:
            st.error(str(exc))
        except Exception:
            st.error("บันทึกไม่สำเร็จ ไม่มีการบันทึกบางส่วน กรุณาตรวจไฟล์และการเชื่อมต่อ")


def demo_rows():
    return [dict(observation_key=f"demo:{i}", plmn="52003", xci="350342102" if i < 3 else "117266",
                 lac="23072" if i < 3 else "55653", xnbid="116876", system="4", lat=7.01+i*.001,
                 lon=100.47+i*.001, rsrp=[-82,-98,-112,-88,-102][i], observed_at=datetime(2025,9,3,9,11,i)) for i in range(5)]


with st.container(border=True, key="search_panel"):
    st.markdown("### 🔎 ค้นหาพิกัดภาคสนาม")
    with st.form("search"):
        a, b, c = st.columns(3)
        cells = a.text_area("CELL / XCI", placeholder="117266\n116876\n64918", height=140, key="cell_input")
        lacs = b.text_area("LAC / TAC", placeholder="55653\n55653\n06611", height=140, key="lac_input")
        nbids = c.text_area("xNBID", placeholder="116876\n117266", height=140, key="nbid_input")
        plmn = st.selectbox("เครือข่าย / PLMN", ["ทุกเครือข่าย"] + list(NETWORKS), format_func=network_label, key="plmn_input")
        st.caption("CELL และ LAC จับคู่ตามบรรทัด · เว้นทั้งช่องเพื่อค้นหาอีกช่องอย่างเดียว · xNBID ใส่ได้หลายบรรทัด")
        search_button = st.form_submit_button("ค้นหาพิกัด", type="primary", width="stretch", disabled=not (ready or DEMO))
    st.button("ล้างการค้นหา", on_click=clear_search, width="stretch", key="clear_search_button")
    if search_button:
        try:
            c, l, pairs = paired_ids(cells, lacs)
            n = parse_ids(nbids)
            if not any((c,l,n)):
                raise ValueError("กรุณากรอก CELL, LAC หรือ xNBID อย่างน้อยหนึ่งช่อง")
            begin = time.perf_counter()
            with st.spinner("กำลังค้นหาทุกจุดจากข้อมูลต้นฉบับ…"):
                if DEMO:
                    rows = [r for r in demo_rows() if (not pairs or (r['xci'],r['lac']) in pairs) and
                            (pairs or ((not c or r['xci'] in c) and (not l or r['lac'] in l))) and
                            (not n or r['xnbid'] in n) and (plmn == "ทุกเครือข่าย" or r['plmn'] == plmn)]
                else:
                    rows, _ = db.search(engine, c, l, n, [] if plmn == "ทุกเครือข่าย" else [plmn], pairs=pairs)
            st.session_state.update(rows=rows, mode="ค้นหา", elapsed=time.perf_counter()-begin,
                                    notice=f"พบ {len(rows):,} รายการ รวมข้อมูลซ้ำ")
            st.session_state.revision += 1
        except ValueError as exc:
            st.error(str(exc))
        except Exception:
            st.error("ค้นหาไม่สำเร็จ กรุณาตรวจการเชื่อมต่อแล้วลองใหม่")

with st.expander("📞 วิเคราะห์ CDR · VOICE / DATA · ใช้ชั่วคราว"):
    st.caption("จับคู่ทุกพิกัด G-Mon ด้วย LAC/CELL · ใช้พิกัด CDR เมื่อไม่พบ G-Mon · ไม่บันทึก CDR ลงฐานข้อมูล")
    a, b = st.columns(2)
    voice = a.file_uploader("ไฟล์ VOICE", type=["csv","txt","xlsx"], key=f"voice_{st.session_state.cdr_generation}")
    data = b.file_uploader("ไฟล์ DATA", type=["csv","txt","xlsx"], key=f"data_{st.session_state.cdr_generation}")
    with st.form("cdr_options"):
        cdr_network = st.selectbox("เครือข่ายของ CDR", ["ไม่ระบุ"]+list(NETWORKS), format_func=network_label)
        filter_time = st.checkbox("กรองช่วงเวลาเหตุการณ์")
        a,b = st.columns(2)
        start_day = a.date_input("วันที่เริ่ม", date.today())
        start_time = a.time_input("เวลาเริ่ม", day_time(0,0))
        end_day = b.date_input("วันที่สิ้นสุด", date.today())
        end_time = b.time_input("เวลาสิ้นสุด", day_time(23,59,59))
        analyze = st.form_submit_button("วิเคราะห์ VOICE / DATA", type="primary", disabled=not (ready or DEMO))
    st.button("ล้างไฟล์และผล CDR", on_click=clear_cdr)
    if analyze:
        try:
            if not voice and not data:
                raise ValueError("เลือกไฟล์ VOICE หรือ DATA อย่างน้อยหนึ่งไฟล์")
            batches, all_errors, offset = [], [], 0
            for kind, file in [("VOICE",voice),("DATA",data)]:
                if file:
                    raw = read_table(file.getvalue(), file.name, max_rows=None)
                    events, errors = prepare_cdr(raw, kind=kind, offset=offset)
                    offset += len(raw)
                    if not events.empty:
                        batches.append(events)
                    if not errors.empty:
                        errors["ประเภท"] = kind
                        all_errors.append(errors)
            st.session_state.cdr_errors = pd.concat(all_errors, ignore_index=True) if all_errors else pd.DataFrame()
            if not batches:
                raise ValueError("ไม่พบเหตุการณ์ที่อ่านวันเวลาและ LAC/CELL ได้")
            events = pd.concat(batches, ignore_index=True).sort_values(["event_at","event_id"])
            if filter_time:
                start, end = datetime.combine(start_day,start_time), datetime.combine(end_day,end_time)
                if start > end:
                    raise ValueError("เวลาเริ่มต้องไม่เกินเวลาสิ้นสุด")
                events = events[events.event_at.between(start,end)]
            if events.empty:
                raise ValueError("ไม่พบเหตุการณ์ในช่วงเวลาที่เลือก กรุณาตรวจช่วงเวลาหรือปิดตัวกรองเวลา")
            with st.spinner("กำลังจับคู่ทุกจุด G-Mon…"):
                candidates = demo_rows() if DEMO else db.lookup_pairs(engine,list(zip(events.xci,events.lac)),[] if cdr_network == "ไม่ระบุ" else [cdr_network])
                if DEMO and cdr_network != "ไม่ระบุ":
                    candidates = [r for r in candidates if r['plmn']==cdr_network]
                rows = match_cdr(events,candidates)
            st.session_state.update(rows=rows,mode="CDR",notice=f"วิเคราะห์ {len(events):,} เหตุการณ์ · จับคู่ได้ {len(rows):,} รายการ",elapsed=None)
            st.session_state.revision += 1
        except ValueError as exc:
            st.error(str(exc))
        except Exception:
            st.error("วิเคราะห์ไม่สำเร็จ กรุณาตรวจไฟล์และการเชื่อมต่อ")
    if not st.session_state.get("cdr_errors",pd.DataFrame()).empty:
        st.dataframe(st.session_state.cdr_errors,hide_index=True)

with st.expander("🎥 วิเคราะห์เส้นทางจากกล้อง + CDR", expanded=False):
    st.caption("อัปโหลดข้อมูลกล้องเพื่อเทียบเวลาเหตุการณ์ CDR · ชื่อด่านใช้ข้อความหลัง | · ไฟล์กล้องไม่ถูกบันทึกลงฐานข้อมูล")
    camera_file = st.file_uploader("ไฟล์กล้อง/ด่าน (CSV, XLSX)", type=["csv","txt","xlsx"], key="camera_file")
    camera_window = st.number_input("ช่วงเวลายอมรับรอบเหตุการณ์ (นาที)", min_value=1, max_value=240, value=10)
    camera_run = st.button("จับคู่กล้องกับ CDR", type="primary", disabled=not camera_file)
    if camera_run and camera_file:
        try:
            if prepare_camera is None:
                raise ValueError("รุ่นที่ Deploy อยู่ยังไม่รองรับตัวแปลงไฟล์กล้อง กรุณารีเฟรช Deploy")
            camera_raw = read_table(camera_file.getvalue(), camera_file.name, max_rows=None)
            cameras, camera_errors = prepare_camera(camera_raw)
            st.session_state.camera_rows = cameras
            st.session_state.camera_errors = camera_errors
            if cameras.empty:
                st.warning("ไม่พบรายการกล้องที่อ่านได้")
            else:
                st.success(f"อ่านข้อมูลกล้องได้ {len(cameras):,} รายการ")
        except Exception as exc:
            st.error(f"อ่านไฟล์กล้องไม่สำเร็จ: {exc}")
    cameras = st.session_state.get("camera_rows", pd.DataFrame())
    if not cameras.empty:
        st.dataframe(cameras.assign(camera_time=cameras.camera_time.map(display_time)), hide_index=True, width="stretch")
        cdr_events = [r for r in st.session_state.get("rows", []) if r.get("event_type") in {"VOICE","DATA"} and r.get("event_at")]
        if cdr_events:
            timeline = []
            for cam in cameras.to_dict("records"):
                nearby = [r for r in cdr_events if abs((r["event_at"] - cam["camera_time"]).total_seconds()) <= camera_window*60]
                # Prefer VOICE at the same window; DATA fills windows with no call.
                voice = [r for r in nearby if r.get("event_type") == "VOICE"]
                selected = voice or [r for r in nearby if r.get("event_type") == "DATA"]
                for r in selected:
                    timeline.append({"เวลา": display_time(cam["camera_time"]), "กล้อง/ด่าน": cam["checkpoint"],
                                     "ทิศทาง": cam["direction"], "ประเภท": r.get("event_type"),
                                     "เวลา CDR": display_time(r["event_at"]), "LAC": r.get("lac"), "CELL": r.get("xci"),
                                     "สถานะ": "สนับสนุนโดย CDR"})
            if timeline:
                st.success(f"พบเหตุการณ์ใกล้เวลากล้อง {len(timeline):,} รายการ")
                st.dataframe(pd.DataFrame(timeline), hide_index=True, width="stretch")
            else:
                st.warning("ไม่พบ CDR ในช่วงเวลาที่กำหนดรอบกล้อง")
        else:
            st.info("กรุณาวิเคราะห์ไฟล์ CDR ก่อน ระบบจะใช้เวลา CDR ประกอบกับเวลากล้อง")

with st.expander("ค้นหาพื้นที่ด้วยกรอบพิกัด"):
    with st.form("area"):
        a,b = st.columns(2)
        south = a.number_input("ใต้",-90.,90.,6.9,format="%.5f")
        north = b.number_input("เหนือ",-90.,90.,7.2,format="%.5f")
        west = a.number_input("ตะวันตก",-180.,180.,100.3,format="%.5f")
        east = b.number_input("ตะวันออก",-180.,180.,100.7,format="%.5f")
        area_search = st.form_submit_button("ค้นหาภายในพื้นที่",disabled=not (ready or DEMO))
    if area_search:
        try:
            if south>=north or west>=east:
                raise ValueError("ขอบเขตพื้นที่ไม่ถูกต้อง")
            found = [r for r in demo_rows() if south<=r['lat']<=north and west<=r['lon']<=east] if DEMO else db.search(engine,bounds=dict(south=south,north=north,west=west,east=east))[0]
            st.session_state.update(rows=found,mode="พื้นที่",elapsed=None,notice=f"พบ {len(found):,} รายการในพื้นที่ รวมข้อมูลซ้ำ")
            st.session_state.revision += 1
        except ValueError as exc:
            st.error(str(exc))
        except Exception:
            st.error("ค้นหาพื้นที่ไม่สำเร็จ กรุณาตรวจการเชื่อมต่อ")

rows = st.session_state.rows
if st.session_state.notice:
    st.success(st.session_state.notice)
valid = [r for r in rows if coordinates(r.get("lat"),r.get("lon"))]
metrics = st.columns(4)
metrics[0].metric("รายการพิกัด",f"{len(valid):,}")
metrics[1].metric("G-Mon",f"{sum(r.get('source','G-Mon')=='G-Mon' for r in valid):,}")
metrics[2].metric("CDR สำรอง",f"{sum(r.get('source')=='CDR สำรอง' for r in valid):,}")
metrics[3].metric("ไม่มีพิกัด",f"{len(rows)-len(valid):,}")
st.markdown("### 🗺️ แผนที่วิเคราะห์")
st.caption("🟢 HIGH ≥ −90 · 🟡 MID ≥ −105 · 🔴 LOW < −105 dBm — ใช้กับ LTE RSRP · เทา = ไม่มีค่า/ระบบอื่น")
st.caption("เก็บทุกรายการ จุดพิกัดเดียวกันอาจซ้อนกัน เปิดตารางเพื่อดูรายละเอียดครบทุกแถว")
with st.expander("ตั้งค่าการแสดงผลแผนที่"):
    playback = st.checkbox("เล่นไทม์ไลน์แบบเน้นกลุ่มจุด",value=True,disabled=st.session_state.mode != "CDR")
    sector = st.checkbox("เปิด Sector จำลอง")
    a,b,c = st.columns(3)
    bearing_text = a.text_input("ทิศจำลอง (0–359°)",placeholder="เช่น 90")
    radius = b.number_input("รัศมีจำลอง (เมตร)",10,20000,1000,100)
    beam = c.number_input("ความกว้าง (องศา)",1,360,90)
    bearing = None
    if bearing_text.strip():
        try:
            bearing = float(bearing_text)
            if not 0<=bearing<360:
                raise ValueError()
        except ValueError:
            bearing = None
            st.warning("ทิศต้องตั้งแต่ 0 ถึงน้อยกว่า 360 องศา")
    if sector and (bearing is None or len(valid)>500):
        st.info("กรอกทิศจำลอง และค้นหาไม่เกิน 500 จุดเพื่อเปิดรูปพัด")
map_obj = build_map(rows,sector=sector,bearing=bearing,radius=radius,beam=beam,path=playback and st.session_state.mode=="CDR")
st_folium(map_obj,height=620,use_container_width=True,key=f"map_{st.session_state.revision}",returned_objects=[])
st.caption("จุด G-Mon คือจุดตรวจพบสัญญาณ ไม่ใช่ตำแหน่งเสาจริง · ไทม์ไลน์เน้นทุกจุดของเหตุการณ์โดยไม่เลือกตำแหน่งโทรศัพท์เอง")
if st.session_state.elapsed is not None:
    st.caption(f"ค้นหาฐานข้อมูล {st.session_state.elapsed:.2f} วินาที")
if any(r.get("ambiguous") for r in rows):
    st.warning("มีหลาย PLMN ตรงกับ LAC/CELL เดียวกัน แสดงทุกเครือข่าย กรุณาเลือกเครือข่ายเพื่อจำกัดผล")
if rows:
    with st.expander("ตารางผลทั้งหมด · รวมรายการซ้ำ"):
        table = pd.DataFrame(rows)
        for column in ("event_at","observed_at"):
            if column in table:
                table[column] = table[column].map(display_time)
        columns = [c for c in ["event_type","event_id","event_at","source","plmn","xci","lac","lac_display","xnbid","lat","lon","rsrp","observed_at","status"] if c in table]
        st.dataframe(table[columns],hide_index=True,width="stretch")
st.markdown('<div class="footer">วิเคราะห์พิกัด <span>G-Mon เก็บทุกแถว · CDR ใช้เฉพาะเซสชัน</span></div>',unsafe_allow_html=True)
