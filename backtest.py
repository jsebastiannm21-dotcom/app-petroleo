# backtest.py - ¿Habría funcionado la estrategia en el pasado?
# Regla (la misma de estrategia.py):
#   - Buscar días parecidos con el filtro más estricto que dé al menos 30 casos
#     (RSI ±5 y mismo mes -> RSI ±5 -> ±10 -> ±15 -> ±20). Si no hay 30: ESPERAR (no compra).
#   - COMPRAR al cierre si la probabilidad de subida es 56% o más Y la Time Machine sale a favor.
#   - Vender con la PRIMERA de: stop loss -3%, objetivo +6%, o 5 días de mercado (al cierre).
# Reglas del backtest:
#   - Cada decisión usa solo datos conocidos ese día (sin mirar el futuro).
#   - 0,5% de costo por operación (compra + venta).
#   - Se mide aparte en los primeros 4 años y en el último año, contra "comprar y mantener".
# Uso:  python backtest.py                (petróleo WTI, con gráfica)
#       python backtest.py --activo GLD   (otro activo)
#       python backtest.py --todos        (resumen de los activos que sigue el simulador)
#       python backtest.py --todos --completo   (todos los activos; tarda bastante)
# AVISO: resultados del pasado no garantizan resultados futuros.

import argparse

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

import activos  # noqa: E402
import estrategia  # noqa: E402

DIAS = estrategia.DIAS_ADELANTE
UMBRAL = estrategia.UMBRAL_COMPRA
MIN_CASOS = estrategia.MIN_CASOS
STOP = estrategia.STOP_LOSS / 100
OBJETIVO = estrategia.OBJETIVO / 100
COSTO = estrategia.COSTO
CAPITAL = 10_000


class Backtest:
    def __init__(self, simbolo, umbral=UMBRAL, stop=STOP, objetivo=OBJETIVO):
        self.simbolo = simbolo
        self.umbral, self.stop, self.objetivo = umbral, stop, objetivo     # Otros valores = probar un ajuste de regla
        activos.asegurar_datos(simbolo)
        ind = pd.read_csv(activos.ruta_indicadores(simbolo), index_col="Fecha", parse_dates=True)
        precios = pd.read_csv(activos.ruta_precios(simbolo), index_col="Fecha", parse_dates=True)
        datos = ind.join(precios[["Apertura", "Maximo", "Minimo"]])
        self.fechas = datos.index
        self.validos = datos["MM200"].notna().values
        self.alcista = (datos["MM50"] > datos["MM200"]).values
        self.rsi = datos["RSI14"].values
        self.mes = datos.index.month.values
        self.ret5 = (datos["Cierre"].shift(-DIAS) / datos["Cierre"] - 1).values
        self.cierre, self.apertura = datos["Cierre"].values, datos["Apertura"].values
        self.maximo, self.minimo = datos["Maximo"].values, datos["Minimo"].values
        self.barras = estrategia.barras(datos)
        self.mm200 = datos["MM200"].values
        self.corte = int(np.searchsorted(self.fechas, self.fechas[-1] - pd.DateOffset(years=1)))

    def probabilidad(self, t):
        """Probabilidad con el filtro adaptativo, usando solo días cuyo resultado se conocía el día t."""
        hasta = t - DIAS + 1
        if hasta <= 0:
            return np.nan, 0
        base = self.validos[:hasta] & (self.alcista[:hasta] == self.alcista[t])
        distancia = np.abs(self.rsi[:hasta] - self.rsi[t])
        for rango, mes in estrategia.NIVELES_FILTRO:
            filtro = base & (distancia <= rango)
            if mes:
                filtro &= self.mes[:hasta] == self.mes[t]
            casos = self.ret5[:hasta][filtro]
            if len(casos) >= MIN_CASOS:
                return (casos > 0).mean() * 100, len(casos), np.flatnonzero(filtro)
        return np.nan, len(casos), None                            # ESPERAR: datos insuficientes

    def a_favor(self, posiciones_casos, t):
        """Time Machine con los días que siguieron a cada caso (todos conocidos el día t)."""
        filas = (posiciones_casos[:, None] + np.arange(1, DIAS + 1)).ravel()
        pool = self.barras[filas[filas <= t]]
        pool = pool[~np.isnan(pool).any(axis=1)]
        return len(pool) > 0 and estrategia.time_machine(pool, semilla=t, stop_loss=self.stop * 100,
                                                         objetivo=self.objetivo * 100)["a_favor"]

    def salida(self, t):
        """Día, precio y motivo de venta de una compra hecha al cierre del día t."""
        entrada = self.cierre[t]
        stop, meta = entrada * (1 - self.stop), entrada * (1 + self.objetivo)
        for k in range(1, DIAS + 1):
            d = t + k
            if self.apertura[d] <= stop:          # Abrió por debajo del stop: se vende a la apertura
                return d, self.apertura[d], "stop loss"
            if self.minimo[d] <= stop:            # Si toca stop y objetivo el mismo día, asumimos lo peor
                return d, stop, "stop loss"
            if self.apertura[d] >= meta:
                return d, self.apertura[d], "objetivo"
            if self.maximo[d] >= meta:
                return d, meta, "objetivo"
        return t + DIAS, self.cierre[t + DIAS], "plazo"

    def simular(self, desde, hasta):
        capital, curva, operaciones = CAPITAL, [], []
        t = desde
        while t < hasta:
            curva.append((self.fechas[t], capital))
            if not self.validos[t] or t + DIAS >= hasta:
                t += 1
                continue
            prob, n, pos = self.probabilidad(t)
            cayendo = self.cierre[t] < self.mm200[t] and self.cierre[t] < self.cierre[t - DIAS]   # Protección
            if not np.isnan(prob) and prob >= self.umbral and not cayendo and self.a_favor(pos, t):
                dia, precio, motivo = self.salida(t)
                invertido = capital * (1 - COSTO)
                for d in range(t + 1, dia):
                    curva.append((self.fechas[d], invertido * self.cierre[d] / self.cierre[t]))
                capital = invertido * precio / self.cierre[t]
                operaciones.append({"Compra": self.fechas[t].date(), "Venta": self.fechas[dia].date(),
                                    "Precio_compra": round(self.cierre[t], 2), "Precio_venta": round(precio, 2),
                                    "Motivo": motivo, "Probabilidad_%": round(prob, 1), "Casos": n,
                                    "Resultado_neto_%": round((precio / self.cierre[t] * (1 - COSTO) - 1) * 100, 2)})
                t = dia
            else:
                t += 1
        curva.append((self.fechas[hasta - 1], capital))
        return pd.Series(dict(curva)).sort_index(), pd.DataFrame(operaciones)

    def comprar_y_mantener(self, desde, hasta):
        precios = pd.Series(self.cierre[desde:hasta], index=self.fechas[desde:hasta])
        return CAPITAL * (1 - COSTO) * precios / precios.iloc[0]


def resumen(curva, operaciones=None):
    r = {"Resultado_%": (curva.iloc[-1] / CAPITAL - 1) * 100,
         "Peor_caida_%": ((curva / curva.cummax()) - 1).min() * 100}
    if operaciones is not None:
        r["Operaciones"] = len(operaciones)
        r["Aciertos_%"] = (operaciones["Resultado_neto_%"] > 0).mean() * 100 if len(operaciones) else np.nan
    return r


def resultados(simbolo):
    bt = Backtest(simbolo)
    n = len(bt.fechas)
    primer = int(np.argmax(bt.validos)) if bt.validos.any() else bt.corte
    salida = {"bt": bt}
    for periodo, (desde, hasta) in {"ajuste": (primer, bt.corte), "prueba": (bt.corte, n)}.items():
        curva, ops = bt.simular(desde, hasta)
        bh = bt.comprar_y_mantener(desde, hasta)
        salida[periodo] = {"curva": curva, "ops": ops, "bh": bh, "est": resumen(curva, ops), "cym": resumen(bh)}
    return salida


def informe(simbolo):
    res = resultados(simbolo)
    bt = res["bt"]
    f = bt.fechas
    print(f"{activos.etiqueta(simbolo)}")
    print(f"Regla: COMPRAR con >= {UMBRAL}% y {MIN_CASOS}+ casos; salida stop -{STOP:.0%}, objetivo +{OBJETIVO:.0%} "
          f"o {DIAS} días; costo {COSTO:.1%}\n")
    print(f"  {'Periodo':<34}{'Estrategia':>11}{'Operac.':>9}{'Aciertos':>10}{'Peor caída':>12}{'Comprar y mant.':>17}")
    for periodo, texto in [("ajuste", f"4 años ({f[0].date()} a {f[bt.corte - 1].date()})"),
                           ("prueba", f"Último año (desde {f[bt.corte].date()})")]:
        e, c = res[periodo]["est"], res[periodo]["cym"]
        print(f"  {texto:<34}{e['Resultado_%']:>+10.1f}%{e['Operaciones']:>9}{e['Aciertos_%']:>9.0f}%"
              f"{e['Peor_caida_%']:>+11.1f}%{c['Resultado_%']:>+16.1f}%")
    ops = res["prueba"]["ops"]
    if len(ops):
        print(f"\nSalidas en el último año: {ops['Motivo'].value_counts().to_dict()}")
        print(ops.to_string(index=False))
        ops.to_csv("operaciones_backtest.csv" if simbolo == activos.PRINCIPAL
                   else activos.DATOS / f"operaciones_backtest_{activos._slug(simbolo)}.csv", index=False)
    return res


def grafica(res):
    bt, curva, bh = res["bt"], res["prueba"]["curva"], res["prueba"]["bh"]
    FONDO, TEXTO, TEXTO_SUAVE, REJILLA = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
    plt.rcParams.update({"font.size": 10, "text.color": TEXTO, "axes.labelcolor": TEXTO_SUAVE,
                         "xtick.color": TEXTO_SUAVE, "ytick.color": TEXTO_SUAVE})
    fig, ax = plt.subplots(figsize=(12, 6), facecolor=FONDO)
    ax.set_facecolor(FONDO)
    for serie, color, nombre in [(curva, "#2a78d6", "Estrategia"), (bh, "#eb6834", "Comprar y mantener")]:
        ax.plot(serie.index, serie, color=color, linewidth=2, label=nombre)
        ax.annotate(f"{nombre}: {serie.iloc[-1]:,.0f}", xy=(serie.index[-1], serie.iloc[-1]),
                    xytext=(6, 0), textcoords="offset points", va="center", fontsize=9, color=TEXTO)
    ax.axhline(CAPITAL, color=TEXTO_SUAVE, linewidth=1, linestyle=":")
    ax.set_title(f"Backtest {activos.nombre(bt.simbolo)} (último año): 10.000 dólares", loc="left",
                 fontsize=13, fontweight="bold", pad=12)
    ax.set_ylabel("Capital (dólares)")
    ax.yaxis.set_major_formatter(lambda y, _: f"{y:,.0f}")
    ax.legend(loc="upper left", frameon=False)
    ax.grid(axis="y", color=REJILLA, linewidth=0.8)
    for lado in ("top", "right", "left"):
        ax.spines[lado].set_visible(False)
    ax.spines["bottom"].set_color(REJILLA)
    ax.tick_params(length=0)
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    fig.subplots_adjust(left=0.08, right=0.84, top=0.9, bottom=0.08)
    nombre = "grafica_backtest.png" if bt.simbolo == activos.PRINCIPAL else \
        activos.DATOS / f"grafica_backtest_{activos._slug(bt.simbolo)}.png"
    fig.savefig(nombre, dpi=150, facecolor=FONDO)
    print(f"Gráfica guardada en {nombre}")


def todos(simbolos):
    filas = []
    for i, simbolo in enumerate(simbolos, 1):
        print(f"[{i}/{len(simbolos)}] {activos.etiqueta(simbolo)}...", flush=True)
        try:
            res = resultados(simbolo)
        except Exception as error:
            print(f"   omitido: {error}")
            continue
        a, p = res["ajuste"], res["prueba"]
        filas.append({"Activo": simbolo, "Ajuste_estrategia_%": a["est"]["Resultado_%"],
                      "Ajuste_CyM_%": a["cym"]["Resultado_%"], "Prueba_estrategia_%": p["est"]["Resultado_%"],
                      "Prueba_CyM_%": p["cym"]["Resultado_%"], "Operaciones_prueba": p["est"]["Operaciones"],
                      "Aciertos_prueba_%": p["est"]["Aciertos_%"], "Peor_caida_prueba_%": p["est"]["Peor_caida_%"]})
    tabla = pd.DataFrame(filas).round(1)
    print("\nRESUMEN (CyM = comprar y mantener)")
    print(tabla.to_string(index=False))
    gana = (tabla["Prueba_estrategia_%"] > tabla["Prueba_CyM_%"]).sum()
    print(f"\nÚltimo año: la estrategia le ganó a comprar y mantener en {gana} de {len(tabla)} activos; "
          f"ganó dinero en {(tabla['Prueba_estrategia_%'] > 0).sum()}.")
    tabla.to_csv("backtest_todos.csv", index=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backtest de la estrategia")
    parser.add_argument("--activo", default=activos.PRINCIPAL)
    parser.add_argument("--todos", action="store_true", help="Resumen de varios activos")
    parser.add_argument("--completo", action="store_true", help="Con --todos: todos los activos")
    args = parser.parse_args()
    if args.todos:
        todos(list(activos.ACTIVOS) if args.completo else activos.SIMULAR)
    else:
        grafica(informe(activos.limpiar(args.activo)))
