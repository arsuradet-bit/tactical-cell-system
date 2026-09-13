# ผลตรวจชุดส่งมอบ

ตรวจเมื่อ 14 กันยายน 2026 โดยใช้ข้อมูลสังเคราะห์และตัวอย่างโครงสร้างจากผู้ใช้

## ผ่านแล้ว

- Python compile และ unit tests 11 กรณี: ตัวอย่าง G-Mon, fingerprint ซ้ำ, รหัสและ PLMN, พิกัดผิดรูปแบบ, วันเวลา ค.ศ./พ.ศ., CSV comma/semicolon/tab, CDR headers และการไม่เก็บเลขระบุตัวบุคคลในผล, G-Mon หลัก/CDR สำรอง, หลาย PLMN, รูปพัด และ escape popup
- Streamlit AppTest: เปิดหน้าได้ไม่มี exception, ค้นหา CELL/LAC/NBID แยกกัน, เงื่อนไขร่วม AND, ล้าง CDR และปิดทางเข้าสู่หน้าใช้งานเมื่อไม่มี Secrets
- ทดสอบ SQL จริงบน PostgreSQL แบบฝัง PGlite 0.3.16 ในหน่วยความจำ ผ่านสะพานคำสั่ง SQLAlchemy: schema, batch import, duplicate, latest by survey timestamp, exact search, PLMN separation, exact-pair lookup, bounds, result limit และ transaction rollback
- ทดสอบเบราว์เซอร์บน localhost: อัปโหลด CDR สังเคราะห์ 3 เหตุการณ์ ได้ G-Mon 2 จุดและ CDR สำรอง 1 จุด แสดงปุ่มเล่นเหตุการณ์และเล่นถึงเหตุการณ์ที่ 3
- กดล้าง CDR แล้วไฟล์หายจาก uploader ผลแผนที่และตัวนับกลับเป็น 0
- ตรวจหน้าเดสก์ท็อปและจอแคบด้วยข้อมูลสังเคราะห์

## ยังไม่ทดสอบกับระบบจริง

- ไม่ได้เปลี่ยน GitHub, Streamlit ที่เผยแพร่อยู่ หรือ Cloud SQL ของผู้ใช้
- ไม่ได้ทดสอบ network/TLS/สิทธิ์ของอินสแตนซ์ intel-db จริง หรือ connection pooling กับผู้ใช้พร้อมกัน 10–15 คน
- ไม่ได้ตรวจ CSV/CDR ต้นฉบับจริง มีเพียงหัวคอลัมน์และตัวอย่างแถวที่ส่งในแชท
- การทดสอบ PGlite ตรวจตรรกะ PostgreSQL แต่ไม่ทดแทนการทดสอบ psycopg2/Cloud SQL ผ่านเครือข่ายจริง
- ยังไม่ได้วัดความเร็วกับขนาดฐานข้อมูลสะสมจริง จึงไม่รับรองเวลาค้นหา

## ก่อนใช้งานจริง

ตั้ง Secrets, สร้างตารางใหม่, ย้ายข้อมูลเดิมหรือนำเข้าใหม่ และทดสอบไฟล์จริงตาม README.md ก่อนสลับผู้ใช้มาใช้ชุดใหม่ ต้องไม่เปิด INTEL_DEMO บนระบบจริง
