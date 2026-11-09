# Inicio: consejo del día, Nasdaq/Petróleo/Oro lado a lado, top 5, Mis activos y alertas de hoy

import pandas as pd
import streamlit as st

import activos
import alertas
import consejo
import mis_activos
import noticias
import ui

encabezado = st.container(horizontal=True, vertical_alignment="bottom")
encabezado.title("Inicio")
if ui.puede("actualizar") and encabezado.button("Actualizar datos", icon=":material/refresh:",
                                                 help="Descarga precios y noticias nuevas (tarda unos 3 minutos)."):
    ui.actualizar_todo()
    st.rerun()
tabla = ui.tabla_ranking()
st.caption(f"Precios al {pd.to_datetime(tabla['Fecha_datos']).max():%d/%m/%Y} · noticias actualizadas: "
           f"{noticias.ultima_actualizacion() or 'nunca'}")

# ---------- Carrusel de mercados (los mismos de Seguimiento; Mis activos va aparte, más abajo) ----------
paneles = [p for p in activos.PANELES if any(activos.mercado_activo(m) for m in p[1])]
nombres = [p[0] for p in paneles]
if st.session_state.get("panel_inicio") not in nombres:
    st.session_state["panel_inicio"] = nombres[0]
PESTANA_DE_PANEL = {"Bonos globales": "Bonos"}          # Nombre de la pestaña de Seguimiento si es distinto
CLAVES_BANCO = {"Estados Unidos": ["Fed", "Reserva Federal", "FOMC"], "Europa": ["BCE", "Banco Central Europeo"],
                "Asia": ["Banco de Japón", "BoJ"], "Colombia": ["Banco de la República", "BanRep"],
                "Latinoamérica": ["Copom", "Banxico"]}


def mover(paso):
    i = nombres.index(st.session_state["panel_inicio"])
    st.session_state["panel_inicio"] = nombres[(i + paso) % len(nombres)]


fila = st.container(horizontal=True, vertical_alignment="center")
fila.button("Anterior", icon=":material/chevron_left:", on_click=mover, args=(-1,), key="panel_atras")
fila.segmented_control("Mercado", nombres, required=True, key="panel_inicio", label_visibility="collapsed")
fila.button("Siguiente", icon=":material/chevron_right:", on_click=mover, args=(1,), key="panel_adelante",
            icon_position="right")
nombre_panel, mercados_panel, simbolos_panel, banco = next(p for p in paneles if p[0] == st.session_state["panel_inicio"])

ui.consejo_tendencia(simbolos_panel[0], nombre_panel)
if banco:
    nombre_banco, que_hace, moneda = banco
    proximo = ui.calendario.proximos_eventos(dias=120)
    proximo = proximo[proximo["Evento"].str.contains("|".join(CLAVES_BANCO.get(nombre_panel, ["@@"])), case=False)]
    with st.container(border=True):
        st.markdown(f":material/account_balance: **Banco central:** {nombre_banco}. {que_hace}  \n"
                    f":material/currency_exchange: **Moneda:** {moneda}"
                    + (f"  \n:material/event: **Próxima reunión o dato:** {proximo['Fecha'].iloc[0]:%d/%m/%Y} · "
                       f"{proximo['Evento'].iloc[0]}" if len(proximo) else ""))
for inicio in range(0, len(simbolos_panel), 3):                # Tarjetas de 3 en 3 (en celular, una debajo de otra)
    for columna, simbolo in zip(st.columns(3), simbolos_panel[inicio:inicio + 3]):
        try:
            r = ui.analisis(simbolo)
        except Exception:
            columna.caption(f"Sin datos de {simbolo}")
            continue
        decision, color, _ = ui.unificada(r)
        with columna.container(border=True, height="stretch"):
            st.metric(activos.nombre(simbolo), ui.numero(r["precio"]), f"{r['cambio_dia_%']:+.2f}% hoy")
            with st.container(horizontal=True):
                st.badge(activos.tipo_nombre(simbolo), color="violet")
                st.badge(r["estado"], color=ui.COLOR_ESTADO[r["estado"]])
                ui.insignia_decision(decision)
            st.plotly_chart(ui.mini_grafica(r["datos"]["Cierre"].tail(66), alto=120), width="stretch",
                            key=f"mini_{simbolo}")
            if st.button("Ver activo", key=f"ver_{simbolo}", icon=":material/arrow_forward:", width="stretch"):
                ui.ir_a_activo(simbolo)

compra = consejo.comprar_hoy(analizar=ui.analisis, mercados=mercados_panel)
vende = consejo.vender_hoy(mercados=mercados_panel)
if not ui.puede("mis_activos") and len(vende):              # Lo real solo lo ve el superadmin
    vende = vende[vende["Origen"].astype(str).str.contains("imul", case=False)]
izq, der = st.columns(2)
with izq.container(border=True, height="stretch"):
    st.subheader(f":material/shopping_cart: Hoy compra estos · {nombre_panel}")
    if compra.empty:
        st.caption(f":material/info: Hoy no hay oportunidades en {nombre_panel}.")
    for _, f in compra.iterrows():
        st.markdown(f":{f['Color']}[**{f['Decision']}**] · **{f['Activo']}** {f['Nombre']}  \n"
                    f"Precio {ui.numero(f['Precio'])} · stop {ui.numero(f['Stop'])} · objetivo {ui.numero(f['Objetivo'])}"
                    f" · vender a más tardar el {f['Vender_el']:%d/%m}")
        if f["Dudas"]:
            st.caption(f":material/help: {f['Dudas'][0]}")
with der.container(border=True, height="stretch"):
    st.subheader(f":material/sell: Hoy vende estos · {nombre_panel}")
    if vende.empty:
        st.caption(f":material/info: Nada para vender en {nombre_panel}: ni en Mis activos ni en el simulador.")
    for _, f in vende.iterrows():
        st.markdown(f"**{f['Origen']}** · **{f['Activo']}** {f['Nombre']}: {f['Motivo']}  \n"
                    f"Precio {ui.numero(f['Precio'])} · stop {ui.numero(f['Stop'])} · objetivo {ui.numero(f['Objetivo'])}")
if st.button(f"Ver todo {nombre_panel} en Seguimiento", icon=":material/list:"):
    st.session_state["pestana_mercado"] = PESTANA_DE_PANEL.get(nombre_panel, nombre_panel)
    st.switch_page(ui.PAGINA_SEGUIMIENTO)

# ---------- Ranking, Mis activos y alertas ----------
izq, centro, der = st.columns([1.3, 1, 1])
with izq.container(border=True, height="stretch"):
    st.subheader("Ranking top 5")
    top = tabla.head(5).copy()
    top["Decision"] = [ui.unificada(ui.analisis(s))[0] for s in top["Activo"]]
    evento = st.dataframe(
        top[["Sector", "Activo", "Nombre", "Probabilidad_%", "Decision"]], hide_index=True, on_select="rerun",
        selection_mode=["single-row", "single-cell"], key="top5", alt="Los cinco activos con mayor probabilidad de subida",
        column_config={"Sector": st.column_config.TextColumn("Sector", help=ui.AYUDA_SECTOR),
                       "Probabilidad_%": st.column_config.ProgressColumn("Probabilidad", format="%.1f%%",
                                                                         min_value=0, max_value=100),
                       "Decision": st.column_config.TextColumn("Decisión", help="Tócala para ver por qué")})
    if evento.selection.cells:
        fila_t, columna = evento.selection.cells[0]
        if columna == "Decision":
            ui.explicar_decision(ui.analisis(top["Activo"].iloc[fila_t]))
        else:
            ui.ir_a_activo(top["Activo"].iloc[fila_t])
    elif evento.selection.rows:
        ui.ir_a_activo(top["Activo"].iloc[evento.selection.rows[0]])
    st.caption("Toca la decisión para ver por qué; toca otra celda para abrir el activo.")

with centro.container(border=True, height="stretch"):
    st.subheader("Mis activos" if ui.puede("mis_activos") else "Mi simulador")
    mios = mis_activos.abiertas() if ui.puede("mis_activos") else __import__("simulador").cartera.posiciones()
    if mios.empty:
        st.caption(":material/info: Todavía no tienes compras abiertas.")
    for _, p in mios.iterrows():
        g = p["Ganancia_%"]
        st.markdown(f"**{p['Activo']}** · {p['Cantidad']:g} a {ui.dinero(p['Precio_compra'])} → "
                    f":{'green' if (g or 0) >= 0 else 'red'}[{ui.numero(g, 1)}%] · **{p['Sugerencia']}**")
    if not ui.puede("mis_activos"):
        if st.button("Ir al simulador", icon=":material/arrow_forward:", width="stretch"):
            st.switch_page("app_pages/simulacion.py")
    elif st.button("Ir a Mis activos", icon=":material/arrow_forward:", width="stretch"):
        st.session_state["pestana_mercado"] = "Mis activos"
        st.switch_page(ui.PAGINA_SEGUIMIENTO)

with der.container(border=True, height="stretch"):
    st.subheader("Alertas de hoy")
    textos = list(alertas.alertas_de_hoy()["Alerta"])
    if not ui.puede("mis_activos"):                         # Sin avisos de las compras reales del superadmin
        textos = [t for t in textos if "REAL" not in t and "Mis activos" not in t]
    textos = textos[:8]
    if not textos:
        for simbolo in activos.REFERENCIAS.values():
            textos += [t for _, t in alertas.detectar_patrones(ui.analisis(simbolo)["datos"], simbolo)]
    for t in textos[:8]:
        st.markdown(f"- {t}")
    if not textos:
        st.caption("Sin alertas hoy.")
