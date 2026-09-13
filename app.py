import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text
from streamlit_folium import st_folium
import folium

# --- ตั้งค่าการเชื่อมต่อ Cloud SQL ---
DB_USER = "postgres"
DB_PASS = "0656637888Ar."
DB_HOST = "34.15.139.132"
DB_PORT = "5432"
DB_NAME = "postgres"

st.set_page_config(
    page_title="INTEL : TACTICAL CELL ANALYSIS SYSTEM", layout="wide"
)

# Custom CSS ธีมเข้มสไตล์ Tactical
st.markdown(
    """
    <style>
    .main { background-color: #0b132b; color: #ffffff; }
    .stApp { background-color: #0b132b; }
    h1, h2, h3, h4, p, label { color: #ffffff !important; }
    .tactical-header {
        background-color: #1c2541; padding: 15px; border-radius: 8px;
        text-align: center; border: 1px solid #3a506b; margin-bottom: 20px;
    }
    .tactical-alert-success {
        background-color: #132a13; color: #52b788; padding: 12px; border-radius: 6px;
        border: 1px solid #2d6a4f; font-weight: bold; margin-bottom: 15px;
    }
    .tactical-alert-error {
        background-color: #2b1313; color: #e63946; padding: 12px; border-radius: 6px;
        border: 1px solid #9d0208; font-weight: bold; margin-bottom: 15px;
    }
    </style>
""",
    unsafe_allow_html=True,
)

# --- สร้าง Session State สำหรับเก็บสถานะข้อความและข้อมูลเป้าหมาย ---
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
        <h2 style="color: #6fffe9; margin: 0;">INTEL : TACTICAL CELL ANALYSIS SYSTEM</h2>
        <p style="color: #adb5bd; margin: 5px 0 0 0;">ระบบสืบสวนและวิเคราะห์พิกัดสัญญาณโทรศัพท์เคลื่อนที่ (Cloud SQL Powered)</p>
    </div>
""",
    unsafe_allow_html=True,
)

# --- ช่องค้นหา ---
with st.form(key="search_form"):
  col_s1, col_s2, col_s3, col_btn = st.columns([2, 2, 2, 1])
  with col_s1:
    cell_input = st.text_input("CELL (XCI)", placeholder="ระบุรหัส CELL...")
  with col_s2:
    lac_input = st.text_input("LAC (LAC/TAC)", placeholder="ระบุรหัส LAC...")
  with col_s3:
    nbid_input = st.text_input("NBID (xNBID)", placeholder="ระบุรหัส NBID...")
  with col_btn:
    st.write("")
    scan_clicked = st.form_submit_button("SCAN 🔍", use_container_width=True, type="primary")

st.markdown("---")

# --- ฟังก์ชันเชื่อมต่อฐานข้อมูลแบบมี Connection Pool เพื่อความเสถียรสูงสุด ---
@st.cache_resource
def get_engine():
  return create_engine(
      f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}",
      pool_size=10,
      max_overflow=20,
      pool_recycle=3600
  )

engine = get_engine()

# เมื่อมีการกดปุ่ม SCAN ให้ดึงข้อมูลจาก Cloud SQL โดยตรงด้วย SQL Query (ใช้ความแรงฐานข้อมูลกรองข้อมูล)
if scan_clicked:
  if not cell_input and not lac_input and not nbid_input:
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

        if nbid_input:
          query += " AND (CAST(xnbid AS TEXT) LIKE :nbid)"
          params["nbid"] = f"%{nbid_input.strip()}%"

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

# --- แสดงผลข้อความแจ้งเตือนแบบค้างไว้ ---
if st.session_state.search_message:
  if st.session_state.alert_type == "success":
    st.markdown(f'<div class="tactical-alert-success">{st.session_state.search_message}</div>', unsafe_allow_html=True)
  else:
    st.markdown(f'<div class="tactical-alert-error">{st.session_state.search_message}</div>', unsafe_allow_html=True)

# --- ส่วนแสดงผลแผนที่ (OpenStreetMap ดั้งเดิม โหลดไว ไร้ลายน้ำกวนใจ) ---
st.subheader("🗺️ แผนที่แสดงพิกัดยุทธวิธี (Tactical Map)")

target_df = st.session_state.target_df

# กำหนดพิกัดกลางเริ่มต้น (กรณีพิกัดแรก หรือยังไม่ได้สแกน)
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

# วาดจุดวงกลมสีแดงลงบนแผนที่ทีละจุด
if not target_df.empty and "lat" in target_df.columns and "lon" in target_df.columns:
  map_df = target_df.dropna(subset=["lat", "lon"]).copy()
  map_df["lat"] = map_df["lat"].astype(float)
  map_df["lon"] = map_df["lon"].astype(float)

  for idx, row in map_df.iterrows():
    folium.CircleMarker(
        location=[row["lat"], row["lon"]],
        radius=6,
        color="#ff0000",
        fill=True,
        fill_color="#ff0000",
        fill_opacity=0.9,
        popup=f"CELL: {row.get('xci', 'N/A')} | LAC: {row.get('lac/tac', 'N/A')}"
    ).add_to(m)

st_folium(m, width="100%", height=700, key="tactical_map")