# semanal.py - Cierre de cada viernes (o último día hábil de la semana) de todos los activos,
# en cierres_semanales.csv. Nunca borra lo guardado: solo agrega las semanas nuevas.
# Uso:  python semanal.py

import pandas as pd

import activos

ARCHIVO = activos.CARPETA / "cierres_semanales.csv"


def leer():
    if not ARCHIVO.exists():
        return pd.DataFrame(columns=["Fecha", "Activo", "Cierre"])
    return pd.read_csv(ARCHIVO, encoding="utf-8-sig", parse_dates=["Fecha"])


def actualizar():
    """Agrega las semanas terminadas que todavía no están guardadas. Devuelve cuántas filas nuevas."""
    guardado = leer()
    ya = set(zip(guardado["Fecha"], guardado["Activo"]))
    nuevas = []
    for s in activos.ACTIVOS:
        try:
            c = pd.read_csv(activos.ruta_precios(s), index_col="Fecha", parse_dates=True)["Cierre"]
        except Exception:
            continue
        viernes = c.resample("W-FRI").last().dropna()
        viernes = viernes[viernes.index <= c.index[-1]]          # Solo semanas que ya cerraron
        nuevas += [{"Fecha": f, "Activo": s, "Cierre": round(float(v), 4)}
                   for f, v in viernes.items() if (f, s) not in ya]
    if nuevas:
        tabla = pd.concat([guardado, pd.DataFrame(nuevas)], ignore_index=True).sort_values(["Fecha", "Activo"])
        tabla.to_csv(ARCHIVO, index=False, encoding="utf-8-sig")
    return len(nuevas)


if __name__ == "__main__":
    antes = len(leer())
    print(f"{actualizar()} cierres nuevos (había {antes}).")
    assert actualizar() == 0                                     # Correrlo dos veces no duplica
    print("Sin duplicados al repetir: OK")
