# eventos.py - Etapa 4: ¿cómo reaccionó el precio a cada evento?
# Lee precios_petroleo.csv y eventos.csv, mide el cambio del precio 1, 3 y 5 días
# de mercado después de cada evento, guarda reaccion_eventos.csv y dibuja grafica_eventos.png

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.lines import Line2D

PRECIOS = "precios_petroleo.csv"
EVENTOS = "eventos.csv"
SALIDA = "reaccion_eventos.csv"
GRAFICA = "grafica_eventos.png"
DIAS = [1, 3, 5]

# ---------- 1. Leer los archivos ----------
cierre = pd.read_csv(PRECIOS, index_col="Fecha", parse_dates=True)["Cierre"]
eventos = pd.read_csv(EVENTOS, parse_dates=["Fecha"])
# Solo las noticias que afectan al petróleo (la columna Activo puede tener varios grupos separados por ";")
eventos = eventos[eventos["Activo"].fillna("petróleo").str.split(";").apply(lambda g: "petróleo" in g)]
eventos = eventos.reset_index(drop=True)


# ---------- 2. Clasificar cada evento ----------
# Usamos la primera palabra del texto para saber qué decidió la OPEP
def categoria(fila):
    if fila["Tipo"] == "Geopolítico":
        return "Geopolítico"
    if fila["Tipo"] != "OPEP":          # Irán, Ormuz, Trump...
        return fila["Tipo"]
    if fila["Evento"].startswith("Aumenta"):
        return "OPEP aumenta producción"
    if fila["Evento"].startswith("Recorta"):
        return "OPEP recorta producción"
    if fila["Evento"].startswith(("Mantiene", "Pospone")):
        return "OPEP mantiene o pospone"
    return "OPEP otro"          # Noticias de la OPEP que no son decisiones de producción

eventos["Categoria"] = eventos.apply(categoria, axis=1)

# ---------- 3. Medir la reacción del precio ----------
# Precio base = último cierre ANTES del día del evento (así capturamos toda la reacción,
# aunque el anuncio haya sido durante el día o en fin de semana).
# "1 día después" = cierre de la 1ª sesión de mercado desde el evento, "3 días" = la 3ª, etc.
fechas = cierre.index
for d in DIAS:
    eventos[f"Cambio_{d}d_%"] = float("nan")

for i, ev in eventos.iterrows():
    pos_base = fechas.searchsorted(ev["Fecha"]) - 1   # Posición del último día antes del evento
    if pos_base < 0:
        continue                                      # El evento es anterior a nuestros datos
    base = cierre.iloc[pos_base]
    eventos.loc[i, "Precio_base"] = base
    for d in DIAS:
        if pos_base + d < len(cierre):                # Solo si ya pasaron esos días
            eventos.loc[i, f"Cambio_{d}d_%"] = (cierre.iloc[pos_base + d] / base - 1) * 100

columnas = ["Fecha", "Categoria", "Evento", "Precio_base"] + [f"Cambio_{d}d_%" for d in DIAS]
resultado = eventos[columnas].round({c: 2 for c in columnas[3:]})
resultado.to_csv(SALIDA, index=False)

pd.set_option("display.width", 200, "display.max_colwidth", 60)
print(resultado.drop(columns="Evento").to_string(index=False))

print("\nPromedio por tipo de evento (%):")
promedios = resultado.groupby("Categoria")[[f"Cambio_{d}d_%" for d in DIAS]].mean().round(2)
promedios["Eventos"] = resultado.groupby("Categoria").size()
print(promedios.to_string())

# ---------- 4. Gráfica ----------
FONDO, TEXTO, TEXTO_SUAVE, REJILLA = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
ESTILO = {   # color y forma de cada tipo de evento (la forma ayuda si no se distinguen colores)
    "OPEP aumenta producción": ("#2a78d6", "^"),
    "OPEP recorta producción": ("#eb6834", "v"),
    "OPEP mantiene o pospone": ("#1baf7a", "o"),
    "OPEP otro": ("#eda100", "D"),
    "Irán": ("#e87ba4", "P"),
    "Ormuz": ("#008300", "s"),
    "Trump": ("#6250d6", "X"),
}

plt.rcParams.update({"font.size": 10, "text.color": TEXTO, "axes.labelcolor": TEXTO_SUAVE,
                     "xtick.color": TEXTO_SUAVE, "ytick.color": TEXTO_SUAVE})
fig, ax = plt.subplots(figsize=(13, 6.5), facecolor=FONDO)
ax.set_facecolor(FONDO)
ax.plot(cierre.index, cierre, color="#8a8984", linewidth=1.2, zorder=2)

# Puntos de las reuniones de la OPEP, sobre el precio del día del evento
for cat, (color, forma) in ESTILO.items():
    sub = eventos[eventos["Categoria"] == cat]
    pos = fechas.searchsorted(sub["Fecha"]).clip(max=len(cierre) - 1)
    ax.scatter(fechas[pos], cierre.iloc[pos], color=color, marker=forma, s=70,
               edgecolor=FONDO, linewidth=1.2, zorder=4)

# Eventos geopolíticos: línea vertical punteada con su nombre
for _, ev in eventos[eventos["Categoria"] == "Geopolítico"].iterrows():
    ax.axvline(ev["Fecha"], color=TEXTO, linewidth=1, linestyle="--", zorder=3)
    nombre = ev["Evento"].split(" (")[0].split(";")[0]
    ax.text(ev["Fecha"] + pd.Timedelta(days=12), 128, nombre, fontsize=9, color=TEXTO,
            va="top", bbox=dict(facecolor=FONDO, edgecolor="none", pad=1.5), zorder=5)

leyenda = [Line2D([], [], color="#8a8984", linewidth=1.5, label="Precio de cierre")]
leyenda += [Line2D([], [], color=c, marker=m, linestyle="", markersize=8, label=cat)
            for cat, (c, m) in ESTILO.items()]
leyenda += [Line2D([], [], color=TEXTO, linestyle="--", linewidth=1, label="Evento geopolítico")]
ax.legend(handles=leyenda, loc="lower left", frameon=False, ncol=3)

ax.set_title("Petróleo WTI y decisiones de la OPEP+ (últimos 5 años)", loc="left",
             fontsize=13, fontweight="bold", pad=12)
ax.set_ylabel("Dólares por barril")
ax.set_ylim(40, 130)
ax.grid(axis="y", color=REJILLA, linewidth=0.8, zorder=0)
for lado in ("top", "right", "left"):
    ax.spines[lado].set_visible(False)
ax.spines["bottom"].set_color(REJILLA)
ax.tick_params(length=0)
ax.xaxis.set_major_locator(mdates.YearLocator())
ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

fig.tight_layout()
fig.savefig(GRAFICA, dpi=150, facecolor=FONDO)
print(f"\nTabla guardada en {SALIDA} y gráfica en {GRAFICA}")
