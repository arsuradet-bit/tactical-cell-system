import html

import folium
from branca.element import MacroElement, Template

from core import coordinates, sector_points


def build_map(rows, center=None, zoom=7, fit=True, sector=False, bearing=None,
              radius=1000, beam=90, path=False, related=()):
    m = folium.Map(location=center or [13.15, 100.6], zoom_start=zoom, tiles="OpenStreetMap",
                   prefer_canvas=True, control_scale=True)
    primary = folium.FeatureGroup(name="ผลค้นหา", show=True).add_to(m)
    supplemental = folium.FeatureGroup(name="CELL ร่วม NBID (ไม่ทราบทิศ)", show=True).add_to(m)
    points = []
    for row, group in [(r, primary) for r in rows] + [(r, supplemental) for r in related]:
        gps = coordinates(row.get("lat"), row.get("lon"))
        if not gps:
            continue
        points.append(gps)
        source = row.get("source", "G-Mon")
        color = "#f0b65b" if source == "CDR สำรอง" else "#4ac5c1"
        if row.get("ambiguous"):
            color = "#c49cf3"
        if group is supplemental:
            color = "#8293aa"
        def esc(value):
            return html.escape(str(value if value is not None else "—"))
        lines = [f"<b>{esc(source)}</b>", f"CELL {esc(row.get('xci'))} · LAC {esc(row.get('lac'))}",
                 f"PLMN {esc(row.get('plmn'))} · NBID {esc(row.get('xnbid'))}",
                 f"{gps[0]:.6f}, {gps[1]:.6f}"]
        if row.get("event_at") is not None:
            lines.append("เหตุการณ์: " + esc(row["event_at"]))
        if row.get("observed_at") is not None:
            lines.append("สำรวจ: " + esc(row["observed_at"]))
        if row.get("ambiguous"):
            lines.append("หลายเครือข่ายตรงกัน — ยังไม่เลือกเส้นทาง")
        folium.CircleMarker(gps, radius=6 if group is primary else 4, color="#e4f5f4", weight=1,
                            fill=True, fill_color=color, fill_opacity=.95,
                            tooltip=f"CELL {esc(row.get('xci'))} · {esc(source)}",
                            popup=folium.Popup("<br>".join(lines), max_width=350)).add_to(group)
        if sector and bearing is not None and group is primary:
            folium.Polygon(sector_points(*gps, bearing, beam, radius), color=color, weight=1,
                           fill=True, fill_opacity=.12, tooltip="Sector จำลอง — ทิศที่ผู้ใช้กำหนด").add_to(group)
    # Unresolved and missing events break the line instead of inventing a link.
    animation = []
    if path:
        segments, segment, seen = [], [], set()
        for row in rows:
            event_id = row.get("event_id")
            if event_id in seen:
                continue
            seen.add(event_id)
            gps = coordinates(row.get("lat"), row.get("lon"))
            if row.get("ambiguous") or not gps:
                if segment:
                    segments.append(segment)
                segment = []
                continue
            segment.append(gps)
            animation.append({"lat": gps[0], "lon": gps[1], "label": str(row.get("event_at", ""))})
        if segment:
            segments.append(segment)
        for segment in segments:
            if len(segment) > 1:
                folium.PolyLine(segment, color="#51b8cf", weight=3, opacity=.8, dash_array="6 8",
                                tooltip="เส้นเชื่อมเหตุการณ์ ไม่ใช่เส้นทางเดินทางที่ยืนยัน").add_to(m)
    if fit and points:
        m.fit_bounds(points, padding=(35, 35), max_zoom=15)
    if len(animation) > 1:
        playback = MacroElement()
        playback._template = Template("""
        {% macro script(this, kwargs) %}
        (function(){
          const map = {{this._parent.get_name()}}, points = {{this.points|tojson}};
          const control = L.control({position:'bottomleft'});
          control.onAdd = function(){
            const box = L.DomUtil.create('div');
            box.style.cssText='background:#111e30;color:#fff;padding:10px;border-radius:8px;font:12px sans-serif;min-width:220px';
            const button = document.createElement('button'); button.textContent='▶ เล่นเหตุการณ์';
            button.style.cssText='background:#51b8cf;border:0;padding:7px;border-radius:4px;cursor:pointer';
            const slider = document.createElement('input'); slider.type='range'; slider.min=0; slider.max=points.length-1; slider.value=0;
            slider.style.cssText='display:block;width:100%;margin-top:8px';
            const label=document.createElement('div');
            box.append(button,slider,label); L.DomEvent.disableClickPropagation(box); L.DomEvent.disableScrollPropagation(box);
            let timer=null,index=0;
            const marker=L.circleMarker([points[0].lat,points[0].lon],{radius:10,color:'#fff',fillColor:'#f0b65b',fillOpacity:1}).addTo(map);
            function show(){const p=points[index];marker.setLatLng([p.lat,p.lon]);slider.value=index;label.textContent=(index+1)+' / '+points.length+' · '+p.label;}
            function stop(){clearInterval(timer);timer=null;button.textContent='▶ เล่นเหตุการณ์';}
            button.onclick=function(){if(timer){stop();return;} if(index===points.length-1)index=0;show();button.textContent='❚❚ หยุด';timer=setInterval(function(){index++;show();if(index>=points.length-1)stop();},1200);};
            slider.oninput=function(){stop();index=Number(slider.value);show();};
            map.on('unload',stop);show();return box;
          };control.addTo(map);
        })();
        {% endmacro %}""")
        playback.points = animation
        m.add_child(playback)
    folium.LayerControl(collapsed=True).add_to(m)
    return m
