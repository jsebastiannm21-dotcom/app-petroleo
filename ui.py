# ui.py - Piezas que comparten todas las pantallas de la app (carga de datos, gráficas, cuadros)

import json
from datetime import date, timedelta

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import activos
import calendario
import estrategia
import ranking

LEYENDA_TABLA = ("Leyenda: la columna **Sector** dice a qué se dedica cada activo (💻 Tecnología · 🛢️ Petróleo y gas · "
                 "🥇/⛏️ Oro y minería · 🏦 Bancos · ⚡ Energía eléctrica · 🛒🛍️ Consumo · 💊 Salud · 🏭 Industria · "
                 "🪙 Cripto · 📜 Futuros · 🧺 ETF · 📊 Índice). **La casilla de la izquierda** de cada fila sirve para "
                 "**abrir la página del activo**: tócala.")
AYUDA_SECTOR = "A qué se dedica: 💻 Tecnología, 🛢️ Petróleo y gas, ⛏️ Minería, 🏦 Bancos y finanzas, ⚡ Energía eléctrica, " \
               "🛒 Consumo básico, 🛍️ Consumo, 💊 Salud, 🏭 Industria, 🪙 Cripto, 📜 Futuros, 🧺 ETF (canasta), 📊 Índice."


@st.cache_data(ttl=3600, show_spinner=False)
def tasa_usd(moneda):
    return activos.tasa_usd(moneda)


@st.cache_resource
def salud():
    """Tiempos de carga y errores recientes de la app (memoria del servidor; se ven en el Panel admin)."""
    from collections import deque
    return {"tiempos": deque(maxlen=500), "errores": deque(maxlen=50), "avisados": {}}


def contar_uso(que):
    """Cuenta (una vez por sesión y día) que alguien usó una función, para las cifras del Panel admin."""
    import nube
    clave = f"uso_{que}_{date.today()}"
    if nube.conectado() and not st.session_state.get(clave):
        st.session_state[clave] = True
        __import__("gestion").uso(que)


@st.cache_data(ttl=1800, show_spinner=False)
def comunidad():
    """(porcentajes por mercado, compras, ¿se usa como señal?, texto del backtest). Anónimo y agregado."""
    import gestion
    pct, n = gestion.comunidad()
    usar, texto = gestion.comunidad_validada()
    return pct, n, usar, texto


def tarjeta_comunidad():
    import nube
    if not nube.conectado():
        return
    pct, n, usar, texto = comunidad()
    with st.container(border=True):
        st.markdown("#### :material/groups: Sentimiento de la comunidad (anónimo)")
        if not n:
            st.caption("Esta semana todavía no hay compras en la comunidad.")
            return
        top = ", ".join(f"**{v:.0f}%** {activos.NOMBRE_MERCADO.get(m, m)}" for m, v in pct.head(3).items())
        st.markdown(f"De las {n} compras de esta semana: {top}.")
        st.caption(texto)


def yo():
    import nube
    return st.session_state.get("yo") or {"email": nube.superadmin(), "nombre": "Superadmin", "rol": "superadmin"}


def puede(que):
    """mis_activos, admin, actualizar o automatico, según el rol del usuario de esta sesión."""
    import usuarios
    return usuarios.puede(yo(), que)


def filtro_mercados(clave):
    """Filtro por mercado. Vacío = todos. Devuelve el conjunto de mercados elegidos (claves internas)."""
    nombres = {v: k for k, v in activos.NOMBRE_MERCADO.items() if k != "dividendos" and activos.mercado_activo(k)}
    elegidos = st.pills("Filtrar por mercado (vacío = todos)", list(nombres), selection_mode="multi", key=clave)
    return {nombres[e] for e in elegidos}


def consejo_tendencia(simbolo, nombre_mercado):
    """'Este mercado está AL ALZA / A LA BAJA / LATERAL' con la razón en una frase."""
    try:
        d = analisis(simbolo)["datos"]
    except Exception:
        return
    hoy = d.iloc[-1]
    mes = (hoy["Cierre"] / d["Cierre"].iloc[-22] - 1) * 100 if len(d) > 22 else 0.0
    sobre50, sobre200, cruz = hoy["Cierre"] > hoy["MM50"], hoy["Cierre"] > hoy["MM200"], hoy["MM50"] > hoy["MM200"]
    if sobre50 and cruz and mes > 0:
        texto, tipo = "AL ALZA", st.success
        razon = f"el precio está por encima de sus medias de 50 y 200 días y subió {mes:+.1f}% en el último mes"
    elif not sobre50 and not cruz and mes < 0:
        texto, tipo = "A LA BAJA", st.error
        razon = f"el precio está por debajo de sus medias de 50 y 200 días y cambió {mes:+.1f}% en el último mes"
    else:
        texto, tipo = "LATERAL", st.info
        razon = (f"las señales están mezcladas: el precio está {'por encima' if sobre50 else 'por debajo'} de la media "
                 f"de 50 días, {'por encima' if sobre200 else 'por debajo'} de la de 200, y cambió {mes:+.1f}% en el mes")
    tipo(f"Según {activos.nombre(simbolo)}: {razon}.", title=f"Este mercado está {texto}", icon=":material/trending_flat:"
         if texto == "LATERAL" else ":material/trending_up:" if texto == "AL ALZA" else ":material/trending_down:")


def estacionalidad_de(simbolo, dias_semana=False):
    """Retorno promedio por mes (y por día de la semana) y % de años en que subió, en los últimos 10 años."""
    import estacional
    try:
        c = estacional.cierres_10_anios(simbolo)
        meses = estacional.por_mes(c, 10)
    except Exception:
        st.caption("No hay datos suficientes para la estacionalidad.")
        return
    st.markdown(f"**Estacionalidad de {activos.nombre(simbolo)}** (últimos {int(meses['Años'].max())} años)")
    frase = estacional.frase_mes_actual(meses, activos.nombre(simbolo))
    if frase:
        st.caption(f":material/calendar_month: {frase}")
    mes_actual = pd.Timestamp.now().month
    fig = go.Figure(go.Bar(
        x=meses["Mes"], y=meses["Retorno_promedio_%"],
        marker_color=[VERDE if v >= 0 else ROJO for v in meses["Retorno_promedio_%"]],
        marker_line=dict(color=["#FFFFFF" if m == mes_actual else "rgba(0,0,0,0)" for m in meses.index], width=3),
        text=[f"{v:+.1f}%<br>{p:.0f}%↑" for v, p in zip(meses["Retorno_promedio_%"], meses["Subio_%"])],
        textposition="outside", hovertemplate="%{x}: %{y:+.2f}%<extra></extra>"))
    fig.update_yaxes(ticksuffix="%", title_text="Retorno promedio del mes")
    izq, der = st.columns([2, 1]) if dias_semana else (st.container(), None)
    izq.plotly_chart(estilo(fig, 280, leyenda=False), width="stretch", key=f"estac_{simbolo}")
    if der is not None:
        dias = estacional.por_dia(c, 10)
        fig = go.Figure(go.Bar(x=[d[:3] for d in dias["Dia"]], y=dias["Retorno_promedio_%"],
                               marker_color=[VERDE if v >= 0 else ROJO for v in dias["Retorno_promedio_%"]],
                               text=[f"{v:+.2f}%" for v in dias["Retorno_promedio_%"]], textposition="outside"))
        fig.update_yaxes(ticksuffix="%", title_text="Promedio por día")
        der.plotly_chart(estilo(fig, 280, leyenda=False), width="stretch", key=f"estac_dia_{simbolo}")
    st.caption("Debajo de cada barra: % de años en que ese mes subió. Borde blanco = mes en curso.")


AYUDA_TAMANO = ("Tamaño = capitalización de mercado: el valor de TODAS las acciones de la empresa juntas (precio de una "
                "acción × número de acciones). Gigante: más de US$ 200 mil millones · Grande: más de 10 mil millones · "
                "Mediana: más de 2 mil millones · Pequeña: menos. En los ETF es el dinero que administra el fondo.")
CRISIS = {"2000": "la caída de las puntocom", "2001": "los atentados del 11 de septiembre", "2008": "la crisis financiera",
          "2009": "la crisis financiera", "2011": "la crisis del euro", "2014": "la caída del petróleo",
          "2015": "la caída del petróleo", "2016": "la caída del petróleo", "2018": "la caída de fin de año",
          "2020": "la pandemia", "2022": "la subida de tasas e inflación", "2025": "los aranceles"}


def _dividendos_ficha(simbolo, d):
    """Texto de dividendos. En índices: el índice no paga, pero sus ETFs sí."""
    import dividendos
    t = dividendos.leer()
    rend = lambda s: (t.set_index("Activo")["Rendimiento_%"].get(s) if len(t) else None)
    if activos.tipo(simbolo) in ("índice", "bono"):
        etfs = activos.INDICE_ETF.get(simbolo)
        if not etfs:
            return "No (es una medida del mercado)"
        r = next((rend(e) for e in etfs if rend(e)), None)
        return (f"El índice no paga, pero sus ETFs ({', '.join(etfs)}) sí" + (f", ~{r:.1f}% al año" if r else ""))
    if activos.tipo(simbolo) in ("cripto", "divisa", "futuro"):
        return "No"
    div = rend(simbolo) or d.get("dividendYield")
    return f"Sí, {div:.2f}% al año" if div else "No"


@st.dialog("Gráfica de ese año", width="large")
def grafica_anio(simbolo, anio):
    """Precio del activo durante un año de crisis (se descarga solo ese año, porque los datos guardados son de 5 años)."""
    st.markdown(f"### {activos.nombre(simbolo)} en {anio}: {CRISIS.get(anio, '')}")
    datos = _anio(simbolo, int(anio))
    if datos.empty:
        st.caption(f"No hay datos de {simbolo} en {anio} (quizás todavía no cotizaba).")
        return
    fig = go.Figure(go.Scatter(x=datos.index, y=datos.values, name="Precio", line=dict(color=AZUL, width=1.8)))
    st.plotly_chart(estilo(fig, 380, leyenda=False), width="stretch")
    cambio = (datos.iloc[-1] / datos.iloc[0] - 1) * 100
    caida = (datos / datos.cummax() - 1).min() * 100
    fila = st.container(horizontal=True)
    fila.metric(f"Cambio en {anio}", f"{cambio:+.1f}%")
    fila.metric("Peor caída desde un máximo", f"{caida:.1f}%")


@st.cache_data(ttl=7 * 86400, show_spinner="Descargando ese año...")
def _anio(simbolo, anio):
    import yfinance as yf
    d = yf.download(simbolo, start=f"{anio}-01-01", end=f"{anio + 1}-01-01", progress=False, auto_adjust=False)
    if d.empty:
        return pd.Series(dtype=float)
    if isinstance(d.columns, pd.MultiIndex):
        d.columns = d.columns.get_level_values(0)
    return d["Close"].dropna()


def ficha(simbolo):
    """Ficha: tipo, sector, país, tamaño y dividendos al instante. La descripción y los riesgos (los escribe Claude,
    tarda unos segundos la primera vez) solo cuando se abre su sección."""
    import re

    import fichas
    d = fichas.datos(simbolo)
    with st.container(border=True):
        st.markdown("#### :material/badge: Ficha")
        fila = st.container(horizontal=True)
        fila.metric("Tipo", activos.tipo_nombre(simbolo), help=activos.que_es(simbolo).capitalize())
        fila.metric("Sector", activos.etiqueta_sector(simbolo))
        fila.metric("País", activos.pais(simbolo))
        tam, como = fichas.tamano_de(simbolo)
        fila.metric("Tamaño", tam, help=f"{AYUDA_TAMANO} Aquí: {como}.")
        st.markdown(f"**¿Paga dividendos?** {_dividendos_ficha(simbolo, d)}")
        st.caption(f":material/schedule: Horario: {activos.horario(simbolo)} · :material/storefront: Dónde comprar: "
                   f"{activos.donde_comprar(simbolo)}")
        seccion = st.expander("A qué se dedica y principales riesgos", icon=":material/description:",
                              key=f"ficha_desc_{simbolo}", on_change="rerun")
        if seccion.open:
            with seccion:
                clave = f"ficha_es_{simbolo}"
                if clave not in st.session_state:
                    with st.spinner("Preparando la descripción en español (solo la primera vez, unos segundos)..."):
                        st.session_state[clave] = fichas.descripcion(simbolo)
                es = st.session_state[clave]
                st.markdown(es.get("que_hace", ""))
                if es.get("riesgos"):
                    st.markdown("**Principales riesgos:**")
                    for riesgo in es["riesgos"]:
                        st.markdown(f"- {riesgo}")
                anios = sorted({a for r in es.get("riesgos", []) + [es.get("que_hace", "")]
                                for a in re.findall(r"\b(?:19|20)\d{2}\b", r)} | {"2008", "2020"})
                st.caption("Toca un año para ver qué le pasó a este activo en esa crisis:")
                fila = st.container(horizontal=True)
                for anio in anios:
                    if fila.button(f"{anio}" + (f" · {CRISIS[anio]}" if anio in CRISIS else ""),
                                   key=f"crisis_{simbolo}_{anio}", type="tertiary", icon=":material/show_chart:"):
                        grafica_anio(simbolo, anio)
                if es.get("respaldo"):
                    st.caption("Descripción tomada de Yahoo Finance (en inglés): Claude no respondió esta vez.")


# Paleta fija (se distingue también con daltonismo). Los colores se asignan en este orden, nunca en ciclo.
# Paleta neón (tema ciberpunk). Cian y magenta para series; verde/rojo reservados para subir/bajar.
PALETA = ["#00E5FF", "#FF2BD6", "#00FF9C", "#FFD300", "#8B5CF6", "#FF9F1C", "#4DD0FF", "#FF3864"]
FORMAS = ["triangle-up", "triangle-down", "circle", "diamond", "star", "square", "x", "pentagon"]
AZUL, NARANJA, VERDE_AGUA, GRIS = PALETA[0], PALETA[1], PALETA[2], "#7A8CA3"
VERDE, ROJO = "#00FF9C", "#FF3864"
COLOR_DECISION = {"COMPRAR": "green", "NO COMPRAR": "red", "ESPERAR": "gray", "SOLO MIRAR": "blue",
                  "COMPRAR CONFIRMADO": "green", "COMPRAR CON CAUTELA": "orange"}
ICONO_DECISION = {"COMPRAR": ":material/check_circle:", "NO COMPRAR": ":material/cancel:",
                  "ESPERAR": ":material/hourglass_empty:", "COMPRAR CONFIRMADO": ":material/verified:",
                  "COMPRAR CON CAUTELA": ":material/warning:", "SOLO MIRAR": ":material/visibility:"}
COLOR_ESTADO = {"alcista": "green", "bajista": "red", "neutral": "gray"}
ORDEN_CATEGORIAS = ["OPEP aumenta producción", "OPEP recorta producción", "OPEP mantiene o pospone", "OPEP otro",
                    "Irán", "Ormuz", "Trump", "Fed", "Inflación", "Tasas", "Tecnológicas", "Empleo",
                    "Ecopetrol", "Gobierno", "Dólar", "Política petrolera", "Petróleo (OPEP y geopolítica)"]
PAGINA_ACTIVO = "app_pages/activo.py"
PAGINA_SEGUIMIENTO = "app_pages/seguimiento.py"


def pesos(x):
    return f"${x:,.0f}".replace(",", ".")


def numero(x, decimales=2):
    return "—" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:,.{decimales}f}"


def version(simbolo):
    """Cambia cada vez que se actualizan los archivos del activo: así la app sabe cuándo recalcular."""
    archivos = [activos.ruta_precios(simbolo), activos.ruta_indicadores(simbolo), activos.CARPETA / "eventos.csv"]
    return tuple(a.stat().st_mtime if a.exists() else 0 for a in archivos)


# ---------- Datos en memoria (para que la app sea rápida) ----------
@st.cache_data(show_spinner=False, max_entries=300)
def _analisis(simbolo, _version):
    return estrategia.analizar(simbolo)


def analisis(simbolo):
    activos.asegurar_datos(simbolo)
    return _analisis(simbolo, version(simbolo))


@st.cache_data(show_spinner=False, max_entries=300)
def _precios(simbolo, _version):
    return pd.read_csv(activos.ruta_precios(simbolo), index_col="Fecha", parse_dates=True)


def precios(simbolo):
    activos.asegurar_datos(simbolo)
    return _precios(simbolo, version(simbolo))


@st.cache_data(show_spinner=False)
def _ranking(_version):
    tabla = ranking.leer()
    tabla["Ultimos_30"] = tabla["Ultimos_30"].apply(json.loads)
    return tabla


def tabla_ranking():
    if ranking.leer() is None:
        with st.spinner(f"Primera vez: descargando los {len(activos.ACTIVOS)} activos (tarda unos 3 minutos)..."):
            ranking.calcular(actualizar=True)
    return _ranking(ranking.ARCHIVO.stat().st_mtime)


def actualizar_todo():
    import noticias
    import nube
    with st.spinner("Descargando precios de todos los activos y recalculando..."):
        ranking.calcular(actualizar=True)
    with st.spinner("Buscando noticias nuevas..."):
        noticias.actualizar()
    if nube.conectado():
        with st.spinner("Guardando en la nube..."):
            nube.empacar_precios()
            nube.subir(nube.COMPARTIDOS + [nube.PRECIOS])
    st.cache_data.clear()


def unificada(r):
    """(decisión, color, dudas) combinando la app y el análisis de Claude."""
    import analisis_claude
    return analisis_claude.decision_unificada(r)


def ir_a_activo(simbolo):
    st.session_state["activo_pendiente"] = simbolo      # app.py lo aplica al selector antes de dibujarlo
    st.switch_page(PAGINA_ACTIVO)


def texto_decision(decision):
    return {"COMPRAR": "🟢 Comprar", "NO COMPRAR": "🔴 No comprar", "ESPERAR": "⚪ Esperar"}[decision]


# ---------- Cuadros ----------
def insignia_decision(decision):
    st.badge(decision, icon=ICONO_DECISION[decision], color=COLOR_DECISION[decision])


GLOSARIO = {
    "días parecidos": "Días del pasado en que el activo estaba en una situación similar a hoy: la misma tendencia de "
                      "sus medias y un RSI parecido.",
    "RSI": "Índice de fuerza relativa (0 a 100): mide si el precio subió o bajó muy rápido en las últimas 2 semanas. "
           "Más de 70 = subió muy rápido; menos de 30 = cayó muy rápido.",
    "media de 50 días": "El precio promedio de los últimos 50 días de mercado: muestra la tendencia de mediano plazo.",
    "media de 200 días": "El precio promedio de los últimos 200 días de mercado (casi un año): la tendencia de largo plazo.",
    "episodios": "Grupos de días parecidos separados por más de una semana. Si los casos son todos de la misma semana, "
                 "en realidad son una sola situación repetida.",
    "regla del 56%": "La app solo sugiere comprar si en al menos 56 de cada 100 días parecidos el precio subió.",
    "Time Machine": "Repite 10.000 veces la compra de hoy con días reales del pasado, aplicando el stop loss y el "
                    "objetivo, para ver cuánto se ganaría o perdería en promedio.",
    "ganancia esperada": "El promedio de ganancia o pérdida de las 10.000 simulaciones, ya descontado el 0,5% de costo.",
    "stop loss": "Precio al que se vende para cortar la pérdida: 3% por debajo del precio de compra.",
    "objetivo": "Precio al que se vende para asegurar la ganancia: 6% por encima del precio de compra.",
    "protección": "Si el precio está por debajo de su media de 200 días y sigue cayendo, la app espera una señal de "
                  "rebote antes de sugerir comprar.",
    "sentimiento": "Cada titular se marca como positivo (habla de subidas, ganancias) o negativo (caídas, pérdidas, "
                   "crisis) según sus palabras. Es una pista, no una certeza.",
}
AYUDA_AVANZADO = {
    "atr": "ATR (rango verdadero promedio): cuánto se mueve el precio en un día normal, mirando las últimas 2 semanas. "
           "Si un activo se mueve 4% al día, un stop loss de 3% te sacaría por puro ruido.",
    "sr": "Soporte: precio donde antes dejó de caer y rebotó (como un piso). Resistencia: precio donde antes dejó de "
          "subir (como un techo). Cuantas más veces lo tocó, más fuerte es el nivel.",
    "sent": "Leemos los titulares de la última semana del activo y de su mercado, y marcamos cada uno como positivo, "
            "negativo o neutro según sus palabras. El balance es una señal extra, no cambia la decisión.",
    "corr": "Correlación (de -1 a 1): qué tanto se mueven juntos dos activos. Cerca de 1 = suben y bajan casi igual, "
            "así que tener los dos es como tener el doble de uno solo. Cerca de 0 = no tienen que ver.",
    "var": "Valor en riesgo (VaR) al 95%: la pérdida de un día malo que solo se supera 1 de cada 20 días. Se calcula "
           "aplicándole a tu portafolio de hoy los movimientos reales de cada día de los últimos 2 años.",
}


def termino(texto, clave=None):
    """El término con su explicación al pasar el mouse."""
    ayuda = GLOSARIO[clave or texto].replace('"', "'")
    return f'<abbr title="{ayuda}" style="text-decoration: underline dotted; cursor: help">{texto}</abbr>'


@st.dialog("¿Por qué esta decisión?", width="large")
def explicar_decision(r):
    pasos_decision(r)


def explicacion_visible(r):
    """La explicación paso a paso, siempre visible (para estudiantes)."""
    with st.container(border=True):
        st.markdown("#### :material/school: ¿Por qué esta decisión? Paso a paso")
        pasos_decision(r)


def pasos_decision(r):
    """Explicación paso a paso de la decisión, para estudiantes."""
    decision, color, dudas = unificada(r)
    h = r["hoy"]
    st.markdown(f"### {activos.nombre(r['simbolo'])} · :{color}[{decision}]")
    pasos = []
    if r["decision"] == "SOLO MIRAR":
        pasos.append("Este activo está marcado como «solo para mirar»: la app no da señales para él.")
    else:
        if "MM50" in h and pd.notna(h.get("MM50")):
            pasos.append(f"Hoy el precio es {numero(r['precio'])}. La {termino('media de 50 días')} está en "
                         f"{numero(h['MM50'])} y la {termino('media de 200 días')} en {numero(h['MM200'])}: tendencia "
                         f"**{h.get('Tendencia', r['estado'])}**. El {termino('RSI')} está en {h['RSI14']:.0f}.")
        n = len(r["casos"])
        if not r["suficiente"]:
            pasos.append(f"Se encontraron solo **{n}** {termino('días parecidos')} y la regla pide al menos "
                         f"{estrategia.MIN_CASOS}. Con tan pocos datos no se puede decidir.")
        else:
            subieron = int((r["casos"]["Retorno_5d_%"] > 0).sum())
            pasos.append(f"Se encontraron **{n}** {termino('días parecidos')} a hoy, en {r['episodios']} "
                         f"{termino('episodios')} distintos (filtro: {estrategia.texto_filtro(r['rango_rsi'], r['usar_mes'])}).")
            pasos.append(f"En **{subieron}** de ellos el precio subió en los 5 días siguientes: **{r['prob']:.0f}%**.")
            supera = r["prob"] >= estrategia.UMBRAL_COMPRA
            pasos.append(f"{'**Supera**' if supera else '**No llega a**'} la {termino('regla del 56%')}.")
            tm = r["tm"]
            if tm:
                pasos.append(f"La {termino('Time Machine')} dio una {termino('ganancia esperada')} de "
                             f"**{tm['ganancia_esperada']:+.2f}%** ({'a favor' if tm['a_favor'] else 'en contra'}): llega "
                             f"al {termino('objetivo')} en {tm['p_objetivo']:.0f}% de las simulaciones y toca el "
                             f"{termino('stop loss')} en {tm['p_stop']:.0f}%.")
            try:
                import avanzado
                t = avanzado.noticias_semana(r["simbolo"], activos.noticias(r["simbolo"]))
                if len(t):
                    pos, neg, neu, txt = avanzado.balance(t["Titular"])
                    pasos.append(f"Señal extra, el {termino('sentimiento')} de las noticias de la semana: {pos} positivas, "
                                 f"{neg} negativas y {neu} neutras, balance **{txt}**. No cambia la decisión, pero un "
                                 "balance negativo es motivo para ir con más cuidado.")
            except Exception:
                pass
            try:
                import nube
                if nube.conectado():
                    pct, n, usar, _ = comunidad()
                    mercado = (activos.mercados(r["simbolo"]) or [None])[0]
                    if usar and mercado in pct.index:
                        pasos.append(f"Señal extra de la comunidad (anónima, validada con backtest): el "
                                     f"{pct[mercado]:.0f}% de las compras de esta semana fueron de "
                                     f"{activos.NOMBRE_MERCADO.get(mercado, mercado)}.")
            except Exception:
                pass
            if r.get("proteccion"):
                pasos.append(f"Se activó la {termino('protección')}: el precio está bajo su media de 200 días y sigue cayendo.")
            if r.get("cerrado"):
                pasos.append("Hoy el mercado de este activo está cerrado (fin de semana o festivo): no se sugiere comprar.")
        if r["decision"] == "COMPRAR":
            pasos.append("Claude revisó resultados, pares y noticias: **está de acuerdo**." if decision == "COMPRAR CONFIRMADO"
                         else "Claude tiene dudas o aún no lo revisa: " + "; ".join(dudas))
    for i, paso in enumerate(pasos, 1):
        st.markdown(f"**{i}.** {paso}", unsafe_allow_html=True)
    st.markdown(f"#### Por eso: :{color}[{decision}]")
    st.caption("Pasa el mouse sobre las palabras subrayadas para ver qué significan. Es un análisis del pasado, no "
               "una recomendación de inversión.")


@st.dialog("¿Por qué mantener o vender?", width="large")
def explicar_sugerencia(p):
    """Explicación de 'Mantener' o 'Vender' de una compra (real o simulada)."""
    g = p["Ganancia_%"]
    st.markdown(f"### {p['Nombre']} · {p['Sugerencia'].upper()}")
    pasos = [f"Compraste a {numero(p['Precio_compra'])} y hoy vale {numero(p['Precio_actual'])}: vas **{g:+.2f}%**.",
             f"El {termino('stop loss')} está en {numero(p['Stop'])} (-{estrategia.STOP_LOSS}%) y el "
             f"{termino('objetivo')} en {numero(p['Objetivo'])} (+{estrategia.OBJETIVO}%).",
             f"Motivo: {p['Motivo']}."]
    for i, paso in enumerate(pasos, 1):
        st.markdown(f"**{i}.** {paso}", unsafe_allow_html=True)
    st.markdown(f"#### Por eso: **{p['Sugerencia'].upper()}**")
    st.caption("«Vender» aparece si tocó el stop loss o el objetivo, o si la probabilidad de subida bajó de 50%.")


@st.cache_data(ttl=86400, show_spinner="Buscando las noticias de ese día...")
def _noticias_del_dia(simbolo, fecha):
    import noticias
    nombre = activos.nombre(simbolo).split(" (")[0]
    d = pd.Timestamp(fecha)
    busqueda = f'"{nombre}" after:{d:%Y-%m-%d} before:{d + pd.Timedelta(days=2):%Y-%m-%d}'
    idioma = noticias.ESPANOL if "ecopetrol" in activos.noticias(simbolo) else noticias.INGLES
    resultados = noticias._consultar(busqueda, idioma, dias=4000)       # Rango largo: la fecha la pone la búsqueda
    return [(t, f, u) for _, t, f, u in resultados][:10]


@st.dialog("Detalle del caso parecido", width="large")
def dialogo_caso(simbolo, r, fecha, columna):
    """Al tocar una celda de la tabla de casos parecidos: noticias del día o la gráfica de esa columna."""
    fecha = pd.Timestamp(fecha)
    d = r["datos"]
    st.markdown(f"### {activos.nombre(simbolo)} · {fecha:%d/%m/%Y}")
    if columna == "Fecha":
        eventos = eventos_de(simbolo, version(simbolo))
        cerca = eventos[(eventos["Fecha"] - fecha).abs() <= pd.Timedelta(days=3)]
        for _, e in cerca.iterrows():
            st.markdown(f"- **{e['Fecha']:%d/%m/%Y}** · {e['Tipo']}: {e['Evento']}")
        lista = _noticias_del_dia(simbolo, fecha.date())
        if lista:
            st.markdown("**Titulares de esos días:**")
            for titular, fuente, url in lista:
                st.markdown(f"- [{titular}]({url}) · :gray[{fuente}]")
        elif cerca.empty:
            st.caption("No encontré noticias de ese día.")
        return
    ventana = {"Cierre": (10, 20), "RSI14": (15, 15), "Retorno_5d_%": (1, 8), "Perdida_max_%": (10, 20)}[columna]
    tramo = d[(d.index >= fecha - pd.Timedelta(days=ventana[0])) & (d.index <= fecha + pd.Timedelta(days=ventana[1]))]
    y = "RSI14" if columna == "RSI14" else "Cierre"
    fig = go.Figure(go.Scatter(x=tramo.index, y=tramo[y], mode="lines+markers", line=dict(color=AZUL, width=2),
                               name="RSI" if y == "RSI14" else "Cierre"))
    fig.add_vline(x=fecha, line=dict(color=NARANJA, dash="dash"))
    if columna == "RSI14":
        for nivel in (70, 30):
            fig.add_hline(y=nivel, line=dict(color=GRIS, dash="dot"))
        texto = f"RSI de ese mes. El día del caso estaba en {d.loc[fecha, 'RSI14']:.0f}."
    elif columna == "Retorno_5d_%":
        cinco = d[d.index >= fecha].head(estrategia.DIAS_ADELANTE + 1)
        fig.add_vrect(x0=cinco.index[0], x1=cinco.index[-1], fillcolor="rgba(0,229,255,0.08)", line_width=0)
        texto = f"Los 5 días siguientes: de {numero(cinco['Cierre'].iloc[0])} a {numero(cinco['Cierre'].iloc[-1])} ({d.loc[fecha, 'Retorno_5d_%']:+.2f}%)."
    elif columna == "Perdida_max_%":
        cinco = d[d.index > fecha].head(estrategia.DIAS_ADELANTE)
        if len(cinco):
            dia_min = cinco["Minimo"].idxmin()
            fig.add_trace(go.Scatter(x=[dia_min], y=[cinco["Minimo"].min()], mode="markers", name="Precio más bajo",
                                     marker=dict(color=ROJO, size=13, symbol="triangle-down")))
        texto = f"La peor caída en esos 5 días fue {d.loc[fecha, 'Perdida_max_%']:+.2f}% (triángulo rojo)."
    else:
        texto = "El cierre en las semanas alrededor de ese día."
    st.plotly_chart(estilo(fig, 340), width="stretch")
    st.caption(f"{texto} La línea punteada naranja marca el día del caso.")


QUE_TENDRIA_QUE_PASAR = {
    "petróleo": {"Optimista": "que la OPEP recorte producción, crezca la tensión en Ormuz o bajen los inventarios de EE.UU.",
                 "Base": "que no haya noticias fuertes y el petróleo se mueva dentro de su rango normal.",
                 "Pesimista": "que la OPEP suba producción, haya avances de paz con Irán o suban los inventarios."},
    "oro": {"Optimista": "que la Fed baje tasas, suba la inflación o aumente la tensión geopolítica.",
            "Base": "que los datos de inflación y empleo salgan como se esperaba.",
            "Pesimista": "que la Fed suba tasas o el dólar se fortalezca."},
    "nasdaq": {"Optimista": "buenos resultados de las tecnológicas o datos que hagan pensar en tasas más bajas.",
               "Base": "un mercado sin sorpresas grandes esta semana.",
               "Pesimista": "resultados decepcionantes, inflación alta o una Fed más dura."},
    "ecopetrol": {"Optimista": "que suba el petróleo y lleguen buenas noticias de sus resultados o del gobierno.",
                  "Base": "que el petróleo y el dólar se queden estables.",
                  "Pesimista": "que baje el petróleo o suba el riesgo político o fiscal en Colombia."},
}


@st.dialog("Escenarios de la predicción", width="large")
def dialogo_escenarios(r):
    contar_uso("escenarios")
    tm = r["tm"]
    grupo = (activos.noticias(r["simbolo"]) or ["nasdaq"])[0]
    textos = QUE_TENDRIA_QUE_PASAR.get(grupo, QUE_TENDRIA_QUE_PASAR["nasdaq"])
    st.markdown(f"### {activos.nombre(r['simbolo'])} · hoy {numero(r['precio'])}")
    st.caption(f"Basado en {tm['simulaciones']:,} simulaciones de la Time Machine con stop loss -{estrategia.STOP_LOSS}% "
               f"y objetivo +{estrategia.OBJETIVO}%.".replace(",", "."))
    for nombre, color, titulo in [("Optimista", "green", "llega al objetivo"), ("Base", "blue", "vence el plazo"),
                                  ("Pesimista", "red", "toca el stop loss")]:
        e = tm["escenarios"][nombre]
        with st.container(border=True):
            st.markdown(f"#### :{color}[{nombre}] · {titulo}")
            fila = st.container(horizontal=True)
            fila.metric("Probabilidad", f"{e['probabilidad']:.0f}%")
            if e["retorno"] is None:
                st.caption("No ocurrió en ninguna simulación.")
                continue
            fila.metric("Precio esperado", numero(r["precio"] * e["precio_factor"]))
            fila.metric("Retorno", f"{e['retorno']:+.2f}%")
            fila.metric("Pérdida máxima", f"{e['perdida_max']:+.2f}%", help="La peor caída antes de vender.")
            fila.metric("Plazo", f"{e['dias']:.1f} días", help="Días de mercado promedio hasta vender.")
            st.markdown(f"**Qué tendría que pasar:** {textos[nombre]}")


def abanico(simbolo, dias_opciones=(5, 10, 20)):
    """Abanico de 100 caminos posibles (Monte Carlo) con mediana y bandas del 10% y 90%."""
    import montecarlo
    contar_uso("abanico")
    cab = st.container(horizontal=True, vertical_alignment="center")
    cab.markdown("#### Abanico de predicciones (Monte Carlo)")
    boton_que_es(cab, "montecarlo", f"mc_{simbolo}")
    dias = st.segmented_control("Días hacia adelante", list(dias_opciones), default=20, required=True,
                                key=f"abanico_dias_{simbolo}")
    cierre = precios(simbolo)["Cierre"]
    matriz = montecarlo.caminos(cierre, dias)
    fechas = [cierre.index[-1]] + list(pd.bdate_range(cierre.index[-1] + pd.Timedelta(days=1), periods=dias))
    bandas, r = montecarlo.resumen(matriz, fechas)
    muestra = matriz[:100]
    suben = int((muestra[:, -1] > muestra[0, 0]).sum())
    reciente = cierre.tail(60)
    fig = go.Figure(go.Scatter(x=reciente.index, y=reciente, name="Precio real", line=dict(color=AZUL, width=2)))
    for i, camino in enumerate(muestra):
        fig.add_trace(go.Scatter(x=fechas, y=camino, mode="lines", showlegend=False, hoverinfo="skip",
                                 line=dict(width=0.8, color="rgba(0,255,156,0.30)" if camino[-1] > camino[0]
                                           else "rgba(255,56,100,0.30)")))
    for col, nombre in [("P10", "Banda 10%"), ("P90", "Banda 90%")]:
        fig.add_trace(go.Scatter(x=fechas, y=bandas[col], name=nombre, line=dict(color=NARANJA, width=1.6, dash="dash")))
    fig.add_trace(go.Scatter(x=fechas, y=bandas["Mediana"], name="Mediana", line=dict(color="#FFFFFF", width=3)))
    st.plotly_chart(estilo(fig, 420), width="stretch", key=f"abanico_{simbolo}")
    fila = st.container(horizontal=True)
    fila.metric(f"Mediana en {dias} días", numero(r["mediana"]), f"{(r['mediana'] / cierre.iloc[-1] - 1) * 100:+.1f}%")
    fila.metric("Rango (10% a 90%)", f"{numero(r['p10'])} – {numero(r['p90'])}")
    fila.metric("Caminos que suben", f"{suben} de 100", delta_color="off")
    fila.metric("Caminos que bajan", f"{100 - suben} de 100", delta_color="off")
    st.caption("Cada línea es un futuro posible armado con cambios diarios reales de los últimos 2 años: verde si "
               "termina arriba, rojo si termina abajo. No es una predicción segura.")
    st.caption(f":material/info: {EXPLICACION_BANDAS}")


def caja_sugerencia(r):
    """La casilla 'Sugerencia' de la barra izquierda."""
    decision, _, dudas = unificada(r)
    with st.container(border=True):
        st.markdown("**Sugerencia**")
        insignia_decision(decision)
        if r["suficiente"]:
            st.markdown(f"Probabilidad de subida: **{r['prob']:.1f}%**")
        st.caption(dudas[0] if dudas else r["razon"])


AYUDA_DIAS_PARECIDOS = ("Días de los últimos 5 años en que el activo estaba en una situación parecida a hoy: la misma "
                        "tendencia de sus medias y un RSI parecido (es el filtro). Se mira qué pasó después de cada uno.")


@st.dialog("¿Qué es esto?", width="large")
def dialogo_tutorial(tema):
    import tutorial
    titulo, que_es, ejemplo = tutorial.TUTORIAL[tema]
    st.markdown(f"### {titulo}")
    st.markdown(que_es)
    st.markdown(f"**Ejemplo:** {ejemplo}")
    st.caption("Todas las explicaciones están en la página «Aprende» (barra de abajo).")


def boton_que_es(donde, tema, clave):
    """Botón «¿Qué es esto?» que abre la explicación del tutorial."""
    if donde.button("¿Qué es esto?", icon=":material/school:", key=f"que_es_{clave}", type="tertiary"):
        dialogo_tutorial(tema)


def muestra_casos(r):
    """'Muestra: últimos 5 años, del 08/11/2021 al 06/11/2026'."""
    d = r["datos"].index
    return f"Muestra: últimos 5 años, del {d[0]:%d/%m/%Y} al {d[-1]:%d/%m/%Y}"


def color_signo(x, texto=None):
    """Número en verde si es positivo y en rojo si es negativo (para st.markdown)."""
    return f":{'green' if x > 0 else 'red' if x < 0 else 'gray'}[{texto or f'{x:+.2f}%'}]"


def decision_grande(r):
    """La decisión grande de la página de un activo (app + Claude)."""
    import avanzado
    decision, color, dudas = unificada(r)
    simbolo = r["simbolo"]
    with st.container(border=True):
        st.markdown(f"## :{color}[{ICONO_DECISION[decision]} {decision}]")
        if activos.tipo(simbolo) in ("índice", "bono") and activos.INDICE_ETF.get(simbolo):
            st.caption(f":material/info: Un índice no se compra directamente: «Comprar / No comprar» se refiere a su "
                       f"ETF ({' o '.join(activos.INDICE_ETF[simbolo])}), que lo copia casi igual.")
        st.markdown(r["razon"])
        if decision == "COMPRAR CONFIRMADO":
            st.caption(":material/verified: La app y el análisis de Claude coinciden.")
        for d in dudas:
            st.markdown(f":orange[:material/help: {d}]")
        fila = st.container(horizontal=True)
        fila.metric("Probabilidad de subida", "—" if not r["suficiente"] else f"{r['prob']:.1f}%",
                    help="De cada 100 días parecidos a hoy en el pasado, cuántos terminaron más arriba 5 días después.")
        rango = r["tm"]["rango_5d"] if r["tm"] else None
        fila.metric("Predicción a 5 días", numero(r["prediccion_5d"]),
                    f"rango {numero(r['precio'] * rango[0])} a {numero(r['precio'] * rango[2])}" if rango else None,
                    delta_color="off",
                    help="Precio esperado (escenario base). El rango es donde termina el precio en 8 de cada 10 "
                         "simulaciones (del 10% al 90%). Toca «Ver escenarios» para el detalle.")
        if r["tm"] and fila.button("Ver escenarios", icon=":material/insights:", key=f"esc_{simbolo}"):
            dialogo_escenarios(r)
        fila.metric("Precio de compra", numero(r["precio"]), help="Último precio de cierre.")
        fila.metric(f"Stop loss (-{estrategia.STOP_LOSS}%)", numero(r["stop"]),
                    help="Si el precio baja hasta aquí, se vende para limitar la pérdida. Puedes poner tu stop "
                         "personal más abajo, en «Tu stop loss personal».")
        fila.metric(f"Objetivo (+{estrategia.OBJETIVO}%)", numero(r["objetivo"]),
                    help="Si el precio sube hasta aquí, se vende para asegurar la ganancia.")
        if r["suficiente"]:
            st.dataframe(r["escenarios"].iloc[::-1], hide_index=True, alt="Tres escenarios a 5 días",
                         column_config={"Retorno esperado %": st.column_config.NumberColumn(format="%+.2f%%"),
                                        "Pérdida máxima %": st.column_config.NumberColumn(format="%+.2f%%")})
            st.caption(f"Filtro usado: {estrategia.texto_filtro(r['rango_rsi'], r['usar_mes'])}: **{len(r['casos'])} "
                       f"días parecidos** en {r['episodios']} episodios. {muestra_casos(r)}. Cada escenario es un "
                       "tercio de los días parecidos, de peor a mejor; pérdida máxima = la peor caída tocada durante "
                       "los 5 días.", help=AYUDA_DIAS_PARECIDOS)
        tm = r["tm"]
        if tm:
            titulo = st.container(horizontal=True, vertical_alignment="center")
            titulo.markdown(f"#### :material/history: Time Machine · {tm['simulaciones']:,} simulaciones".replace(",", "."))
            if tm["a_favor"]:
                titulo.badge("A favor", icon=":material/thumb_up:", color="green")
            else:
                titulo.badge("En contra", icon=":material/thumb_down:", color="red")
            boton_que_es(titulo, "time_machine", f"tm_{simbolo}")
            fila = st.container(horizontal=True)
            fila.metric(f"Llega al objetivo (+{estrategia.OBJETIVO}%)", f"{tm['p_objetivo']:.1f}%")
            fila.metric(f"Toca el stop loss (-{estrategia.STOP_LOSS}%)", f"{tm['p_stop']:.1f}%")
            fila.metric(f"Vende a los {estrategia.DIAS_ADELANTE} días", f"{tm['p_plazo']:.1f}%")
            g = tm["ganancia_esperada"]
            fila.metric("Ganancia esperada", f"{g:+.2f}%", "a favor" if tm["a_favor"] else
                        ("-en contra" if g <= 0 else "-muy poca: no alcanza"), delta_color="normal",
                        help=f"Promedio de las 10.000 simulaciones, ya restado el {estrategia.COSTO * 100:.1f}% de costo. "
                             f"Solo dice «a favor» si pasa de +{estrategia.MARGEN_A_FAVOR}%: ganar 0,05% no compensa el riesgo.")
            fila.metric("Peor caso", f"{tm['peor_caso']:+.2f}%",
                        help=f"La peor de las 10.000. En 5 de cada 100 se pierde {tm['percentil_5']:+.2f}% o más.")
            st.markdown(f"**Ganancia esperada:** {color_signo(g)} (ya restada la comisión)")
            if tm["p_stop"] > tm["p_objetivo"]:
                st.warning(f"Toca el stop loss más veces ({tm['p_stop']:.0f}%) que el objetivo ({tm['p_objetivo']:.0f}%): "
                           f"en estos casos es más probable perder {estrategia.STOP_LOSS}% que ganar {estrategia.OBJETIVO}%.",
                           icon=":material/warning:")
            if tm["peor_caso"] < -estrategia.STOP_LOSS - 0.5:
                st.caption(f":material/info: ¿Por qué el peor caso ({tm['peor_caso']:+.1f}%) es peor que el stop de "
                           f"-{estrategia.STOP_LOSS}%? Porque el stop no garantiza el precio: si sale una noticia de noche, "
                           "el precio puede **abrir** al día siguiente mucho más abajo (un salto o «gap») y la venta se hace "
                           "a ese precio, no al del stop.")
            # Plazo y hora de venta según lo que pasó en los días parecidos (1, 2, 3 o 5 días; nunca minutos)
            t = avanzado.plazos(r["datos"], r["casos"].index, estrategia.COSTO * 100)
            if len(t):
                h, hora, f = avanzado.mejor_plazo(t)
                fecha = pd.Timestamp(r["fecha"]) + pd.offsets.BDay(h)
                st.markdown(f":material/event: **Cuándo vender:** a los **{h} día{'s' if h > 1 else ''} de mercado** "
                            f"(fecha sugerida: **{fecha:%d/%m/%Y}**). **Hora sugerida:** {hora}. Antes, si toca el stop loss "
                            "o el objetivo.")
                vista = t.rename(columns={"Plazo": "Vender a los", "Aciertos_%": "Aciertos", "Al_cierre_%": "Ganancia al cierre",
                                          "En_apertura_%": "Ganancia en la apertura", "Casos": "Días parecidos"})
                vista["Vender a los"] = vista["Vender a los"].map(lambda d: f"{d} día{'s' if d > 1 else ''}")
                st.dataframe(vista.style.map(lambda v: f"color: {VERDE if v > 0 else ROJO}" if isinstance(v, float) else "",
                                             subset=["Ganancia al cierre", "Ganancia en la apertura"]),
                             hide_index=True, alt="Aciertos y ganancia promedio para cada plazo de venta",
                             column_config={"Aciertos": st.column_config.NumberColumn(
                                                format="%.0f%%", help="Tasa de aciertos: % de días parecidos en que el "
                                                                      "precio terminó más arriba a ese plazo."),
                                            "Ganancia al cierre": st.column_config.NumberColumn(format="%+.2f%%"),
                                            "Ganancia en la apertura": st.column_config.NumberColumn(format="%+.2f%%"),
                                            "Días parecidos": st.column_config.NumberColumn(help=AYUDA_DIAS_PARECIDOS)})
            st.caption("La Time Machine repite 10.000 veces la compra de hoy con días reales que vinieron después de "
                       "los días parecidos, aplicando el stop loss y el objetivo. Si la ganancia esperada no es "
                       f"claramente positiva (más de +{estrategia.MARGEN_A_FAVOR}%), la decisión es NO COMPRAR aunque la "
                       "probabilidad pase de 56%.")


# ---------- Gráficas ----------
def modo_claro():
    return getattr(st.context.theme, "type", "dark") == "light"


def estilo(fig, alto, leyenda=True):
    """Estilo HUD: cuadrícula cian tenue y letra monoespaciada. En modo claro la gráfica es un panel oscuro (el neón
    no se lee sobre blanco)."""
    fig.update_layout(height=alto, margin=dict(l=8, r=8, t=28 if leyenda else 8, b=8), hovermode="x unified",
                      showlegend=leyenda, legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
                      paper_bgcolor="#0B1220" if modo_claro() else "rgba(0,0,0,0)", plot_bgcolor="rgba(0,229,255,0.02)",
                      font=dict(family="Share Tech Mono, monospace", color="#D6F6FF"),
                      hoverlabel=dict(bgcolor="#0B1220", bordercolor="#00E5FF", font_family="Share Tech Mono"))
    fig.update_xaxes(showgrid=False, linecolor="rgba(0,229,255,0.35)")
    fig.update_yaxes(gridcolor="rgba(0,229,255,0.10)", zerolinecolor="rgba(0,229,255,0.25)")
    return fig


def banda(fig, x, baja, alta, nombre, color="rgba(255,43,214,0.22)"):
    """Rango como polígono cerrado (siempre visible, no depende del orden de las líneas)."""
    x = list(x)
    fig.add_trace(go.Scatter(x=x + x[::-1], y=list(alta) + list(baja)[::-1], fill="toself", fillcolor=color,
                             line=dict(width=0), name=nombre, hoverinfo="skip"))


def mini_grafica(serie, alto=150):
    color = VERDE if serie.iloc[-1] >= serie.iloc[0] else ROJO
    fig = go.Figure(go.Scatter(x=serie.index, y=serie, line=dict(color=color, width=2), name="Precio",
                               hovertemplate="%{x|%d/%m}: %{y:,.2f}<extra></extra>"))
    return estilo(fig, alto, leyenda=False)


@st.cache_data(ttl=600, show_spinner="Bajando los precios por hora...")
def _por_hora(simbolo):
    """Velas de 1 hora del último día de mercado, en hora de Bogotá."""
    import yfinance as yf
    d = yf.download(simbolo, period="5d", interval="60m", progress=False, auto_adjust=False)
    if d.empty:
        return pd.Series(dtype=float)
    if isinstance(d.columns, pd.MultiIndex):
        d.columns = d.columns.get_level_values(0)
    c = d["Close"].dropna()
    c.index = c.index.tz_convert("America/Bogota").tz_localize(None)
    return c[c.index.date == c.index[-1].date()]


def grafica_un_dia(simbolo, clave):
    c = _por_hora(simbolo)
    if len(c) < 2:
        st.caption(":material/info: Yahoo no tiene precios por hora de este activo para el último día.")
        return
    fig = go.Figure(go.Scatter(x=c.index, y=c, name="Precio por hora", mode="lines+markers",
                               line=dict(color=AZUL, width=2), hovertemplate="%{x|%I:%M %p}: %{y:,.2f}<extra></extra>"))
    fig.update_xaxes(tickformat="%I:%M %p")
    st.caption(f"{c.index[-1]:%d/%m/%Y}, hora de Bogotá: {(c.iloc[-1] / c.iloc[0] - 1) * 100:+.2f}% en el día "
               "(una vela por hora)")
    st.plotly_chart(estilo(fig, 380, leyenda=False), width="stretch", key=f"dia_{clave}")


def filtro_periodo(clave, fechas, con_dia=False):
    """Botones 1D ... 5A y fechas personalizadas. Devuelve (desde, hasta), o (None, None) si eligió «1 día»."""
    opciones = {"1 semana": 7, "1 mes": 31, "3 meses": 92, "6 meses": 183, "1 año": 366, "5 años": 1830}
    elegido = st.segmented_control("Periodo", (["1 día"] if con_dia else []) + list(opciones) + ["Personalizado"],
                                   default="6 meses", required=True, key=f"periodo_{clave}")
    if elegido == "1 día":
        return None, None
    fin = fechas[-1].date()
    if elegido == "Personalizado":
        rango = st.date_input("Fechas", value=(fin - timedelta(days=90), fin), min_value=fechas[0].date(),
                              max_value=fin, key=f"fechas_{clave}", format="DD/MM/YYYY")
        if isinstance(rango, (tuple, list)) and len(rango) == 2:
            return pd.Timestamp(rango[0]), pd.Timestamp(rango[1])
        return pd.Timestamp(fin - timedelta(days=90)), pd.Timestamp(fin)
    return pd.Timestamp(fin - timedelta(days=opciones[elegido])), pd.Timestamp(fin)


def categoria(fila, noticias_activo):
    grupos = str(fila["Activo"]).split(";")
    if "ecopetrol" in noticias_activo and "ecopetrol" not in grupos:
        return "Petróleo (OPEP y geopolítica)"       # Para Ecopetrol, las noticias de petróleo van juntas
    if fila["Tipo"] == "Geopolítico":
        return "Geopolítico"
    if fila["Tipo"] == "OPEP":
        for palabra, cat in [("Aumenta", "OPEP aumenta producción"), ("Recorta", "OPEP recorta producción"),
                             ("Mantiene", "OPEP mantiene o pospone"), ("Pospone", "OPEP mantiene o pospone")]:
            if fila["Evento"].startswith(palabra):
                return cat
        return "OPEP otro"
    return fila["Tipo"]


@st.cache_data(show_spinner=False)
def eventos_de(simbolo, _version):
    eventos = pd.read_csv(activos.CARPETA / "eventos.csv", parse_dates=["Fecha"])
    grupos = set(activos.noticias(simbolo))
    if not grupos:
        return eventos.iloc[0:0].assign(Categoria=[])
    eventos = eventos[eventos["Activo"].str.split(";").apply(lambda g: bool(grupos & set(g)))].copy()
    eventos["Categoria"] = eventos.apply(categoria, axis=1, noticias_activo=grupos)
    return eventos


def grafica_precio(simbolo, r, clave="principal"):
    """Precio con medias, noticias y RSI, con filtro de periodo."""
    ind = r["datos"]
    desde, hasta = filtro_periodo(clave, ind.index, con_dia=True)
    if desde is None:
        grafica_un_dia(simbolo, clave)
        return
    d = ind[(ind.index >= desde) & (ind.index <= hasta)]
    if len(d) < 2:
        st.caption(":material/info: No hay datos en esas fechas.")
        return
    ev = eventos_de(simbolo, version(simbolo))
    ev = ev[(ev["Fecha"] >= desde) & (ev["Fecha"] <= hasta)]
    from plotly.subplots import make_subplots
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.75, 0.25], vertical_spacing=0.05)
    for col, nombre, color, grosor in [("Cierre", "Precio", AZUL, 1.6), ("MM50", "Media 50 días", NARANJA, 2),
                                       ("MM200", "Media 200 días", VERDE_AGUA, 2)]:
        if col in d and d[col].notna().any():
            fig.add_trace(go.Scatter(x=d.index, y=d[col], name=nombre, line=dict(color=color, width=grosor)), row=1, col=1)
    presentes = [c for c in ORDEN_CATEGORIAS if c in set(ev["Categoria"])]
    for i, cat in enumerate(presentes[:len(PALETA)]):
        sub = ev[ev["Categoria"] == cat]
        pos = d.index.searchsorted(sub["Fecha"]).clip(max=len(d) - 1)
        fig.add_trace(go.Scatter(x=d.index[pos], y=d["Cierre"].iloc[pos], mode="markers", name=cat,
                                 marker=dict(color=PALETA[i], symbol=FORMAS[i], size=11, line=dict(color="white", width=1.5)),
                                 text=sub["Evento"].values, hovertemplate="%{text}<extra></extra>"), row=1, col=1)
    for _, e in ev[ev["Categoria"] == "Geopolítico"].iterrows():
        fig.add_vline(x=e["Fecha"], line=dict(color=GRIS, dash="dash", width=1), row=1, col=1)
    fig.add_trace(go.Scatter(x=d.index, y=d["RSI14"], name="RSI 14", line=dict(color=AZUL, width=1.2),
                             showlegend=False), row=2, col=1)
    for nivel in (70, 30):
        fig.add_hline(y=nivel, line=dict(color=GRIS, dash="dash", width=1), row=2, col=1)
    # Franjas de tendencia: verde = al alza (precio > media 50 > media 200), roja = a la baja (al revés)
    estado = np.where((d["Cierre"] > d["MM50"]) & (d["MM50"] > d["MM200"]), 1,
                      np.where((d["Cierre"] < d["MM50"]) & (d["MM50"] < d["MM200"]), -1, 0))
    cambios = np.flatnonzero(np.diff(estado)) + 1
    for ini, fin in zip(np.r_[0, cambios], np.r_[cambios, len(d)]):
        if estado[ini] != 0 and fin - ini >= 3:            # Ignora franjas de 1-2 días (ruido)
            fig.add_vrect(x0=d.index[ini], x1=d.index[fin - 1], line_width=0, layer="below", row=1, col=1,
                          fillcolor="rgba(0,255,156,0.07)" if estado[ini] > 0 else "rgba(255,56,100,0.07)")
    fig.update_yaxes(title_text="Precio", row=1, col=1)
    fig.update_yaxes(title_text="RSI", range=[0, 100], row=2, col=1)
    cambio = (d["Cierre"].iloc[-1] / d["Cierre"].iloc[0] - 1) * 100
    st.caption(f"Del {d.index[0]:%d/%m/%Y} al {d.index[-1]:%d/%m/%Y}: {cambio:+.1f}% · franja verde = periodo al alza, "
               "franja roja = periodo a la baja")
    st.plotly_chart(estilo(fig, 560), width="stretch", key=f"graf_{clave}")
    if len(ev):
        st.caption("Pasa el mouse sobre los puntos para ver cada noticia. RSI: 70 = sobrecompra, 30 = sobreventa.")


def grafica_comparacion(simbolos, clave="comparar"):
    """Varios activos en porcentaje desde el inicio del periodo (todos empiezan en 0%)."""
    series = {}
    for s in simbolos[:len(PALETA)]:
        try:
            series[s] = precios(s)["Cierre"]
        except Exception as error:
            st.warning(f"No pude cargar {s}: {error}")
    if not series:
        return
    todas = pd.DataFrame(series).sort_index().ffill()
    desde, hasta = filtro_periodo(clave, todas.index)
    t = todas[(todas.index >= desde) & (todas.index <= hasta)].dropna(how="all")
    fig = go.Figure()
    for i, (s, serie) in enumerate(t.items()):
        serie = serie.dropna()
        if len(serie) < 2:
            continue
        pct = (serie / serie.iloc[0] - 1) * 100
        fig.add_trace(go.Scatter(x=pct.index, y=pct, name=f"{s} ({pct.iloc[-1]:+.1f}%)",
                                 line=dict(color=PALETA[i], width=2), hovertemplate="%{y:+.1f}%"))
    fig.add_hline(y=0, line=dict(color=GRIS, width=1, dash="dot"))
    fig.update_yaxes(title_text="Cambio desde el inicio (%)", ticksuffix="%")
    st.plotly_chart(estilo(fig, 420), width="stretch", key=f"graf_{clave}")


def ayuda_proximo_evento():
    return ("El próximo evento del calendario que suele mover este mercado: reuniones de la OPEP+ e inventarios "
            "de petróleo (miércoles) para el petróleo; decisiones de la Fed, inflación y empleo de EE.UU. para el "
            "Nasdaq y el oro. Ese día el precio puede moverse más de lo normal.")


def hoy_texto():
    return date.today().strftime("%d/%m/%Y")


# ---------- Dinero ----------
def dinero(x, moneda="USD", decimales=2):
    """US$ 1,234.56 para dólares; $1.234.567 COP para pesos."""
    if x is None or pd.isna(x):
        return "—"
    if moneda == "COP":
        return pesos(x) + " COP"
    return f"US$ {x:,.{decimales}f}"


# ---------- Noticias de una empresa ----------
@st.dialog("Noticias", width="large")
def panel_noticias(simbolo):
    import noticias
    st.markdown(f"### {activos.nombre(simbolo)} ({simbolo})")
    with st.spinner("Buscando noticias..."):
        t = noticias.de_empresa(simbolo)
    if activos.noticias(simbolo):                          # Más las noticias de su mercado
        t = pd.concat([t, noticias.de_grupos(activos.noticias(simbolo))]).drop_duplicates("URL")
    periodo = st.segmented_control("Periodo", ["Hoy", "Última semana", "Último mes", "Todas"], default="Última semana",
                                   required=True, key=f"per_not_{simbolo}")
    dias = {"Hoy": 0, "Última semana": 7, "Último mes": 30, "Todas": None}[periodo]
    if dias is not None:
        t = t[t["Fecha"] >= pd.Timestamp.now().normalize() - pd.Timedelta(days=dias)]
    t = t.sort_values("Fecha", ascending=False)
    st.caption(f"{len(t)} noticias · última actualización: {noticias.ultima_actualizacion() or 'nunca'} · "
               "fuente: Google Noticias")
    with st.container(height=520):
        for _, n in t.iterrows():
            st.markdown(f"**[{n['Titular']}]({n['URL']})**  \n:gray[{n['Fuente']} · {n['Fecha']:%d/%m/%Y %I:%M %p}"
                        + (f" · {n['Tipo']}" if n["Tipo"] != "Empresa" else "") + "]")
        if t.empty:
            st.caption("No hay noticias en este periodo.")


# ---------- Seguimiento: cambio y mini gráfica por periodo ----------
PERIODOS_LISTA = {"1 día": 1, "1 semana": 7, "15 días": 15, "30 días": 30, "60 días": 60, "90 días": 90,
                  "180 días": 180, "1 año": 365, "5 años": 1830}


@st.cache_data(show_spinner="Calculando el periodo...")
def tabla_periodo(dias, _version):
    """Cambio % y precios para la mini gráfica de cada activo en el periodo elegido."""
    filas = {}
    for s in ranking.leer()["Activo"]:
        try:                                                # Directo del archivo: no llena la memoria de la app
            c = pd.read_csv(activos.ruta_precios(s), usecols=["Fecha", "Cierre"], index_col="Fecha",
                            parse_dates=True)["Cierre"]
        except Exception:
            continue
        ventana = c.iloc[-2:] if dias == 1 else c[c.index >= c.index[-1] - pd.Timedelta(days=dias)]
        paso = max(1, len(ventana) // 60)                   # Máximo ~60 puntos en la mini gráfica
        filas[s] = {"Cambio_%": (ventana.iloc[-1] / ventana.iloc[0] - 1) * 100,
                    "Grafica": [round(float(x), 4) for x in ventana.iloc[::paso]]}
    return filas


# ---------- Formularios de compra y venta ----------
@st.cache_data(ttl=600, show_spinner="Buscando el precio real...")
def _precio_en(simbolo, cuando):
    return activos.precio_en(simbolo, cuando)


@st.cache_data(ttl=3600, show_spinner=False)
def _tasa_cop_en(cuando):
    return activos.tasa_cop_en(cuando)


@st.cache_data(ttl=60, show_spinner="Consultando el precio del momento...")
def _precio_ahora(simbolo):
    return activos.precio_ahora(simbolo)


def _elegir_activo(cartera, venta, clave):
    """Compra: todos los activos con filtro por mercado. Venta: solo los que tienes, con la cantidad."""
    if venta:
        pos = cartera.posiciones(con_precio=False)
        if pos.empty:
            st.caption(":material/info: No tienes nada para vender.")
            return None, 0.0
        tengo = dict(zip(pos["Activo"], pos["Cantidad"]))
        s = st.selectbox("Activo que tienes", list(tengo), key=f"{clave}_act_v",
                         format_func=lambda x: f"{activos.etiqueta(x)} · tienes {tengo[x]:g}")
        return s, tengo[s]
    import nube
    ev = nube.EVENTO.get() if clave == "s" else None
    abiertos = None
    if ev:
        import cursos
        abiertos = set(cursos.mercados_hoy(ev))
        st.caption(":material/lock_open: Mercados abiertos esta semana en el evento: " +
                   ", ".join(activos.NOMBRE_MERCADO.get(m, m) for m in sorted(abiertos)))
    nombres = {v: k for k, v in activos.NOMBRE_MERCADO.items() if abiertos is None or k in abiertos}
    elegidos = st.pills("Filtrar por mercado (vacío = todos)", list(nombres), selection_mode="multi", key=f"{clave}_merc")
    opciones = [s for s in activos.ACTIVOS if (not elegidos or set(activos.mercados(s)) & {nombres[m] for m in elegidos})
                and (abiertos is None or set(activos.mercados(s)) & abiertos)]
    s = st.selectbox("Activo", opciones, format_func=activos.etiqueta, accept_new_options=True, index=None,
                     placeholder="Elige o escribe un símbolo", key=f"{clave}_act_c")
    return (activos.limpiar(s) if s else None), None


def formulario_real(cartera):
    """Registrar una compra o venta REAL: precio real a esa fecha y hora, aviso si te alejas más de 5%."""
    from datetime import datetime
    with st.container(border=True):
        st.markdown("**Registrar una compra o venta real**")
        tipo = st.segmented_control("Operación", ["Compra", "Venta"], default="Compra", required=True, key="r_tipo")
        activo, tengo = _elegir_activo(cartera, tipo == "Venta", "r")
        if not activo:
            return
        from formato import leer_numero, mostrar
        c1, c2 = st.columns(2)
        fecha = c1.date_input("Fecha", value="today", max_value="today", format="DD/MM/YYYY", key="r_fecha")
        hora = c2.time_input("Hora de Colombia (Bogotá)", value="now", step=300, key="r_hora", format="12h")
        cuando = datetime.combine(fecha, hora)
        moneda = activos.moneda(activo)
        c1, c2 = st.columns(2)
        en = c1.segmented_control("Moneda", ["COP", "US$"], default="COP" if moneda == "COP" else "US$",
                                  required=True, key="r_moneda", help="La app convierte con la tasa del dólar del "
                                                                      "día de la operación y guarda las dos monedas.")
        por = c2.segmented_control("Registrar por", ["Monto invertido", "Cantidad"], default="Monto invertido",
                                   required=True, key="r_por",
                                   help="Monto: escribes cuánto dinero pusiste y la app calcula la cantidad (o fracción).")
        tasa_dia = _tasa_cop_en(cuando)                                         # Pesos por dólar ese día
        a_usd = 1 / tasa_dia if moneda == "COP" else 1 / activos.tasa_usd(moneda)   # De la moneda del activo a US$
        factor = a_usd * (tasa_dia if en == "COP" else 1)                       # De la moneda del activo a la elegida
        real = _precio_en(activo, cuando)
        real_en = real * factor if real else None                               # Precio real YA en la moneda elegida
        if st.session_state.get("r_combo") != (activo, cuando, en) and real:    # Rellena con el precio real
            st.session_state["r_precio_txt"] = mostrar(real_en, 2 if en == "COP" else 4)
            st.session_state["r_combo"] = (activo, cuando, en)
        c1, c2 = st.columns(2)
        txt_precio = c1.text_input(f"Precio por unidad ({en})", key="r_precio_txt", live=True,
                                   help="Formato colombiano: punto de miles y coma decimal. Ej.: 1.685.191,96")
        try:
            precio = leer_numero(txt_precio)
            c1.caption(f"Leído: {mostrar(precio, 2 if en == 'COP' else 4)} {en}" if precio else "Escribe el precio")
        except ValueError as error:
            precio = None
            c1.error(str(error))
        etiqueta = f"Monto invertido ({en})" if por == "Monto invertido" else \
            "Cantidad" + (f" (tienes {mostrar(tengo, 4)})" if tengo else "")
        txt = c2.text_input(etiqueta, key=f"r_{'monto' if por == 'Monto invertido' else 'cant'}_txt", live=True,
                            placeholder="Ej.: 20.000" if por == "Monto invertido" else "Ej.: 0,5")
        try:
            valor = leer_numero(txt)
        except ValueError as error:
            valor = None
            c2.error(str(error))
        cantidad = (valor / precio if valor and precio else None) if por == "Monto invertido" else valor
        if por == "Monto invertido" and valor:
            c2.caption(f"Leído: {mostrar(valor, 2)} {en} → cantidad: {mostrar(cantidad, 6) if cantidad else '—'}")
        elif valor:
            c2.caption(f"Leído: {mostrar(valor, 6)} unidades")
        st.caption(f"Tasa del día: $ {mostrar(tasa_dia)} por dólar")
        if real:
            st.caption(f"Precio real a esa fecha y hora: {dinero(real_en, 'COP' if en == 'COP' else 'USD')}")
            if precio and abs(precio / real_en - 1) > 0.05:          # Se compara en la misma moneda
                st.warning(f"El precio que escribiste se aleja {abs(precio / real_en - 1) * 100:.1f}% del precio real "
                           f"({dinero(real_en, 'COP' if en == 'COP' else 'USD')}). Revísalo. Si escribiste lo que "
                           "invertiste, usa «Registrar por: Monto invertido».", icon=":material/warning:")
        nota = st.text_input("Nota (opcional)", key="r_nota", placeholder="Por ejemplo: comisión de Trii")
        if st.button("Guardar", icon=":material/save:", type="primary", key="r_guardar"):
            if not precio or not cantidad:
                st.error("Falta el precio o el monto/cantidad.")
                return
            usd = precio / (tasa_dia if en == "COP" else 1)
            error = cartera.registrar(activo, tipo.upper(), precio / factor, cantidad, cuando, nota,
                                      moneda, Tasa_COP=tasa_dia, Precio_COP=usd * tasa_dia, Precio_USD=usd)
            if error:
                st.error(error)
            else:
                for k in ("r_combo", "r_cant_txt", "r_monto_txt", "r_nota"):
                    st.session_state.pop(k, None)
                st.toast("Guardado")
                st.rerun()


AYUDA_ATR = ("ATR (rango verdadero promedio): cuánto se mueve el precio en un día normal, mirando las últimas 2 "
             "semanas. El stop sugerido es 2 × ATR: así un movimiento normal no te saca de la compra.")


def stop_personal(simbolo):
    """Regla base de 3% y, al lado, tu stop loss personal para este activo (con el sugerido por volatilidad)."""
    import avanzado
    clave = f"stop_pers_{simbolo}"
    actual = estrategia.stop_de(simbolo)
    personal = simbolo in estrategia.stops_personales()
    if f"{clave}_pendiente" in st.session_state:       # Del botón «Usar el sugerido», antes de dibujar la casilla
        st.session_state[clave] = st.session_state.pop(f"{clave}_pendiente")
    st.session_state.setdefault(clave, actual)
    try:
        sugerido = round(avanzado.stop_por_volatilidad(avanzado.atr(precios(simbolo))[1]), 1)
    except Exception:
        sugerido = None
    with st.container(border=True):
        st.markdown("**:material/shield: Tu stop loss personal**")
        fila = st.container(horizontal=True, vertical_alignment="bottom")
        fila.metric("Regla base", f"{estrategia.STOP_LOSS}%", help="El stop loss de la estrategia para todos los activos.")
        fila.number_input("Tu stop para este activo (%)", min_value=0.5, max_value=30.0, step=0.5, key=clave,
                          help="Se usa en tus compras de este activo (reales y simuladas): sugerencia de vender, "
                               "alertas y columna Stop. La regla de la estrategia no cambia.")
        if sugerido and fila.button(f"Usar el sugerido por volatilidad (ATR): {sugerido}%", key=f"{clave}_atr",
                                    help=AYUDA_ATR, icon=":material/speed:"):
            st.session_state[f"{clave}_pendiente"] = sugerido
            st.rerun()
        if fila.button("Guardar", key=f"{clave}_guardar", type="primary", icon=":material/save:"):
            estrategia.guardar_stop(simbolo, st.session_state[clave])
            st.toast(f"Stop personal de {simbolo}: {st.session_state[clave]}%")
            st.rerun()
        if personal and fila.button("Volver a la regla base", key=f"{clave}_base", icon=":material/undo:"):
            estrategia.guardar_stop(simbolo, None)
            st.session_state.pop(clave, None)
            st.rerun()
        st.caption(f"Ahora: **{actual:g}%** ({'personal' if personal else 'regla base'})."
                   + (f" Volatilidad: el sugerido es {sugerido}%." if sugerido else ""), help=AYUDA_ATR)


@st.dialog("Confirma la operación")
def confirmar_operacion(sim, tipo, activo, monto_cop=None, cantidad=None):
    """Ventana en lenguaje sencillo antes de cada compra o venta del simulador."""
    import comisiones
    precio, moneda, abierto = _precio_ahora(activo)
    tasa = sim.tasa_a_pesos(moneda)
    usd = sim.tasa_a_pesos("USD")
    if tipo == "Compra":
        costo = comisiones.costo(monto_cop, moneda)
        cantidad = (monto_cop - costo["total"]) / (precio * tasa)
        total_cop = monto_cop
        verbo = "comprar"
    else:
        bruto = precio * cantidad * tasa
        costo = comisiones.costo(bruto, moneda)
        total_cop = bruto - costo["total"]
        verbo = "vender"
    st.markdown(f"Vas a **{verbo} {numero(cantidad, 6).replace(',', 'X').replace('.', ',').replace('X', '.')} "
                f"unidades de {activo}**, {activos.que_es(activo)}, por "
                f"**{dinero(total_cop / usd)}** (**{pesos(total_cop)} COP**)"
                + (" en total" if tipo == "Compra" else " que te llegan") + ".")
    st.markdown(f"Comisión estimada: **{pesos(costo['comision'])} COP**"
                + (f" + spread cambiario **{pesos(costo['spread'])} COP**" if costo["spread"] else "") + ".")
    if tipo == "Venta" and total_cop <= 0:
        st.warning(f"La comisión es mayor que lo que vale esta venta: en vez de recibir dinero, pagarías "
                   f"{pesos(-total_cop)} COP. Con montos tan pequeños no conviene vender por separado.",
                   icon=":material/warning:")
    if not abierto:
        st.caption(":material/schedule: El mercado está cerrado: se usa el precio del último cierre.")
    import cursos
    ev = sim.evento()
    obligatoria = bool(ev and ev.get("bitacora_obligatoria"))
    st.markdown("**Bitácora:** ¿por qué " + ("compras" if tipo == "Compra" else "vendes") + "?"
                + (" *(obligatoria en este evento)*" if obligatoria else " *(opcional)*"))
    razon = st.pills("Razón", cursos.RAZONES, key="bitacora_razon", label_visibility="collapsed")
    frase = st.text_input("Una frase (opcional)", key="bitacora_frase", max_chars=200,
                          placeholder="Ej.: el petróleo subió por la OPEP")
    try:                                               # ¿Siguió la sugerencia de la app?
        r = analisis(activo)
        if tipo == "Compra":
            siguio = r["decision"] == "COMPRAR"
        else:
            import cartera as motor
            pos = sim.cartera.posiciones()
            g = pos.loc[pos["Activo"] == activo, "Ganancia_%"]
            siguio = motor.sugerencia(activo, float(g.iloc[0]) if len(g) and pd.notna(g.iloc[0]) else None)[0] == "Vender"
        st.caption(f":material/insights: La app {'sugería' if siguio else 'no sugería'} esta "
                   f"{'compra' if tipo == 'Compra' else 'venta'} hoy.")
    except Exception:
        siguio = None
    st.markdown("**¿Confirmas?**")
    fila = st.container(horizontal=True)
    if fila.button("Sí, confirmo", type="primary", icon=":material/check:"):
        nota = cursos.nota_bitacora(razon, frase, siguio) if (razon or frase or siguio is not None) else ""
        if obligatoria and not razon:
            st.error("En este evento la bitácora es obligatoria: elige una razón.")
            return
        if tipo == "Compra":
            _, error = sim.comprar(activo, monto_cop=monto_cop, nota=nota)
        else:
            _, error = sim.vender(activo, cantidad=cantidad, nota=nota)
        if error:
            st.error(error)
        else:
            st.session_state["operacion_hecha"] = f"{tipo} simulada hecha: {activo}"
            for k in ("bitacora_razon", "bitacora_frase"):   # La próxima bitácora empieza en blanco
                st.session_state.pop(k, None)
            st.rerun()
    if fila.button("Cancelar"):
        st.rerun()


def operar_simulador(sim, clave, activo=None, tengo=None, tipo="Compra"):
    """Comprar o vender en el simulador principal (mismo saldo e historial en toda la app), con calculadora de
    comisiones y ventana de confirmación. Si el activo es un índice, ofrece comprar su ETF."""
    import comisiones
    if st.session_state.get("operacion_hecha"):
        st.toast(st.session_state.pop("operacion_hecha"))
    if tipo == "Compra" and activos.tipo(activo) in ("índice", "bono"):
        etfs = activos.INDICE_ETF.get(activo)
        if not etfs:
            st.caption(f":material/info: {activo} es {activos.que_es(activo)}. No tiene un ETF asociado en la app.")
            return
        st.caption(f":material/info: {activos.nombre(activo)} no se compra directamente: se compra su ETF, que lo copia.")
        activo = st.segmented_control("Comprar a través de", etfs, default=etfs[0], required=True, key=f"{clave}_etf",
                                      format_func=activos.etiqueta)
    precio, moneda, abierto = _precio_ahora(activo)
    st.metric(f"Precio del momento de {activo}", dinero(precio, moneda),
              "mercado abierto" if abierto else "mercado cerrado: último cierre", delta_color="off")
    s = sim.resumen()
    if tipo == "Compra":
        en = st.segmented_control("Monto en", ["COP", "US$"], default="COP", required=True, key=f"{clave}_moneda")
        tasa = s["tasa"]
        sugerido = min(s["disponible"], s["total"] * sim.FRACCION)
        monto = st.number_input(f"Monto a invertir ({en})", min_value=0.0,
                                value=float(max(sugerido, 0) / (tasa if en == "US$" else 1)),
                                step=5_000.0 if en == "COP" else 5.0, format="%.0f" if en == "COP" else "%.2f",
                                key=f"{clave}_monto_{en}")
        monto_cop = monto * (tasa if en == "US$" else 1)
        disponible = s["disponible"] / (tasa if en == "US$" else 1)
        costo = comisiones.costo(monto_cop, moneda)
        subida = comisiones.subida_para_cubrir(monto_cop, moneda)
        with st.container(border=True):
            st.markdown("**:material/calculate: Calculadora de comisiones**")
            fila = st.container(horizontal=True)
            fila.metric("Comisión de compra", pesos(costo["comision"]) + " COP",
                        f"+ spread {pesos(costo['spread'])}" if costo["spread"] else None, delta_color="off")
            fila.metric("Comisión de venta (aprox.)", pesos(comisiones.costo(monto_cop, moneda)["total"]) + " COP")
            fila.metric("Tiene que subir solo para empatar", f"{subida:.2f}%" if subida is not None else "No alcanza",
                        help="Cuánto tiene que subir el activo para recuperar las comisiones de compra y de venta, "
                             "con este monto. Por debajo de eso, aunque suba, pierdes.")
            if subida is not None and subida > estrategia.OBJETIVO:
                st.warning(f"Con este monto, las comisiones se comen más que el objetivo de +{estrategia.OBJETIVO}%. "
                           "Invierte un monto mayor o no compres.", icon=":material/warning:")
            st.caption("Tarifas de Trii editables en «Comisiones de Trii» (pantalla Simulador).")
        if st.button(f"Comprar {activo}", icon=":material/shopping_cart:", type="primary", key=f"{clave}_comprar"):
            if monto_cop > s["disponible"] + 1e-6:
                st.error(f"Saldo insuficiente: tienes {pesos(disponible) + ' COP' if en == 'COP' else dinero(disponible)} "
                         "disponibles.")
            elif subida is None:
                st.error(f"El monto no alcanza ni para la comisión ({pesos(costo['total'])} COP).")
            else:
                confirmar_operacion(sim, "Compra", activo, monto_cop=monto_cop)
    else:
        cantidad = st.number_input(f"Cantidad (tienes {tengo:g})", min_value=0.0, value=float(tengo), format="%.6f",
                                   key=f"{clave}_cant")
        if st.button(f"Vender {activo}", icon=":material/sell:", type="primary", key=f"{clave}_vender"):
            if cantidad > tengo + 1e-9:
                st.error(f"No tienes tanto: tienes {tengo:g} unidades.")
            elif cantidad <= 0:
                st.error("Escribe cuánto quieres vender.")
            else:
                confirmar_operacion(sim, "Venta", activo, cantidad=cantidad)


def formulario_simulador(sim):
    """Comprar o vender en el SIMULADOR al precio real del momento."""
    with st.container(border=True):
        cab = st.container(horizontal=True, vertical_alignment="center")
        cab.markdown("**Comprar o vender**")
        cab.badge("SIMULACIÓN", icon=":material/science:", color="violet")
        tipo = st.segmented_control("Operación", ["Compra", "Venta"], default="Compra", required=True, key="s_tipo")
        activo, tengo = _elegir_activo(sim.cartera, tipo == "Venta", "s")
        if activo:
            operar_simulador(sim, "s", activo, tengo, tipo)


def compra_rapida(simbolo):
    """Botón rápido al final de la página del activo: compra o vende en el simulador principal."""
    import simulador
    with st.container(border=True):
        cab = st.container(horizontal=True, vertical_alignment="center")
        cab.markdown(f"#### :material/bolt: Comprar o vender {simbolo} en el simulador")
        cab.badge("SIMULACIÓN · mismo saldo e historial del Simulador", icon=":material/science:", color="violet")
        tengo = simulador.cartera.tengo(simbolo)
        ev = simulador.evento()
        if ev:
            import cursos
            st.caption(f":material/event: Estás usando el simulador del evento **{ev['nombre']}**.")
            if not set(activos.mercados(simbolo)) & set(cursos.mercados_hoy(ev)) and tengo <= 0:
                st.caption(":material/lock: Este activo no está abierto esta semana en tu evento.")
                return
        tipo = st.segmented_control("Operación", ["Compra", "Venta"] if tengo > 0 else ["Compra"], default="Compra",
                                    required=True, key=f"rapida_tipo_{simbolo}")
        operar_simulador(simulador, f"rapida_{simbolo}", simbolo, tengo, tipo)


# ---------- Tablas y gráfica de una cartera ----------
def tabla_posiciones(pos, simulacion=False):
    vista = pos[["Activo", "Nombre", "Moneda", "Cantidad", "Precio_compra", "Precio_actual", "Ganancia_papel",
                 "Ganancia_%", "Stop", "Objetivo", "Sugerencia", "Motivo"]]

    def color(v):
        return "" if pd.isna(v) else f"color: {VERDE if v >= 0 else ROJO}; font-weight: 600"

    def accion(v):
        fondo = "rgba(220,38,38,0.15)" if v == "Vender" else "rgba(5,150,105,0.15)"
        return f"background-color: {fondo}; font-weight: 600"

    evento = st.dataframe(
                 vista.style.map(color, subset=["Ganancia_papel", "Ganancia_%"]).map(accion, subset=["Sugerencia"]),
                 hide_index=True, on_select="rerun", selection_mode="single-cell",
                 key=f"posiciones_{'sim' if simulacion else 'real'}",
                 alt="Compras abiertas" + (" (simulación)" if simulacion else ""),
                 column_config={"Moneda": st.column_config.TextColumn(help="Moneda de los precios de esa fila."),
                                "Precio_compra": st.column_config.NumberColumn("Precio de compra", format="%,.2f"),
                                "Precio_actual": st.column_config.NumberColumn("Precio actual", format="%,.2f"),
                                "Ganancia_papel": st.column_config.NumberColumn("Ganancia en papel", format="%+,.2f"),
                                "Ganancia_%": st.column_config.NumberColumn("Ganancia %", format="%+.2f%%"),
                                "Stop": st.column_config.NumberColumn("Stop loss", format="%,.2f"),
                                "Objetivo": st.column_config.NumberColumn(format="%,.2f"),
                                "Sugerencia": st.column_config.TextColumn(help="Toca «Mantener» o «Vender» para ver por qué")})
    st.caption("Toca **Mantener** o **Vender** para ver la explicación; toca otra celda para abrir el activo.")
    if evento.selection.cells:
        fila, columna = evento.selection.cells[0]
        if columna == "Sugerencia":
            explicar_sugerencia(pos.iloc[fila])
        else:
            ir_a_activo(pos["Activo"].iloc[fila])


def predicciones_cartera(cartera, clave, etiqueta=""):
    """Predicción a 5 días y abanico de Monte Carlo de toda la cartera junta, y de un activo a elegir."""
    import montecarlo
    pos = cartera.posiciones()
    if pos.empty:
        return
    contar_uso("predicciones_cartera")
    st.markdown(f"#### :material/insights: Predicciones {etiqueta}")
    vista = st.segmented_control("Ver", ["Todos mis activos juntos", "Un activo"], default="Todos mis activos juntos",
                                 required=True, key=f"pred_vista_{clave}")
    if vista == "Un activo":
        s = st.selectbox("Activo", list(pos["Activo"]), format_func=activos.etiqueta, key=f"pred_activo_{clave}")
        abanico(s)
        return
    dias = 20
    total, filas = None, []
    for i, p in enumerate(pos.itertuples()):
        cierre = precios(p.Activo)["Cierre"]
        m = montecarlo.caminos(cierre, dias, n=1000, semilla=i) * p.Cantidad / tasa_usd(p.Moneda)   # Valor en US$
        total = m if total is None else total + m
        fin = m[:, -1]
        filas.append({"Activo": p.Activo, "Valor hoy (US$)": m[0, 0], "Mediana a 20 días": float(np.median(fin)),
                      "Escenario 10%": float(np.percentile(fin, 10)), "Escenario 90%": float(np.percentile(fin, 90)),
                      "Caminos que suben": f"{int((fin > m[0, 0]).mean() * 100)}%"})
    fechas = [pd.Timestamp.now().normalize()] + list(pd.bdate_range(pd.Timestamp.now() + pd.Timedelta(days=1), periods=dias))
    bandas, r = montecarlo.resumen(total, fechas)
    fig = go.Figure()
    for camino in total[:100]:
        fig.add_trace(go.Scatter(x=fechas, y=camino, mode="lines", showlegend=False, hoverinfo="skip",
                                 line=dict(width=0.8, color="rgba(0,255,156,0.28)" if camino[-1] > camino[0]
                                           else "rgba(255,56,100,0.28)")))
    for col, nombre in [("P10", "Escenario 10%"), ("P90", "Escenario 90%")]:
        fig.add_trace(go.Scatter(x=fechas, y=bandas[col], name=nombre, line=dict(color=NARANJA, width=1.6, dash="dash")))
    fig.add_trace(go.Scatter(x=fechas, y=bandas["Mediana"], name="Mediana", line=dict(color="#FFFFFF", width=3)))
    fig.update_yaxes(title_text="Valor de la cartera (US$)", tickprefix="US$ ")
    st.plotly_chart(estilo(fig, 380), width="stretch", key=f"abanico_cartera_{clave}")
    fila = st.container(horizontal=True)
    fila.metric("Valor hoy", dinero(total[0, 0]))
    fila.metric("Mediana en 20 días", dinero(r["mediana"]), f"{(r['mediana'] / total[0, 0] - 1) * 100:+.1f}%")
    fila.metric("Rango (10% a 90%)", f"{dinero(r['p10'])} – {dinero(r['p90'])}")
    fila.metric("Caminos que suben", f"{r['suben'] / r['n'] * 100:.0f}%")
    st.dataframe(pd.DataFrame(filas), hide_index=True, alt="Predicción por activo",
                 column_config={c: st.column_config.NumberColumn(format="US$ %,.2f") for c in
                                ["Valor hoy (US$)", "Mediana a 20 días", "Escenario 10%", "Escenario 90%"]})
    st.caption(EXPLICACION_BANDAS + " Cada activo se simula por separado (shortcut: no se tiene en cuenta que suelen "
               "moverse juntos, así que el rango real puede ser un poco más ancho).")


@st.cache_resource(show_spinner=False)
def _flujo(simbolo):
    import binance
    return binance.Flujo(simbolo)                 # Una sola conexión WebSocket por cripto, compartida


def cripto_en_vivo(simbolo):
    """Gráfica en tiempo real (WebSocket público de Binance), refrescada cada 1,5 segundos."""
    st.markdown("#### :material/bolt: En vivo (Binance)")
    flujo = _flujo(simbolo)

    @st.fragment(run_every=1.5)
    def grafica():
        datos = list(flujo.datos)
        if not datos:
            st.caption("Conectando con Binance..." + (f" ({flujo.error})" if flujo.error else ""))
            return
        t = pd.DataFrame(datos, columns=["Hora", "Precio"])
        t["Hora"] = pd.to_datetime(t["Hora"], unit="s", utc=True).dt.tz_convert("America/Bogota").dt.tz_localize(None)
        t = t.groupby(t["Hora"].dt.floor("s")).last().reset_index(drop=True)      # Un punto por segundo
        ultimo = t["Precio"].iloc[-1]
        cambio = (ultimo / t["Precio"].iloc[0] - 1) * 100
        fila = st.container(horizontal=True)
        fila.metric("Precio ahora", f"US$ {ultimo:,.2f}", f"{cambio:+.3f}% desde que abriste esta página")
        fig = go.Figure(go.Scatter(x=t["Hora"], y=t["Precio"], mode="lines+markers", marker=dict(size=4),
                                   line=dict(color=VERDE if cambio >= 0 else ROJO, width=2),
                                   hovertemplate="%{x|%I:%M:%S %p}: US$ %{y:,.2f}<extra></extra>"))
        evento = st.plotly_chart(estilo(fig, 280, leyenda=False), width="stretch", key=f"vivo_{simbolo}",
                                 on_select="rerun", selection_mode="points")
        puntos = evento.selection.points if evento and evento.selection else []
        if puntos:
            fila.metric("Precio en el punto que tocaste", f"US$ {puntos[0]['y']:,.2f}",
                        pd.Timestamp(puntos[0]["x"]).strftime("%I:%M:%S %p"), delta_color="off")
        st.caption("Cada punto es un segundo de operaciones reales en Binance. Toca un punto para ver su precio exacto. "
                   "Las señales y sugerencias siguen siendo diarias; las compras y ventas del simulador en cripto usan "
                   "este precio en vivo.")

    grafica()


EXPLICACION_BANDAS = ("Las líneas punteadas del 10% y el 90% son los escenarios extremos y poco probables: solo 1 de cada "
                      "10 caminos termina por debajo de la del 10% y 1 de cada 10 por encima de la del 90%. La mediana "
                      "(línea blanca) es el caso más típico: la mitad de los caminos termina arriba y la mitad abajo.")


def editor_operaciones(cartera, clave):
    """Tabla para corregir o eliminar compras y ventas."""
    historial = cartera.con_resultado()
    if historial.empty:
        return
    st.markdown("**Historial: editar o eliminar compras y ventas**")
    st.caption("Toca una celda para corregirla. Para eliminar, marca la casilla de la izquierda de la fila y toca la "
               "basura. Luego «Guardar cambios». La columna Resultado (ganancia de cada venta) se calcula sola.")
    editada = st.data_editor(
        historial, num_rows="dynamic", hide_index=True, key=f"editor_{clave}", disabled=["Resultado"],
        alt="Historial editable",
        column_config={"Fecha": st.column_config.DatetimeColumn(format="DD/MM/YYYY hh:mm a", required=True),
                       "Activo": st.column_config.TextColumn(required=True),
                       "Tipo": st.column_config.SelectboxColumn(options=["COMPRA", "VENTA"], required=True),
                       "Precio": st.column_config.NumberColumn(min_value=0.0, format="%.4f", required=True),
                       "Cantidad": st.column_config.NumberColumn(min_value=0.0, format="%.4f", required=True),
                       "Resultado": st.column_config.NumberColumn("Resultado (US$)", format="%+.2f")})
    botones = st.container(horizontal=True)
    if botones.button("Guardar cambios", icon=":material/save:", type="primary", key=f"guardar_{clave}"):
        error = cartera.reemplazar(editada.drop(columns="Resultado"))
        if error:
            st.error(error)
        else:
            st.toast("Cambios guardados")
            st.rerun()
    if botones.button("Descartar cambios", icon=":material/undo:", key=f"descartar_{clave}"):
        st.session_state.pop(f"editor_{clave}", None)
        st.rerun()


def grafica_cartera(cartera, clave, etiqueta=""):
    """Valor de cada activo y del total (US$) + precio de un activo con compra, stop y objetivo."""
    dias = st.segmented_control("Periodo", [1, 8, 15, 30, 60, 90, 180, 360], default=30, required=True,
                                format_func=lambda d: f"{d} día" + ("s" if d > 1 else ""), key=f"per_{clave}")
    valores = cartera.valor_historico(max(dias, 3))
    if valores.empty:
        st.caption("Todavía no hay datos para la gráfica.")
        return
    ops = cartera.leer()
    en_periodo = ops[ops["Fecha"] >= pd.Timestamp.now() - pd.Timedelta(days=dias)]
    monto = en_periodo["Precio"] * en_periodo["Cantidad"]
    neto = monto.where(en_periodo["Tipo"] == "COMPRA", -monto).sum()
    ganancia = valores["Total"].iloc[-1] - valores["Total"].iloc[0] - neto
    st.metric(f"Ganancia o pérdida en {dias} días {etiqueta}", dinero(ganancia),
              help="Cambio del valor total menos lo que compraste y más lo que vendiste en el periodo.")
    fig = go.Figure()
    for i, columna in enumerate([c for c in valores.columns if c != "Total"][:len(PALETA) - 1]):
        fig.add_trace(go.Scatter(x=valores.index, y=valores[columna], name=columna,
                                 line=dict(color=PALETA[i + 1], width=1.6), hovertemplate="US$ %{y:,.2f}"))
    fig.add_trace(go.Scatter(x=valores.index, y=valores["Total"], name="Total", line=dict(color=AZUL, width=3),
                             hovertemplate="US$ %{y:,.2f}"))
    fig.update_yaxes(title_text="Valor (US$)", tickprefix="US$ ")
    st.plotly_chart(estilo(fig, 320), width="stretch", key=f"valor_{clave}")

    pos = cartera.posiciones(con_precio=False)
    if pos.empty:
        return
    s = st.selectbox("Precio de", list(pos["Activo"]), format_func=activos.etiqueta, key=f"precio_de_{clave}")
    p = pos[pos["Activo"] == s].iloc[0]
    c = precios(s)["Cierre"]
    c = c[c.index >= c.index[-1] - pd.Timedelta(days=max(dias, 8))]
    fig = go.Figure(go.Scatter(x=c.index, y=c, name="Precio", line=dict(color=AZUL, width=2),
                               hovertemplate="US$ %{y:,.2f}"))
    for nivel, color, texto in [(p["Precio_compra"], GRIS, "compra"), (p["Stop"], ROJO, "stop loss"),
                                (p["Objetivo"], VERDE, "objetivo")]:
        fig.add_hline(y=nivel, line=dict(color=color, dash="dash", width=1.5),
                      annotation_text=f"{texto} US$ {nivel:,.2f}", annotation_position="top left")
    compras = ops[(ops["Activo"] == s) & (ops["Tipo"] == "COMPRA")]
    fig.add_trace(go.Scatter(x=compras["Fecha"], y=compras["Precio"], mode="markers", name="Compra",
                             marker=dict(color=NARANJA, size=12, symbol="triangle-up", line=dict(color="white", width=1.5)),
                             hovertemplate="Compra %{x|%d/%m %I:%M %p}: US$ %{y:,.2f}<extra></extra>"))
    fig.update_yaxes(title_text="Precio (US$)")
    st.plotly_chart(estilo(fig, 300), width="stretch", key=f"precio_{clave}")


# ---------- Análisis avanzados (secciones cerradas; cada una calcula solo cuando se abre) ----------
def _seccion_atr(simbolo, clave):
    import avanzado
    valor, pct = avanzado.atr(precios(simbolo))
    stop = avanzado.stop_por_volatilidad(pct)
    fila = st.container(horizontal=True)
    fila.metric("Movimiento diario normal (ATR)", numero(valor), f"{pct:.2f}% del precio", delta_color="off")
    fila.metric("Stop loss de la regla", f"{estrategia.STOP_LOSS}%", "fijo", delta_color="off")
    fila.metric("Stop sugerido por volatilidad", f"{stop:.1f}%", "2 × ATR", delta_color="off")
    if stop > estrategia.STOP_LOSS * 1.2:
        st.caption(f"Este activo se mueve mucho: con el stop fijo de {estrategia.STOP_LOSS}% es fácil que te saque por un "
                   "movimiento normal. Si decides usar un stop más amplio, compra menos cantidad para arriesgar lo mismo.")
    elif stop < estrategia.STOP_LOSS * 0.8:
        st.caption(f"Este activo se mueve poco: el stop fijo de {estrategia.STOP_LOSS}% le da bastante espacio.")
    else:
        st.caption(f"El stop fijo de {estrategia.STOP_LOSS}% está en línea con lo que se mueve este activo.")
    st.caption("La regla no cambia sola: el stop sugerido es informativo. Si quieres cambiarla, pídelo.")


def _seccion_sr(simbolo, clave):
    import avanzado
    p = precios(simbolo)
    soportes, resistencias = avanzado.soportes_resistencias(p)
    d = p.tail(250)
    fig = go.Figure(go.Scatter(x=d.index, y=d["Cierre"], name="Precio", line=dict(color=AZUL, width=1.6)))
    for nivel, veces in soportes:
        fig.add_hline(y=nivel, line=dict(color=VERDE, dash="dash", width=1 + veces * 0.5),
                      annotation_text=f"Soporte {numero(nivel)} ({veces}×)", annotation_position="bottom left")
    for nivel, veces in resistencias:
        fig.add_hline(y=nivel, line=dict(color=ROJO, dash="dash", width=1 + veces * 0.5),
                      annotation_text=f"Resistencia {numero(nivel)} ({veces}×)", annotation_position="top left")
    st.plotly_chart(estilo(fig, 380, leyenda=False), width="stretch", key=f"sr_{clave}")
    precio = float(d["Cierre"].iloc[-1])
    if soportes:
        st.caption(f"Soporte más cercano: {numero(soportes[0][0])} ({(soportes[0][0] / precio - 1) * 100:+.1f}%).")
    if resistencias:
        st.caption(f"Resistencia más cercana: {numero(resistencias[0][0])} "
                   f"({(resistencias[0][0] / precio - 1) * 100:+.1f}%).")
    st.caption("Línea más gruesa = nivel tocado más veces en el último año.")


CARA = {"Positivo": "😊 Positivo", "Negativo": "😞 Negativo", "Neutro": "😐 Neutro"}


def _seccion_sent(simbolo, clave):
    import avanzado
    t = avanzado.noticias_semana(simbolo, activos.noticias(simbolo))
    if t.empty:
        st.caption("No hay titulares guardados de esta semana. Se actualizan solos con las revisiones programadas.")
        return
    pos, neg, neu, _ = avanzado.balance(t["Titular"])
    izq, der = st.columns([3, 1])
    vista = t.sort_values("Fecha", ascending=False)[["Fecha", "Titular", "Fuente", "URL"]].copy()
    vista.insert(1, "Sentimiento", vista["Titular"].map(lambda x: CARA[avanzado.sentimiento(x)]))
    izq.dataframe(vista, hide_index=True, alt="Titulares de la semana con su sentimiento",
                  column_config={"Fecha": st.column_config.DatetimeColumn(format="DD/MM HH:mm"),
                                 "URL": st.column_config.LinkColumn("Leer", display_text="abrir")})
    with der.container(border=True):
        st.markdown("**Balance de la semana**")
        cara, texto = ("😊", "Pesan más las positivas") if pos > neg else             ("😞", "Pesan más las negativas") if neg > pos else ("😐", "Empate")
        st.markdown(f"<div style='font-size:3.5rem;text-align:center'>{cara}</div>", unsafe_allow_html=True)
        st.markdown(f"**{texto}**", text_alignment="center")
        st.caption(f"😊 {pos} positivas · 😞 {neg} negativas · 😐 {neu} neutras", text_alignment="center")
    st.caption("Se cuenta con palabras de subida y de bajada, así que a veces se equivoca (no entiende ironías).")


def _carteras():
    """{'Mis activos': posiciones, 'Simulador': posiciones} con las compras abiertas (solo lectura)."""
    import mis_activos
    import simulador
    carteras = {"Simulador": simulador.cartera.posiciones()}
    if puede("mis_activos"):                               # Mis activos solo lo ve el superadmin
        carteras = {"Mis activos": mis_activos.cartera.posiciones(), **carteras}
    return carteras


def _seccion_corr(simbolo, clave):
    import avanzado
    simbolos = list(dict.fromkeys([simbolo] + [s for pos in _carteras().values() for s in pos.get("Activo", [])]))
    if len(simbolos) < 2:
        st.caption("Necesitas al menos un activo comprado (real o simulado) para comparar.")
        return
    m = avanzado.correlacion({s: precios(s)["Cierre"] for s in simbolos})
    fig = go.Figure(go.Heatmap(z=m.values, x=m.columns, y=m.index, zmin=-1, zmax=1, text=m.round(2).values,
                               texttemplate="%{text}", colorscale=[[0, ROJO], [0.5, "#0B1220"], [1, AZUL]]))
    st.plotly_chart(estilo(fig, 160 + 40 * len(simbolos), leyenda=False), width="stretch", key=f"corr_{clave}")
    parecidos = avanzado.pares_parecidos(m)
    for a, b, c in parecidos:
        st.warning(f"{a} y {b} se mueven casi igual (correlación {c:.2f}). Tener los dos no reparte el riesgo.",
                   icon=":material/warning:")
    if not parecidos:
        st.caption("Ningún par se mueve casi igual (todos por debajo de 0,8): el riesgo está repartido.")
    st.caption(f"Incluye {activos.nombre(simbolo)} y tus compras abiertas, reales y simuladas. Retornos diarios del "
               "último año.")


def _seccion_var(simbolo, clave):
    import avanzado
    tasa = tasa_usd("COP")
    for nombre, pos in _carteras().items():
        if pos.empty:
            st.caption(f"{nombre}: sin compras abiertas.")
            continue
        valores = {p.Activo: float(p.Valor_USD) for p in pos.itertuples() if pd.notna(p.Valor_USD)}
        var = avanzado.var_historico(valores, {s: precios(s)["Cierre"] for s in valores})
        total = sum(valores.values())
        fila = st.container(horizontal=True)
        fila.metric(f"{nombre}: valor hoy", dinero(total), dinero(total * tasa, "COP"), delta_color="off")
        fila.metric("Pérdida en un día malo (95%)", dinero(var),
                    f"{dinero(var * tasa, 'COP')} · {var / total * 100:.1f}% del total" if total else None,
                    delta_color="off")
    st.caption("Ejemplo: si dice US$ 10, en 19 de cada 20 días perderías menos de US$ 10. El día 20 puede ser peor.")


SECCIONES_AVANZADAS = [("Volatilidad (ATR) y stop loss sugerido", ":material/speed:", "atr", _seccion_atr),
                       ("Soportes y resistencias", ":material/align_vertical_center:", "sr", _seccion_sr),
                       ("Sentimiento de noticias de la semana", ":material/newspaper:", "sent", _seccion_sent),
                       ("Correlación con tus activos", ":material/hub:", "corr", _seccion_corr),
                       ("Valor en riesgo (VaR) de tus portafolios", ":material/shield:", "var", _seccion_var)]


def analisis_avanzado(simbolo, clave):
    """Cinco análisis extra en secciones cerradas. Cada una solo calcula cuando la abres (así la página no se pone lenta)."""
    st.markdown("#### :material/biotech: Análisis avanzados",
                help="Información extra para decidir. Ninguno cambia la regla de compra.")
    for titulo, icono, id_, funcion in SECCIONES_AVANZADAS:
        seccion = st.expander(titulo, icon=icono, key=f"av_{id_}_{clave}", on_change="rerun")
        if seccion.open:
            with seccion:
                boton_que_es(st, id_, f"{id_}_{clave}_{simbolo}")
                try:
                    funcion(simbolo, f"{clave}_{simbolo}")
                except Exception as error:
                    st.caption(f"No se pudo calcular para {simbolo}: {error}")


# ---------- Diario de errores ----------
def diario_errores(cartera, nombre, clave):
    """Pide en un clic la razón de cada venta con pérdida y muestra los errores más repetidos."""
    import errores
    p = errores.pendientes(cartera, nombre)
    rep = errores.mas_repetidos()
    if p.empty and rep.empty:
        return
    with st.container(border=True):
        st.markdown(f"#### :material/menu_book: Diario de errores · {nombre}")
        for i, v in p.iterrows():
            st.markdown(f"**{v['Activo']}** se vendió el {pd.Timestamp(v['Fecha']):%d/%m/%Y} con pérdida de "
                        f":red[{v['Resultado']:,.2f}] ({v['Moneda'] or 'USD'}). ¿Qué pasó?")
            razon = st.pills("Razón", errores.RAZONES, key=f"err_{clave}_{i}", label_visibility="collapsed")
            if razon:
                errores.anotar(v["Fecha"], nombre, v["Activo"], v["Resultado"], razon)
                st.toast("Anotado en tu diario de errores")
                st.rerun()
        if len(rep):
            st.markdown("**Tus errores más repetidos**")
            st.bar_chart(rep.set_index("Razón")["Veces"], horizontal=True, height=60 + 32 * len(rep),
                         alt="Errores más repetidos")
            st.caption(f"El que más se repite: **{rep['Razón'].iloc[0]}** ({rep['Veces'].iloc[0]} veces). "
                       "Saberlo ayuda a no repetirlo.")
