# noticias.py - Noticias automáticas desde el RSS de Google Noticias (gratis, sin clave).
# (GDELT bloqueaba casi todas las consultas desde esta conexión por su límite de 1 consulta cada 5 segundos.)
# Guarda los titulares en noticias.csv, sin duplicados, con su grupo y tipo.
# Uso:  python noticias.py                   (actualiza las noticias de los 4 grupos)
#       python noticias.py --empresa NVDA

import argparse
import json
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime

import pandas as pd
import requests

import activos

ARCHIVO = activos.CARPETA / "noticias.csv"
ESTADO = activos.CARPETA / "noticias_estado.json"
URL = "https://news.google.com/rss/search"
ESPANOL = {"hl": "es-419", "gl": "CO", "ceid": "CO:es-419"}
INGLES = {"hl": "en-US", "gl": "US", "ceid": "US:en"}
COLUMNAS = ["Fecha", "Grupo", "Tipo", "Activo", "Titular", "Fuente", "URL"]

# Grupo -> Tipo -> (búsqueda, idioma)
BUSQUEDAS = {
    "petróleo": {"OPEP": ("OPEC oil", INGLES), "Irán": ("Iran oil", INGLES), "Ormuz": ("Strait of Hormuz", INGLES),
                 "Trump": ("Trump oil prices", INGLES)},
    "ecopetrol": {"Ecopetrol": ("Ecopetrol", ESPANOL), "Dólar": ("dólar Colombia peso", ESPANOL),
                  "Gobierno": ("gobierno De la Espriella economía", ESPANOL),
                  "Política petrolera": ("política petrolera Colombia exploración fracking", ESPANOL)},
    "oro": {"Fed": ("Federal Reserve gold", INGLES), "Tasas": ("interest rates gold price", INGLES),
            "Inflación": ("inflation gold", INGLES), "Geopolítico": ("gold safe haven geopolitical", INGLES)},
    "nasdaq": {"Fed": ("Federal Reserve Nasdaq stocks", INGLES),
               "Tecnológicas": ("big tech earnings Nasdaq", INGLES),
               "Empleo": ("jobs report payrolls stocks", INGLES)},
    "asia": {"Japón": ("Bank of Japan Nikkei stocks", INGLES), "China": ("China economy Hang Seng stocks", INGLES),
             "Corea y Taiwán": ("Samsung TSMC Korea Taiwan stocks", INGLES), "India": ("India stocks Nifty Sensex", INGLES)},
    "cripto": {"Bitcoin": ("Bitcoin price", INGLES), "Ethereum": ("Ethereum price", INGLES),
               "Regulación": ("crypto regulation SEC ETF", INGLES)},
    "europa": {"BCE": ("European Central Bank rates stocks", INGLES), "Bolsas": ("FTSE DAX CAC stocks Europe", INGLES)},
}
BUSQUEDAS["ecopetrol"]["Café"] = ("precio del café Colombia", ESPANOL)
BUSQUEDAS["agro"] = {"Granos": ("corn wheat soybean prices", INGLES), "Cacao y azúcar": ("cocoa sugar prices", INGLES),
                     "Ganado": ("cattle hog futures", INGLES)}
BUSQUEDAS["latam"] = {"Brasil": ("Bovespa Brasil bolsa real", ESPANOL), "México": ("Bolsa Mexicana peso Banxico", ESPANOL),
                      "Argentina": ("Merval Argentina bonos dólar", ESPANOL), "Chile y Perú": ("bolsa Chile Perú cobre", ESPANOL)}
BUSQUEDAS["divisas"] = {"Dólar": ("dollar index DXY currencies", INGLES), "Peso colombiano": ("dólar hoy Colombia", ESPANOL)}
BUSQUEDAS["bonos"] = {"Tesoro": ("Treasury yields bonds", INGLES), "TES": ("TES Colombia bonos tasas", ESPANOL)}


# ---------- Titulares de medios (RSS) ----------
MEDIOS = {
    "Investing.com": ["https://www.investing.com/rss/news_25.rss", "https://www.investing.com/rss/news_11.rss"],
    "Bloomberg": ["https://feeds.bloomberg.com/markets/news.rss"],
    "Washington Post": ["https://feeds.washingtonpost.com/rss/business"],
    "Portafolio": ["https://www.portafolio.co/rss/economia.xml"],
    "La República": ["https://www.larepublica.co/rss/"],
    "Valora Analitik": ["https://www.valoraanalitik.com/feed/"],
}
# Palabras que hacen relevante un titular para cada mercado (en minúsculas)
PALABRAS = {
    "petróleo": ["oil", "crude", "brent", "wti", "opec", "opep", "petróleo", "petroleo", "hormuz", "ormuz", "barrel",
                 "barril", "gasolina", "refiner"],
    "oro": ["gold", " oro ", "bullion", "precious metal", "metales preciosos"],
    "nasdaq": ["nasdaq", "wall street", "stocks", "s&p 500", "federal reserve", " fed ", "tech stock", "earnings",
               "nvidia", "apple", "microsoft", "jobs report", "inflation", "inflación", "treasury"],
    "ecopetrol": ["ecopetrol", "dólar", "dolar", "peso colombiano", "hidrocarburos", "banco de la república",
                  "de la espriella", "minhacienda", "fracking", "bancolombia", "cibest", "grupo aval", "grupo sura",
                  "grupo argos", "davivienda", "celsia", "colcap", "bolsa de colombia"],
    "asia": ["nikkei", "bank of japan", "boj", "yen", "hang seng", "china stocks", "shanghai", "kospi", "taiwan",
             "tsmc", "samsung", "toyota", "alibaba", "tencent", "byd", "india stocks", "nifty", "sensex"],
    "cripto": ["bitcoin", "ethereum", "crypto", "cripto", "solana", "xrp", "binance", "stablecoin"],
    "europa": ["ftse", "dax", "cac 40", "stoxx", "european central bank", "ecb", "lagarde", "eurozone", "euro zone"],
}
PALABRAS["ecopetrol"] += ["café", "coffee", "arabica"]
PALABRAS["agro"] = ["corn", "wheat", "soybean", "cocoa", "cacao", "sugar", "azúcar", "cotton", "cattle", "ganado",
                    "maíz", "trigo", "soya", "grain"]
PALABRAS["latam"] = ["bovespa", "brasil", "brazil", "méxico", "mexico", "banxico", "argentina", "merval", "milei", "chile",
                     "perú", "peru", "lula", "real brasileño"]
PALABRAS["divisas"] = ["dólar", "dollar", "euro", "yen", "peso", "currency", "divisa", "forex", "dxy", "tipo de cambio"]
PALABRAS["bonos"] = ["treasury", "yield", "bond", "bono", " tes ", "tasa de interés", "rendimiento de los bonos"]
# Palabras de noticias FUERTES (avisan al momento)
GRAVES = ["opec", "opep", "federal reserve", " fed ", "warsh", "rate hike", "rate cut", "trump", " war ", "guerra",
          "attack", "ataque", "missile", "misil", "airstrike", "invasion", "invasión", "plunge", "crash", "tumble",
          "se desploma", "desplome", "collapse", "colapso", "sanction", "sanción", "embargo"]


def _texto(titular):
    return f" {str(titular).lower()} "


def es_grave(titular):
    return any(p in _texto(titular) for p in GRAVES)


def mis_simbolos():
    """Activos que tienes: reales (Mis activos) y simulados."""
    import mis_activos
    import simulador
    return list(dict.fromkeys(list(mis_activos.abiertas().get("Activo", [])) +
                              list(simulador.cartera.posiciones(con_precio=False).get("Activo", []))))


def relevancia(titular, simbolos):
    """(puntaje, grupo, activo). Tus activos pesan más que el mercado; las noticias fuertes suman."""
    t = _texto(titular)
    for s in simbolos:
        nombre = activos.nombre(s).lower().split(" (")[0]
        if (len(nombre) > 3 and nombre in t) or (len(s) >= 3 and f" {s.lower()} " in t):
            return 3 + 2 * es_grave(titular), (activos.noticias(s) or ["nasdaq"])[0], s
    for grupo, palabras in PALABRAS.items():
        if any(p in t for p in palabras):
            return 1 + 2 * es_grave(titular), grupo, ""
    return 0, None, ""


def _rss(url):
    try:
        r = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        items = ET.fromstring(r.content).findall(".//item")
    except (requests.RequestException, ET.ParseError):
        return []
    salida = []
    for it in items:
        texto_fecha = it.findtext("pubDate") or ""
        try:
            fecha = pd.Timestamp(parsedate_to_datetime(texto_fecha))
        except (TypeError, ValueError):
            fecha = pd.to_datetime(texto_fecha, utc=True, errors="coerce")     # Investing usa "AAAA-MM-DD hh:mm:ss" (UTC)
            if pd.isna(fecha):
                continue
        fecha = fecha.tz_convert("America/Bogota").tz_localize(None) if fecha.tzinfo else fecha
        salida.append((fecha, " ".join((it.findtext("title") or "").split()), it.findtext("link")))
    return salida


def actualizar_medios():
    """Titulares de los medios, solo los relacionados con tus activos y mercados."""
    simbolos = mis_simbolos()
    fuentes = {medio: urls for medio, urls in MEDIOS.items()}
    sigue = list(dict.fromkeys(simbolos + list(activos.REFERENCIAS.values()) + ["EC"]))
    fuentes["Yahoo Finance"] = [f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={','.join(sigue)}&region=US&lang=en-US"]
    filas = []
    for medio, urls in fuentes.items():
        for url in urls:
            for fecha, titular, enlace in _rss(url):
                puntaje, grupo, activo = relevancia(titular, simbolos)
                if puntaje:
                    filas.append({"Fecha": fecha, "Grupo": grupo, "Tipo": "Titular de medio", "Activo": activo,
                                  "Titular": titular, "Fuente": medio, "URL": enlace})
    # Reuters a través de Google Noticias
    for fecha, titular, fuente, enlace in _consultar("site:reuters.com (oil OR gold OR Fed OR Nasdaq OR OPEC)", INGLES):
        puntaje, grupo, activo = relevancia(titular, simbolos)
        if puntaje:
            filas.append({"Fecha": pd.Timestamp(fecha).tz_convert("America/Bogota").tz_localize(None), "Grupo": grupo,
                          "Tipo": "Titular de medio", "Activo": activo, "Titular": titular, "Fuente": "Reuters",
                          "URL": enlace})
    _guardar(filas)
    return len(filas)


def para_mi(horas=24, n=5):
    """Las n noticias más relevantes de las últimas horas para tus activos y tus mercados."""
    t = leer()
    t = t[t["Fecha"] >= pd.Timestamp.now() - pd.Timedelta(hours=horas)].copy()
    if t.empty:
        return t
    simbolos = mis_simbolos()
    puntos = t["Titular"].map(lambda x: relevancia(x, simbolos)[0])
    t["Puntaje"] = puntos + (t["Tipo"] == "Titular de medio") * 0.5 + (t["Activo"].isin(simbolos)) * 2
    t = t[t["Puntaje"] > 0].sort_values(["Puntaje", "Fecha"], ascending=False)
    return t.drop_duplicates("Titular").head(n)


def titulares_por_medio(horas=24, por_medio=3):
    """{medio: [titulares]} de las últimas horas (solo titulares de medios relevantes)."""
    t = leer()
    t = t[(t["Tipo"] == "Titular de medio") & (t["Fecha"] >= pd.Timestamp.now() - pd.Timedelta(hours=horas))]
    t = t.sort_values("Fecha", ascending=False).drop_duplicates("Titular")
    return {medio: g.head(por_medio) for medio, g in t.groupby("Fuente")}


IMPACTO = {
    "petróleo": "Puede mover el precio del petróleo (WTI y Brent) y de las petroleras como Ecopetrol.",
    "oro": "Puede mover el precio del oro y de las mineras de oro.",
    "nasdaq": "Puede mover las acciones de tecnología y el Nasdaq.",
    "ecopetrol": "Puede mover la acción de Ecopetrol y el dólar en Colombia.",
}


def impacto_simple(fila):
    """Frase de impacto sin Claude (respaldo)."""
    if fila["Activo"]:
        return f"Habla de {activos.nombre(fila['Activo'])}, que tienes: puede mover su precio."
    return IMPACTO.get(fila["Grupo"], "Puede mover tus mercados.")


def impacto_con_claude(filas):
    """Una frase por titular de cómo podría afectar el precio (Claude, sin herramientas; respaldo simple)."""
    import subprocess
    lista = [{"titular": f["Titular"], "activo_o_mercado": activos.nombre(f["Activo"]) if f["Activo"] else f["Grupo"]}
             for _, f in filas.iterrows()]
    prompt = ("Para cada titular, escribe UNA frase corta en español sencillo de cómo podría afectar el precio del "
              "activo o mercado indicado (sube, baja o incierto, y por qué). Responde SOLO una lista JSON de frases, "
              f"en el mismo orden:\n{json.dumps(lista, ensure_ascii=False)}")
    try:
        proc = subprocess.run(["claude", "-p", prompt, "--output-format", "json"], capture_output=True, text=True,
                              encoding="utf-8", timeout=180, cwd=activos.CARPETA)
        texto = json.loads(proc.stdout).get("result", "")
        frases = json.loads(texto[texto.index("["): texto.rindex("]") + 1])
        if len(frases) == len(lista):
            return [str(f) for f in frases]
    except Exception:
        pass
    return [impacto_simple(f) for _, f in filas.iterrows()]


def _consultar(busqueda, idioma, dias=1):
    """Una búsqueda en Google Noticias. Devuelve [(fecha, titular, fuente, enlace)]."""
    params = {"q": f"{busqueda} when:{dias}d", **idioma}
    try:
        r = requests.get(URL, params=params, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        items = ET.fromstring(r.content).findall(".//item")
    except (requests.RequestException, ET.ParseError):
        return []
    salida = []
    for it in items:
        fuente = it.findtext("source") or ""
        titular = (it.findtext("title") or "").strip()
        if fuente and titular.endswith(f" - {fuente}"):         # Google agrega " - Fuente" al final
            titular = titular[: -len(fuente) - 3]
        try:
            fecha = parsedate_to_datetime(it.findtext("pubDate"))
        except (TypeError, ValueError):
            continue
        salida.append((fecha, titular, fuente, it.findtext("link")))
    return salida


def _filas(resultados, grupo, tipo, activo=""):
    return [{"Fecha": pd.Timestamp(f).tz_convert("America/Bogota").tz_localize(None), "Grupo": grupo, "Tipo": tipo,
             "Activo": activo, "Titular": t, "Fuente": fu, "URL": u} for f, t, fu, u in resultados]


def leer():
    if not ARCHIVO.exists():
        return pd.DataFrame(columns=COLUMNAS)
    t = pd.read_csv(ARCHIVO, encoding="utf-8-sig", parse_dates=["Fecha"])
    t["Activo"] = t["Activo"].fillna("")
    return t


def _guardar(nuevas):
    """Une con lo guardado, sin duplicados (mismo enlace o mismo titular en el mismo grupo/activo)."""
    tabla = pd.concat([leer(), pd.DataFrame(nuevas, columns=COLUMNAS)], ignore_index=True)
    tabla["Activo"] = tabla["Activo"].fillna("")
    tabla = tabla.drop_duplicates(subset=["URL", "Grupo", "Activo"]).drop_duplicates(subset=["Titular", "Grupo", "Activo"])
    tabla = tabla.sort_values("Fecha", ascending=False).head(20_000)
    tabla.to_csv(ARCHIVO, index=False, encoding="utf-8-sig")
    return tabla


def _estado():
    return json.loads(ESTADO.read_text()) if ESTADO.exists() else {}


def ultima_actualizacion():
    return _estado().get("ultima")


def actualizar(dias=1):
    """Busca las noticias de los 4 grupos. Devuelve cuántas noticias nuevas hubo."""
    antes = len(leer())
    nuevas = []
    for grupo, tipos in BUSQUEDAS.items():
        for tipo, (busqueda, idioma) in tipos.items():
            nuevas += _filas(_consultar(busqueda, idioma, dias), grupo, tipo)
            time.sleep(0.5)                                      # Pausa corta por cortesía
    _guardar(nuevas)
    actualizar_medios()
    tabla = leer()
    ESTADO.write_text(json.dumps({**_estado(), "ultima": datetime.now().strftime("%Y-%m-%d %H:%M")}))
    return len(tabla) - antes


def de_empresa(simbolo, refrescar_horas=6):
    """Noticias de una empresa (las busca si no se han buscado en las últimas horas)."""
    estado = _estado()
    ultima = estado.get("empresas", {}).get(simbolo)
    if not ultima or (datetime.now() - datetime.fromisoformat(ultima)).total_seconds() > refrescar_horas * 3600:
        nombre = activos.nombre(simbolo)
        idioma = ESPANOL if "ecopetrol" in activos.noticias(simbolo) or simbolo.endswith(".CL") else INGLES
        busqueda = f'"{nombre}"' if simbolo in activos.ACTIVOS else simbolo
        _guardar(_filas(_consultar(busqueda, idioma, 90), "empresa", "Empresa", simbolo))
        estado.setdefault("empresas", {})[simbolo] = datetime.now().isoformat(timespec="minutes")
        ESTADO.write_text(json.dumps(estado))
    t = leer()
    return t[t["Activo"] == simbolo].sort_values("Fecha", ascending=False)


def de_grupos(grupos, desde=None):
    """Noticias de los grupos indicados (por ejemplo ["petróleo"]), de la más reciente a la más antigua."""
    t = leer()
    t = t[t["Grupo"].isin(grupos)]
    if desde is not None:
        t = t[t["Fecha"] >= desde]
    return t.sort_values("Fecha", ascending=False)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Noticias automáticas (Google Noticias)")
    parser.add_argument("--empresa")
    parser.add_argument("--dias", type=int, default=1, help="Cuántos días hacia atrás buscar")
    args = parser.parse_args()
    if args.empresa:
        t = de_empresa(activos.limpiar(args.empresa))
        print(f"{len(t)} noticias")
        print(t[["Fecha", "Fuente", "Titular"]].head(8).to_string(index=False))
    else:
        n = actualizar(args.dias)
        t = leer()
        print(f"{n} noticias nuevas. Total guardado: {len(t)}. Por tipo:")
        print(t[t["Grupo"] != "empresa"].groupby(["Grupo", "Tipo"]).size().to_string())
