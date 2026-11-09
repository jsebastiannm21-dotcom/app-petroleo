# etoro.py - Conexión con eToro (PREPARADA, todavía sin claves)
# Basado en la documentación pública del API de eToro: https://api-portal.etoro.com
#
# SEGURIDAD:
#  - Las claves se leen del archivo .env (ETORO_API_KEY y ETORO_USER_KEY), nunca del código.
#  - Este archivo SOLO opera en la cuenta DEMO (dinero virtual de eToro). El modo real está
#    bloqueado a propósito: habilitarlo requiere cambiar el código conscientemente.
#  - No está conectado al simulador ni a las alertas: nada se ejecuta solo.
#
# Uso (cuando tengas las claves en .env):
#   python etoro.py --estado            -> revisa las claves y muestra tu cuenta demo
#   python etoro.py --buscar GLD        -> busca el número de instrumento de eToro
#   python etoro.py --comprar-demo GLD --monto 100   -> compra DEMO de 100 USD con stop y objetivo

import argparse
import os
import uuid
from pathlib import Path

import requests
from dotenv import load_dotenv

import activos
import estrategia

CARPETA = Path(__file__).resolve().parent
BASE = "https://public-api.etoro.com"

# Símbolo de Yahoo Finance -> símbolo en eToro. Las ACCIONES y ETFs (las 101 del Nasdaq 100, las
# petroleras, las mineras, GLD, USO, QQQ, SPY) usan el mismo símbolo, así que no hace falta ponerlas aquí.
# Los futuros e índices tienen nombres propios en eToro: confírmalos con  python etoro.py --buscar <nombre>
SIMBOLO_ETORO = {
    "CL=F": None,     # Petróleo WTI: por confirmar (en eToro suele llamarse "OIL")
    "BZ=F": None,     # Petróleo Brent: por confirmar
    "GC=F": None,     # Oro: por confirmar (en eToro suele llamarse "GOLD")
    "^NDX": None,     # Nasdaq 100: por confirmar (en eToro suele llamarse "NSDQ100")
}


class ClaveFaltante(Exception):
    pass


def _credenciales():
    load_dotenv(CARPETA / ".env", override=True)
    api, user = os.getenv("ETORO_API_KEY", "").strip(), os.getenv("ETORO_USER_KEY", "").strip()
    if not (api and user):
        raise ClaveFaltante("Faltan ETORO_API_KEY y ETORO_USER_KEY en el archivo .env")
    return api, user


def _cabeceras():
    api, user = _credenciales()
    # x-request-id: un identificador único por petición (evita órdenes duplicadas si se reintenta)
    return {"x-api-key": api, "x-user-key": user, "x-request-id": str(uuid.uuid4()),
            "Content-Type": "application/json"}


def _pedir(metodo, ruta, **kwargs):
    r = requests.request(metodo, BASE + ruta, headers=_cabeceras(), timeout=30, **kwargs)
    if not r.ok:
        raise RuntimeError(f"eToro respondió {r.status_code}: {r.text[:300]}")
    return r.json()


def buscar_instrumento(simbolo_etoro):
    """Devuelve el número de instrumento (instrumentId) de eToro para un símbolo."""
    datos = _pedir("GET", "/api/v1/market-data/search", params={"internalSymbolFull": simbolo_etoro})
    for item in datos.get("items", []):
        if str(item.get("internalSymbolFull", "")).upper() == simbolo_etoro.upper():
            return item["instrumentId"]
    return None


def cuenta_demo():
    """Saldo disponible y posiciones abiertas de la cuenta DEMO."""
    datos = _pedir("GET", "/api/v1/trading/info/demo/pnl").get("clientPortfolio", {})
    return {"credito_usd": datos.get("credit"), "ganancia_no_realizada": datos.get("unrealizedPnL"),
            "posiciones": datos.get("positions", [])}


def comprar_demo(simbolo_yahoo, monto_usd):
    """Abre una compra en la cuenta DEMO con el stop loss (3%) y el objetivo (6%) de la estrategia."""
    if simbolo_yahoo in SIMBOLO_ETORO and SIMBOLO_ETORO[simbolo_yahoo] is None:
        raise ValueError(f"Falta confirmar cómo se llama {simbolo_yahoo} en eToro. Búscalo con --buscar y "
                         "escríbelo en SIMBOLO_ETORO.")
    simbolo_etoro = SIMBOLO_ETORO.get(simbolo_yahoo) or simbolo_yahoo
    instrumento = buscar_instrumento(simbolo_etoro)
    if instrumento is None:
        raise ValueError(f"eToro no tiene el símbolo '{simbolo_etoro}'. Revisa SIMBOLO_ETORO en este archivo.")
    precio, _ = activos.precio_y_moneda(simbolo_yahoo)   # Precio aproximado para calcular los niveles
    orden = {
        "action": "open", "transaction": "buy", "instrumentId": instrumento, "orderType": "mkt",
        "leverage": 1,                    # Sin apalancamiento
        "amount": float(monto_usd), "orderCurrency": "usd",
        "stopLossRate": round(precio * (1 - estrategia.STOP_LOSS / 100), 4),
        "takeProfitRate": round(precio * (1 + estrategia.OBJETIVO / 100), 4),
        "stopLossType": "fixed",
    }
    # Solo la ruta DEMO. Una respuesta 200 significa "recibida", no "ejecutada".
    return _pedir("POST", "/api/v2/trading/execution/demo/orders", json=orden)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Conexión con eToro (solo cuenta demo)")
    parser.add_argument("--estado", action="store_true")
    parser.add_argument("--buscar", metavar="SIMBOLO")
    parser.add_argument("--comprar-demo", metavar="SIMBOLO_YAHOO")
    parser.add_argument("--monto", type=float, default=100, help="Dólares a invertir en la cuenta demo")
    args = parser.parse_args()
    try:
        if args.buscar:
            print(f"{args.buscar}: instrumentId = {buscar_instrumento(args.buscar)}")
        elif args.comprar_demo:
            print(comprar_demo(activos.limpiar(args.comprar_demo), args.monto))
        else:
            c = cuenta_demo()
            print(f"Claves OK. Cuenta DEMO: disponible {c['credito_usd']} USD, "
                  f"{len(c['posiciones'])} posiciones abiertas")
    except ClaveFaltante as error:
        print(f"{error}. Cuando las tengas, ponlas en .env y vuelve a correr esto.")
