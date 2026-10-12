"""Modo histórico (agosto 2023 – julio 2024).

Los feeds RSS solo muestran las últimas noticias, por eso el histórico se arma con:
1. GDELT: se descarga UNA vez (comando `python -m monitor historico`) y se guarda en
   datos/gdelt_historico.json, para no repetir cientos de consultas cada 6 horas.
2. datos/hechos_clave.csv: hechos geopolíticos de referencia cargados a mano.
3. datos/incidentes_historicos.csv: ataques conocidos cargados a mano.
"""
import csv
import os
import time
from datetime import date, timedelta

from .config import ARCHIVO_GDELT_HIST, ARCHIVO_HECHOS, ARCHIVO_INCIDENTES, guardar_json, leer_json
from .fuentes import gdelt


def _leer_csv(ruta) -> list[dict]:
    if not ruta.exists():
        return []
    with open(ruta, encoding="utf-8-sig", newline="") as f:
        filas = [{k.strip(): (v or "").strip() for k, v in fila.items() if k} for fila in csv.DictReader(f)]
    # Las filas de ejemplo y las vacías se ignoran
    return [f for f in filas if f.get("id") and f.get("fecha") and not f["id"].upper().startswith("EJEMPLO")]


def cargar_hechos_clave() -> list[dict]:
    return [{
        "id": f"hc-{f['id']}",
        "titulo": f["titulo"],
        "resumen": f.get("descripcion", ""),
        "url": f.get("fuente_url", ""),
        "fecha": f["fecha"] + "T12:00:00+00:00",
        "fuente": f.get("fuente_nombre") or "Hecho clave (carga manual)",
        "origen": "hecho_clave",
        "carril": "geo",
        "categoria": f.get("categoria", ""),
        "confianza": f.get("confianza", ""),
        "verificado": f.get("verificado", ""),
    } for f in _leer_csv(ARCHIVO_HECHOS)]


def cargar_incidentes() -> list[dict]:
    eventos = []
    for f in _leer_csv(ARCHIVO_INCIDENTES):
        tecnicas = [t.strip() for t in f.get("tecnicas_mitre", "").replace(",", ";").split(";") if t.strip()]
        titulo = f"{f.get('grupo') or 'Actor desconocido'} → {f.get('objetivo') or f.get('dominio_objetivo') or 'objetivo argentino'}"
        if f.get("tipo_ataque"):
            titulo += f" ({f['tipo_ataque']})"
        eventos.append({
            "id": f"inc-{f['id']}",
            "titulo": titulo,
            "resumen": f.get("descripcion", ""),
            "url": f.get("fuente_url", ""),
            "fecha": f["fecha"] + "T12:00:00+00:00",
            "fuente": f.get("fuente_nombre") or "Incidente (carga manual)",
            "origen": "incidente_csv",
            "carril": "ataque",
            "tecnicas": tecnicas,
            "grupos": [f["grupo"]] if f.get("grupo") else [],
            "sector": f.get("sector", ""),
            "dominio_objetivo": f.get("dominio_objetivo", ""),
            "motivacion": f.get("motivacion_declarada", ""),
            "confianza": f.get("confianza", ""),
            "verificado": f.get("verificado", ""),
        })
    return eventos


def construir_gdelt_historico(config: dict) -> dict:
    """Descarga de GDELT las noticias del periodo histórico, en tramos semanales.

    Cada consulta devuelve como máximo `max_resultados` artículos (límite de la API), por
    eso el periodo se divide en tramos cortos (`historico.dias_por_tramo`). Si un tramo
    llega al máximo se marca como "saturado" (puede faltar cobertura ese tramo). El resultado se guarda en datos/gdelt_historico.json.
    """
    cfg = config["gdelt"]
    dias_por_tramo = config["historico"].get("dias_por_tramo", 3)
    # Las variables de entorno permiten probar un rango corto sin tocar config.json
    inicio = date.fromisoformat(os.environ.get("MONITOR_HIST_INICIO") or config["historico"]["inicio"])
    fin = date.fromisoformat(os.environ.get("MONITOR_HIST_FIN") or config["historico"]["fin"])
    consultas = cfg["consultas_geopoliticas"] + cfg["consultas_ciber"]
    noticias, vistas, tramos = [], set(), []
    d = inicio
    while d <= fin:
        hasta = min(d + timedelta(days=dias_por_tramo), fin + timedelta(days=1))
        for q in consultas:
            try:
                arts = gdelt.consultar(cfg, q, inicio=d.strftime("%Y%m%d000000"), fin=hasta.strftime("%Y%m%d000000"))
                nuevos = [a for a in arts if a["url"] not in vistas]
                for a in nuevos:
                    a["origen"] = "gdelt_historico"
                    vistas.add(a["url"])
                noticias.extend(nuevos)
                saturado = len(arts) >= cfg.get("max_resultados", 250)
                tramos.append({"desde": d.isoformat(), "hasta": hasta.isoformat(), "consulta": q,
                               "articulos": len(arts), "saturado": saturado})
                print(f"[GDELT hist] {d} → {hasta}: {len(arts)} artículos ({len(nuevos)} nuevos)"
                      + (" ⚠ SATURADO" if saturado else ""))
            except Exception as e:
                tramos.append({"desde": d.isoformat(), "hasta": hasta.isoformat(), "consulta": q, "error": str(e)[:200]})
                print(f"[GDELT hist] {d} → {hasta}: ERROR {e}")
            time.sleep(cfg.get("pausa_entre_consultas_seg", 6))
        d = hasta
    resultado = {"generado": date.today().isoformat(), "inicio": inicio.isoformat(), "fin": fin.isoformat(),
                 "tramos": tramos, "noticias": noticias}
    guardar_json(ARCHIVO_GDELT_HIST, resultado, compacto=True)
    print(f"[GDELT hist] Total: {len(noticias)} artículos guardados en {ARCHIVO_GDELT_HIST.name}")
    return resultado


def cargar_gdelt_historico() -> list[dict]:
    return leer_json(ARCHIVO_GDELT_HIST, {}).get("noticias", [])
