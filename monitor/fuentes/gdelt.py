"""Consultas a la API de documentos de GDELT 2.0 (DOC API).

Documentación: https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/
Límite de uso: aproximadamente una consulta cada 5 segundos.
"""
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests

from .rss import CABECERAS


def _fecha_gdelt(s: str) -> str:
    # GDELT devuelve fechas como "20240206T120000Z"
    try:
        return datetime.strptime(s, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc).isoformat(timespec="seconds")
    except (TypeError, ValueError):
        return datetime.now(timezone.utc).isoformat(timespec="seconds")


def consultar(cfg_gdelt: dict, consulta: str, *, timespan: str | None = None,
              inicio: str | None = None, fin: str | None = None, reintentos: int = 5) -> list[dict]:
    """Devuelve artículos (modo ArtList). inicio/fin con formato AAAAMMDDHHMMSS."""
    params = {"query": consulta, "mode": "ArtList", "format": "json",
              "maxrecords": str(cfg_gdelt.get("max_resultados", 250)), "sort": "DateDesc"}
    if timespan:
        params["timespan"] = timespan
    if inicio and fin:
        params.update(startdatetime=inicio, enddatetime=fin)
    for intento in range(reintentos):
        try:
            r = requests.get(cfg_gdelt["url"], params=params, headers=CABECERAS, timeout=60)
            if r.status_code == 429 or "limit requests" in r.text[:200].lower():
                # GDELT limita a 1 consulta cada 5 s por IP; los servidores de GitHub
                # son compartidos, así que se espera cada vez más antes de reintentar.
                if intento == reintentos - 1:
                    raise RuntimeError("GDELT: límite de consultas (HTTP 429) tras varios reintentos")
                time.sleep(15 * (intento + 1))
                continue
            r.raise_for_status()
            if not r.text.strip().startswith("{"):
                # GDELT responde con texto plano cuando la consulta es inválida
                raise ValueError(r.text.strip()[:200])
            articulos = r.json().get("articles", [])
            return [{
                "titulo": a.get("title", "").strip(),
                "resumen": "",
                "url": a.get("url", ""),
                "fecha": _fecha_gdelt(a.get("seendate")),
                "fuente": a.get("domain") or urlparse(a.get("url", "")).netloc,
                "origen": "gdelt",
                "idioma": a.get("language", ""),
                "pais_fuente": a.get("sourcecountry", ""),
            } for a in articulos if a.get("url")]
        except ValueError:
            raise
        except Exception:
            if intento == reintentos - 1:
                raise
            time.sleep(5 * (intento + 1))
    return []
