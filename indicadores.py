# indicadores.py - Etapa 2: medias móviles de 50 y 200 días y RSI de 14 días
# Uso:  python indicadores.py               (petróleo WTI: crea indicadores.csv y grafica_medias.png)
#       python indicadores.py --activo GLD  (otro activo: se guarda en la carpeta datos)

import argparse

import matplotlib
import pandas as pd

matplotlib.use("Agg")              # Dibuja directo a un archivo de imagen, sin abrir ventanas
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

import activos  # noqa: E402

parser = argparse.ArgumentParser(description="Calcula medias móviles y RSI")
parser.add_argument("--activo", default=activos.PRINCIPAL)
simbolo = activos.limpiar(parser.parse_args().activo)

# ---------- 1. Leer precios y calcular ----------
precios = pd.read_csv(activos.ruta_precios(simbolo), index_col="Fecha", parse_dates=True)
resultado = activos.calcular_indicadores(precios["Cierre"])
resultado.to_csv(activos.ruta_indicadores(simbolo))
print(f"Indicadores de {activos.etiqueta(simbolo)} guardados en {activos.ruta_indicadores(simbolo).name}")
print("\nÚltimas 5 filas:")
print(resultado.tail(5))

# ---------- 2. Gráfica ----------
GRAFICA = "grafica_medias.png" if simbolo == activos.PRINCIPAL else \
    activos.DATOS / f"grafica_medias_{activos._slug(simbolo)}.png"
FONDO, TEXTO, TEXTO_SUAVE, REJILLA = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
AZUL, NARANJA, VERDE_AGUA = "#2a78d6", "#eb6834", "#1baf7a"
plt.rcParams.update({"font.size": 10, "text.color": TEXTO, "axes.labelcolor": TEXTO_SUAVE,
                     "xtick.color": TEXTO_SUAVE, "ytick.color": TEXTO_SUAVE})

fig, (arriba, abajo) = plt.subplots(2, 1, figsize=(12, 7.5), sharex=True,
                                    gridspec_kw={"height_ratios": [3, 1], "hspace": 0.12}, facecolor=FONDO)
cierre = resultado["Cierre"]
series = [("Precio de cierre", cierre, AZUL, 1.2), ("Media 50 días", resultado["MM50"], NARANJA, 2),
          ("Media 200 días", resultado["MM200"], VERDE_AGUA, 2)]
for nombre, serie, color, grosor in series:
    arriba.plot(serie.index, serie, color=color, linewidth=grosor, label=nombre)

# Etiqueta con el nombre y el último valor al final de cada línea (separadas si quedarían encimadas)
ultima_fecha = cierre.index[-1]
separacion = (cierre.max() - cierre.min()) * 0.04
posiciones = []
for nombre, serie, color, _ in series:
    valor = serie.iloc[-1]
    y = valor
    for p in posiciones:
        if abs(y - p) < separacion:
            y = p - separacion if y < p else p + separacion
    posiciones.append(y)
    arriba.annotate(f"{nombre}: {valor:,.2f}", xy=(ultima_fecha, valor),
                    xytext=(ultima_fecha + pd.Timedelta(days=15), y), textcoords="data",
                    va="center", fontsize=9, color=TEXTO, annotation_clip=False)
    arriba.plot([ultima_fecha], [valor], "o", color=color, markersize=6, markeredgecolor=FONDO, markeredgewidth=1.5)

arriba.set_title(f"{activos.nombre(simbolo)}: precio y medias móviles (últimos 5 años)",
                 loc="left", fontsize=13, fontweight="bold", pad=12)
arriba.set_ylabel("Precio")
arriba.legend(loc="upper left", frameon=False)

abajo.plot(resultado.index, resultado["RSI14"], color=AZUL, linewidth=1.2)
abajo.axhline(70, color=TEXTO_SUAVE, linewidth=1, linestyle="--")
abajo.axhline(30, color=TEXTO_SUAVE, linewidth=1, linestyle="--")
caja = dict(facecolor=FONDO, edgecolor="none", pad=1.5)   # Fondo para que el texto se lea
abajo.text(resultado.index[0], 72, "70: sobrecompra", fontsize=8, color=TEXTO_SUAVE, va="bottom", bbox=caja, zorder=5)
abajo.text(resultado.index[0], 28, "30: sobreventa", fontsize=8, color=TEXTO_SUAVE, va="top", bbox=caja, zorder=5)
abajo.set_ylim(0, 100)
abajo.set_yticks([0, 30, 50, 70, 100])
abajo.set_ylabel("RSI 14 días")

for ax in (arriba, abajo):
    ax.set_facecolor(FONDO)
    ax.grid(axis="y", color=REJILLA, linewidth=0.8)
    for lado in ("top", "right", "left"):
        ax.spines[lado].set_visible(False)
    ax.spines["bottom"].set_color(REJILLA)
    ax.tick_params(length=0)
abajo.xaxis.set_major_locator(mdates.YearLocator())
abajo.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

fig.subplots_adjust(left=0.07, right=0.83, top=0.92, bottom=0.06)
fig.savefig(GRAFICA, dpi=150, facecolor=FONDO)
print(f"\nGráfica guardada en {GRAFICA}")
