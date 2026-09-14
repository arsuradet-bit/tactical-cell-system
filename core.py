"""Pure data processing. CDR is never persisted or globally cached."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

import pandas as pd

NETWORKS = {"52001": "AIS", "52003": "AIS", "52000": "TRUE", "52004": "TRUE",
            "52005": "DTAC", "52018": "DTAC", "52002": "NT", "52015": "NT"}


def network_label(value):
    name = NETWORKS.get(value)
    return f"{ {'AIS':'🟢','TRUE':'🔴','DTAC':'🔵','NT':'🟡'}[name]} {name} ({value})" if name else value


def paired_ids(cells, lacs):
    """Pair lines before normalization; never form a Cartesian product."""
    def lines(value):
        return [line.strip() for line in value.strip().splitlines()] if value.strip() else []
    c, l = lines(cells), lines(lacs)
    if c and l and len(c) != len(l):
        raise ValueError("จำนวนบรรทัด CELL และ LAC ต้องเท่ากัน เพื่อจับคู่ตามบรรทัด")
    if any(not x for x in c + l):
        raise ValueError("มีบรรทัดว่างระหว่างรหัส กรุณาลบให้ตรงคู่ก่อนค้นหา")
    if max(len(c), len(l)) > 200:
        raise ValueError("ค้นหาได้ไม่เกิน 200 บรรทัดต่อครั้ง")
    return ([identifier(x) for x in c], [identifier(x) for x in l],
            [(identifier(a), identifier(b)) for a, b in zip(c, l)] if c and l else [])


def display_time(value):
    try:
        return timestamp(value).strftime("%d/%m/%y %H:%M:%S")
    except (ValueError, TypeError):
        return clean(value) or "—"


def signal_level(row):
    value = number(row.get("rsrp"))
    # RSRP thresholds are only applied to LTE; RSCP/NR require separate scales.
    system = clean(row.get("system")).upper()
    if value is None or system not in {"4", "4.0", "4G", "LTE"}:
        return "#94a3b8", "ไม่มีเกณฑ์ / ไม่มีค่า", value
    return ("#22c55e", "HIGH", value) if value >= -90 else (("#facc15", "MID", value) if value >= -105 else ("#ef4444", "LOW", value))


def clean(value):
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def identifier(value):
    s = clean(value)
    if not s or s.lower() in {"nan", "none", "null", "--", "-"}:
        return ""
    try:
        d = Decimal(s)
        if not d.is_finite() or d < 0 or d != d.to_integral_value():
            raise ValueError("รหัสต้องเป็นจำนวนเต็มตั้งแต่ศูนย์ขึ้นไป")
        return str(int(d))
    except InvalidOperation as exc:
        raise ValueError("รหัส CELL/LAC/NBID ต้องเป็นตัวเลขฐานสิบ") from exc


def plmn_value(value):
    s = clean(value)
    if re.fullmatch(r"\d{5,6}", s):
        return s
    # Handle numeric Excel cells without removing leading zeros in text cells.
    if s.endswith(".0") and re.fullmatch(r"\d{5,6}", s[:-2]):
        return s[:-2]
    raise ValueError("PLMN ต้องมีตัวเลข 5 หรือ 6 หลัก")


def parse_ids(value):
    tokens = re.split(r"[\s,;]+", clean(value))
    values = list(dict.fromkeys(identifier(t) for t in tokens if t))
    if len(values) > 200:
        raise ValueError("ค้นหาได้ไม่เกิน 200 รหัสต่อช่อง")
    return values


def number(value):
    try:
        x = float(value)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def coordinates(lat, lon):
    lat, lon = number(lat), number(lon)
    if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    if lat == 0 and lon == 0:
        return None
    return lat, lon


def timestamp(value):
    s = clean(value)
    if not s:
        raise ValueError("ไม่มีวันเวลา")
    # Accept ISO/G-Mon Y/M/D and Thai day-first dates, including Buddhist years.
    m = re.fullmatch(r"(\d{1,4})[/.-](\d{1,2})[/.-](\d{1,4})(?:[ T]+(\d{1,2}):(\d{2})(?::(\d{2})(?:\.\d+)?)?)?", s)
    if not m:
        raise ValueError("รูปแบบวันเวลาไม่รองรับ ใช้ YYYY/MM/DD HH:MM:SS หรือ DD/MM/YYYY HH:MM:SS")
    a, b, c = map(int, m.group(1, 2, 3))
    year, month, day = (a, b, c) if len(m.group(1)) == 4 else (c, b, a)
    if year > 2400:
        year -= 543
    if year < 100:
        year += 2000
    return datetime(year, month, day, int(m.group(4) or 0), int(m.group(5) or 0), int(m.group(6) or 0))


def read_table(data: bytes, filename: str, max_rows=100000):
    if len(data) > 20 * 1024 * 1024:
        raise ValueError("ไฟล์ต้องไม่เกิน 20 MB")
    if filename.lower().endswith(".xlsx"):
        sheets = pd.read_excel(io.BytesIO(data), sheet_name=None, dtype=str, keep_default_na=False)
        frames = [frame for frame in sheets.values() if not frame.empty]
        if not frames:
            raise ValueError("ไฟล์ไม่มีรายการข้อมูล")
        # Preserve every row from every worksheet, including intentional duplicates.
        df = pd.concat(frames, ignore_index=True, sort=False)
    else:
        decoded = None
        encodings = ("utf-16",) if data.startswith((b"\xff\xfe", b"\xfe\xff")) else ("utf-8-sig", "cp874")
        for encoding in encodings:
            try:
                decoded = data.decode(encoding)
                break
            except UnicodeError:
                continue
        if decoded is None:
            raise ValueError("อ่านรหัสภาษาในไฟล์ไม่ได้ กรุณาบันทึกเป็น UTF-8")
        lines = decoded.splitlines()
        start = next((i for i, line in enumerate(lines[:30]) if
                      ("XCI" in line.upper() and "PLMN" in line.upper()) or
                      ("CELL ID" in line.upper() and "LAC" in line.upper())), 0)
        body = "\n".join(lines[start:])
        try:
            delimiter = csv.Sniffer().sniff(body[:8192], delimiters=",;\t").delimiter
        except csv.Error:
            delimiter = max(",;\t", key=lambda d: (lines[start] if lines else "").count(d))
        df = pd.read_csv(io.StringIO(body), sep=delimiter, dtype=str, keep_default_na=False)
    df.columns = [str(c).strip().lower().replace("\ufeff", "") for c in df.columns]
    if df.columns.duplicated().any() or any(re.search(r"\.\d+$", c) and c.rsplit(".", 1)[0] in df.columns for c in df.columns):
        raise ValueError("พบชื่อคอลัมน์ซ้ำ กรุณาตรวจหัวตาราง")
    # Drop only completely empty columns, never discard actual data in column 43.
    df = df.loc[:, [c for c in df.columns if not (c.startswith("unnamed:") and df[c].map(clean).eq("").all())]]
    if df.empty:
        raise ValueError("ไฟล์ไม่มีรายการข้อมูล")
    if max_rows is not None and len(df) > max_rows:
        raise ValueError("ไฟล์หนึ่งรองรับไม่เกิน 100,000 แถว กรุณาแบ่งไฟล์")
    return df


def require(df, names):
    missing = set(names) - set(df.columns)
    if missing:
        raise ValueError("ขาดคอลัมน์: " + ", ".join(sorted(missing)))


def prepare_gmon(df):
    aliases = {"lac_tac": "lac/tac", "rsrp_rscp": "rsrp/rscp", "rsrq_ecio": "rsrq/ecio", "pci_psc_bsic": "pci/psc/bsic"}
    df = df.rename(columns={a:b for a,b in aliases.items() if a in df.columns and b not in df.columns})
    require(df, ["plmn", "xci", "lac/tac", "lat", "lon", "date", "time"])
    records, errors = [], []
    for index, row in df.iterrows():
        try:
            gps = coordinates(row["lat"], row["lon"])
            if gps is None:
                raise ValueError("พิกัดว่างหรืออยู่นอกช่วง")
            xci, lac = identifier(row["xci"]), identifier(row["lac/tac"])
            if not xci or not lac:
                raise ValueError("ไม่มี XCI หรือ LAC/TAC")
            # Subscriber/device identifiers are not needed for G-Mon analysis;
            # exclude them before the raw row can be persisted.
            raw = {k: clean(v) for k, v in row.items()
                   if not re.search(r"(?:^|[^a-z])(imsi|imei|number ?a|number ?b)(?:$|[^a-z])", str(k).lower())}
            record = dict(plmn=plmn_value(row["plmn"]), xci=xci, lac=lac,
                          xnbid=identifier(row.get("xnbid")), local_cid=identifier(row.get("local_cid")),
                          system=clean(row.get("system")), lat=gps[0], lon=gps[1],
                          observed_at=timestamp(clean(row["date"]) + " " + clean(row["time"])),
                          rsrp=number(row.get("rsrp/rscp")), rssi=number(row.get("rssi")),
                          gps_accuracy=number(row.get("gps_accuracy")),
                          site_name=clean(row.get("clf_label")), raw=raw)
            canonical = {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in record.items() if k != "raw"}
            mapped = {"plmn", "xci", "lac/tac", "xnbid", "local_cid", "system", "lat", "lon", "date", "time",
                      "rsrp/rscp", "rssi", "gps_accuracy", "clf_label", "id", "network_name", "network_code"}
            canonical["extra"] = {k: v for k, v in raw.items() if k not in mapped and v}
            record["fingerprint"] = hashlib.sha256(json.dumps(canonical, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
            records.append(record)
        except (ValueError, TypeError) as exc:
            errors.append({"แถวข้อมูล": int(index) + 1, "ปัญหา": str(exc)})
    return records, pd.DataFrame(errors)


def prepare_cdr(df, kind="CDR", offset=0):
    require(df, ["cell id", "lac", "start date"])
    records, errors = [], []
    for index, row in df.iterrows():
        try:
            cell, lac = identifier(row["cell id"]), identifier(row["lac"])
            if not cell or not lac:
                raise ValueError("ไม่มี Cell ID หรือ LAC")
            when = timestamp(row["start date"])
            gps = coordinates(row.get("latitude"), row.get("longitude"))
            # Do not infer subtypes from Service Type.  The uploaded file is
            # the sole source of truth: every row in a VOICE file is VOICE,
            # and every row in a DATA file is DATA.
            cdr_kind = str(kind or "CDR").upper()
            records.append(dict(event_id=int(index) + 1 + offset, event_type=cdr_kind, cdr_kind=cdr_kind,
                                xci=cell, lac=lac, event_at=when,
                                cdr_lat=gps[0] if gps else None, cdr_lon=gps[1] if gps else None,
                                site_name=clean(row.get("site name")),
                                area=" · ".join(clean(row.get(k)) for k in ["sub-district", "district", "province"] if clean(row.get(k)))))
        except (ValueError, TypeError) as exc:
            errors.append({"แถวข้อมูล": int(index) + 1, "ปัญหา": str(exc)})
    return pd.DataFrame(records), pd.DataFrame(errors)


def prepare_camera(df, offset=0):
    """Normalize checkpoint/camera exports without requiring one vendor schema."""
    aliases = {}
    for c in df.columns:
        key = re.sub(r"[^a-z0-9ก-๙]+", " ", str(c).lower()).strip()
        if "ทะเบียน" in key or "อักษร" in key or "plate" in key or "license" in key: aliases[c] = "plate"
        elif "จังหวัด" in key or "province" in key: aliases[c] = "province"
        elif "ละติจูด" in key or "latitude" in key or key in {"lat", "พิกัด lat"}: aliases[c] = "lat"
        elif "ลองจิจูด" in key or "longitude" in key or key in {"lon", "lng", "พิกัด lon"}: aliases[c] = "lon"
        elif "เวลา" in key or "time" in key or "date" in key: aliases[c] = "camera_time"
        elif "ด่าน" in key or "กล้อง" in key or "checkpoint" in key or "camera" in key: aliases[c] = "checkpoint"
    data = df.rename(columns=aliases)
    # Camera exports often use a blank/locale-specific header; the documented
    # four-column layout is a safe fallback when names cannot be decoded.
    if any(c not in data.columns for c in ("plate", "checkpoint", "camera_time")) and len(data.columns) >= 4:
        positional = list(data.columns[:4])
        for source, target in zip(positional, ("plate", "province", "checkpoint", "camera_time")):
            if target not in data.columns: data = data.rename(columns={source: target})
    if "checkpoint" not in data.columns and len(df.columns) >= 3:
        data["checkpoint"] = df.iloc[:, 2]
    required = ["plate", "checkpoint", "camera_time"]
    missing = [c for c in required if c not in data.columns]
    if missing: raise ValueError("ไฟล์กล้องขาดคอลัมน์: " + ", ".join(missing))
    records, errors = [], []
    for index, row in data.iterrows():
        try:
            raw_checkpoint = clean(row.get("checkpoint"))
            checkpoint = raw_checkpoint.split("|", 1)[1].strip() if "|" in raw_checkpoint else raw_checkpoint
            direction = "เข้า กทม." if re.search(r"(?:_|\s)เข้า$", checkpoint, re.I) else ("ออกจาก กทม." if re.search(r"(?:_|\s)ออก$", checkpoint, re.I) else "")
            base = re.sub(r"(?:_|\s)(?:เข้า|ออก)$", "", checkpoint, flags=re.I).replace("_", " ").strip()
            records.append(dict(camera_id=int(index)+1+offset, event_type="CAMERA", source="กล้อง", plate=clean(row.get("plate")),
                                province=clean(row.get("province")), checkpoint=base, direction=direction,
                                camera_time=timestamp(clean(row.get("camera_time"))),
                                lat=clean(row.get("lat")), lon=clean(row.get("lon"))))
        except (ValueError, TypeError) as exc:
            errors.append({"แถวข้อมูล": int(index)+1, "ปัญหา": str(exc)})
    return pd.DataFrame(records), pd.DataFrame(errors)


def match_cdr(events, candidates):
    groups = {}
    for row in candidates:
        groups.setdefault((row["xci"], row["lac"]), []).append(row)
    output = []
    for event in events.sort_values(["event_at", "event_id"]).to_dict("records"):
        matches = groups.get((event["xci"], event["lac"]), [])
        valid = [m for m in matches if coordinates(m["lat"], m["lon"])]
        if valid:
            ambiguous = len({m["plmn"] for m in valid}) > 1
            for row in valid:
                output.append({**event, **row, "event_at": event["event_at"], "source": "G-Mon",
                               "ambiguous": ambiguous, "status": "หลาย PLMN — เลือกเครือข่าย" if ambiguous else "พบพิกัด"})
        else:
            gps = coordinates(event["cdr_lat"], event["cdr_lon"])
            output.append({**event, "lat": gps[0] if gps else None, "lon": gps[1] if gps else None,
                           "plmn": "", "xnbid": "", "source": "CDR สำรอง" if gps else "ไม่พบพิกัด",
                           "ambiguous": False, "status": "พิกัดสำรอง" if gps else "ไม่พบพิกัด"})
    return output


def sector_points(lat, lon, bearing, width, radius):
    result = [[lat, lon]]
    p1, l1, distance = math.radians(lat), math.radians(lon), radius / 6371008.8
    for i in range(49):
        angle = math.radians(bearing - width / 2 + width * i / 48)
        p2 = math.asin(math.sin(p1) * math.cos(distance) + math.cos(p1) * math.sin(distance) * math.cos(angle))
        l2 = l1 + math.atan2(math.sin(angle) * math.sin(distance) * math.cos(p1), math.cos(distance) - math.sin(p1) * math.sin(p2))
        result.append([math.degrees(p2), (math.degrees(l2) + 540) % 360 - 180])
    return result + [[lat, lon]]
