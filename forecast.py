# forecast.py - Etapa 6: proyección del precio a 30 días
# Usa Prophet (de Meta). Si Prophet no está disponible o falla, usa un método
# sencillo de respaldo: "caminata aleatoria con tendencia".
# Guarda forecast.csv y la gráfica grafica_forecast.png
# AVISO: es una proyección estadística, no una predicción segura ni consejo de inversión.

import logging
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

ENTRADA = "precios_petroleo.csv"
SALIDA = "forecast.csv"
GRAFICA = "grafica_forecast.png"
DIAS = 30            # Días de calendario a proyectar (solo se cuentan días de semana)
NIVEL = 0.80         # La banda cubre el 80% de los resultados probables

datos = pd.read_csv(ENTRADA, index_col="Fecha", parse_dates=True)
cierre = datos["Cierre"]
ultima_fecha = cierre.index[-1]
# Fechas futuras: los próximos 30 días de calendario, quitando sábados y domingos
futuro = pd.bdate_range(ultima_fecha + pd.Timedelta(days=1), ultima_fecha + pd.Timedelta(days=DIAS))


# ---------- Método 1: Prophet ----------
def con_prophet(serie, fechas_futuras):
    from prophet import Prophet
    logging.getLogger("cmdstanpy").setLevel(logging.WARNING)   # Menos mensajes técnicos
    # Prophet pide una tabla con dos columnas: "ds" (fecha) y "y" (valor)
    # Usamos el logaritmo del precio: así los cambios se miden en %, no en dólares
    tabla = pd.DataFrame({"ds": serie.index, "y": np.log(serie.values)})
    modelo = Prophet(
        interval_width=NIVEL,
        weekly_seasonality=False,    # No hay datos en fines de semana
        yearly_seasonality=True,     # Patrón según la época del año
        daily_seasonality=False,
    )
    modelo.fit(tabla)
    pred = modelo.predict(pd.DataFrame({"ds": fechas_futuras}))
    return pd.DataFrame({
        "Central": np.exp(pred["yhat"].values),
        "Banda_baja": np.exp(pred["yhat_lower"].values),
        "Banda_alta": np.exp(pred["yhat_upper"].values),
    }, index=fechas_futuras)


# ---------- Método 2 (respaldo): caminata aleatoria con tendencia ----------
def metodo_sencillo(serie, fechas_futuras):
    # Idea: mañana = hoy + un cambio al azar del tamaño típico de los últimos 6 meses.
    # La línea central sigue la tendencia promedio; la banda se ensancha con el tiempo
    # porque mientras más lejos, más incertidumbre.
    from statistics import NormalDist
    cambios = np.log(serie).diff().dropna().iloc[-126:]        # Últimos ~6 meses
    tendencia, volatilidad = cambios.mean(), cambios.std()
    z = NormalDist().inv_cdf(0.5 + NIVEL / 2)                  # 1,28 para una banda del 80%
    pasos = np.arange(1, len(fechas_futuras) + 1)
    base = np.log(serie.iloc[-1]) + tendencia * pasos
    ancho = z * volatilidad * np.sqrt(pasos)
    return pd.DataFrame({"Central": np.exp(base), "Banda_baja": np.exp(base - ancho),
                         "Banda_alta": np.exp(base + ancho)}, index=fechas_futuras)


def proyectar(serie, fechas_futuras):
    try:
        return con_prophet(serie, fechas_futuras), "Prophet"
    except Exception as error:      # Si Prophet no está instalado o falla, usamos el respaldo
        print(f"Prophet no disponible ({error}). Uso el método sencillo.")
        return metodo_sencillo(serie, fechas_futuras), "Caminata aleatoria con tendencia"


if __name__ == "__main__":    # (Esta línea permite usar las funciones desde otros archivos)
    # ---------- 1. Proyección con los dos métodos ----------
    pronostico, metodo = proyectar(cierre, futuro)
    sencillo = metodo_sencillo(cierre, futuro)
    resultados = {metodo: pronostico}
    if metodo == "Prophet":
        resultados["Método sencillo"] = sencillo

    tabla = pd.concat({k: v for k, v in resultados.items()}, axis=1).round(2)
    tabla.index.name = "Fecha"
    tabla.to_csv(SALIDA)

    print(f"Último precio real ({ultima_fecha.date()}): {cierre.iloc[-1]:.2f}")
    for nombre, p in resultados.items():
        fin = p.iloc[-1]
        print(f"{nombre}: al {p.index[-1].date()} -> {fin['Central']:.2f} "
              f"(banda del {NIVEL:.0%}: {fin['Banda_baja']:.2f} a {fin['Banda_alta']:.2f})")

    # ---------- 2. Prueba: ¿qué tan bien le habría ido a cada método en el último año? ----------
    # 10 veces: escondemos los datos desde una fecha, proyectamos 30 días y comparamos con lo real
    print("\nPRUEBA (10 proyecciones de 30 días durante el último año):")
    cortes = [ultima_fecha - pd.Timedelta(days=30 * k) for k in range(1, 11)]
    funciones = {"Prophet": lambda s, f: proyectar(s, f)[0], "Método sencillo": metodo_sencillo}
    for nombre in resultados:
        errores, dentro = [], []
        for corte in cortes:
            pasado = cierre[cierre.index <= corte]
            real = cierre[(cierre.index > corte) & (cierre.index <= corte + pd.Timedelta(days=DIAS))]
            p = funciones[nombre](pasado, real.index)
            errores.append((abs(p["Central"] - real) / real).mean() * 100)
            dentro.append(((real >= p["Banda_baja"]) & (real <= p["Banda_alta"])).mean() * 100)
        print(f"  {nombre:<16} error promedio {np.mean(errores):5.1f}%   "
              f"precio real dentro de la banda {np.mean(dentro):4.0f}% (debería ser ~{NIVEL:.0%})")

    # ---------- 3. Gráfica: un panel por método, misma escala ----------
    FONDO, TEXTO, TEXTO_SUAVE, REJILLA = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
    AZUL, NARANJA = "#2a78d6", "#eb6834"
    plt.rcParams.update({"font.size": 10, "text.color": TEXTO, "axes.labelcolor": TEXTO_SUAVE,
                         "xtick.color": TEXTO_SUAVE, "ytick.color": TEXTO_SUAVE})
    fig, ejes = plt.subplots(1, len(resultados), figsize=(7 * len(resultados), 5.5),
                             sharey=True, facecolor=FONDO, squeeze=False)
    reciente = cierre[cierre.index > ultima_fecha - pd.DateOffset(months=6)]

    for ax, (nombre, p) in zip(ejes[0], resultados.items()):
        ax.set_facecolor(FONDO)
        ax.plot(reciente.index, reciente, color=AZUL, linewidth=1.5, label="Precio real (6 meses)")
        # Unimos la banda al último precio real para que no quede un hueco
        x = [ultima_fecha] + list(p.index)
        ax.fill_between(x, [cierre.iloc[-1]] + list(p["Banda_baja"]),
                        [cierre.iloc[-1]] + list(p["Banda_alta"]),
                        color=NARANJA, alpha=0.15, linewidth=0, label=f"Rango probable ({NIVEL:.0%})")
        ax.plot(p.index, p["Central"], color=NARANJA, linewidth=2, label="Proyección central")
        ax.axvline(ultima_fecha, color=TEXTO_SUAVE, linewidth=1, linestyle=":")
        for col, txt in [("Banda_alta", "máx"), ("Central", "central"), ("Banda_baja", "mín")]:
            v = p[col].iloc[-1]
            ax.annotate(f"{txt}: {v:.1f}", xy=(p.index[-1], v), xytext=(6, 0),
                        textcoords="offset points", va="center", fontsize=9, color=TEXTO)
        ax.set_title(nombre, loc="left", fontsize=12, fontweight="bold")
        ax.grid(axis="y", color=REJILLA, linewidth=0.8)
        for lado in ("top", "right", "left"):
            ax.spines[lado].set_visible(False)
        ax.spines["bottom"].set_color(REJILLA)
        ax.tick_params(length=0)
        ax.xaxis.set_major_locator(mdates.MonthLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))

    ejes[0][0].set_ylabel("Dólares por barril")
    manijas, nombres = ejes[0][0].get_legend_handles_labels()
    fig.legend(manijas, nombres, loc="lower left", bbox_to_anchor=(0.05, 0.0), ncol=3, frameon=False)
    fig.suptitle(f"Petróleo WTI: proyección a {DIAS} días desde el {ultima_fecha:%d/%m/%Y}",
                 x=0.05, ha="left", fontsize=13, fontweight="bold")
    fig.subplots_adjust(left=0.06, right=0.93, top=0.86, bottom=0.15, wspace=0.22)
    fig.savefig(GRAFICA, dpi=150, facecolor=FONDO)
    print(f"\nGuardado: {SALIDA} y {GRAFICA}")
