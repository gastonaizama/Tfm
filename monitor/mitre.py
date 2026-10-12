"""Catálogo MITRE ATT&CK (Enterprise).

Se descarga el paquete STIX oficial desde el repositorio público de MITRE
(github.com/mitre/cti) y se guarda solo lo necesario (id, nombre, táctica, enlace)
en datos/mitre_tecnicas.json. Si la descarga falla, se usa la copia guardada.
"""
import requests

from .config import ARCHIVO_MITRE, guardar_json, leer_json

URL_STIX = "https://raw.githubusercontent.com/mitre/cti/master/enterprise-attack/enterprise-attack.json"


def actualizar_catalogo(tecnicas_usadas: set[str]) -> dict:
    catalogo = leer_json(ARCHIVO_MITRE, {})
    try:
        r = requests.get(URL_STIX, timeout=120)
        r.raise_for_status()
        nuevo = {}
        for obj in r.json()["objects"]:
            if obj.get("type") != "attack-pattern" or obj.get("revoked") or obj.get("x_mitre_deprecated"):
                continue
            ref = next((x for x in obj.get("external_references", []) if x.get("source_name") == "mitre-attack"), None)
            if ref and ref["external_id"] in tecnicas_usadas:
                nuevo[ref["external_id"]] = {
                    "nombre": obj["name"],
                    "tacticas": [p["phase_name"] for p in obj.get("kill_chain_phases", [])],
                    "url": ref.get("url", ""),
                }
        if nuevo:
            catalogo = nuevo
            guardar_json(ARCHIVO_MITRE, catalogo)
            print(f"[MITRE] Catálogo actualizado: {len(catalogo)} técnicas")
    except Exception as e:  # sin conexión: se sigue con la copia local
        print(f"[MITRE] No se pudo actualizar ({e}); se usa la copia local")
    return catalogo
