import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
from streamlit_folium import st_folium
import folium

# --- ตั้งค่าหน้าเว็บ Streamlit ---
st.set_page_config(
    page_title="INTEL : TACTICAL CELL ANALYSIS SYSTEM", layout="wide"
)

# --- ระบบความปลอดภัย ---
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
# ส่วนล่างนี้จะทำงานเฉพาะเมื่อใส่รหัสผ่านถูกต้องแล้ว
# ==========================================

# --- CSS โคลนนิ่ง UI จากภาพตัวอย่าง ---
st.markdown(
    """
    <style>
    /* พื้นหลังหลักของเว็บ */
    .stApp { background-color: #0b1426 !important; color: #e2e8f0; }
    
    /* กล่อง Header หลัก */
    .tactical-header {
        background-color: #0f172a; padding: 20px; border-radius: 8px; text-align: center; 
        border-bottom: 2px solid #3b82f6; margin-bottom: 25px;
    }
    
    /* สีพื้นหลังของกรอบ Container */
    [data-testid="stVerticalBlockBorderWrapper"] {
        border: 1px solid #1e293b !important;
        border-radius: 8px !important;
        background-color: #0f172a !important;
        padding: 10px;
    }
    
    /* แต่งปุ่ม SCAN (สีแดง) -> ใช้ kind="primary" */
    button[kind="primary"] {
        background-color: #d9534f !important; color: white !important;
        border: none !important; font-weight: bold !important;
    }
    button[kind="primary"]:hover { background-color: #c93022 !important; }
    
    /* แต่งปุ่ม อัปโหลด (สีเขียว) -> ใช้ kind="secondary" */
    button[kind="secondary"] {
        background-color: #5cb85c !important; color: white !important;
        border: none !important; font-weight: bold !important;
    }
    button[kind="secondary"]:hover { background-color: #4cae4c !important; }
    
    /* แต่งกล่องกรอกข้อความ (ช่องใหญ่) */
    .stTextArea textarea, input[type="text"], div[data-baseweb="select"] > div {
        background-color: #1e293b !important; color: white !important;
        border: 1px solid #334155 !important;
    }
    
    /* แต่งกล่องอัปโหลดไฟล์ให้ดูกระชับขึ้น */
    [data-testid="stFileUploadDropzone"] {
        background-color: #1e293b !important;
        border: 1px dashed #475569 !important;
        padding: 5px !important;
    }
    </style>
""",
    unsafe_allow_html=True,
)

# --- Header ---
st.markdown(
    """
    <div class="tactical-header">
        <h2 style="color: #60a5fa !important; margin: 0;">CELL & CDR : Tracking System</h2>
    </div>
""",
    unsafe_allow_html=True,
)

col_top_btn1, col_top_btn2 = st.columns([10, 1])
with col_top_btn2:
    if st.button("🚪 Logout", type="tertiary"):
        st.session_state.authenticated = False
        st.rerun()

# --- ตั้งค่า DB ---
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

# --- สร้าง Session State ---
if "search_message" not in st.session_state:
    st.session_state.search_message = ""
if "alert_type" not in st.session_state:
    st.session_state.alert_type = ""
if "target_df" not in st.session_state:
    st.session_state.target_df = pd.DataFrame()

# ==========================================
# 🔍 1. ส่วนแกะรอยเป้าหมาย (Search) - อยู่ด้านบนแบบในรูป
# ==========================================
with st.container(border=True):
    st.markdown("#### 📍 1. แกะรอยเป้าหมาย (CELL_ID / ค้นหา LAC)")
    
    with st.form(key="search_form", border=False):
        col_s1, col_s2, col_btn = st.columns([2.5, 2.5, 1])
        
        with col_s1:
            # ใช้ text_area เพื่อให้กล่องใหญ่เหมือนในรูปตัวอย่าง
            cell_input = st.text_area("รหัส CELL_ID (ปล่อยว่างได้ถ้าค้นหาเฉพาะ LAC)", placeholder="วาง CELL_ID...", height=100)
        with col_s2:
            lac_input = st.text_area("รหัส LAC/TAC (ใช้ค้นหาเฉพาะ LAC ได้)", placeholder="วาง LAC/TAC...", height=100)
        with col_btn:
            st.markdown("<br>", unsafe_allow_html=True) # ดันปุ่มลงมาให้เสมอขอบล่าง
            # ปุ่มสีแดง (primary)
            scan_clicked = st.form_submit_button("SCAN 🔍", use_container_width=True, type="primary")

    if scan_clicked:
        # ทำความสะอาดข้อมูลเผื่อก็อปปี้มาแล้วมีเว้นวรรค/ขึ้นบรรทัดใหม่
        c_val = cell_input.strip().split('\n')[0] if cell_input else ""
        l_val = lac_input.strip().split('\n')[0] if lac_input else ""
        
        if not c_val and not l_val:
            st.session_state.search_message = "⚠️ กรุณากรอกข้อมูลสำหรับค้นหาอย่างน้อย 1 ช่อง"
            st.session_state.alert_type = "error"
            st.session_state.target_df = pd.DataFrame()
        else:
            with st.spinner("กำลังแกะรอยเป้าหมาย..."):
                try:
                    query = "SELECT * FROM gmon_survey_logs WHERE 1=1"
                    params = {}

                    if c_val:
                        query += " AND (CAST(xci AS TEXT) LIKE :cell OR CAST(local_cid AS TEXT) LIKE :cell)"
                        params["cell"] = f"%{c_val}%"

                    if l_val:
                        query += " AND (CAST(\"lac/tac\" AS TEXT) LIKE :lac)"
                        params["lac"] = f"%{l_val}%"

                    with engine.connect() as conn:
                        filtered_df = pd.read_sql(text(query), conn, params=params)
                        filtered_df.columns = [str(c).lower() for c in filtered_df.columns]

                    if not filtered_df.empty:
                        st.session_state.search_message = f"🎯 ค้นหาสำเร็จ! พบเป้าหมาย {len(filtered_df):,} จุด"
                        st.session_state.alert_type = "success"
                        st.session_state.target_df = filtered_df.copy()
                    else:
                        st.session_state.search_message = "❌ ไม่พบข้อมูลในระบบ!"
                        st.session_state.alert_type = "error"
                        st.session_state.target_df = pd.DataFrame()
                except Exception as e:
                    st.session_state.search_message = f"❌ Error: {e}"
                    st.session_state.alert_type = "error"
                    st.session_state.target_df = pd.DataFrame()

# แสดงข้อความแจ้งเตือนผลการค้นหา
if st.session_state.search_message:
    if st.session_state.alert_type == "success":
        st.markdown(f'<div style="background-color: #064e3b; color: #34d399; padding: 12px; border-radius: 6px; border: 1px solid #059669; font-weight: bold; margin-bottom: 15px;">{st.session_state.search_message}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div style="background-color: #7f1d1d; color: #fca5a5; padding: 12px; border-radius: 6px; border: 1px solid #b91c1c; font-weight: bold; margin-bottom: 15px;">{st.session_state.search_message}</div>', unsafe_allow_html=True)

# ==========================================
# 📥 2. อัปโหลดฐานข้อมูลเสา - อยู่ด้านล่างแบบในรูป
# ==========================================
st.markdown("<br>", unsafe_allow_html=True)
with st.container(border=True):
    st.markdown("#### 📥 2. อัปโหลดฐานข้อมูลเสา (G-MoN Pro CSV)")
    
    network_mapping = {
        "🟢 AIS (52001, 52003)": {"name": "AIS", "code": "52001, 52003"},
        "🔴 TRUE (52000, 52004)": {"name": "TRUE", "code": "52000, 52004"},
        "🔵 DTAC (52005, 52018)": {"name": "DTAC", "code": "52005, 52018"},
        "🟡 NT (52002, 52015)": {"name": "NT", "code": "52002, 52015"},
        "⚪ ไม่ระบุ (ใช้ข้อมูลเดิม)": {"name": None, "code": None}
    }

    # จัด 3 คอลัมน์ให้สมมาตร (ใช้ vertical_alignment="center" แบบ native)
    col_net, col_file, col_btn = st.columns([1.5, 3, 1], vertical_alignment="center")

    with col_net:
        selected_network = st.selectbox("เครือข่าย", options=list(network_mapping.keys()), label_visibility="collapsed")
    with col_file:
        uploaded_file = st.file_uploader("เลือกไฟล์", type=["csv"], label_visibility="collapsed")
    with col_btn:
        # ปุ่มสีเขียว (secondary)
        upload_clicked = st.button("⬆️ อัปโหลดเข้าฐานข้อมูล", use_container_width=True, type="secondary")

    if upload_clicked:
        if uploaded_file is not None:
            with st.spinner("กำลังบันทึกลงฐานข้อมูล..."):
                try:
                    df_upload = pd.read_csv(uploaded_file)
                    df_upload.columns = [str(c).strip().lower() for c in df_upload.columns]
                    
                    net_info = network_mapping[selected_network]
                    if net_info["name"]:
                        df_upload['network_name'] = net_info["name"]
                    if net_info["code"]:
                        df_upload['network_code'] = net_info["code"]
                    
                    df_upload.to_sql('gmon_survey_logs', con=engine, if_exists='append', index=False)
                    st.success(f"✅ สำเร็จ! อัปโหลด {len(df_upload):,} จุด")
                except Exception as e:
                    st.error(f"❌ Error: {e}")
        else:
            st.warning("⚠️ กรุณาเลือกไฟล์ก่อนกดอัปโหลด")

# --- แผนที่ (Tactical Map) ---
st.markdown("---")
st.subheader("🗺️ แผนที่พิกัดยุทธวิธี")

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
            radius=6, color="#e04a3a", fill=True, fill_color="#e04a3a", fill_opacity=0.9,
            popup=f"CELL: {row.get('xci', 'N/A')} | LAC: {row.get('lac/tac', 'N/A')}<br>เครือข่าย: {net_popup} ({net_code_popup})"
        ).add_to(m)

st_folium(m, width="100%", height=700, key="tactical_map")
