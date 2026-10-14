# AGENTS.md

## Estado del proyecto
- Sitio estático, sin build. Repo: `https://github.com/estebanlab2021/inferencia_estadistica` (rama `main`), desplegado con GitHub Pages en `https://estebanlab2021.github.io/inferencia_estadistica/`. Archivos: `index.html`, `styles.css`, `app.js`, `stats_core.py`, `README.md`.
- La especificación técnica detallada (arquitectura, CDNs, flujo, UI, contrato de `stats_core.py`) está en `spec.md` — es la fuente de verdad del producto.
- Para probar localmente: `python -m http.server` en este directorio y abrir `http://localhost:8000`. Pyodide carga `stats_core.py` vía `fetch`, así que **no funciona con `file://`**.

## Arquitectura (no obvia)
- `stats_core.py` usa **solo `math` de la stdlib** (sin scipy): implementa a mano la CDF/inversa de la normal (erf + bisección), la t de Student y la F de Fisher (ambas con beta incompleta regularizada + bisección). No agregues scipy: Pyodide tendría que cargarlo y el cálculo ya está verificado.
- `app.js` tiene un objeto `TESTS` con los inputs de cada test; las claves del payload deben coincidir con los kwargs de las funciones de `stats_core.py`. El puente es `pyodide.runPython("ejecutar(<test>, <json-string>)")` donde el payload viaja como **cadena JSON** (doble `JSON.stringify`): incrustar el JSON crudo como literal de Python falla con `NameError: name 'true' is not defined` porque JS manda `true`/`false` y Python espera `True`/`False`; `json.loads()` sí los parsea bien.
- ANOVA: los inputs son **dinámicos** (selector de k, y por tratamiento una lista de inputs numéricos con botones ＋/−); `n_i` se deduce de los valores digitados y `cacheGrupos` preserva los datos al cambiar k. El panel de alternativas se oculta en ANOVA (H₁ fija).
- El boxplot de ANOVA usa el plugin **@sgratzl/chartjs-chart-boxplot** (CDN jsDelivr, UMD: `build/index.umd.min.js`, global `ChartBoxPlot`); el UMD **sí auto-registra** los controladores en el `Chart` global (la advertencia de "no auto-registra" del README aplica solo al build ESM). `renderBoxplot` crea el gráfico en `try/catch` y muestra un mensaje si el plugin no cargó. Cada tratamiento tiene **color propio**: paleta de 8 colores (`PALETA`) pasada como arreglos indexables a `backgroundColor`/`borderColor`/`outlierBackgroundColor`; la línea de mediana es gris oscuro fijo.
- Convención de los PDFs (Prof. S. Araya Pizarro, U. de La Serena): con σ desconocida se usa **S_c (cuasivarianza, /(n−1))**: t = (X̄−μ₀)/(S_c/√n). La opción S (varianza muestral, /n) es la ruta equivalente: S/√(n−1) = S_c/√n. El toggle S/S_c por defecto está en S_c.
- Frontera Z vs t: σ conocida → Z siempre (aunque n<30, así lo hacen los PDFs); σ desconocida → Z si n≥30, t si n<30 (gl = n−1; gl = n₁+n₂−2 para dos medias). ANOVA siempre es cola derecha: rechazar si F > F_α(k−1, N−k).
- Chart.js con datos en formato objeto `{x, y}` **no acepta `null`** en el array (crashea con `Cannot read properties of null (reading 'x')`); los huecos se marcan con `NaN` y los saltos de línea se logran con datasets separados, no con `null` entre puntos.
- Valores verificados contra los ejemplos resueltos de los PDFs (revisar si se toca la matemática): Z(σ)=1.55 con (203.5,200,16,50); t(Sc)=3.53 con (120,100,15,7,α=0.10,derecha), crítico 1.4398; Z(prop)=−2.80 con (0.775,0.8,2000); Z(2 medias)=−3.16 con (50,60,12,16,40,40); t(2 medias,Sc)=2.67 con (20,16,3,2,10,5,α=0.10), crítico 1.7709; **ANOVA** (Empleados 1–3 del PDF): SST=992, SSE=90, F=49.6, p=1.3806e-05, F_crít(0.05; 2,9)=4.25649473 → rechaza.

## Producto
App web pedagógica, simple y minimalista, para contrastes de hipótesis estadísticos. Contexto: consultoría de estadística en español → textos de la UI en español.

## Restricciones duras (definidas por el usuario)
- HTML estático que se despliegue en GitHub Pages: sin backend, sin servidor, sin build obligatorio.
- Los cálculos se hacen en Python ejecutándose en el navegador vía WebAssembly. Pyodide (o PyScript) es la vía estándar para esto; cargarlo desde CDN para mantener el sitio 100% estático.
- Modularidad ante todo: núcleo estadístico en Python puro (funciones sin acceso al DOM) separado de la capa de UI, de modo que agregar un test nuevo no altere la estructura existente.

## Tests a implementar (alcance acordado)
1. Una media: Z (varianza poblacional conocida) o t (desconocida).
2. Diferencia de dos medias, muestras independientes: Z o t.
3. Una proporción (Z).
4. Diferencia de dos proporciones (Z).
5. ANOVA de un factor (F): k tratamientos con valores individuales por tratamiento; tabla ANOVA completa + gráfico de F + boxplot de grupos.

## Salida requerida por cada test
- Datos ingresados por inputs en la página; resultados en la misma página, sin recarga.
- Procedimiento visible paso a paso: fórmula en LaTeX (render con MathJax/KaTeX) → sustitución con los valores → estadístico (Z, t o F), p-valor y conclusión del contraste.
- Gráfico de la distribución de referencia (normal, t o F) con las regiones críticas de rechazo sombreadas y la posición del estadístico calculado marcada. En ANOVA, además: tabla ANOVA (formato de `../formulas.md`) y boxplot de los grupos.

## Referencia y verificación
- Los PDFs `../Hipotesis de una muestra .pdf`, `../Hipótesis de 2 muestras .pdf` y `../Anovas.pdf`, más `../formulas.md` (en la carpeta padre, fuera de este directorio) definen la notación, los procedimientos y el ejemplo ANOVA de referencia.
- No hay toolchain de build/test: el sitio es estático; la verificación es abrir la página en el navegador y comparar contra los ejemplos de los PDFs (valores listados arriba).
- Si un cambio de estilo/JS/Python no se ve en el navegador, es caché: `index.html` enlaza `styles.css?v=3` y `app.js?v=4`, y `app.js` carga `stats_core.py?v=2` vía `fetch` para bustear la caché — bumpear el número ante cambios de CSS, JS o Python, o hacer Ctrl+F5.
