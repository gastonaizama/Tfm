# Instrucciones del proyecto (TFM · Monitor Ciber-Geopolítico Argentina)

- El autor no programa: explicar cada paso en español, de forma simple, y avisar cuando deba hacer algo él (por ejemplo, en la configuración de GitHub).
- Desarrollar en la rama de trabajo y llevar los cambios a `main` mediante Pull Request, que aprueba el autor.

## Memoria del proyecto (obligatorio en cada avance)
El autor pidió que **todos los avances queden plasmados en la memoria Word** (`memoria/Memoria_TFM.docx`).
En cada avance:
1. Agregar una entrada en `memoria/bitacora.json` → `eventos` (fecha, tipo, título, detalle). Si el avance es relevante, agregar también una versión nueva en `versiones`.
2. Si cambia algo descrito en los capítulos (fuentes, reglas, semáforo, web, workflows, decisiones, estado), actualizar el texto en `memoria/generar_memoria.js`.
3. Si ayuda a entender, agregar capturas en `memoria/capturas/` y referenciarlas con `figura(...)`.
4. Regenerar:
   ```
   node memoria/generar_memoria.js
   python3 memoria/actualizar_indice.py memoria/Memoria_TFM.docx
   ```
5. Revisar el resultado (convertir a PDF y mirar las páginas), hacer commit y enviar el archivo al autor.

## Integridad de los datos
- No inventar incidentes ni hechos: todo dato cargado en `datos/*.csv` debe tener fuente y ser validado por el autor.
