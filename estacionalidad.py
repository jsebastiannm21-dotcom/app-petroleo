# estacionalidad.py - Etapa 3: ¿hay meses del año en que el petróleo suele subir o bajar?
# Lee precios_petroleo.csv, calcula el retorno de cada mes y lo promedia por mes del año.
# Guarda la tabla en estacionalidad.csv y la gráfica en grafica_estacionalidad.png

import pandas as pd
import matplotlib
matplotlib.use("Agg")              # Dibuja directo a un archivo de imagen, sin abrir ventanas
import matplotlib.pyplot as plt

ENTRADA = "precios_petroleo.csv"
SALIDA = "estacionalidad.csv"
GRAFICA = "grafica_estacionalidad.png"
MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]

# ---------- 1. Leer precios ----------
datos = pd.read_csv(ENTRADA, index_col="Fecha", parse_dates=True)
cierre = datos["Cierre"]

# ---------- 2. Retorno de cada mes ----------
# Tomamos el último precio de cada mes ("ME" = fin de mes)...
fin_de_mes = cierre.resample("ME").last()
# ...y calculamos cuánto cambió en % respecto al fin del mes anterior
retorno_mensual = fin_de_mes.pct_change() * 100

# El mes actual todavía no termina, así que no lo contamos (sería un dato a medias)
hoy = cierre.index[-1]
retorno_mensual = retorno_mensual[retorno_mensual.index < hoy.to_period("M").start_time]
retorno_mensual = retorno_mensual.dropna()   # El primer mes no tiene mes anterior para comparar

# ---------- 3. Agrupar por mes del año ----------
tabla = pd.DataFrame({"retorno": retorno_mensual, "mes": retorno_mensual.index.month})
resumen = tabla.groupby("mes")["retorno"].agg(
    Retorno_promedio="mean",                       # Promedio de los años
    Retorno_mediano="median",                      # El valor del medio (menos sensible a años extremos)
    Anios_subio=lambda r: int((r > 0).sum()),      # Cuántos años ese mes terminó en subida
    Anios_total="count",                           # Cuántos años tenemos de ese mes
)
resumen.insert(0, "Mes", MESES)
resumen = resumen.round(2)
resumen.to_csv(SALIDA, index=False)

print(f"Meses analizados: {len(retorno_mensual)} "
      f"(de {retorno_mensual.index[0]:%b %Y} a {retorno_mensual.index[-1]:%b %Y})")
print(resumen.to_string(index=False))

# ---------- 4. Gráfica de barras ----------
FONDO, TEXTO, TEXTO_SUAVE, REJILLA = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
AZUL, ROJO = "#2a78d6", "#e34948"        # Azul = sube en promedio, rojo = baja en promedio

plt.rcParams.update({"font.size": 10, "text.color": TEXTO, "axes.labelcolor": TEXTO_SUAVE,
                     "xtick.color": TEXTO_SUAVE, "ytick.color": TEXTO_SUAVE})
fig, ax = plt.subplots(figsize=(11, 6), facecolor=FONDO)
ax.set_facecolor(FONDO)

valores = resumen["Retorno_promedio"]
colores = [AZUL if v > 0 else ROJO for v in valores]
ax.bar(MESES, valores, color=colores, width=0.55, zorder=3)
ax.axhline(0, color=TEXTO_SUAVE, linewidth=1, zorder=4)   # Línea del cero

# Encima (o debajo) de cada barra: el promedio y cuántos años subió ese mes
for i, fila in enumerate(resumen.itertuples()):
    v = fila.Retorno_promedio
    separacion = 0.4 if v > 0 else -0.4
    ax.text(i, v + separacion, f"{v:+.1f}%", ha="center", va="bottom" if v > 0 else "top",
            fontsize=9, color=TEXTO, fontweight="bold")
    ax.text(i, v + separacion * 3.2, f"subió {fila.Anios_subio}/{fila.Anios_total}",
            ha="center", va="bottom" if v > 0 else "top", fontsize=8, color=TEXTO_SUAVE)

ax.set_title("Petróleo WTI: retorno promedio de cada mes del año", loc="left",
             fontsize=13, fontweight="bold", pad=24)
ax.text(0, 1.02, f"Promedio de {retorno_mensual.index[0]:%m/%Y} a {retorno_mensual.index[-1]:%m/%Y}. "
        "Azul = sube en promedio, rojo = baja en promedio. "
        "\"subió 3/5\" = terminó en subida 3 de los 5 años.",
        transform=ax.transAxes, fontsize=9, color=TEXTO_SUAVE)
ax.set_ylabel("Cambio promedio en el mes (%)")
margen = max(abs(valores.min()), abs(valores.max())) * 1.45
ax.set_ylim(-margen, margen)
ax.yaxis.set_major_formatter(lambda y, _: f"{y:+.0f}%")
ax.grid(axis="y", color=REJILLA, linewidth=0.8, zorder=0)
for lado in ("top", "right", "left", "bottom"):
    ax.spines[lado].set_visible(False)
ax.tick_params(length=0)

fig.tight_layout()
fig.savefig(GRAFICA, dpi=150, facecolor=FONDO)
print(f"\nTabla guardada en {SALIDA} y gráfica en {GRAFICA}")
