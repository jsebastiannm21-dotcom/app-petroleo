# Alertas: las de hoy, la conexión con Telegram y qué significa cada alerta

import pandas as pd
import streamlit as st

import alertas
import estrategia
import ui

st.title("Alertas")
admin = ui.puede("admin")

if admin:
    import usuarios
    with st.expander("Usuarios registrados (solo superadmin)", icon=":material/group:"):
        usuarios.panel_admin()

# ---------- Conexión con Telegram ----------
if admin:
    with st.container(border=True):
        st.subheader("Telegram")
        token, chat = alertas.config()
        if not token:
            st.warning("Falta la clave del bot. Abre el archivo .env con el Bloc de notas y pégala después de "
                       "TELEGRAM_TOKEN=", title="Paso 1 de 3")
        elif not chat:
            st.warning("La clave está guardada. Abre tu bot en Telegram, toca Iniciar, escríbele «hola» y luego "
                       "toca el botón.", title="Paso 2 de 3")
            if st.button("Ya le escribí «hola»: buscar mi chat", icon=":material/search:"):
                try:
                    alertas.obtener_chat_id()
                    st.rerun()
                except SystemExit as aviso:
                    st.error(str(aviso))
        else:
            st.success("Bot conectado. Recibirás los mensajes de los horarios de abajo si programaste las "
                       "revisiones (ver COMO_FUNCIONA.md).", title="Listo")
            if st.button("Enviar mensaje de prueba", icon=":material/send:"):
                st.toast("Mensaje enviado" if alertas.enviar("✅ Prueba desde la app: tu bot funciona.") else "No se pudo enviar")

# ---------- Alertas de hoy ----------
st.subheader("Alertas de hoy")
if admin and st.button("Revisar alertas ahora", icon=":material/refresh:",
             help="Actualiza todos los activos (unos 1.100) y manda por Telegram las alertas nuevas (tarda unos 3 minutos)."):
    with st.spinner("Revisando..."):
        import ranking
        tabla = ranking.calcular(actualizar=True)
        resultados = {}
        for s in tabla["Activo"]:
            try:
                resultados[s] = estrategia.analizar(s)
            except Exception:
                pass
        nuevas = alertas.revisar_alertas(resultados)
    st.cache_data.clear()
    st.toast(f"{len(nuevas)} alertas nuevas")
hoy = alertas.alertas_de_hoy()
if not admin and len(hoy):                                 # Sin avisos de las compras reales del superadmin
    hoy = hoy[~hoy["Alerta"].astype(str).str.contains("REAL|Mis activos")]
if hoy.empty:
    st.caption("Todavía no hay alertas hoy.")
else:
    st.dataframe(hoy, hide_index=True, alt="Alertas de hoy",
                 column_config={"Fecha_hora": "Hora", "Alerta": st.column_config.TextColumn(width="large")})

# ---------- Registro de aciertos ----------
import aciertos  # noqa: E402

st.subheader("Registro de aciertos")
aciertos.evaluar()
res = aciertos.resumen()
fila = st.container(horizontal=True)
fila.metric("Aciertos de la app sola", "—" if res["app_%"] is None else f"{res['app_%']:.0f}%",
            f"{res['app_n']} sugerencias revisadas", delta_color="off",
            help="De las veces que la app dijo COMPRAR, en cuántas el precio estaba más arriba 5 días de mercado después.")
fila.metric("Aciertos de COMPRAR CONFIRMADO", "—" if res["unificada_%"] is None else f"{res['unificada_%']:.0f}%",
            f"{res['unificada_n']} revisadas", delta_color="off", help="Solo cuando la app y Claude coincidieron.")
fila.metric("Esperando sus 5 días", res["pendientes"])
registro = aciertos.leer()
if registro.empty:
    st.caption("Cada mañana se anotan las sugerencias de COMPRAR con su fecha y precio; a los 5 días de mercado se "
               "revisa si acertaron.")
else:
    st.dataframe(registro.iloc[::-1], hide_index=True, alt="Registro de sugerencias",
                 column_config={"Fecha": st.column_config.DateColumn(format="DD/MM/YYYY"),
                                "Fecha_revision": st.column_config.DateColumn("Revisada el", format="DD/MM/YYYY"),
                                "Acierto": st.column_config.CheckboxColumn()})

# ---------- Aciertos del modo automático (superadmin) ----------
import automatico  # noqa: E402

if admin:
    cab = st.container(horizontal=True, vertical_alignment="center")
    cab.subheader("Aciertos del modo automático")
    cab.badge("Uso del superadmin", icon=":material/admin_panel_settings:", color="orange")
    tabla_auto, r_auto = automatico.comparar_simulador()
    if r_auto is None:
        st.caption("El simulador todavía no tiene operaciones del modo automático. Cuando lo actives (pantalla Simulador), "
                   "aquí verás sus aciertos comparados con comprar y mantener.")
    else:
        st.markdown("**Automático vs. comprar y mantener** (las mismas compras, pero sin vender hasta hoy)")
        fila = st.container(horizontal=True)
        fila.metric("Rendimiento automático", f"{r_auto['auto_%']:+.2f}%",
                    f"{r_auto['auto_%'] - r_auto['mantener_%']:+.2f} vs. mantener", help="Promedio ponderado por monto.")
        fila.metric("Comprar y mantener", f"{r_auto['mantener_%']:+.2f}%")
        fila.metric("Operaciones", r_auto["operaciones"], f"{r_auto['cerradas']} cerradas", delta_color="off")
        fila.metric("Aciertos automático", "—" if r_auto["aciertos_auto_%"] is None else f"{r_auto['aciertos_auto_%']:.0f}%",
                    help="De las operaciones cerradas, cuántas terminaron con ganancia.")
        fila.metric("Aciertos mantener", f"{r_auto['aciertos_mantener_%']:.0f}%")
        fila.metric("Peor caída (automático / mantener)", f"{r_auto['peor_auto_%']:+.1f}% / {r_auto['peor_mantener_%']:+.1f}%",
                    help="La peor operación de cada estrategia.")
        st.dataframe(tabla_auto.iloc[::-1], hide_index=True, alt="Operaciones del modo automático",
                     column_config={"Invertido_COP": st.column_config.NumberColumn("Invertido", format="$ %,.0f"),
                                    "Automatico_%": st.column_config.NumberColumn("Automático", format="%+.2f%%"),
                                    "Mantener_%": st.column_config.NumberColumn("Si mantenía", format="%+.2f%%")})

# ---------- Horarios ----------
if admin:                                  # Los horarios de Telegram solo le sirven al superadmin
    st.subheader("Horarios de Telegram (días hábiles, hora de Bogotá)")
    st.table(pd.DataFrame([
        ("7:30 a.m.", "Claude analiza los activos con COMPRAR y los tuyos (no manda mensaje)."),
        ("8:00 a.m.", "Reporte del día: top 5, sugerencia por mercado y dividendos próximos."),
        ("9:45 a.m.", "Qué comprar y qué vender hoy, con la orden lista para Trii si es COMPRAR CONFIRMADO."),
        ("12:00 m.", "Revisión: ¿algo tocó el stop loss o el objetivo?"),
        ("3:30 p.m.", "Última llamada antes del cierre."),
        ("8:00 p.m.", "Resumen del día, aciertos y noticias de la noche."),
        ("Cada 15 min (7:00 a.m. a 10:00 p.m.)", "Aviso al momento si una posición real o simulada toca el stop o el "
                                                 "objetivo, o si sale una noticia fuerte (OPEP, Fed, Trump, guerra, caída fuerte)."),
    ], columns=["Hora", "Qué llega"]).set_index("Hora"))
    st.caption("Para activarlos, escribe en Claude Code: ! powershell -ExecutionPolicy Bypass -File programar_revisiones.ps1")

# ---------- Qué significa cada alerta ----------
st.subheader("Qué significa cada alerta")
st.table(pd.DataFrame([
    ("🟢 COMPRAR", f"La probabilidad de subida llegó a {estrategia.UMBRAL_COMPRA}% o más, con {estrategia.MIN_CASOS}+ casos."),
    ("🟡 Pasó de 55%", "Está cerca de la señal de compra."),
    ("🔴 Bajó de 50%", "Es más probable que baje a que suba. Si lo tienes, el simulador lo vende."),
    ("⚪ Zona neutral", "Volvió a estar entre 50% y 55%."),
    ("✨ Cruce dorado / ⚠️ Cruce de la muerte", "La media de 50 días cruzó por encima / por debajo de la de 200."),
    ("📈 Sobrecompra / 📉 Sobreventa", "El RSI pasó de 70 (subió muy rápido) o bajó de 30 (cayó muy rápido)."),
    ("↕️ Cruce de la media de 200", "El precio pasó por encima o por debajo de su tendencia de largo plazo."),
    ("💥 Movimiento fuerte", "Subió o bajó 5% o más en un día."),
    (f"⚠️ Cerca del stop loss", f"Una compra va perdiendo {estrategia.STOP_LOSS - 1}% o más (el stop es -{estrategia.STOP_LOSS}%)."),
    (f"🎯 Cerca del objetivo", f"Una compra va ganando {estrategia.OBJETIVO - 1}% o más (el objetivo es +{estrategia.OBJETIVO}%)."),
    ("📅 / 📊 Evento", "Hoy o mañana hay reunión de la OPEP, de la Fed, inflación, empleo o inventarios de petróleo."),
], columns=["Alerta", "Qué significa"]).set_index("Alerta"))
st.caption("De los activos del simulador y de Mis activos te llegan todas las alertas. De los demás solo "
           "cuando llegan a COMPRAR (en un solo mensaje), para no llenarte de mensajes.")
