"""Original survey rows plus append-only uploads; CDR is never persisted."""
import json
from sqlalchemy import bindparam, text
from database import connect
from core import clean, coordinates, identifier, number, timestamp


def health(engine):
    with engine.connect() as conn:
        return bool(conn.execute(text("SELECT to_regclass('public.intel_gmon_uploads') IS NOT NULL")).scalar())


def normalized(expression):
    return f"CASE WHEN ({expression}) ~ '^[0-9]+([.][0-9]+)?([eE][+]?[0-9]+)?$' THEN CASE WHEN ({expression})::numeric = trunc(({expression})::numeric) THEN trunc(({expression})::numeric)::text END ELSE ({expression}) END"


SOURCE = """WITH raw_rows AS (
 SELECT 'legacy:' || g.ctid::text AS observation_key, to_jsonb(g) AS raw FROM gmon_survey_logs g
 UNION ALL SELECT 'upload:' || id::text, raw FROM intel_gmon_uploads
), observations AS (SELECT observation_key,raw,
""" + ",".join(normalized(expr) + " AS " + name for name, expr in [
    ("xci", "raw->>'xci'"), ("lac", "coalesce(raw->>'lac/tac',raw->>'lac_tac')"),
    ("xnbid", "raw->>'xnbid'"), ("plmn", "raw->>'plmn'")]) + " FROM raw_rows) "

SOURCE_UPLOAD = """WITH raw_rows AS (
 SELECT 'upload:' || id::text AS observation_key, raw FROM intel_gmon_uploads
), observations AS (SELECT observation_key,raw,
""" + ",".join(normalized(expr) + " AS " + name for name, expr in [
    ("xci", "raw->>'xci'"), ("lac", "coalesce(raw->>'lac/tac',raw->>'lac_tac')"),
    ("xnbid", "raw->>'xnbid'"), ("plmn", "raw->>'plmn'")]) + " FROM raw_rows) "


# Fast path for migrated, indexed observations; raw uploads remain supported.
SOURCE_FAST = """WITH raw_uploads AS (
 SELECT 'upload:' || id::text AS observation_key, raw FROM intel_gmon_uploads
), uploads AS (SELECT observation_key,raw,
""" + ",".join(normalized(expr) + " AS " + name for name, expr in [
    ("xci", "raw->>'xci'"), ("lac", "coalesce(raw->>'lac/tac',raw->>'lac_tac')"),
    ("xnbid", "raw->>'xnbid'"), ("plmn", "raw->>'plmn'")]) + """ FROM raw_uploads), observations AS (
 SELECT 'obs:' || id::text AS observation_key, raw, xci, lac, xnbid, plmn FROM intel_gmon_observations
 UNION ALL SELECT observation_key, raw, xci, lac, xnbid, plmn FROM uploads
) """

def _source(engine):
    with engine.connect() as conn:
        normalized_count = conn.execute(text("SELECT CASE WHEN to_regclass('public.intel_gmon_observations') IS NULL THEN 0 ELSE (SELECT count(*) FROM intel_gmon_observations) END")).scalar()
        if normalized_count:
            return SOURCE_FAST
        legacy = bool(conn.execute(text("SELECT to_regclass('public.gmon_survey_logs') IS NOT NULL")).scalar())
    return SOURCE if legacy else SOURCE_UPLOAD


def materialize(row):
    raw = row["raw"]
    if isinstance(raw, str):
        raw = json.loads(raw)
    gps = coordinates(raw.get("lat"), raw.get("lon"))
    try:
        observed = timestamp(clean(raw.get("date")) + " " + clean(raw.get("time")))
    except ValueError:
        observed = None
    return dict(observation_key=row["observation_key"], xci=row["xci"], lac=row["lac"],
                lac_display=clean(raw.get("lac/tac", raw.get("lac_tac"))),
                plmn=row["plmn"], xnbid=row["xnbid"], system=clean(raw.get("system")),
                lat=gps[0] if gps else None, lon=gps[1] if gps else None,
                observed_at=observed, rsrp=number(raw.get("rsrp/rscp", raw.get("rsrp_rscp"))),
                rssi=number(raw.get("rssi")), gps_accuracy=number(raw.get("gps_accuracy")),
                site_name=clean(raw.get("clf_label")), source="G-Mon",
                status="พบพิกัด" if gps else "พิกัดว่างหรือไม่ถูกต้อง")


def search(engine, cells=(), lacs=(), nbids=(), plmns=(), bounds=None, limit=None, pairs=()):
    clauses, params, bindings = [], {}, []
    if pairs:
        pair_clauses = []
        for i, (cell, lac) in enumerate(dict.fromkeys(pairs)):
            pair_clauses.append(f"(xci=:cell{i} AND lac=:lac{i})")
            params[f"cell{i}"], params[f"lac{i}"] = identifier(cell), identifier(lac)
        clauses.append("(" + " OR ".join(pair_clauses) + ")")
    for column, values in [("xci", () if pairs else cells), ("lac", () if pairs else lacs), ("xnbid", nbids), ("plmn", plmns)]:
        if values:
            clauses.append(f"{column} IN :{column}")
            params[column] = [identifier(v) for v in values]
            bindings.append(bindparam(column, expanding=True))
    if bounds:
        for name, lo, hi in [("lat", "south", "north"), ("lon", "west", "east")]:
            clauses.append(f"CASE WHEN raw->>'{name}' ~ '^-?[0-9]+([.][0-9]+)?$' THEN (raw->>'{name}')::numeric BETWEEN :{lo} AND :{hi} ELSE false END")
        params.update(bounds)
    if not clauses:
        raise ValueError("กรุณาระบุเงื่อนไขค้นหา")
    suffix = " ORDER BY observation_key" + (" LIMIT :limit" if limit is not None else "")
    if limit is not None:
        params["limit"] = limit
    statement = text(_source(engine) + "SELECT * FROM observations WHERE " + " AND ".join(clauses) + suffix).bindparams(*bindings)
    with engine.connect() as conn:
        rows = [materialize(r) for r in conn.execute(statement, params).mappings()]
    return rows, False


def lookup_pairs(engine, pairs, plmns=()):
    unique_pairs = list(dict.fromkeys(pairs))
    results = []
    # Bound SQL size, not the number of CDR events. Canonicalize before batching.
    unique_pairs = list(dict.fromkeys((identifier(c), identifier(l)) for c, l in unique_pairs))
    for start in range(0, len(unique_pairs), 40):
        # A fresh short transaction per batch keeps large CDR imports from
        # holding one Cloud SQL connection for the entire analysis.
        results.extend(search(engine, pairs=unique_pairs[start:start+40], plmns=plmns, limit=None)[0])
    return results


def save_raw(engine, frame):
    """Atomic append of every input row/column, including repeated/invalid GPS rows."""
    records = [{str(k): clean(v) for k, v in r.items()} for r in frame.to_dict("records")]
    with engine.begin() as conn:
        for offset in range(0, len(records), 500):
            conn.execute(text("INSERT INTO intel_gmon_uploads(raw) SELECT value FROM jsonb_array_elements(CAST(:batch AS jsonb))"),
                         {"batch": json.dumps(records[offset:offset+500], ensure_ascii=False)})
    return len(records)

def checkpoints(engine):
    """Read the checkpoint reference table used to place camera events."""
    with engine.connect() as conn:
        return [dict(r) for r in conn.execute(text(
            "SELECT checkpoint_code, checkpoint_name, direction, lat, lon FROM intel_checkpoints"
        )).mappings()]
