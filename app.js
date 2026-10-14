/* app.js — DOM, carga de Pyodide y puente con stats_core.py */
"use strict";

const $ = (sel) => document.querySelector(sel);

let pyodide = null;
let chart = null;

/* Definición de cada test: inputs numericos y si maneja varianzas.
   Los ids de payload deben coincidir con los kwargs de stats_core.py. */
const TESTS = {
  una_media: {
    medios: true,
    inputs: [
      { id: "x_bar", label: "Media muestral (x̄)", value: "105.2", step: "any" },
      { id: "mu0", label: "Media hipotética (μ₀)", value: "100", step: "any" },
      { id: "n", label: "Tamaño de muestra (n)", value: "24", min: "1", step: "1" },
    ],
  },
  diferencia_medias: {
    medios: true,
    inputs: [
      { id: "x1", label: "Media muestra 1 (x̄₁)", value: "20", step: "any" },
      { id: "x2", label: "Media muestra 2 (x̄₂)", value: "16", step: "any" },
      { id: "n1", label: "Tamaño muestra 1 (n₁)", value: "10", min: "1", step: "1" },
      { id: "n2", label: "Tamaño muestra 2 (n₂)", value: "5", min: "1", step: "1" },
    ],
  },
  proporcion: {
    medios: false,
    inputs: [
      { id: "p_hat", label: "Proporción muestral (p̂)", value: "0.775", step: "any" },
      { id: "P0", label: "Proporción hipotética (P₀)", value: "0.8", step: "any" },
      { id: "n", label: "Tamaño de muestra (n)", value: "2000", min: "1", step: "1" },
    ],
  },
  diferencia_proporciones: {
    medios: false,
    inputs: [
      { id: "p1", label: "Proporción muestra 1 (p̂₁)", value: "0.5", step: "any" },
      { id: "p2", label: "Proporción muestra 2 (p̂₂)", value: "0.45", step: "any" },
      { id: "n1", label: "Tamaño muestra 1 (n₁)", value: "100", min: "1", step: "1" },
      { id: "n2", label: "Tamaño muestra 2 (n₂)", value: "120", min: "1", step: "1" },
    ],
  },
  anova: {
    anova: true,
  },
};

/* ---------- Inputs dinámicos de ANOVA ---------- */

/* Ejemplo por defecto: el de los PDFs (Empleado 1-3). */
function gruposPorDefecto() {
  return [
    { nombre: "Empleado 1", datos: [55, 54, 59, 56] },
    { nombre: "Empleado 2", datos: [66, 76, 67, 71] },
    { nombre: "Empleado 3", datos: [47, 51, 46, 48] },
  ];
}

/* Ultimo estado conocido de los grupos (sobrevive al cambiar k). */
let cacheGrupos = null;

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/* Lee los grupos del DOM (solo valores numericos completos). */
function leerGrupos() {
  const wrap = $("#grupos-panel");
  if (!wrap || !wrap.querySelector(".grupo")) {
    return cacheGrupos ? cacheGrupos : gruposPorDefecto();
  }
  const grupos = [];
  wrap.querySelectorAll(".grupo").forEach((el) => {
    const nombre = el.querySelector('input[type="text"]').value;
    const datos = Array.from(el.querySelectorAll(".valores input"))
      .map((inp) => parseFloat(inp.value))
      .filter((v) => Number.isFinite(v));
    grupos.push({ nombre, datos });
  });
  cacheGrupos = grupos;
  return grupos;
}

function valorInputHtml(j, valor) {
  return (
    '<input type="number" step="any" class="valor-input" ' +
    'placeholder="x' + (j + 1) + '" value="' + valor + '">'
  );
}

/* Actualiza el conteo n_i mostrado del grupo i. */
function actualizarNi(i) {
  const grupo = $('#grupos-panel .grupo[data-grupo="' + i + '"]');
  if (!grupo) return;
  const n = Array.from(grupo.querySelectorAll(".valores input"))
    .map((inp) => parseFloat(inp.value))
    .filter((v) => Number.isFinite(v)).length;
  grupo.querySelector(".ni-count").textContent = n;
}

function renderGrupos(k) {
  const wrap = $("#grupos-panel");
  const previos = leerGrupos();
  let html = "";
  for (let i = 0; i < k; i++) {
    const previo = previos[i] || null;
    const nombre = previo ? previo.nombre : "Tratamiento " + (i + 1);
    const datos = previo && previo.datos.length > 0 ? previo.datos : ["", ""];
    html +=
      '<div class="grupo" data-grupo="' + i + '">' +
      '<div class="grupo-header">' +
      '<div class="field grupo-nombre-field">' +
      '<label for="grupo-nombre-' + i + '">Tratamiento ' + (i + 1) + "</label>" +
      '<input id="grupo-nombre-' + i + '" type="text" value="' +
      escapeHtml(nombre) + '"></div>' +
      '<span class="ni-badge">n<sub>' + (i + 1) + " = " +
      '<span class="ni-count">' + (previo ? previo.datos.length : 0) +
      "</span></span></span>" +
      "</div>" +
      '<div class="valores">' +
      datos.map((v, j) => valorInputHtml(j, v)).join("") +
      "</div>" +
      '<div class="grupo-acciones">' +
      '<button type="button" class="btn-mini" data-accion="agregar" data-grupo="' + i +
      '">＋ Agregar valor</button>' +
      '<button type="button" class="btn-mini" data-accion="quitar" data-grupo="' + i + '"' +
      (datos.length <= 1 ? " disabled" : "") + ">− Quitar valor</button>" +
      "</div>" +
      "</div>";
  }
  wrap.innerHTML = html;

  /* Delegacion: botones +/− y conteo n_i en vivo al digitar. */
  wrap.addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-accion]");
    if (!btn || !wrap.contains(btn)) return;
    const i = parseInt(btn.dataset.grupo, 10);
    const grupoEl = wrap.querySelector('.grupo[data-grupo="' + i + '"]');
    const valores = grupoEl.querySelector(".valores");
    if (btn.dataset.accion === "agregar") {
      const j = valores.querySelectorAll("input").length;
      valores.insertAdjacentHTML("beforeend", valorInputHtml(j, ""));
    } else {
      const inputs = valores.querySelectorAll("input");
      if (inputs.length > 1) {
        inputs[inputs.length - 1].remove();
      }
    }
    const btnQuitar = grupoEl.querySelector('button[data-accion="quitar"]');
    if (btnQuitar) {
      btnQuitar.disabled = valores.querySelectorAll("input").length <= 1;
    }
    actualizarNi(i);
  });
  wrap.addEventListener("input", (e) => {
    if (e.target.matches(".valores input")) {
      const grupoEl = e.target.closest(".grupo");
      actualizarNi(parseInt(grupoEl.dataset.grupo, 10));
    }
  });
}

function renderInputsAnova(panel) {
  const k = cacheGrupos ? Math.max(cacheGrupos.length, 2) : 3;
  let opciones = "";
  for (let n = 2; n <= 8; n++) {
    opciones +=
      '<option value="' + n + '"' + (n === k ? " selected" : "") + ">" + n + "</option>";
  }
  panel.innerHTML =
    '<div class="field">' +
    '<label for="n-grupos">Número de tratamientos (k)</label>' +
    '<select id="n-grupos">' + opciones + "</select></div>" +
    '<p class="hint">Se carga el ejemplo de los PDFs (Empleado 1–3). ' +
    "Agrega o quita valores con los botones ＋/− de cada tratamiento; " +
    "n<sub>i</sub> se actualiza en vivo.</p>" +
    '<div id="grupos-panel"></div>';
  $("#n-grupos").addEventListener("change", (e) => {
    leerGrupos(); /* guarda en cache antes de re-renderizar */
    renderGrupos(parseInt(e.target.value, 10));
  });
  renderGrupos(k);
}

/* Campo de desviación estándar. La etiqueta cambia dinamamente
   entre la convencion S y la Sc (toggle). */
function sdField(id, labelS, labelSc, value) {
  return (
    '<div class="field"><label for="' + id + '">' +
    '<span class="sd-label" data-s="' + labelS + '" data-sc="' + labelSc + '">' +
    labelSc + "</span></label>" +
    '<input id="' + id + '" type="number" step="any" min="0.0000001" value="' + value + '">' +
    "</div>"
  );
}

function updateSdLabels() {
  const tipo = document.querySelector('input[name="tipo_sd"]:checked');
  if (!tipo) return;
  document.querySelectorAll(".sd-label").forEach((el) => {
    el.textContent = tipo.value === "S" ? el.dataset.s : el.dataset.sc;
  });
}

function renderInputs(testId) {
  const t = TESTS[testId];
  const panel = $("#inputs-panel");

  /* ANOVA tiene H1 fija ("no todos los promedios son iguales"):
     ocultar el panel de alternativas. */
  const alternativaPanel = $("#alternativa-panel");
  if (alternativaPanel) {
    alternativaPanel.style.display = testId === "anova" ? "none" : "";
  }

  if (testId === "anova") {
    renderInputsAnova(panel);
    return;
  }

  const uno = testId === "una_media";
  let html = "";

  if (t.medios) {
    html +=
      '<fieldset><legend>Varianza poblacional</legend>' +
      '<label><input type="radio" name="varianza" value="conocida"> Conocida (σ)</label>' +
      '<label><input type="radio" name="varianza" value="desconocida" checked> Desconocida (muestral)</label>' +
      "</fieldset>" +
      '<div id="var-conocida" class="var-bloque" hidden>' +
      (uno
        ? sdField("sd_c", "Desviación estándar poblacional (σ)", "Desviación estándar poblacional (σ)", "16")
        : sdField("sd1_c", "Desviación estándar poblacional 1 (σ₁)", "Desviación estándar poblacional 1 (σ₁)", "12") +
          sdField("sd2_c", "Desviación estándar poblacional 2 (σ₂)", "Desviación estándar poblacional 2 (σ₂)", "16")) +
      "</div>" +
      '<div id="var-desconocida" class="var-bloque">' +
      '<div class="sd-toggle" role="radiogroup" aria-label="Tipo de desviación estándar">' +
      '<input type="radio" name="tipo_sd" id="sd-s" value="S">' +
      '<label for="sd-s">S<span>Desv. estándar muestral<br>(varianza con n)</span></label>' +
      '<input type="radio" name="tipo_sd" id="sd-sc" value="Sc" checked>' +
      '<label for="sd-sc">S<sub>c</sub><span>Cuasidesv. / corregida<br>(varianza con n−1) · convención PDF</span></label>' +
      "</div>" +
      '<p class="hint">Ambas opciones son equivalentes con datos consistentes: ' +
      "S/√(n−1) = S<sub>c</sub>/√n. Por defecto se usa la convención de los PDFs (S<sub>c</sub>).</p>" +
      (uno
        ? sdField("sd_d", "Desviación estándar (S)", "Cuasidesviación estándar (S_c)", "15")
        : sdField("sd1_d", "Desviación estándar 1 (S₁)", "Cuasidesviación estándar 1 (S_c₁)", "3") +
          sdField("sd2_d", "Desviación estándar 2 (S₂)", "Cuasidesviación estándar 2 (S_c₂)", "2")) +
      "</div>";
  }

  html += t.inputs
    .map(
      (i) =>
        '<div class="field"><label for="' + i.id + '">' + i.label + "</label>" +
        '<input id="' + i.id + '" type="number" step="' + i.step + '"' +
        (i.min ? ' min="' + i.min + '"' : "") + ' value="' + i.value + '"></div>'
    )
    .join("");

  panel.innerHTML = html;

  panel.querySelectorAll('input[name="varianza"]').forEach((r) =>
    r.addEventListener("change", () => {
      const conocida =
        panel.querySelector('input[name="varianza"]:checked').value === "conocida";
      $("#var-conocida").hidden = !conocida;
      $("#var-desconocida").hidden = conocida;
    })
  );
  panel.querySelectorAll('input[name="tipo_sd"]').forEach((r) =>
    r.addEventListener("change", updateSdLabels)
  );
  updateSdLabels();
}

function gatherPayload(testId) {
  const t = TESTS[testId];
  const alpha = parseFloat($("#alpha").value);

  if (testId === "anova") {
    /* grupos: [{nombre, datos:[...]}] — coincide con el kwargs de
       test_anova() de stats_core.py */
    return { grupos: leerGrupos(), alpha };
  }

  const payload = {
    alpha: alpha,
    alternativa: document.querySelector('input[name="alternativa"]:checked').value,
  };
  t.inputs.forEach((i) => {
    payload[i.id] = parseFloat($("#" + i.id).value);
  });
  if (t.medios) {
    const conocida =
      document.querySelector('input[name="varianza"]:checked').value === "conocida";
    if (testId === "una_media") {
      payload.varianza_conocida = conocida;
      payload.sd = parseFloat($("#" + (conocida ? "sd_c" : "sd_d")).value);
    } else {
      payload.varianzas_conocidas = conocida;
      payload.sd1 = parseFloat($("#" + (conocida ? "sd1_c" : "sd1_d")).value);
      payload.sd2 = parseFloat($("#" + (conocida ? "sd2_c" : "sd2_d")).value);
    }
    // Con varianza conocida el tipo de SD es irrelevante para Python.
    payload.tipo_sd = conocida
      ? "Sc"
      : document.querySelector('input[name="tipo_sd"]:checked').value;
  }
  return payload;
}

/* ---------- Formateo de numeros para las tablas ---------- */

function fmtNum(x, dec) {
  dec = dec === undefined ? 4 : dec;
  if (x === 0) return "0";
  if (Math.abs(x) >= 1e6 || Math.abs(x) < 1e-4) return x.toExponential(2);
  return parseFloat(x.toFixed(dec)).toString();
}

function fmtP(p) {
  if (p === 0) return "0";
  if (p < 1e-4) return p.toExponential(4);
  return fmtNum(p, 4);
}

/* ---------- Resultados de ANOVA ---------- */

function renderAnovaResults(r) {
  const sec = $("#resultados");
  sec.hidden = false;

  $("#hipotesis").innerHTML =
    '<div class="bloque"><h3>Hipótesis</h3>' +
    "<p>$" + r.h0 + "$</p><p>$" + r.h1 + "$</p></div>";

  const L = r.latex;
  $("#paso-paso").innerHTML =
    '<div class="bloque"><h3>1. Fórmulas</h3><p>$$' + L.general + "$$</p></div>" +
    '<div class="bloque"><h3>2. Medias de los grupos y media global</h3><p>$$' +
    L.medios + "$$</p></div>" +
    '<div class="bloque"><h3>3. Suma de cuadrados entre grupos (SST)</h3><p>$$' +
    L.sst + "$$</p></div>" +
    '<div class="bloque"><h3>4. Suma de cuadrados dentro de los grupos (SSE)</h3><p>$$' +
    L.sse + "$$</p></div>" +
    '<div class="bloque"><h3>5. Estadístico F</h3><p>$$' + L.resultado + "$$</p></div>" +
    '<div class="bloque"><h3>6. p-valor y valor crítico</h3><p>$$' + L.p_valor +
    "$$</p><p>$$" + L.crit + "$$</p></div>";

  /* Tabla ANOVA (mismo formato que formulas.md / el PDF) */
  const filas = r.tabla
    .map((fila) => {
      const celdas = [
        "<td>" + fila.fuente + "</td>",
        "<td>" + fila.df + "</td>",
        "<td>" + fmtNum(fila.sc, 4) + "</td>",
        fila.cm !== undefined ? "<td>" + fmtNum(fila.cm, 4) + "</td>" : "<td></td>",
        fila.f !== undefined ? "<td>" + fmtNum(fila.f, 4) + "</td>" : "<td></td>",
        fila.p !== undefined ? "<td>" + fmtP(fila.p) + "</td>" : "<td></td>",
        fila.crit !== undefined
          ? "<td>" + fila.crit.toFixed(8) + "</td>"
          : "<td></td>",
      ];
      return "<tr>" + celdas.join("") + "</tr>";
    })
    .join("");
  $("#tabla-resultados").innerHTML =
    '<table class="tabla tabla-anova">' +
    "<thead><tr>" +
    "<th>Fuente de Variación</th>" +
    "<th>Grados de libertad (df)</th>" +
    "<th>Suma de cuadrados (SC)</th>" +
    "<th>Cuadrados medios (CM)</th>" +
    "<th>Estadístico F</th>" +
    "<th>p-value</th>" +
    "<th>Valor crítico para F</th>" +
    "</tr></thead><tbody>" + filas + "</tbody></table>" +
    '<p class="nota">' + r.nota + "</p>";

  /* Gráfico de F (curva + region de rechazo + F calculado) */
  renderChart(r);

  /* Boxplot de los grupos */
  $("#boxplot-wrap").hidden = false;
  renderBoxplot(r);

  $("#conclusion").textContent = r.conclusion;

  renderMathInElement(sec, {
    delimiters: [
      { left: "$$", right: "$$", display: true },
      { left: "$", right: "$", display: false },
    ],
    throwOnError: false,
  });
}

let boxplotChart = null;

/* Paleta de colores por tratamiento (cicla si k > 8). */
const PALETA = [
  { bg: "rgba(37, 99, 235, 0.45)", borde: "#2563eb" }, // azul
  { bg: "rgba(220, 38, 38, 0.45)", borde: "#dc2626" }, // rojo
  { bg: "rgba(22, 163, 74, 0.45)", borde: "#16a34a" }, // verde
  { bg: "rgba(234, 88, 12, 0.45)", borde: "#ea580c" }, // naranja
  { bg: "rgba(147, 51, 234, 0.45)", borde: "#9333ea" }, // morado
  { bg: "rgba(219, 39, 119, 0.45)", borde: "#db2777" }, // rosa
  { bg: "rgba(8, 145, 178, 0.45)", borde: "#0891b2" }, // cian
  { bg: "rgba(202, 138, 4, 0.45)", borde: "#ca8a04" }, // amarillo
];

function renderBoxplot(r) {
  const ctx = $("#grafico-boxplot");
  const errorEl = $("#boxplot-error");
  if (boxplotChart) {
    boxplotChart.destroy();
    boxplotChart = null;
  }
  errorEl.hidden = true;
  ctx.hidden = false;
  try {
    /* Colores por tratamiento: Chart.js resuelve arreglos
       indexables (un color por caja, bigotes y outliers). */
    const fondos = [];
    const bordes = [];
    const outliers = [];
    r.grupos.forEach((g, i) => {
      const c = PALETA[i % PALETA.length];
      fondos.push(c.bg);
      bordes.push(c.borde);
      outliers.push(c.borde);
    });
    boxplotChart = new Chart(ctx, {
      type: "boxplot",
      data: {
        labels: r.grupos.map((g) => g.nombre),
        datasets: [
          {
            label: "Observaciones",
            data: r.grupos.map((g) => g.datos),
            backgroundColor: fondos,
            borderColor: bordes,
            borderWidth: 1.5,
            outlierBackgroundColor: outliers,
            medianColor: "#1f2937",
            itemRadius: 3,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: true,
        aspectRatio: 2,
        animation: false,
        plugins: {
          legend: { display: false },
          tooltip: { enabled: true },
        },
        scales: {
          x: { title: { display: true, text: "Grupos / Tratamientos" } },
          y: { title: { display: true, text: "Valores" } },
        },
      },
    });
  } catch (err) {
    /* El plugin chartjs-chart-boxplot no está disponible */
    boxplotChart = null;
    ctx.hidden = true;
    errorEl.hidden = false;
  }
}

function validateNumerico(payload) {
  Object.entries(payload).forEach(([k, v]) => {
    if (typeof v === "number" && !Number.isFinite(v)) {
      throw new Error('Revisa los datos: «' + k + "» no es un número válido.");
    }
  });
}

async function calcular() {
  const testId = $("#test-selector").value;
  const errorDiv = $("#error");
  errorDiv.textContent = "";
  try {
    const payload = gatherPayload(testId);
    validateNumerico(payload);
    // El payload viaja como CADENA JSON (doble JSON.stringify): asi los
    // true/false de JS no se interpretan como literales de Python
    // (NameError: name 'true' is not defined) y json.loads() de
    // stats_core.py los convierte a True/False correctamente.
    const llamada =
      "ejecutar(" +
      JSON.stringify(testId) +
      ", " +
      JSON.stringify(JSON.stringify(payload)) +
      ")";
    const salida = pyodide.runPython(llamada);
    const r = JSON.parse(salida);
    if (testId === "anova") {
      renderAnovaResults(r);
    } else {
      renderResults(r);
    }
  } catch (e) {
    errorDiv.textContent = e.message || String(e);
    $("#resultados").hidden = true;
  }
}

function renderResults(r) {
  const sec = $("#resultados");
  sec.hidden = false;
  $("#boxplot-wrap").hidden = true;

  $("#hipotesis").innerHTML =
    '<div class="bloque"><h3>Hipótesis</h3>' +
    "<p>$" + r.h0 + "$</p><p>$" + r.h1 + "$</p></div>";

  const L = r.latex;
  $("#paso-paso").innerHTML =
    '<div class="bloque"><h3>1. Fórmula</h3><p>$$' + L.general + "$$</p></div>" +
    '<div class="bloque"><h3>2. Error estándar</h3><p>$$' + L.se + "$$</p></div>" +
    '<div class="bloque"><h3>3. Sustitución</h3><p>$$' + L.sustituida + "$$</p></div>" +
    '<div class="bloque"><h3>4. Resultado</h3><p>$$' + L.resultado + "$$</p></div>" +
    '<div class="bloque"><h3>5. p-valor</h3><p>$$' + L.p_valor + "$$</p></div>";

  const criticos = r.valores_criticos.map((c) => c.toFixed(4)).join("  /  ");
  const rechazar = r.decision === "rechazar";
  $("#tabla-resultados").innerHTML =
    '<table class="tabla">' +
    "<tr><td>Distribución</td><td>" + r.distribucion + (r.gl ? " (gl = " + r.gl + ")" : "") + "</td></tr>" +
    "<tr><td>Estadístico calculado</td><td>" + r.estadistico.toFixed(4) + "</td></tr>" +
    "<tr><td>p-valor</td><td>" + r.p_valor.toFixed(4) + "</td></tr>" +
    "<tr><td>Valor(es) crítico(s) (α = " + r.alpha + ")</td><td>" + criticos + "</td></tr>" +
    '<tr><td>Decisión</td><td class="' + (rechazar ? "decision-rechazar" : "decision-no") + '">' +
    (rechazar ? "Se rechaza H₀" : "No se rechaza H₀") + "</td></tr>" +
    "</table>" +
    '<p class="nota">' + r.nota + "</p>" +
    (r.advertencia ? '<p class="nota advertencia">' + r.advertencia + "</p>" : "");

  renderChart(r);
  $("#conclusion").textContent = r.conclusion;

  renderMathInElement(sec, {
    delimiters: [
      { left: "$$", right: "$$", display: true },
      { left: "$", right: "$", display: false },
    ],
    throwOnError: false,
  });
}

function renderChart(r) {
  const ctx = $("#grafico");
  if (chart) {
    chart.destroy();
    chart = null;
  }
  const xs = r.grafico.xs;
  const curva = r.grafico.curva;
  const region = r.grafico.region;
  const datosCurva = xs.map((x, i) => ({ x, y: curva[i] }));
  // NOTA: con datos {x, y} Chart.js NO acepta null (crashea con
  // "Cannot read properties of null (reading 'x')"); usa NaN para
  // los huecos, que la linea rompe y el relleno se hace por tramos.
  const datosRegion = xs.map((x, i) => ({
    x,
    y: region[i] == null ? NaN : region[i],
  }));
  const yMax = Math.max.apply(null, curva) * 1.15;

  const datasets = [
    {
      label: "Distribución",
      data: datosCurva,
      borderColor: "#2563eb",
      borderWidth: 2,
      pointRadius: 0,
      fill: false,
    },
    {
      label: "Región de rechazo",
      data: datosRegion,
      borderWidth: 0,
      pointRadius: 0,
      fill: "origin",
      backgroundColor: "rgba(220, 38, 38, 0.18)",
    },
  ];

  // Un dataset por valor critico (evita nulls para romper la linea).
  r.valores_criticos.forEach((c) => {
    datasets.push({
      label: "Valor(es) crítico(s)",
      data: [
        { x: c, y: 0 },
        { x: c, y: yMax },
      ],
      borderColor: "#dc2626",
      borderDash: [6, 4],
      borderWidth: 1.5,
      pointRadius: 0,
      fill: false,
    });
  });

  datasets.push({
    label: "Estadístico calculado",
    data: [
      { x: r.estadistico, y: 0 },
      { x: r.estadistico, y: yMax },
    ],
    borderColor: "#16a34a",
    borderWidth: 2,
    pointRadius: 0,
    fill: false,
  });

  chart = new Chart(ctx, {
    type: "line",
    data: { datasets },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      aspectRatio: 2,
      animation: false,
      spanGaps: false,
      plugins: {
        legend: {
          display: true,
          position: "bottom",
          labels: {
            boxWidth: 12,
            font: { size: 11 },
            // Evita etiquetas duplicadas (ej: dos valores criticos).
            filter: (item, data) =>
              data.datasets.findIndex((d) => d.label === item.text) ===
              item.datasetIndex,
          },
        },
        tooltip: { enabled: false },
      },
      scales: {
        x: {
          type: "linear",
          title: { display: true, text: r.eje_x || "Valor del estadístico" },
          ticks: { maxTicksLimit: 11 },
        },
        y: { display: false, min: 0 },
      },
    },
  });
}

async function init() {
  const loading = $("#loading");
  const btn = $("#calcular");
  try {
    loading.textContent = "Cargando motor estadístico (Python)…";
    pyodide = await loadPyodide({
      indexURL: "https://cdn.jsdelivr.net/pyodide/v0.26.4/full/",
    });
    /* ?v=2 bustea la cache del navegador: sin esto puede
       ejecutarse una version vieja de stats_core.py. */
    const resp = await fetch("stats_core.py?v=2");
    if (!resp.ok) {
      throw new Error(
        "No se pudo cargar stats_core.py (código HTTP " + resp.status + ")"
      );
    }
    await pyodide.runPython(await resp.text());
    loading.textContent = "Motor estadístico (Python) listo ✓";
    loading.classList.add("listo");
    btn.disabled = false;
  } catch (e) {
    loading.textContent = "Error al cargar Pyodide: " + e.message;
    loading.classList.add("error");
  }
}

document.addEventListener("DOMContentLoaded", () => {
  renderInputs($("#test-selector").value);
  $("#test-selector").addEventListener("change", (e) => {
    renderInputs(e.target.value);
    $("#resultados").hidden = true;
    $("#boxplot-wrap").hidden = true;
    $("#error").textContent = "";
  });
  $("#calcular").addEventListener("click", calcular);
  init();
});
