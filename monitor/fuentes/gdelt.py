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


class LimiteGdelt(RuntimeError):
    """GDELT rechazó la consulta por exceso de uso (HTTP 429)."""


def consultar(cfg_gdelt: dict, consulta: str, *, timespan: str | None = None,
              inicio: str | None = None, fin: str | None = None, orden: str = "HybridRel",
              reintentos: int = 3) -> list[dict]:
    """Devuelve artículos (modo ArtList). inicio/fin con formato AAAAMMDDHHMMSS.

    orden="HybridRel" devuelve primero los artículos más relevantes (útil porque la API
    corta en `max_resultados`); "DateDesc" devuelve los más recientes.
    Lanza LimiteGdelt si GDELT sigue rechazando por exceso de uso tras los reintentos.
    """
    params = {"query": consulta, "mode": "ArtList", "format": "json",
              "maxrecords": str(cfg_gdelt.get("max_resultados", 250)), "sort": orden}
    if timespan:
        params["timespan"] = timespan
    if inicio and fin:
        params.update(startdatetime=inicio, enddatetime=fin)
    espera_429 = cfg_gdelt.get("espera_tras_limite_seg", 20)
    ultimo_error = None
    for intento in range(reintentos):
        try:
            r = requests.get(cfg_gdelt["url"], params=params, headers=CABECERAS, timeout=45)
        except requests.RequestException as e:   # corte de red o demora excesiva
            ultimo_error = e
            time.sleep(5 * (intento + 1))
            continue
        if r.status_code == 429 or "limit requests" in r.text[:200].lower():
            # GDELT admite ~1 consulta cada 5 s por IP; los servidores de GitHub son
            # compartidos con otros usuarios, así que a veces hay que esperar más.
            ultimo_error = LimiteGdelt("GDELT: límite de consultas (HTTP 429)")
            time.sleep(espera_429 * (intento + 1))
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
    raise ultimo_error
