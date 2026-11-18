# precios_vivos.py - Precios e históricos desde eToro, SOLO LECTURA, con respaldo en Yahoo Finance (yfinance).
# Documentación oficial: https://api-portal.etoro.com  (todos los endpoints de aquí salen de ahí)
#
# SEGURIDAD
#  - Las claves se leen del .env (ETORO_API_KEY y ETORO_USER_KEY). Nunca van en el código ni se imprimen.
#  - Este archivo SOLO hace consultas GET y se suscribe a precios. No puede comprar, vender ni modificar nada:
#    _get() rechaza cualquier método que no sea GET.
#  - Si faltan las claves o eToro falla, todo sigue funcionando con Yahoo Finance (marcado como "respaldo").
#
# Fuente de cada dato:
#   "en vivo"   -> eToro, precio de hace menos de 2 minutos (WebSocket o consulta)
#   "diferido"  -> eToro, pero el precio es más viejo (mercado cerrado o sin operaciones recientes)
#   "respaldo"  -> Yahoo Finance (eToro no respondió o no tiene ese activo). Puede venir con ~15 min de retraso.
#
# Uso:  python precios_vivos.py --permisos      -> qué puede hacer tu clave (sin mostrarla)
#       python precios_vivos.py --precio GLD     -> precio, hora y fuente
#       python precios_vivos.py --vivo GLD       -> escucha el WebSocket 15 segundos

import argparse
import json
import os
import threading
import time
import uuid
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

CARPETA = Path(__file__).resolve().parent
BASE = "https://public-api.etoro.com"
WS_URL = "wss://ws.etoro.com/ws"
RUTA_IDS = CARPETA / "datos" / "etoro_ids.json"
ZONA = "America/Bogota"
VIVO_SEG = 120                       # Un precio de eToro más viejo que esto se marca "diferido"
LIMITE_MIN = 55                      # eToro permite 60 GET por minuto por clave: dejamos margen
INTERVALOS = {"OneMinute": "1m", "FiveMinutes": "5m", "FifteenMinutes": "15m", "ThirtyMinutes": "30m",
              "OneHour": "60m", "OneDay": "1d", "OneWeek": "1wk"}       # eToro -> yfinance (para el respaldo)

# Símbolo de Yahoo -> símbolo en eToro, solo para los que se llaman distinto (acciones y ETFs se llaman igual).
# Estos nombres NO están confirmados en la documentación: se buscan en eToro y solo se aceptan si coinciden
# exactamente; si no, ese activo usa Yahoo. Confírmalos con: python precios_vivos.py --precio CL=F
SIMBOLO_ETORO = {"CL=F": "OIL", "BZ=F": "UKOIL", "GC=F": "GOLD", "^NDX": "NSDQ100"}
SEGUNDOS = {"OneMinute": 60, "FiveMinutes": 300, "FifteenMinutes": 900, "ThirtyMinutes": 1800, "OneHour": 3600,
            "OneDay": 86400, "OneWeek": 604800}


class EtoroError(Exception):
    pass


# ---------------------------------------------------------------- claves y consultas (solo GET)

def claves():
    """(api_key, user_key) del .env, o None si faltan. Así eToro se activa solo cuando pegas las claves."""
    load_dotenv(CARPETA / ".env", override=True)
    api, user = os.getenv("ETORO_API_KEY", "").strip(), os.getenv("ETORO_USER_KEY", "").strip()
    return (api, user) if api and user else None


_llamadas = deque()                  # Horas de las últimas consultas, para no pasar el límite
_bloqueo = threading.Lock()


def _hay_cupo():
    with _bloqueo:
        ahora = time.time()
        while _llamadas and ahora - _llamadas[0] > 60:
            _llamadas.popleft()
        if len(_llamadas) >= LIMITE_MIN:
            return False
        _llamadas.append(ahora)
        return True


def _get(ruta, params=None, metodo="GET", intentos=3):
    if metodo != "GET":                                   # Candado: este conector es de solo lectura
        raise PermissionError("precios_vivos solo hace consultas GET (solo lectura).")
    c = claves()
    if not c:
        raise EtoroError("Faltan ETORO_API_KEY y ETORO_USER_KEY en .env")
    espera = 1
    for intento in range(intentos):
        if not _hay_cupo():
            raise EtoroError("Límite de 60 consultas por minuto alcanzado; uso el respaldo un momento.")
        try:
            r = requests.get(BASE + ruta, params=params, timeout=10,
                             headers={"x-api-key": c[0], "x-user-key": c[1], "x-request-id": str(uuid.uuid4())})
        except requests.RequestException as error:        # Sin internet o eToro caído: reintenta
            ultimo = f"sin conexión ({type(error).__name__})"
        else:
            if r.ok:
                return r.json()
            if r.status_code in (401, 403):               # Clave mala o sin permiso: reintentar no sirve
                raise EtoroError(f"eToro rechazó la clave ({r.status_code}). Revisa ETORO_API_KEY/ETORO_USER_KEY.")
            ultimo = f"eToro respondió {r.status_code}"
            if r.status_code == 429:
                espera = max(espera, float(r.headers.get("Retry-After", espera)))
            elif r.status_code < 500:
                raise EtoroError(f"{ultimo}: {r.text[:200]}")
        if intento < intentos - 1:
            time.sleep(min(espera, 10))
            espera *= 2
    raise EtoroError(ultimo)


# ---------------------------------------------------------------- símbolo -> instrumentId (con caché en disco)

def _leer_ids():
    try:
        return json.loads(RUTA_IDS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def instrumento(simbolo_yahoo):
    """instrumentId de eToro para un símbolo de Yahoo, o None si eToro no lo tiene."""
    ids = _leer_ids()
    if simbolo_yahoo in ids:
        return ids[simbolo_yahoo]
    buscado = SIMBOLO_ETORO.get(simbolo_yahoo) or simbolo_yahoo
    datos = _get("/api/v1/market-data/search", {"internalSymbolFull": buscado,
                                                "fields": "instrumentId,internalSymbolFull,displayname"})
    # El filtro se ignora si no existe, así que se confirma que el símbolo devuelto sea exactamente el pedido
    encontrado = next((i["instrumentId"] for i in datos.get("items", [])
                       if str(i.get("internalSymbolFull", "")).upper() == buscado.upper()), None)
    ids[simbolo_yahoo] = encontrado
    RUTA_IDS.parent.mkdir(exist_ok=True)
    RUTA_IDS.write_text(json.dumps(ids, indent=1), encoding="utf-8")
    return encontrado


# ---------------------------------------------------------------- precio actual

_cache = {}                          # clave -> (hora_guardado, valor)


def _cacheado(clave, ttl, funcion):
    guardado = _cache.get(clave)
    if guardado and time.time() - guardado[0] < ttl:
        return guardado[1]
    valor = funcion()
    _cache[clave] = (time.time(), valor)
    return valor


def _fuente(hora):
    return "en vivo" if (datetime.now(timezone.utc) - hora).total_seconds() < VIVO_SEG else "diferido"


def _precio_etoro(simbolo):
    iid = instrumento(simbolo)
    if iid is None:
        raise EtoroError(f"eToro no tiene {simbolo}")
    tasa = _get("/api/v1/market-data/instruments/rates", {"instrumentIds": iid})["rates"][0]
    hora = pd.Timestamp(tasa["date"]).tz_convert("UTC").to_pydatetime()
    valor = tasa.get("lastExecution") or (tasa["bid"] + tasa["ask"]) / 2
    return {"precio": float(valor), "hora": hora, "fuente": _fuente(hora), "origen": "eToro"}


def _precio_yahoo(simbolo, motivo):
    import yfinance as yf
    d = yf.Ticker(simbolo).history(period="5d", interval="1m")
    if d.empty:
        raise EtoroError(f"Ni eToro ni Yahoo tienen precio de {simbolo}")
    return {"precio": float(d["Close"].iloc[-1]), "hora": d.index[-1].tz_convert("UTC").to_pydatetime(),
            "fuente": "respaldo", "origen": "Yahoo Finance", "motivo": motivo}


def precio(simbolo, flujo=None):
    """{'precio', 'hora' (UTC), 'fuente': 'en vivo'|'diferido'|'respaldo', 'origen'}. Nunca deja la app sin dato:
    primero el WebSocket (si llegó algo reciente), luego la consulta a eToro, y si falla, Yahoo."""
    if flujo and flujo.ultimo and _fuente(flujo.ultimo["hora"]) == "en vivo":
        return flujo.ultimo
    try:
        if not claves():
            raise EtoroError("sin claves de eToro")
        return _cacheado(("precio", simbolo), 5, lambda: _precio_etoro(simbolo))
    except EtoroError as error:
        return _cacheado(("yahoo", simbolo), 60, lambda: _precio_yahoo(simbolo, str(error)))


def precios(simbolos):
    """{simbolo: precio(simbolo)} con UNA sola consulta a eToro para todos (hasta 100), para no gastar el límite."""
    resultado = {}
    try:
        if not claves():
            raise EtoroError("sin claves de eToro")
        ids = {s: instrumento(s) for s in simbolos}
        validos = {i: s for s, i in ids.items() if i is not None}
        if validos:
            clave = ("lote", tuple(sorted(validos)))
            tasas = _cacheado(clave, 5, lambda: _get("/api/v1/market-data/instruments/rates",
                                                     {"instrumentIds": ",".join(map(str, list(validos)[:100]))}))
            for t in tasas.get("rates", []):
                hora = pd.Timestamp(t["date"]).tz_convert("UTC").to_pydatetime()
                valor = t.get("lastExecution") or (t["bid"] + t["ask"]) / 2
                resultado[validos[t["instrumentID"]]] = {"precio": float(valor), "hora": hora,
                                                         "fuente": _fuente(hora), "origen": "eToro"}
    except EtoroError:
        pass                                              # Los que falten van por el respaldo, uno por uno
    for s in simbolos:
        if s not in resultado:
            try:
                resultado[s] = precio(s)
            except Exception:
                resultado[s] = None
    return resultado


# ---------------------------------------------------------------- históricos (velas)

def velas(simbolo, intervalo="OneHour", cantidad=200):
    """DataFrame (hora de Bogotá) con Open, High, Low, Close, Volume. df.attrs['fuente'] dice de dónde salió.
    intervalo: OneMinute, FiveMinutes, FifteenMinutes, ThirtyMinutes, OneHour, OneDay, OneWeek."""
    ttl = 30 if intervalo in ("OneMinute", "FiveMinutes") else 300

    def de_etoro():
        iid = instrumento(simbolo)
        if iid is None:
            raise EtoroError(f"eToro no tiene {simbolo}")
        datos = _get(f"/api/v1/market-data/instruments/{iid}/history/candles/asc/{intervalo}/{min(cantidad, 1000)}")
        filas = datos["candles"][0]["candles"] if datos.get("candles") else []
        d = pd.DataFrame(filas)
        if d.empty:
            raise EtoroError(f"eToro no devolvió velas de {simbolo}")
        d.index = pd.to_datetime(d["fromDate"], utc=True).dt.tz_convert(ZONA).dt.tz_localize(None)
        d = d.rename(columns=str.capitalize)[["Open", "High", "Low", "Close", "Volume"]]
        edad = (pd.Timestamp.now(ZONA).tz_localize(None) - d.index[-1]).total_seconds()  # Desde que abrió la vela
        d.attrs.update(fuente="en vivo" if edad < SEGUNDOS[intervalo] + VIVO_SEG else "diferido", origen="eToro")
        return d

    def de_yahoo(motivo):
        import yfinance as yf
        periodo = {"1m": "5d", "5m": "30d", "15m": "30d", "30m": "30d", "60m": "90d"}.get(INTERVALOS[intervalo], "5y")
        d = yf.download(simbolo, period=periodo, interval=INTERVALOS[intervalo], progress=False, auto_adjust=False)
        if isinstance(d.columns, pd.MultiIndex):
            d.columns = d.columns.get_level_values(0)
        if not d.empty and d.index.tz is not None:
            d.index = d.index.tz_convert(ZONA).tz_localize(None)
        d = d[["Open", "High", "Low", "Close", "Volume"]].tail(cantidad)
        d.attrs.update(fuente="respaldo", origen="Yahoo Finance", motivo=motivo)
        return d

    try:
        if not claves():
            raise EtoroError("sin claves de eToro")
        return _cacheado(("velas", simbolo, intervalo, cantidad), ttl, de_etoro)
    except EtoroError as error:
        return _cacheado(("velas_yahoo", simbolo, intervalo, cantidad), ttl * 2, lambda: de_yahoo(str(error)))


# ---------------------------------------------------------------- streaming (WebSocket) con reconexión

class Flujo:
    """Escucha los precios de un activo por el WebSocket de eToro en un hilo aparte.
    Guarda los últimos ticks (hora, precio) y se reconecta solo si se cae (espera 2, 4, 8... hasta 60 s)."""

    def __init__(self, simbolo, maximo=3600):
        self.simbolo = simbolo
        self.datos = deque(maxlen=maximo)
        self.ultimo = None
        self.error = None
        self.conectado = False
        self.parar = False
        threading.Thread(target=self._escuchar, daemon=True).start()

    def _enviar(self, ws, operacion, datos):
        ws.send(json.dumps({"id": str(uuid.uuid4()), "operation": operacion, "data": datos}))

    def _escuchar(self):
        from websockets.sync.client import connect
        espera = 2
        while not self.parar:
            c = claves()
            try:
                if not c:
                    raise EtoroError("sin claves de eToro")
                iid = instrumento(self.simbolo)
                if iid is None:
                    self.error = f"eToro no tiene {self.simbolo}: se usa el respaldo"
                    return                                 # No hay nada que escuchar
                with connect(WS_URL, open_timeout=10, ping_interval=20) as ws:
                    self._enviar(ws, "Authenticate", {"userKey": c[1], "apiKey": c[0]})
                    respuesta = json.loads(ws.recv(timeout=10))
                    if respuesta.get("success") is False:
                        raise EtoroError(f"autenticación rechazada: {respuesta.get('errorCode')}")
                    self._enviar(ws, "Subscribe", {"topics": [f"instrument:{iid}"], "snapshot": True})
                    self.conectado, self.error, espera = True, None, 2
                    for mensaje in ws:
                        if self.parar:
                            return
                        self._procesar(json.loads(mensaje))
            except Exception as error:
                self.error = f"{type(error).__name__}: {error}"[:200]
            self.conectado = False
            time.sleep(espera)
            espera = min(espera * 2, 60)

    def _procesar(self, m):
        for item in m.get("messages", [m]):               # Puede venir un mensaje suelto o un lote
            if item.get("type") != "Trading.Instrument.Rate":
                continue
            tasa = json.loads(item["content"])            # content es un JSON dentro de un texto
            hora = pd.Timestamp(tasa["Date"]).tz_convert("UTC").to_pydatetime()
            valor = float(tasa.get("LastExecution") or (float(tasa["Bid"]) + float(tasa["Ask"])) / 2)
            self.datos.append((hora, valor))
            self.ultimo = {"precio": valor, "hora": hora, "fuente": _fuente(hora), "origen": "eToro (WebSocket)"}


_flujos = {}                         # Una conexión por activo, compartida por todas las pestañas abiertas
MAX_FLUJOS = 5


def flujo(simbolo):
    """El Flujo de ese activo (lo abre si hace falta), o None sin claves. Cierra el más viejo si hay más de 5."""
    if not claves():
        return None
    with _bloqueo:
        if simbolo not in _flujos:
            if len(_flujos) >= MAX_FLUJOS:
                _flujos.pop(next(iter(_flujos))).parar = True
            _flujos[simbolo] = Flujo(simbolo)
        else:
            _flujos[simbolo] = _flujos.pop(simbolo)          # Lo marca como el más reciente
        return _flujos[simbolo]


# ---------------------------------------------------------------- permisos de la clave

def permisos():
    """Prueba la clave SOLO con consultas de lectura. Nunca intenta comprar ni vender para 'probar' escritura."""
    resultado = {}
    try:
        yo = _get("/api/v1/me")
        resultado["usuario"] = yo.get("username")
        resultado["permisos (scopes)"] = yo.get("scopes") or "eToro no los informa para claves API"
    except EtoroError as error:
        resultado["perfil"] = str(error)
    for nombre, ruta, params in [("precios de mercado", "/api/v1/market-data/instruments/rates", {"instrumentIds": 1}),
                                 ("cuenta DEMO (lectura)", "/api/v1/trading/info/demo/pnl", None),
                                 ("cuenta REAL (lectura)", "/api/v1/trading/info/real/pnl", None)]:
        try:
            _get(ruta, params, intentos=1)
            resultado[nombre] = "sí"
        except EtoroError as error:
            resultado[nombre] = f"no ({error})"
    return resultado


def _probar_sin_red():
    f = Flujo.__new__(Flujo)
    f.datos, f.ultimo = deque(maxlen=5), None
    f._procesar({"messages": [{"topic": "instrument:1", "type": "Trading.Instrument.Rate", "content": json.dumps(
        {"Ask": "101", "Bid": "99", "LastExecution": "100.5", "Date": datetime.now(timezone.utc).isoformat()})}]})
    assert f.ultimo["precio"] == 100.5 and f.ultimo["fuente"] == "en vivo"
    f._procesar({"type": "Trading.Instrument.Rate", "content": json.dumps(
        {"Ask": "3", "Bid": "1", "LastExecution": "", "Date": "2020-01-01T00:00:00Z"})})
    assert f.ultimo["precio"] == 2 and f.ultimo["fuente"] == "diferido"
    try:
        _get("/x", metodo="POST")
        raise AssertionError("debía bloquear")
    except PermissionError:
        pass


if __name__ == "__main__":
    _probar_sin_red()
    p = argparse.ArgumentParser(description="Precios eToro (solo lectura) con respaldo Yahoo")
    p.add_argument("--permisos", action="store_true")
    p.add_argument("--precio", metavar="SIMBOLO")
    p.add_argument("--vivo", metavar="SIMBOLO")
    a = p.parse_args()
    if a.permisos:
        if not claves():
            print("Todavía no hay claves en .env (ETORO_API_KEY y ETORO_USER_KEY).")
        for k, v in permisos().items():
            print(f"{k}: {v}")
    elif a.precio:
        r = precio(a.precio)
        print(f"{a.precio}: {r['precio']:,.4f} · {r['hora'].astimezone():%H:%M:%S} · {r['fuente']} ({r['origen']})"
              + (f" · motivo: {r['motivo']}" if r.get("motivo") else ""))
    elif a.vivo:
        f = Flujo(a.vivo)
        time.sleep(15)
        print(f"Ticks en 15 s: {len(f.datos)} · conectado: {f.conectado} · error: {f.error} · último: {f.ultimo}")
    else:
        print("Pruebas internas OK. Usa --permisos, --precio o --vivo.")
