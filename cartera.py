# cartera.py - Motor de una cartera (compras y ventas) que usan Mis activos (real) y el Simulador.
# Método de costo promedio: si compras varias veces, el precio de compra es el promedio ponderado.
# Ganancia "en papel" = de lo que todavía tienes; ganancia "realizada" = de lo que ya vendiste.

import pandas as pd

import activos
import estrategia

COLUMNAS = ["Fecha", "Activo", "Tipo", "Precio", "Cantidad", "Moneda", "Nota"]


class Cartera:
    def __init__(self, archivo, extra=(), nube=None):
        """nube = (correo, "real" o "sim"): con Supabase conectado, se guarda en la tabla operaciones."""
        self.archivo = archivo
        self.columnas = COLUMNAS + list(extra)
        self.nube = nube

    def _en_nube(self):
        import nube
        return self.nube is not None and nube.conectado()

    # ---------- Leer y guardar ----------
    def leer(self):
        if self._en_nube():
            import nube
            t = nube.leer_operaciones(*self.nube)
            if t.empty:
                return pd.DataFrame(columns=self.columnas)
            t["Fecha"] = pd.to_datetime(t["Fecha"], format="mixed")
        elif not self.archivo.exists():
            return pd.DataFrame(columns=self.columnas)
        else:
            t = pd.read_csv(self.archivo, encoding="utf-8-sig", parse_dates=["Fecha"])
        for c in self.columnas:
            if c not in t:
                t[c] = "USD" if c == "Moneda" else None
        t = t[self.columnas]
        if "Precio_COP" in self.columnas and pd.to_numeric(t["Precio_COP"], errors="coerce").isna().any():
            t = self._completar_monedas(t)
        return t

    def _monedas(self, fila):
        """Tasa del día de la operación, precio en pesos y en dólares, para una fila."""
        tasa = pd.to_numeric(fila.get("Tasa_COP"), errors="coerce")
        if pd.isna(tasa):
            tasa = activos.tasa_cop_en(fila["Fecha"])
        moneda = fila.get("Moneda") or "USD"
        if moneda == "COP":
            return tasa, fila["Precio"], fila["Precio"] / tasa
        usd = fila["Precio"] / (1.0 if moneda == "USD" else activos.tasa_usd(moneda))
        return tasa, usd * tasa, usd

    def _completar_monedas(self, t):
        """Migración: completa la tasa y los precios en COP y US$ de las filas viejas. No borra nada."""
        try:
            for i in t.index[pd.to_numeric(t["Precio_COP"], errors="coerce").isna()]:
                t.loc[i, ["Tasa_COP", "Precio_COP", "Precio_USD"]] = self._monedas(t.loc[i])
            self._guardar(t)
        except Exception:
            pass                       # Sin internet: se intenta otra vez después; las filas quedan como estaban
        return t

    def _guardar(self, tabla):
        tabla = tabla.sort_values("Fecha", kind="stable")[self.columnas]
        if self._en_nube():
            import nube
            nube.reemplazar_operaciones(*self.nube, tabla)
        else:
            tabla.to_csv(self.archivo, index=False, encoding="utf-8-sig")

    def borrar_todo(self):
        """Borra todas las operaciones (solo lo usa «Reiniciar simulador», después de un respaldo)."""
        if self._en_nube():
            import nube
            nube.reemplazar_operaciones(*self.nube, pd.DataFrame(columns=self.columnas))
        else:
            self.archivo.unlink(missing_ok=True)

    def tengo(self, activo):
        t = self.leer()
        t = t[t["Activo"] == activo]
        return float(t["Cantidad"].where(t["Tipo"] == "COMPRA", -t["Cantidad"]).sum())

    def registrar(self, activo, tipo, precio, cantidad, fecha, nota="", moneda=None, **extra):
        """Agrega una compra o venta. Devuelve un mensaje de error o None si salió bien."""
        activo, tipo = activos.limpiar(activo), tipo.upper()
        if precio is None or cantidad is None or precio <= 0 or cantidad <= 0:
            return "El precio y la cantidad deben ser mayores que cero."
        if tipo == "VENTA" and cantidad > self.tengo(activo) + 1e-9:
            return f"No puedes vender {cantidad:g} de {activo}: solo tienes {self.tengo(activo):g}."
        fila = {"Fecha": pd.Timestamp(fecha), "Activo": activo, "Tipo": tipo, "Precio": float(precio),
                "Cantidad": float(cantidad), "Moneda": moneda or activos.moneda(activo), "Nota": nota, **extra}
        if "Precio_COP" in self.columnas and "Precio_COP" not in extra:       # Guarda ambas monedas
            fila["Tasa_COP"], fila["Precio_COP"], fila["Precio_USD"] = self._monedas(fila)
        self._guardar(pd.concat([self.leer(), pd.DataFrame([fila])], ignore_index=True))
        return None

    def reemplazar(self, tabla):
        """Guarda la tabla editada (cambios y filas borradas). Devuelve un mensaje de error o None."""
        tabla = tabla.dropna(how="all").copy()
        if tabla[["Fecha", "Activo", "Tipo", "Precio", "Cantidad"]].isna().any().any():
            return "Hay filas incompletas: llena fecha, activo, tipo, precio y cantidad."
        tabla["Activo"] = tabla["Activo"].astype(str).map(activos.limpiar)
        tabla["Tipo"] = tabla["Tipo"].astype(str).str.upper()
        if not tabla["Tipo"].isin(["COMPRA", "VENTA"]).all():
            return "El tipo debe ser COMPRA o VENTA."
        if (tabla["Precio"] <= 0).any() or (tabla["Cantidad"] <= 0).any():
            return "El precio y la cantidad deben ser mayores que cero."
        tabla["Fecha"] = pd.to_datetime(tabla["Fecha"])
        tabla = tabla.sort_values("Fecha", kind="stable")
        saldo = tabla["Cantidad"].where(tabla["Tipo"] == "COMPRA", -tabla["Cantidad"]).groupby(tabla["Activo"]).cumsum()
        if (saldo < -1e-9).any():
            return f"Con estos cambios vendes más de lo que tenías en: {', '.join(sorted(tabla.loc[saldo < -1e-9, 'Activo'].unique()))}."
        for c in self.columnas:
            if c not in tabla:
                tabla[c] = ""
        tabla["Nota"] = tabla["Nota"].fillna("")
        tabla["Moneda"] = tabla["Moneda"].replace("", None).fillna(tabla["Activo"].map(activos.moneda))
        self._guardar(tabla)
        return None

    # ---------- Cálculos ----------
    def con_resultado(self):
        """El historial con el resultado de cada venta (ganancia realizada a costo promedio)."""
        return self._recorrer()[0]

    def _recorrer(self):
        """Recorre las operaciones en orden. Devuelve (historial con Resultado, {activo: [cantidad, costo]})."""
        t = self.leer().sort_values("Fecha", kind="stable").copy()
        t["Resultado"] = None
        cop = pd.to_numeric(t.get("Precio_COP"), errors="coerce") if "Precio_COP" in t else pd.Series(float("nan"), t.index)
        usd = pd.to_numeric(t.get("Precio_USD"), errors="coerce") if "Precio_USD" in t else pd.Series(float("nan"), t.index)
        estado = {}                     # activo -> [cantidad, costo (moneda del activo), costo en COP, costo en US$]
        for i, op in t.iterrows():
            cant, costo, c_cop, c_usd = estado.get(op["Activo"], [0.0, 0.0, 0.0, 0.0])
            if op["Tipo"] == "COMPRA":
                cant, costo = cant + op["Cantidad"], costo + op["Precio"] * op["Cantidad"]
                c_cop += (cop[i] if pd.notna(cop[i]) else 0) * op["Cantidad"]
                c_usd += (usd[i] if pd.notna(usd[i]) else 0) * op["Cantidad"]
            else:
                parte = op["Cantidad"] / cant if cant else 0
                promedio = costo / cant if cant else 0
                t.at[i, "Resultado"] = (op["Precio"] - promedio) * op["Cantidad"]
                cant, costo = cant - op["Cantidad"], costo - promedio * op["Cantidad"]
                c_cop, c_usd = c_cop * (1 - parte), c_usd * (1 - parte)
            estado[op["Activo"]] = [cant, costo, c_cop, c_usd]
        return t, estado

    def posiciones(self, solo_abiertas=True, con_precio=True):
        """Una fila por activo: cantidad, precio promedio, ganancia en papel, realizada y sugerencia."""
        filas = []
        t, estado = self._recorrer()
        for activo, ops in t.groupby("Activo", sort=False):
            cant, costo, c_cop, c_usd = estado[activo]
            compras = ops[ops["Tipo"] == "COMPRA"]
            abierta = cant > 1e-9
            if solo_abiertas and not abierta:
                continue
            fila = {"Activo": activo, "Nombre": activos.nombre(activo), "Moneda": ops["Moneda"].iloc[-1] or "USD",
                    "Cantidad": round(cant, 6), "Precio_compra": costo / cant if abierta else None,
                    "Invertido": costo if abierta else 0.0, "Fecha_compra": compras["Fecha"].max(),
                    "Invertido_COP": c_cop if abierta else 0.0, "Invertido_USD": c_usd if abierta else 0.0,
                    "Ganancia_realizada": float(pd.to_numeric(ops["Resultado"], errors="coerce").fillna(0).sum())}
            if abierta:
                fila["Stop"] = fila["Precio_compra"] * (1 - estrategia.stop_de(activo) / 100)
                fila["Objetivo"] = fila["Precio_compra"] * (1 + estrategia.OBJETIVO / 100)
            if con_precio and abierta:
                precio = ultimo_cierre(activo)
                fila["Precio_actual"] = precio
                fila["Valor_actual"] = precio * cant if precio else None
                if precio:                                # Valor de hoy en las dos monedas (tasa de hoy)
                    fila["Valor_USD"] = fila["Valor_actual"] / activos.tasa_usd(fila["Moneda"])
                    fila["Valor_COP"] = fila["Valor_USD"] * activos.tasa_usd("COP")
                fila["Ganancia_papel"] = fila["Valor_actual"] - costo if precio else None
                fila["Ganancia_%"] = (precio / fila["Precio_compra"] - 1) * 100 if precio else None
                fila["Sugerencia"], fila["Motivo"] = sugerencia(activo, fila["Ganancia_%"])
            filas.append(fila)
        return pd.DataFrame(filas)

    def valor_historico(self, dias):
        """Valor diario (en la moneda de cada activo) de lo que tenías cada día, por activo y total."""
        t = self.leer()
        if t.empty:
            return pd.DataFrame()
        fin = pd.Timestamp.now().normalize()
        inicio = fin - pd.Timedelta(days=dias)
        tabla = {}
        for activo, ops in t.groupby("Activo"):
            try:
                cierres = pd.read_csv(activos.ruta_precios(activo), index_col="Fecha", parse_dates=True)["Cierre"]
            except Exception:
                continue
            cierres = cierres[cierres.index >= inicio - pd.Timedelta(days=7)]
            mov = ops["Cantidad"].where(ops["Tipo"] == "COMPRA", -ops["Cantidad"])
            cantidad = mov.groupby(ops["Fecha"].dt.normalize()).sum().cumsum()
            cantidad = cantidad.reindex(cantidad.index.union(cierres.index)).ffill().fillna(0)
            tabla[activo] = (cantidad.reindex(cierres.index) * cierres)
        valores = pd.DataFrame(tabla).ffill()
        valores = valores[valores.index >= inicio]
        valores["Total"] = valores.sum(axis=1)
        return valores


def ultimo_cierre(simbolo):
    try:
        activos.asegurar_datos(simbolo)
        return float(pd.read_csv(activos.ruta_precios(simbolo), usecols=["Cierre"])["Cierre"].iloc[-1])
    except Exception:
        return None


def sugerencia(simbolo, ganancia_pct):
    """'Vender' si tocó el stop loss o el objetivo, o si la probabilidad de subida bajó de 50%."""
    if ganancia_pct is None:
        return "Mantener", "Sin precio actual"
    stop = estrategia.stop_de(simbolo)
    if ganancia_pct <= -stop:
        return "Vender", f"Pierde {ganancia_pct:.1f}%: pasó el stop loss de -{stop:g}%"
    if ganancia_pct >= estrategia.OBJETIVO:
        return "Vender", f"Gana {ganancia_pct:+.1f}%: llegó al objetivo de +{estrategia.OBJETIVO}%"
    try:
        r = estrategia.analizar(simbolo)
    except Exception:
        return "Mantener", "No se pudo analizar el activo"
    if r["suficiente"] and r["prob"] < estrategia.ALERTA_BAJA:
        return "Vender", f"La probabilidad de subida bajó a {r['prob']:.0f}% (menos de 50%)"
    return "Mantener", f"Va {ganancia_pct:+.1f}%, entre el stop loss y el objetivo"
