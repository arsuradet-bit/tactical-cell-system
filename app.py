import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
from streamlit_folium import st_folium
import folium

# --- ตั้งค่าหน้าเว็บ Streamlit ---
st.set_page_config(
    page_title="INTEL : TACTICAL CELL ANALYSIS SYSTEM", layout="wide"
)

# --- ระบบความปลอดภัย: รหัสผ่านคือ ncid ---
TACTICAL_PASSWORD = "ncid"

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    col_l1, col_l2, col_l3 = st.columns([1, 2, 1])
    with col_l2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        try:
            st.image("logo.png", width=150)
        except Exception:
            pass
        st.markdown("## 🔒 RESTRICTED ACCESS")
        st.markdown("<p style='color: #adb5bd;'>INTEL : TACTICAL CELL ANALYSIS SYSTEM<br>กรุณากรอกรหัสผ่านเพื่อเข้าสู่ระบบปฏิบัติการ</p>", unsafe_allow_html=True)
        
        entered_password = st.text_input("Password", type="password", placeholder="กรอกรหัสผ่าน...")
        if st.button("LOGIN 🚀", type="primary", use_container_width=True):
            if entered_password == TACTICAL_PASSWORD:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("❌ รหัสผ่านไม่ถูกต้อง!")
    st.stop()

# ==========================================
# ส่วนด้านล่างนี้จะทำงานเฉพาะเมื่อใส่รหัสผ่านถูกต้องแล้ว
# ==========================================

# --- CSS ตกแต่งให้สวยงามและอ่านง่าย ---
st.markdown(
    """
    <style>
    .stApp { background-color: #0b1426 !important; color: #ffffff !important; }
    
    /* บังคับตัวหนังสือ Label ให้สว่างชัดเจน */
    label, p, span, .stMarkdown {
        color: #f1f5f9 !important;
        font-weight: 500 !important;
    }
    
    /* กล่อง Header หลัก */
    .tactical-header {
        background: linear-gradient(90deg, #0f172a 0%, #1e293b 100%);
        padding: 15px; border-radius: 8px; text-align: center; 
        border-left: 4px solid #3b82f6; border-right: 4px solid #3b82f6;
        margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    
    /* กรอบ Container */
    [data-testid="stVerticalBlockBorderWrapper"] {
        border: 1px solid #1e293b !important;
        border-radius: 8px !important;
        background-color: #0f172a !important;
        padding: 15px;
    }
    
    /* ช่องกรอกข้อมูลและ Dropdown */
    input[type="text"], input[type="password"], div[data-baseweb="select"] > div {
        background-color: #1e293b !important; 
        color: #ffffff !important;
        border: 1px solid #3b82f6 !important;
    }
    input::placeholder { color: #94a3b8 !important; opacity: 1 !important; }
    
    /* กล่องอัปโหลดไฟล์ */
    [data-testid="stFileUploadDropzone"] {
        background-color: #1e293b !important;
        border: 1px dashed #3b82f6 !important;
    }
    [data-testid="stFileUploadDropzone"] * {
        color: #ffffff !important;
    }

    /* ปุ่ม SCAN (สีแดง) */
    button[kind="primary"] {
        background-color: #d9534f !important; color: white !important;
        border: none !important; font-weight: bold !important;
    }
    button[kind="primary"]:hover { background-color: #c93022 !important; }
    
    /* ปุ่มจำลองเส้นทาง / ปุ่มอื่นๆ (สีส้ม/เหลืองยุทธวิธี) */
    .stButton > button {
        font-weight: bold !important;
    }
    </style>
""",
    unsafe_allow_html=True,
)

# --- Top Navigation Bar (แบบต้นแบบ) ---
col_nav1, col_nav2 = st.columns([6, 4])
with col_nav1:
    st.markdown("<p style='color: #38bdf8; font-weight: bold; margin: 0;'>🛡️ INTEL | Tactical Command Center<br><span style='color: #22c55e; font-size: 12px;'>ระบบพร้อม: เชื่อมต่อ Cloud SQL สำเร็จ</span></p>", unsafe_allow_html=True)
with col_nav2:
    col_nb1, col_nb2, col_nb3 = st.columns(3)
    with col_nb1:
        st.button("📍 ระบบพิกัดเสา-CDR", use_container_width=True)
    with col_nb2:
        st.button("🚗 คัดกรองรถ", use_container_width=True)
    with col_nb3:
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.authenticated = False
            st.rerun()

st.markdown("---")

# --- Header หลักของระบบ ---
st.markdown(
    """
    <div class="tactical-header">
        <h3 style="color: #60a5fa; margin: 0;">CELL & CDR : Tracking System</h3>
    </div>
""",
    unsafe_allow_html=True,
)

# --- ตั้งค่า Database ---
DB_USER = "postgres"
DB_PASS = "0656637888Ar."
DB_HOST = "34.15.139.132"
DB_PORT = "5432"
DB_NAME = "postgres"

@st.cache_resource
def get_engine():
    return create_engine(
        f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}",
        pool_size=10, max_overflow=20, pool_recycle=3600
    )
engine = get_engine()

# --- Session State ---
if "search_message" not in st.session_state:
    st.session_state.search_message = ""
if "alert_type" not in st.session_state:
    st.session_state.alert_type = ""
if "target_df" not in st.session_state:
    st.session_state.target_df = pd.DataFrame()

# ==========================================
# 📍 1. โซนแกะรอยเป้าหมาย (CELL, LAC, NBID)
# ==========================================
with st.container(border=True):
    # แถบสลับโหมดจำลองตามต้นแบบ
    st.markdown("""
        <div style="display: flex; gap: 10px; margin-bottom: 15px;">
            <span style="background-color: #3b82f6; color: white; padding: 5px 12px; border-radius: 4px; font-size: 13px; font-weight: bold;">📍 1. แกะรอยเป้าหมาย (CELL_ID / ค้นหา LAC)</span>
            <span style="background-color: #1e293b; color: #94a3b8; padding: 5px 12px; border-radius: 4px; font-size: 13px;">📡 2. ตรวจสอบเสาหลัก (NBID)</span>
            <span style="background-color: #1e293b; color: #94a3b8; padding: 5px 12px; border-radius: 4px; font-size: 13px;">🗺️ 3. ค้นหาด้วยที่อยู่</span>
        </div>
    """, unsafe_allow_html=True)
    
    with st.form(key="search_form", border=False):
        col_s1, col_s2, col_s3, col_btn = st.columns([1.5, 1.5, 1.5, 1], vertical_alignment="bottom")
        
        with col_s1:
            cell_input = st.text_input("รหัส CELL_ID (ปล่อยว่างได้ถ้าค้นหาเฉพาะ LAC)", placeholder="วาง CELL_ID...")
        with col_s2:
            lac_input = st.text_input("รหัส LAC/TAC (ใช้ค้นหาเฉพาะ LAC ได้)", placeholder="วาง LAC/TAC...")
        with col_s3:
            nbid_input = st.text_input("รหัส NBID (Node ID)", placeholder="วาง NBID...")
        with col_btn:
            scan_clicked = st.form_submit_button("SCAN 🔍", use_container_width=True, type="primary")
            sim_clicked = st.form_submit_button("▶️ จำลองเส้นทาง", use_container_width=True)

    # แถบตัวเลือกเสริมทางยุทธวิธี (ตามภาพต้นแบบ)
    st.markdown("<br>", unsafe_allow_html=True)
    col_opt1, col_opt2, col_opt3, col_opt4, col_opt5 = st.columns([1.2, 1.2, 1.2, 1, 1])
    with col_opt1:
        opt_sector = st.checkbox("เปิดระยะรูปพัด", value=True)
    with col_opt2:
        opt_sub = st.checkbox("แสดง Sector รอง", value=True)
    with col_opt3:
        opt_line = st.checkbox("ลากเส้นไทม์ไลน์", value=True)
    with col_opt4:
        radius_val = st.text_input("รัศมี", value="1000")
    with col_opt5:
        width_val = st.text_input("กว้าง", value="90")

    if scan_clicked or sim_clicked:
        c_val = cell_input.strip()
        l_val = lac_input.strip()
        n_val = nbid_input.strip()
        
        if not c_val and not l_val and not n_val:
            st.session_state.search_message = "⚠️ กรุณากรอกรหัสสำหรับค้นหาอย่างน้อย 1 ช่อง"
            st.session_state.alert_type = "error"
            st.session_state.target_df = pd.DataFrame()
        else:
            with st.spinner("กำลังแกะรอยพิกัดจากฐานข้อมูล Cloud SQL..."):
                try:
                    query = "SELECT * FROM gmon_survey_logs WHERE 1=1"
                    params = {}

                    if c_val:
                        query += " AND (CAST(xci AS TEXT) LIKE :cell OR CAST(local_cid AS TEXT) LIKE :cell)"
                        params["cell"] = f"%{c_val}%"
                    if l_val:
                        query += " AND (CAST(\"lac/tac\" AS TEXT) LIKE :lac)"
                        params["lac"] = f"%{l_val}%"
                    if n_val:
                        query += " AND (CAST(xnbid AS TEXT) LIKE :nbid)"
                        params["nbid"] = f"%{n_val}%"

                    with engine.connect() as conn:
                        filtered_df = pd.read_sql(text(query), conn, params=params)
                        filtered_df.columns = [str(c).lower() for c in filtered_df.columns]

                    if not filtered_df.empty:
                        st.session_state.search_message = f"🎯 ค้นหาสำเร็จ! พบพิกัดเป้าหมายทั้งหมด {len(filtered_df):,} จุด"
                        st.session_state.alert_type = "success"
                        st.session_state.target_df = filtered_df.copy()
                    else:
                        st.session_state.search_message = "❌ ไม่พบพิกัดที่ตรงกับเงื่อนไขในระบบ!"
                        st.session_state.alert_type = "error"
                        st.session_state.target_df = pd.DataFrame()
                except Exception as e:
                    st.session_state.search_message = f"❌ Error: {e}"
                    st.session_state.alert_type = "error"
                    st.session_state.target_df = pd.DataFrame()

if st.session_state.search_message:
    if st.session_state.alert_type == "success":
        st.success(st.session_state.search_message)
    else:
        st.error(st.session_state.search_message)

# ==========================================
# 📥 2. โซนอัปโหลดฐานข้อมูลเสา (G-MoN Pro)
# ==========================================
st.markdown("<br>", unsafe_allow_html=True)
with st.container(border=True):
    st.markdown("#### 📥 1. อัปโหลดฐานข้อมูลเสา (G-MoN Pro CSV)")
    
    network_mapping = {
        "🟢 AIS (52001, 52003)": {"name": "AIS", "code": "52001, 52003"},
        "🔴 TRUE (52000, 52004)": {"name": "TRUE", "code": "52000, 52004"},
        "🔵 DTAC (52005, 52018)": {"name": "DTAC", "code": "52005, 52018"},
        "🟡 NT (52002, 52015)": {"name": "NT", "code": "52002, 52015"},
        "⚪ ไม่ระบุ (ใช้ข้อมูลเดิมในไฟล์)": {"name": None, "code": None}
    }

    col_up1, col_up2, col_up3 = st.columns([1.5, 2.5, 1], vertical_alignment="center")
    
    with col_up1:
        selected_network = st.selectbox("เลือกเครือข่าย", options=list(network_mapping.keys()), label_visibility="collapsed")
    with col_up2:
        uploaded_file = st.file_uploader("เลือกไฟล์ CSV", type=["csv"], label_visibility="collapsed")
    with col_up3:
        upload_clicked = st.button("⬆️ อัปโหลดเข้าฐานข้อมูล", use_container_width=True)

    if upload_clicked:
        if uploaded_file is not None:
            with st.spinner("กำลังบันทึกลงฐานข้อมูล Cloud SQL..."):
                try:
                    df_upload = pd.read_csv(uploaded_file)
                    df_upload.columns = [str(c).strip().lower() for c in df_upload.columns]
                    
                    net_info = network_mapping[selected_network]
                    if net_info["name"]:
                        df_upload['network_name'] = net_info["name"]
                    if net_info["code"]:
                        df_upload['network_code'] = net_info["code"]
                    
                    df_upload.to_sql('gmon_survey_logs', con=engine, if_exists='append', index=False)
                    st.success(f"✅ สำเร็จ! นำเข้าข้อมูลพิกัดใหม่จำนวน {len(df_upload):,} จุด เรียบร้อยแล้ว")
                except Exception as e:
                    st.error(f"❌ เกิดข้อผิดพลาด: {e}")
        else:
            st.warning("⚠️ กรุณาเลือกไฟล์ CSV ก่อนกดอัปโหลด")

# ==========================================
# 📞 3. โซนอัปโหลดประวัติการโทร (Data CDR) - ตามภาพต้นแบบ
# ==========================================
st.markdown("<br>", unsafe_allow_html=True)
with st.container(border=True):
    st.markdown("#### 📍 2. อัปโหลดประวัติการโทร (Data CDR)")
    
    col_cdr1, col_cdr2, col_cdr3, col_cdr4 = st.columns([1.5, 1.5, 1, 2])
    with col_cdr1:
        date_start = st.text_input("ตั้งแต่", placeholder="วว/ดด/ปปปป --:--")
    with col_cdr2:
        date_end = st.text_input("ถึง", placeholder="วว/ดด/ปปปป --:--")
    with col_cdr3:
        st.markdown("<br>", unsafe_allow_html=True)
        st.button("🔄 ล้างเวลา", use_container_width=True)
    with col_cdr4:
        st.markdown("<br>", unsafe_allow_html=True)
        # ช่องว่างจัดเลย์เอาต์

    col_cdr_file, col_cdr_btn = st.columns([3, 1], vertical_alignment="center")
    with col_cdr_file:
        cdr_file = st.file_uploader("เลือกไฟล์ CDR", type=["csv", "xlsx"], label_visibility="collapsed")
    with col_cdr_btn:
        st.button("▶️ สแกนเส้นทาง CDR", use_container_width=True, type="primary")

# ==========================================
# 🗺️ 4. แผนที่พิกัดยุทธวิธี (Tactical Map)
# ==========================================
st.markdown("---")
st.subheader("🗺️ แผนที่แสดงพิกัดยุทธวิธี (Tactical Map)")

target_df = st.session_state.target_df
lat_center, lon_center = 7.0123, 100.4911

if not target_df.empty and "lat" in target_df.columns and "lon" in target_df.columns:
    valid_target = target_df.dropna(subset=["lat", "lon"])
    if not valid_target.empty:
        lat_center = float(valid_target["lat"].iloc[0])
        lon_center = float(valid_target["lon"].iloc[0])

m = folium.Map(location=[lat_center, lon_center], zoom_start=12, tiles="OpenStreetMap")

if not target_df.empty and "lat" in target_df.columns and "lon" in target_df.columns:
    map_df = target_df.dropna(subset=["lat", "lon"]).copy()
    map_df["lat"] = map_df["lat"].astype(float)
    map_df["lon"] = map_df["lon"].astype(float)

    for idx, row in map_df.iterrows():
        net_popup = row.get('network_name', 'N/A')
        net_code_popup = row.get('network_code', 'N/A')
        
        folium.CircleMarker(
            location=[row["lat"], row["lon"]],
            radius=6, color="#ef4444", fill=True, fill_color="#ef4444", fill_opacity=0.9,
            popup=f"CELL: {row.get('xci', 'N/A')} | LAC: {row.get('lac/tac', 'N/A')} | NBID: {row.get('xnbid', 'N/A')}<br>เครือข่าย: {net_popup} ({net_code_popup})"
        ).add_to(m)

st_folium(m, width="100%", height=700, key="tactical_map")
