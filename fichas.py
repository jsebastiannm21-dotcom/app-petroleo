# fichas.py - Ficha de cada activo: a qué se dedica, sector, país, tamaño, dividendos y riesgos.
# Los datos básicos vienen de Yahoo Finance; la descripción en español sencillo y los riesgos los escribe
# Claude una sola vez por activo. Todo queda guardado en fichas.json (caché).
# Uso:  python fichas.py            (descarga los datos básicos de todos los activos)

import json
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

import yfinance as yf

import activos

ARCHIVO = activos.CARPETA / "fichas.json"
CAMPOS = ["longName", "sector", "industry", "country", "marketCap", "dividendYield", "quoteType", "currency",
          "longBusinessSummary", "category", "fundFamily", "totalAssets", "website",
          "sharesOutstanding", "impliedSharesOutstanding", "regularMarketPrice", "previousClose"]
_bloqueo = threading.Lock()
_cache = None


def _leer():
    global _cache
    if _cache is None:
        _cache = json.loads(ARCHIVO.read_text(encoding="utf-8")) if ARCHIVO.exists() else {}
    return _cache


def _guardar():
    with _bloqueo:
        ARCHIVO.write_text(json.dumps(_leer(), ensure_ascii=False, indent=1), encoding="utf-8")


def _bajar(simbolo):
    try:
        info = yf.Ticker(simbolo).info or {}
    except Exception:
        info = {}
    d = {k: info.get(k) for k in CAMPOS}
    if not (d.get("marketCap") or d.get("sharesOutstanding") or d.get("totalAssets")):
        try:                                             # Otra fuente de Yahoo para calcular precio × acciones
            d["sharesOutstanding"] = yf.Ticker(simbolo).fast_info.get("shares")
        except Exception:
            pass
    return d


def datos(simbolo, bajar_si_falta=False):
    """Datos básicos guardados (vacío si no están y no se pide bajarlos)."""
    fichas = _leer()
    if simbolo not in fichas and bajar_si_falta:
        fichas[simbolo] = {"yahoo": _bajar(simbolo)}
        _guardar()
    return fichas.get(simbolo, {}).get("yahoo", {})


def actualizar_todos():
    fichas = _leer()
    # Los que no están o son de antes de agregar el número de acciones (la descripción en español se conserva)
    faltan = [s for s in activos.ACTIVOS if "sharesOutstanding" not in fichas.get(s, {}).get("yahoo", {})
              or not fichas[s]["yahoo"].get("quoteType")]
    with ThreadPoolExecutor(4) as pool:
        for s, d in zip(faltan, pool.map(_bajar, faltan)):
            if d.get("quoteType") or s not in fichas:  # Una descarga vacía (Yahoo bloqueó) no borra datos buenos
                fichas.setdefault(s, {})["yahoo"] = d
    _guardar()
    return len(faltan)


def descripcion(simbolo):
    """{'que_hace': ..., 'riesgos': [...]} en español sencillo (Claude, guardado en caché)."""
    fichas = _leer()
    ficha = fichas.setdefault(simbolo, {})
    if ficha.get("es"):
        return ficha["es"]
    d = datos(simbolo, bajar_si_falta=True)
    tipo = activos.ACTIVOS.get(simbolo, {}).get("tipo", "acción")
    extra = activos.DESCRIPCION_FUTUROS.get(simbolo, "")
    prompt = (f"Explica para alguien que no sabe de finanzas el activo {simbolo} ({activos.nombre(simbolo)}), de tipo "
              f"{tipo}. Si es una empresa, a qué se dedica; si es un ETF, qué contiene; si es un futuro, índice o "
              f"cripto, qué representa. Datos de Yahoo: {json.dumps({k: d.get(k) for k in ('longName', 'sector', 'industry', 'country', 'category', 'longBusinessSummary')}, ensure_ascii=False)[:2500]} {extra}\n"
              'Responde SOLO un JSON: {"que_hace": "2 o 3 frases en español sencillo", '
              '"riesgos": ["riesgo principal 1", "riesgo 2", "riesgo 3"]}')
    try:
        proc = subprocess.run(["claude", "-p", prompt, "--output-format", "json"], capture_output=True, text=True,
                              encoding="utf-8", timeout=180, cwd=activos.CARPETA)
        texto = json.loads(proc.stdout).get("result", "")
        es = json.loads(texto[texto.index("{"): texto.rindex("}") + 1])
        assert es.get("que_hace")
    except Exception:
        resumen = d.get("longBusinessSummary") or extra or "Sin descripción disponible."
        return {"que_hace": resumen[:400] + ("…" if len(resumen) > 400 else ""), "riesgos": [], "respaldo": True}
    ficha["es"] = es
    _guardar()
    return es


def tamano(capitalizacion, moneda="USD"):
    """Capitalización en dólares y en palabras: 'Gigante (US$ 3,50 billones)'. Convierte si viene en otra moneda."""
    if not capitalizacion:
        return "—"
    if moneda and moneda != "USD":
        capitalizacion = capitalizacion / activos.tasa_usd(moneda)
    b = capitalizacion / 1e9
    nivel = "Gigante" if b >= 200 else "Grande" if b >= 10 else "Mediana" if b >= 2 else "Pequeña"
    return f"{nivel} (US$ {b:,.1f} mil millones)" if b < 1000 else f"{nivel} (US$ {b / 1000:,.2f} billones)"



def tamano_de(simbolo):
    """(texto, explicación). Capitalización de Yahoo; si no la trae, precio × número de acciones; en ETFs, el dinero
    que administran."""
    d = datos(simbolo)
    moneda = d.get("currency") or activos.moneda(simbolo)
    if d.get("marketCap"):
        return tamano(d["marketCap"], moneda), "capitalización según Yahoo Finance"
    if d.get("totalAssets"):
        return tamano(d["totalAssets"], moneda), "dinero que administra el fondo"
    acciones = d.get("sharesOutstanding") or d.get("impliedSharesOutstanding")
    precio = d.get("regularMarketPrice") or d.get("previousClose")
    if acciones and not precio and activos.ruta_precios(simbolo).exists():
        import pandas as pd
        precio = float(pd.read_csv(activos.ruta_precios(simbolo), usecols=["Cierre"])["Cierre"].iloc[-1])
    if acciones and precio:
        return tamano(acciones * precio, moneda), "calculado: precio × número de acciones"
    return "—", "Yahoo no trae este dato"


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    assert tamano(3.5e12).startswith("Gigante") and tamano(5e8).startswith("Pequeña")
    _leer()["_PRUEBA"] = {"yahoo": {"sharesOutstanding": 1e9, "regularMarketPrice": 20.0, "currency": "USD"}}
    assert tamano_de("_PRUEBA")[0].startswith("Grande") and "precio ×" in tamano_de("_PRUEBA")[1]
    del _leer()["_PRUEBA"]
    print(f"Datos nuevos: {actualizar_todos()} activos. Total en caché: {len(_leer())}")
