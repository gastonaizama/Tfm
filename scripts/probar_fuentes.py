"""Prueba cada fuente configurada y muestra un informe de disponibilidad."""
import json, sys, time, urllib.parse
import requests, feedparser

UA = {"User-Agent": "Mozilla/5.0 (TFM-CTI-monitor; +https://github.com/gastonaizama/Tfm)"}
FEEDS = {
    "The Record": ["https://therecord.media/feed"],
    "BleepingComputer": ["https://www.bleepingcomputer.com/feed/"],
    "The Hacker News": ["https://feeds.feedburner.com/TheHackersNews"],
    "WeLiveSecurity ES": ["https://www.welivesecurity.com/es/rss/feed/", "https://www.welivesecurity.com/es/feed/"],
    "WeLiveSecurity EN": ["https://www.welivesecurity.com/en/rss/feed/"],
    "Infobae": ["https://www.infobae.com/arc/outboundfeeds/rss/", "https://www.infobae.com/feeds/rss/"],
    "La Nacion": ["https://www.lanacion.com.ar/arc/outboundfeeds/rss/?outputType=xml", "https://www.lanacion.com.ar/arc/outboundfeeds/rss/"],
}
for nombre, urls in FEEDS.items():
    for u in urls:
        try:
            r = requests.get(u, headers=UA, timeout=30)
            f = feedparser.parse(r.content)
            fechas = [e.get("published", e.get("updated", "")) for e in f.entries[:1]] + [e.get("published", "") for e in f.entries[-1:]]
            print(f"FEED {nombre} | {u} | HTTP {r.status_code} | {len(f.entries)} items | {fechas}")
        except Exception as e:
            print(f"FEED {nombre} | {u} | ERROR {e}")

G = "https://api.gdeltproject.org/api/v2/doc/doc"
q = '(Argentina OR argentino) (Israel OR Hamas OR Iran OR AMIA OR embajada)'
for label, extra in [("ultimos7d", {"timespan": "7d"}),
                     ("feb2024", {"startdatetime": "20240201000000", "enddatetime": "20240215000000"}),
                     ("oct2023", {"startdatetime": "20231007000000", "enddatetime": "20231014000000"}),
                     ("ago2023", {"startdatetime": "20230801000000", "enddatetime": "20230815000000"}),
                     ("timeline_hist", {"mode": "TimelineVolRaw", "startdatetime": "20230801000000", "enddatetime": "20240731000000"})]:
    p = {"query": q, "mode": "ArtList", "format": "json", "maxrecords": "250", "sort": "DateAsc"}
    p.update(extra)
    try:
        r = requests.get(G, params=p, headers=UA, timeout=60)
        txt = r.text
        try:
            d = r.json()
            n = len(d.get("articles", [])) if "articles" in d else len(d.get("timeline", [{}])[0].get("data", []))
            muestra = (d.get("articles") or [{}])[0] if "articles" in d else str(d)[:300]
        except Exception:
            n, muestra = -1, txt[:300]
        print(f"GDELT {label} | HTTP {r.status_code} | n={n} | {muestra}")
    except Exception as e:
        print(f"GDELT {label} | ERROR {e}")
    time.sleep(6)
# GDELT 1.0 daily event files (fallback for history)
for u in ["http://data.gdeltproject.org/events/20240206.export.CSV.zip", "http://data.gdeltproject.org/gdeltv2/20240206120000.export.CSV.zip"]:
    try:
        r = requests.head(u, timeout=30); print(f"GDELTFILE {u} | HTTP {r.status_code} | {r.headers.get('Content-Length')}")
    except Exception as e:
        print(f"GDELTFILE {u} | ERROR {e}")
