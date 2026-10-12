"""Lectura de feeds RSS/Atom."""
import time
from datetime import datetime, timezone

import feedparser
import requests

from ..texto import limpiar_html

CABECERAS = {"User-Agent": "Mozilla/5.0 (compatible; TFM-CTI-Monitor/1.0; +https://github.com/gastonaizama/Tfm)"}


def _fecha(entrada) -> str:
    for campo in ("published_parsed", "updated_parsed"):
        t = entrada.get(campo)
        if t:
            return datetime.fromtimestamp(time.mktime(t), tz=timezone.utc).isoformat(timespec="seconds")
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def leer_feed(fuente: dict) -> tuple[list[dict], dict]:
    """Devuelve (noticias, diagnóstico). Nunca lanza excepción: un feed caído no detiene el resto."""
    diag = {"nombre": fuente["nombre"], "url": fuente["url"], "ok": False, "items": 0, "detalle": ""}
    try:
        r = requests.get(fuente["url"], headers=CABECERAS, timeout=30)
        diag["http"] = r.status_code
        r.raise_for_status()
        feed = feedparser.parse(r.content)
        noticias = []
        for e in feed.entries:
            if not e.get("link"):
                continue
            noticias.append({
                "titulo": limpiar_html(e.get("title", ""), 250),
                "resumen": limpiar_html(e.get("summary", "") or e.get("description", ""), 400),
                "url": e["link"],
                "fecha": _fecha(e),
                "fuente": fuente["nombre"],
                "origen": "rss",
                "idioma": fuente.get("idioma", ""),
            })
        diag.update(ok=len(noticias) > 0, items=len(noticias), detalle="" if noticias else "feed sin entradas")
        return noticias, diag
    except Exception as ex:
        diag["detalle"] = f"{type(ex).__name__}: {ex}"[:300]
        return [], diag
