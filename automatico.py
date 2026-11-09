# automatico.py - Cómo le va al MODO AUTOMÁTICO del simulador (uso del superadmin):
# - Cada compra automática se empareja con su venta (o con el precio de hoy si sigue abierta).
# - Se compara con "comprar y mantener": haber comprado lo mismo y no vender hasta hoy.
# - Resumen diario de ganancia y pérdida del simulador (se guarda una foto del total cada noche).
# Prueba:  python automatico.py

from datetime import datetime

import pandas as pd

import activos

HISTORIAL = activos.CARPETA / "simulador_historial.csv"   # Una fila por día con el total del simulador


def pares(ops):
    """[(compra, venta o None)] emparejando cada compra con la siguiente venta del mismo activo (en orden)."""
    resultado = []
    for _, g in ops.sort_values("Fecha", kind="stable").groupby("Activo"):
        abiertas = []
        for _, op in g.iterrows():
            if op["Tipo"] == "COMPRA":
                abiertas.append(op)
            elif abiertas:
                resultado.append((abiertas.pop(0), op))
        resultado += [(c, None) for c in abiertas]
    return resultado


def comparar(ops, precio_hoy, tasa_hoy, costo_venta=lambda monto, moneda: 0.0):
    """Automático vs. comprar y mantener, solo con las compras de origen 'automático'.
    precio_hoy(símbolo) y tasa_hoy(moneda) dan el precio y los pesos por unidad de hoy."""
    filas = []
    for c, v in pares(ops):
        if str(c.get("Origen", "")) != "automático":
            continue
        tasa_c = float(c["Tasa_COP"]) if pd.notna(c.get("Tasa_COP")) else tasa_hoy(c["Moneda"])
        entrada = c["Precio"] * c["Cantidad"] * tasa_c + float(pd.to_numeric(c.get("Costo_COP"), errors="coerce") or 0)
        hoy = precio_hoy(c["Activo"]) * c["Cantidad"] * tasa_hoy(c["Moneda"])
        mantener = hoy - costo_venta(hoy, c["Moneda"])
        if v is not None:
            bruto = v["Precio"] * c["Cantidad"] * float(v["Tasa_COP"] if pd.notna(v.get("Tasa_COP")) else tasa_hoy(c["Moneda"]))
            salida = bruto - float(pd.to_numeric(v.get("Costo_COP"), errors="coerce") or 0) * (c["Cantidad"] / v["Cantidad"])
        else:
            salida = mantener                            # Sigue abierta: vale lo de hoy
        filas.append({"Activo": c["Activo"], "Compra": c["Fecha"], "Venta": v["Fecha"] if v is not None else None,
                      "Invertido_COP": entrada, "Automatico_%": (salida / entrada - 1) * 100,
                      "Mantener_%": (mantener / entrada - 1) * 100, "Cerrada": v is not None})
    t = pd.DataFrame(filas)
    if t.empty:
        return t, None
    peso = t["Invertido_COP"] / t["Invertido_COP"].sum()
    cerradas = t[t["Cerrada"]]
    resumen = {"operaciones": len(t), "cerradas": len(cerradas),
               "auto_%": float((t["Automatico_%"] * peso).sum()), "mantener_%": float((t["Mantener_%"] * peso).sum()),
               "aciertos_auto_%": float((cerradas["Automatico_%"] > 0).mean() * 100) if len(cerradas) else None,
               "aciertos_mantener_%": float((t["Mantener_%"] > 0).mean() * 100),
               "peor_auto_%": float(t["Automatico_%"].min()), "peor_mantener_%": float(t["Mantener_%"].min())}
    return t, resumen


def comparar_simulador():
    """La comparación con los datos reales del simulador."""
    import cartera
    import comisiones
    import simulador
    return comparar(simulador.cartera.leer(), cartera.ultimo_cierre, simulador.tasa_a_pesos,
                    lambda monto, moneda: comisiones.costo(monto, moneda)["total"])


def foto_del_dia(total):
    """Guarda el total del simulador de hoy (reemplaza la foto de hoy si ya había). Devuelve la tabla."""
    hoy = datetime.now().strftime("%Y-%m-%d")
    t = pd.read_csv(HISTORIAL) if HISTORIAL.exists() else pd.DataFrame(columns=["Fecha", "Total_COP"])
    t = pd.concat([t[t["Fecha"] != hoy], pd.DataFrame([{"Fecha": hoy, "Total_COP": round(float(total), 2)}])])
    t = t.sort_values("Fecha")
    t.to_csv(HISTORIAL, index=False)
    return t


def resumen_diario():
    """Texto para Telegram: ganancia o pérdida del día del simulador y operaciones automáticas de hoy."""
    import simulador
    s = simulador.resumen()
    t = foto_del_dia(s["total"])
    ayer = float(t["Total_COP"].iloc[-2]) if len(t) > 1 else s["inicial"]
    dia = s["total"] - ayer
    ops = simulador.cartera.leer()
    hoy = ops[(pd.to_datetime(ops["Fecha"]).dt.date == datetime.now().date()) & (ops.get("Origen") == "automático")] \
        if len(ops) else ops
    lineas = [f"🤖 Simulador hoy ({simulador.modo()}): {'+' if dia >= 0 else '-'}{simulador.pesos(abs(dia))} "
              f"({dia / ayer * 100:+.2f}%) · total {simulador.pesos(s['total'])} ({s['ganancia_%']:+.1f}% desde el inicio)."]
    if len(hoy):
        lineas.append(f"Operaciones automáticas de hoy: {len(hoy)} ("
                      + ", ".join(f"{o['Tipo'].lower()} {o['Activo']}" for _, o in hoy.iterrows()) + ").")
    return "\n".join(lineas)


if __name__ == "__main__":
    ops = pd.DataFrame([
        {"Fecha": "2026-10-01", "Activo": "A", "Tipo": "COMPRA", "Precio": 100, "Cantidad": 1, "Moneda": "USD",
         "Tasa_COP": 4000, "Costo_COP": 0, "Origen": "automático"},
        {"Fecha": "2026-10-05", "Activo": "A", "Tipo": "VENTA", "Precio": 110, "Cantidad": 1, "Moneda": "USD",
         "Tasa_COP": 4000, "Costo_COP": 0, "Origen": "automático"},
        {"Fecha": "2026-10-06", "Activo": "B", "Tipo": "COMPRA", "Precio": 50, "Cantidad": 2, "Moneda": "USD",
         "Tasa_COP": 4000, "Costo_COP": 0, "Origen": "automático"},
        {"Fecha": "2026-10-07", "Activo": "C", "Tipo": "COMPRA", "Precio": 10, "Cantidad": 1, "Moneda": "USD",
         "Tasa_COP": 4000, "Costo_COP": 0, "Origen": "manual"}])
    hoy = {"A": 120.0, "B": 45.0, "C": 99.0}
    t, r = comparar(ops, hoy.get, lambda m: 4000.0)
    assert r["operaciones"] == 2 and r["cerradas"] == 1                 # La compra manual no cuenta
    assert abs(t.loc[t["Activo"] == "A", "Automatico_%"].iloc[0] - 10) < 1e-9   # Vendió en 110: +10%
    assert abs(t.loc[t["Activo"] == "A", "Mantener_%"].iloc[0] - 20) < 1e-9     # Manteniendo, hoy vale 120: +20%
    assert abs(r["peor_auto_%"] + 10) < 1e-9 and r["aciertos_auto_%"] == 100     # B sigue abierta: 45 vs 50 = -10%
    print("Automático: pruebas OK")
