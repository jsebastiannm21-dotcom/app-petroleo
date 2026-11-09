# simulador.py - Juego con plata virtual: UNA cuenta en pesos colombianos.
# - Modo automático: compra y vende solo con las señales. Modo manual: tú compras y vendes.
# - Compras y ventas al precio real del momento (si el mercado está cerrado, el último cierre).
# - Saldo inicial editable (por defecto 100.000 COP). Meta del mes: +15%.
# Uso:  python simulador.py                 (revisión automática de activos.SIMULAR y compras abiertas)
#       python simulador.py --saldo 200000  (cambia el saldo inicial y reinicia)
#       python simulador.py --reiniciar
#       python simulador.py --modo manual

import argparse
import json
from datetime import datetime

import pandas as pd

import activos
import comisiones
import nube
import estrategia
from cartera import Cartera

CONFIG = activos.CARPETA / "simulador_config.json"
ARCHIVO = activos.CARPETA / "simulador_operaciones.csv"
FRACCION = 0.20          # En automático, cada compra usa el 20% del saldo total
MINIMO_COP = 1_000
_carteras = {}


def _cartera_de(email):
    """El simulador personal del usuario o, si eligió un evento, su simulador de ese evento (uno por evento)."""
    ev = nube.EVENTO.get()
    clave = (email, ev["id"] if ev else None)
    if clave not in _carteras:
        propio = email == nube.superadmin() and not ev  # El simulador de siempre es el personal del superadmin
        archivo = ARCHIVO if propio else activos.CARPETA / (
            f"simulador_{activos._slug(email)}" + (f"_ev_{ev['id']}" if ev else "") + ".csv")
        _carteras[clave] = Cartera(archivo, extra=["Tasa_COP", "Costo_COP", "Origen", "Precio_COP", "Precio_USD"],
                                   nube=(email, f"ev:{ev['id']}" if ev else "sim"))
    return _carteras[clave]


def evento():
    """El evento cuyo simulador se está usando (dict) o None."""
    return nube.EVENTO.get()


class _CarteraDelUsuario:
    """El simulador del usuario de esta sesión: cada usuario tiene el suyo, separado de los demás."""
    def __getattr__(self, nombre):
        return getattr(_cartera_de(nube.usuario()), nombre)


cartera = _CarteraDelUsuario()


def pesos(x):
    return f"${x:,.0f}".replace(",", ".")


# ---------- Configuración ----------
def config():
    base = {"saldo_inicial": 100_000.0, "modo": "manual", "meta_%": 15}
    ev = evento()
    if ev:                                             # En un evento: monto fijo del profesor y solo modo manual
        return {**base, "saldo_inicial": float(ev["monto"]), "inicio": ev["inicio"]}
    if nube.conectado():
        return {**base, **(nube.leer_ajuste("simulador_config", defecto={}) or {})}
    return {**base, **(json.loads(CONFIG.read_text()) if CONFIG.exists() else {})}


def _guardar_config(**cambios):
    if evento():
        raise ValueError("En un evento no se cambia el monto ni el modo: los fija el profesor.")
    nuevo = {**config(), **cambios}
    if nube.conectado():
        nube.guardar_ajuste("simulador_config", nuevo)
    else:
        CONFIG.write_text(json.dumps(nuevo))


def saldo_inicial():
    return float(config()["saldo_inicial"])


def modo():
    return config()["modo"]


def cambiar_modo(nuevo):
    _guardar_config(modo=nuevo)


def reiniciar(nuevo_saldo=None):
    """Borra todas las operaciones. Si se da un monto, ese es el nuevo saldo inicial."""
    if evento():
        raise ValueError("En un evento no se puede reiniciar el simulador.")
    monto = float(nuevo_saldo) if nuevo_saldo is not None else saldo_inicial()
    if monto <= 0:
        raise ValueError("El saldo inicial debe ser mayor que cero.")
    _guardar_config(saldo_inicial=monto, inicio=datetime.now().strftime("%Y-%m-%d"))
    from respaldo import respaldar
    respaldar()                                # Antes de borrar, siempre una copia de seguridad
    cartera.borrar_todo()                      # La cartera activa (en las pruebas, un archivo temporal)


# ---------- Dinero ----------
_tasas = {}


def tasa_a_pesos(moneda="USD"):
    """Cuántos pesos vale 1 unidad de la moneda (se pide una vez por corrida)."""
    if moneda == "COP":
        return 1.0
    if moneda not in _tasas:                   # Pesos por dólar / unidades de esa moneda por dólar
        _tasas[moneda] = activos.tasa_usd("COP") / activos.tasa_usd(moneda)
    return _tasas[moneda]


def efectivo():
    """Pesos disponibles: saldo inicial - compras (con su costo) + ventas."""
    t = cartera.leer()
    if t.empty:
        return saldo_inicial()
    monto = t["Precio"] * t["Cantidad"] * pd.to_numeric(t["Tasa_COP"], errors="coerce").fillna(1)
    costo = pd.to_numeric(t["Costo_COP"], errors="coerce").fillna(0)
    return saldo_inicial() - (monto + costo)[t["Tipo"] == "COMPRA"].sum() + (monto - costo)[t["Tipo"] == "VENTA"].sum()


def resumen():
    """Disponible, invertido (valor actual) y total, en pesos y en dólares, y la meta del mes."""
    pos = cartera.posiciones()
    tasa = tasa_a_pesos("USD")
    invertido = float(sum((p["Valor_actual"] or 0) * tasa_a_pesos(p["Moneda"]) for _, p in pos.iterrows()))
    disponible = efectivo()
    total, inicial = disponible + invertido, saldo_inicial()
    meta = inicial * (1 + config()["meta_%"] / 100)
    hoy = pd.Timestamp.now()
    fin_mes = hoy + pd.offsets.MonthEnd(0)
    return {"inicial": inicial, "disponible": disponible, "invertido": invertido, "total": total, "tasa": tasa,
            "total_usd": total / tasa, "disponible_usd": disponible / tasa, "invertido_usd": invertido / tasa,
            "ganancia": total - inicial, "ganancia_%": (total / inicial - 1) * 100,
            # shortcut: la meta se mide desde el saldo inicial, no desde el valor del 1.º del mes; reinicia cada mes para medirla mensual
            "meta": meta, "progreso_meta": max(0.0, min(1.0, (total - inicial) / (meta - inicial))),
            "dias_mes": (fin_mes.normalize() - hoy.normalize()).days,
            "posiciones": len(pos), "operaciones": len(cartera.leer())}


# ---------- Comprar y vender ----------
def comprar(simbolo, monto_cop=None, cantidad=None, origen="manual", nota=""):
    """Compra al precio real del momento. Devuelve (fila, error)."""
    simbolo = activos.limpiar(simbolo)
    precio, moneda, abierto = activos.precio_ahora(simbolo)
    tasa = tasa_a_pesos(moneda)
    if cantidad is None:                       # Comisiones de Trii (comisiones.py): salen del mismo monto
        costo = comisiones.costo(monto_cop, moneda)["total"]
        if monto_cop <= costo:
            return None, f"El monto no alcanza ni para la comisión ({pesos(costo)})."
        cantidad = (monto_cop - costo) / (precio * tasa)
    else:
        costo = comisiones.costo(precio * cantidad * tasa, moneda)["total"]
    if precio * cantidad * tasa + costo > efectivo() + 1e-6:
        return None, f"Saldo insuficiente: tienes {pesos(efectivo())} disponibles."
    ev = evento()
    if ev:                                             # Reglas del evento, revisadas también aquí (no solo en la pantalla)
        import cursos
        if ev.get("bitacora_obligatoria") and not cursos.leer_bitacora(nota).get("razon"):
            return None, "En este evento la bitácora es obligatoria: elige la razón de tu compra."
        pos = cartera.posiciones()
        fila = pos[pos["Activo"] == simbolo] if len(pos) else pos
        ya = float(fila["Valor_actual"].iloc[0]) * tasa if len(fila) and pd.notna(fila["Valor_actual"].iloc[0]) else 0.0
        error = cursos.regla_de_compra(ev, simbolo, precio * cantidad * tasa + costo, resumen()["total"], ya)
        if error:
            return None, error
    nota = nota or ("" if abierto else "Mercado cerrado: precio del último cierre")
    error = cartera.registrar(simbolo, "COMPRA", precio, cantidad, datetime.now(), nota, moneda,
                              Tasa_COP=tasa, Costo_COP=round(costo, 2), Origen=origen)
    return ({"Activo": simbolo, "Tipo": "COMPRA", "Precio": precio, "Cantidad": cantidad, "Monto_COP": precio * cantidad * tasa + costo,
             "Abierto": abierto, "Nota": nota}, error)


def vender(simbolo, cantidad=None, origen="manual", nota=""):
    """Vende al precio real del momento (todo si no se da cantidad). Devuelve (fila, error)."""
    simbolo = activos.limpiar(simbolo)
    cantidad = cantidad if cantidad is not None else cartera.tengo(simbolo)
    ev = evento()
    if ev and ev.get("bitacora_obligatoria"):
        import cursos
        if not cursos.leer_bitacora(nota).get("razon"):
            return None, "En este evento la bitácora es obligatoria: elige la razón de tu venta."
    precio, moneda, abierto = activos.precio_ahora(simbolo)
    tasa = tasa_a_pesos(moneda)
    costo = comisiones.costo(precio * cantidad * tasa, moneda)["total"]
    nota = nota or ("" if abierto else "Mercado cerrado: precio del último cierre")
    error = cartera.registrar(simbolo, "VENTA", precio, cantidad, datetime.now(), nota, moneda,
                              Tasa_COP=tasa, Costo_COP=round(costo, 2), Origen=origen)
    return ({"Activo": simbolo, "Tipo": "VENTA", "Precio": precio, "Cantidad": cantidad,
             "Monto_COP": precio * cantidad * tasa - costo,
             "Abierto": abierto, "Nota": nota}, error)


def revisar(simbolos=None, actualizar=False):
    """Modo automático: vende si toca stop/objetivo/alerta/plazo y compra con señal COMPRAR.
    En modo manual no opera: solo devuelve las sugerencias."""
    abiertas = cartera.posiciones()
    simbolos = list(dict.fromkeys([activos.limpiar(s) for s in (simbolos or activos.SIMULAR)] +
                                  list(abiertas.get("Activo", []))))
    if actualizar:
        activos.actualizar_varios(simbolos)
        abiertas = cartera.posiciones()
    automatico = modo() == "automatico"
    acciones = []
    for simbolo in simbolos:
        fila = abiertas[abiertas["Activo"] == simbolo] if len(abiertas) else abiertas
        try:
            if len(fila):
                p = fila.iloc[0]
                dias = int((pd.Timestamp.now().normalize() - pd.Timestamp(p["Fecha_compra"]).normalize()).days)
                r = estrategia.analizar(simbolo)
                motivo = p["Motivo"] if p["Sugerencia"] == "Vender" else None
                if not motivo and dias >= 7 and not r["comprar"]:          # ~5 días de mercado
                    motivo = f"Se cumplió el plazo de {estrategia.DIAS_ADELANTE} días de mercado"
                if motivo:
                    if automatico:
                        hecho, error = vender(simbolo, origen="automático", nota=motivo)
                        acciones.append({**hecho, "Motivo": motivo, "Error": error})
                    else:
                        acciones.append({"Activo": simbolo, "Tipo": "SUGERENCIA: VENDER", "Motivo": motivo})
            else:
                r = estrategia.analizar(simbolo)
                if r["comprar"]:
                    monto = min(efectivo(), resumen()["total"] * FRACCION)
                    if not automatico:
                        acciones.append({"Activo": simbolo, "Tipo": "SUGERENCIA: COMPRAR", "Motivo": r["razon"]})
                    elif monto >= MINIMO_COP:
                        hecho, error = comprar(simbolo, monto_cop=monto, origen="automático", nota=r["razon"][:200])
                        acciones.append({**hecho, "Motivo": r["razon"], "Error": error})
        except Exception as error:
            acciones.append({"Activo": simbolo, "Tipo": "ERROR", "Motivo": str(error)})
    return acciones


def main(argumentos=None):
    parser = argparse.ArgumentParser(description="Simulador con plata virtual")
    parser.add_argument("--saldo", type=float, help="Nuevo saldo inicial (reinicia)")
    parser.add_argument("--reiniciar", action="store_true")
    parser.add_argument("--modo", choices=["automatico", "manual"])
    parser.add_argument("--sin-actualizar", action="store_true")
    args = parser.parse_args(argumentos)
    if args.modo:
        cambiar_modo(args.modo)
        print(f"Modo: {args.modo}")
        return
    if args.saldo is not None or args.reiniciar:
        reiniciar(args.saldo)
        print(f"Simulador reiniciado con {pesos(saldo_inicial())}.")
        return
    for a in revisar(actualizar=not args.sin_actualizar):
        print(f"  {a['Activo']}: {a['Tipo']} - {str(a.get('Motivo', ''))[:90]}")
    s = resumen()
    print(f"\nModo {modo()} | Disponible {pesos(s['disponible'])} | Invertido {pesos(s['invertido'])} | "
          f"Total {pesos(s['total'])} (US$ {s['total_usd']:,.2f}) | {s['ganancia_%']:+.2f}%")


if __name__ == "__main__":
    main()
