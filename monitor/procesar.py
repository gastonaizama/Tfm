"""Proceso principal: recolectar → clasificar → calcular semáforo → generar datos para la web."""
import hashlib
import time
from datetime import datetime, timedelta, timezone

from . import evaluacion, historico, mitre, semaforo
from .clasificador import Clasificador
from .config import (ARCHIVO_ESTADO_FUENTES, ARCHIVO_GDELT_HIST, ARCHIVO_NOTICIAS, ARCHIVO_SALIDA_WEB, cargar_config,
                     cargar_mapeo_mitre, guardar_json, leer_json)
from .fuentes import gdelt, rss, telegram
from .ia import integracion as ia
from .texto import buscar_terminos, normalizar


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

    for canal in config.get("fuentes_telegram", {}).get("canales", []):
        if not canal.get("activa", True):
            continue
        items, diag = telegram.leer_canal(canal)
        print(f"[Telegram] {canal['nombre']}: {'OK' if diag['ok'] else 'FALLA'} ({diag['items']} mensajes) {diag['detalle']}")
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


def _clasificar(clasificador: Clasificador, n: dict) -> dict:
    # Los mensajes de los canales de Telegram de los grupos se leen como reclamos (ver clasificador.py)
    return clasificador.clasificar(n["titulo"], n.get("resumen", ""), n["url"], reclamo=n.get("origen") == "telegram")


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
        c = _clasificar(clasificador, n)
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
        c = _clasificar(clasificador, n)
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


def en_foco(e: dict, alcance: dict) -> bool:
    """¿El evento pertenece al actor foco de la plataforma (LulzSec)?

    Los eventos geopolíticos siempre se muestran. Un ataque está en foco si es un reclamo de los
    canales de Telegram del actor, o si el grupo del incidente o el texto de la noticia lo nombran.
    """
    if not alcance or e.get("carril") != "ataque":
        return True
    if e.get("origen") == "telegram":
        return True
    texto = normalizar(" ".join([*e.get("grupos", []), e.get("titulo", "")] +
                                ([e.get("resumen", "")] if e.get("origen") != "incidente_csv" else [])))
    return bool(buscar_terminos(texto, alcance.get("terminos_actor", [])))


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
    # Alcance (decisión del autor, 30/10/2026): la plataforma muestra solo los ataques de LulzSec.
    # Los demás se conservan únicamente como grupo de comparación de la evaluación.
    alcance = config.get("alcance", {})
    for e in eventos:
        e["en_foco"] = en_foco(e, alcance)
    eventos_web = [e for e in eventos if e["en_foco"]]

    # Modo curado: las noticias que en modo automático serían detonantes se proponen como candidatos.
    nuevos = historico.agregar_candidatos_hechos_clave(
        semaforo.candidatos_por_dia(eventos, config["semaforo"]["min_fuentes_distintas_por_dia"]))
    print(f"[Candidatos] {nuevos} días nuevos propuestos en datos/candidatos_hechos_clave.csv")

    tecnicas = {t for r in mapeo["reglas"] for t in r["tecnicas"]} | {t for e in eventos for t in e.get("tecnicas", [])}
    catalogo = mitre.actualizar_catalogo(tecnicas)

    hoy = datetime.now(timezone.utc).date()
    resultado = semaforo.calcular(eventos_web, config["semaforo"], hoy)

    cfg_eval = config.get("evaluacion", {})
    ventanas = cfg_eval.get("ventanas_sensibilidad", [config["semaforo"]["ventana_vigilancia_dias"]])
    inicio_eval = cfg_eval.get("inicio", config["historico"]["inicio"])
    # Tres variantes: todos los incidentes, solo confianza media o alta, y solo verificados (robustez).
    # La evaluación usa TODOS los eventos: los actores fuera de foco son el grupo de comparación.
    variantes = {"todos": {}, "confianza_media_alta": {"confianzas": {"media", "alta"}},
                 "verificados": {"solo_verificados": True}}
    resultado_eval = {v: evaluacion.evaluar(eventos, config["semaforo"], ventanas, inicio_eval, hoy.isoformat(), **f)
                      for v, f in variantes.items()}
    comparacion = {v: evaluacion.comparar_modos(eventos, config["semaforo"], ventanas, cfg_eval.get("tramos", []),
                                                hoy.isoformat(), **f)
                   for v, f in variantes.items()}

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
        "eventos": eventos_web,
        "alcance": {"actor_foco": alcance.get("actor_foco"),
                    "ataques_fuera_de_foco": sum(1 for e in eventos if not e["en_foco"])},
        "mitre": catalogo,
        "fuentes": leer_json(ARCHIVO_ESTADO_FUENTES, {}),
        "historico_gdelt": _estado_historico(),
        "evaluacion": resultado_eval,
        "comparacion_modos": comparacion,
        "incidentes_sin_fecha": [e for e in historico.cargar_incidentes_sin_fecha() if en_foco(e, alcance)],
        "incidentes_descartados": [e for e in historico.cargar_incidentes_descartados() if en_foco(e, alcance)],
        "informe_ia": informe,
    }
    guardar_json(ARCHIVO_SALIDA_WEB, salida, compacto=True)
    n_geo = sum(e["carril"] == "geo" for e in eventos_web)
    print(f"[Resultado] Nivel actual: {resultado['actual']['nivel'].upper()} | "
          f"eventos geo: {n_geo} | ataques de {alcance.get('actor_foco', 'todos')}: {len(eventos_web) - n_geo} | "
          f"fuera de foco (solo comparación): {salida['alcance']['ataques_fuera_de_foco']} | "
          f"periodos: {len(resultado['periodos'])}")
    return salida
