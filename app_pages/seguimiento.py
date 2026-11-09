# Seguimiento: listas por mercado, Dividendos y Mis activos (real)

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import activos
import consejo
import dividendos
import mis_activos
import ui

st.title("Seguimiento")
tabla = ui.tabla_ranking()
FILTRO = {"Estados Unidos": "eeuu", "Nasdaq": "nasdaq", "Petróleo": "petróleo", "Oro": "oro",
          "Materias primas": "materias", "Colombia": "colombia", "Latinoamérica": "latam", "Europa": "europa",
          "Asia": "asia", "Cripto": "cripto", "Futuros": "futuros", "Divisas": "divisas", "ETFs": "etf", "Bonos": "bonos"}
FILTRO = {n: m for n, m in FILTRO.items() if activos.mercado_activo(m)}   # Mercados apagados no salen
NOMBRES = ["Todo"] + list(FILTRO) + ["Bolsas", "Dividendos", "Semanal"] + (["Mis activos"] if ui.puede("mis_activos") else [])
NOTA_MERCADO = {
    "futuros": "Los futuros son contratos para expertos: se compran con apalancamiento y pueden hacer perder más de lo "
               "invertido. No se compran en Trii. Úsalos para mirar hacia dónde va cada mercado.",
    "cripto": "Las criptomonedas operan 24 horas, los 7 días, y se mueven mucho más que las acciones. No están en Trii.",
    "asia": "Las bolsas de Asia abren de noche en hora de Bogotá. Los ADR (en Nueva York) se compran en horario de "
            "EE.UU.; las acciones locales, en eToro (algunas) o solo para mirar.",
    "colombia": "Precios en pesos (COP) y su equivalente en dólares. Se compran en Trii (Bolsa de Colombia). Los ADR "
                "(CIB, AVAL, EC) cotizan en dólares en Nueva York. Incluye el café y el petróleo, que mueven la economía "
                "colombiana (el carbón, el níquel y las flores no tienen datos diarios gratuitos).",
    "europa": "Las bolsas de Europa abren de madrugada en hora de Bogotá (Londres, Frankfurt y París: 3:00 a 11:30 a.m. "
              "aprox.). Las acciones de Londres cotizan en peniques (GBp): 100 peniques = 1 libra.",
    "latam": "Brasil, México, Chile, Perú y Argentina (Colombia tiene su propia pestaña). Casi todas se compran como "
             "ADR en Nueva York, en dólares. Chile, Perú y Argentina no tienen su índice en Yahoo: se usan sus ETFs "
             "(ECH, EPU y ARGT).",
    "divisas": "El precio de una moneda frente a otra. USD/COP = cuántos pesos vale un dólar: si sube, todo lo que "
               "compras en dólares te cuesta más pesos. No se compran en Trii; sirven para entender el mercado.",
    "eeuu": "Los índices no se compran directamente: se compran a través de sus ETF (SPY copia al S&P 500, QQQ al Nasdaq).",
}


def color_cambio(v):
    return "" if pd.isna(v) else f"color: {ui.VERDE if v >= 0 else ui.ROJO}; font-weight: 600"


def color_decision(v):
    fondo = {"🟢 Comprar": "rgba(5,150,105,0.18)", "🔴 No comprar": "rgba(220,38,38,0.15)"}.get(v, "rgba(100,116,139,0.15)")
    return f"background-color: {fondo}; font-weight: 600"


def lista(t, clave):
    periodo = st.segmented_control("Periodo del cambio y la mini gráfica", list(ui.PERIODOS_LISTA), default="1 día",
                                   required=True, key=f"periodo_lista_{clave}")
    buscar = st.text_input("Buscar", placeholder="Escribe un nombre o símbolo", key=f"buscar_{clave}",
                           label_visibility="collapsed")
    if buscar:
        b = buscar.lower()
        t = t[t["Activo"].str.lower().str.contains(b, regex=False) | t["Nombre"].str.lower().str.contains(b, regex=False)]
    datos = ui.tabla_periodo(ui.PERIODOS_LISTA[periodo], ui.ranking.ARCHIVO.stat().st_mtime)
    vista = t[["Sector", "Activo", "Nombre", "Precio", "Moneda", "Probabilidad_%", "Decision"]].copy()
    vista.insert(5, "Precio_USD", [p / ui.tasa_usd(m) for p, m in zip(vista["Precio"], vista["Moneda"])])
    vista.insert(6, "Cambio_%", vista["Activo"].map(lambda s: datos.get(s, {}).get("Cambio_%")))
    vista.insert(7, "Grafica", vista["Activo"].map(lambda s: datos.get(s, {}).get("Grafica", [])))
    vista["Decision"] = vista["Decision"].map(ui.texto_decision)
    st.caption(ui.LEYENDA_TABLA)
    evento = st.dataframe(
        vista.style.map(color_cambio, subset=["Cambio_%"]).map(color_decision, subset=["Decision"]),
        hide_index=True, on_select="rerun", selection_mode=["single-row", "single-cell"], key=f"lista_{clave}",
        height=min(38 * len(vista) + 40, 640), alt=f"Activos de {clave}",
        column_config={"Sector": st.column_config.TextColumn("Sector", width="medium", help=ui.AYUDA_SECTOR),
                       "Precio": st.column_config.NumberColumn("Precio", format="%,.2f",
                                                               help="En la moneda en que cotiza (ver columna Moneda)."),
                       "Moneda": st.column_config.TextColumn(width="small", help="COP = pesos colombianos, USD = "
                                                             "dólares, JPY = yenes, KRW = wones, HKD = dólares de Hong Kong..."),
                       "Precio_USD": st.column_config.NumberColumn("Precio US$", format="US$ %,.2f",
                                                                   help="Convertido a dólares con la tasa de hoy."),
                       "Cambio_%": st.column_config.NumberColumn(f"Cambio {periodo}", format="%+.2f%%"),
                       "Grafica": st.column_config.LineChartColumn(f"Últimos {periodo}", color="auto"),
                       "Probabilidad_%": st.column_config.ProgressColumn("Probabilidad", format="%.1f%%",
                                                                         min_value=0, max_value=100,
                                                                         help="Probabilidad de subida a 5 días."),
                       "Decision": st.column_config.TextColumn("Decisión", help="🟢 Comprar · 🔴 No comprar · ⚪ Esperar")})
    st.caption(f"{len(vista)} activos · {(t['Decision'] == 'COMPRAR').sum()} dicen COMPRAR.")
    if evento.selection.cells:                       # Tocó una celda: la decisión explica, lo demás abre el activo
        fila, columna = evento.selection.cells[0]
        if columna == "Decision":
            ui.explicar_decision(ui.analisis(vista["Activo"].iloc[fila]))
        else:
            ui.ir_a_activo(vista["Activo"].iloc[fila])
    elif evento.selection.rows:
        ui.ir_a_activo(vista["Activo"].iloc[evento.selection.rows[0]])


def cabecera_mercado(mercado):
    """Tendencia del mercado, nota, estacionalidad y calendario."""
    ref = activos.REFERENCIAS_MERCADO[mercado]
    ui.consejo_tendencia(ref, activos.NOMBRE_MERCADO[mercado])
    if mercado in NOTA_MERCADO:
        st.caption(f":material/info: {NOTA_MERCADO[mercado]}")
    with st.expander(f"Estacionalidad y calendario de {activos.NOMBRE_MERCADO[mercado]}"):
        for s in activos.ESTACIONALIDAD_MERCADO.get(mercado, [ref]):
            ui.estacionalidad_de(s, dias_semana=True)
        grupos = sorted({g for s in activos.ACTIVOS if mercado in activos.mercados(s) for g in activos.noticias(s)})
        cal = ui.calendario.proximos_eventos(dias=45, grupos=grupos).drop(columns=["Momento", "Grupo"])
        st.markdown(f"**Próximos eventos que mueven {activos.NOMBRE_MERCADO[mercado]}**")
        st.dataframe(cal, hide_index=True, alt="Próximos eventos del mercado",
                     column_config={"Fecha": st.column_config.DateColumn(format="DD/MM/YYYY")})
        if mercado == "asia":
            st.markdown("**Horario de cada bolsa (hora de Bogotá)**")
            st.dataframe(pd.DataFrame([{"Bolsa": n, "Horario": activos.horario(s)} for n, s in
                                       [("Tokio", "7203.T"), ("Corea", "005930.KS"), ("Taiwán", "2330.TW"),
                                        ("Hong Kong", "9988.HK"), ("Shanghái", "000001.SS"), ("India", "RELIANCE.NS")]]),
                         hide_index=True, alt="Horarios de las bolsas de Asia")
        if mercado == "futuros":
            st.markdown(f"**Horario:** {activos.horario('ES=F')}")


def pantalla_dividendos():
    t = dividendos.leer()
    if t.empty:
        with st.spinner("Buscando dividendos (la primera vez tarda un poco)..."):
            t = dividendos.actualizar()
    nombres = {v: k for k, v in activos.NOMBRE_MERCADO.items()}
    t = t[~t["Activo"].map(lambda s: activos.ACTIVOS.get(s, {}).get("tipo") in ("cripto", "futuro", "índice"))]
    t = t[t["Rendimiento_%"] > 0].copy()                 # Solo los que pagan
    t["Mercados"] = t["Activo"].map(lambda s: ";".join(activos.mercados(s)))   # Con los mercados de hoy
    t["Moneda"] = t["Activo"].map(activos.moneda)
    st.caption(f"{len(t)} activos de la app pagan dividendos (revisados con Yahoo Finance). Ordenados por rendimiento "
               "anual: cuánto pagaron en los últimos 12 meses dividido por el precio de hoy.")
    presentes = {m for ms in t["Mercados"].fillna("") for m in ms.split(";") if m}      # Solo mercados con dividendos
    nombres = {nombre: clave for nombre, clave in nombres.items() if clave in presentes}
    elegidos = st.pills("Filtrar por mercado (vacío = todos)", list(nombres), selection_mode="multi", key="div_merc",
                        help="«Dividendos» = la lista especial: aristócratas del dividendo y fondos de dividendos.")
    if elegidos:
        t = t[t["Mercados"].fillna("").str.split(";").apply(lambda m: bool(set(m) & {nombres[e] for e in elegidos}))]
    frecuencias = [f for f in ["Mensual", "Trimestral", "Semestral", "Anual"] if f in set(t["Frecuencia"])]
    frecuencias += sorted(set(t["Frecuencia"]) - set(frecuencias))
    cada = st.pills("Frecuencia de pago (vacío = todas)", frecuencias, selection_mode="multi", key="div_frec")
    if cada:
        t = t[t["Frecuencia"].isin(cada)]
    st.dataframe(t[["Activo", "Nombre", "Precio", "Moneda", "Rendimiento_%", "Dividendo_anual", "Frecuencia",
                    "Proximo_corte", "Corte_estimado", "Proximo_pago"]], hide_index=True, alt="Activos con dividendos",
                 height=min(38 * len(t) + 40, 640),
                 column_config={"Precio": st.column_config.NumberColumn(format="%,.2f"),
                                "Moneda": st.column_config.TextColumn(width="small"),
                                "Rendimiento_%": st.column_config.NumberColumn("Rendimiento anual", format="%.2f%%"),
                                "Dividendo_anual": st.column_config.NumberColumn("Dividendo anual por acción",
                                                                                 format="%,.2f",
                                                                                 help="En la moneda del activo."),
                                "Proximo_corte": st.column_config.DateColumn("Próxima fecha de corte", format="DD/MM/YYYY"),
                                "Corte_estimado": st.column_config.CheckboxColumn("¿Estimada?"),
                                "Proximo_pago": st.column_config.DateColumn("Próximo pago", format="DD/MM/YYYY")})
    st.caption("Fecha de corte (ex-dividendo): para cobrar el dividendo debes tener la acción ANTES de ese día. "
               "«Estimada» = calculada con las fechas de pagos anteriores, porque Yahoo todavía no la publica.")

    st.subheader("Proyección a largo plazo")
    c1, c2, c3 = st.columns(3)
    aporte = c1.number_input("Aporte mensual (US$)", min_value=0.0, value=100.0, step=10.0)
    base = c2.selectbox("Basado en", activos.DIVIDENDOS, format_func=activos.etiqueta)
    fila = dividendos.leer().set_index("Activo")
    sugerido = dividendos.crecimiento_historico(base) + (fila["Rendimiento_%"].get(base, 0.0) if len(fila) else 0)
    rendimiento = c3.number_input("Rendimiento total anual (%)", value=round(float(sugerido), 1), step=0.5,
                                  help="Crecimiento del precio en los últimos 5 años + rendimiento por dividendo. "
                                       "Cámbialo si quieres ser más conservador.")
    fila_m = st.container(horizontal=True)
    for anios in (10, 20):
        aportado = aporte * 12 * anios
        final = dividendos.proyeccion(aporte, rendimiento, anios)
        fila_m.metric(f"En {anios} años", ui.dinero(final, decimales=0),
                      f"aportaste {ui.dinero(aportado, decimales=0)}", delta_color="off")
    st.caption("Supone que reinviertes todos los dividendos y que el rendimiento se mantiene igual cada año, lo cual "
               "nunca pasa exactamente. Es una guía, no una promesa.")


@st.cache_data(show_spinner="Guardando los cierres de la semana...")
def _semanal(_version):
    """Solo vuelve a revisar los 1.100 activos cuando hay precios nuevos (tarda unos 15 segundos)."""
    import semanal
    semanal.actualizar()
    return semanal.leer()


def pantalla_semanal():
    t = _semanal(ui.ranking.ARCHIVO.stat().st_mtime)
    mercados = ui.filtro_mercados("semanal_merc")
    opciones = [s for s in sorted(t["Activo"].unique()) if not mercados or set(activos.mercados(s)) & mercados]
    defecto = [s for s in ["CL=F", "BZ=F", "GC=F", "^NDX"] if s in opciones] or opciones[:4]
    elegidos = st.multiselect("Activos", opciones, default=defecto, format_func=activos.etiqueta,
                              key=f"semanal_activos_{'-'.join(sorted(mercados))}")
    if not elegidos:
        st.caption(":material/info: Elige al menos un activo.")
        return
    tabla = t[t["Activo"].isin(elegidos)].pivot(index="Fecha", columns="Activo", values="Cierre").sort_index()
    en_porcentaje = st.toggle("Ver en porcentaje (todos empiezan en 0%)", value=len(elegidos) > 1, key="semanal_pct")
    ver = (tabla / tabla.bfill().iloc[0] - 1) * 100 if en_porcentaje else tabla
    fig = go.Figure()
    for i, s in enumerate(ver.columns):
        fig.add_trace(go.Scatter(x=ver.index, y=ver[s], name=s, line=dict(color=ui.PALETA[i % len(ui.PALETA)], width=2)))
    fig.update_yaxes(title_text="Cambio %" if en_porcentaje else "Cierre del viernes", ticksuffix="%" if en_porcentaje else "")
    st.plotly_chart(ui.estilo(fig, 380), width="stretch")
    st.dataframe(tabla.iloc[::-1].head(52), alt="Cierres de cada viernes (último año)",
                 column_config={"Fecha": st.column_config.DateColumn(format="DD/MM/YYYY")})
    st.caption(f"Cierre de cada viernes (o del último día hábil de la semana). Se guardan en cierres_semanales.csv "
               f"sin borrar los anteriores: {len(t):,} cierres de {t['Activo'].nunique()} activos.".replace(",", "."))


BOLSAS = [  # (bolsa, índice, acciones grandes)
    ("Nueva York", "^GSPC", "Apple, Microsoft, Nvidia, Amazon (en el S&P 500)"), ("Nueva York", "^DJI", "30 empresas grandes"),
    ("Nueva York", "^RUT", "2.000 empresas pequeñas"), ("Nasdaq", "^IXIC", "Nvidia, Apple, Microsoft, Alphabet, Meta"),
    ("Londres", "^FTSE", "AstraZeneca, HSBC, Unilever, Shell"), ("Frankfurt", "^GDAXI", "SAP, Siemens, Allianz"),
    ("París", "^FCHI", "LVMH, L'Oréal, Airbus, TotalEnergies"), ("Europa", "^STOXX50E", "ASML, SAP, LVMH, Siemens"),
    ("Tokio", "^N225", "Toyota, Sony"), ("Hong Kong", "^HSI", "Tencent, Alibaba, BYD"),
    ("Shanghái", "000001.SS", "Grandes empresas chinas"), ("Corea", "^KS11", "Samsung, Hyundai"),
    ("Taiwán", "^TWII", "TSMC"), ("India", "^NSEI", "Reliance, Infosys, HDFC"),
    ("Colombia", "ICOLCAP.CL", "Ecopetrol, Grupo Cibest, ISA, Grupo Aval (ETF que copia el MSCI COLCAP)"),
]


def abierta_ahora(simbolo):
    from datetime import datetime, time
    from zoneinfo import ZoneInfo
    suf = activos._sufijo(simbolo)
    _, zona, ini, fin, _ = activos.SUFIJOS[suf] if suf else ("USD", "America/New_York", "09:30", "16:00", "US")
    ahora = datetime.now(ZoneInfo(zona))
    if ahora.weekday() >= 5 or ahora.date() in activos.festivos_de(simbolo, [ahora.year]):
        return "🔴 Cerrada"
    h = lambda t: time(*map(int, t.split(":")))
    return "🟢 Abierta" if h(ini) <= ahora.time() <= h(fin) else "🔴 Cerrada"


def pantalla_bolsas():
    filas = []
    for bolsa, s, grandes in BOLSAS:
        try:
            r = ui.analisis(s)
            precio, cambio = r["precio"], r["cambio_dia_%"]
        except Exception:
            precio = cambio = None
        filas.append({"Bolsa": bolsa, "Índice": f"{activos.nombre(s)} ({s})", "Último": precio, "Cambio_%": cambio,
                      "Horario": activos.horario(s), "Ahora": abierta_ahora(s), "Acciones grandes": grandes})
    t = pd.DataFrame(filas)
    st.dataframe(t.style.map(color_cambio, subset=["Cambio_%"]), hide_index=True, alt="Bolsas del mundo",
                 column_config={"Último": st.column_config.NumberColumn(format="%,.2f"),
                                "Cambio_%": st.column_config.NumberColumn("Cambio día", format="%+.2f%%"),
                                "Horario": st.column_config.TextColumn("Horario (hora de Bogotá)", width="large")})
    st.caption("El horario se calcula con la zona horaria de cada bolsa, así que se ajusta solo cuando cambian al "
               "horario de verano. «Ahora» tiene en cuenta fines de semana y festivos de cada país.")


TASAS = {"^IRX": "3 meses", "^FVX": "5 años", "^TNX": "10 años", "^TYX": "30 años"}


def pantalla_bonos(t):
    st.info("Un bono es un **préstamo**: le prestas plata al gobierno o a una empresa y te devuelve lo prestado en una "
            "fecha fija, pagándote intereses mientras tanto. La **tasa** es el interés que paga.\n\n"
            "**Regla de oro: cuando las tasas suben, el precio de los bonos que ya existen baja** (y al revés). "
            "¿Por qué? Si hoy salen bonos nuevos pagando 5%, nadie quiere pagar lo mismo por tu bono viejo que paga 3%: "
            "para venderlo tienes que bajarle el precio. Los bonos más largos (20-30 años) se mueven más.",
            title="¿Qué es un bono?", icon=":material/school:")
    tasas = pd.DataFrame({f"Tasa a {n}": ui.precios(s)["Cierre"] for s, n in TASAS.items()}).tail(250)
    fila = st.container(horizontal=True)
    for col in tasas:
        serie = tasas[col].dropna()
        fila.metric(col, f"{serie.iloc[-1]:.2f}%", f"{serie.iloc[-1] - serie.iloc[-21]:+.2f} en el mes",
                    delta_color="inverse", help="Tasa anual del Tesoro de EE.UU. Si sube, los bonos bajan de precio.")
    fig = go.Figure()
    for i, col in enumerate(tasas):
        fig.add_trace(go.Scatter(x=tasas.index, y=tasas[col], name=col, line=dict(color=ui.PALETA[i], width=2)))
    fig.update_yaxes(title_text="Tasa anual", ticksuffix="%")
    st.plotly_chart(ui.estilo(fig, 340), width="stretch", key="tasas_tesoro")
    st.markdown("**La regla de oro en la práctica: la tasa a 10 años contra el ETF de bonos largos TLT**")
    par = pd.DataFrame({"Tasa a 10 años": ui.precios("^TNX")["Cierre"], "TLT": ui.precios("TLT")["Cierre"]}).dropna().tail(250)
    cambio = (par / par.iloc[0] - 1) * 100
    fig = go.Figure()
    for i, col in enumerate(cambio):
        fig.add_trace(go.Scatter(x=cambio.index, y=cambio[col], name=col, line=dict(color=ui.PALETA[i], width=2)))
    fig.update_yaxes(title_text="Cambio en el último año", ticksuffix="%")
    st.plotly_chart(ui.estilo(fig, 300), width="stretch", key="tasa_vs_tlt")
    corr = par.pct_change().corr().iloc[0, 1]
    st.caption(f"Correlación de sus movimientos diarios: {corr:.2f}. Un número negativo confirma que se mueven al revés.")
    st.caption("TES de Colombia: Yahoo Finance no tiene datos diarios gratuitos de los TES ni de un ETF de TES, así que "
               "no se incluyen. El ETF EMB tiene bonos de países emergentes, entre ellos Colombia.")
    st.markdown("**Bonos y tasas en la app**")
    lista(t, "Bonos")


def pantalla_mis_activos():
    cartera = mis_activos.cartera
    with st.expander("Mi saldo real para invertir (para la orden de Trii)"):
        saldo = st.number_input("Saldo disponible en Trii (US$)", min_value=0.0, value=float(consejo.saldo_real_usd()),
                                step=50.0)
        if st.button("Guardar saldo"):
            consejo.guardar_saldo_real_usd(saldo)
            st.toast("Saldo guardado")
    ui.formulario_real(cartera)

    pos = cartera.posiciones()
    todas = cartera.posiciones(solo_abiertas=False, con_precio=False)
    realizada = float(todas["Ganancia_realizada"].sum()) if len(todas) else 0.0
    fila = st.container(horizontal=True)
    suma = lambda col: float(pd.to_numeric(pos[col], errors="coerce").fillna(0).sum()) if len(pos) and col in pos else 0.0
    inv_usd, inv_cop, val_usd, val_cop = suma("Invertido_USD"), suma("Invertido_COP"), suma("Valor_USD"), suma("Valor_COP")
    fila.metric("Invertido", ui.dinero(inv_usd), ui.dinero(inv_cop, "COP"), delta_color="off",
                help="Con la tasa del dólar del día de cada compra.")
    fila.metric("Valor actual", ui.dinero(val_usd), ui.dinero(val_cop, "COP"), delta_color="off",
                help="Con la tasa del dólar de hoy.")
    fila.metric("Ganancia en papel", ui.dinero(val_usd - inv_usd),
                f"{(val_usd / inv_usd - 1) * 100:+.2f}% · {ui.dinero(val_cop - inv_cop, 'COP')}" if inv_usd else None,
                help="De lo que todavía tienes. En pesos incluye el efecto del cambio del dólar.")
    fila.metric("Ganancia realizada", ui.dinero(realizada), help="De lo que ya vendiste.")
    if pos.empty:
        st.info("Cuando registres una compra, aquí verás cuánto vas ganando y si conviene mantener o vender.")
    else:
        ui.tabla_posiciones(pos)
        pagos = dividendos.cobrados(cartera)
        pagos = pagos[(pagos["Pagado_US$"] > 0) | (pagos["Esperado_12m_US$"] > 0)]
        if len(pagos):
            st.markdown("**💵 Dividendos**")
            fila = st.container(horizontal=True)
            fila.metric("Te han pagado", ui.dinero(pagos["Pagado_US$"].sum()))
            fila.metric("Esperas en los próximos 12 meses", ui.dinero(pagos["Esperado_12m_US$"].sum()))
            st.dataframe(pagos, hide_index=True, alt="Dividendos por activo",
                         column_config={"Pagado_US$": st.column_config.NumberColumn("Pagado", format="US$ %.2f"),
                                        "Esperado_12m_US$": st.column_config.NumberColumn("Esperado 12 meses",
                                                                                          format="US$ %.2f")})
        ui.grafica_cartera(cartera, "real")
        ui.predicciones_cartera(cartera, "real", "de mis activos")
    ui.diario_errores(cartera, "Mis activos", "real")
    ui.editor_operaciones(cartera, "real")


pestanas = st.tabs(NOMBRES, on_change="rerun", key="pestana_mercado")
for nombre, pestana in zip(NOMBRES, pestanas):
    if not pestana.open:
        continue
    with pestana:
        if nombre == "Mis activos":
            pantalla_mis_activos()
        elif nombre == "Dividendos":
            pantalla_dividendos()
        elif nombre == "Semanal":
            pantalla_semanal()
        elif nombre == "Bolsas":
            pantalla_bolsas()
        elif nombre == "Todo":
            lista(tabla, nombre)
        elif nombre == "Bonos":
            pantalla_bonos(tabla[tabla["Mercados"].str.split(";").apply(lambda m: "bonos" in m)])
        else:
            cabecera_mercado(FILTRO[nombre])
            lista(tabla[tabla["Mercados"].str.split(";").apply(lambda m: FILTRO[nombre] in m)], nombre)
