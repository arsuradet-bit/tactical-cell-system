import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
from streamlit_folium import st_folium
import folium

# --- ตั้งค่าหน้าเว็บ Streamlit (ต้องเป็นคำสั่งแรกสุด) ---
st.set_page_config(
    page_title="INTEL : TACTICAL CELL ANALYSIS SYSTEM", layout="wide"
)

# --- ระบบความปลอดภัย: ตรวจสอบรหัสผ่านก่อนเข้าใช้งาน ---
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
        
        entered_password = st.text_input("Password", type="password", placeholder="กรอกรหัสผ่านหน่วยงาน...")
        if st.button("LOGIN 🚀", type="primary", use_container_width=True):
            if entered_password == TACTICAL_PASSWORD:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("❌ รหัสผ่านไม่ถูกต้อง! กรุณาลองใหม่อีกครั้ง")
    st.stop()

# ==========================================
# ส่วนด้านล่างนี้จะทำงานเฉพาะเมื่อใส่รหัสผ่านถูกต้องแล้วเท่านั้น
# ==========================================

# --- แสดงโลโก้หน่วยงานขนาดพอดี (จัดไว้ตรงกลาง) ---
col1, col2, col3 = st.columns([2, 1, 2])
with col2:
    try:
        st.image("logo.png", width=130)
    except Exception:
        pass

# --- ตั้งค่าการเชื่อมต่อ Cloud SQL ---
DB_USER = "postgres"
DB_PASS = "0656637888Ar."
DB_HOST = "34.15.139.132"
DB_PORT = "5432"
DB_NAME = "postgres"

# Custom CSS ธีม Detective Blue และการจัด Layout
st.markdown(
    """
    <style>
    /* พื้นหลังหลักของเว็บ */
    .stApp { 
        background-color: #0b1426 !important; 
        color: #e2e8f0; 
    }
    
    /* กล่อง Header หลัก */
    .tactical-header {
        background: linear-gradient(90deg, #0f172a 0%, #1e293b 100%);
        padding: 20px; 
        border-radius: 8px;
        text-align: center; 
        border-left: 5px solid #3b82f6;
        border-right: 5px solid #3b82f6;
        margin-bottom: 25px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
    }
    
    /* สีของปุ่มกดหลัก (ปุ่ม SCAN และ อัปโหลด) */
    .stButton > button[kind="primary"] {
        background-color: #1d4ed8 !important; /* สีน้ำเงินเข้ม */
        color: white !important;
        border: 1px solid #2563eb !important;
        border-radius: 6px !important;
        font-weight: bold !important;
        height: 42px !important; /* ล็อกความสูงปุ่มให้เท่ากับช่องกรอกข้อมูล */
    }
    .stButton > button[kind="primary"]:hover {
        background-color: #2563eb !important; /* สีสว่างขึ้นเมื่อชี้เมาส์ */
        box-shadow: 0 0 10px rgba(59, 130, 246, 0.5);
    }
    
    /* สีของปุ่มกดรอง (Logout) */
    .stButton > button[kind="secondary"] {
        background-color: #1e293b !important;
        color: #e2e8f0 !important;
        border: 1px solid #334155 !important;
    }
    
    /* ปรับขนาดกล่องอัปโหลดไฟล์ให้บางลงและแนบเนียนขึ้น */
    [data-testid="stFileUploadDropzone"] {
        background-color: #1e293b !important;
        border: 1px dashed #3b82f6 !important;
        color: #e2e8f0 !important;
        min-height: 42px !important; /* บีบความสูงให้เท่าปุ่ม */
        padding: 5px !important;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    
    /* สีช่องกรอกข้อมูลและ Selectbox */
    .stTextInput input, .stSelectbox div[data-baseweb="select"] {
        background-color: #1e293b !important;
        color: white !important;
        border: 1px solid #334155 !important;
        border-radius: 6px !important;
    }
    
    /* สีตัวอักษรหัวข้อและ Label */
    label, .stMarkdown p { color: #94a3b8 !important; font-weight: 500 !important; }
    h2, h3, h4 { color: #f8fafc !important; }
    
    /* กล่องแจ้งเตือน */
    .tactical-alert-success {
        background-color: #064e3b; color: #34d399; padding: 12px; border-radius: 6px;
        border: 1px solid #059669; font-weight: bold; margin-bottom: 15px;
    }
    .tactical-alert-error {
        background-color: #7f1d1d; color: #fca5a5; padding: 12px; border-radius: 6px;
        border: 1px solid #b91c1c; font-weight: bold; margin-bottom: 15px;
    }
    </style>
""",
    unsafe_allow_html=True,
)

# --- สร้าง Session State ---
if "search_message" not in st.session_state:
    st.session_state.search_message = ""
if "alert_type" not in st.session_state:
    st.session_state.alert_type = ""
if "target_df" not in st.session_state:
    st.session_state.target_df = pd.DataFrame()

# --- ส่วนหัวระบบ (Header) ---
st.markdown(
    """
    <div class="tactical-header">
        <h2 style="color: #38bdf8 !important; margin: 0;">INTEL : TACTICAL CELL ANALYSIS SYSTEM</h2>
        <p style="color: #94a3b8; margin: 5px 0 0 0;">ระบบสืบสวนและวิเคราะห์พิกัดสัญญาณโทรศัพท์เคลื่อนที่ (Cloud SQL Powered)</p>
    </div>
""",
    unsafe_allow_html=True,
)

# --- ปุ่มออกจากระบบ (Logout) ---
col_top_btn1, col_top_btn2 = st.columns([10, 1])
with col_top_btn2:
    if st.button("🚪 Logout"):
        st.session_state.authenticated = False
        st.rerun()

# --- ฟังก์ชันเชื่อมต่อฐานข้อมูล ---
@st.cache_resource
def get_engine():
    return create_engine(
        f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}",
        pool_size=10,
        max_overflow=20,
        pool_recycle=3600
    )

engine = get_engine()

# ==========================================
# 📥 1. อัปโหลดฐานข้อมูลเสา (G-MoN Pro CSV)
# ==========================================
st.markdown("#### 📥 1. อัปโหลดฐานข้อมูลเสา (G-MoN Pro CSV)")

network_mapping = {
    "🟢 AIS (52001, 52003)": {"name": "AIS", "code": "52001, 52003"},
    "🔴 TRUE (52000, 52004)": {"name": "TRUE", "code": "52000, 52004"},
    "🔵 DTAC (52005, 52018)": {"name": "DTAC", "code": "52005, 52018"},
    "🟡 NT (52002, 52015)": {"name": "NT", "code": "52002, 52015"},
    "⚪ ไม่ระบุ (ใช้ข้อมูลเดิมในไฟล์)": {"name": None, "code": None}
}

# จัด Layout 3 ช่องให้สัมพันธ์กัน (ปรับสมดุลช่อง)
col_net, col_file, col_btn = st.columns([1.2, 1.8, 1])

with col_net:
    selected_network = st.selectbox(
        "เครือข่าย", 
        options=list(network_mapping.keys()), 
        label_visibility="collapsed"
    )

with col_file:
    uploaded_file = st.file_uploader(
        "เลือกไฟล์ CSV", 
        type=["csv"], 
        label_visibility="collapsed"
    )

with col_btn:
    # เพิ่มระยะขอบบนนิดหน่อยให้ปุ่มตรงกับกล่องพอดีเป๊ะ
    st.markdown("<div style='margin-top: 1px;'></div>", unsafe_allow_html=True)
    upload_clicked = st.button("⬆️ อัปโหลดเข้าฐานข้อมูล", use_container_width=True, type="primary")

if upload_clicked:
    if uploaded_file is not None:
        with st.spinner("กำลังเตรียมข้อมูลและบันทึกลงฐานข้อมูล..."):
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

st.markdown("---")

# ==========================================
# 🔍 2. ส่วนค้นหาพิกัดยุทธวิธี
# ==========================================
st.markdown("#### 🔍 2. ค้นหาพิกัดและแกะรอยเป้าหมาย")
with st.form(key="search_form"):
    # แบ่งช่องเป็น 1:1:1:1 เท่าๆ กันทุกช่อง
    col_s1, col_s2, col_s3, col_s4 = st.columns([1, 1, 1, 1])
    
    with col_s1:
        cell_input = st.text_input("CELL (XCI)", placeholder="ระบุรหัส CELL...")
    with col_s2:
        lac_input = st.text_input("LAC (LAC/TAC)", placeholder="ระบุรหัส LAC...")
    with col_s3:
        ncid_input = st.text_input("NCID", placeholder="ระบุรหัส NCID...")
    with col_s4:
        # ใช้ CSS ดันปุ่มลงมา 28px เพื่อให้ปุ่ม SCAN อยู่ในระนาบเดียวกับช่องกรอกข้อมูลพอดี
        st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
        scan_clicked = st.form_submit_button("SCAN 🔍", use_container_width=True, type="primary")

# เมื่อมีการกดปุ่ม SCAN
if scan_clicked:
    if not cell_input and not lac_input and not ncid_input:
        st.session_state.search_message = "⚠️ กรุณากรอกข้อมูลสำหรับค้นหาอย่างน้อย 1 ช่อง"
        st.session_state.alert_type = "error"
        st.session_state.target_df = pd.DataFrame()
    else:
        with st.spinner("กำลังเจาะข้อมูลจาก Cloud SQL และแกะรอยเป้าหมาย..."):
            try:
                query = "SELECT * FROM gmon_survey_logs WHERE 1=1"
                params = {}

                if cell_input:
                    query += " AND (CAST(xci AS TEXT) LIKE :cell OR CAST(local_cid AS TEXT) LIKE :cell)"
                    params["cell"] = f"%{cell_input.strip()}%"

                if lac_input:
                    query += " AND (CAST(\"lac/tac\" AS TEXT) LIKE :lac)"
                    params["lac"] = f"%{lac_input.strip()}%"

                if ncid_input:
                    query += " AND (CAST(ncid AS TEXT) LIKE :ncid OR CAST(xnbid AS TEXT) LIKE :ncid)"
                    params["ncid"] = f"%{ncid_input.strip()}%"

                with engine.connect() as conn:
                    filtered_df = pd.read_sql(text(query), conn, params=params)
                    filtered_df.columns = [str(c).lower() for c in filtered_df.columns]

                if not filtered_df.empty:
                    st.session_state.search_message = f"🎯 ค้นหาสำเร็จ! พบข้อมูลเป้าหมายทั้งหมด {len(filtered_df):,} จุด"
                    st.session_state.alert_type = "success"
                    st.session_state.target_df = filtered_df.copy()
                else:
                    st.session_state.search_message = "❌ ไม่พบข้อมูล! ไม่พบพิกัดที่ตรงกับเงื่อนไขที่ระบุในฐานข้อมูล"
                    st.session_state.alert_type = "error"
                    st.session_state.target_df = pd.DataFrame()
                    
            except Exception as e:
                st.session_state.search_message = f"❌ เกิดข้อผิดพลาดในการดึงข้อมูลจาก Cloud SQL: {e}"
                st.session_state.alert_type = "error"
                st.session_state.target_df = pd.DataFrame()

# --- แสดงผลข้อความแจ้งเตือน ---
if st.session_state.search_message:
    if st.session_state.alert_type == "success":
        st.markdown(f'<div class="tactical-alert-success">{st.session_state.search_message}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="tactical-alert-error">{st.session_state.search_message}</div>', unsafe_allow_html=True)

# --- ส่วนแสดงผลแผนที่ (OpenStreetMap) ---
st.subheader("🗺️ แผนที่แสดงพิกัดยุทธวิธี (Tactical Map)")

target_df = st.session_state.target_df

lat_center, lon_center = 7.0123, 100.4911

if not target_df.empty and "lat" in target_df.columns and "lon" in target_df.columns:
    valid_target = target_df.dropna(subset=["lat", "lon"])
    if not valid_target.empty:
        lat_center = float(valid_target["lat"].iloc[0])
        lon_center = float(valid_target["lon"].iloc[0])

m = folium.Map(
    location=[lat_center, lon_center],
    zoom_start=12,
    tiles="OpenStreetMap"
)

if not target_df.empty and "lat" in target_df.columns and "lon" in target_df.columns:
    map_df = target_df.dropna(subset=["lat", "lon"]).copy()
    map_df["lat"] = map_df["lat"].astype(float)
    map_df["lon"] = map_df["lon"].astype(float)

    for idx, row in map_df.iterrows():
        net_popup = row.get('network_name', 'N/A')
        net_code_popup = row.get('network_code', 'N/A')
        
        folium.CircleMarker(
            location=[row["lat"], row["lon"]],
            radius=6,
            color="#38bdf8", # เปลี่ยนสีจุดบนแผนที่เป็นสีฟ้า (Cyber Blue)
            fill=True,
            fill_color="#38bdf8",
            fill_opacity=0.9,
            popup=f"CELL: {row.get('xci', 'N/A')} | LAC: {row.get('lac/tac', 'N/A')} | NCID: {row.get('ncid', row.get('xnbid', 'N/A'))}<br>เครือข่าย: {net_popup} ({net_code_popup})"
        ).add_to(m)

st_folium(m, width="100%", height=700, key="tactical_map")
