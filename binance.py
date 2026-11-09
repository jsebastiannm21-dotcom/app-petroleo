# binance.py - Precio de cripto EN VIVO desde la API pública de Binance (sin cuenta ni clave).
#  - precio(simbolo): precio exacto de este momento (consulta normal).
#  - Flujo(simbolo): conexión WebSocket que recibe cada operación en tiempo real (para la gráfica en vivo).

import json
import re
import threading
import time
from collections import deque

import requests

REST = "https://api.binance.com/api/v3/ticker/price"
WS = "wss://stream.binance.com:9443/ws/{}@trade"


def par(simbolo):
    """'BTC-USD' (Yahoo) -> 'BTCUSDT' (Binance, en dólares estables USDT). 'UNI7083-USD' -> 'UNIUSDT'."""
    return re.sub(r"\d+$", "", simbolo.upper().replace("-USD", "")).replace("-", "") + "USDT"


def precio(simbolo):
    """Precio de este momento en Binance, o None si no responde."""
    try:
        return float(requests.get(REST, params={"symbol": par(simbolo)}, timeout=5).json()["price"])
    except Exception:
        return None


class Flujo:
    """Guarda las últimas operaciones (hora, precio) que llegan por WebSocket, en un hilo aparte."""

    def __init__(self, simbolo, maximo=3600):
        self.simbolo = simbolo
        self.datos = deque(maxlen=maximo)
        self.error = None
        threading.Thread(target=self._escuchar, daemon=True).start()

    def _escuchar(self):
        from websockets.sync.client import connect
        while True:                                         # Si se cae la conexión, reintenta
            try:
                with connect(WS.format(par(self.simbolo).lower()), open_timeout=10) as ws:
                    self.error = None
                    for mensaje in ws:
                        m = json.loads(mensaje)
                        self.datos.append((m["T"] / 1000, float(m["p"])))
            except Exception as error:
                self.error = str(error)
                time.sleep(3)


if __name__ == "__main__":
    assert par("BTC-USD") == "BTCUSDT" and par("ETH-USD") == "ETHUSDT"
    print("BTC ahora:", precio("BTC-USD"))
    f = Flujo("BTC-USD")
    time.sleep(4)
    print(f"Operaciones recibidas en 4 segundos: {len(f.datos)}; error: {f.error}")
