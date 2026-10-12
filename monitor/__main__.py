"""Uso:
  python -m monitor actualizar             # revisión completa (lo que corre cada 6 horas)
  python -m monitor recalcular             # recalcula semáforo y web SIN descargar noticias
  python -m monitor historico              # continúa la descarga por partes del histórico de GDELT
  python -m monitor historico --reiniciar  # borra el histórico de GDELT y empieza de nuevo
  python -m monitor diagnostico            # prueba variantes de consulta a GDELT (para ajustar)
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
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
