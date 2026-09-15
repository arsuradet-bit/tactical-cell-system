import io
import unittest
from datetime import datetime

import pandas as pd

from core import coordinates, identifier, match_cdr, parse_ids, plmn_value, prepare_cdr, prepare_camera, prepare_gmon, read_table, sector_points, timestamp
from maps import build_map


class DataTests(unittest.TestCase):
    def gmon(self):
        return pd.DataFrame([dict(plmn="52004", xci="30020114", xnbid="117266", **{
            "lac/tac": "55653", "lat": "6.876632", "lon": "100.417216", "date": "2026/08/30", "time": "17:05:16"})])

    def test_actual_header_example(self):
        records, errors = prepare_gmon(self.gmon())
        self.assertTrue(errors.empty)
        self.assertEqual(records[0]["xci"], "30020114")
        self.assertEqual(records[0]["observed_at"], datetime(2026, 8, 30, 17, 5, 16))

    def test_duplicate_fingerprint(self):
        a, _ = prepare_gmon(self.gmon())
        b, _ = prepare_gmon(self.gmon())
        self.assertEqual(a[0]["fingerprint"], b[0]["fingerprint"])
        frame = self.gmon()
        frame.loc[0, "time"] = "17:06:16"
        c, _ = prepare_gmon(frame)
        self.assertNotEqual(a[0]["fingerprint"], c[0]["fingerprint"])

    def test_identifiers(self):
        self.assertEqual(identifier("30020114.0"), "30020114")
        self.assertEqual(plmn_value("00101"), "00101")
        self.assertEqual(parse_ids("18,19\n18"), ["18", "19"])
        with self.assertRaises(ValueError):
            identifier("18 OR 1=1")
        with self.assertRaises(ValueError):
            identifier("2.2")

    def test_invalid_coordinates(self):
        for lat, lon in [(91, 100), (7, 181), ("", ""), (float('inf'), 1), (0, 0)]:
            self.assertIsNone(coordinates(lat, lon))
        frame = self.gmon()
        frame.loc[0, "lat"] = "invalid"
        records, errors = prepare_gmon(frame)
        self.assertEqual(len(records), 0)
        self.assertEqual(len(errors), 1)

    def test_dates(self):
        self.assertEqual(timestamp("30/08/2569 17:05:16"), timestamp("2026/08/30 17:05:16"))
        with self.assertRaises(ValueError):
            timestamp("31/02/2026 10:00:00")

    def test_delimiters(self):
        for sep in [",", ";", "\t"]:
            content = self.gmon().to_csv(index=False, sep=sep).encode("utf-8-sig")
            parsed = read_table(content, "gmon.csv")
            self.assertEqual(len(prepare_gmon(parsed)[0]), 1)

    def test_cdr_headers_and_privacy(self):
        frame = pd.DataFrame([{"cell id":"30020114", "lac":"55653", "start date":"30/08/2026 18:00:00",
                               "latitude":"7.1", "longitude":"100.1", "number a":"secret", "imsi":"private"}])
        events, errors = prepare_cdr(frame)
        self.assertTrue(errors.empty)
        self.assertNotIn("number a", events.columns)
        self.assertNotIn("imsi", events.columns)
        records, _ = prepare_gmon(self.gmon())
        matched = match_cdr(events, records)
        self.assertEqual(matched[0]["source"], "G-Mon")
        self.assertEqual(matched[0]["lat"], 6.876632)
        self.assertEqual(matched[0]["event_at"].hour, 18)
        fallback = match_cdr(events, [])
        self.assertEqual(fallback[0]["source"], "CDR สำรอง")

    def test_cdr_service_type_normalization(self):
        frame = pd.DataFrame([
            {"service type":"MOC", "cell id":"1", "lac":"2", "start date":"2026/01/01 00:00:00"},
            {"service type":"MTC", "cell id":"1", "lac":"2", "start date":"2026/01/01 00:00:01"},
            {"service type":"SMT", "cell id":"1", "lac":"2", "start date":"2026/01/01 00:00:02"},
            {"service type":"SMS-MC", "cell id":"1", "lac":"2", "start date":"2026/01/01 00:00:03"},
        ])
        events, errors = prepare_cdr(frame)
        self.assertTrue(errors.empty)
        self.assertEqual(events.event_type.tolist(), ["CDR", "CDR", "CDR", "CDR"])

    def test_camera_checkpoint_direction(self):
        frame = pd.DataFrame([{"plate":"3", "province":"BKK", "checkpoint":"car|gate_out", "camera_time":"2026/07/19 18:57:44"}])
        records, errors = prepare_camera(frame)
        self.assertTrue(errors.empty)
        self.assertEqual(records.iloc[0]["checkpoint"], "gate out")

    def test_camera_time_before_date(self):
        records, errors = prepare_camera(pd.DataFrame([{
            "อักษร": "TEST", "จังหวัด": "ทดสอบ", "ด่าน": "รถ|ด่านทดสอบ_ออก",
            "เวลา": "18:57:44 19/07/2026"}]))
        self.assertTrue(errors.empty)
        self.assertEqual(records.iloc[0]["camera_time"].strftime("%Y-%m-%d %H:%M:%S"), "2026-07-19 18:57:44")

    def test_ambiguous_plmn(self):
        events, _ = prepare_cdr(pd.DataFrame([{"cell id":"30020114", "lac":"55653", "start date":"2026/08/30 18:00:00"}]))
        records, _ = prepare_gmon(self.gmon())
        result = match_cdr(events, [records[0], {**records[0], "plmn":"52003"}])
        self.assertEqual(len(result), 2)
        self.assertTrue(all(r["ambiguous"] for r in result))
        self.assertEqual(match_cdr(events, [])[0]["source"], "ไม่พบพิกัด")

    def test_sector_north(self):
        points = sector_points(7, 100, 0, 90, 1000)
        self.assertEqual(points[0], points[-1])
        self.assertGreater(points[25][0], 7)
        self.assertAlmostEqual(points[25][1], 100, places=5)

    def test_map_escapes_popup(self):
        row = dict(lat=7, lon=100, xci="<script>alert(1)</script>", lac="1", plmn="52003", xnbid="2")
        html = build_map([row]).get_root().render()
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_cdr_map_playback_and_gap(self):
        rows = [dict(lat=7+i/100, lon=100, xci="1", lac="1", event_id=i, event_at=datetime(2026, 8, 30, 10, i)) for i in range(3)]
        rows[1]["ambiguous"] = True
        html = build_map(rows, path=True).get_root().render()
        self.assertNotIn("L.polyline(", html)
        self.assertIn("setInterval", html)


if __name__ == "__main__":
    unittest.main()
