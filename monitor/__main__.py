"""Uso:
  python -m monitor actualizar             # revisión completa (lo que corre cada 6 horas)
  python -m monitor recalcular             # recalcula semáforo y web SIN descargar noticias
  python -m monitor historico              # continúa la descarga por partes del histórico de GDELT
  python -m monitor historico --reiniciar  # borra el histórico de GDELT y empieza de nuevo
  python -m monitor diagnostico            # prueba variantes de consulta a GDELT (para ajustar)
  python -m monitor telegram               # lee los canales de Telegram y muestra qué se clasifica como reclamo
"""
import sys

from . import historico, procesar
from .config import cargar_config


def diagnostico_gdelt(config: dict) -> None:
    """Muestra cuántos artículos devuelve GDELT con distintas variantes de consulta."""
    import time
    from .fuentes import gdelt
    cfg = config["gdelt"]
    pruebas = [
        ("geo actual, 1d, relevancia", cfg["consultas_geopoliticas"][0], {"timespan": "1d"}),
        ("geo actual, 7d, fecha", cfg["consultas_geopoliticas"][0], {"timespan": "7d", "orden": "DateDesc"}),
        ("geo simple, 7d", "Argentina Israel", {"timespan": "7d"}),
        ("geo actual, feb-2024", cfg["consultas_geopoliticas"][0], {"inicio": "20240205000000", "fin": "20240207000000"}),
        ("ciber actual, 30d", cfg["consultas_ciber"][0], {"timespan": "30d"}),
    ]
    for nombre, q, extra in pruebas:
        try:
            arts = gdelt.consultar(cfg, q, **extra)
            print(f"[diag] {nombre}: {len(arts)} artículos | ej.: {arts[0]['titulo'][:90] if arts else '-'}")
        except Exception as e:
            print(f"[diag] {nombre}: ERROR {type(e).__name__}: {e}")
        time.sleep(10)


def diagnostico_telegram(config: dict) -> None:
    """Lee los canales públicos de Telegram y muestra qué mensajes se toman como reclamo contra Argentina."""
    from .clasificador import Clasificador
    from .config import cargar_mapeo_mitre
    from .fuentes import telegram
    clasificador = Clasificador(config, cargar_mapeo_mitre())
    for canal in config.get("fuentes_telegram", {}).get("canales", []):
        mensajes, diag = telegram.leer_canal(canal)
        fechas = sorted(m["fecha"][:10] for m in mensajes)
        print(f"[telegram] {canal['nombre']}: {'OK' if diag['ok'] else 'FALLA'} HTTP {diag.get('http')} · "
              f"{diag['items']} mensajes ({fechas[0] if fechas else '-'} a {fechas[-1] if fechas else '-'}) {diag['detalle']}")
        for m in mensajes:
            c = clasificador.clasificar(m["titulo"], m["resumen"], m["url"], reclamo=True)
            if c["menciona_argentina"]:
                marca = "ATAQUE" if c["es_ataque"] else "solo menciona"
                print(f"   {marca:13} {m['fecha'][:10]} {m['url']} | {m['titulo'][:100]}")


def main() -> None:
    comando = sys.argv[1] if len(sys.argv) > 1 else "actualizar"
    if comando == "actualizar":
        procesar.ejecutar(recolectar_en_vivo=True)
    elif comando == "recalcular":
        procesar.ejecutar(recolectar_en_vivo=False)
    elif comando == "historico":
        historico.construir_gdelt_historico(cargar_config(), reiniciar="--reiniciar" in sys.argv)
    elif comando == "diagnostico":
        diagnostico_gdelt(cargar_config())
    elif comando == "telegram":
        diagnostico_telegram(cargar_config())
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
