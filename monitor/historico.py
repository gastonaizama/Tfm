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


def construir_gdelt_historico(config: dict, reiniciar: bool = False) -> bool:
    """Descarga de GDELT las noticias del periodo histórico, POR PARTES.

    - El periodo se divide en tramos (`historico.dias_por_tramo`): cortos para las consultas
      geopolíticas (mucho volumen) y largos para las ciber (poco volumen).
    - El progreso se guarda en datos/gdelt_historico.json: cada ejecución continúa donde
      quedó la anterior, hasta `historico.presupuesto_minutos` minutos como máximo.
    - Si GDELT rechaza varias consultas seguidas por exceso de uso, se detiene y se
      reintenta en la próxima ejecución (6 horas después).
    - Cada consulta devuelve como máximo `max_resultados` artículos; los tramos que llegan
      a ese máximo se marcan como "saturado" (puede faltar cobertura).

    Devuelve True si el histórico quedó completo.
    """
    cfg = config["gdelt"]
    h = config["historico"]
    # Las variables de entorno permiten probar un rango corto sin tocar config.json
    inicio = date.fromisoformat(os.environ.get("MONITOR_HIST_INICIO") or h["inicio"])
    fin = date.fromisoformat(os.environ.get("MONITOR_HIST_FIN") or h["fin"])
    minutos = float(os.environ.get("MONITOR_HIST_MINUTOS") or h.get("presupuesto_minutos", 40))
    dias_por_tramo = h.get("dias_por_tramo", {"geo": 2, "ciber": 30})
    consultas = [(q, dias_por_tramo["geo"]) for q in cfg["consultas_geopoliticas"]] + \
                [(q, dias_por_tramo["ciber"]) for q in cfg["consultas_ciber"]]

    previo = {} if reiniciar else leer_json(ARCHIVO_GDELT_HIST, {})
    if previo.get("inicio") != inicio.isoformat() or previo.get("fin") != fin.isoformat() \
            or previo.get("dias_por_tramo") != dias_por_tramo:
        previo = {}   # cambió el periodo o el tamaño de tramo: se empieza de cero
    noticias = previo.get("noticias", [])
    hechos = {(t["desde"], t["consulta"]): t for t in previo.get("tramos", []) if "error" not in t}
    vistas = {n["url"] for n in noticias}

    pendientes = []
    for q, dias in consultas:
        d = inicio
        while d <= fin:
            hasta = min(d + timedelta(days=dias), fin + timedelta(days=1))
            if (d.isoformat(), q) not in hechos:
                pendientes.append((d, hasta, q))
            d = hasta
    pendientes.sort(key=lambda p: p[0])   # avanzar en orden cronológico
    total = len(pendientes) + len(hechos)
    print(f"[GDELT hist] {len(hechos)}/{total} tramos ya descargados; pendientes: {len(pendientes)}")

    def guardar():
        guardar_json(ARCHIVO_GDELT_HIST, {
            "actualizado": date.today().isoformat(), "inicio": inicio.isoformat(), "fin": fin.isoformat(),
            "dias_por_tramo": dias_por_tramo, "completo": len(hechos) == total,
            "tramos": sorted(hechos.values(), key=lambda t: (t["desde"], t["consulta"])),
            "noticias": noticias}, compacto=True)

    limite_tiempo = time.monotonic() + minutos * 60
    rechazos_seguidos = 0
    for i, (d, hasta, q) in enumerate(pendientes):
        if time.monotonic() > limite_tiempo:
            print(f"[GDELT hist] Se alcanzó el tiempo máximo ({minutos:.0f} min); se continúa en la próxima ejecución.")
            break
        try:
            arts = gdelt.consultar(cfg, q, inicio=d.strftime("%Y%m%d000000"), fin=hasta.strftime("%Y%m%d000000"))
        except gdelt.LimiteGdelt:
            rechazos_seguidos += 1
            print(f"[GDELT hist] {d} → {hasta}: GDELT rechazó por exceso de uso ({rechazos_seguidos} seguidos)")
            if rechazos_seguidos >= 3:
                print("[GDELT hist] Demasiados rechazos seguidos; se continúa en la próxima ejecución.")
                break
            continue
        except Exception as e:
            print(f"[GDELT hist] {d} → {hasta}: ERROR {type(e).__name__}: {e}")
            continue
        finally:
            time.sleep(cfg.get("pausa_entre_consultas_seg", 6))
        rechazos_seguidos = 0
        nuevos = [a for a in arts if a["url"] not in vistas]
        for a in nuevos:
            a["origen"] = "gdelt_historico"
            vistas.add(a["url"])
        noticias.extend(nuevos)
        saturado = len(arts) >= cfg.get("max_resultados", 250)
        hechos[(d.isoformat(), q)] = {"desde": d.isoformat(), "hasta": hasta.isoformat(), "consulta": q,
                                      "articulos": len(arts), "saturado": saturado}
        print(f"[GDELT hist] {d} → {hasta}: {len(arts)} artículos ({len(nuevos)} nuevos)"
              + (" ⚠ SATURADO" if saturado else ""))
        if i % 5 == 4:
            guardar()
    guardar()
    completo = len(hechos) == total
    print(f"[GDELT hist] Progreso: {len(hechos)}/{total} tramos · {len(noticias)} artículos"
          + (" · COMPLETO" if completo else " · incompleto (continúa en la próxima ejecución)"))
    return completo


def cargar_gdelt_historico() -> list[dict]:
    return leer_json(ARCHIVO_GDELT_HIST, {}).get("noticias", [])
