# aciertos.py - Registro de aciertos: guarda cada sugerencia de COMPRAR con su fecha y precio,
# y a los 5 días de mercado revisa si el precio subió (acierto) o no.

import pandas as pd

import activos
import estrategia

ARCHIVO = activos.CARPETA / "registro_sugerencias.csv"
COLUMNAS = ["Fecha", "Activo", "Precio", "Decision_app", "Decision_unificada", "Fecha_revision", "Precio_5d", "Acierto"]


def leer():
    if not ARCHIVO.exists():
        return pd.DataFrame(columns=COLUMNAS)
    return pd.read_csv(ARCHIVO, encoding="utf-8-sig", parse_dates=["Fecha", "Fecha_revision"])


def registrar(resultados):
    """Anota las sugerencias COMPRAR de hoy (una por activo y día). resultados = {símbolo: analizar()}."""
    import analisis_claude
    t = leer()
    nuevas = []
    for simbolo, r in resultados.items():
        if r["decision"] != "COMPRAR":
            continue
        fecha = pd.Timestamp(r["fecha"]).normalize()
        if ((t["Activo"] == simbolo) & (t["Fecha"] == fecha)).any():
            continue
        nuevas.append({"Fecha": fecha, "Activo": simbolo, "Precio": r["precio"], "Decision_app": r["decision"],
                       "Decision_unificada": analisis_claude.decision_unificada(r)[0]})
    if nuevas:
        pd.concat([t, pd.DataFrame(nuevas)], ignore_index=True).to_csv(ARCHIVO, index=False, encoding="utf-8-sig")
    return len(nuevas)


def evaluar():
    """Revisa las sugerencias que ya cumplieron 5 días de mercado."""
    t = leer()
    pendientes = t["Acierto"].isna()
    for i in t[pendientes].index:
        try:
            cierres = pd.read_csv(activos.ruta_precios(t.at[i, "Activo"]), index_col="Fecha", parse_dates=True)["Cierre"]
        except Exception:
            continue
        despues = cierres[cierres.index > t.at[i, "Fecha"]]
        if len(despues) >= estrategia.DIAS_ADELANTE:
            t.at[i, "Fecha_revision"] = despues.index[estrategia.DIAS_ADELANTE - 1]
            t.at[i, "Precio_5d"] = float(despues.iloc[estrategia.DIAS_ADELANTE - 1])
            t.at[i, "Acierto"] = bool(t.at[i, "Precio_5d"] > t.at[i, "Precio"])
    t.to_csv(ARCHIVO, index=False, encoding="utf-8-sig")
    return t


def resumen():
    """Porcentaje de aciertos de la app sola y de la decisión unificada (COMPRAR CONFIRMADO)."""
    t = leer()
    revisadas = t[t["Acierto"].notna()].copy()
    revisadas["Acierto"] = revisadas["Acierto"].astype(str).str.lower() == "true"
    conf = revisadas[revisadas["Decision_unificada"] == "COMPRAR CONFIRMADO"]
    pct = lambda x: x["Acierto"].mean() * 100 if len(x) else None
    return {"app_%": pct(revisadas), "app_n": len(revisadas), "unificada_%": pct(conf), "unificada_n": len(conf),
            "pendientes": int(t["Acierto"].isna().sum())}
