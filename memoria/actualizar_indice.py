"""Rellena el índice del .docx con LibreOffice, para que se vea completo aunque el documento
se abra en un visor que no actualiza campos (vista previa de GitHub, Google Drive, etc.).
Uso: python3 memoria/actualizar_indice.py memoria/Memoria_TFM.docx
Requiere LibreOffice y el módulo de Python 'uno'. Si no están, el .docx sigue siendo válido:
Word completa el índice al abrirlo."""
import os
import subprocess
import sys
import tempfile
import time

import uno
from com.sun.star.beans import PropertyValue


def pv(nombre, valor):
    p = PropertyValue()
    p.Name, p.Value = nombre, valor
    return p


def main(ruta: str) -> None:
    ruta = os.path.abspath(ruta)
    perfil = tempfile.mkdtemp(prefix="lo-perfil-")
    puerto = "2002"
    proc = subprocess.Popen([
        "soffice", "--headless", "--invisible", "--nologo", "--norestore",
        f"-env:UserInstallation=file://{perfil}",
        f"--accept=socket,host=127.0.0.1,port={puerto};urp;",
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        local = uno.getComponentContext()
        resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
        for _ in range(60):
            try:
                ctx = resolver.resolve(f"uno:socket,host=127.0.0.1,port={puerto};urp;StarOffice.ComponentContext")
                break
            except Exception:
                time.sleep(0.5)
        else:
            raise RuntimeError("No se pudo conectar con LibreOffice")
        desktop = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
        url = uno.systemPathToFileUrl(ruta)
        doc = desktop.loadComponentFromURL(url, "_blank", 0, (pv("Hidden", True),))
        indices = doc.getDocumentIndexes()
        cantidad = indices.getCount()
        for i in range(cantidad):
            indices.getByIndex(i).update()
        doc.storeToURL(url, (pv("FilterName", "MS Word 2007 XML"),))
        doc.close(True)
        print(f"Índice actualizado ({cantidad} índice/s): {ruta}")
    finally:
        proc.terminate()


if __name__ == "__main__":
    main(sys.argv[1])
