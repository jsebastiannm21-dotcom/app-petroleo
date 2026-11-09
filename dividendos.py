# dividendos.py - Dividendos (largo plazo): rendimiento, frecuencia, próximas fechas, lo cobrado y proyección.
# Uso:  python dividendos.py      (actualiza dividendos.csv con todos los activos que pagan dividendos)

import sys
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import yfinance as yf

import activos

ARCHIVO = activos.CARPETA / "dividendos.csv"
FRECUENCIA = {12: "Mensual", 4: "Trimestral", 2: "Semestral", 1: "Anual"}


def historial(simbolo):
    """Dividendos pagados por acción (índice = fecha de corte, sin zona horaria)."""
    d = yf.Ticker(simbolo).dividends
    if d.empty:
        return d
    d.index = d.index.tz_localize(None)
    return d


def _ficha(simbolo):
    try:
        d = historial(simbolo)
        if d.empty:
            return None
        hoy = pd.Timestamp.now().normalize()
        ultimo_anio = d[d.index > hoy - pd.Timedelta(days=365)]
        if ultimo_anio.empty:
            return None
        precio = float(pd.read_csv(activos.ruta_precios(simbolo), usecols=["Cierre"])["Cierre"].iloc[-1])
        anual = float(ultimo_anio.sum())
        cal = yf.Ticker(simbolo).calendar or {}
        corte, pago = cal.get("Ex-Dividend Date"), cal.get("Dividend Date")
        corte = pd.Timestamp(corte) if corte is not None and pd.Timestamp(corte) >= hoy else None
        pago = pd.Timestamp(pago) if pago is not None and pd.Timestamp(pago) >= hoy else None
        estimada = corte is None
        if estimada:                                   # Estimamos con el intervalo típico entre pagos
            paso = d.index.to_series().diff().dt.days.tail(6).median()
            corte = d.index[-1] + pd.Timedelta(days=paso if pd.notna(paso) else 365)
            while corte < hoy:
                corte += pd.Timedelta(days=paso if pd.notna(paso) else 365)
        return {"Activo": simbolo, "Nombre": activos.nombre(simbolo), "Mercados": ";".join(activos.mercados(simbolo)),
                "Precio": precio, "Dividendo_anual": anual, "Rendimiento_%": anual / precio * 100,
                "Frecuencia": FRECUENCIA.get(len(ultimo_anio), f"{len(ultimo_anio)} al año"),
                "Proximo_corte": corte.date(), "Corte_estimado": estimada,
                "Proximo_pago": pago.date() if pago is not None else None}
    except Exception:
        return None


def actualizar(simbolos=None):
    # Cripto, futuros e índices no pagan dividendos: solo se revisan acciones y ETFs
    simbolos = simbolos or [s for s, d in activos.ACTIVOS.items() if d["tipo"] in ("acción", "etf")]
    with ThreadPoolExecutor(8) as pool:
        filas = [f for f in pool.map(_ficha, simbolos) if f]
    tabla = pd.DataFrame(filas).sort_values("Rendimiento_%", ascending=False)
    tabla.to_csv(ARCHIVO, index=False, encoding="utf-8-sig")
    return tabla


def leer():
    if not ARCHIVO.exists():
        return pd.DataFrame()
    return pd.read_csv(ARCHIVO, encoding="utf-8-sig", parse_dates=["Proximo_corte", "Proximo_pago"])


def cobrados(cartera):
    """Dividendos que te han pagado (US$) y los que esperas en los próximos 12 meses, por activo."""
    ops = cartera.leer()
    tabla = leer()
    filas = []
    for simbolo, o in ops.groupby("Activo"):
        try:
            d = historial(simbolo)
        except Exception:
            continue
        if d.empty:
            continue
        mov = o["Cantidad"].where(o["Tipo"] == "COMPRA", -o["Cantidad"])
        pagado = 0.0
        for fecha_corte, monto in d[d.index >= o["Fecha"].min()].items():
            pagado += monto * mov[o["Fecha"] < fecha_corte].sum()      # Acciones que tenías antes del corte
        cantidad = mov.sum()
        anual = tabla.set_index("Activo")["Dividendo_anual"].get(simbolo, 0.0) if len(tabla) else 0.0
        filas.append({"Activo": simbolo, "Pagado_US$": pagado, "Esperado_12m_US$": anual * max(cantidad, 0)})
    return pd.DataFrame(filas, columns=["Activo", "Pagado_US$", "Esperado_12m_US$"])


def proyeccion(aporte_mensual, rendimiento_anual_pct, anios):
    """Valor final aportando cada mes y reinvirtiendo los dividendos (rendimiento total anual)."""
    r = rendimiento_anual_pct / 100 / 12
    meses = anios * 12
    return aporte_mensual * meses if r == 0 else aporte_mensual * ((1 + r) ** meses - 1) / r


def crecimiento_historico(simbolo):
    """Crecimiento anual promedio del precio en los datos descargados (5 años)."""
    c = pd.read_csv(activos.ruta_precios(simbolo), index_col="Fecha", parse_dates=True)["Cierre"]
    anios = (c.index[-1] - c.index[0]).days / 365.25
    return ((c.iloc[-1] / c.iloc[0]) ** (1 / anios) - 1) * 100


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    assert abs(proyeccion(100, 0, 10) - 12_000) < 1e-9               # Sin rendimiento: solo lo aportado
    assert proyeccion(100, 8, 20) > proyeccion(100, 8, 10) * 2        # El interés compuesto acelera
    t = actualizar()
    print(f"{len(t)} activos pagan dividendos.")
    print(t[t["Activo"].isin(activos.DIVIDENDOS)][["Activo", "Rendimiento_%", "Frecuencia", "Proximo_corte",
                                                     "Corte_estimado", "Proximo_pago"]].round(2).to_string(index=False))
