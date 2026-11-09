# Prueba del motor de carteras (Mis activos y Simulador).  Uso: python test_carteras.py
import pathlib
import tempfile

import activos
import cartera
import nube

nube.conectado = lambda: False      # La prueba NUNCA toca Supabase (ni tus datos reales en la nube)
import estrategia
import simulador as s

tmp = pathlib.Path(tempfile.mkdtemp())
cartera.ultimo_cierre = lambda sym: 110.0                       # Precio "actual" inventado

# --- Mis activos: compras, venta parcial, ganancia en papel y realizada ---
c = cartera.Cartera(tmp / "mis.csv")
assert c.registrar("GLD", "COMPRA", 100, 2, "2026-10-01 10:00") is None
assert c.registrar("GLD", "COMPRA", 120, 2, "2026-10-05 10:00") is None      # promedio 110
assert c.registrar("GLD", "VENTA", 130, 1, "2026-10-10 10:00") is None       # realiza (130-110)*1 = 20
assert "solo tienes 3" in c.registrar("GLD", "VENTA", 130, 5, "2026-10-11")
p = c.posiciones().iloc[0]
assert p["Cantidad"] == 3 and abs(p["Precio_compra"] - 110) < 1e-9 and abs(p["Ganancia_realizada"] - 20) < 1e-9, p
assert abs(p["Ganancia_papel"]) < 1e-9, p                       # vale 110 y costó 110
t = c.leer(); t.loc[[0, 1], "Cantidad"] = 0.1           # quedaría 0,2 comprado y 1 vendido
assert "vendes más" in c.reemplazar(t)

# --- Simulador: efectivo en pesos, modo manual no opera ---
s.cartera, s.CONFIG = cartera.Cartera(tmp / "sim.csv", extra=["Tasa_COP", "Costo_COP", "Origen"]), tmp / "cfg.json"
s.ARCHIVO = tmp / "sim.csv"
import comisiones  # noqa: E402
import respaldo  # noqa: E402
comisiones.ARCHIVO = tmp / "comisiones.json"     # Comisiones por defecto de Trii, sin tocar las reales
respaldo.respaldar = lambda: (None, {})          # La prueba no crea respaldos
assert s.cartera.archivo.parent == tmp and s.CONFIG.parent == tmp   # Nunca tocar los archivos reales
s.tasa_a_pesos = lambda moneda="USD": 4000.0
activos.precio_ahora = lambda sym: (100.0, "USD", False)
s.reiniciar(200_000)
fila, error = s.comprar("GLD", monto_cop=40_000)
assert error is None and abs(s.efectivo() - 160_000) < 1e-6, s.efectivo()
assert "Mercado cerrado" in fila["Nota"]
fila, error = s.vender("GLD")
# Compra de 40.000: 14.875 de comisión + 1% de spread (400) -> invierte 24.725. Vende 24.725 y paga 14.875 + 247,25
assert error is None and abs(s.efectivo() - (160_000 + 24_725 - 15_122.25)) < 1e-6, s.efectivo()
assert "Saldo insuficiente" in s.comprar("GLD", monto_cop=999_999)[1]
assert s.comprar("GLD", monto_cop=999_999)[1] is not None                               # no alcanza
real = estrategia.analizar
estrategia.analizar = lambda sym: {**real("EC"), "comprar": True, "razon": "prueba"}
s.cambiar_modo("manual")
acc = s.revisar(["EC"])
assert acc and acc[0]["Tipo"] == "SUGERENCIA: COMPRAR" and len(s.cartera.leer()) == 2, acc
s.cambiar_modo("automatico")
acc = s.revisar(["EC"])
assert acc[0]["Tipo"] == "COMPRA" and acc[0]["Error"] is None, acc
print("Carteras: pruebas OK")
