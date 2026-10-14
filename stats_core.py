# -*- coding: utf-8 -*-
"""Nucleo estadistico puro para la app de contrastes de hipotesis.

Solo usa la libreria estandar ``math`` (sin scipy): se ejecuta en Pyodide
sin instalar paquetes. Cada test publico recibe datos primitivos
(floats/ints) y retorna un dict serializable a JSON con el estadistico,
el p-valor, los valores criticos, las formulas LaTeX sustituidas y los
datos del grafico.

Convenciones (PDFs de referencia, Prof. S. Araya Pizarro, U. de La Serena):
- sigma conocida ................ Z = (X̄ - mu0) / (sigma / sqrt(n))
- sigma desconocida, convencion Sc (la del PDF):
      t = (X̄ - mu0) / (Sc / sqrt(n)),  gl = n - 1
- sigma desconocida, convencion S (varianza muestral con /n):
      t = (X̄ - mu0) / (S / sqrt(n-1))   [equivalente a la de arriba]
- Dos medias, varianzas desconocidas iguales, convencion Sc (la del PDF):
      Spc = sqrt(((n1-1)Sc1^2 + (n2-1)Sc2^2)/(n1+n2-2))
      t = (X̄1 - X̄2) / (Spc * sqrt(1/n1 + 1/n2)),  gl = n1+n2-2
- Dos medias, convencion S: Sp = sqrt((n1*S1^2 + n2*S2^2)/(n1+n2-2))
  [equivalente a la de arriba]
- Proporcion:        Z = (p̂ - P) / sqrt(P(1-P)/n)
- Dos proporciones:  Z = (p̂1 - p̂2) / sqrt(P̂*Q̂*(1/n1 + 1/n2)),
                     P̂ = (n1*p̂1 + n2*p̂2)/(n1+n2), Q̂ = 1 - P̂
- ANOVA de un factor: F = MST/MSE,  MST = SST/(k-1),  MSE = SSE/(N-k),
  SST = sum_i n_i*(x̄_i - x̄)^2,  SSE = sum_i sum_j (x_ij - x̄_i)^2,
  gl_entre = k-1,  gl_dentro = N-k.  Rechazar H₀ si F > F_α(k-1, N-k).

Regla de frontera del spec: n >= 30 -> Z (aproximacion); n < 30 -> t.
"""

import json
import math

# --------------------------------------------------------------------------
# Distribuciones (implementadas a mano, sin scipy)
# --------------------------------------------------------------------------


def normal_cdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def normal_ppf(p):
    """Inversa de la normal estandar por biseccion (p en (0,1))."""
    if not 0.0 < p < 1.0:
        raise ValueError("p debe estar en (0,1)")
    lo, hi = -10.0, 10.0
    for _ in range(200):
        mid = (lo + hi) / 2.0
        if normal_cdf(mid) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def _betacf(a, b, x):
    """Fraccion continua para la beta incompleta (Numerical Recipes)."""
    MAXIT = 300
    EPS = 3e-14
    FPMIN = 1e-300
    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < FPMIN:
        d = FPMIN
    d = 1.0 / d
    h = d
    for m in range(1, MAXIT + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < FPMIN:
            d = FPMIN
        c = 1.0 + aa / c
        if abs(c) < FPMIN:
            c = FPMIN
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < FPMIN:
            d = FPMIN
        c = 1.0 + aa / c
        if abs(c) < FPMIN:
            c = FPMIN
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < EPS:
            break
    return h


def _beta_reg(a, b, x):
    """Beta incompleta regularizada I_x(a, b)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lbeta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    front = math.exp(lbeta + a * math.log(x) + b * math.log(1.0 - x))
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1.0 - x) / b


def t_cdf(t, df):
    """CDF de Student-t."""
    x = df / (df + t * t)
    ib = _beta_reg(df / 2.0, 0.5, x)
    if t > 0.0:
        return 1.0 - 0.5 * ib
    return 0.5 * ib


def t_ppf(p, df):
    """Inversa de la t de Student por biseccion (p en (0,1))."""
    if not 0.0 < p < 1.0:
        raise ValueError("p debe estar en (0,1)")
    lo, hi = -1e4, 1e4
    for _ in range(200):
        mid = (lo + hi) / 2.0
        if t_cdf(mid, df) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def _normal_pdf(x):
    return math.exp(-x * x / 2.0) / math.sqrt(2.0 * math.pi)


def _t_pdf(x, df):
    coef = math.exp(math.lgamma((df + 1.0) / 2.0) - math.lgamma(df / 2.0))
    return coef / math.sqrt(df * math.pi) * (1.0 + x * x / df) ** (-(df + 1.0) / 2.0)


# --------------------------------------------------------------------------
# Distribucion F (para ANOVA)
# --------------------------------------------------------------------------


def f_cdf(x, d1, d2):
    """CDF de la distribucion F de Fisher."""
    if x <= 0.0:
        return 0.0
    z = d1 * x / (d1 * x + d2)
    return _beta_reg(d1 / 2.0, d2 / 2.0, z)


def f_ppf(p, d1, d2):
    """Inversa de la F por biseccion: retorna x con P(F <= x) = p."""
    if not 0.0 < p < 1.0:
        raise ValueError("p debe estar en (0,1)")
    lo, hi = 0.0, 1e7
    for _ in range(300):
        mid = (lo + hi) / 2.0
        if f_cdf(mid, d1, d2) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def _f_pdf(x, d1, d2):
    """Densidad de la F (calculada en logaritmos para estabilidad)."""
    if x <= 0.0:
        return 0.0
    a = d1 / 2.0
    b = d2 / 2.0
    ln_b = math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)
    ln_f = (
        0.5
        * (
            d1 * math.log(d1 * x)
            + d2 * math.log(d2)
            - (d1 + d2) * math.log(d1 * x + d2)
        )
        - math.log(x)
        - ln_b
    )
    return math.exp(ln_f)


# --------------------------------------------------------------------------
# Utilidades
# --------------------------------------------------------------------------


def _fmt(x, dec=4):
    """Formatea un numero para LaTeX: sin ceros finales, punto decimal."""
    x = float(x)
    if abs(x) < 5e-5:
        return "0"
    if x == int(x) and abs(x) < 1e15:
        return f"{x:.0f}"
    s = f"{x:.{dec}f}".rstrip("0").rstrip(".")
    return s if s not in ("", "-") else "0"


def _fmt_es(x, dec=4):
    """Formatea un numero para texto en espanol (coma decimal, como los PDF)."""
    return _fmt(x, dec).replace(".", ",")


def _fmt_p(x):
    """Formatea p-valores: notacion cientifica LaTeX para valores pequenos."""
    if x == 0.0:
        return "0"
    if x < 1e-4:
        s = f"{x:.2e}"  # p. ej. "1.38e-05"
        mant, exp = s.split("e")
        return mant + " \\cdot 10^{" + str(int(exp)) + "}"
    return _fmt(x)


def _validar_alpha(alpha):
    alpha = float(alpha)
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha debe estar entre 0 y 1")
    return alpha


def _validar_alternativa(alternativa):
    if alternativa not in ("bilateral", "derecha", "izquierda"):
        raise ValueError("alternativa debe ser bilateral, derecha o izquierda")
    return alternativa


def _crit_pvalor(dist, gl, estadistico, alternativa, alpha):
    """Retorna (valores_criticos, p_valor, simbolo_latex) segun la alternativa."""
    if dist == "Z":
        cdf, ppf = normal_cdf, normal_ppf
        simb = "Z"
    else:
        cdf = lambda v: t_cdf(v, gl)
        ppf = lambda p: t_ppf(p, gl)
        simb = "t_{" + str(int(gl)) + "}"
    if alternativa == "bilateral":
        c = ppf(1.0 - alpha / 2.0)
        criticos = [-c, c]
        p = 2.0 * (1.0 - cdf(abs(estadistico)))
    elif alternativa == "derecha":
        c = ppf(1.0 - alpha)
        criticos = [c]
        p = 1.0 - cdf(estadistico)
    else:  # izquierda
        c = ppf(alpha)
        criticos = [c]
        p = cdf(estadistico)
    return criticos, p, simb


def _decision(alternativa, estadistico, criticos):
    if alternativa == "bilateral":
        return abs(estadistico) > abs(criticos[0])
    if alternativa == "derecha":
        return estadistico > criticos[0]
    return estadistico < criticos[0]


def _grafico(dist, gl, estadistico, criticos, alternativa):
    """Curva de la distribucion y region de rechazo (null fuera de ella)."""
    if dist == "Z":

        def pdf(v):
            return _normal_pdf(v)

    else:

        def pdf(v):
            return _t_pdf(v, gl)

    maxv = max([abs(c) for c in criticos] + [abs(estadistico)])
    pad = max(0.75, 0.2 * maxv)
    lo, hi = -(maxv + pad), maxv + pad
    N = 240
    xs, curva, region = [], [], []
    for i in range(N + 1):
        x = lo + (hi - lo) * i / N
        y = pdf(x)
        if alternativa == "bilateral":
            dentro = x <= criticos[0] or x >= criticos[1]
        elif alternativa == "derecha":
            dentro = x >= criticos[0]
        else:
            dentro = x <= criticos[0]
        xs.append(round(x, 4))
        curva.append(round(y, 6))
        region.append(round(y, 6) if dentro else None)
    return {"xs": xs, "curva": curva, "region": region}


def _grafico_f(f_est, f_crit, d1, d2):
    """Curva F y region de rechazo (siempre cola derecha: F > Fc)."""
    maxv = max(f_est, f_crit)
    hi = maxv * 1.25 + 1.0
    N = 240
    xs, curva, region = [], [], []
    for i in range(N + 1):
        x = hi * i / N
        y = _f_pdf(x, d1, d2)
        xs.append(round(x, 4))
        curva.append(round(y, 6))
        region.append(round(y, 6) if x >= f_crit else None)
    return {"xs": xs, "curva": curva, "region": region}


def _hipotesis(mu0, alternativa, dos_muestras=False, proporcion=False):
    """Retorna (h0, h1) en LaTeX segun la alternativa."""
    if dos_muestras:
        h0 = r"H_{0}: \mu_{1} - \mu_{2} = 0"
        base = r"H_{1}: \mu_{1} - \mu_{2}"
        if alternativa == "bilateral":
            h1 = base + r" \neq 0"
        elif alternativa == "derecha":
            h1 = base + r" > 0"
        else:
            h1 = base + r" < 0"
    elif proporcion:
        h0 = "H_{0}: p = " + _fmt(mu0)
        base = r"H_{1}: p"
        if alternativa == "bilateral":
            h1 = base + r" \neq " + _fmt(mu0)
        elif alternativa == "derecha":
            h1 = base + r" > " + _fmt(mu0)
        else:
            h1 = base + r" < " + _fmt(mu0)
    else:
        h0 = r"H_{0}: \mu = " + _fmt(mu0)
        base = r"H_{1}: \mu"
        if alternativa == "bilateral":
            h1 = base + r" \neq " + _fmt(mu0)
        elif alternativa == "derecha":
            h1 = base + r" > " + _fmt(mu0)
        else:
            h1 = base + r" < " + _fmt(mu0)
    return h0, h1


def _pvalor_latex(simb, estadistico, alternativa, p):
    if alternativa == "bilateral":
        return (
            "p = 2 \\cdot P(" + simb + " > |" + _fmt(estadistico) + "|) = " + _fmt(p)
        )
    if alternativa == "derecha":
        return (
            "p = P(" + simb + " > " + _fmt(estadistico) + ") = " + _fmt(p)
        )
    return "p = P(" + simb + " < " + _fmt(estadistico) + ") = " + _fmt(p)


def _conclusion(alternativa, rechazar, estadistico, criticos, alpha, tema):
    if alternativa == "bilateral":
        comp = "|" + _fmt_es(estadistico) + "| " + (">" if rechazar else "≤") + " |" + _fmt_es(criticos[0]) + "|"
        efecto = tema["bilateral"]
    elif alternativa == "derecha":
        comp = _fmt_es(estadistico) + " " + (">" if rechazar else "≤") + " " + _fmt_es(criticos[0])
        efecto = tema["derecha"]
    else:
        comp = _fmt_es(estadistico) + " " + ("<" if rechazar else "≥") + " " + _fmt_es(criticos[0])
        efecto = tema["izquierda"]
    if rechazar:
        return (
            "Con α = " + _fmt_es(alpha) + " se rechaza H₀ (" + comp + "): "
            "la evidencia indica que " + efecto + "."
        )
    return (
        "Con α = " + _fmt_es(alpha) + " no se rechaza H₀ (" + comp + "): "
        "la evidencia no indica que " + efecto + "."
    )


# --------------------------------------------------------------------------
# Tests publicos (reciben primitivos, retornan dict serializable)
# --------------------------------------------------------------------------


def test_una_media(x_bar, mu0, sd, n, varianza_conocida, tipo_sd, alpha, alternativa):
    """Contraste para una media poblacional."""
    n = int(n)
    alpha = _validar_alpha(alpha)
    alternativa = _validar_alternativa(alternativa)
    if n < 1:
        raise ValueError("n debe ser ≥ 1")
    if sd <= 0:
        raise ValueError("La desviación estándar debe ser positiva")
    if not varianza_conocida and n < 2:
        raise ValueError("Con varianza desconocida se requiere n ≥ 2")

    # Error estandar segun la convencion elegida (S/√(n-1) ≡ Sc/√n)
    if varianza_conocida:
        se = sd / math.sqrt(n)
        dist, gl = "Z", None
        se_latex = (
            "SE = \\frac{\\sigma}{\\sqrt{n}} = \\frac{" + _fmt(sd)
            + "}{\\sqrt{" + _fmt(n) + "}} = " + _fmt(se)
        )
        nota = "σ conocida → distribución normal estándar (Z)"
    else:
        if tipo_sd == "S":
            se = sd / math.sqrt(n - 1)
            se_latex = (
                "SE = \\frac{S}{\\sqrt{n-1}} = \\frac{" + _fmt(sd)
                + "}{\\sqrt{" + _fmt(n - 1) + "}} = " + _fmt(se)
            )
        else:  # Sc: convencion del PDF
            se = sd / math.sqrt(n)
            se_latex = (
                "SE = \\frac{S_{c}}{\\sqrt{n}} = \\frac{" + _fmt(sd)
                + "}{\\sqrt{" + _fmt(n) + "}} = " + _fmt(se)
            )
        if n >= 30:
            dist, gl = "Z", None
            nota = (
                "n = " + str(n) + " ≥ 30 → aproximación Z "
                "(la t de Student tiende a la normal)"
            )
        else:
            dist, gl = "t", n - 1
            nota = (
                "n = " + str(n) + " < 30 y σ desconocida → distribución t "
                "de Student (gl = " + str(n - 1) + ")"
            )

    estadistico = (x_bar - mu0) / se
    criticos, p_valor, simb = _crit_pvalor(dist, gl, estadistico, alternativa, alpha)
    rechazar = _decision(alternativa, estadistico, criticos)

    h0, h1 = _hipotesis(mu0, alternativa)
    general = dist + r" = \frac{\bar{X} - \mu_{0}}{S / \sqrt{n-1}}"
    if varianza_conocida:
        general = dist + r" = \frac{\bar{X} - \mu_{0}}{\sigma / \sqrt{n}}"
    elif tipo_sd == "Sc":
        general = dist + r" = \frac{\bar{X} - \mu_{0}}{S_{c} / \sqrt{n}}"
    k = n if (varianza_conocida or tipo_sd == "Sc") else n - 1
    sustituida = (
        dist + " = \\frac{" + _fmt(x_bar) + " - " + _fmt(mu0) + "}{"
        + _fmt(sd) + " / \\sqrt{" + _fmt(k) + "}} = " + _fmt(estadistico)
    )
    resultado = dist + " = " + _fmt(estadistico)

    return {
        "test": "una_media",
        "distribucion": dist,
        "gl": gl,
        "estadistico": estadistico,
        "p_valor": p_valor,
        "valores_criticos": criticos,
        "alpha": alpha,
        "alternativa": alternativa,
        "h0": h0,
        "h1": h1,
        "decision": "rechazar" if rechazar else "no_rechazar",
        "conclusion": _conclusion(
            alternativa,
            rechazar,
            estadistico,
            criticos,
            alpha,
            {
                "bilateral": "la media poblacional es diferente de " + _fmt_es(mu0),
                "derecha": "la media poblacional es superior a " + _fmt_es(mu0),
                "izquierda": "la media poblacional es inferior a " + _fmt_es(mu0),
            },
        ),
        "nota": nota,
        "latex": {
            "general": general,
            "se": se_latex,
            "sustituida": sustituida,
            "resultado": resultado,
            "p_valor": _pvalor_latex(simb, estadistico, alternativa, p_valor),
        },
        "grafico": _grafico(dist, gl, estadistico, criticos, alternativa),
    }


def test_diferencia_medias(x1, x2, sd1, sd2, n1, n2, varianzas_conocidas, tipo_sd, alpha, alternativa):
    """Contraste para la diferencia de dos medias (muestras independientes,
    varianzas desconocidas asumidas iguales)."""
    n1, n2 = int(n1), int(n2)
    alpha = _validar_alpha(alpha)
    alternativa = _validar_alternativa(alternativa)
    if n1 < 1 or n2 < 1:
        raise ValueError("n₁ y n₂ deben ser ≥ 1")
    if sd1 <= 0 or sd2 <= 0:
        raise ValueError("Las desviaciones estándar deben ser positivas")
    if not varianzas_conocidas and (n1 < 2 or n2 < 2):
        raise ValueError("Con varianzas desconocidas se requiere n₁, n₂ ≥ 2")

    raiz = "\\sqrt{\\frac{1}{" + _fmt(n1) + "} + \\frac{1}{" + _fmt(n2) + "}}"

    if varianzas_conocidas:
        se = math.sqrt(sd1 * sd1 / n1 + sd2 * sd2 / n2)
        se_latex = (
            "SE = \\sqrt{\\frac{" + _fmt(sd1) + "^{2}}{" + _fmt(n1) + "} + \\frac{"
            + _fmt(sd2) + "^{2}}{" + _fmt(n2) + "}} = " + _fmt(se)
        )
        dist, gl = "Z", None
        nota = "Varianzas poblacionales conocidas → distribución normal estándar (Z)"
    else:
        if tipo_sd == "S":
            sp = math.sqrt((n1 * sd1 * sd1 + n2 * sd2 * sd2) / (n1 + n2 - 2))
            sp_latex = (
                "S_{p} = \\sqrt{\\frac{n_{1} S_{1}^{2} + n_{2} S_{2}^{2}}{n_{1} + n_{2} - 2}}"
                " = \\sqrt{\\frac{" + _fmt(n1) + " \\cdot " + _fmt(sd1) + "^{2} + "
                + _fmt(n2) + " \\cdot " + _fmt(sd2) + "^{2}}{" + _fmt(n1 + n2 - 2)
                + "}} = " + _fmt(sp)
            )
        else:  # Sc: convencion del PDF
            sp = math.sqrt(((n1 - 1) * sd1 * sd1 + (n2 - 1) * sd2 * sd2) / (n1 + n2 - 2))
            sp_latex = (
                "S_{pc} = \\sqrt{\\frac{(n_{1}-1) S_{c1}^{2} + (n_{2}-1) S_{c2}^{2}}{n_{1} + n_{2} - 2}}"
                " = \\sqrt{\\frac{" + _fmt(n1 - 1) + " \\cdot " + _fmt(sd1) + "^{2} + "
                + _fmt(n2 - 1) + " \\cdot " + _fmt(sd2) + "^{2}}{" + _fmt(n1 + n2 - 2)
                + "}} = " + _fmt(sp)
            )
        se = sp * math.sqrt(1.0 / n1 + 1.0 / n2)
        se_latex = (
            sp_latex + ", \\quad SE = " + _fmt(sp) + " \\cdot " + raiz + " = " + _fmt(se)
        )
        if n1 >= 30 and n2 >= 30:
            dist, gl = "Z", None
            nota = (
                "n₁ = " + str(n1) + ", n₂ = " + str(n2) + " ≥ 30 → aproximación Z "
                "(la t de Student tiende a la normal)"
            )
        else:
            dist, gl = "t", n1 + n2 - 2
            nota = (
                "n₁ = " + str(n1) + ", n₂ = " + str(n2) + " < 30 y varianzas desconocidas → "
                "distribución t de Student (gl = " + str(n1 + n2 - 2) + ")"
            )

    estadistico = (x1 - x2) / se
    criticos, p_valor, simb = _crit_pvalor(dist, gl, estadistico, alternativa, alpha)
    rechazar = _decision(alternativa, estadistico, criticos)

    if varianzas_conocidas:
        general = (
            r"Z = \frac{\bar{X}_{1} - \bar{X}_{2}}"
            r"{\sqrt{\frac{\sigma_{1}^{2}}{n_{1}} + \frac{\sigma_{2}^{2}}{n_{2}}}}"
        )
        sustituida = (
            "Z = \\frac{" + _fmt(x1) + " - " + _fmt(x2) + "}{\\sqrt{\\frac{"
            + _fmt(sd1) + "^{2}}{" + _fmt(n1) + "} + \\frac{" + _fmt(sd2) + "^{2}}{"
            + _fmt(n2) + "}}} = " + _fmt(estadistico)
        )
    else:
        general = (
            r"t = \frac{\bar{X}_{1} - \bar{X}_{2}}{S_{pc} \sqrt{\frac{1}{n_{1}} + \frac{1}{n_{2}}}}"
            if tipo_sd == "Sc"
            else r"t = \frac{\bar{X}_{1} - \bar{X}_{2}}{S_{p} \sqrt{\frac{1}{n_{1}} + \frac{1}{n_{2}}}}"
        )
        sustituida = (
            "t = \\frac{" + _fmt(x1) + " - " + _fmt(x2) + "}{" + _fmt(sp)
            + " \\cdot " + raiz + "} = " + _fmt(estadistico)
        )

    h0, h1 = _hipotesis(0, alternativa, dos_muestras=True)
    resultado = dist + " = " + _fmt(estadistico)

    return {
        "test": "diferencia_medias",
        "distribucion": dist,
        "gl": gl,
        "estadistico": estadistico,
        "p_valor": p_valor,
        "valores_criticos": criticos,
        "alpha": alpha,
        "alternativa": alternativa,
        "h0": h0,
        "h1": h1,
        "decision": "rechazar" if rechazar else "no_rechazar",
        "conclusion": _conclusion(
            alternativa,
            rechazar,
            estadistico,
            criticos,
            alpha,
            {
                "bilateral": "las medias poblacionales difieren (μ₁ ≠ μ₂)",
                "derecha": "la media poblacional 1 es mayor que la 2 (μ₁ > μ₂)",
                "izquierda": "la media poblacional 1 es menor que la 2 (μ₁ < μ₂)",
            },
        ),
        "nota": nota,
        "latex": {
            "general": general,
            "se": se_latex,
            "sustituida": sustituida,
            "resultado": resultado,
            "p_valor": _pvalor_latex(simb, estadistico, alternativa, p_valor),
        },
        "grafico": _grafico(dist, gl, estadistico, criticos, alternativa),
    }


def test_proporcion(p_hat, P0, n, alpha, alternativa):
    """Contraste para una proporcion poblacional (aproximacion normal)."""
    n = int(n)
    alpha = _validar_alpha(alpha)
    alternativa = _validar_alternativa(alternativa)
    if n < 1:
        raise ValueError("n debe ser ≥ 1")
    if not 0.0 < P0 < 1.0:
        raise ValueError("La proporción hipotética P₀ debe estar entre 0 y 1")
    if not 0.0 <= p_hat <= 1.0:
        raise ValueError("La proporción muestral p̂ debe estar entre 0 y 1")

    se = math.sqrt(P0 * (1.0 - P0) / n)
    estadistico = (p_hat - P0) / se
    criticos, p_valor, simb = _crit_pvalor("Z", None, estadistico, alternativa, alpha)
    rechazar = _decision(alternativa, estadistico, criticos)

    h0, h1 = _hipotesis(P0, alternativa, proporcion=True)
    advertencia = None
    if n * P0 * (1.0 - P0) < 5:
        advertencia = (
            "Nota: n·P₀·(1−P₀) = " + _fmt_es(n * P0 * (1 - P0), 2) + " < 5; "
            "la aproximación normal suele requerir n·P₀·(1−P₀) ≥ 5"
        )

    return {
        "test": "proporcion",
        "distribucion": "Z",
        "gl": None,
        "estadistico": estadistico,
        "p_valor": p_valor,
        "valores_criticos": criticos,
        "alpha": alpha,
        "alternativa": alternativa,
        "h0": h0,
        "h1": h1,
        "decision": "rechazar" if rechazar else "no_rechazar",
        "conclusion": _conclusion(
            alternativa,
            rechazar,
            estadistico,
            criticos,
            alpha,
            {
                "bilateral": "la proporción poblacional es diferente de " + _fmt_es(P0),
                "derecha": "la proporción poblacional es superior a " + _fmt_es(P0),
                "izquierda": "la proporción poblacional es inferior a " + _fmt_es(P0),
            },
        ),
        "nota": "Proporciones → aproximación normal estándar (Z)",
        "advertencia": advertencia,
        "latex": {
            "general": r"Z = \frac{\hat{p} - P}{\sqrt{\frac{P(1-P)}{n}}}",
            "se": (
                "SE = \\sqrt{\\frac{P(1-P)}{n}} = \\sqrt{\\frac{" + _fmt(P0)
                + " \\cdot " + _fmt(1 - P0) + "}{" + _fmt(n) + "}} = " + _fmt(se)
            ),
            "sustituida": (
                "Z = \\frac{" + _fmt(p_hat) + " - " + _fmt(P0) + "}{\\sqrt{\\frac{"
                + _fmt(P0) + " \\cdot " + _fmt(1 - P0) + "}{" + _fmt(n) + "}}} = "
                + _fmt(estadistico)
            ),
            "resultado": "Z = " + _fmt(estadistico),
            "p_valor": _pvalor_latex(simb, estadistico, alternativa, p_valor),
        },
        "grafico": _grafico("Z", None, estadistico, criticos, alternativa),
    }


def test_diferencia_proporciones(p1, p2, n1, n2, alpha, alternativa):
    """Contraste para la diferencia de dos proporciones (aproximacion normal,
    proporcion agrupada bajo H₀)."""
    n1, n2 = int(n1), int(n2)
    alpha = _validar_alpha(alpha)
    alternativa = _validar_alternativa(alternativa)
    if n1 < 1 or n2 < 1:
        raise ValueError("n₁ y n₂ deben ser ≥ 1")
    if not 0.0 <= p1 <= 1.0 or not 0.0 <= p2 <= 1.0:
        raise ValueError("Las proporciones muestrales deben estar entre 0 y 1")

    P = (n1 * p1 + n2 * p2) / (n1 + n2)
    Q = 1.0 - P
    se = math.sqrt(P * Q * (1.0 / n1 + 1.0 / n2))
    estadistico = (p1 - p2) / se
    criticos, p_valor, simb = _crit_pvalor("Z", None, estadistico, alternativa, alpha)
    rechazar = _decision(alternativa, estadistico, criticos)

    h0, h1 = _hipotesis(0, alternativa, dos_muestras=True)

    return {
        "test": "diferencia_proporciones",
        "distribucion": "Z",
        "gl": None,
        "estadistico": estadistico,
        "p_valor": p_valor,
        "valores_criticos": criticos,
        "alpha": alpha,
        "alternativa": alternativa,
        "h0": h0,
        "h1": h1,
        "decision": "rechazar" if rechazar else "no_rechazar",
        "conclusion": _conclusion(
            alternativa,
            rechazar,
            estadistico,
            criticos,
            alpha,
            {
                "bilateral": "las proporciones poblacionales difieren (p₁ ≠ p₂)",
                "derecha": "la proporción poblacional 1 es mayor que la 2 (p₁ > p₂)",
                "izquierda": "la proporción poblacional 1 es menor que la 2 (p₁ < p₂)",
            },
        ),
        "nota": "Diferencia de proporciones → aproximación normal estándar (Z), proporción agrupada bajo H₀",
        "advertencia": None,
        "latex": {
            "general": (
                r"Z = \frac{\hat{p}_{1} - \hat{p}_{2}}{\sqrt{\hat{P}\hat{Q}\left(\frac{1}{n_{1}} + \frac{1}{n_{2}}\right)}}, \quad \hat{P} = \frac{n_{1}\hat{p}_{1} + n_{2}\hat{p}_{2}}{n_{1} + n_{2}}"
            ),
            "se": (
                "\\hat{P} = \\frac{" + _fmt(n1) + " \\cdot " + _fmt(p1) + " + "
                + _fmt(n2) + " \\cdot " + _fmt(p2) + "}{" + _fmt(n1 + n2) + "} = " + _fmt(P)
                + ", \\quad SE = \\sqrt{\\hat{P}\\hat{Q}\\left(\\frac{1}{n_{1}} + \\frac{1}{n_{2}}\\right)} = \\sqrt{"
                + _fmt(P) + " \\cdot " + _fmt(Q) + " \\cdot \\left(\\frac{1}{" + _fmt(n1)
                + "} + \\frac{1}{" + _fmt(n2) + "}\\right)} = " + _fmt(se)
            ),
            "sustituida": (
                "Z = \\frac{" + _fmt(p1) + " - " + _fmt(p2) + "}{\\sqrt{" + _fmt(P)
                + " \\cdot " + _fmt(Q) + " \\cdot \\left(\\frac{1}{" + _fmt(n1)
                + "} + \\frac{1}{" + _fmt(n2) + "}\\right)}} = " + _fmt(estadistico)
            ),
            "resultado": "Z = " + _fmt(estadistico),
            "p_valor": _pvalor_latex(simb, estadistico, alternativa, p_valor),
        },
        "grafico": _grafico("Z", None, estadistico, criticos, alternativa),
    }


def test_anova(grupos, alpha):
    """ANOVA de un factor.

    H0: los promedios de todos los grupos son iguales.
    H1: no todos los promedios son iguales.
    Rechazar H0 si F = MST/MSE > F_alpha(k-1, N-k).

    ``grupos`` es una lista de dicts {"nombre": str, "datos": [numeros]}.
    """
    alpha = _validar_alpha(alpha)
    if not isinstance(grupos, list) or len(grupos) < 2:
        raise ValueError("Se requieren al menos 2 grupos")

    nombres, datos = [], []
    for g in grupos:
        nombre = str(g.get("nombre", "")).strip()
        vals = [float(v) for v in g.get("datos", [])]
        if not vals:
            raise ValueError("Cada grupo debe tener al menos un valor")
        nombres.append(nombre or "Grupo")
        datos.append(vals)

    k = len(datos)
    ns = [len(d) for d in datos]
    N = sum(ns)
    if N - k < 1:
        raise ValueError(
            "Se requiere más observaciones que grupos (N > k): "
            "al menos un grupo debe tener 2 o más valores"
        )

    medias = [sum(d) / n for d, n in zip(datos, ns)]
    media_global = sum(sum(d) for d in datos) / N

    # SST: variacion entre grupos (tratamientos)
    sst = sum(n * (m - media_global) ** 2 for n, m in zip(ns, medias))
    # SSE: variacion dentro de los grupos (error)
    sse_grupos = [
        sum((x - m) ** 2 for x in d) for d, m in zip(datos, medias)
    ]
    sse = sum(sse_grupos)
    total = sst + sse

    df_entre = k - 1
    df_dentro = N - k
    df_total = N - 1
    mst = sst / df_entre
    mse = sse / df_dentro
    f_est = mst / mse

    p_valor = 1.0 - f_cdf(f_est, df_entre, df_dentro)
    f_crit = f_ppf(1.0 - alpha, df_entre, df_dentro)
    rechazar = f_est > f_crit

    # --- LaTeX ---
    h0 = (
        r"H_{0}: \mu_{1} = \mu_{2} = \cdots = \mu_{" + str(k) + "}"
    )
    h1 = r"H_{1}: \text{No todos los promedios son iguales}"

    general = (
        r"SST = \sum_{i=1}^{k} n_{i} (\bar{x}_{i} - \bar{x})^{2}, \quad "
        r"SSE = \sum_{i=1}^{k} \sum_{j=1}^{n_{i}} (x_{ij} - \bar{x}_{i})^{2}"
    )
    medios_latex = (
        ", \\quad ".join(
            "\\bar{x}_{" + str(i + 1) + "} = " + _fmt(m)
            for i, m in enumerate(medias)
        )
        + ", \\quad \\bar{x} = "
        + _fmt(media_global)
    )
    sst_latex = (
        "SST = "
        + " + ".join(
            _fmt(n) + " \\cdot (" + _fmt(m) + " - " + _fmt(media_global) + ")^{2}"
            for n, m in zip(ns, medias)
        )
        + " = "
        + _fmt(sst)
    )
    sse_latex = (
        "SSE = " + " + ".join(_fmt(v) for v in sse_grupos) + " = " + _fmt(sse)
    )
    resultado = (
        "F = \\frac{MST}{MSE} = \\frac{" + _fmt(mst) + "}{" + _fmt(mse)
        + "} = " + _fmt(f_est)
    )
    simb = "F_{" + str(df_entre) + "," + str(df_dentro) + "}"
    p_latex = (
        "p = P(" + simb + " > " + _fmt(f_est) + ") = " + _fmt_p(p_valor)
    )
    crit_latex = (
        "F_{\\alpha}({" + str(df_entre) + "," + str(df_dentro)
        + "}) = " + _fmt(f_crit)
    )

    if rechazar:
        conclusion = (
            "Con α = " + _fmt_es(alpha) + " se rechaza H₀ (F = "
            + _fmt_es(f_est) + " > F_crít = " + _fmt_es(f_crit)
            + "): la evidencia indica que no todos los promedios son iguales "
            "(existe diferencia entre los grupos)."
        )
    else:
        conclusion = (
            "Con α = " + _fmt_es(alpha) + " no se rechaza H₀ (F = "
            + _fmt_es(f_est) + " ≤ F_crít = " + _fmt_es(f_crit)
            + "): la evidencia no indica diferencias entre los promedios "
            "de los grupos."
        )

    return {
        "test": "anova",
        "distribucion": "F",
        "gl": None,
        "estadistico": f_est,
        "p_valor": p_valor,
        "valores_criticos": [f_crit],
        "alpha": alpha,
        "alternativa": "anova",
        "h0": h0,
        "h1": h1,
        "decision": "rechazar" if rechazar else "no_rechazar",
        "conclusion": conclusion,
        "nota": (
            "ANOVA de un factor: F = MST/MSE con gl = (" + str(df_entre)
            + ", " + str(df_dentro) + "). Rechazo por la cola derecha."
        ),
        "eje_x": "Valor de F",
        "media_global": media_global,
        "grupos": [
            {"nombre": nombres[i], "n": ns[i], "media": medias[i], "datos": datos[i]}
            for i in range(k)
        ],
        "tabla": [
            {
                "fuente": "Entre grupos (Tratamientos)",
                "df": df_entre,
                "sc": sst,
                "cm": mst,
                "f": f_est,
                "p": p_valor,
                "crit": f_crit,
            },
            {
                "fuente": "Dentro de los grupos (Error)",
                "df": df_dentro,
                "sc": sse,
                "cm": mse,
            },
            {"fuente": "Total", "df": df_total, "sc": total},
        ],
        "latex": {
            "general": general,
            "medios": medios_latex,
            "sst": sst_latex,
            "sse": sse_latex,
            "resultado": resultado,
            "p_valor": p_latex,
            "crit": crit_latex,
        },
        "grafico": _grafico_f(f_est, f_crit, df_entre, df_dentro),
    }


# --------------------------------------------------------------------------
# Dispatcher usado desde app.js (via Pyodide)
# --------------------------------------------------------------------------

_TESTS = {
    "una_media": test_una_media,
    "diferencia_medias": test_diferencia_medias,
    "proporcion": test_proporcion,
    "diferencia_proporciones": test_diferencia_proporciones,
    "anova": test_anova,
}


def ejecutar(nombre_test, payload_json):
    """Ejecuta un test desde la UI.

    ``payload_json`` es un JSON con los argumentos con nombre del test;
    retorna el resultado serializado en JSON (la UI lo parsea).
    """
    kwargs = json.loads(payload_json)
    if nombre_test not in _TESTS:
        raise ValueError("Test desconocido: " + nombre_test)
    resultado = _TESTS[nombre_test](**kwargs)
    return json.dumps(resultado, ensure_ascii=False)
