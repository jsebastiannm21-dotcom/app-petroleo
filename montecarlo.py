# montecarlo.py - Abanico de predicciones: caminos posibles del precio armados con cambios diarios reales
# (Monte Carlo por remuestreo: cada día futuro toma al azar un cambio diario de los últimos 2 años).

import numpy as np
import pandas as pd


def caminos(cierre, dias=20, n=1000, semilla=0, historia=504):
    """Matriz (n, dias+1) de precios simulados; la columna 0 es el último precio real."""
    cambios = np.log(cierre).diff().dropna().tail(historia).to_numpy()
    rng = np.random.default_rng(semilla)
    sorteo = cambios[rng.integers(0, len(cambios), size=(n, dias))]
    return float(cierre.iloc[-1]) * np.exp(np.hstack([np.zeros((n, 1)), np.cumsum(sorteo, axis=1)]))


def resumen(matriz, fechas):
    """Mediana y bandas del 10% y 90% por día, y cuántos caminos terminan arriba o abajo."""
    inicio = matriz[0, 0]
    final = matriz[:, -1]
    bandas = pd.DataFrame({"P10": np.percentile(matriz, 10, axis=0), "Mediana": np.median(matriz, axis=0),
                           "P90": np.percentile(matriz, 90, axis=0)}, index=fechas)
    return bandas, {"mediana": float(np.median(final)), "p10": float(np.percentile(final, 10)),
                    "p90": float(np.percentile(final, 90)), "suben": int((final > inicio).sum()),
                    "bajan": int((final <= inicio).sum()), "n": len(final)}


if __name__ == "__main__":
    plano = pd.Series([100.0] * 300)                       # Precio que nunca cambia -> todos los caminos planos
    m = caminos(plano, dias=5, n=50)
    assert m.shape == (50, 6) and np.allclose(m, 100)
    sube = pd.Series(100 * 1.01 ** np.arange(300))         # Sube 1% diario -> todos los caminos suben
    _, r = resumen(caminos(sube, dias=5, n=50), range(6))
    assert r["suben"] == 50 and abs(r["mediana"] - sube.iloc[-1] * 1.01 ** 5) < 1e-6
    print("Monte Carlo: pruebas OK")
