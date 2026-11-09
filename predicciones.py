# predicciones.py - Guarda cada predicción a 5 días (Prophet, Monte Carlo y Kronos) y, cuando pasa su plazo,
# la compara con el precio real: ¿acertó la dirección (sube/baja)? ¿quedó dentro del rango?
# Uso:  python predicciones.py              (registra las de hoy y revisa las vencidas)

import sys

import pandas as pd

import activos
import montecarlo

ARCHIVO = activos.CARPETA / "predicciones.csv"
HORIZONTE = 5            # Días de mercado
COLUMNAS = ["Fecha", "Activo", "Metodo", "Precio_inicial", "Prediccion", "Banda_baja", "Banda_alta",
            "Fecha_objetivo", "Precio_real", "Acierto_direccion", "Dentro_rango", "Error_%"]


def leer():
    if not ARCHIVO.exists():
        return pd.DataFrame(columns=COLUMNAS)
    return pd.read_csv(ARCHIVO, encoding="utf-8-sig", parse_dates=["Fecha", "Fecha_objetivo"])


def predecir(simbolo, metodos=("Prophet", "Monte Carlo", "Kronos")):
    """Predicción del precio dentro de 5 días de mercado con cada método disponible."""
    import forecast
    import kronos_pronostico
    cierre = pd.read_csv(activos.ruta_precios(simbolo), index_col="Fecha", parse_dates=True)["Cierre"]
    futuro = pd.bdate_range(cierre.index[-1] + pd.Timedelta(days=1), periods=HORIZONTE)
    salida = {}
    if "Monte Carlo" in metodos:
        _, r = montecarlo.resumen(montecarlo.caminos(cierre, HORIZONTE), range(HORIZONTE + 1))
        salida["Monte Carlo"] = (r["mediana"], r["p10"], r["p90"])
    if "Prophet" in metodos:
        p = forecast.con_prophet(cierre, futuro).iloc[-1]
        salida["Prophet"] = (p["Central"], p["Banda_baja"], p["Banda_alta"])
    if "Kronos" in metodos and kronos_pronostico.activado() and kronos_pronostico.disponible()[0]:
        salida["Kronos"] = (float(kronos_pronostico.pronosticar(simbolo, HORIZONTE)["Central"].iloc[-1]), None, None)
    return float(cierre.iloc[-1]), cierre.index[-1], futuro[-1], salida


def registrar(simbolos):
    """Guarda las predicciones de hoy (una por activo, método y fecha de datos)."""
    t = leer()
    nuevas = []
    for s in simbolos:
        try:
            inicial, fecha, objetivo, salida = predecir(s)
        except Exception as error:
            print(f"No pude predecir {s}: {error}")
            continue
        for metodo, (pred, baja, alta) in salida.items():
            if ((t["Activo"] == s) & (t["Metodo"] == metodo) & (t["Fecha"] == fecha)).any():
                continue
            nuevas.append({"Fecha": fecha, "Activo": s, "Metodo": metodo, "Precio_inicial": inicial, "Prediccion": pred,
                           "Banda_baja": baja, "Banda_alta": alta, "Fecha_objetivo": objetivo})
    if nuevas:
        t = pd.concat([t, pd.DataFrame(nuevas)], ignore_index=True)
        t.to_csv(ARCHIVO, index=False, encoding="utf-8-sig")
    return len(nuevas)


def evaluar():
    """Compara con el precio real las predicciones cuyo plazo ya pasó."""
    t = leer()
    for i in t[t["Precio_real"].isna()].index:
        try:
            cierre = pd.read_csv(activos.ruta_precios(t.at[i, "Activo"]), index_col="Fecha", parse_dates=True)["Cierre"]
        except Exception:
            continue
        despues = cierre[cierre.index >= t.at[i, "Fecha_objetivo"]]
        if despues.empty:
            continue
        real, ini, pred = float(despues.iloc[0]), t.at[i, "Precio_inicial"], t.at[i, "Prediccion"]
        t.at[i, "Precio_real"] = real
        t.at[i, "Acierto_direccion"] = bool((pred > ini) == (real > ini))
        t.at[i, "Error_%"] = abs(pred - real) / real * 100
        if pd.notna(t.at[i, "Banda_baja"]):
            t.at[i, "Dentro_rango"] = bool(t.at[i, "Banda_baja"] <= real <= t.at[i, "Banda_alta"])
    t.to_csv(ARCHIVO, index=False, encoding="utf-8-sig")
    return t


def tasa_aciertos(simbolo=None):
    """Por método: % de aciertos de dirección, % dentro del rango, error promedio y cuántas revisadas."""
    t = leer()
    t = t[t["Precio_real"].notna()]
    if simbolo:
        t = t[t["Activo"] == simbolo]
    if t.empty:
        return pd.DataFrame(columns=["Metodo", "Aciertos_%", "Dentro_rango_%", "Error_%", "Revisadas"])
    es = lambda col: t[col].astype(str).str.lower() == "true"
    t = t.assign(_dir=es("Acierto_direccion"), _rango=es("Dentro_rango"))
    g = t.groupby("Metodo")
    return pd.DataFrame({"Aciertos_%": g["_dir"].mean() * 100, "Dentro_rango_%": g["_rango"].mean() * 100,
                         "Error_%": g["Error_%"].mean(), "Revisadas": g.size()}).reset_index()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(f"Nuevas: {registrar(activos.SIMULAR)}")
    evaluar()
    print(tasa_aciertos())
