# Especificación Técnica (spec.md) - App de Contrastes de Hipótesis

## 1. Arquitectura de Archivos Propuesta
El proyecto debe autogenerarse con la siguiente estructura limpia y estática:
- `index.html` -> El contenedor principal de la interfaz de usuario.
- `styles.css` -> Estilos minimalistas y limpios.
- `app.js` -> Manejo del DOM, carga de Pyodide, y puente entre inputs y Python.
- `stats_core.py` -> Núcleo de cálculo estadístico en Python puro (sin dependencias externas complejas, solo matemática nativa de Python y `scipy` si Pyodide la incluye por defecto, o fórmulas explícitas).
- `README.md` -> Documentación del proyecto para usuarios y docentes.

## 2. Flujo de Inicialización de la Aplicación
1. El usuario abre `index.html`.
2. Se cargan las CDNs externas especificadas en las restricciones duras:
   - **Pyodide** (WebAssembly para ejecutar Python).
   - **KaTeX** o **MathJax** (para renderizar fórmulas estadísticas en LaTeX).
   - **Chart.js** (o una librería ligera de Canvas) para dibujar las distribuciones y zonas de rechazo de forma dinámica.
   - **@sgratzl/chartjs-chart-boxplot** (plugin de Chart.js, UMD que auto-registra el controlador `boxplot` en el `Chart` global) para el boxplot de grupos del módulo ANOVA.
3. Se muestra un indicador visual de "Cargando motor estadístico (Python)..." hasta que Pyodide esté listo.

## 3. Especificación de la Interfaz (UI)
- **Selector de Test**: Un menú desplegable en la parte superior para elegir uno de los 5 tests del alcance (4 contrastes + ANOVA de un factor).
- **Panel de Inputs dinámicos**: Cambia según el test seleccionado (ej: para una media pide: x̄, μ₀, σ o s, y n).
- **Panel de ANOVA** (solo para ANOVA de un factor):
  - Selector de **número de tratamientos (k)** (2 a 8).
  - Por cada tratamiento: input de nombre (ej: "Empleado 1") y una **lista dinámica de inputs numéricos** con botones **＋ Agregar valor** / **− Quitar valor**. `n_i` se deduce de la cantidad de valores ingresados y se muestra en vivo (insignia "n_i = …"). Cambiar k preserva los datos ya digitados. Por defecto se carga el ejemplo de los PDFs.
- **Toggle S / S_c (tests de medias con varianza desconocida)**: Radio button segmentado para elegir si el dato ingresado es **Desviación Estándar Muestral (S)** (varianza con n) o **Cuasidesviación Estándar / Corregida (S_c)** (varianza con n−1, convención de los PDFs, por defecto). La fórmula de LaTeX mostrada y el cálculo en Python cambian según lo elegido:
  - S:  error estándar = S/√(n−1)  (una media)  |  S_p = √((n₁S₁²+n₂S₂²)/(n₁+n₂−2))  (dos medias)
  - S_c: error estándar = S_c/√n  (una media)  |  S_pc = √(((n₁−1)S_c1²+(n₂−1)S_c2²)/(n₁+n₂−2))  (dos medias)
  - Ambas son algebraicamente equivalentes si los datos son consistentes (S/√(n−1) = S_c/√n).
- **Panel de Opciones del Contraste**: Radio buttons para elegir el tipo de hipótesis alternativa:
  - Bilateral (H₁: μ ≠ μ₀)
  - Unilateral derecha (H₁: μ > μ₀)
  - Unilateral izquierda (H₁: μ < μ₀)
  - *Nota:* en ANOVA este panel se oculta — ANOVA tiene H₁ fija: "No todos los promedios son iguales".
- **Panel de Resultados**: Oculto hasta que se presione "Calcular". Al activarse, muestra:
  - El paso a paso en LaTeX sustituyendo los valores ingresados.
  - El gráfico interactivo generado con los datos calculados.
  - En ANOVA: la **tabla ANOVA completa** (formato de `formulas.md`: Fuente de Variación | df | SC | CM | F | p-value | Valor crítico para F) y **dos gráficos**: la distribución F con zona de rechazo y el F calculado, y un **boxplot** de los grupos/tratamientos.

## 4. Requisitos del Núcleo Estadístico (Python)
Las funciones en `stats_core.py` deben recibir datos primitivos (floats/ints) y retornar un diccionario o JSON con:
- `estadistico_calculado` (float)
- `p_valor` (float)
- `valores_criticos` (list o float) para el sombreado del gráfico.
- Cadenas de texto con las fórmulas sustituidas formateadas para LaTeX.

Para ANOVA, `test_anova(grupos, alpha)` recibe `grupos = [{"nombre": str, "datos": [floats]}` (k ≥ 2, N > k) y retorna, además:
- `tabla`: filas de la tabla ANOVA (Fuente de Variación, df, SC, CM, F, p-value, Valor crítico para F).
- `grupos`: por grupo, `n`, `media` y `datos` (para el boxplot).
- `media_global`.
- La distribución F se implementa con la beta incompleta regularizada (misma rutina `_beta_reg` de la t de Student), sin scipy.

## 5. Fórmulas Matemáticas y Criterios de Cálculo
El motor estadístico y el renderizado visual de pasos deben basarse estrictamente en la siguiente tabla de referencia:

|Estadístico | Muestras grandes  (n ≥ 30) | Muestras pequeñas (n<30)|
| :--- | :---| :--- |
|**Una Media** | $Z=\frac{\bar{X}-\mu}{\sigma / \sqrt{n}}$ | **Opción A (Varianza muestral):** $t=\frac{\bar{X}-\mu}{S / \sqrt{n-1}}$<br>**Opción B (Cuasivarianza / PDF):** $t=\frac{\bar{X}-\mu}{S_{c} / \sqrt{n}}$|
| **Diferencia de Medias** | $Z=\frac{\bar{X}_{1}-\bar{X}_{2}}{\sqrt{\frac{S_{1}^{2}}{n_{1}}+ \frac{S_{2}^{2}}{n_{2}}}}$ | **Opción A (Varianzas muestrales):** $t = \frac{\bar{X}_{1}-\bar{X}_{2}}{S_{p} \sqrt{\frac{1}{n_{1}}+\frac{1}{n_{2}}}}$, donde $S_{p}=\sqrt{\frac{n_{1} S_{1}^{2} + n_{2} S_{2}^{2}}{n_{1}+n_{2}-2}}$<br><br>**Opción B (Cuasivarianzas / PDF):** $t = \frac{\bar{X}_{1}-\bar{X}_{2}}{S_{pc} \sqrt{\frac{1}{n_{1}}+\frac{1}{n_{2}}}}$, donde $S_{pc}=\sqrt{\frac{(n_{1}-1)S_{1c}^{2} + (n_{2}-1)S_{2c}^{2}}{n_{1}+n_{2}-2}}$ |
| **Proporciones** | $Z = \frac{\hat{p}-P}{\sqrt{\frac{P(1-P)}{n}}}$ |
| **Diferencia de Proporciones** | $Z = \frac{\hat{p}_{1}-\hat{p}_{2}}{\sqrt{P \cdot Q\left( \frac{1}{n_{1}}+ \frac{1}{n_{2}}\right)}}$, donde: $P = \frac{n_{1} \cdot \hat{p}_{1} + n_{2} \cdot \hat{p}_{2} }{n_{1} + n_{2}}$ y $Q=1-P$

### ANOVA de un factor (tabla y fórmulas)

| Fuente de Variación | Grados de Libertad ($df$) | Suma de Cuadrados ($SC$) | Cuadrados Medios ($CM$) | Estadístico $F$ |
| :--- | :--- | :--- | :--- | :--- |
| **Entre grupos (Tratamientos)** | $k - 1$ | $SST = \sum_{i=1}^{k} n_i (\bar{x}_i - \bar{x})^2$ | $MST = \frac{SST}{k - 1}$ | $F = \frac{MST}{MSE}$ |
| **Dentro de los grupos (Error)** | $N - k$ | $SSE = \sum_{i=1}^{k} \sum_{j=1}^{n_i} (x_{ij} - \bar{x}_i)^2$ | $MSE = \frac{SSE}{N - k}$ | |
| **Total** | $N - 1$ | $Total = \sum_{i=1}^{k} \sum_{j=1}^{n_i} (x_{ij} - \bar{x})^2 = SST + SSE$ | | |

- Hipótesis: $H_0$: los promedios de todos los grupos son iguales ($\mu_1 = \mu_2 = \cdots = \mu_k$); $H_1$: no todos los promedios son iguales.
- Decisión: rechazar $H_0$ si $F > F_{\alpha}(k-1,\ N-k)$ (prueba siempre unilateral por la derecha).
- $p\text{-value} = P(F_{k-1,\,N-k} > F_{obs})$.
- Notación: $k$ = número de grupos, $n_i$ = observaciones del grupo $i$, $N = \sum n_i$, $\bar{x}_i$ = media del grupo $i$, $\bar{x}$ = media global.

*Nota para el Agente:* Revisa los archivos del directorio superior (`../Hipotesis de una muestra .pdf`, `../Hipótesis de 2 muestras .pdf`, `../Anovas.pdf` y `../formulas.md`) para asegurar que la notación simbólica y las decisiones de fórmulas coincidan exactamente con la convención del material pedagógico.

## 6. Salida Esperada por cada Test
Al presionar "Calcular", la pantalla debe actualizarse (sin recargar) mostrando:
1. **Paso a paso:** Mostrar la fórmula teórica en LaTeX, luego la misma fórmula con los números sustituidos, y finalmente el valor final del estadístico calculado (\(Z\) o \(t\)).
2. **P-Valor e Hipótesis:** El p-valor calculado según la hipótesis alternativa seleccionada (Bilateral, Unilateral Izquierda, Unilateral Derecha) y la conclusión estadística en español.
3. **Gráfico:** Una curva dinámica sombreada que represente gráficamente el nivel de significación (\(\alpha\)) y la posición exacta del estadístico.

En **ANOVA** la salida es:
1. Paso a paso: medias de los grupos y media global, SST sustituida (ej: `4·(56−58)² + 4·(70−58)² + 4·(48−58)² = 992`), SSE sustituida (ej: `14 + 62 + 14 = 90`), F, p-valor y valor crítico.
2. **Tabla ANOVA** con todas sus columnas (idéntica al formato de `formulas.md` y el PDF: Fuente de Variación, df, SC, CM, F, p-value, Valor crítico para F).
3. **Gráfico de F**: curva de la distribución F, área de rechazo sombreada (cola derecha) y la posición del F calculado.
4. **Boxplot** de los grupos/tratamientos involucrados.


