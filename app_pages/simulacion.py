# Simulador: juego con plata virtual (una cuenta en pesos), automático o manual

import streamlit as st

import activos
import estrategia
import simulador
import ui


@st.dialog("¿Reiniciar el simulador?")
def confirmar_reinicio(nuevo_saldo):
    st.write(f"Se borrarán **todas** las operaciones simuladas y empezarás de cero con **{ui.pesos(nuevo_saldo)}**.")
    botones = st.container(horizontal=True)
    if botones.button("Sí, reiniciar", type="primary", icon=":material/restart_alt:"):
        simulador.reiniciar(nuevo_saldo)
        st.rerun()
    if botones.button("Cancelar"):
        st.rerun()


cab = st.container(horizontal=True, vertical_alignment="center")
cab.title("Simulador")
cab.badge("SIMULACIÓN · plata virtual", icon=":material/science:", color="violet")

if not ui.puede("automatico") and simulador.modo() == "automatico":
    simulador.cambiar_modo("manual")
modos = ["automatico", "manual"] if ui.puede("automatico") else ["manual"]
if not ui.puede("automatico"):
    st.caption(":material/info: Con tu tipo de cuenta el simulador es manual. El modo automático es para "
               "inversionistas.")
modo = st.segmented_control(
    "Modo", modos, default=simulador.modo(), required=True, key="modo_sim",
    format_func=lambda m: {"automatico": "Automático (opera solo con las señales)",
                           "manual": "Manual (tú compras y vendes)"}[m],
    help="**Automático:** el simulador compra solo cuando la app dice COMPRAR y vende solo al tocar el stop loss, el "
         "objetivo o el plazo. Te avisa por Telegram cada operación con su razón y un resumen cada noche. "
         "**Manual:** tú decides cada compra y venta; la app solo sugiere.")
if modo != simulador.modo():
    simulador.cambiar_modo(modo)
    st.toast(f"Modo {modo}")

s = simulador.resumen()
fila = st.container(horizontal=True)
fila.metric("Disponible", ui.pesos(s["disponible"]), ui.dinero(s["disponible_usd"]), delta_color="off")
fila.metric("Invertido", ui.pesos(s["invertido"]), ui.dinero(s["invertido_usd"]), delta_color="off")
fila.metric("Total", ui.pesos(s["total"]), f"{s['ganancia_%']:+.2f}% · {ui.dinero(s['total_usd'])}")

with st.container(border=True):
    st.markdown(f"**Meta del mes:** pasar de {ui.pesos(s['inicial'])} a {ui.pesos(s['meta'])} "
                f"(+{simulador.config()['meta_%']}%)")
    st.progress(s["progreso_meta"], text=f"{s['progreso_meta']:.0%} de la meta · faltan {s['dias_mes']} días del mes")

with st.expander("Comisiones de Trii", icon=":material/payments:"):
    import comisiones
    c = comisiones.config()
    st.caption("Se descuentan en cada compra y venta del simulador. Cámbialas si Trii cambia sus tarifas.")
    col = st.columns(3)
    fija = col[0].number_input("Comisión fija (COP, IVA incluido)", min_value=0.0, value=float(c["fija_cop"]), step=125.0)
    limite = col[1].number_input("Hasta este monto por operación (COP)", min_value=0.0, value=float(c["limite_cop"]),
                                 step=500_000.0, format="%.0f")
    pct = col[2].number_input("Por encima: % del monto (+ IVA)", min_value=0.0, value=float(c["porcentaje"]), step=0.05)
    col = st.columns(3)
    iva = col[0].number_input("IVA (%)", min_value=0.0, value=float(c["iva"]), step=1.0)
    spread = col[1].number_input("Spread cambiario para activos en US$ (%)", min_value=0.0,
                                 value=float(c["spread_cambiario"]), step=0.1,
                                 help="Diferencia entre el dólar al que Trii te cambia y el dólar real, en cada operación.")
    if col[2].button("Guardar comisiones", icon=":material/save:"):
        comisiones.guardar(fija_cop=fija, limite_cop=limite, porcentaje=pct, iva=iva, spread_cambiario=spread)
        st.toast("Comisiones guardadas")

with st.expander("Saldo inicial y reinicio"):
    controles = st.container(horizontal=True, vertical_alignment="bottom")
    nuevo = controles.number_input("Saldo inicial (pesos)", min_value=1_000.0, value=float(s["inicial"]),
                                   step=50_000.0, format="%.0f")
    if controles.button("Cambiar saldo inicial", icon=":material/edit:"):
        confirmar_reinicio(nuevo)
    if controles.button("Reiniciar simulador", icon=":material/restart_alt:"):
        confirmar_reinicio(s["inicial"])

if modo == "automatico":
    if st.button("Correr la revisión automática ahora", icon=":material/play_arrow:",
                 help="Vende lo que tocó stop/objetivo/alerta/plazo y compra lo que dice COMPRAR "
                      f"(con el {simulador.FRACCION:.0%} del saldo total cada uno)."):
        with st.spinner("Actualizando precios y revisando señales..."):
            acciones = simulador.revisar(actualizar=True)
        st.cache_data.clear()
        hechas = [a for a in acciones if a["Tipo"] in ("COMPRA", "VENTA")]
        st.toast(f"{len(hechas)} operaciones" if hechas else "Sin compras ni ventas esta vez")
        st.rerun()

ui.formulario_simulador(simulador)

# Análisis del activo elegido en el formulario (igual que en el resto de la app)
elegido = st.session_state.get("s_act_v") if st.session_state.get("s_tipo") == "Venta" else st.session_state.get("s_act_c")
if elegido:
    with st.expander(f"Análisis de {activos.etiqueta(activos.limpiar(elegido))}: decisión, Time Machine, escenarios y "
                     "abanico", expanded=True):
        r = ui.analisis(activos.limpiar(elegido))
        ui.decision_grande(r)
        if st.button("¿Por qué esta decisión?", icon=":material/school:", key="sim_porque"):
            ui.explicar_decision(r)
        ui.abanico(activos.limpiar(elegido))
    ui.analisis_avanzado(activos.limpiar(elegido), "sim")

st.subheader("Compras abiertas")
pos = simulador.cartera.posiciones()
if pos.empty:
    st.caption(":material/info: No hay compras abiertas.")
else:
    ui.tabla_posiciones(pos, simulacion=True)
    ui.grafica_cartera(simulador.cartera, "sim", "(SIMULACIÓN)")
    ui.predicciones_cartera(simulador.cartera, "sim", "del simulador (SIMULACIÓN)")
st.caption(f"Reglas: stop loss -{estrategia.STOP_LOSS}%, objetivo +{estrategia.OBJETIVO}%, vende si la probabilidad "
           f"baja de 50% o a los {estrategia.DIAS_ADELANTE} días de mercado. Cada compra paga 0,5% de costo.")
ui.editor_operaciones(simulador.cartera, "sim")

ui.diario_errores(simulador.cartera, "Simulador", "sim")
