"""Canvas survey dots and event-group playback. Every survey record is retained."""
import html
import math
from collections import OrderedDict
import folium
from branca.element import MacroElement, Template
from core import coordinates, display_time, signal_level, sector_points


def build_map(rows, center=None, zoom=7, fit=True, sector=False, bearing=None,
              radius=1000, beam=90, path=False, related=()):
    m = folium.Map(location=center or [7.05, 100.5], zoom_start=zoom, tiles="OpenStreetMap",
                   prefer_canvas=True, control_scale=True)
    points, events, records = [], OrderedDict(), OrderedDict()
    for i, row in enumerate(rows):
        event_id = row.get("event_id")
        if event_id is not None:
            events.setdefault(event_id, {"label": display_time(row.get("event_at")) + " · " + row.get("event_type", "CDR"), "members": []})
        gps = coordinates(row.get("lat"), row.get("lon"))
        if not gps:
            continue
        # Same observation reused by multiple CDR events is drawn once, not lost.
        key = row.get("observation_key") or (f"cdr:{event_id}" if event_id is not None else f"row:{i}")
        if key not in records:
            color, level, value = signal_level(row)
            esc = lambda v: html.escape(str(v if v is not None else "—"))
            popup = "<br>".join([f"<b>{esc(row.get('source', 'G-Mon'))}</b>",
                f"CELL {esc(row.get('xci'))} · LAC {esc(row.get('lac_display') or row.get('lac'))}",
                f"PLMN {esc(row.get('plmn'))} · xNBID {esc(row.get('xnbid'))}",
                f"{gps[0]:.6f}, {gps[1]:.6f}",
                f"RSRP/RSCP: {esc(value)} dBm · {esc(level)}",
                "สำรวจ: " + esc(display_time(row.get("observed_at")))])
            kind = str(row.get("cdr_kind") or "").upper()
            event_type = str(row.get("event_type") or "").upper()
            if kind == "VOICE" or event_type.startswith("VOICE"):
                marker_type, marker_color, marker_symbol = "VOICE", "#ef4444", "☎"
            elif kind == "DATA":
                marker_type, marker_color, marker_symbol = "DATA", "#2563eb", "📡"
            elif kind == "SMS" or event_type.startswith("SMS"):
                marker_type, marker_color, marker_symbol = "SMS", "#a855f7", "✉"
            else:
                marker_type, marker_color, marker_symbol = "GMON", color, ""
            records[key] = {"gps": list(gps), "color": marker_color, "popup": popup,
                            "label": (marker_type + " · " if marker_type != "GMON" else "") + "CELL " + str(row.get("xci")),
                            "marker_type": marker_type, "marker_symbol": marker_symbol, "index": len(records)}
            points.append(gps)
        if event_id is not None:
            events[event_id]["members"].append(records[key]["index"])
    if fit and points:
        south, north = min(p[0] for p in points), max(p[0] for p in points)
        west, east = min(p[1] for p in points), max(p[1] for p in points)
        m.location = [(south+north)/2, (west+east)/2]
        m.options['zoom'] = min(15, max(3, int(math.log2(120/max(north-south,east-west,.001)))) )
        m.fit_bounds(points, padding=(25, 25), max_zoom=15)
    layer = MacroElement()
    layer.data = list(records.values())
    layer.events = list(events.values()) if path else []
    layer.sectors = [sector_points(*p, bearing, beam, radius) for p in points] if sector and bearing is not None and len(points) <= 500 else []
    layer._template = Template("""
    {% macro script(this, kwargs) %}
    (function(){
      const map={{this._parent.get_name()}}, data={{this.data|tojson}}, events={{this.events|tojson}};
      const renderer=L.canvas({padding:.5}), dots=[], group=L.featureGroup().addTo(map);
      data.forEach(p=>{
        let dot;
        if(p.marker_type==='GMON') dot=L.circleMarker(p.gps,{renderer:renderer,radius:5,color:'#fff',weight:1,fillColor:p.color,fillOpacity:.9}).addTo(group);
        else { const icon=L.divIcon({className:'intel-event-marker',html:'<span style="display:inline-flex;align-items:center;justify-content:center;width:24px;height:24px;border-radius:50%;background:'+p.color+';border:2px solid #fff;color:#fff;font-size:14px;box-shadow:0 1px 4px #000">'+p.marker_symbol+'</span>',iconSize:[24,24],iconAnchor:[12,12]}); dot=L.marker(p.gps,{icon}).addTo(group); }
        dot.bindTooltip(p.label); dot.bindPopup(()=>p.popup); dots.push(dot);
      });
      {{this.sectors|tojson}}.forEach(p=>L.polygon(p,{color:'#38bdf8',weight:1,fillOpacity:.08}).bindTooltip('Sector จำลอง').addTo(map));
      const legend=L.control({position:'topright'});
      legend.onAdd=function(){const box=L.DomUtil.create('div');box.style.cssText='background:#102036;color:white;border-radius:6px;padding:8px;font:12px sans-serif';box.innerHTML='Signal: <span style="color:#22c55e">● HIGH</span> <span style="color:#facc15">● MID</span> <span style="color:#ef4444">● LOW</span><br><small>LTE RSRP · เทา = ไม่มีค่า/ไม่มีเกณฑ์</small>';L.DomEvent.disableClickPropagation(box);return box;};legend.addTo(map);
      if(!events.length)return;
      const control=L.control({position:'bottomleft'});
      control.onAdd=function(){
        const box=L.DomUtil.create('div');box.style.cssText='background:#102036;color:white;padding:10px;border-radius:8px;font:12px sans-serif;max-width:75vw';
        const button=document.createElement('button');button.textContent='▶ เล่นเหตุการณ์';button.style.cssText='background:#38bdf8;border:0;padding:9px;border-radius:5px;cursor:pointer';
        const slider=document.createElement('input');slider.type='range';slider.min=0;slider.max=events.length-1;slider.value=0;slider.setAttribute('aria-label','ลำดับเหตุการณ์');slider.style.cssText='display:block;width:100%;margin:8px 0';
        const label=document.createElement('div');box.append(button,slider,label);L.DomEvent.disableClickPropagation(box);L.DomEvent.disableScrollPropagation(box);
        let timer=null,index=0,previous=[];
        function show(){previous.forEach(i=>dots[i].setStyle({radius:5,weight:1,color:'#fff'}));const e=events[index];previous=e.members;const bounds=[];e.members.forEach(i=>{dots[i].setStyle({radius:8,weight:3,color:'#38bdf8'});dots[i].bringToFront();bounds.push(data[i].gps);});if(bounds.length)map.fitBounds(bounds,{padding:[35,35],maxZoom:15});slider.value=index;label.textContent=(index+1)+' / '+events.length+' · '+e.label+' · '+(bounds.length?bounds.length+' จุด':'ไม่พบพิกัด');}
        function stop(){clearInterval(timer);timer=null;button.textContent='▶ เล่นเหตุการณ์';}
        button.onclick=function(){if(timer){stop();return;}if(index===events.length-1)index=0;show();if(events.length===1)return;button.textContent='❚❚ หยุด';timer=setInterval(()=>{index++;show();if(index>=events.length-1)stop();},1800);};
        slider.oninput=function(){stop();index=Number(slider.value);show();};map.on('unload',stop);show();return box;
      };control.addTo(map);
    })();
    {% endmacro %}
    """)
    m.add_child(layer)
    return m
