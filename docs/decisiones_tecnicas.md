# Decisiones técnicas

Registro de las decisiones de diseño de la plataforma, con su motivo y las alternativas descartadas. Sirve como base para el capítulo de metodología e implementación de la memoria del TFM.

Formato de cada decisión: **contexto → decisión → motivo → alternativas descartadas / consecuencias**.

---

## A. Arquitectura

### D1. Arquitectura sin servidor: GitHub Actions + GitHub Pages
- **Contexto:** la plataforma debe funcionar sin infraestructura propia, sin costo y sin instalar nada en la computadora del autor.
- **Decisión:** GitHub Actions ejecuta el proceso de recolección y análisis cada 6 horas, y GitHub Pages publica una web estática que lee el resultado (`web/datos.json`).
- **Motivo:** el servicio es gratuito para repositorios públicos, no requiere mantener un servidor, el proceso queda auditable (cada ejecución deja un registro en *Actions*) y el repositorio sirve también como portfolio.
- **Descartado:** un servidor propio o un VPS (costo y mantenimiento), funciones *serverless* de nube comercial (requieren cuenta y tarjeta) y bases de datos externas.
- **Consecuencias:** la frecuencia mínima razonable es de horas, no de minutos, porque GitHub puede retrasar los *cron* programados. Para alerta temprana de hacktivismo, una resolución de 6 horas es adecuada.

### D2. Los datos se guardan en el propio repositorio (git como base de datos)
- **Decisión:** después de cada ejecución, el *workflow* hace un *commit* de `datos/` y `web/datos.json`.
- **Motivo:** queda un historial versionado y reproducible de lo que la plataforma "sabía" en cada momento. Esto es útil para la evaluación del TFM y como trazabilidad de inteligencia. No requiere servicios externos.
- **Consecuencias:** se guardan solo las noticias potencialmente relevantes (ver D10) para que el repositorio no crezca de forma descontrolada.

### D3. Python con dos dependencias mínimas
- **Decisión:** Python 3.12 con `requests` (HTTP) y `feedparser` (RSS/Atom), con versiones fijadas en `requirements.txt`.
- **Motivo:** es el lenguaje estándar en CTI, legible para no programadores y con pocas dependencias, lo que reduce la superficie de ataque de la cadena de suministro y simplifica la replicación.

### D4. La web es HTML/CSS/JavaScript sin librerías ni CDN
- **Decisión:** la línea de tiempo se dibuja con SVG generado a mano en `web/app.js`.
- **Motivo:** no hay dependencias externas que puedan romperse o rastrear al visitante, carga rápido y funciona igual en GitHub Pages que abriendo el archivo localmente. Incluye modo oscuro, diseño adaptable a celular y una tabla accesible con todos los eventos.

### D5. Toda la lógica de alertas se calcula en Python, no en el navegador
- **Decisión:** Python precalcula la **serie diaria de niveles**, los periodos de vigilancia y las alertas. La web solo filtra por fechas y muestra los datos.
- **Motivo:** hay una única fuente de verdad, con la misma lógica probada por los tests (`tests/test_reglas.py`). El modo histórico y el modo en vivo usan exactamente el mismo algoritmo.
- **Consecuencia:** al cambiar un parámetro en `config.json` hay que recalcular. El *workflow* lo hace automáticamente al detectar cambios en `config/` o en los CSV.

### D6. Configuración externa en JSON
- **Decisión:** las palabras clave, los pesos, las fuentes, los umbrales y la ventana de vigilancia están en `config/config.json`. Las reglas MITRE están en `config/mitre_mapeo.json`.
- **Motivo:** el analista puede ajustar el modelo desde la web de GitHub sin tocar el código. Además, separa el "conocimiento de dominio" del "código".

---

## B. Fuentes

### D7. Selección y validación de las fuentes RSS
- **Prueba realizada:** el 12/10/2026, desde los servidores de GitHub Actions.
- **Resultado:** los seis feeds solicitados funcionan. Para WeLiveSecurity (ESET) la dirección correcta es `https://www.welivesecurity.com/es/rss/feed/` (`/es/feed/` responde 404). Para Infobae, la dirección correcta es `/arc/outboundfeeds/rss/` (`/feeds/rss/` responde 404).
- **Decisión:** se usan los seis feeds. Cada revisión registra el estado de cada uno (`datos/estado_fuentes.json`) y la web lo muestra. Si un feed se cae, el resto sigue funcionando.
- **Combinación de fuentes:** los medios especializados en ciberseguridad (en inglés) detectan campañas reportadas internacionalmente. Los medios argentinos (en español) detectan hechos geopolíticos locales y ataques a organismos nacionales que no llegan a la prensa internacional.

### D8. GDELT DOC 2.0 API como fuente geopolítica con historial
- **Prueba realizada:** la API devuelve artículos de 2023–2024 consultando por rango de fechas (`startdatetime`/`enddatetime`). Por ejemplo, se obtuvieron 250 artículos para el 1–15 de febrero de 2024. El modo `TimelineVolRaw` devuelve el volumen diario de todo el periodo.
- **Limitación detectada:** GDELT permite una consulta cada 5 segundos por IP. Los servidores de GitHub son compartidos, así que se reciben errores HTTP 429 aun respetando ese ritmo.
- **Decisión:** se espera 6 segundos entre consultas y se reintenta con espera creciente (15, 30, 45… segundos) ante un 429. Si una consulta falla, no se detiene la revisión: el error queda registrado en el diagnóstico de fuentes.
- **Consultas:** dos geopolíticas (en español e inglés) y dos cibernéticas (en español e inglés), definidas en `config.json`.

### D9. El histórico de GDELT se descarga una sola vez
- **Decisión:** `python -m monitor historico` descarga agosto 2023 – julio 2024 en **tramos de 3 días** y lo guarda en `datos/gdelt_historico.json`. El *workflow* lo hace automáticamente si el archivo no existe.
- **Motivo:** son unas 500 consultas (alrededor de 1 hora). Repetirlas cada 6 horas sería innecesario y abusivo con un servicio gratuito.
- **Tramos cortos:** cada consulta devuelve como máximo 250 artículos. Los tramos que llegan al máximo se marcan como `saturado: true` para que se sepa dónde puede faltar cobertura.

### D10. Archivo propio de noticias en vivo
- **Contexto:** los feeds RSS solo muestran las últimas 5–100 noticias; lo anterior desaparece.
- **Decisión:** cada revisión agrega a `datos/noticias_vivo.json` las noticias nuevas que mencionan a Argentina **y** contienen algún término geopolítico o cibernético. Se conservan 400 días.
- **Motivo:** la plataforma construye su propio historial desde el día en que empieza a funcionar. Se guardan también noticias con puntaje bajo, para poder recalcular si se cambian los umbrales.
- **Descartado:** guardar todas las noticias (decenas de MB por año en el repositorio).

### D11. Carga manual de incidentes y hechos clave (CSV)
- **Contexto:** los ataques hacktivistas se anuncian sobre todo en Telegram y X, y la prensa no recoge todos. No existe un registro público y estructurado de los incidentes del caso de estudio.
- **Decisión:** `datos/incidentes_historicos.csv` (ataques) y `datos/hechos_clave.csv` (hechos geopolíticos de referencia), editables desde la web de GitHub. Las columnas siguen campos habituales en CTI: actor, objetivo, sector, TTP (MITRE), fuente, **confianza** y **verificado**.
- **Regla:** un hecho clave abre una ventana de vigilancia por sí solo, porque es un hecho verificado por el analista. Un incidente cargado cuenta siempre como ataque.
- **Nota de integridad:** los hechos clave incluidos se cargaron con fecha y descripción, pero sin URL de fuente y con `verificado = no`. El autor debe completarlos y verificarlos. El CSV de incidentes se entrega solo con una fila de ejemplo, que se ignora; no se inventaron incidentes.

---

## C. Clasificación (Fase 1)

### D12. Normalización y búsqueda por palabra completa
- **Decisión:** el texto se pasa a minúsculas, sin tildes ni HTML, y los términos se buscan como **palabras completas**. Por ejemplo, "iran" no coincide con "Irán" dentro de "tirano".
- **Motivo:** reduce los falsos positivos por coincidencias parciales y permite escribir las palabras clave sin preocuparse por tildes o mayúsculas.

### D13. Puntaje geopolítico ponderado + mención obligatoria de Argentina
- **Decisión:** cada término geopolítico tiene un peso (1 o 2). Una noticia es relevante si **menciona a Argentina** y suma ≥ 2 (umbral configurable).
- **Motivo:** "Argentina" e "Israel" aparecen juntas en muchas noticias irrelevantes (deportes, comercio). Los términos con más carga de conflicto (Hamás, Irán, AMIA, Hezbolá) pesan 2. Los términos de contexto (Israel, Palestina, embajada, ONU) pesan 1 y necesitan otro término para disparar.
- **Clasificación sobre título y resumen:** en GDELT solo se dispone del título. La consulta a GDELT funciona como prefiltro (busca en el texto completo), pero la regla se aplica sobre el título para evitar que cualquier noticia de Medio Oriente publicada por un medio argentino active la alerta.

### D14. Corroboración: al menos 2 fuentes distintas por día
- **Decisión:** un día es detonante solo si las noticias relevantes provienen de **≥ 2 fuentes distintas** (configurable).
- **Motivo:** es un principio básico de inteligencia (corroboración independiente). Evita que una sola nota, o un mismo medio que publica varias notas, abra una ventana.

### D15. Detección de ataques: término cibernético + Argentina
- **Decisión:** una noticia es "ataque" si contiene un término cibernético y menciona a Argentina (o un dominio `.gob.ar`). Si una noticia es a la vez geopolítica y de ataque, se clasifica como **ataque**, y sus términos geopolíticos se conservan como contexto.
- **Términos genéricos excluidos:** se descartaron "filtración" y "leaked" a secas porque en la prensa argentina se usan mucho para filtraciones políticas (audios, documentos). Se usan frases más específicas ("filtración de datos", "datos filtrados").

### D16. "REM" solo en mayúsculas
- **Decisión:** las siglas ambiguas (`terminos_sensibles_mayusculas`) solo cuentan si aparecen escritas en MAYÚSCULAS como palabra aislada.
- **Motivo:** "rem" en minúsculas aparece en otros contextos (por ejemplo, "fase REM" del sueño en notas de salud, o fragmentos de palabras).

### D17. Mapeo a MITRE ATT&CK por reglas
- **Decisión:** `config/mitre_mapeo.json` asocia expresiones con técnicas Enterprise ATT&CK:
  - defacement → **T1491.002** External Defacement
  - DDoS / sitio caído → **T1498** Network DoS, **T1499** Endpoint DoS
  - filtración de datos → **T1213** Data from Information Repositories, **T1567** Exfiltration Over Web Service
  - explotación → **T1190**, credenciales → **T1078**, ransomware → **T1486**, phishing → **T1566**
- Los nombres y enlaces oficiales se descargan en cada ejecución del paquete STIX de MITRE (`github.com/mitre/cti`), con una copia local por si falla la descarga.
- **Motivo:** el hacktivismo del caso de estudio usa sobre todo defacement, DDoS y filtraciones. Mapear a ATT&CK permite comparar con otros informes de CTI.
- **Limitación:** el mapeo es indicativo, porque se basa en cómo la prensa describe el ataque.

---

## D. Semáforo

### D18. Ventana de vigilancia de 7 días, configurable, con fusión de ventanas
- **Decisión:** cada día detonante abre una ventana `[día, día + 7]`. Si un detonante cae dentro de una ventana abierta, la ventana se **extiende** y se forma un único "periodo de vigilancia".
- **Motivo:** los hechos geopolíticos suelen llegar en racimos (anuncio, reacciones, viaje), y fusionarlos evita alertas amarillas duplicadas. Los 7 días son un valor inicial razonable para campañas hacktivistas de respuesta rápida, y la memoria puede analizar la sensibilidad a 3, 7 y 14 días cambiando `ventana_vigilancia_dias`.

### D19. Rojo persistente hasta el cierre de la ventana
- **Decisión:** después del primer ataque dentro de un periodo, el nivel queda en **rojo** hasta que el periodo termina.
- **Motivo:** la campaña sigue activa mientras dure la ventana. Bajar a amarillo al día siguiente del ataque transmitiría una falsa sensación de seguridad.

### D20. Alertas informativas para ataques sin detonante
- **Decisión:** los ataques fuera de cualquier ventana no cambian el semáforo, pero se listan como alertas "info".
- **Motivo:** permiten **evaluar el modelo**. Un ataque sin detonante previo puede indicar un detonante no detectado (falso negativo del carril geopolítico) o actividad no ligada a la geopolítica. Para la memoria se puede calcular qué proporción de ataques cayó dentro de ventanas, que funciona como una medida de capacidad de anticipación.

---

## E. Automatización y calidad

### D21. Horario: cada 6 horas, en el minuto 17
- **Decisión:** `cron: "17 */6 * * *"`.
- **Motivo:** GitHub recomienda evitar el minuto 0, porque concentra la carga y produce retrasos.

### D22. Workflows separados para producción y verificación
- `actualizar.yml` (rama `main`): se ejecuta por programación, manualmente o al cambiar la configuración. Guarda los datos y publica la web.
- `verificar.yml` (ramas de desarrollo y *pull requests*): ejecuta los tests y una revisión real contra las fuentes **sin guardar nada**. Deja la web resultante como *artifact* descargable.
- **Motivo:** probar los cambios con datos reales antes de que afecten a la plataforma publicada.

### D23. Tests automáticos de las reglas
- `tests/test_reglas.py` comprueba la clasificación (geo, ataque, REM, técnicas MITRE) y el semáforo (verde, amarillo, rojo, corroboración, fusión de ventanas, ventana configurable). Se ejecutan en cada *workflow* antes de procesar datos.

### D24. Secretos
- Ninguna credencial va en el código. La Fase 2 leerá `ANTHROPIC_API_KEY` desde los **secretos de GitHub Actions**, que se inyectan como variable de entorno y GitHub oculta en los registros.

---

## F. Fase 2 (diseño previsto)

### D25. Modelos y contrato de datos de la IA
- **Clasificación:** Claude Haiku 5.5 (`claude-haiku-5-5`), por su bajo costo y latencia, para procesar todas las noticias en cada revisión. Devolverá los mismos campos que el clasificador de reglas (`carril`, `puntaje`, `tecnicas`, `grupos`), más `confianza` y `justificacion`. Así se puede **comparar** con las reglas (evaluación A/B en la memoria) y el semáforo no cambia.
- **Informe:** Claude Sonnet 5.5 (`claude-sonnet-5-5`), solo cuando el nivel es rojo (configurable), para controlar el costo. Tendrá la estructura de un informe de inteligencia: BLUF, contexto, actividad observada, TTP, evaluación con lenguaje probabilístico estimativo, recomendaciones y fuentes.
- **Punto de integración único:** `monitor/ia/integracion.py`. Si `ia.activada` es `false`, o falta el secreto, la plataforma funciona exactamente igual que en la Fase 1.

---

## G. Limitaciones y consideraciones éticas

- El sistema mide **coincidencia temporal**, no atribución. Una alerta roja no prueba que el ataque fuera motivado por el hecho geopolítico.
- Las palabras clave tienen sesgo de idioma (español/inglés) y de cobertura mediática: los ataques a organismos pequeños pueden no llegar a la prensa.
- Solo se usan fuentes abiertas (OSINT). No se accede a canales cerrados ni se interactúa con actores.
- Por respeto a los derechos de los medios, se almacena solo el título, un resumen breve y el enlace de cada noticia.
