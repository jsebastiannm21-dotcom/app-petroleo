# estacional.py - Estacionalidad del petróleo (WTI y Brent): retorno promedio por mes y por día de la semana,
# y % de veces que cada mes subió, en los últimos 5 o 10 años.

from datetime import datetime

import pandas as pd
import yfinance as yf

import activos

MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]


def cierres_10_anios(simbolo):
    """10 años de cierres diarios (se descargan una vez al día y se guardan en la carpeta datos)."""
    archivo = activos.DATOS / f"precios10_{activos._slug(simbolo)}.csv"
    if not archivo.exists() or datetime.fromtimestamp(archivo.stat().st_mtime).date() < datetime.now().date():
        desde = (pd.Timestamp.now().to_period("M").start_time - pd.DateOffset(years=10, months=2)).date()
        d = yf.download(simbolo, start=desde, interval="1d", auto_adjust=False, progress=False)   # 10 años + 2 meses
        if isinstance(d.columns, pd.MultiIndex):
            d.columns = d.columns.get_level_values(0)
        d[["Close"]].rename(columns={"Close": "Cierre"}).dropna().to_csv(archivo)
    return pd.read_csv(archivo, index_col=0, parse_dates=True)["Cierre"]


MESES_LARGOS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
                "noviembre", "diciembre"]


def _ventana(cierre, anios):
    c = cierre[cierre.index >= cierre.index[-1] - pd.DateOffset(years=anios)]
    return c[c > 0]          # Abril 2020: el WTI llegó a valer menos de cero; esos días deforman los promedios


def por_mes(cierre, anios):
    # Cada mes del año debe aparecer 'anios' veces: empezamos un mes antes para tener el cierre del mes previo
    inicio = pd.Timestamp.now().to_period("M").start_time - pd.DateOffset(years=anios, months=1)
    c = cierre[cierre.index >= inicio]
    c = c[c > 0]             # Abril 2020: el WTI llegó a valer menos de cero; esos días deforman los promedios
    mensual = c.resample("ME").last().pct_change().dropna() * 100
    mensual = mensual[mensual.index < pd.Timestamp.now().to_period("M").start_time]     # Sin el mes en curso
    g = mensual.groupby(mensual.index.month)
    return pd.DataFrame({"Mes": [MESES[m - 1] for m in g.mean().index], "Retorno_promedio_%": g.mean().values,
                         "Subio_%": (g.apply(lambda x: (x > 0).mean()) * 100).values, "Años": g.size().values},
                        index=g.mean().index)


def por_dia(cierre, anios):
    c = _ventana(cierre, anios)
    diario = c.pct_change().dropna() * 100
    diario = diario[diario.index.dayofweek < 5]
    g = diario.groupby(diario.index.dayofweek)
    return pd.DataFrame({"Dia": [DIAS[d] for d in g.mean().index], "Retorno_promedio_%": g.mean().values,
                         "Subio_%": (g.apply(lambda x: (x > 0).mean()) * 100).values})


def frase_mes_actual(tabla, nombre):
    mes = datetime.now().month
    if mes not in tabla.index:
        return ""
    f = tabla.loc[mes]
    tendencia = "suele subir" if f["Retorno_promedio_%"] > 0 and f["Subio_%"] >= 50 else \
        "suele bajar" if f["Retorno_promedio_%"] < 0 and f["Subio_%"] < 50 else "no tiene un patrón claro"
    return (f"Estamos en {MESES_LARGOS[mes - 1]}: el {nombre} {tendencia}. Subió en {f['Subio_%']:.0f}% de los "
            f"{int(f['Años'])} años, con un cambio promedio de {f['Retorno_promedio_%']:+.1f}%.")


if __name__ == "__main__":
    for s in ("CL=F", "BZ=F"):
        c = cierres_10_anios(s)
        print(activos.nombre(s), f"{c.index[0].date()} a {c.index[-1].date()}")
        print(frase_mes_actual(por_mes(c, 10), activos.nombre(s)))
        print(por_dia(c, 10).round(2).to_string(index=False))
