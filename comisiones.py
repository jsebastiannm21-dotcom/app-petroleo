# comisiones.py - Comisiones de Trii para el simulador (editables en comisiones.json o desde la app).
# - Hasta 5.000.000 COP por operación: 14.875 COP fijos (IVA incluido).
# - Por encima: 0,25% del monto + IVA (19%).
# - Activos en otra moneda (US$...): además, un spread cambiario (diferencia entre el dólar de compra y el real).
# Prueba:  python comisiones.py

import json

import activos

ARCHIVO = activos.CARPETA / "comisiones.json"
BASE = {"fija_cop": 14_875.0, "limite_cop": 5_000_000.0, "porcentaje": 0.25, "iva": 19.0, "spread_cambiario": 1.0}


def config():
    return {**BASE, **(json.loads(ARCHIVO.read_text(encoding="utf-8")) if ARCHIVO.exists() else {})}


def guardar(**cambios):
    ARCHIVO.write_text(json.dumps({**config(), **cambios}), encoding="utf-8")
    import nube
    if nube.conectado():
        nube.subir(["comisiones.json"])


def costo(monto_cop, moneda="COP", c=None):
    """Comisión de UNA operación (compra o venta) en pesos: {'comision', 'spread', 'total'}."""
    c = c or config()
    comision = c["fija_cop"] if monto_cop <= c["limite_cop"] else monto_cop * c["porcentaje"] / 100 * (1 + c["iva"] / 100)
    spread = monto_cop * c["spread_cambiario"] / 100 if moneda != "COP" else 0.0
    return {"comision": comision, "spread": spread, "total": comision + spread}


def subida_para_cubrir(monto_cop, moneda="COP", c=None):
    """% que tiene que subir el activo SOLO para recuperar las comisiones de compra y de venta (None si el monto no
    alcanza ni para la comisión de compra)."""
    compra = costo(monto_cop, moneda, c)["total"]
    if monto_cop <= compra:
        return None
    venta = costo(monto_cop, moneda, c)["total"]           # La venta será de un monto parecido
    return ((monto_cop + venta) / (monto_cop - compra) - 1) * 100


if __name__ == "__main__":
    c = dict(BASE)
    assert costo(100_000, "COP", c)["total"] == 14_875
    assert abs(costo(10_000_000, "COP", c)["comision"] - 10_000_000 * 0.0025 * 1.19) < 1e-6
    assert costo(1_000_000, "USD", c)["spread"] == 10_000
    # 1.000.000 COP en una acción colombiana: compra y venta de 14.875 -> sube ~3,03% solo para empatar
    assert abs(subida_para_cubrir(1_000_000, "COP", c) - ((1_014_875 / 985_125) - 1) * 100) < 1e-9
    assert subida_para_cubrir(10_000, "COP", c) is None    # No alcanza ni para la comisión
    print("Comisiones: pruebas OK")
