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
TACTICAL_PASSWORD = "TAC2026"

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
        <h2 style="color: #6fffe9; margin: 0;">INTEL : TACTICAL CELL ANALYSIS SYSTEM</h2>
        <p style="color: #adb5bd; margin: 5px 0 0 0;">ระบบสืบสวนและวิเคราะห์พิกัดสัญญาณโทรศัพท์เคลื่อนที่ (Cloud SQL Powered)</p>
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
# 📤 ส่วนอัปโหลดข้อมูลจาก G-Mon Pro เข้า Cloud SQL
# ==========================================
with st.expander("📤 นำเข้าข้อมูลเป้าหมายใหม่ (G-Mon Pro CSV Upload)", expanded=False):
    st.markdown("**(Optional) เติมข้อมูลเครือข่ายอัตโนมัติ:** หากในไฟล์ CSV ไม่มีข้อมูลเครือข่าย (เช่น เลข 5200X ไม่มา) ให้พิมพ์ระบุด้านล่าง ระบบจะเติมข้อมูลให้ทุกบรรทัดก่อนบันทึก")
    
    col_up1, col_up2 = st.columns(2)
    with col_up1:
        manual_net_name = st.text_input("ชื่อเครือข่าย", placeholder="เช่น AIS, TRUE, DTAC (เว้นว่างได้ถ้าไม่ต้องการเติม)")
    with col_up2:
        manual_net_code = st.text_input("เลขเครือข่าย (MCC/MNC)", placeholder="เช่น 52003, 52004 (เว้นว่างได้ถ้าไม่ต้องการเติม)")

    uploaded_file = st.file_uploader("ลากไฟล์ CSV จาก G-Mon Pro มาวางที่นี่", type=["csv"])
    
    if uploaded_file is not None:
        if st.button("บันทึกข้อมูลเข้า Cloud SQL", type="primary"):
            with st.spinner("กำลังเตรียมข้อมูลและเขียนลงฐานข้อมูล..."):
                try:
                    # 1. อ่านไฟล์ CSV
                    df_upload = pd.read_csv(uploaded_file)
                    
                    # 2. ปรับชื่อคอลัมน์ให้เป็นตัวพิมพ์เล็กทั้งหมด
                    df_upload.columns = [str(c).strip().lower() for c in df_upload.columns]
                    
                    # 3. ถ้าผู้กองระบุข้อมูลเครือข่ายมา ให้สร้าง/ทับคอลัมน์นั้นใน Dataframe ก่อนดันขึ้น Database
                    if manual_net_name:
                        df_upload['network_name'] = manual_net_name  # เปลี่ยนชื่อคอลัมน์ตรงนี้ให้ตรงกับ Database ได้ครับ
                    if manual_net_code:
                        df_upload['network_code'] = manual_net_code  # เปลี่ยนชื่อคอลัมน์ตรงนี้ให้ตรงกับ Database ได้ครับ
                    
                    # 4. เขียนข้อมูลลง Cloud SQL (ตาราง gmon_survey_logs) แบบต่อท้าย (append)
                    df_upload.to_sql('gmon_survey_logs', con=engine, if_exists='append', index=False)
                    
                    st.success(f"✅ สำเร็จ! นำเข้าข้อมูลพิกัดใหม่จำนวน {len(df_upload):,} จุด เรียบร้อยแล้ว พร้อมใช้งานในระบบค้นหาทันที")
                except Exception as e:
                    st.error(f"❌ เกิดข้อผิดพลาด: {e} (กรุณาเช็คว่าชื่อคอลัมน์ใน CSV ตรงกับในฐานข้อมูลหรือไม่)")

st.markdown("---")

# ==========================================
# 🔍 ส่วนค้นหาพิกัดยุทธวิธี
# ==========================================
with st.form(key="search_form"):
    col_s1, col_s2, col_s3, col_btn = st.columns([2, 2, 2, 1])
    with col_s1:
        cell_input = st.text_input("CELL (XCI)", placeholder="ระบุรหัส CELL...")
    with col_s2:
        lac_input = st.text_input("LAC (LAC/TAC)", placeholder="ระบุรหัส LAC...")
    with col_s3:
        ncid_input = st.text_input("NCID", placeholder="ระบุรหัส NCID...")
    with col_btn:
        st.write("")
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
        # ดึงข้อมูลเพิ่มเติมมาแสดงใน Popup ของจุดบนแผนที่
        net_popup = row.get('network_name', 'N/A')
        net_code_popup = row.get('network_code', 'N/A')
        
        folium.CircleMarker(
            location=[row["lat"], row["lon"]],
            radius=6,
            color="#ff0000",
            fill=True,
            fill_color="#ff0000",
            fill_opacity=0.9,
            popup=f"CELL: {row.get('xci', 'N/A')} | LAC: {row.get('lac/tac', 'N/A')} | NCID: {row.get('ncid', row.get('xnbid', 'N/A'))}<br>เครือข่าย: {net_popup} ({net_code_popup})"
        ).add_to(m)

st_folium(m, width="100%", height=700, key="tactical_map")
