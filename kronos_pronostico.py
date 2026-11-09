# kronos_pronostico.py - Segundo pronóstico con Kronos (modelo de código abierto para velas de mercado):
# https://github.com/shiyu-coder/Kronos  (versión small, corre en el procesador, sin tarjeta gráfica).
# El interruptor está en kronos_config.json (la app lo cambia desde la pestaña Pronóstico).
# Uso:  python kronos_pronostico.py CL=F

import json
import sys
import time

import pandas as pd

import activos

CONFIG = activos.CARPETA / "kronos_config.json"
CARPETA_KRONOS = activos.CARPETA / "vendor" / "Kronos"
_predictor = None


def activado():
    return json.loads(CONFIG.read_text()).get("activado", False) if CONFIG.exists() else False


def cambiar(activo):
    CONFIG.write_text(json.dumps({"activado": bool(activo)}))


def disponible():
    """(True, '') si Kronos se puede usar; si no, (False, motivo en palabras sencillas)."""
    if not CARPETA_KRONOS.exists():
        return False, "No está descargado (falta la carpeta vendor/Kronos)."
    try:
        import torch  # noqa: F401
    except ImportError:
        return False, "Falta PyTorch, el motor que necesita Kronos."
    return True, ""


def _cargar():
    global _predictor
    if _predictor is None:
        sys.path.insert(0, str(CARPETA_KRONOS))
        from model import Kronos, KronosPredictor, KronosTokenizer
        tokenizer = KronosTokenizer.from_pretrained("NeoQuasar/Kronos-Tokenizer-base")
        modelo = Kronos.from_pretrained("NeoQuasar/Kronos-small")
        _predictor = KronosPredictor(modelo, tokenizer, device="cpu", max_context=512)
    return _predictor


def pronosticar(simbolo, dias=5, historia=400):
    """Precio de cierre previsto para los próximos 'dias' días hábiles (columna Central)."""
    p = pd.read_csv(activos.ruta_precios(simbolo), index_col="Fecha", parse_dates=True).tail(historia)
    x = pd.DataFrame({"open": p["Apertura"].values, "high": p["Maximo"].values, "low": p["Minimo"].values,
                      "close": p["Cierre"].values, "volume": p["Volumen"].fillna(0).values})
    futuro = pd.bdate_range(p.index[-1] + pd.Timedelta(days=1), periods=dias)
    pred = _cargar().predict(df=x, x_timestamp=pd.Series(p.index), y_timestamp=pd.Series(futuro), pred_len=dias,
                             T=1.0, top_p=0.9, sample_count=1, verbose=False)
    return pd.DataFrame({"Central": pred["close"].values}, index=futuro)


if __name__ == "__main__":
    simbolo = sys.argv[1] if len(sys.argv) > 1 else activos.PRINCIPAL
    inicio = time.time()
    print(pronosticar(simbolo))
    print(f"Tardó {time.time() - inicio:.0f} segundos (incluye cargar el modelo la primera vez)")
