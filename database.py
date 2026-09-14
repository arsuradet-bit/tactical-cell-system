"""PostgreSQL repository. Only G-Mon records can be written here."""
import json

from sqlalchemy import URL, bindparam, create_engine, text

SELECT = """SELECT o.plmn,o.xci,o.lac,o.xnbid,o.local_cid,o.system,o.lat,o.lon,
            o.observed_at,o.rsrp,o.rssi,o.gps_accuracy,o.site_name FROM intel_gmon_latest l
            JOIN intel_gmon_observations o ON o.id=l.observation_id"""


def connect(config):
    url = URL.create("postgresql+psycopg2", username=config["user"], password=config["password"],
                     host=config["host"], port=int(config.get("port", 5432)), database=config.get("name", "postgres"))
    args = {"connect_timeout": 8, "sslmode": config.get("sslmode", "require"),
            "options": "-c statement_timeout=60000", "application_name": "intel_cell"}
    for key in ("sslrootcert", "sslcert", "sslkey"):
        if config.get(key):
            args[key] = config[key]
    return create_engine(url, pool_size=5, max_overflow=5, pool_timeout=10,
                         pool_pre_ping=True, pool_recycle=1200, connect_args=args, hide_parameters=True)


def health(engine):
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
        return bool(conn.execute(text("SELECT to_regclass('public.intel_gmon_latest') IS NOT NULL")).scalar())


def search(engine, cells=(), lacs=(), nbids=(), plmns=(), bounds=None, limit=2000):
    clauses, params, bindings = [], {"limit": limit + 1}, []
    for column, values in [("xci", cells), ("lac", lacs), ("xnbid", nbids), ("plmn", plmns)]:
        if values:
            clauses.append(f"l.{column} IN :{column}")
            params[column] = list(values)
            bindings.append(bindparam(column, expanding=True))
    if bounds:
        clauses.extend(["o.lat BETWEEN :south AND :north", "o.lon BETWEEN :west AND :east"])
        params.update(bounds)
    if not clauses:
        raise ValueError("กรุณาระบุเงื่อนไขค้นหา")
    statement = text(SELECT + " WHERE " + " AND ".join(clauses) + " ORDER BY l.observed_at DESC,l.plmn,l.xci,l.lac LIMIT :limit").bindparams(*bindings)
    with engine.connect() as conn:
        rows = [dict(r) for r in conn.execute(statement, params).mappings()]
    return rows[:limit], len(rows) > limit


def lookup_pairs(engine, pairs, plmns=()):
    pairs = list(set(pairs))
    results = []
    # Exact pairs only: no Cartesian product, no identifier from CDR is logged.
    with engine.connect() as conn:
        for offset in range(0, len(pairs), 300):
            chunk = pairs[offset:offset + 300]
            params, values = {}, []
            for i, (cell, lac) in enumerate(chunk):
                values.append(f"(:c{i},:l{i})")
                params[f"c{i}"], params[f"l{i}"] = cell, lac
            if not values:
                continue
            sql = SELECT + " JOIN (VALUES " + ",".join(values) + ") AS wanted(cell,lac) ON l.xci=wanted.cell AND l.lac=wanted.lac"
            statement = text(sql + (" WHERE l.plmn IN :plmns" if plmns else ""))
            if plmns:
                statement = statement.bindparams(bindparam("plmns", expanding=True))
                params["plmns"] = list(plmns)
            results.extend(dict(r) for r in conn.execute(statement, params).mappings())
    return results


def save_gmon(engine, records):
    insert = text("""INSERT INTO intel_gmon_observations
        (fingerprint,plmn,xci,lac,xnbid,local_cid,system,lat,lon,observed_at,rsrp,rssi,gps_accuracy,site_name,raw)
        SELECT fingerprint,plmn,xci,lac,xnbid,local_cid,system,lat,lon,observed_at,rsrp,rssi,gps_accuracy,site_name,raw
        FROM jsonb_to_recordset(CAST(:batch AS jsonb)) AS batch(
        fingerprint TEXT,plmn TEXT,xci TEXT,lac TEXT,xnbid TEXT,local_cid TEXT,system TEXT,
        lat DOUBLE PRECISION,lon DOUBLE PRECISION,observed_at TIMESTAMP,rsrp DOUBLE PRECISION,
        rssi DOUBLE PRECISION,gps_accuracy DOUBLE PRECISION,site_name TEXT,raw JSONB)
        ORDER BY plmn,xci,lac,observed_at,fingerprint
        ON CONFLICT (fingerprint) DO NOTHING RETURNING id""")
    latest = text("""INSERT INTO intel_gmon_latest AS current
        (plmn,xci,lac,observation_id,xnbid,observed_at)
        SELECT DISTINCT ON (plmn,xci,lac) plmn,xci,lac,id,xnbid,observed_at
        FROM intel_gmon_observations WHERE id = ANY(:ids)
        ORDER BY plmn,xci,lac,observed_at DESC,id ASC
        ON CONFLICT (plmn,xci,lac) DO UPDATE SET
        observation_id=EXCLUDED.observation_id,xnbid=EXCLUDED.xnbid,observed_at=EXCLUDED.observed_at
        WHERE EXCLUDED.observed_at > current.observed_at""")
    inserted = 0
    # Two round trips per batch. Atomic import, even if a later batch fails.
    with engine.begin() as conn:
        ordered = sorted(records, key=lambda r: (r["plmn"], r["xci"], r["lac"], r["observed_at"], r["fingerprint"]))
        for offset in range(0, len(ordered), 500):
            batch = [{**r, "observed_at": r["observed_at"].isoformat()} for r in ordered[offset:offset+500]]
            ids = list(conn.execute(insert, {"batch": json.dumps(batch, ensure_ascii=False)}).scalars())
            inserted += len(ids)
            if ids:
                conn.execute(latest, {"ids": ids})
    return inserted, len(records) - inserted
