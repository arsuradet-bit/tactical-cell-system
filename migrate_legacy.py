"""Explicit legacy migration, run locally by an administrator after schema.sql."""
import argparse
from pathlib import Path
import tomllib

import pandas as pd
from sqlalchemy import text

from core import prepare_gmon
from database import connect, save_gmon


def main():
    parser = argparse.ArgumentParser(description="ตรวจ/คัดลอก G-Mon เดิม โดยไม่แก้ไขหรือลบตารางเดิม")
    parser.add_argument("--secrets", default=".streamlit/secrets.toml")
    parser.add_argument("--apply", action="store_true", help="เขียนตารางใหม่จริง; ถ้าไม่ระบุจะตรวจอย่างเดียว")
    args = parser.parse_args()
    config = tomllib.loads(Path(args.secrets).read_text(encoding="utf-8"))
    engine = connect(config["database"])
    total = valid = invalid = inserted = duplicate = 0
    with engine.connect().execution_options(stream_results=True) as conn:
        for chunk in pd.read_sql(text("SELECT * FROM gmon_survey_logs"), conn, chunksize=2000):
            chunk.columns = [str(c).strip().lower() for c in chunk.columns]
            records, errors = prepare_gmon(chunk.reset_index(drop=True))
            total += len(chunk)
            valid += len(records)
            invalid += len(errors)
            if args.apply:
                added, skipped = save_gmon(engine, records)
                inserted += added
                duplicate += skipped
    print(dict(mode="apply" if args.apply else "check-only", total=total, valid=valid, invalid=invalid,
               inserted=inserted, duplicates=duplicate))
    if invalid:
        print("พบแถวผิดรูปแบบ ยังเก็บอยู่ในตารางเดิม กรุณาตรวจข้อมูลก่อนใช้งานจริง")


if __name__ == "__main__":
    main()
