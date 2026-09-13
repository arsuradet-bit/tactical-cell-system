import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
from streamlit_folium import st_folium
import folium

# --- ตั้งค่าหน้าเว็บ Streamlit (ต้องเป็นคำสั่งแรกสุด) ---
st.set_page_config(
    page_title="INTEL : TACTICAL CELL ANALYSIS SYSTEM", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- ระบบความปลอดภัย ---
TACTICAL_PASSWORD = "ncid"

# --- CSS ตกแต่ง UI ยุทธวิธี (Tactical Theme) ---
st.markdown(
    """
    <style>
    /* พื้นหลังหลักของเว็บ (สีน้ำเงินเข้มจัดเกือบดำ) */
    .stApp { 
        background-color: #0b1120 !important; 
        color: #f1f5f9 !important; 
    }
    
    /* แต่งกรอบ Container ให้เป็นเหมือนการ์ด (Card) สีเทาเข้ม */
    [data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #1e293b !important;
        border: 1px solid #334155 !important;
        border-radius: 12px !important;
        padding: 15px !important;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.5) !important;
    }

    /* แต่งช่องกรอกข้อมูลและ Dropdown ให้อ่านง่าย ตัวหนังสือสีสว่าง */
    .stTextInput input, .stTextArea textarea, div[data-baseweb="select"] > div {
        background-color: #0f172a !important;
        color: #ffffff !important;
        border: 1px solid #3b82f6 !important;
        border-radius: 6px !important;
    }
    
    /* สีของ Placeholder (ข้อความจางๆ ในช่อง) */
    ::placeholder {
        color: #64748b !important;
    }

    /* กล่อง File Uploader */
    [data-testid="stFileUploadDropzone"] {
        background-color: #0f172a !important;
        border: 1px dashed #3b82f6 !important;
        border-radius: 8px !important;
        padding: 10px !important;
    }

    /* แต่งปุ่ม Primary (ปุ่มสีแดง สำหรับ SCAN) */
    button[kind="primary"] {
        background-color: #ef4444 !important; /* สีแดง */
        color: white !important;
        border: none !important;
        font-weight: bold !important;
        border-radius: 6px !important;
    }
    button[kind="primary"]:hover {
        background-color: #dc2626 !important;
    }

    /* แต่งปุ่ม Secondary (ปุ่มสีเขียว สำหรับ อัปโหลด) */
    button[kind="secondary"] {
        background-color: #22c55e !important; /* สีเขียว */
        color: white !important;
        border: none !important;
        font-weight: bold !important;
        border-radius: 6px !important;
    }
    button[kind="secondary"]:hover {
        background-color: #16a34a !important;
    }
    
    /* ซ่อนแถบด้านบนสุดของ Streamlit */
    header {visibility: hidden;}
    </style>
    """,
    unsafe_allow_html=True,
)

# --- หน้า Login ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    col_l1, col_l2, col_l3 = st.columns([1, 2, 1])
    with col_l2:
        st.markdown("<br><br><br>", unsafe_allow_html=True)
        # โลโก้แบบจัดกลาง
        col_img1, col_img2, col_img3 = st.columns([1, 1, 1])
        with col_img2:
            try:
                st.image("logo.png", use_column_width=True)
            except Exception:
                st.markdown("<h1 style='text-align: center; color: #3b82f6;'>🛡️ INTEL</h1>", unsafe_allow_html=True)
                
        st.markdown("<h2 style='text-align: center;'>🔒 RESTRICTED ACCESS</h2>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #94a3b8;'>TACTICAL CELL ANALYSIS SYSTEM</p>", unsafe_allow_html=True)
        
        entered_password = st.text_input("Password", type="password", placeholder="ระบุรหัสผ่าน...")
        if st.button("LOGIN 🚀", type="primary", use_container_width=True):
            if entered_password == TACTICAL_PASSWORD:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("❌ รหัสผ่านไม่ถูกต้อง!")
    st.stop()

# ==========================================
# 🟢 ส่วน Dashboard (เมื่อ Login ผ่านแล้ว)
# ==========================================

# โลโก้และหัวข้อของหน้าหลัก
col_head1, col_head2, col_head3 = st.columns([1, 8, 1], vertical_alignment="center")
with col_head1:
    try:
        st.image("logo.png", width=60)
    except Exception:
        st.markdown("🛡️")
with col_head2:
    st.markdown("<h3 style='color: #60a5fa; margin-bottom: 0;'>CELL & CDR : Tracking System</h3>", unsafe_allow_html=True)
with col_head3:
    if st.button("🚪 Logout"):
        st.session_state.authenticated = False
        st.rerun()

st.markdown("---")

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

# --- สร้าง Session State ---
if "search_message" not in st.session_state:
    st.session_state.search_message = ""
if "alert_type" not in st.session_state:
    st.session_state.alert_type = ""
if "target_df" not in st.session_state:
    st.session_state.target_df = pd.DataFrame()

# ==========================================
# 📍 1. โซนแกะรอยเป้าหมาย (Search) 
# ==========================================
with st.container(border=True):
    st.markdown("#### 📍 1. แกะรอยเป้าหมาย (CELL_ID / ค้นหา LAC)")
    
    with st.form(key="search_form", border=False):
        # ใช้ vertical_alignment="bottom" เพื่อให้กล่องข้อความและปุ่มกดเรียงขอบล่างเสมอกัน
        col_s1, col_s2, col_btn = st.columns([2.5, 2.5, 1], vertical_alignment="bottom")
        
        with col_s1:
            cell_input = st.text_input("รหัส CELL_ID (ปล่อยว่างได้ถ้าค้นหาเฉพาะ LAC)", placeholder="วาง CELL_ID...")
        with col_s2:
            lac_input = st.text_input("รหัส LAC/TAC (ใช้ค้นหาเฉพาะ LAC ได้)", placeholder="วาง LAC/TAC...")
        with col_btn:
            scan_clicked = st.form_submit_button("SCAN 🔍", use_container_width=True, type="primary") # type=primary ทำให้ปุ่มเป็นสีแดงตาม CSS

    # ระบบค้นหา
    if scan_clicked:
        c_val = cell_input.strip()
        l_val = lac_input.strip()
        
        if not c_val and not l_val:
            st.session_state.search_message = "⚠️ กรุณากรอกรหัส CELL_ID หรือ LAC"
            st.session_state.alert_type = "error"
            st.session_state.target_df = pd.DataFrame()
        else:
            with st.spinner("กำลังแกะรอยเป้าหมายจาก Cloud SQL..."):
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
                        st.session_state.search_message = f"🎯 ค้นหาสำเร็จ! พบพิกัดเป้าหมาย {len(filtered_df):,} จุด"
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

# แสดงผลลัพธ์การค้นหา
if st.session_state.search_message:
    if st.session_state.alert_type == "success":
        st.success(st.session_state.search_message)
    else:
        st.error(st.session_state.search_message)

# ==========================================
# 📥 2. โซนอัปโหลดไฟล์
# ==========================================
st.markdown("<br>", unsafe_allow_html=True) # เว้นบรรทัดนิดนึง
with st.container(border=True):
    st.markdown("#### 📥 2. อัปโหลดฐานข้อมูลเสา (G-MoN Pro CSV)")
    
    network_mapping = {
        "🟢 AIS (52001, 52003)": {"name": "AIS", "code": "52001, 52003"},
        "🔴 TRUE (52000, 52004)": {"name": "TRUE", "code": "52000, 52004"},
        "🔵 DTAC (52005, 52018)": {"name": "DTAC", "code": "52005, 52018"},
        "🟡 NT (52002, 52015)": {"name": "NT", "code": "52002, 52015"},
        "⚪ ไม่ระบุ (ใช้ข้อมูลเดิมในไฟล์)": {"name": None, "code": None}
    }

    # จัดเลย์เอาต์อัปโหลดให้ใช้งานง่าย
    col_up1, col_up2 = st.columns([1, 2], vertical_alignment="center")
    
    with col_up1:
        selected_network = st.selectbox("เลือกเครือข่าย", options=list(network_mapping.keys()))
        upload_clicked = st.button("⬆️ อัปโหลดเข้าฐานข้อมูล", use_container_width=True, type="secondary") # type=secondary เป็นสีเขียว
    
    with col_up2:
        uploaded_file = st.file_uploader("ลากไฟล์ CSV มาวางที่นี่", type=["csv"], label_visibility="collapsed")

    # ระบบอัปโหลด
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
                    st.success(f"✅ สำเร็จ! นำเข้าข้อมูล {len(df_upload):,} จุด เรียบร้อยแล้ว")
                except Exception as e:
                    st.error(f"❌ เกิดข้อผิดพลาด: {e}")
        else:
            st.warning("⚠️ กรุณาแนบไฟล์ CSV ก่อนทำการกดอัปโหลด")

# ==========================================
# 🗺️ 3. โซนแผนที่ (Tactical Map)
# ==========================================
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
            radius=6, color="#ef4444", fill=True, fill_color="#ef4444", fill_opacity=0.9,
            popup=f"CELL: {row.get('xci', 'N/A')} | LAC: {row.get('lac/tac', 'N/A')}<br>เครือข่าย: {net_popup} ({net_code_popup})"
        ).add_to(m)

st_folium(m, width="100%", height=700, key="tactical_map")
