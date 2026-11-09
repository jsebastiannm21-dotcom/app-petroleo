# mis_activos.py - Tus compras y ventas REALES (las que haces en tu bróker), en mis_operaciones.csv.
# Este archivo NO compra ni vende nada: solo lleva la cuenta (el motor está en cartera.py).

import activos
import nube
from cartera import Cartera

ARCHIVO = activos.CARPETA / "mis_operaciones.csv"
# Solo el superadmin tiene Mis activos (en la nube, filas del superadmin con cartera "real")
cartera = Cartera(ARCHIVO, extra=["Tasa_COP", "Precio_COP", "Precio_USD"], nube=(nube.superadmin(), "real"))


def abiertas():
    """Lo que tienes hoy (cantidad mayor que cero), con su ganancia en papel y sugerencia."""
    return cartera.posiciones()
