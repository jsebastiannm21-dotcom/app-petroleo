# avanzado.py - Análisis avanzados: volatilidad (ATR), soportes y resistencias, correlación, valor en riesgo (VaR)
# y sentimiento de noticias. Solo cálculos (sin pantallas); la app los muestra en secciones desplegables.
# Ninguno cambia la regla de compra: son información extra para decidir.
# Prueba:  python avanzado.py

import re

import numpy as np
import pandas as pd


# ---------- Volatilidad (ATR) ----------
def atr(precios, dias=14):
    """ATR de Wilder: cuánto se mueve el precio en promedio por día (en precio y en % del precio)."""
    alto, bajo, cierre = precios["Maximo"], precios["Minimo"], precios["Cierre"]
    anterior = cierre.shift()
    rango = pd.concat([alto - bajo, (alto - anterior).abs(), (bajo - anterior).abs()], axis=1).max(axis=1)
    serie = rango.ewm(alpha=1 / dias, min_periods=dias, adjust=False).mean()
    return float(serie.iloc[-1]), float(serie.iloc[-1] / cierre.iloc[-1] * 100)


def stop_por_volatilidad(atr_pct, multiplo=2):
    """Stop loss sugerido: 2 veces el movimiento diario normal (entre 1% y 15%), para no salir por puro ruido."""
    return float(np.clip(atr_pct * multiplo, 1, 15))


# ---------- Soportes y resistencias ----------
def soportes_resistencias(precios, dias=250, ventana=10, juntar_pct=1.5, maximo=3):
    """Niveles donde el precio rebotó (soportes, debajo del precio) o se frenó (resistencias, encima) en el último año.
    Un pivote es el mínimo (o máximo) de los 10 días a cada lado; pivotes a menos de 1,5% se juntan en un nivel."""
    d = precios.tail(dias)
    bajo, alto, precio = d["Minimo"], d["Maximo"], float(d["Cierre"].iloc[-1])
    ancho = 2 * ventana + 1
    pivotes = list(bajo[bajo == bajo.rolling(ancho, center=True).min()]) + \
        list(alto[alto == alto.rolling(ancho, center=True).max()])
    niveles = []                                         # [precio promedio, veces que lo tocó]
    for p in sorted(pivotes):
        if niveles and p <= niveles[-1][0] * (1 + juntar_pct / 100):
            n = niveles[-1][1]
            niveles[-1] = [(niveles[-1][0] * n + p) / (n + 1), n + 1]
        else:
            niveles.append([p, 1])
    soportes = sorted([n for n in niveles if n[0] < precio], key=lambda n: -n[0])[:maximo]
    resistencias = sorted([n for n in niveles if n[0] > precio], key=lambda n: n[0])[:maximo]
    return soportes, resistencias


# ---------- Correlación ----------
def correlacion(cierres, dias=250):
    """Matriz de correlación de los retornos diarios del último año. cierres = {símbolo: serie de cierres}."""
    retornos = pd.DataFrame(cierres).sort_index().pct_change(fill_method=None).tail(dias)
    return retornos.corr(min_periods=60)


def pares_parecidos(matriz, limite=0.8):
    """Pares que se mueven casi igual (correlación de 0,8 o más)."""
    columnas = list(matriz.columns)
    return [(a, b, float(matriz.loc[a, b])) for i, a in enumerate(columnas) for b in columnas[i + 1:]
            if pd.notna(matriz.loc[a, b]) and matriz.loc[a, b] >= limite]


# ---------- Valor en riesgo (VaR) ----------
def var_historico(valores_usd, cierres, confianza=95, dias=500):
    """Cuánto podría perder el portafolio en un día malo: la pérdida que solo se supera 1 de cada 20 días (95%).
    Simulación histórica: se le aplican al portafolio de hoy los movimientos diarios reales de los últimos 2 años.
    valores_usd = {símbolo: valor hoy en US$}; cierres = {símbolo: serie de cierres}."""
    retornos = pd.DataFrame(cierres).sort_index().pct_change(fill_method=None).tail(dias)
    retornos = retornos.dropna(how="all").fillna(0)     # Día sin dato de un activo (festivo) = no se movió
    pnl = sum(retornos[s] * v for s, v in valores_usd.items())
    return float(-np.percentile(pnl, 100 - confianza))


# ---------- Sentimiento de noticias ----------
POSITIVAS = ["surge", "soar", "rall", "gain", "jump", "rise", "rising", "beat", "record high", "upgrade", "strong",
             "boost", "rebound", "climb", "bullish", "profit", "growth", "outperform", "tops", "raises", "higher",
             "sube", "subida", "alza", "gana", "ganancia", "récord", "repunt", "crece", "crecimiento", "mejora",
             "dispara", "avanza", "optimis", "utilidad", "dividendo extraordinario"]
NEGATIVAS = ["fall", "drop", "plunge", "slump", "tumble", "crash", "loss", "cut", "downgrade", "weak", "miss",
             "bearish", "decline", "sink", "lawsuit", "probe", "warning", "slide", "fear", "recession", "sell-off",
             "layoff", "lower", "cae", "caída", "baja", "pierde", "pérdida", "desplom", "recorte", "crisis", "sanción",
             "demanda", "alerta", "retrocede", "pesimis", "quiebra", "despido"]
_PATRON = {signo: re.compile(r"\b(" + "|".join(map(re.escape, palabras)) + ")", re.IGNORECASE)
           for signo, palabras in ((1, POSITIVAS), (-1, NEGATIVAS))}


def sentimiento(titular):
    """'Positivo', 'Negativo' o 'Neutro' contando palabras de subida y de bajada (en español e inglés).
    shortcut: lista de palabras, no entiende ironía ni negaciones ('no cae'); usar Claude si hace falta precisión."""
    puntos = len(_PATRON[1].findall(titular)) - len(_PATRON[-1].findall(titular))
    return "Positivo" if puntos > 0 else "Negativo" if puntos < 0 else "Neutro"


def balance(titulares):
    """(positivas, negativas, neutras, texto del balance)."""
    s = pd.Series([sentimiento(t) for t in titulares], dtype=str)
    pos, neg, neu = int((s == "Positivo").sum()), int((s == "Negativo").sum()), int((s == "Neutro").sum())
    texto = "positivo" if pos > neg * 1.5 else "negativo" if neg > pos * 1.5 else "mixto"
    return pos, neg, neu, texto


def noticias_semana(simbolo, grupos):
    """Titulares guardados de los últimos 7 días del activo y de su mercado (sin ir a internet)."""
    import noticias
    t = noticias.leer()
    if t.empty:
        return t
    t = t[(t["Activo"] == simbolo) | t["Grupo"].isin(grupos)]
    return t[t["Fecha"] >= pd.Timestamp.now() - pd.Timedelta(days=7)].drop_duplicates("Titular")



# ---------- Plazo y hora de venta ----------
PLAZOS = (1, 2, 3, 5)


def plazos(datos, fechas, costo_pct=0.5):
    """Para cada plazo (1, 2, 3 y 5 días de mercado), qué pasó en los días parecidos si se vendía ese día:
    % que subió (tasa de aciertos), ganancia promedio vendiendo al cierre y vendiendo en la apertura (ya restado el costo)."""
    pos = datos.index.get_indexer(fechas)
    cierre, apertura = datos["Cierre"].to_numpy(), datos["Apertura"].to_numpy()
    filas = []
    for h in PLAZOS:
        p = pos[(pos >= 0) & (pos + h < len(datos))]
        if not len(p):
            continue
        al_cierre = (cierre[p + h] / cierre[p] - 1) * 100 - costo_pct
        al_abrir = (apertura[p + h] / cierre[p] - 1) * 100 - costo_pct
        filas.append({"Plazo": h, "Aciertos_%": float((al_cierre > 0).mean() * 100), "Al_cierre_%": float(np.nanmean(al_cierre)),
                      "En_apertura_%": float(np.nanmean(al_abrir)), "Casos": len(p)})
    return pd.DataFrame(filas)


def mejor_plazo(tabla):
    """(plazo en días, hora sugerida en palabras, fila) con la mayor ganancia promedio. Siempre en días, nunca minutos."""
    t = tabla.assign(Mejor=tabla[["Al_cierre_%", "En_apertura_%"]].max(axis=1))
    f = t.loc[t["Mejor"].idxmax()]
    diferencia = f["En_apertura_%"] - f["Al_cierre_%"]
    if diferencia > 0.1:
        hora = "Antes de la apertura: deja la orden de venta programada para que se ejecute apenas abra el mercado"
    elif diferencia < -0.1:
        hora = "Al cierre: en la última media hora del mercado"
    else:
        hora = "En la apertura (vender al abrir o al cerrar dio casi lo mismo)"
    return int(f["Plazo"]), hora, f


if __name__ == "__main__":
    fechas = pd.bdate_range("2024-01-01", periods=300)
    # Precio que oscila entre 90 y 110: soporte cerca de 90, resistencia cerca de 110, ATR conocido
    cierre = pd.Series(100 + 10 * np.sin(np.arange(300) / 8), index=fechas)
    p = pd.DataFrame({"Cierre": cierre, "Maximo": cierre + 1, "Minimo": cierre - 1})
    _, pct = atr(p)
    assert 1 < pct < 3, pct
    assert stop_por_volatilidad(0.2) == 1 and stop_por_volatilidad(20) == 15
    sop, res = soportes_resistencias(p)
    assert sop and abs(sop[-1][0] - 89) < 1.5 and res and abs(res[-1][0] - 111) < 1.5, (sop, res)
    m = correlacion({"A": cierre, "B": cierre * 2, "C": cierre[::-1].set_axis(fechas)})
    assert pares_parecidos(m) == [("A", "B", 1.0)] or abs(pares_parecidos(m)[0][2] - 1) < 1e-9
    v = var_historico({"A": 1000}, {"A": cierre})
    assert 0 < v < 1000 * 0.1, v
    assert sentimiento("Oil prices surge on OPEC cut") in ("Neutro", "Positivo")
    assert sentimiento("Ecopetrol se desploma en bolsa") == "Negativo"
    assert sentimiento("Apple beats estimates, stock jumps") == "Positivo"
    assert balance(["sube", "sube", "cae"])[:3] == (2, 1, 0)
    # Plazos: un precio que sube 1% cada día y abre 0,5% por encima del cierre anterior
    f2 = pd.bdate_range("2024-01-01", periods=40)
    c2 = pd.Series(100 * 1.01 ** np.arange(40), index=f2)
    d2 = pd.DataFrame({"Cierre": c2, "Apertura": c2.shift(1) * 1.005})
    t = plazos(d2, f2[5:20], costo_pct=0)
    assert list(t["Plazo"]) == [1, 2, 3, 5] and (t["Aciertos_%"] == 100).all()
    h, hora, _ = mejor_plazo(t)
    assert h == 5 and hora.startswith("Al cierre"), (h, hora)       # Subiendo todo el día: mejor al cierre y al plazo largo
    print("Análisis avanzados: pruebas OK")
