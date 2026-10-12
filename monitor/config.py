"""Carga de la configuración y rutas del proyecto."""
import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DIR_CONFIG = RAIZ / "config"
DIR_DATOS = RAIZ / "datos"
DIR_WEB = RAIZ / "web"

ARCHIVO_NOTICIAS = DIR_DATOS / "noticias_vivo.json"        # archivo propio que acumula lo visto en vivo
ARCHIVO_GDELT_HIST = DIR_DATOS / "gdelt_historico.json"     # se genera una sola vez (modo histórico)
ARCHIVO_INCIDENTES = DIR_DATOS / "incidentes_historicos.csv"
ARCHIVO_HECHOS = DIR_DATOS / "hechos_clave.csv"
ARCHIVO_MITRE = DIR_DATOS / "mitre_tecnicas.json"
ARCHIVO_ESTADO_FUENTES = DIR_DATOS / "estado_fuentes.json"
ARCHIVO_SALIDA_WEB = DIR_WEB / "datos.json"                 # lo que lee la página


def cargar_config() -> dict:
    with open(DIR_CONFIG / "config.json", encoding="utf-8") as f:
        return json.load(f)


def cargar_mapeo_mitre() -> dict:
    with open(DIR_CONFIG / "mitre_mapeo.json", encoding="utf-8") as f:
        return json.load(f)


def leer_json(ruta: Path, por_defecto):
    if not ruta.exists():
        return por_defecto
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def guardar_json(ruta: Path, datos, compacto: bool = False) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as f:
        if compacto:
            json.dump(datos, f, ensure_ascii=False, separators=(",", ":"))
        else:
            json.dump(datos, f, ensure_ascii=False, indent=1)
        f.write("\n")
