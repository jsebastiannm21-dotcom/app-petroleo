# activos.py - Lista de activos y funciones comunes para descargar precios y calcular indicadores
# Todos los demás programas usan este archivo, así el análisis funciona con cualquier activo.
# Las listas (Nasdaq 100, petroleras, mineras) son de noviembre de 2026 y cambian con el tiempo.
# El resto del catálogo (unos 1.100 activos) viene de catalogo_ampliado.json (ver actualizar_listas.py).

import re
import time
from pathlib import Path

import pandas as pd
import yfinance as yf

CARPETA = Path(__file__).resolve().parent
DATOS = CARPETA / "datos"            # Aquí se guardan los precios de los activos (menos el WTI)
DATOS.mkdir(exist_ok=True)
PRINCIPAL = "CL=F"

# ---------- Catálogo ----------
# mercados: en qué pestañas aparece; noticias: qué grupos de eventos.csv le afectan
NASDAQ_100 = {
    "AAPL": "Apple", "ABNB": "Airbnb", "ADBE": "Adobe", "ADI": "Analog Devices", "ADP": "ADP",
    "ADSK": "Autodesk", "AEP": "American Electric Power", "ALAB": "Astera Labs", "ALNY": "Alnylam Pharmaceuticals",
    "AMAT": "Applied Materials", "AMD": "AMD", "AMGN": "Amgen", "AMZN": "Amazon", "APP": "AppLovin",
    "ARM": "Arm", "ASML": "ASML", "AVGO": "Broadcom", "AXON": "Axon", "BKNG": "Booking Holdings",
    "BKR": "Baker Hughes", "CCEP": "Coca-Cola Europacific Partners", "CDNS": "Cadence", "CEG": "Constellation Energy",
    "CMCSA": "Comcast", "COST": "Costco", "CPRT": "Copart", "CRWD": "CrowdStrike", "CRWV": "CoreWeave",
    "CSCO": "Cisco", "CSX": "CSX", "CTAS": "Cintas", "DASH": "DoorDash", "DDOG": "Datadog", "DXCM": "Dexcom",
    "EXC": "Exelon", "FANG": "Diamondback Energy", "FAST": "Fastenal", "FER": "Ferrovial", "FTNT": "Fortinet",
    "GEHC": "GE HealthCare", "GILD": "Gilead Sciences", "GOOG": "Alphabet (clase C)", "GOOGL": "Alphabet (clase A)",
    "HON": "Honeywell Technologies", "HONA": "Honeywell Aerospace", "IDXX": "Idexx Laboratories", "INTC": "Intel",
    "INTU": "Intuit", "ISRG": "Intuitive Surgical", "KDP": "Keurig Dr Pepper", "KLAC": "KLA", "LIN": "Linde",
    "LITE": "Lumentum", "LRCX": "Lam Research", "MAR": "Marriott", "MCHP": "Microchip Technology",
    "MDLZ": "Mondelez", "MELI": "MercadoLibre", "META": "Meta Platforms", "MNST": "Monster Beverage",
    "MPWR": "Monolithic Power Systems", "MRNA": "Moderna", "MRVL": "Marvell Technology", "MSFT": "Microsoft",
    "MSTR": "Strategy (MicroStrategy)", "MU": "Micron Technology", "NBIS": "Nebius Group", "NFLX": "Netflix",
    "NVDA": "Nvidia", "NXPI": "NXP", "ODFL": "Old Dominion", "ORLY": "O'Reilly Auto Parts", "PANW": "Palo Alto Networks",
    "PAYX": "Paychex", "PCAR": "Paccar", "PDD": "PDD Holdings", "PEP": "PepsiCo", "PLTR": "Palantir",
    "PYPL": "PayPal", "QCOM": "Qualcomm", "REGN": "Regeneron", "RKLB": "Rocket Lab", "ROP": "Roper Technologies",
    "ROST": "Ross Stores", "SBUX": "Starbucks", "SHOP": "Shopify", "SNDK": "Sandisk", "SNPS": "Synopsys",
    "SPCX": "SpaceX", "STX": "Seagate Technology", "TER": "Teradyne", "TMUS": "T-Mobile US", "TRI": "Thomson Reuters",
    "TSLA": "Tesla", "TTWO": "Take-Two Interactive", "TXN": "Texas Instruments", "VRTX": "Vertex",
    "WDAY": "Workday", "WDC": "Western Digital", "WMT": "Walmart", "XEL": "Xcel Energy",
}
PETROLERAS = {
    "XOM": "ExxonMobil", "CVX": "Chevron", "SHEL": "Shell", "TTE": "TotalEnergies", "COP": "ConocoPhillips",
    "BP": "BP", "EQNR": "Equinor", "PBR": "Petrobras", "EOG": "EOG Resources", "CNQ": "Canadian Natural Resources",
    "SU": "Suncor Energy", "E": "Eni", "OXY": "Occidental Petroleum", "FANG": "Diamondback Energy",
    "WDS": "Woodside Energy", "IMO": "Imperial Oil", "CVE": "Cenovus Energy", "DVN": "Devon Energy",
    "YPF": "YPF", "EC": "Ecopetrol",
}
MINERAS_ORO = {
    "NEM": "Newmont", "AEM": "Agnico Eagle", "B": "Barrick Mining", "GFI": "Gold Fields", "KGC": "Kinross Gold",
    "AU": "AngloGold Ashanti", "AGI": "Alamos Gold", "HMY": "Harmony Gold", "EGO": "Eldorado Gold",
    "CDE": "Coeur Mining",
}

ACTIVOS = {}
for s, n in NASDAQ_100.items():
    ACTIVOS[s] = {"nombre": n, "tipo": "acción", "mercados": ["nasdaq"], "noticias": ["nasdaq"]}
for s, n in PETROLERAS.items():
    if s in ACTIVOS:                                  # Diamondback está en el Nasdaq 100 y es petrolera
        ACTIVOS[s]["mercados"].append("petróleo")
        ACTIVOS[s]["noticias"].append("petróleo")
    else:
        ACTIVOS[s] = {"nombre": n, "tipo": "acción", "mercados": ["petróleo"], "noticias": ["petróleo"]}
ACTIVOS["EC"]["noticias"] = ["ecopetrol", "petróleo"]   # A Ecopetrol le afectan Colombia y el petróleo
for s, n in MINERAS_ORO.items():
    ACTIVOS[s] = {"nombre": n, "tipo": "acción", "mercados": ["oro"], "noticias": ["oro"]}
ACTIVOS.update({
    "CL=F": {"nombre": "Petróleo WTI", "tipo": "futuro", "mercados": ["petróleo"], "noticias": ["petróleo"]},
    "BZ=F": {"nombre": "Petróleo Brent", "tipo": "futuro", "mercados": ["petróleo"], "noticias": ["petróleo"]},
    "GC=F": {"nombre": "Oro", "tipo": "futuro", "mercados": ["oro"], "noticias": ["oro"]},
    "^NDX": {"nombre": "Índice Nasdaq 100", "tipo": "índice", "mercados": ["nasdaq"], "noticias": ["nasdaq"]},
    "GLD": {"nombre": "Fondo de oro GLD", "tipo": "etf", "mercados": ["etf", "oro"], "noticias": ["oro"]},
    "USO": {"nombre": "Fondo de petróleo USO", "tipo": "etf", "mercados": ["etf", "petróleo"], "noticias": ["petróleo"]},
    "QQQ": {"nombre": "Fondo Nasdaq 100 QQQ", "tipo": "etf", "mercados": ["etf", "nasdaq"], "noticias": ["nasdaq"]},
    "SPY": {"nombre": "Fondo S&P 500 SPY", "tipo": "etf", "mercados": ["etf"], "noticias": ["nasdaq"]},
    # Largo plazo: dividendos
    "SCHD": {"nombre": "Fondo de dividendos SCHD", "tipo": "etf", "mercados": ["etf", "dividendos"], "noticias": ["nasdaq"]},
    "VYM": {"nombre": "Fondo de dividendos VYM", "tipo": "etf", "mercados": ["etf", "dividendos"], "noticias": ["nasdaq"]},
    "VIG": {"nombre": "Fondo de dividendos VIG", "tipo": "etf", "mercados": ["etf", "dividendos"], "noticias": ["nasdaq"]},
    "KO": {"nombre": "Coca-Cola", "tipo": "acción", "mercados": ["dividendos"], "noticias": ["nasdaq"]},
    "JNJ": {"nombre": "Johnson & Johnson", "tipo": "acción", "mercados": ["dividendos"], "noticias": ["nasdaq"]},
    "PG": {"nombre": "Procter & Gamble", "tipo": "acción", "mercados": ["dividendos"], "noticias": ["nasdaq"]},
})
ACTIVOS["EC"]["mercados"].append("dividendos")
DIVIDENDOS = ["SCHD", "VYM", "VIG", "KO", "JNJ", "PG", "EC"]
# Solo para mirar (precio y gráfica): sin señales de compra, ranking ni alertas. Vacío por ahora.
SOLO_MIRAR = set()

# ---------- Colombia (Bolsa de Colombia, en pesos) y sus ADR en EE.UU. ----------
COLOMBIA = {
    "ECOPETROL.CL": ("Ecopetrol (Bolsa de Colombia)", "Petróleo y gas"),
    "CIBEST.CL": ("Grupo Cibest - Bancolombia (ordinaria)", "Bancos y finanzas"),
    "PFCIBEST.CL": ("Grupo Cibest - Bancolombia (preferencial)", "Bancos y finanzas"),
    "GRUPOAVAL.CL": ("Grupo Aval (ordinaria)", "Bancos y finanzas"), "PFAVAL.CL": ("Grupo Aval (preferencial)", "Bancos y finanzas"),
    "PFDAVVNDA.CL": ("Davivienda (preferencial)", "Bancos y finanzas"), "BOGOTA.CL": ("Banco de Bogotá", "Bancos y finanzas"),
    "CORFICOLCF.CL": ("Corficolombiana (ordinaria)", "Bancos y finanzas"),
    "PFCORFICOL.CL": ("Corficolombiana (preferencial)", "Bancos y finanzas"),
    "GRUPOSURA.CL": ("Grupo Sura (ordinaria)", "Bancos y finanzas"), "PFGRUPSURA.CL": ("Grupo Sura (preferencial)", "Bancos y finanzas"),
    "BVC.CL": ("Bolsa de Valores de Colombia", "Bancos y finanzas"),
    "ISA.CL": ("ISA (Interconexión Eléctrica)", "Energía eléctrica"), "CELSIA.CL": ("Celsia", "Energía eléctrica"),
    "GEB.CL": ("Grupo Energía Bogotá", "Energía eléctrica"), "PROMIGAS.CL": ("Promigas", "Energía eléctrica"),
    "GRUPOARGOS.CL": ("Grupo Argos (ordinaria)", "Industria"), "PFGRUPOARG.CL": ("Grupo Argos (preferencial)", "Industria"),
    "CEMARGOS.CL": ("Cementos Argos (ordinaria)", "Industria"), "PFCEMARGOS.CL": ("Cementos Argos (preferencial)", "Industria"),
    "ENKA.CL": ("Enka de Colombia", "Industria"), "MINEROS.CL": ("Mineros", "Minería de oro"),
    "TERPEL.CL": ("Terpel", "Petróleo y gas"), "CNEC.CL": ("Canacol Energy", "Petróleo y gas"),
    "NUTRESA.CL": ("Grupo Nutresa", "Consumo básico"), "ICOLCAP.CL": ("ETF iShares COLCAP (índice de Colombia)", "ETF (canasta)"),
    "CIB": ("Grupo Cibest - Bancolombia (ADR en Nueva York)", "Bancos y finanzas"),
    "AVAL": ("Grupo Aval (ADR en Nueva York)", "Bancos y finanzas"),
}
for s, (n, sector) in COLOMBIA.items():
    tipo = "etf" if s == "ICOLCAP.CL" else "acción"
    ACTIVOS[s] = {"nombre": n, "tipo": tipo, "mercados": ["colombia"], "noticias": ["ecopetrol"], "sector": sector}
ACTIVOS["EC"]["mercados"].append("colombia")

# ---------- Asia ----------
ASIA = {
    "^N225": ("Índice Nikkei 225 (Japón)", "índice"), "7203.T": ("Toyota (Bolsa de Tokio)", "acción"),
    "TM": ("Toyota (ADR en Nueva York)", "acción"), "6758.T": ("Sony (Bolsa de Tokio)", "acción"),
    "SONY": ("Sony (ADR en Nueva York)", "acción"), "^KS11": ("Índice KOSPI (Corea)", "índice"),
    "005930.KS": ("Samsung Electronics (Bolsa de Corea)", "acción"), "005380.KS": ("Hyundai Motor (Bolsa de Corea)", "acción"),
    "^TWII": ("Índice Taiex (Taiwán)", "índice"), "2330.TW": ("TSMC (Bolsa de Taiwán)", "acción"),
    "TSM": ("TSMC (ADR en Nueva York)", "acción"), "^HSI": ("Índice Hang Seng (Hong Kong)", "índice"),
    "9988.HK": ("Alibaba (Bolsa de Hong Kong)", "acción"), "BABA": ("Alibaba (ADR en Nueva York)", "acción"),
    "0700.HK": ("Tencent (Bolsa de Hong Kong)", "acción"), "TCEHY": ("Tencent (ADR fuera de bolsa, EE.UU.)", "acción"),
    "1211.HK": ("BYD (Bolsa de Hong Kong)", "acción"), "BYDDY": ("BYD (ADR fuera de bolsa, EE.UU.)", "acción"),
    "000001.SS": ("Índice de Shanghái (China)", "índice"), "^NSEI": ("Índice Nifty 50 (India)", "índice"),
    "RELIANCE.NS": ("Reliance Industries (Bolsa de India)", "acción"), "INFY": ("Infosys (ADR en Nueva York)", "acción"),
    "HDB": ("HDFC Bank (ADR en Nueva York)", "acción"),
    "EWJ": ("ETF de Japón (EWJ)", "etf"), "EWY": ("ETF de Corea (EWY)", "etf"),
    "FXI": ("ETF de China (FXI)", "etf"), "INDA": ("ETF de India (INDA)", "etf"),
}
for s, (n, tipo) in ASIA.items():
    ACTIVOS[s] = {"nombre": n, "tipo": tipo, "mercados": ["asia"] + (["etf"] if tipo == "etf" else []), "noticias": ["asia"]}

# ---------- Cripto (opera 24/7) ----------
CRIPTO = {"BTC-USD": "Bitcoin", "ETH-USD": "Ethereum", "XRP-USD": "XRP", "BNB-USD": "BNB", "SOL-USD": "Solana",
          "DOGE-USD": "Dogecoin", "ADA-USD": "Cardano", "TRX-USD": "Tron", "LINK-USD": "Chainlink"}
for s, n in CRIPTO.items():
    ACTIVOS[s] = {"nombre": n, "tipo": "cripto", "mercados": ["cripto"], "noticias": ["cripto"]}

# ---------- Futuros (para expertos, no se compran en Trii) ----------
FUTUROS = {"NG=F": ("Gas natural (futuro)", "petróleo"), "SI=F": ("Plata (futuro)", "oro"),
           "HG=F": ("Cobre (futuro)", "oro"), "NQ=F": ("Nasdaq 100 (futuro)", "nasdaq"),
           "ES=F": ("S&P 500 (futuro)", "nasdaq"), "YM=F": ("Dow Jones (futuro)", "nasdaq")}
for s, (n, grupo) in FUTUROS.items():
    ACTIVOS[s] = {"nombre": n, "tipo": "futuro", "mercados": ["futuros"], "noticias": [grupo]}
for s in ("CL=F", "BZ=F", "GC=F"):
    ACTIVOS[s]["mercados"].append("futuros")

# ---------- Estados Unidos (índices de Nueva York) ----------
for s, n in {"^GSPC": "Índice S&P 500", "^DJI": "Índice Dow Jones", "^RUT": "Índice Russell 2000 (empresas pequeñas)",
             "^IXIC": "Índice Nasdaq Composite"}.items():
    ACTIVOS[s] = {"nombre": n, "tipo": "índice", "mercados": ["eeuu"], "noticias": ["nasdaq"]}
ACTIVOS["^NDX"]["mercados"].append("eeuu")

# ---------- Europa ----------
EUROPA = {
    "^FTSE": ("Índice FTSE 100 (Londres)", "índice"), "^GDAXI": ("Índice DAX (Frankfurt)", "índice"),
    "^FCHI": ("Índice CAC 40 (París)", "índice"), "^STOXX50E": ("Índice Euro Stoxx 50 (Europa)", "índice"),
    "AZN.L": ("AstraZeneca (Londres)", "acción"), "HSBA.L": ("HSBC (Londres)", "acción"),
    "ULVR.L": ("Unilever (Londres)", "acción"), "SHEL.L": ("Shell (Londres)", "acción"),
    "SAP.DE": ("SAP (Frankfurt)", "acción"), "SIE.DE": ("Siemens (Frankfurt)", "acción"),
    "ALV.DE": ("Allianz (Frankfurt)", "acción"), "MC.PA": ("LVMH (París)", "acción"),
    "OR.PA": ("L'Oréal (París)", "acción"), "AIR.PA": ("Airbus (París)", "acción"),
}
for s, (n, tipo) in EUROPA.items():
    ACTIVOS[s] = {"nombre": n, "tipo": tipo, "mercados": ["europa"], "noticias": ["europa"]}

# ---------- Materias primas (incluye las que más pesan en Colombia: petróleo, oro y café) ----------
ACTIVOS["KC=F"] = {"nombre": "Café arábica (futuro)", "tipo": "futuro", "mercados": ["materias", "colombia", "futuros"],
                   "noticias": ["ecopetrol"]}
for s in ("CL=F", "BZ=F", "NG=F", "GC=F", "SI=F", "HG=F", "KC=F"):
    if "materias" not in ACTIVOS[s]["mercados"]:
        ACTIVOS[s]["mercados"].append("materias")
for s in ("CL=F", "BZ=F", "GC=F"):                     # Pesan en la economía colombiana
    ACTIVOS[s]["mercados"].append("colombia")

# ---------- Catálogo ampliado (S&P 500, Europa, Asia, energía, minería, materias, cripto, bonos, dividendos) ----------
# Lo arma y verifica actualizar_listas.py. Si un activo ya existía, solo se le suman mercados (no se cambia nada más).
_AMPLIADO = CARPETA / "catalogo_ampliado.json"
if _AMPLIADO.exists():
    import json
    for s, d in json.loads(_AMPLIADO.read_text(encoding="utf-8"))["activos"].items():
        if s in ACTIVOS:
            for campo in ("mercados", "noticias"):
                ACTIVOS[s][campo] += [m for m in d[campo] if m not in ACTIVOS[s][campo]]
        else:
            ACTIVOS[s] = {k: v for k, v in d.items() if v is not None}

# Revisión de TODOS los activos: si Yahoo Finance dice otro tipo (por ejemplo, que algo es una cripto y no un ETF),
# manda Yahoo. Las tasas del Tesoro se quedan como "bono" (Yahoo las llama índice).
QUOTE_TIPO = {"EQUITY": "acción", "ETF": "etf", "MUTUALFUND": "etf", "INDEX": "índice", "FUTURE": "futuro",
              "CRYPTOCURRENCY": "cripto", "CURRENCY": "divisa"}
CORREGIDOS = {}                                         # símbolo -> (tipo que tenía, tipo corregido)
_FICHAS = CARPETA / "fichas.json"
if _FICHAS.exists():
    import json
    for s, f in json.loads(_FICHAS.read_text(encoding="utf-8")).items():
        correcto = QUOTE_TIPO.get((f.get("yahoo") or {}).get("quoteType"))
        if s in ACTIVOS and correcto and ACTIVOS[s]["tipo"] not in (correcto, "bono"):
            CORREGIDOS[s] = (ACTIVOS[s]["tipo"], correcto)
            ACTIVOS[s]["tipo"] = correcto
    del json

# Sectores que Yahoo no trae (fondos de inversión de Londres)
for _s, _sec in {"ALW.L": "Bancos y finanzas", "FCIT.L": "Bancos y finanzas", "SMT.L": "Bancos y finanzas",
                 "PCT.L": "Tecnología", "BBOX.L": "Inmobiliario"}.items():
    if _s in ACTIVOS:
        ACTIVOS[_s]["sector"] = _sec

TIPO_NOMBRE = {"acción": "Acción", "etf": "ETF", "índice": "Índice", "futuro": "Futuro", "cripto": "Cripto",
               "bono": "Bono", "divisa": "Divisa"}
# ETFs que copian a cada índice: el "Comprar" de un índice se refiere a su ETF
INDICE_ETF = {"^GSPC": ["SPY", "VOO"], "^NDX": ["QQQ"], "^IXIC": ["ONEQ", "QQQ"], "^DJI": ["DIA"], "^RUT": ["IWM"],
              "^STOXX50E": ["FEZ"], "^FTSE": ["EWU"], "^GDAXI": ["EWG"], "^FCHI": ["EWQ"], "^N225": ["EWJ"],
              "^HSI": ["EWH"], "000001.SS": ["MCHI", "FXI"], "^KS11": ["EWY"], "^TWII": ["EWT"], "^NSEI": ["INDA"],
              "^BVSP": ["EWZ"], "^MXX": ["EWW"], "^IRX": ["SHY"], "^FVX": ["IEF"], "^TNX": ["IEF"], "^TYX": ["TLT"]}
ETF_DE_INDICE = {e: i for i, etfs in INDICE_ETF.items() if not i.startswith(("^IRX", "^FVX", "^TNX", "^TYX"))
                 for e in etfs}


def tipo(simbolo):
    return ACTIVOS.get(simbolo, {}).get("tipo", "acción")


def tipo_nombre(simbolo):
    return TIPO_NOMBRE.get(tipo(simbolo), "Acción")


def que_es(simbolo):
    """Una frase de qué es el activo, para la ventana de confirmación: 'un ETF que sigue al S&P 500'."""
    n, t = nombre(simbolo), tipo(simbolo)
    if simbolo in ETF_DE_INDICE:
        return f"un ETF (una canasta que se compra como una acción) que sigue al {nombre(ETF_DE_INDICE[simbolo])}"
    return {"acción": f"una acción: un pedacito de la empresa {n}",
            "etf": f"un ETF: una canasta de muchos activos que se compra como una sola acción ({n})",
            "índice": f"un índice ({n}): una medida del mercado que no se compra directamente, sino con su ETF",
            "futuro": f"un futuro ({n}): un contrato para comprar o vender en una fecha futura, para expertos",
            "cripto": f"una criptomoneda ({n}): dinero digital que opera las 24 horas y se mueve mucho",
            "bono": f"una tasa de interés de bonos ({n}): se invierte a través de ETFs de bonos",
            "divisa": f"una divisa ({n}): el precio de una moneda frente a otra"}[t]


DESCRIPCION_FUTUROS = {
    "KC=F": "Contrato sobre 37.500 libras de café arábica, el que produce Colombia. Se mueve con el clima en Brasil.",
    "CL=F": "Contrato para comprar o vender 1.000 barriles de petróleo WTI (Texas) en una fecha futura.",
    "BZ=F": "Contrato sobre 1.000 barriles de petróleo Brent (Mar del Norte), la referencia de Europa y Colombia.",
    "NG=F": "Contrato sobre gas natural de EE.UU. (10.000 MMBtu). Se mueve mucho con el clima y el invierno.",
    "GC=F": "Contrato sobre 100 onzas de oro.", "SI=F": "Contrato sobre 5.000 onzas de plata.",
    "HG=F": "Contrato sobre 25.000 libras de cobre: un termómetro de la industria y de China.",
    "NQ=F": "Contrato que sigue al índice Nasdaq 100 (tecnológicas de EE.UU.).",
    "ES=F": "Contrato que sigue al índice S&P 500 (las 500 empresas más grandes de EE.UU.).",
    "YM=F": "Contrato que sigue al índice Dow Jones (30 empresas grandes de EE.UU.).",
}

# Cada mercado es un bloque independiente: pon False para apagarlo (desaparece de pestañas, filtros y carrusel)
MERCADOS_ACTIVOS = {"eeuu": True, "nasdaq": True, "petróleo": True, "oro": True, "materias": True, "colombia": True,
                    "latam": True, "europa": True, "asia": True, "cripto": True, "futuros": True, "divisas": True,
                    "etf": True, "bonos": True, "dividendos": True}


def mercado_activo(m):
    return MERCADOS_ACTIVOS.get(m, True)


# Las tres "referencias" de cada mercado (las gráficas del Inicio)
REFERENCIAS = {"nasdaq": "^NDX", "petróleo": "CL=F", "oro": "GC=F"}
NOMBRE_MERCADO = {"eeuu": "Estados Unidos", "nasdaq": "Nasdaq", "petróleo": "Petróleo", "oro": "Oro",
                  "materias": "Materias primas", "colombia": "Colombia", "europa": "Europa", "asia": "Asia",
                  "latam": "Latinoamérica", "divisas": "Divisas", "cripto": "Cripto", "bonos": "Bonos", "futuros": "Futuros", "etf": "ETFs", "dividendos": "Dividendos"}
ICONO_MERCADO = {"eeuu": "🇺🇸", "nasdaq": "💻", "petróleo": "🛢️", "oro": "🥇", "materias": "🌾", "colombia": "🇨🇴",
                 "europa": "🇪🇺", "asia": "🌏", "latam": "🌎", "divisas": "💱", "cripto": "🪙", "bonos": "🏛️", "futuros": "📜", "etf": "🧺", "dividendos": "💵"}
# Activo de referencia de cada mercado (tendencia, estacionalidad). El Inicio muestra los tres primeros.
REFERENCIAS_MERCADO = {"eeuu": "^GSPC", "nasdaq": "^NDX", "petróleo": "CL=F", "oro": "GC=F", "materias": "CL=F",
                       "colombia": "ICOLCAP.CL", "europa": "^STOXX50E", "asia": "^N225", "latam": "^BVSP", "divisas": "COP=X", "cripto": "BTC-USD", "bonos": "^TNX",
                       "futuros": "ES=F", "etf": "SPY", "dividendos": "SCHD"}
# Estacionalidad de cada mercado: sus activos más representativos
ESTACIONALIDAD_MERCADO = {"petróleo": ["CL=F", "BZ=F"], "colombia": ["ICOLCAP.CL", "KC=F"], "materias": ["CL=F", "GC=F", "KC=F"]}
# Paneles del carrusel del Inicio, los mismos mercados de Seguimiento:
# (nombre, mercados que cubre, activos que se grafican, banco central y moneda o None)
PANELES = [
    ("Estados Unidos", {"eeuu", "nasdaq", "dividendos"}, ["^GSPC", "^IXIC", "^DJI", "^RUT", "^TNX", "DX-Y.NYB"],
     ("Reserva Federal (Fed)", "Fija la tasa de interés de EE.UU.: si la sube, el dólar suele subir y las acciones bajar.",
      "Dólar (índice DXY)")),
    ("Europa", {"europa"}, ["^STOXX50E", "^FTSE", "^GDAXI", "^FCHI", "EURUSD=X", "GBPUSD=X"],
     ("Banco Central Europeo (BCE)", "Fija la tasa del euro para 20 países.", "Euro y libra (EUR/USD, GBP/USD)")),
    ("Asia", {"asia"}, ["^N225", "^HSI", "000001.SS", "^KS11", "^NSEI", "JPY=X"],
     ("Banco de Japón y Banco Popular de China", "Japón tiene tasas muy bajas; si las sube, el yen se fortalece.",
      "Yen y yuan (USD/JPY, USD/CNY)")),
    ("Latinoamérica", {"latam"}, ["^BVSP", "^MXX", "ECH", "EPU", "ARGT", "BRL=X"],
     ("Bancos centrales de Brasil, México, Chile, Perú y Argentina", "Tasas altas para controlar la inflación.",
      "Real, peso mexicano y demás (USD/BRL, USD/MXN)")),
    ("Colombia", {"colombia"}, ["ICOLCAP.CL", "ECOPETROL.CL", "CIBEST.CL", "COP=X", "KC=F", "EC"],
     ("Banco de la República", "Fija la tasa de interés de Colombia. TES (bonos del gobierno): sin datos diarios "
      "gratuitos en Yahoo.", "Peso colombiano (USD/COP)")),
    ("Materias primas", {"materias"}, ["CL=F", "BZ=F", "GC=F", "KC=F", "HG=F", "ZC=F"], None),
    ("Cripto", {"cripto"}, ["BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD", "BNB-USD", "DOGE-USD"], None),
    ("Futuros", {"futuros"}, ["ES=F", "NQ=F", "YM=F", "CL=F", "GC=F", "NG=F"], None),
    ("Divisas", {"divisas"}, ["COP=X", "EURUSD=X", "MXN=X", "BRL=X", "JPY=X", "DX-Y.NYB"], None),
    ("ETFs", {"etf"}, ["SPY", "QQQ", "VOO", "GLD", "SCHD", "EWZ"], None),
    ("Bonos globales", {"bonos"}, ["^TNX", "^TYX", "TLT", "BND", "BNDX", "EMB"], None),
]

# ---------- Sector con ícono y texto (para que se entienda) ----------
SECTORES = {"Technology": "Tecnología", "Communication Services": "Comunicaciones", "Consumer Cyclical": "Consumo",
            "Consumer Defensive": "Consumo básico", "Healthcare": "Salud", "Financial Services": "Bancos y finanzas",
            "Energy": "Petróleo y gas", "Utilities": "Energía eléctrica", "Industrials": "Industria",
            "Basic Materials": "Materiales y minería", "Real Estate": "Inmobiliario"}
ICONO_SECTOR = {"Tecnología": "💻", "Comunicaciones": "📡", "Consumo": "🛍️", "Consumo básico": "🛒", "Salud": "💊",
                "Bancos y finanzas": "🏦", "Petróleo y gas": "🛢️", "Energía eléctrica": "⚡", "Industria": "🏭",
                "Materiales y minería": "⛏️", "Minería de oro": "⛏️", "Inmobiliario": "🏢", "Oro y metales": "🥇",
                "ETF (canasta)": "🧺", "Futuros": "📜", "Cripto": "🪙", "Índice": "📊", "Empresa": "🏢"}
ICONO_SECTOR.update({"Varios sectores": "🧩", "Divisas": "💱", "Bonos": "🏛️", "Energía (petróleo y gas)": "🛢️",
                     "Metales": "🥇", "Agrícola y ganado": "🌾", "Sin dato de sector": "❔"})
# Activos que el simulador y las revisiones de Telegram siguen siempre
SIMULAR = ["CL=F", "BZ=F", "GC=F", "GLD", "USO", "QQQ", "SPY", "EC"]


def limpiar(simbolo):
    return simbolo.strip().upper()


def nombre(simbolo):
    return ACTIVOS.get(simbolo, {}).get("nombre", simbolo)


def mercados(simbolo):
    return ACTIVOS.get(simbolo, {}).get("mercados", [])


def noticias(simbolo):
    return ACTIVOS.get(simbolo, {}).get("noticias", [])


SECTOR_FUTURO = {"petróleo": "Energía (petróleo y gas)", "oro": "Metales", "agro": "Agrícola y ganado",
                 "ecopetrol": "Agrícola y ganado", "nasdaq": "Varios sectores"}
SECTOR_MERCADO = {"petróleo": "Petróleo y gas", "oro": "Materiales y minería"}


def sector(simbolo):
    """Sector real en palabras sencillas (manual, por tipo o según Yahoo Finance). Nunca 'Empresa'."""
    a = ACTIVOS.get(simbolo, {})
    t = a.get("tipo")
    if t == "índice":
        return "Varios sectores"
    if t in ("cripto", "divisa", "bono"):
        return {"cripto": "Cripto", "divisa": "Divisas", "bono": "Bonos"}[t]
    if t == "futuro":
        return SECTOR_FUTURO.get((a.get("noticias") or ["nasdaq"])[0], "Varios sectores")
    if a.get("sector"):
        return a["sector"]
    if t == "etf":
        if "bonos" in a.get("mercados", []):
            return "Bonos"
        return {"GLD": "Oro y metales", "USO": "Petróleo y gas"}.get(simbolo, "Varios sectores")
    if simbolo in MINERAS_ORO:
        return "Minería de oro"
    if simbolo in PETROLERAS:
        return "Petróleo y gas"
    import fichas
    yahoo = SECTORES.get(fichas.datos(simbolo).get("sector"))
    if yahoo:
        return yahoo
    return next((SECTOR_MERCADO[m] for m in a.get("mercados", []) if m in SECTOR_MERCADO), "Sin dato de sector")


PAISES = {"United States": "Estados Unidos", "United Kingdom": "Reino Unido", "Germany": "Alemania",
          "France": "Francia", "Netherlands": "Países Bajos", "Spain": "España", "Italy": "Italia",
          "Switzerland": "Suiza", "Japan": "Japón", "China": "China", "Hong Kong": "Hong Kong",
          "South Korea": "Corea del Sur", "Taiwan": "Taiwán", "India": "India", "Brazil": "Brasil", "Mexico": "México",
          "Chile": "Chile", "Peru": "Perú", "Argentina": "Argentina", "Colombia": "Colombia", "Canada": "Canadá",
          "Ireland": "Irlanda", "Belgium": "Bélgica", "Finland": "Finlandia", "Denmark": "Dinamarca",
          "Sweden": "Suecia", "Norway": "Noruega", "Australia": "Australia", "South Africa": "Sudáfrica",
          "Luxembourg": "Luxemburgo", "Bermuda": "Bermudas", "Israel": "Israel", "Uruguay": "Uruguay",
          "Singapore": "Singapur", "Jersey": "Jersey", "Cayman Islands": "Islas Caimán", "Austria": "Austria",
          "Portugal": "Portugal", "Greece": "Grecia", "Panama": "Panamá", "Macau": "Macao", "Guernsey": "Guernsey"}
PAIS_SUFIJO = {"CO": "Colombia", "JP": "Japón", "KR": "Corea del Sur", "TW": "Taiwán", "HK": "Hong Kong",
               "CN": "China", "IN": "India", "GB": "Reino Unido", "DE": "Alemania", "FR": "Francia",
               "NL": "Países Bajos", "IT": "Italia", "ES": "España", "BE": "Bélgica", "FI": "Finlandia",
               "CA": "Canadá", "BR": "Brasil", "MX": "México", "CL": "Chile"}


def pais(simbolo):
    """País en español: el que dice Yahoo, o por la bolsa donde cotiza."""
    a = ACTIVOS.get(simbolo, {})
    t = a.get("tipo")
    if t == "cripto":
        return "Global (no tiene país)"
    if t == "divisa":
        return "Mercado mundial de divisas"
    if t == "bono":
        return "Estados Unidos"
    if t == "futuro":
        return "Estados Unidos (bolsas de Chicago y Nueva York)"
    if a.get("pais"):
        return a["pais"]
    suf = _sufijo(simbolo)
    if suf:
        return PAIS_SUFIJO.get(SUFIJOS[suf][4], "—")
    import fichas
    en = fichas.datos(simbolo).get("country")
    if en:
        return PAISES.get(en, en)
    return "Estados Unidos (fondo de EE.UU.)" if t == "etf" else "Estados Unidos"


def etiqueta_sector(simbolo):
    s = sector(simbolo)
    return f"{ICONO_SECTOR.get(s, '🏢')} {s}"


def icono(simbolo):
    return ICONO_SECTOR.get(sector(simbolo), "🏢")


# ---------- Moneda, horario y dónde comprar ----------
SUFIJOS = {  # sufijo de Yahoo -> (moneda, zona horaria, abre, cierra, código de festivos)
    ".CL": ("COP", "America/Bogota", "09:30", "15:55", "CO"), ".T": ("JPY", "Asia/Tokyo", "09:00", "15:30", "JP"),
    ".KS": ("KRW", "Asia/Seoul", "09:00", "15:30", "KR"), ".TW": ("TWD", "Asia/Taipei", "09:00", "13:30", "TW"),
    ".HK": ("HKD", "Asia/Hong_Kong", "09:30", "16:00", "HK"), ".SS": ("CNY", "Asia/Shanghai", "09:30", "15:00", "CN"),
    ".NS": ("INR", "Asia/Kolkata", "09:15", "15:30", "IN"),
    ".L": ("GBp", "Europe/London", "08:00", "16:30", "GB"),      # Londres cotiza en peniques (centavos de libra)
    ".DE": ("EUR", "Europe/Berlin", "09:00", "17:30", "DE"), ".PA": ("EUR", "Europe/Paris", "09:00", "17:30", "FR"),
    ".AS": ("EUR", "Europe/Amsterdam", "09:00", "17:30", "NL"), ".MI": ("EUR", "Europe/Rome", "09:00", "17:30", "IT"),
    ".MC": ("EUR", "Europe/Madrid", "09:00", "17:30", "ES"), ".BR": ("EUR", "Europe/Brussels", "09:00", "17:30", "BE"),
    ".HE": ("EUR", "Europe/Helsinki", "10:00", "18:30", "FI"), ".TO": ("CAD", "America/Toronto", "09:30", "16:00", "CA"),
    ".SA": ("BRL", "America/Sao_Paulo", "10:00", "17:00", "BR"), ".MX": ("MXN", "America/Mexico_City", "08:30", "15:00", "MX"),
    ".SN": ("CLP", "America/Santiago", "09:30", "16:00", "CL"),
}
INDICES_BOLSA = {"^N225": ".T", "^KS11": ".KS", "^TWII": ".TW", "^HSI": ".HK", "000001.SS": ".SS", "^NSEI": ".NS",
                 "^FTSE": ".L", "^GDAXI": ".DE", "^FCHI": ".PA", "^STOXX50E": ".DE", "^BVSP": ".SA", "^MXX": ".MX"}


def _sufijo(simbolo):
    if simbolo in INDICES_BOLSA:
        return INDICES_BOLSA[simbolo]
    return next((suf for suf in SUFIJOS if simbolo.endswith(suf)), None)


def es_cripto(simbolo):
    return ACTIVOS.get(simbolo, {}).get("tipo") == "cripto" or simbolo.endswith("-USD")


def horario(simbolo):
    """Horario de la bolsa en hora de Bogotá (se calcula con la zona horaria, así respeta el horario de verano)."""
    from datetime import datetime, time
    from zoneinfo import ZoneInfo
    if es_cripto(simbolo):
        return "24 horas, los 7 días"
    if tipo(simbolo) == "divisa":
        return "24 horas, de domingo 4:00 p.m. a viernes 4:00 p.m. (hora de Bogotá)"
    bogota = ZoneInfo("America/Bogota")
    hoy = datetime.now(bogota).date()
    a_bogota = lambda h, zona: datetime.combine(hoy, time(*map(int, h.split(":"))), ZoneInfo(zona)).astimezone(bogota)
    if ACTIVOS.get(simbolo, {}).get("tipo") == "futuro":
        abre, pausa = a_bogota("17:00", "America/Chicago"), a_bogota("16:00", "America/Chicago")
        return (f"Domingo {abre:%I:%M %p} a viernes {pausa:%I:%M %p}, con pausa diaria de {pausa:%I:%M %p} a "
                f"{abre:%I:%M %p} (hora de Bogotá)")
    suf = _sufijo(simbolo)
    _, zona, ini, fin, _ = SUFIJOS[suf] if suf else ("USD", "America/New_York", "09:30", "16:00", "US")
    return f"{a_bogota(ini, zona):%I:%M %p} a {a_bogota(fin, zona):%I:%M %p} (hora de Bogotá)"


def festivos_de(simbolo, anios):
    """Festivos del mercado donde cotiza el activo."""
    import holidays
    suf = _sufijo(simbolo)
    if suf:
        return holidays.country_holidays(SUFIJOS[suf][4], years=anios)
    return holidays.financial_holidays("NYSE", years=anios)


def donde_comprar(simbolo):
    tipo = ACTIVOS.get(simbolo, {}).get("tipo")
    if es_cripto(simbolo):
        return "eToro (no está en Trii)"
    if tipo == "futuro":
        return "Solo expertos: no se compran en Trii"
    if tipo == "divisa":
        return "Solo mirar: no se compra en Trii (sirve para saber cuántos pesos cuesta lo que compras en dólares)"
    if tipo == "bono":
        return f"No se compra directamente: se invierte con ETFs de bonos ({', '.join(INDICE_ETF.get(simbolo, ['TLT', 'IEF']))})"
    if tipo == "índice" or simbolo.startswith("^"):
        etfs = INDICE_ETF.get(simbolo)
        return f"Se compra a través de su ETF ({' o '.join(etfs)})" if etfs else "Solo mirar (es un índice)"
    if simbolo.endswith(".CL"):
        return "Trii (Bolsa de Colombia)"
    if simbolo.endswith((".L", ".DE", ".PA", ".AS", ".MI", ".MC", ".BR", ".HE")):
        return "eToro (acciones europeas)"
    if _sufijo(simbolo):
        return "eToro (algunas) o solo mirar"
    return "eToro; en Trii si la tiene en su lista de acciones de EE.UU."


def etiqueta(simbolo):
    return f"{simbolo} · {nombre(simbolo)}" if simbolo in ACTIVOS else simbolo


def _slug(simbolo):
    return re.sub(r"[^A-Za-z0-9]+", "_", simbolo).strip("_")


# El WTI conserva sus archivos de siempre para que los programas de las etapas 1 a 7 sigan funcionando
def ruta_precios(simbolo):
    return CARPETA / "precios_petroleo.csv" if simbolo == PRINCIPAL else DATOS / f"precios_{_slug(simbolo)}.csv"


def ruta_indicadores(simbolo):
    return CARPETA / "indicadores.csv" if simbolo == PRINCIPAL else DATOS / f"indicadores_{_slug(simbolo)}.csv"


def _guardar(simbolo, datos):
    if isinstance(datos.columns, pd.MultiIndex):
        datos.columns = datos.columns.get_level_values(0)
    datos = datos.rename(columns={"Open": "Apertura", "High": "Maximo", "Low": "Minimo", "Close": "Cierre",
                                  "Adj Close": "Cierre_Ajustado", "Volume": "Volumen"})
    datos.index.name = "Fecha"
    datos = datos.dropna(subset=["Cierre"])
    if len(datos) < 30:
        raise ValueError(f"'{simbolo}' tiene muy pocos datos ({len(datos)} días)")
    datos.to_csv(ruta_precios(simbolo))
    tabla = calcular_indicadores(datos["Cierre"])
    tabla.to_csv(ruta_indicadores(simbolo))
    return datos


def descargar(simbolo, periodo="5y"):
    """Baja los precios diarios de un activo y los guarda (con sus indicadores). Devuelve la tabla."""
    datos = yf.download(simbolo, period=periodo, interval="1d", auto_adjust=False, progress=False)
    if datos.empty:
        raise ValueError(f"No encontré datos para '{simbolo}'. Revisa el símbolo en finance.yahoo.com")
    return _guardar(simbolo, datos)


def actualizar_varios(simbolos, periodo="5y", tanda=40):
    """Descarga muchos activos en pocas llamadas. Devuelve la lista de los que fallaron."""
    fallidos = []
    simbolos = list(dict.fromkeys(simbolos))
    for i in range(0, len(simbolos), tanda):
        grupo = simbolos[i:i + tanda]
        datos = yf.download(grupo, period=periodo, interval="1d", auto_adjust=False, progress=False,
                            group_by="ticker", threads=True)
        for s in grupo:
            try:
                _guardar(s, datos[s].copy() if len(grupo) > 1 else datos.copy())
            except Exception:
                fallidos.append(s)
        time.sleep(1)                                   # Pausa corta para no saturar a Yahoo
    for s in list(fallidos):                            # Segundo intento, uno por uno
        try:
            descargar(s, periodo)
            fallidos.remove(s)
        except Exception:
            pass
    return fallidos


def calcular_indicadores(cierre):
    """Medias móviles de 50 y 200 días y RSI de 14 días (método de Wilder)."""
    tabla = pd.DataFrame({"Cierre": cierre})
    tabla["MM50"] = cierre.rolling(50).mean()
    tabla["MM200"] = cierre.rolling(200).mean()
    cambio = cierre.diff()
    subidas = cambio.clip(lower=0).ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    bajadas = (-cambio.clip(upper=0)).ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    tabla["RSI14"] = 100 - 100 / (1 + subidas / bajadas)
    return tabla.round(4 if cierre.min() >= 0.01 else 12)   # Monedas de menos de un centavo (PEPE, BONK) necesitan más decimales


def actualizar(simbolo):
    """Descarga precios y recalcula indicadores. Devuelve la tabla de indicadores."""
    descargar(simbolo)
    return pd.read_csv(ruta_indicadores(simbolo), index_col="Fecha", parse_dates=True)


def asegurar_datos(simbolo):
    """Si el activo nunca se ha descargado, lo descarga."""
    if not ruta_indicadores(simbolo).exists() or not ruta_precios(simbolo).exists():
        descargar(simbolo)


def precio_y_moneda(simbolo):
    """Último precio disponible (en vivo si el mercado está abierto) y su moneda."""
    info = yf.Ticker(simbolo).fast_info
    return float(info["last_price"]), (info.get("currency") or "USD").upper()


def precio_ahora(simbolo):
    """(precio, moneda, mercado_abierto). Con el mercado cerrado, el precio es el último cierre.
    Cripto: precio en vivo de Binance (opera 24/7)."""
    if es_cripto(simbolo):
        import binance
        vivo = binance.precio(simbolo)
        if vivo:
            return vivo, "USD", True
    precio, moneda = precio_y_moneda(simbolo)
    try:
        abierto = yf.Ticker(simbolo).info.get("marketState") == "REGULAR"
    except Exception:
        abierto = False
    return precio, moneda, abierto


def moneda(simbolo):
    """Moneda en que cotiza: por el sufijo del símbolo (.CL = pesos, .T = yenes...); si no tiene, dólares."""
    suf = _sufijo(simbolo)
    if suf:
        return SUFIJOS[suf][0]
    if tipo(simbolo) == "divisa":                      # COP=X vale en pesos; EURUSD=X vale en dólares
        par = simbolo.replace("=X", "")
        return par[-3:]
    return "USD" if simbolo in ACTIVOS or "." not in simbolo else precio_y_moneda(simbolo)[1]


_tasas_usd = {}


def tasa_usd(moneda_local):
    """Cuántas unidades de esa moneda vale 1 dólar hoy (COP: ~3.900). 1 para dólares."""
    if moneda_local == "USD":
        return 1.0
    if moneda_local == "GBp":                          # Peniques: 100 por libra
        return tasa_usd("GBP") * 100
    if moneda_local not in _tasas_usd:
        guardado = ruta_precios(f"{moneda_local}=X")     # Primero la divisa ya descargada (rápido, sin internet)
        al_reves = ruta_precios(f"{moneda_local}USD=X")  # Euro, libra: se guardan como dólares por unidad
        if guardado.exists():
            _tasas_usd[moneda_local] = float(pd.read_csv(guardado, usecols=["Cierre"])["Cierre"].iloc[-1])
        elif al_reves.exists():
            _tasas_usd[moneda_local] = 1 / float(pd.read_csv(al_reves, usecols=["Cierre"])["Cierre"].iloc[-1])
        else:
            _tasas_usd[moneda_local] = precio_y_moneda(f"{moneda_local}=X")[0]
    return _tasas_usd[moneda_local]


def tasa_cop_en(cuando):
    """Pesos por dólar en una fecha y hora (para guardar la tasa del día de cada operación)."""
    return precio_en("COP=X", cuando) or tasa_usd("COP")


def precio_en(simbolo, cuando):
    """Precio real en una fecha y hora (vela de 1 hora si es de los últimos 2 años; si no, cierre del día)."""
    cuando = pd.Timestamp(cuando)
    try:
        if (pd.Timestamp.now() - cuando).days < 700:
            velas = yf.download(simbolo, start=(cuando - pd.Timedelta(days=4)).date(),
                                end=(cuando + pd.Timedelta(days=1)).date(), interval="1h",
                                progress=False, auto_adjust=False)
            if not velas.empty:
                if isinstance(velas.columns, pd.MultiIndex):
                    velas.columns = velas.columns.get_level_values(0)
                idx = velas.index.tz_convert("America/Bogota").tz_localize(None)
                antes = velas["Close"][idx <= cuando]
                if len(antes):
                    return float(antes.iloc[-1])
        diario = pd.read_csv(ruta_precios(simbolo), index_col="Fecha", parse_dates=True)["Cierre"]
        return float(diario[diario.index <= cuando.normalize()].iloc[-1])
    except Exception:
        return None
