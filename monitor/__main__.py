"""Uso:
  python -m monitor actualizar        # revisión completa (lo que corre cada 6 horas)
  python -m monitor recalcular        # recalcula semáforo y web SIN descargar noticias nuevas
  python -m monitor historico         # descarga (una vez) el histórico de GDELT y recalcula
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
        historico.construir_gdelt_historico(cargar_config())
        procesar.ejecutar(recolectar_en_vivo=False)
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
