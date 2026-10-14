# Inferencia Estadística — Contrastes de Hipótesis

App web **pedagógica e interactiva** para contrastes de hipótesis estadísticos. Diseñada para enseñanza: muestra el procedimiento completo paso a paso, con fórmulas en LaTeX, gráficos de las distribuciones de referencia y las regiones críticas de rechazo.

> Contexto: consultoría de estadística en español. Notación y convenciones según el material del **Prof. Sebastián Araya Pizarro (Universidad de La Serena)**.

## 🧪 Pruebas disponibles

| # | Prueba | Estadístico | Distribución |
|---|--------|:-----------:|:------------:|
| 1 | Una media (σ conocida o desconocida) | Z / t | Normal / t de Student |
| 2 | Diferencia de dos medias (muestras independientes) | Z / t | Normal / t de Student |
| 3 | Una proporción | Z | Normal |
| 4 | Diferencia de dos proporciones | Z | Normal |
| 5 | ANOVA de un factor | F | F de Fisher |

## ✨ Características

- **Paso a paso visible**: fórmula teórica en LaTeX → sustitución con los valores ingresados → estadístico, p-valor y conclusión del contraste.
- **Gráficos interactivos** (Chart.js): curva de la distribución de referencia con la **región de rechazo sombreada** y el estadístico calculado marcado.
- **ANOVA completo**: tabla ANOVA (Fuente de Variación · df · SC · CM · F · p-value · Valor crítico), gráfico de F y **boxplot por tratamiento, cada uno con su propio color**.
- **Ingreso dinámico de datos**: en ANOVA se elige el número de tratamientos (*k*, de 2 a 8) y se agregan/quitan valores por tratamiento con botones ＋/−; *n_i* se actualiza en vivo y los datos se conservan al cambiar *k*.
- **Convención pedagógica**: con σ desconocida se usa **S_c** (cuasivarianza, /(n−1)) por defecto — convención de los PDFs — con toggle explícito S/S_c.
- **Frontera Z vs t** automática: σ conocida → Z siempre; σ desconocida → Z si n ≥ 30, t si n < 30.
- **100 % estática**: los cálculos corren en **Python dentro del navegador** (Pyodide / WebAssembly). Sin backend, sin servidor, sin build.

## 🚀 Demo en vivo

👉 **https://estebanlab2021.github.io/inferencia_estadistica/**

## 💻 Uso local

```powershell
python -m http.server
```

Abrir <http://localhost:8000>. ⚠️ Debe servirse con un servidor local: Pyodide carga el núcleo Python vía `fetch`, por lo que **no funciona abriendo `index.html` directamente** (`file://`).

## 🛠️ Tecnologías

- HTML / CSS / JavaScript vanilla (sin instalaciones, sin paso de build)
- [Pyodide](https://pyodide.org/) 0.26.4 — Python 3.12 en WebAssembly
- [KaTeX](https://katex.org/) 0.16.11 — renderizado de LaTeX
- [Chart.js](https://www.chartjs.org/) 4.4.1 — gráficos
- [@sgratzl/chartjs-chart-boxplot](https://github.com/sgratzl/chartjs-chart-boxplot) 4.4.1 — boxplots

**Núcleo estadístico en Python puro** (`stats_core.py`): CDF e inversa de la normal (erf + bisección), t de Student y F de Fisher (beta incompleta regularizada + bisección) — implementado solo con `math` de la stdlib, **sin scipy**.

## 📁 Estructura del proyecto

```
inferencia/
├── index.html      # Interfaz (UI)
├── styles.css      # Estilos
├── app.js          # Puente DOM ⇄ Python (Pyodide) y gráficos
├── stats_core.py   # Núcleo estadístico (Python puro, sin DOM)
├── spec.md         # Especificación técnica detallada
└── AGENTS.md       # Notas de arquitectura y verificación
```

Arquitectura modular: el núcleo estadístico está separado de la capa de UI, de modo que agregar una prueba nueva no altera la estructura existente.

## ✅ Verificación

Los resultados están verificados contra los ejemplos resueltos del material de referencia (PDFs del curso y `formulas.md`). Algunos valores de control:

| Ejemplo | Resultado |
|---|---|
| Z (σ conocida): x̄=203.5, μ₀=200, σ=16, n=50 | Z = 1.55 |
| t (S_c): x̄=120, μ₀=100, S_c=15, n=7, α=0.10 derecha | t = 3.53, crítico 1.4398 |
| Proporción: p̂=0.775, P=0.8, n=2000 | Z = −2.80 |
| Dos medias (Z): (50,60), (12,16), (40,40) | Z = −3.16 |
| Dos medias (t, S_c): (20,16), (3,2), (10,5), α=0.10 | t = 2.67, crítico 1.7709 |
| ANOVA (Empleados 1–3) | SST=992, SSE=90, **F=49.6, p=1.3806·10⁻⁵**, F_crít(0.05; 2,9)=4.2565 → rechaza H₀ |

## 📖 Referencias

- Material del curso: *Hipótesis de una muestra*, *Hipótesis de 2 muestras*, *Anovas* y *formulas.md* (Prof. S. Araya Pizarro, U. de La Serena).
- ANOVA: H₀: μ₁ = μ₂ = … = μ_k; H₁: no todos los promedios son iguales. Decisión: rechazar H₀ si F > F_α(k−1, N−k).

---

*Proyecto estático desplegado con GitHub Pages. Para contribuir: abrir un issue o pull request.*
