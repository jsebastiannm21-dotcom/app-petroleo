# Página de un activo: decisión grande arriba y pestañas Señal de hoy, Pronóstico, Simulador,
# Calendario y Ranking. El activo es el que está elegido en la barra izquierda.

from datetime import timedelta

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import activos
import calendario
import simulador
import ui

simbolo = activos.limpiar(st.session_state.get("activo") or activos.PRINCIPAL)
try:
    r = ui.analisis(simbolo)
except Exception as error:
    st.error(f"No pude analizar '{simbolo}': {error}", title="Símbolo no válido")
    st.stop()

encabezado = st.container(horizontal=True, vertical_alignment="center")
encabezado.title(f"{activos.icono(simbolo)} {activos.nombre(simbolo)}")
encabezado.metric(simbolo, ui.numero(r["precio"]), f"{r['cambio_dia_%']:+.2f}% hoy")
if ui.puede("actualizar") and encabezado.button("Actualizar datos", icon=":material/refresh:"):
    import noticias
    with st.spinner("Descargando precios y noticias..."):
        activos.descargar(simbolo)
        noticias.de_empresa(simbolo, refrescar_horas=0)
    st.cache_data.clear()
    st.rerun()
st.caption(f"Datos al {r['fecha']:%d/%m/%Y} · tendencia {r['estado']} · {activos.tipo_nombre(simbolo)}")
if st.button(f"Ver noticias de {activos.nombre(simbolo)}", type="primary", icon=":material/newspaper:", width="stretch",
             key="noticias_activo", help="Todas sus noticias y las de su mercado, con filtro por fecha."):
    ui.panel_noticias(simbolo)

ui.ficha(simbolo)
ui.decision_grande(r)
if st.button("¿Por qué esta decisión? Explicación paso a paso", icon=":material/school:", key="porque_activo"):
    ui.explicar_decision(r)
if activos.tipo(simbolo) not in ("índice", "bono", "divisa"):
    ui.stop_personal(simbolo)
if activos.es_cripto(simbolo):
    ui.cripto_en_vivo(simbolo)

pestanas = st.tabs(["Señal de hoy", "Pronóstico", "Simulador", "Calendario", "Ranking", "Análisis de Claude"],
                   on_change="rerun", key="pestana_activo")

# ---------- Señal de hoy: gráfica con filtros, comparación y casos ----------
if pestanas[0].open:
    with pestanas[0]:
        ui.grafica_precio(simbolo, r, clave=f"precio_{simbolo}")
        seccion = st.expander("Abanico de predicciones (Monte Carlo)", icon=":material/stacked_line_chart:",
                              key=f"sec_abanico_{simbolo}", on_change="rerun")
        if seccion.open:
            with seccion:
                ui.abanico(simbolo)
        seccion = st.expander("Estacionalidad: meses y días de la semana", icon=":material/calendar_month:",
                              key=f"sec_estac_{simbolo}", on_change="rerun")
        if seccion.open:
            with seccion:
                ui.estacionalidad_de(simbolo, dias_semana=True)
        ui.analisis_avanzado(simbolo, "activo")
        st.markdown("#### Comparar con otros activos (en %)")
        mercados = ui.filtro_mercados(f"comp_merc_{simbolo}")
        opciones = [s for s in activos.ACTIVOS if s != simbolo and (not mercados or set(activos.mercados(s)) & mercados)]
        otros = st.multiselect("Activos a comparar", opciones, format_func=activos.etiqueta,
                               accept_new_options=True, max_selections=7, key=f"comparar_{simbolo}",
                               placeholder="Elige hasta 7 activos")
        if otros:
            ui.grafica_comparacion([simbolo] + [activos.limpiar(o) for o in otros], clave=f"comp_{simbolo}")
        else:
            st.caption("Elige activos para ver cuál subió o bajó más en el mismo periodo (todos empiezan en 0%).")
        if len(r["casos"]):
            st.markdown(f"#### Días parecidos ({len(r['casos'])})", help=ui.AYUDA_DIAS_PARECIDOS)
            st.caption(f"{ui.muestra_casos(r)}. Verde: subió en los 5 días siguientes; rojo: bajó.")
            decision = ui.unificada(r)[0]
            st.info(r["razon"], title=f"¿Por qué {decision.lower()} hoy?", icon=":material/lightbulb:")
            casos = r["casos"][["Cierre", "RSI14", "Retorno_5d_%", "Perdida_max_%"]].round(2).iloc[::-1]
            casos = casos.rename_axis("Fecha").reset_index()
            pinta = lambda fila: [f"background-color: {'rgba(5,150,105,0.15)' if fila['Retorno_5d_%'] > 0 else 'rgba(220,38,38,0.13)'}"] * len(fila)
            evento = st.dataframe(
                casos.style.apply(pinta, axis=1), hide_index=True, on_select="rerun", selection_mode="single-cell",
                key=f"casos_{simbolo}", alt="Casos parecidos: verde subieron, rojo bajaron",
                column_config={"Fecha": st.column_config.DateColumn(format="DD/MM/YYYY", help="Toca para ver las noticias de ese día"),
                               "Cierre": st.column_config.NumberColumn(help="Toca para ver el cierre de esas semanas"),
                               "RSI14": st.column_config.NumberColumn("RSI", help="Toca para ver el RSI de ese mes"),
                               "Retorno_5d_%": st.column_config.NumberColumn("Cambio 5 días", format="%+.2f%%",
                                                                             help="Toca para ver esos 5 días"),
                               "Perdida_max_%": st.column_config.NumberColumn("Peor caída", format="%+.2f%%",
                                                                              help="Toca para ver la peor caída de ese mes")})
            st.caption("Verde = el precio subió en los 5 días siguientes; rojo = bajó. **Toca una celda**: la fecha "
                       "muestra las noticias de ese día y cada columna, su gráfica.")
            if evento.selection.cells:
                fila, columna = evento.selection.cells[0]
                ui.dialogo_caso(simbolo, r, casos["Fecha"].iloc[fila], columna)

# ---------- Pronóstico ----------
@st.cache_data(show_spinner="Calculando el pronóstico...")
def pronostico(simbolo, _version, metodo):
    import forecast
    cierre = ui.precios(simbolo)["Cierre"]
    ultima = cierre.index[-1]
    futuro = pd.bdate_range(ultima + timedelta(days=1), ultima + timedelta(days=forecast.DIAS))
    p = forecast.proyectar(cierre, futuro)[0] if metodo == "Prophet" else forecast.metodo_sencillo(cierre, futuro)
    return cierre, p


if pestanas[1].open:
    with pestanas[1]:
        fila_m = st.container(horizontal=True, vertical_alignment="bottom")
        metodo = fila_m.segmented_control("Método", ["Método sencillo", "Prophet"], default="Método sencillo",
                                          required=True, help="En nuestras pruebas con datos del pasado, el método "
                                                              "sencillo acertó un poco más que Prophet.")
        ui.boton_que_es(fila_m, "prophet", f"prophet_{simbolo}")
        st.markdown("- **Método sencillo:** toma la **tendencia reciente** (cuánto ha subido o bajado en los últimos "
                    "meses) y la prolonga hacia adelante.\n"
                    "- **Prophet:** programa de Meta que suma la **tendencia** y la **estacionalidad** (lo que suele "
                    "pasar en ciertos meses o días de la semana).\n"
                    "- **Kronos:** una **inteligencia artificial entrenada con miles de millones de velas** (precios de "
                    "apertura, máximo, mínimo y cierre) de mercados de todo el mundo; reconoce patrones de precios como "
                    "un chat reconoce palabras.")
        cierre, p = pronostico(simbolo, ui.version(simbolo), "Prophet" if metodo == "Prophet" else "sencillo")
        import kronos_pronostico
        listo, motivo = kronos_pronostico.disponible()
        kronos_on = st.toggle("Kronos como segundo pronóstico", value=kronos_pronostico.activado(), disabled=not listo,
                              help="Modelo de código abierto para velas de mercado (versión small). La primera vez "
                                   "tarda unos 20 segundos en cargar." + ("" if listo else f" No disponible: {motivo}"))
        if kronos_on != kronos_pronostico.activado():
            kronos_pronostico.cambiar(kronos_on)
        reciente = cierre[cierre.index > cierre.index[-1] - pd.DateOffset(months=6)]
        x = [cierre.index[-1]] + list(p.index)
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=reciente.index, y=reciente, name="Precio real", line=dict(color=ui.AZUL, width=1.6)))
        ui.banda(fig, x, [cierre.iloc[-1]] + list(p["Banda_baja"]), [cierre.iloc[-1]] + list(p["Banda_alta"]),
                 "Rango probable (80%)")
        fig.add_trace(go.Scatter(x=p.index, y=p["Central"], name=f"{metodo}: central", line=dict(color=ui.NARANJA, width=2.4),
                                 customdata=np.stack([p["Banda_baja"], p["Banda_alta"]], axis=1),
                                 hovertemplate="%{y:,.2f} (rango %{customdata[0]:,.2f} a %{customdata[1]:,.2f})"))
        if kronos_on and listo:
            with st.spinner("Kronos está calculando..."):
                k = kronos_pronostico.pronosticar(simbolo, dias=len(p))
            fig.add_trace(go.Scatter(x=[cierre.index[-1]] + list(k.index), y=[cierre.iloc[-1]] + list(k["Central"]),
                                     name="Kronos", line=dict(color=ui.VERDE_AGUA, width=2.4, dash="dot")))
        st.plotly_chart(ui.estilo(fig, 460), width="stretch")
        fin = p.iloc[-1]
        fila = st.container(horizontal=True)
        fila.metric(f"Central al {p.index[-1]:%d/%m}", ui.numero(fin["Central"]))
        fila.metric("Mínimo probable", ui.numero(fin["Banda_baja"]))
        fila.metric("Máximo probable", ui.numero(fin["Banda_alta"]))
        if kronos_on and listo:
            fila.metric(f"Kronos al {k.index[-1]:%d/%m}", ui.numero(k["Central"].iloc[-1]))
        st.caption("Proyección a 30 días. Ningún método predice los precios con precisión: la banda magenta es el "
                   "rango probable (8 de cada 10 veces), no un límite.")

        st.markdown("#### Tasa de aciertos de las predicciones a 5 días")
        import predicciones
        predicciones.evaluar()
        tabla = predicciones.tasa_aciertos(simbolo)
        if tabla.empty:
            st.info("Todavía no hay predicciones revisadas para este activo. Cada mañana se guardan las de Prophet, "
                    "Monte Carlo y Kronos, y a los 5 días de mercado se comparan con el precio real.")
        else:
            st.dataframe(tabla, hide_index=True, alt="Aciertos por método",
                         column_config={"Aciertos_%": st.column_config.ProgressColumn("Acertó la dirección", format="%.0f%%",
                                                                                      min_value=0, max_value=100),
                                        "Dentro_rango_%": st.column_config.NumberColumn("Dentro del rango", format="%.0f%%"),
                                        "Error_%": st.column_config.NumberColumn("Error promedio", format="%.2f%%")})
        pendientes = predicciones.leer()
        pendientes = pendientes[(pendientes["Activo"] == simbolo) & pendientes["Precio_real"].isna()]
        if len(pendientes):
            st.caption(f"{len(pendientes)} predicciones esperando su fecha: "
                       + ", ".join(f"{f['Metodo']} {f['Prediccion']:,.2f} para el {f['Fecha_objetivo']:%d/%m}"
                                   for _, f in pendientes.iterrows()))

# ---------- Simulador de este activo ----------
if pestanas[2].open:
    with pestanas[2]:
        s = simulador.resumen()
        fila = st.container(horizontal=True)
        fila.metric("Disponible en el simulador", ui.pesos(s["disponible"]))
        fila.metric("Total del simulador", ui.pesos(s["total"]), f"{s['ganancia_%']:+.2f}%")
        pos = simulador.cartera.posiciones()
        p = pos[pos["Activo"] == simbolo] if len(pos) else pos
        if len(p):
            p = p.iloc[0]
            st.info(f"Comprado a {ui.dinero(p['Precio_compra'])}. Va {p['Ganancia_%']:+.2f}%. Stop loss "
                    f"{ui.dinero(p['Stop'])} · objetivo {ui.dinero(p['Objetivo'])}. Sugerencia: {p['Sugerencia']}.",
                    title="Compra abierta (simulación)")
        st.caption(":material/arrow_downward: Para comprar o vender, usa el botón al final de la página. Todo va al "
                   "mismo saldo e historial de la pantalla Simulador.")
        h = simulador.cartera.con_resultado()
        h = h[h["Activo"] == simbolo]
        if len(h):
            st.dataframe(h.iloc[::-1], hide_index=True, alt=f"Operaciones del simulador con {simbolo}",
                         column_config={"Fecha": st.column_config.DatetimeColumn(format="DD/MM/YYYY hh:mm a"),
                                        "Resultado": st.column_config.NumberColumn(format="US$ %+.2f")})
        else:
            st.caption(f"El simulador todavía no ha operado {simbolo}.")

# ---------- Calendario de su mercado ----------
if pestanas[3].open:
    with pestanas[3]:
        grupos = activos.noticias(simbolo)
        cal = calendario.proximos_eventos(dias=60, grupos=grupos) if grupos else calendario.proximos_eventos(dias=60)
        hoy = calendario.hoy_colombia()
        if len(cal):
            f = cal.iloc[0]
            st.metric("Próximo evento", f"{f['Fecha']:%d/%m} · {f['Tipo']}", f["Evento"], delta_color="off",
                      help=ui.ayuda_proximo_evento())
        cal.insert(1, "Cuándo", ["HOY" if d == hoy else "MAÑANA" if d == hoy + timedelta(days=1)
                                 else f"en {(d - hoy).days} días" for d in cal["Fecha"]])
        st.dataframe(cal.drop(columns="Grupo"), hide_index=True, alt="Próximos eventos")
        st.caption("Petróleo: reuniones de la OPEP+ e inventarios de EE.UU. (cada miércoles). Nasdaq y oro: "
                   "decisiones de la Fed, inflación y empleo de EE.UU. Fechas en calendario_eventos.csv.")

# ---------- Ranking ----------
if pestanas[4].open:
    with pestanas[4]:
        tabla = ui.tabla_ranking().copy()
        tabla["Tipo"] = tabla["Activo"].map(activos.tipo_nombre)
        tabla["Decision"] = tabla["Decision"].map(ui.texto_decision)
        fila = tabla.index[tabla["Activo"] == simbolo]
        ver_todo = st.toggle("Ver el ranking completo", key=f"rank_todo_{simbolo}")
        if len(fila):
            n = int(tabla.loc[fila[0], "Puesto"])
            st.markdown(f"**{activos.nombre(simbolo)} ({simbolo})** está en el puesto **{n}** de {len(tabla)}.")
            if not ver_todo:                              # Abre directo en su puesto: 10 arriba y 10 abajo
                tabla = tabla.iloc[max(0, fila[0] - 10): fila[0] + 11]
        else:
            st.caption(f"{simbolo} no está en el ranking (se calcula con los activos de la lista).")
        mio = lambda f: ["background-color: rgba(0,229,255,0.22); font-weight: 700" if f["Activo"] == simbolo else ""] * len(f)
        color = lambda v: {"🟢 Comprar": "color: #00FF9C; font-weight: 600", "🔴 No comprar": "color: #FF3864; font-weight: 600"}\
            .get(v, "color: #8A9BB3")
        centro = "center"
        st.dataframe(
            tabla[["Puesto", "Tipo", "Sector", "Activo", "Nombre", "Probabilidad_%", "Decision", "Casos"]]
            .style.apply(mio, axis=1).map(color, subset=["Decision"]),
            hide_index=True, alt="Ranking de activos con el activo actual resaltado",
            column_config={"Puesto": st.column_config.NumberColumn(width=60, alignment=centro),
                           "Tipo": st.column_config.TextColumn(width=70, alignment=centro),
                           "Sector": st.column_config.TextColumn(width=170, alignment=centro, help=ui.AYUDA_SECTOR),
                           "Activo": st.column_config.TextColumn("Símbolo", width=90, alignment=centro),
                           "Nombre": st.column_config.TextColumn("Nombre completo", width=230, alignment=centro),
                           "Probabilidad_%": st.column_config.ProgressColumn("Probabilidad", format="%.1f%%",
                                                                             min_value=0, max_value=100, width=130),
                           "Decision": st.column_config.TextColumn("Decisión", width=120, alignment=centro),
                           "Casos": st.column_config.NumberColumn("Días parecidos", width=110, alignment=centro,
                                                                  help=ui.AYUDA_DIAS_PARECIDOS)})

# ---------- Análisis de Claude ----------
if pestanas[5].open:
    with pestanas[5]:
        import analisis_claude
        historial = analisis_claude.del_activo(simbolo)
        if st.button("Pedir un análisis a Claude ahora", icon=":material/psychology:",
                     help="Usa Claude Code con las skills financial-analysis y equity-research. Tarda de 1 a 5 minutos "
                          "y consume uso de tu plan de Claude."):
            with st.spinner("Claude está revisando resultados, pares y noticias (1 a 5 minutos)..."):
                res = analisis_claude.analizar(simbolo)
            st.error(res) if isinstance(res, str) else st.rerun()
        if historial.empty:
            st.info("Claude todavía no ha analizado este activo. Lo hace solo a las 7:30 a.m. con los activos que "
                    "dicen COMPRAR y los que tienes.")
        colores = {"CONFIRMA": "green", "DUDAS": "orange", "EN_CONTRA": "red"}
        for _, a in historial.iterrows():
            with st.container(border=True):
                cab = st.container(horizontal=True, vertical_alignment="center")
                cab.markdown(f"**{a['Fecha']:%d/%m/%Y %I:%M %p}**")
                cab.badge(a["Veredicto"], color=colores.get(a["Veredicto"], "gray"))
                st.markdown(a["Resumen"])
                for titulo, campo in [("Resultados", "Resultados"), ("Comparación con pares", "Pares"),
                                      ("Noticias", "Noticias")]:
                    if pd.notna(a[campo]) and a[campo]:
                        st.markdown(f"**{titulo}:** {a[campo]}")
                dudas = [d.strip() for d in str(a["Dudas"]).split("|") if d.strip() and d.strip() != "nan"]
                for d in dudas:
                    st.markdown(f":orange[:material/help: {d}]")

# ---------- Botón rápido de comprar / vender (simulador principal) ----------
ui.compra_rapida(simbolo)
