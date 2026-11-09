# Prueba de la Time Machine con casos que tienen respuesta conocida.  Uso: python test_time_machine.py
import numpy as np

import estrategia as e

# Días que siempre suben 7% en el máximo -> siempre llega al objetivo el primer día
r = e.time_machine(np.array([[1.0, 1.07, 0.99, 1.02]]), n=1000)
assert r["p_objetivo"] == 100 and abs(r["ganancia_esperada"] - (1.06 * 0.995 - 1) * 100) < 1e-9, r

# Días que siempre bajan 4% en el mínimo -> siempre toca el stop
r = e.time_machine(np.array([[1.0, 1.01, 0.96, 0.98]]), n=1000)
assert r["p_stop"] == 100 and not r["a_favor"], r

# Toca stop y objetivo el mismo día -> cuenta el stop (lo peor)
r = e.time_machine(np.array([[1.0, 1.10, 0.90, 1.0]]), n=1000)
assert r["p_stop"] == 100, r

# Abre 10% abajo -> vende a la apertura (pierde más que el 3%)
r = e.time_machine(np.array([[0.90, 0.92, 0.88, 0.91]]), n=1000)
assert abs(r["peor_caso"] - (0.90 * 0.995 - 1) * 100) < 1e-9, r

# Días quietos -> sale por plazo
r = e.time_machine(np.array([[1.0, 1.005, 0.995, 1.001]]), n=1000)
assert r["p_plazo"] == 100, r
print("Time Machine: 5 pruebas OK")
