# errores.py - Diario de errores: cuando una venta cierra en pérdida, la app te pide la razón en un clic
# y luego muestra tus errores más repetidos. Se guarda en diario_errores.csv (nunca borra lo anterior).
# Prueba:  python errores.py

import pandas as pd

import activos

ARCHIVO = activos.CARPETA / "diario_errores.csv"
RAZONES = ["Entré tarde", "Ignoré la señal", "Noticia inesperada", "Stop muy ajustado", "Otra"]
COLUMNAS = ["Fecha_venta", "Cartera", "Activo", "Resultado", "Razon", "Anotado"]


def leer():
    import nube
    if nube.conectado() and ARCHIVO == activos.CARPETA / "diario_errores.csv":   # En las pruebas, archivo temporal
        filas = nube.cliente().table("diario_errores").select("*").eq("email", nube.usuario()).execute().data
        return pd.DataFrame(filas, columns=["id", "email"] + COLUMNAS)[COLUMNAS]
    return pd.read_csv(ARCHIVO, encoding="utf-8-sig") if ARCHIVO.exists() else pd.DataFrame(columns=COLUMNAS)


def pendientes(cartera, nombre):
    """Ventas con pérdida que todavía no tienen razón anotada."""
    t = cartera.con_resultado()
    perdidas = t[(t["Tipo"] == "VENTA") & (pd.to_numeric(t["Resultado"], errors="coerce") < 0)]
    hechos = leer()
    ya = set(zip(hechos["Fecha_venta"].astype(str), hechos["Cartera"], hechos["Activo"]))
    return perdidas[[(str(f), nombre, a) not in ya for f, a in zip(perdidas["Fecha"], perdidas["Activo"])]]


def anotar(fecha_venta, nombre, activo, resultado, razon):
    fila = pd.DataFrame([{"Fecha_venta": str(fecha_venta), "Cartera": nombre, "Activo": activo,
                          "Resultado": round(float(resultado), 4), "Razon": razon,
                          "Anotado": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")}])
    import nube
    if nube.conectado() and ARCHIVO == activos.CARPETA / "diario_errores.csv":
        nube.cliente().table("diario_errores").insert({**fila.iloc[0].to_dict(), "email": nube.usuario()}).execute()
        return
    pd.concat([leer(), fila], ignore_index=True).to_csv(ARCHIVO, index=False, encoding="utf-8-sig")


def mas_repetidos():
    """Cuántas veces anotaste cada razón, de más a menos."""
    return leer()["Razon"].value_counts().rename_axis("Razón").reset_index(name="Veces")


if __name__ == "__main__":
    import pathlib
    import tempfile

    import cartera
    tmp = pathlib.Path(tempfile.mkdtemp())
    ARCHIVO = tmp / "diario.csv"                          # La prueba nunca toca el diario real
    cartera.ultimo_cierre = lambda s: 90.0
    c = cartera.Cartera(tmp / "ops.csv")
    c.registrar("X", "COMPRA", 100, 1, "2026-10-01 10:00")
    c.registrar("X", "VENTA", 95, 1, "2026-10-03 10:00")        # Pérdida: -5
    c.registrar("Y", "COMPRA", 100, 1, "2026-10-01 10:00")
    c.registrar("Y", "VENTA", 105, 1, "2026-10-03 10:00")       # Ganancia: no se pregunta
    p = pendientes(c, "Prueba")
    assert list(p["Activo"]) == ["X"], p
    anotar(p["Fecha"].iloc[0], "Prueba", "X", p["Resultado"].iloc[0], "Entré tarde")
    assert pendientes(c, "Prueba").empty and mas_repetidos()["Veces"].iloc[0] == 1
    print("Diario de errores: pruebas OK")
