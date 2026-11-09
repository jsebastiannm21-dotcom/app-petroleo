# calendario.py - Próximos eventos que mueven los activos (hora de Bogotá)
#  - calendario_eventos.csv: fechas confirmadas (OPEP+, Fed, CPI, empleo, resultados...). Agrega ahí las nuevas.
#  - Automáticos (se agregan solos hacia el futuro, marcados "estimada" si no están confirmados):
#      inventarios EIA cada miércoles 10:30 a.m. Nueva York (jueves si hay feriado),
#      empleo de EE.UU. el primer viernes del mes 8:30 a.m. NY, inflación (CPI) a mediados de mes 8:30 a.m. NY,
#      reunión mensual de la OPEP+ el primer domingo del mes, festivos de Colombia y días con Wall Street cerrado.

from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import holidays
import pandas as pd

CARPETA = Path(__file__).resolve().parent
ARCHIVO_EVENTOS = CARPETA / "calendario_eventos.csv"
NUEVA_YORK = ZoneInfo("America/New_York")
COLOMBIA = ZoneInfo("America/Bogota")
TODOS = "nasdaq;oro;petróleo;ecopetrol"
COLUMNAS = ["Fecha", "Hora Colombia", "Momento", "Tipo", "Grupo", "Evento"]


def hoy_colombia():
    return datetime.now(COLOMBIA).date()


def _nyse(anios):
    return holidays.financial_holidays("NYSE", years=anios)


def _colombia(anios):
    return holidays.Colombia(years=anios)


def mercado_cerrado(dia, simbolo=""):
    """True si ese día no hay mercado: fin de semana o festivo de la bolsa del activo. Cripto nunca cierra."""
    import activos
    if activos.es_cripto(simbolo):
        return False
    return dia.weekday() >= 5 or dia in activos.festivos_de(simbolo, [dia.year])


def _fila(dia, hora_ny, tipo, grupo, evento, zona=NUEVA_YORK):
    momento = None
    if hora_ny:
        h, m = (int(x) for x in str(hora_ny).split(":"))
        momento = datetime.combine(dia, time(h, m), zona).astimezone(COLOMBIA).replace(tzinfo=None)
    return {"Fecha": dia, "Hora Colombia": momento.strftime("%I:%M %p") if momento else "todo el día",
            "Momento": momento, "Tipo": tipo, "Grupo": grupo, "Evento": evento}


def reportes_eia(desde, hasta):
    feriados = holidays.US(years=range(desde.year, hasta.year + 1))   # La EIA es del gobierno: sigue sus feriados
    filas = []
    for miercoles in pd.date_range(desde - timedelta(days=1), hasta, freq="W-WED"):
        miercoles = miercoles.date()
        se_corre = any(miercoles - timedelta(days=k) in feriados for k in range(3))
        dia = miercoles + timedelta(days=1) if se_corre else miercoles
        if desde <= dia <= hasta:
            filas.append(_fila(dia, "10:30", "Inventarios EIA", "petróleo;ecopetrol",
                               "Reporte semanal de inventarios de petróleo de EE.UU."
                               + (" (se corre al jueves por feriado)" if se_corre else "")))
    return filas


def eventos_programados(desde, hasta):
    if not ARCHIVO_EVENTOS.exists():
        return []
    tabla = pd.read_csv(ARCHIVO_EVENTOS, parse_dates=["Fecha"], dtype={"Hora_NY": str})
    return [_fila(f.Fecha.date(), f.Hora_NY if isinstance(f.Hora_NY, str) else None, f.Tipo, f.Grupo, f.Evento)
            for f in tabla.itertuples() if desde <= f.Fecha.date() <= hasta]


def _primer(dia_semana, anio, mes, n=1):
    """El n-ésimo día de la semana (0 = lunes) de un mes."""
    d = date(anio, mes, 1)
    d += timedelta(days=(dia_semana - d.weekday()) % 7)
    return d + timedelta(weeks=n - 1)


def automaticos(desde, hasta, ya):
    """Eventos que se repiten. 'ya' = {(tipo, año, mes)} que ya están confirmados en el CSV."""
    filas = []
    meses = pd.period_range(desde, hasta, freq="M")
    for p in meses:
        empleo = _primer(4, p.year, p.month)                       # Primer viernes (si es festivo, el siguiente)
        if empleo in _nyse([p.year]):
            empleo += timedelta(weeks=1)
        cpi = _primer(2, p.year, p.month, 2)                       # shortcut: CPI estimado el 2.º miércoles; BLS publica entre el 10 y el 15
        opep = _primer(6, p.year, p.month)                         # Primer domingo
        habil = lambda d: d if d.weekday() < 5 else d + timedelta(days=7 - d.weekday())
        ultimo_habil = (pd.Timestamp(p.end_time.date()) - pd.offsets.BDay(0)).date()
        if ultimo_habil.weekday() >= 5:
            ultimo_habil = (pd.Timestamp(p.end_time.date()) - pd.offsets.BDay(1)).date()
        fin_mes_viernes = p.end_time.date() - timedelta(days=(p.end_time.date().weekday() - 4) % 7)
        eventos_mes = [
            (empleo, "Empleo", "08:30", "nasdaq;oro;cripto", "Informe de empleo de EE.UU. (fecha estimada, confirmar en bls.gov)"),
            (cpi, "Inflación", "08:30", "nasdaq;oro;cripto", "Inflación de EE.UU. (CPI) (fecha estimada, confirmar en bls.gov)"),
            (opep, "OPEP+", None, "petróleo;ecopetrol", "Reunión mensual de la OPEP+ (fecha estimada, confirmar en opec.org)"),
            (habil(date(p.year, p.month, 8)), "Inflación Colombia", None, "ecopetrol",
             "Inflación de Colombia (DANE) (fecha estimada, confirmar en dane.gov.co)"),
            (habil(date(p.year, p.month, 10)), "Datos de China", None, "asia",
             "Inflación de China (fecha estimada); los datos de actividad salen hacia el día 15"),
            (fin_mes_viernes, "Vencimiento cripto", "08:00", "cripto",
             "Vencimiento mensual de opciones de Bitcoin y Ethereum (Deribit): suele mover el precio"),
        ]
        if p.month in (1, 3, 4, 6, 7, 9, 10, 12):                   # Meses con decisión del Banco de la República
            eventos_mes.append((ultimo_habil, "Banco de la República", None, "ecopetrol",
                                "Decisión de tasas del Banco de la República (fecha estimada, confirmar en banrep.gov.co)"))
        for dia, tipo, hora, grupo, texto in eventos_mes:
            if desde <= dia <= hasta and (tipo, p.year, p.month) not in ya:
                zona = ZoneInfo("UTC") if tipo == "Vencimiento cripto" else NUEVA_YORK
                filas.append(_fila(dia, hora, tipo, grupo, texto, zona))
    anios = range(desde.year, hasta.year + 1)
    for dia, nombre in _colombia(anios).items():
        if desde <= dia <= hasta and dia.weekday() < 5:
            filas.append(_fila(dia, None, "Festivo Colombia", "ecopetrol",
                               f"Festivo en Colombia ({nombre}): la Bolsa de Colombia cierra" +
                               ("" if dia in _nyse(anios) else "; EE.UU. sí opera")))
    for dia, nombre in _nyse(anios).items():
        if desde <= dia <= hasta:
            filas.append(_fila(dia, None, "Mercado cerrado", TODOS, f"Wall Street cerrado ({nombre})"))
            if "Thanksgiving" in nombre and desde <= dia + timedelta(days=1) <= hasta:
                filas.append(_fila(dia + timedelta(days=1), "13:00", "Medio día", TODOS,
                                   "Wall Street opera solo medio día (cierra 1:00 p.m. Nueva York)"))
    return filas


def proximos_eventos(dias=60, desde=None, grupo=None, grupos=None):
    """Eventos desde hoy (o 'desde') hasta dentro de 'dias' días.
    Con 'grupo' o 'grupos' (por ejemplo ["oro"]), solo los que afectan a esos mercados."""
    desde = desde or hoy_colombia()
    hasta = desde + timedelta(days=dias)
    confirmados = eventos_programados(desde, hasta)
    ya = {(f["Tipo"].replace("OPEP+", "OPEP+"), f["Fecha"].year, f["Fecha"].month) for f in confirmados}
    filas = confirmados + reportes_eia(desde, hasta) + automaticos(desde, hasta, ya)
    tabla = pd.DataFrame(filas, columns=COLUMNAS)
    buscados = set(grupos or ([grupo] if grupo else []))
    if buscados:
        tabla = tabla[tabla["Grupo"].str.split(";").apply(lambda g: bool(buscados & set(g)))]
    return tabla.sort_values(["Fecha", "Momento"], na_position="first").reset_index(drop=True)


if __name__ == "__main__":
    assert mercado_cerrado(date(2026, 11, 26)) and mercado_cerrado(date(2026, 11, 7))     # Acción de Gracias, sábado
    assert not mercado_cerrado(date(2026, 11, 16)) and mercado_cerrado(date(2026, 11, 16), "ECOPETROL.CL")
    print(proximos_eventos(70).drop(columns="Momento").to_string(index=False))
