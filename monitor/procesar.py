"""Proceso principal: recolectar → clasificar → calcular semáforo → generar datos para la web."""
import hashlib
import time
from datetime import datetime, timedelta, timezone

from . import evaluacion, historico, mitre, semaforo
from .clasificador import Clasificador
from .config import (ARCHIVO_ESTADO_FUENTES, ARCHIVO_GDELT_HIST, ARCHIVO_NOTICIAS, ARCHIVO_SALIDA_WEB, cargar_config,
                     cargar_mapeo_mitre, guardar_json, leer_json)
from .fuentes import gdelt, rss
from .ia import integracion as ia


def _id(url: str, titulo: str) -> str:
    return hashlib.sha1((url or titulo).encode("utf-8")).hexdigest()[:12]


def recolectar(config: dict) -> tuple[list[dict], list[dict]]:
    noticias, diagnostico = [], []
    for fuente in config["fuentes_rss"]:
        if not fuente.get("activa", True):
            diagnostico.append({"nombre": fuente["nombre"], "url": fuente["url"], "ok": False, "items": 0,
                                "detalle": "desactivada en config.json"})
            continue
        items, diag = rss.leer_feed(fuente)
        print(f"[RSS] {fuente['nombre']}: {'OK' if diag['ok'] else 'FALLA'} ({diag['items']} items) {diag['detalle']}")
        noticias.extend(items)
        diagnostico.append(diag)

    cfg = config["gdelt"]
    for q in cfg["consultas_geopoliticas"] + cfg["consultas_ciber"]:
        diag = {"nombre": "GDELT DOC API", "url": q, "ok": False, "items": 0, "detalle": ""}
        try:
            items = gdelt.consultar(cfg, q, timespan=cfg["ventana_consulta_vivo"], reintentos=2)
            diag.update(ok=True, items=len(items))
            noticias.extend(items)
        except Exception as e:
            diag["detalle"] = f"{type(e).__name__}: {e}"[:300]
        print(f"[GDELT] {q[:60]}…: {diag['items']} artículos {diag['detalle']}")
        diagnostico.append(diag)
        time.sleep(cfg.get("pausa_entre_consultas_seg", 6))
    return noticias, diagnostico


def actualizar_almacen(nuevas: list[dict], clasificador: Clasificador, config: dict) -> list[dict]:
    """Acumula en datos/noticias_vivo.json las noticias potencialmente relevantes.

    Los feeds RSS no guardan historia: este archivo ES nuestra historia del modo en vivo.
    Para no inflar el repositorio solo se guardan noticias que mencionan Argentina y
    tienen algún término geopolítico o cibernético.
    """
    almacen = {n["url"]: n for n in leer_json(ARCHIVO_NOTICIAS, [])}
    ahora = datetime.now(timezone.utc).isoformat(timespec="seconds")
    agregadas = 0
    for n in nuevas:
        if n["url"] in almacen:
            continue
        c = clasificador.clasificar(n["titulo"], n.get("resumen", ""), n["url"])
        if c["menciona_argentina"] and (c["terminos_geo"] or c["terminos_ciber"]):
            n["visto_por_primera_vez"] = ahora
            almacen[n["url"]] = n
            agregadas += 1
    limite = (datetime.now(timezone.utc) - timedelta(days=config["almacenamiento"]["dias_retencion_noticias_vivo"])).isoformat()
    lista = sorted((n for n in almacen.values() if n["fecha"] >= limite), key=lambda n: n["fecha"], reverse=True)
    guardar_json(ARCHIVO_NOTICIAS, lista)
    print(f"[Almacén] {agregadas} noticias nuevas; total guardado: {len(lista)}")
    return lista


def construir_eventos(noticias: list[dict], clasificador: Clasificador) -> list[dict]:
    eventos, vistos = [], set()
    for n in noticias:
        c = clasificador.clasificar(n["titulo"], n.get("resumen", ""), n["url"])
        carril = clasificador.carril(c)
        if not carril:
            continue
        eid = _id(n["url"], n["titulo"])
        if eid in vistos:
            continue
        vistos.add(eid)
        eventos.append({
            "id": eid, "carril": carril, "dia": n["fecha"][:10], **n,
            "puntaje_geo": c["puntaje_geo"], "terminos": c["terminos_geo"] + c["terminos_ciber"],
            "grupos": c["grupos"], "tecnicas": c["tecnicas"], "categorias_ataque": c["categorias_ataque"],
        })
    for e in historico.cargar_hechos_clave() + historico.cargar_incidentes():
        e.setdefault("tecnicas", [])
        e.setdefault("grupos", [])
        e.setdefault("terminos", [])
        e["dia"] = e["fecha"][:10]
        eventos.append(e)
    eventos.sort(key=lambda e: e["fecha"])
    return eventos


def _estado_historico() -> dict:
    h = leer_json(ARCHIVO_GDELT_HIST, {})
    tramos = h.get("tramos", [])
    return {"completo": bool(h.get("completo")), "tramos_descargados": len(tramos),
            "tramos_saturados": sum(1 for t in tramos if t.get("saturado")),
            "articulos": len(h.get("noticias", [])), "actualizado": h.get("actualizado")}


def ejecutar(recolectar_en_vivo: bool = True) -> dict:
    config = cargar_config()
    mapeo = cargar_mapeo_mitre()
    clasificador = Clasificador(config, mapeo)

    if recolectar_en_vivo:
        nuevas, diagnostico = recolectar(config)
        guardar_json(ARCHIVO_ESTADO_FUENTES, {"fecha": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                              "fuentes": diagnostico})
    else:
        nuevas = []
    vivo = actualizar_almacen(nuevas, clasificador, config)
    eventos = construir_eventos(vivo + historico.cargar_gdelt_historico(), clasificador)

    tecnicas = {t for r in mapeo["reglas"] for t in r["tecnicas"]} | {t for e in eventos for t in e.get("tecnicas", [])}
    catalogo = mitre.actualizar_catalogo(tecnicas)

    hoy = datetime.now(timezone.utc).date()
    resultado = semaforo.calcular(eventos, config["semaforo"], hoy)

    cfg_eval = config.get("evaluacion", {})
    resultado_eval = evaluacion.evaluar(
        eventos, config["semaforo"], cfg_eval.get("ventanas_sensibilidad", [config["semaforo"]["ventana_vigilancia_dias"]]),
        cfg_eval.get("inicio", config["historico"]["inicio"]), hoy.isoformat())

    # Fase 2 (desactivada por defecto): clasificación con Haiku e informe con Sonnet.
    informe = ia.procesar_si_esta_activada(config, eventos, resultado)

    salida = {
        "generado": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "parametros": {**config["semaforo"], "historico": config["historico"],
                       "periodos_web": [{**p, "fin": hoy.isoformat() if p["fin"] == "hoy" else p["fin"]}
                                        for p in config.get("periodos_web", [])],
                       "ia_activada": config["ia"]["activada"]},
        "actual": resultado["actual"],
        "periodos": resultado["periodos"],
        "alertas": resultado["alertas"],
        "serie_diaria": resultado["serie_diaria"],
        "eventos": eventos,
        "mitre": catalogo,
        "fuentes": leer_json(ARCHIVO_ESTADO_FUENTES, {}),
        "historico_gdelt": _estado_historico(),
        "evaluacion": resultado_eval,
        "incidentes_sin_fecha": historico.cargar_incidentes_sin_fecha(),
        "informe_ia": informe,
    }
    guardar_json(ARCHIVO_SALIDA_WEB, salida, compacto=True)
    n_geo = sum(e["carril"] == "geo" for e in eventos)
    print(f"[Resultado] Nivel actual: {resultado['actual']['nivel'].upper()} | "
          f"eventos geo: {n_geo} | ataques: {len(eventos) - n_geo} | periodos: {len(resultado['periodos'])}")
    return salida
