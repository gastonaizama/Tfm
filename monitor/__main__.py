"""Uso:
  python -m monitor actualizar             # revisión completa (lo que corre cada 6 horas)
  python -m monitor recalcular             # recalcula semáforo y web SIN descargar noticias
  python -m monitor historico              # continúa la descarga por partes del histórico de GDELT
  python -m monitor historico --reiniciar  # borra el histórico de GDELT y empieza de nuevo
"""
import sys

from . import historico, procesar
from .config import cargar_config


def main() -> None:
    comando = sys.argv[1] if len(sys.argv) > 1 else "actualizar"
    if comando == "actualizar":
        procesar.ejecutar(recolectar_en_vivo=True)
    elif comando == "recalcular":
        procesar.ejecutar(recolectar_en_vivo=False)
    elif comando == "historico":
        historico.construir_gdelt_historico(cargar_config(), reiniciar="--reiniciar" in sys.argv)
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
