# actualizar_listas.py - Arma el catálogo ampliado (catalogo_ampliado.json) y verifica cada símbolo en yfinance.
# - Baja de Wikipedia: S&P 500, Euro Stoxx 50, FTSE 100, DAX 40, Hang Seng, Nifty 50 y aristócratas del dividendo.
# - Listas a mano (las más grandes por capitalización, noviembre de 2026): Japón, Corea, Taiwán, petróleo y gas,
#   mineras, materias primas, cripto, bonos y ETFs de dividendos.
# - Descarta los símbolos sin datos recientes en Yahoo y guarda la lista de descartados.
# Uso:  python actualizar_listas.py      (tarda unos minutos; correrlo cada pocos meses basta)

import io
import json
import sys
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import requests
import yfinance as yf

import activos

ARCHIVO = activos.CARPETA / "catalogo_ampliado.json"
WIKI = "https://en.wikipedia.org/wiki/"
CABECERA = {"User-Agent": "Mozilla/5.0 (app-petroleo: lista de indices)"}
GICS = {"Information Technology": "Tecnología", "Health Care": "Salud", "Financials": "Bancos y finanzas",
        "Consumer Discretionary": "Consumo", "Consumer Staples": "Consumo básico", "Energy": "Petróleo y gas",
        "Utilities": "Energía eléctrica", "Industrials": "Industria", "Materials": "Materiales y minería",
        "Real Estate": "Inmobiliario", "Communication Services": "Comunicaciones"}

JAPON = {"7203": "Toyota", "8306": "Mitsubishi UFJ", "6758": "Sony", "6501": "Hitachi", "9984": "SoftBank Group",
         "6861": "Keyence", "8316": "Sumitomo Mitsui Financial", "9983": "Fast Retailing (Uniqlo)",
         "8035": "Tokyo Electron", "9432": "NTT", "4063": "Shin-Etsu Chemical", "8058": "Mitsubishi Corp",
         "8001": "Itochu", "9433": "KDDI", "6098": "Recruit", "7974": "Nintendo", "8411": "Mizuho", "4502": "Takeda",
         "6857": "Advantest", "8766": "Tokio Marine", "7011": "Mitsubishi Heavy Industries", "8031": "Mitsui & Co",
         "4568": "Daiichi Sankyo", "6367": "Daikin", "6981": "Murata", "7267": "Honda", "6503": "Mitsubishi Electric",
         "9434": "SoftBank Corp", "4519": "Chugai Pharmaceutical", "6902": "Denso", "7741": "HOYA", "8002": "Marubeni",
         "6702": "Fujitsu", "4661": "Oriental Land", "6273": "SMC", "2914": "Japan Tobacco", "8053": "Sumitomo Corp",
         "6301": "Komatsu", "7751": "Canon", "6954": "Fanuc", "4543": "Terumo", "3382": "Seven & i",
         "5108": "Bridgestone", "8801": "Mitsui Fudosan"}
COREA = {"005930": "Samsung Electronics", "000660": "SK Hynix", "373220": "LG Energy Solution",
         "207940": "Samsung Biologics", "005380": "Hyundai Motor", "000270": "Kia", "068270": "Celltrion",
         "005490": "POSCO Holdings", "035420": "NAVER", "105560": "KB Financial", "055550": "Shinhan Financial",
         "012330": "Hyundai Mobis", "006400": "Samsung SDI", "051910": "LG Chem", "035720": "Kakao",
         "028260": "Samsung C&T", "012450": "Hanwha Aerospace", "329180": "HD Hyundai Heavy Industries",
         "086790": "Hana Financial", "032830": "Samsung Life", "015760": "KEPCO (Korea Electric Power)",
         "066570": "LG Electronics", "034020": "Doosan Enerbility", "009150": "Samsung Electro-Mechanics",
         "017670": "SK Telecom", "033780": "KT&G", "010130": "Korea Zinc", "042660": "Hanwha Ocean",
         "316140": "Woori Financial", "018260": "Samsung SDS"}
TAIWAN = {"2330": "TSMC", "2317": "Hon Hai (Foxconn)", "2454": "MediaTek", "2308": "Delta Electronics",
          "2382": "Quanta Computer", "2881": "Fubon Financial", "2882": "Cathay Financial", "2412": "Chunghwa Telecom",
          "2891": "CTBC Financial", "3711": "ASE Technology", "2303": "UMC", "2886": "Mega Financial",
          "1216": "Uni-President", "2884": "E.Sun Financial", "2357": "Asustek", "3231": "Wistron", "2345": "Accton",
          "3008": "Largan", "2002": "China Steel", "1303": "Nan Ya Plastics", "1301": "Formosa Plastics",
          "2885": "Yuanta Financial", "2892": "First Financial", "6669": "Wiwynn", "3034": "Novatek",
          "2379": "Realtek", "2603": "Evergreen Marine", "2912": "President Chain Store", "3045": "Taiwan Mobile",
          "2395": "Advantech"}
ENERGIA = {"SLB": "SLB (Schlumberger)", "MPC": "Marathon Petroleum", "PSX": "Phillips 66", "VLO": "Valero Energy",
           "WMB": "Williams (gas)", "KMI": "Kinder Morgan (gas)", "OKE": "ONEOK (gas)", "ET": "Energy Transfer",
           "EPD": "Enterprise Products", "LNG": "Cheniere Energy (gas natural licuado)", "HAL": "Halliburton",
           "TRGP": "Targa Resources (gas)", "CTRA": "Coterra Energy", "EQT": "EQT (gas)", "EXE": "Expand Energy (gas)",
           "APA": "APA", "OVV": "Ovintiv", "AR": "Antero Resources (gas)", "RRC": "Range Resources (gas)",
           "MPLX": "MPLX", "PAA": "Plains All American", "ENB": "Enbridge", "TRP": "TC Energy (gas)",
           "CQP": "Cheniere Energy Partners", "WES": "Western Midstream", "PBA": "Pembina Pipeline", "TPL": "Texas Pacific Land",
           "PR": "Permian Resources", "MTDR": "Matador Resources", "FTI": "TechnipFMC", "NOV": "NOV", "TS": "Tenaris",
           "VIST": "Vista Energy", "CNX": "CNX Resources (gas)", "HES": "Hess", "CHRD": "Chord Energy",
           "SM": "SM Energy", "KOS": "Kosmos Energy", "DTM": "DT Midstream (gas)", "AM": "Antero Midstream"}
MINERAS = {"WPM": "Wheaton Precious Metals", "FNV": "Franco-Nevada", "RGLD": "Royal Gold", "PAAS": "Pan American Silver",
           "AG": "First Majestic Silver", "HL": "Hecla Mining (plata)", "SSRM": "SSR Mining", "FCX": "Freeport-McMoRan (cobre)",
           "SCCO": "Southern Copper", "TECK": "Teck Resources (cobre)", "BHP": "BHP", "RIO": "Rio Tinto", "VALE": "Vale",
           "HBM": "Hudbay Minerals (cobre)", "ERO": "Ero Copper", "OR": "OR Royalties", "BTG": "B2Gold",
           "NGD": "New Gold", "IAG": "Iamgold", "SBSW": "Sibanye Stillwater", "EXK": "Endeavour Silver",
           "FSM": "Fortuna Mining", "TFPM": "Triple Flag Precious Metals", "OGC.TO": "OceanaGold"}
MATERIAS = {  # símbolo: (nombre, grupo de noticias)
    "RB=F": ("Gasolina RBOB (futuro)", "petróleo"), "HO=F": ("Diésel / heating oil (futuro)", "petróleo"),
    "PL=F": ("Platino (futuro)", "oro"), "PA=F": ("Paladio (futuro)", "oro"), "ALI=F": ("Aluminio (futuro)", "oro"),
    "CC=F": ("Cacao (futuro)", "agro"), "SB=F": ("Azúcar (futuro)", "agro"), "ZC=F": ("Maíz (futuro)", "agro"),
    "ZW=F": ("Trigo (futuro)", "agro"), "ZS=F": ("Soya (futuro)", "agro"), "CT=F": ("Algodón (futuro)", "agro"),
    "ZL=F": ("Aceite de soya (futuro)", "agro"), "ZM=F": ("Harina de soya (futuro)", "agro"),
    "ZO=F": ("Avena (futuro)", "agro"), "ZR=F": ("Arroz (futuro)", "agro"), "OJ=F": ("Jugo de naranja (futuro)", "agro"),
    "LE=F": ("Ganado vivo (futuro)", "agro"), "GF=F": ("Ganado de engorde (futuro)", "agro"),
    "HE=F": ("Cerdo magro (futuro)", "agro")}
CRIPTO = {"AVAX-USD": "Avalanche", "XLM-USD": "Stellar", "SUI20947-USD": "Sui", "HBAR-USD": "Hedera",
          "BCH-USD": "Bitcoin Cash", "LTC-USD": "Litecoin", "DOT-USD": "Polkadot", "TON11419-USD": "Toncoin",
          "SHIB-USD": "Shiba Inu", "UNI7083-USD": "Uniswap", "XMR-USD": "Monero", "LEO-USD": "UNUS SED LEO",
          "PEPE24478-USD": "Pepe", "NEAR-USD": "NEAR Protocol", "APT21794-USD": "Aptos", "ICP-USD": "Internet Computer",
          "ETC-USD": "Ethereum Classic", "AAVE-USD": "Aave", "POL28321-USD": "Polygon (POL)", "CRO-USD": "Cronos",
          "VET-USD": "VeChain", "RENDER-USD": "Render", "ATOM-USD": "Cosmos", "FIL-USD": "Filecoin",
          "ALGO-USD": "Algorand", "ARB11841-USD": "Arbitrum", "OP-USD": "Optimism", "INJ-USD": "Injective",
          "IMX10603-USD": "Immutable", "STX4847-USD": "Stacks", "GRT6719-USD": "The Graph", "TAO22974-USD": "Bittensor",
          "HYPE32196-USD": "Hyperliquid", "ENA-USD": "Ethena", "WLD-USD": "Worldcoin", "ONDO-USD": "Ondo",
          "KAS-USD": "Kaspa", "FET-USD": "Artificial Superintelligence (FET)", "BONK-USD": "Bonk", "SEI-USD": "Sei",
          "TIA22861-USD": "Celestia", "JUP29210-USD": "Jupiter", "XTZ-USD": "Tezos", "SAND-USD": "The Sandbox"}
# Sin monedas estables (USDT, USDC...): valen siempre 1 dólar, no tiene sentido analizarlas.
BONOS = {"^IRX": ("Tasa del Tesoro de EE.UU. a 3 meses", "bono"), "^FVX": ("Tasa del Tesoro a 5 años", "bono"),
         "^TNX": ("Tasa del Tesoro a 10 años", "bono"), "^TYX": ("Tasa del Tesoro a 30 años", "bono"),
         "BNDX": ("ETF bonos internacionales fuera de EE.UU. (BNDX)", "etf"),
         "TLT": ("ETF bonos del Tesoro de 20+ años (TLT)", "etf"), "IEF": ("ETF bonos del Tesoro de 7-10 años (IEF)", "etf"),
         "SHY": ("ETF bonos del Tesoro de 1-3 años (SHY)", "etf"), "AGG": ("ETF bonos de EE.UU. en general (AGG)", "etf"),
         "BND": ("ETF bonos de EE.UU. en general (BND)", "etf"),
         "LQD": ("ETF bonos de empresas grandes (LQD)", "etf"), "HYG": ("ETF bonos de alto rendimiento (HYG)", "etf"),
         "TIP": ("ETF bonos protegidos contra la inflación (TIP)", "etf"),
         "EMB": ("ETF bonos de países emergentes, incluye Colombia (EMB)", "etf"),
         "ICOLTES.CL": ("ETF de TES de Colombia (si existe en Yahoo)", "etf")}
ETF_DIVIDENDOS = {"DVY": "Fondo de dividendos DVY", "HDV": "Fondo de dividendos HDV", "SDY": "Fondo de dividendos SDY",
                  "NOBL": "Fondo aristócratas del dividendo NOBL"}

# Latinoamérica sin Colombia (Colombia tiene su propia pestaña): símbolo -> (nombre, tipo, país)
LATAM = {
    "^BVSP": ("Índice Bovespa (Brasil)", "índice", "Brasil"), "EWZ": ("ETF de Brasil (EWZ)", "etf", "Brasil"),
    "ITUB": ("Itaú Unibanco (ADR)", "acción", "Brasil"), "BBD": ("Banco Bradesco (ADR)", "acción", "Brasil"),
    "NU": ("Nu Holdings (Nubank)", "acción", "Brasil"), "ABEV": ("Ambev (ADR)", "acción", "Brasil"),
    "EMBJ": ("Embraer (ADR)", "acción", "Brasil"), "SBS": ("Sabesp (ADR)", "acción", "Brasil"),
    "GGB": ("Gerdau (ADR)", "acción", "Brasil"), "SUZ": ("Suzano (ADR)", "acción", "Brasil"),
    "XP": ("XP Inc.", "acción", "Brasil"), "STNE": ("StoneCo", "acción", "Brasil"), "BSBR": ("Santander Brasil (ADR)", "acción", "Brasil"),
    "PETR4.SA": ("Petrobras (Bolsa de São Paulo)", "acción", "Brasil"), "VALE3.SA": ("Vale (Bolsa de São Paulo)", "acción", "Brasil"),
    "ITUB4.SA": ("Itaú Unibanco (Bolsa de São Paulo)", "acción", "Brasil"), "WEGE3.SA": ("WEG (Bolsa de São Paulo)", "acción", "Brasil"),
    "B3SA3.SA": ("B3, bolsa de Brasil (São Paulo)", "acción", "Brasil"), "BBAS3.SA": ("Banco do Brasil (São Paulo)", "acción", "Brasil"),
    "^MXX": ("Índice IPC (México)", "índice", "México"), "EWW": ("ETF de México (EWW)", "etf", "México"),
    "AMX": ("América Móvil (ADR)", "acción", "México"), "FMX": ("FEMSA (ADR)", "acción", "México"),
    "CX": ("Cemex (ADR)", "acción", "México"), "KOF": ("Coca-Cola FEMSA (ADR)", "acción", "México"),
    "ASR": ("Grupo Aeroportuario del Sureste (ADR)", "acción", "México"), "PAC": ("Grupo Aeroportuario del Pacífico (ADR)", "acción", "México"),
    "WALMEX.MX": ("Walmart de México (Bolsa de México)", "acción", "México"),
    "GFNORTEO.MX": ("Banorte (Bolsa de México)", "acción", "México"), "GMEXICOB.MX": ("Grupo México (Bolsa de México)", "acción", "México"),
    "^IPSA": ("Índice S&P IPSA (Chile)", "índice", "Chile"), "ECH": ("ETF de Chile (ECH)", "etf", "Chile"),
    "SQM": ("SQM, litio (ADR)", "acción", "Chile"), "BCH": ("Banco de Chile (ADR)", "acción", "Chile"),
    "BSAC": ("Banco Santander Chile (ADR)", "acción", "Chile"), "LTM": ("LATAM Airlines (ADR)", "acción", "Chile"),
    "CCU": ("CCU, bebidas (ADR)", "acción", "Chile"), "FALABELLA.SN": ("Falabella (Bolsa de Santiago)", "acción", "Chile"),
    "COPEC.SN": ("Empresas Copec (Bolsa de Santiago)", "acción", "Chile"),
    "^SPBLPGPT": ("Índice S&P/BVL General (Perú)", "índice", "Perú"), "EPU": ("ETF de Perú (EPU)", "etf", "Perú"),
    "BAP": ("Credicorp (Perú)", "acción", "Perú"), "BVN": ("Buenaventura, minera (Perú)", "acción", "Perú"),
    "IFS": ("Intercorp Financial (Perú)", "acción", "Perú"),
    "^MERV": ("Índice Merval (Argentina)", "índice", "Argentina"), "ARGT": ("ETF de Argentina (ARGT)", "etf", "Argentina"),
    "GGAL": ("Grupo Financiero Galicia (ADR)", "acción", "Argentina"), "BMA": ("Banco Macro (ADR)", "acción", "Argentina"),
    "PAM": ("Pampa Energía (ADR)", "acción", "Argentina"), "TEO": ("Telecom Argentina (ADR)", "acción", "Argentina"),
    "CEPU": ("Central Puerto (ADR)", "acción", "Argentina"), "TGS": ("Transportadora de Gas del Sur (ADR)", "acción", "Argentina"),
    "BBAR": ("BBVA Argentina (ADR)", "acción", "Argentina"), "SUPV": ("Grupo Supervielle (ADR)", "acción", "Argentina"),
    "LOMA": ("Loma Negra, cemento (ADR)", "acción", "Argentina"), "GLOB": ("Globant", "acción", "Argentina"),
}
# Divisas: el precio es cuántas unidades de la segunda moneda vale una de la primera
DIVISAS = {"COP=X": "Dólar / peso colombiano (USD/COP)", "EURUSD=X": "Euro / dólar (EUR/USD)",
           "MXN=X": "Dólar / peso mexicano (USD/MXN)", "BRL=X": "Dólar / real brasileño (USD/BRL)",
           "JPY=X": "Dólar / yen japonés (USD/JPY)", "GBPUSD=X": "Libra / dólar (GBP/USD)",
           "CLP=X": "Dólar / peso chileno (USD/CLP)", "PEN=X": "Dólar / sol peruano (USD/PEN)",
           "ARS=X": "Dólar / peso argentino (USD/ARS)", "CNY=X": "Dólar / yuan chino (USD/CNY)",
           "CAD=X": "Dólar / dólar canadiense (USD/CAD)", "CHF=X": "Dólar / franco suizo (USD/CHF)",
           "AUDUSD=X": "Dólar australiano / dólar (AUD/USD)", "EURCOP=X": "Euro / peso colombiano (EUR/COP)"}
# ETFs que copian a cada índice (para comprar "el índice" a través de su ETF): símbolo -> (nombre, mercado)
ETF_INDICES = {"VOO": ("Fondo S&P 500 VOO (Vanguard)", "eeuu"), "DIA": ("Fondo Dow Jones DIA", "eeuu"),
               "IWM": ("Fondo Russell 2000 IWM", "eeuu"), "ONEQ": ("Fondo Nasdaq Composite ONEQ", "eeuu"),
               "FEZ": ("ETF Euro Stoxx 50 (FEZ)", "europa"), "EWU": ("ETF del Reino Unido (EWU)", "europa"),
               "EWG": ("ETF de Alemania (EWG)", "europa"), "EWQ": ("ETF de Francia (EWQ)", "europa"),
               "EWH": ("ETF de Hong Kong (EWH)", "asia"), "EWT": ("ETF de Taiwán (EWT)", "asia"),
               "MCHI": ("ETF de China (MCHI)", "asia")}


def tabla(pagina, columna):
    html = requests.get(WIKI + pagina, headers=CABECERA, timeout=30).text
    return next(t for t in pd.read_html(io.StringIO(html)) if columna in t.columns and len(t) >= 20)


def candidatos():
    """{símbolo: {nombre, tipo, mercados, noticias, sector}} antes de verificar."""
    c = {}
    agregar = lambda s, n, tipo, mercado, grupo, sector=None: c.setdefault(s, {
        "nombre": n, "tipo": tipo, "mercados": [], "noticias": [grupo], "sector": sector})["mercados"].append(mercado)
    sp = tabla("List_of_S%26P_500_companies", "Symbol")
    for _, f in sp.iterrows():
        agregar(f["Symbol"].replace(".", "-"), f["Security"], "acción", "eeuu", "nasdaq", GICS.get(f["GICS Sector"]))
    for _, f in tabla("EURO_STOXX_50", "Ticker").iterrows():
        agregar(f["Ticker"], f["Name"], "acción", "europa", "europa", GICS.get(f["Sector"]))
    for _, f in tabla("FTSE_100_Index", "Ticker").iterrows():
        agregar(f["Ticker"].replace(".", "-").rstrip("-") + ".L", f"{f['Company']} (Londres)", "acción", "europa", "europa")
    for _, f in tabla("DAX", "Ticker").iterrows():
        agregar(f["Ticker"], f["Company"], "acción", "europa", "europa")
    hsi = tabla("Hang_Seng_Index", "Ticker")
    for _, f in hsi.iterrows():
        numero = "".join(ch for ch in str(f["Ticker"]) if ch.isdigit())
        agregar(f"{int(numero):04d}.HK", f"{f['Name']} (Hong Kong)", "acción", "asia", "asia")
    for _, f in tabla("NIFTY_50", "Symbol").dropna(subset=["Symbol"]).iterrows():
        agregar(f"{f['Symbol']}.NS", f"{f['Company name']} (India)", "acción", "asia", "asia")
    for codigo, n in JAPON.items():
        agregar(f"{codigo}.T", f"{n} (Tokio)", "acción", "asia", "asia")
    for codigo, n in COREA.items():
        agregar(f"{codigo}.KS", f"{n} (Corea)", "acción", "asia", "asia")
    for codigo, n in TAIWAN.items():
        agregar(f"{codigo}.TW", f"{n} (Taiwán)", "acción", "asia", "asia")
    for s, n in ENERGIA.items():
        agregar(s, n, "acción", "petróleo", "petróleo", "Petróleo y gas")
    for s, n in MINERAS.items():
        agregar(s, n, "acción", "oro", "oro", "Materiales y minería")
    for s, (n, grupo) in MATERIAS.items():
        agregar(s, n, "futuro", "materias", grupo)
        c[s]["mercados"].append("futuros")
    for s, n in CRIPTO.items():
        agregar(s, n, "cripto", "cripto", "cripto")
    for s, (n, tipo) in BONOS.items():
        agregar(s, n, tipo, "bonos", "bonos")
        if tipo == "etf":
            c[s]["mercados"].append("etf")
    for s, n in ETF_DIVIDENDOS.items():
        agregar(s, n, "etf", "dividendos", "nasdaq")
        c[s]["mercados"].append("etf")
    for s, (n, tipo, pais) in LATAM.items():
        agregar(s, n, tipo, "latam", "latam")
        c[s]["pais"] = pais
        if tipo == "etf":
            c[s]["mercados"].append("etf")
    for s, n in DIVISAS.items():
        agregar(s, n, "divisa", "divisas", "divisas", "Divisas")
    agregar("DX-Y.NYB", "Índice del dólar DXY (contra 6 monedas)", "índice", "divisas", "divisas")
    c["DX-Y.NYB"]["mercados"].append("eeuu")
    for s, (n, mercado) in ETF_INDICES.items():
        agregar(s, n, "etf", "etf", "nasdaq" if mercado == "eeuu" else mercado)
        c[s]["mercados"].append(mercado)
    for _, f in tabla("S%26P_500_Dividend_Aristocrats", "Ticker symbol").iterrows():
        s = f["Ticker symbol"].replace(".", "-")
        agregar(s, f["Company"], "acción", "dividendos", "nasdaq", GICS.get(f["Sector"]))
    return c


def verificar(simbolos, tanda=80):
    """Los que tienen al menos 30 cierres en 3 meses (la app los necesita) y el último hace menos de 10 días."""
    buenos = set()
    limite = pd.Timestamp.now().normalize() - pd.Timedelta(days=10)
    for i in range(0, len(simbolos), tanda):
        grupo = simbolos[i:i + tanda]
        datos = yf.download(grupo, period="3mo", progress=False, group_by="ticker", auto_adjust=False, threads=True)
        for s in grupo:
            try:
                cierre = (datos[s] if len(grupo) > 1 else datos)["Close"].dropna()
                if len(cierre) >= 30 and cierre.index[-1] >= limite:
                    buenos.add(s)
            except Exception:
                pass
    return buenos


def mas_grandes(simbolos, n):
    """Los n de mayor capitalización (para quedarnos con las 30-50 más grandes de cada bolsa)."""
    def tamano(s):
        try:
            return yf.Ticker(s).fast_info["market_cap"] or 0
        except Exception:
            return 0
    with ThreadPoolExecutor(8) as pool:
        tamanos = dict(zip(simbolos, pool.map(tamano, simbolos)))
    return set(sorted(simbolos, key=tamanos.get, reverse=True)[:n])


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    c = candidatos()
    print(f"{len(c)} candidatos. Verificando en Yahoo Finance...")
    buenos = verificar(list(c))
    hk = [s for s in c if s.endswith(".HK") and s in buenos]
    buenos -= set(hk) - mas_grandes(hk, 40)           # Hang Seng: solo las 40 más grandes
    energia = [s for s in ENERGIA if s in buenos]
    for s in set(energia) - mas_grandes(energia, 30):  # Con las 20 de antes quedan 50 de petróleo y gas
        if "eeuu" in c[s]["mercados"]:                 # Si está en el S&P 500 se queda, pero sin la etiqueta de petróleo
            c[s]["mercados"].remove("petróleo")
        else:
            buenos.discard(s)
    descartados = sorted(set(c) - buenos)
    catalogo = {s: d for s, d in c.items() if s in buenos}
    ARCHIVO.write_text(json.dumps({"activos": catalogo, "descartados": descartados}, ensure_ascii=False, indent=0),
                       encoding="utf-8")
    print(f"Guardados {len(catalogo)}. Descartados (sin datos o fuera del top): {len(descartados)}")
    print(", ".join(descartados))


if __name__ == "__main__":
    main()
