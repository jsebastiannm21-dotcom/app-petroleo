# app.py - Entrada de la app. Para abrirla:  streamlit run app.py
# Pantallas (carpeta app_pages): Inicio, Seguimiento (mercados y Mis activos), Simulador, Alertas
# y la página de cada activo. Barra izquierda: selector de activo + casilla "Sugerencia".
# AVISO: herramienta de análisis. No es una recomendación de inversión.

import pandas as pd
import streamlit as st

import activos
import nube
import ui
import usuarios

st.set_page_config(page_title="Análisis de mercados", page_icon=":material/monitoring:", layout="wide")

if nube.conectado():
    @st.cache_resource(ttl=1800, show_spinner="Preparando los datos del mercado (la primera vez tarda un poco)...")
    def _datos_de_la_nube():
        nube.preparar_app()                                 # Ranking, noticias y precios que dejan las tareas
        return True
    _datos_de_la_nube()
yo = usuarios.sesion()                                      # Login con Google y registro (en tu PC entra directo)
st.session_state["yo"] = yo

paginas = {
    "inicio": st.Page("app_pages/inicio.py", title="Inicio", icon=":material/home:", default=True,
                      help="Resumen de Nasdaq, petróleo y oro, el top 5 del ranking, tus activos y las alertas de hoy."),
    "seguimiento": st.Page("app_pages/seguimiento.py", title="Seguimiento", icon=":material/list:",
                           help="Lista de activos por mercado y tus compras reales (Mis activos)."),
    "simulador": st.Page("app_pages/simulacion.py", title="Simulador", icon=":material/science:",
                         help="Cuentas virtuales de 100.000 pesos que siguen la estrategia."),
    "alertas": st.Page("app_pages/avisos.py", title="Alertas", icon=":material/notifications:",
                       help="Alertas de hoy y conexión con Telegram."),
    "aprende": st.Page("app_pages/tutorial.py", title="Aprende", icon=":material/school:",
                       help="Cada análisis explicado en sencillo y con un ejemplo."),
    "activo": st.Page("app_pages/activo.py", title="Activo", icon=":material/insights:", visibility="hidden",
                      help="Página de un activo: decisión, pronóstico, simulador, calendario y ranking."),
}
pagina = st.navigation(list(paginas.values()), position="hidden")

# ---------- Barra izquierda: selector de activo y sugerencia ----------
st.session_state.setdefault("activo", activos.PRINCIPAL)
if "activo_pendiente" in st.session_state:                # Otra pantalla pidió abrir un activo
    st.session_state["activo"] = st.session_state.pop("activo_pendiente")
with st.sidebar:
    st.subheader(":material/monitoring: Análisis de mercados")
    mercados = ui.filtro_mercados("sidebar_mercados")
    activos_on = [s for s in activos.ACTIVOS if any(activos.mercado_activo(m) for m in activos.mercados(s))]
    opciones = [s for s in activos_on if not mercados or set(activos.mercados(s)) & mercados]
    filtrados = list(opciones)                              # Para el contador (antes de agregar el activo elegido)
    if st.session_state.get("activo") and st.session_state["activo"] not in opciones:
        opciones.insert(0, st.session_state["activo"])     # El activo elegido (o escrito a mano) siempre queda
    elegido = st.selectbox("Activo", opciones, format_func=activos.etiqueta, accept_new_options=True,
                           key="activo", placeholder="Elige o escribe un símbolo",
                           help=f"Escribe para buscar entre los {len(filtrados)} activos, o escribe cualquier "
                                "símbolo de Yahoo Finance (por ejemplo ECOPETROL.CL).")
    simbolo = activos.limpiar(elegido or activos.PRINCIPAL)
    try:
        r = ui.analisis(simbolo)
        ui.caja_sugerencia(r)
        if st.button("Ver página del activo", icon=":material/arrow_forward:", width="stretch"):
            ui.ir_a_activo(simbolo)
    except Exception as error:
        st.error(f"No pude analizar '{simbolo}': {error}", title="Símbolo no válido")
    with st.expander(f"¿Cuántos activos hay? ({len(filtrados)}" + (" con el filtro)" if mercados else ")")):
        tipos = pd.Series([activos.tipo_nombre(s) for s in filtrados]).value_counts()
        st.dataframe(tipos.rename_axis("Tipo").reset_index(name="Activos"), hide_index=True, alt="Activos por tipo")
        por_mercado = pd.Series([m for s in filtrados for m in activos.mercados(s)
                                 if not mercados or m in mercados]).value_counts()
        st.dataframe(por_mercado.rename(index=activos.NOMBRE_MERCADO).rename_axis("Mercado").reset_index(name="Activos"),
                     hide_index=True, alt="Activos por mercado")
        st.caption("Un activo puede estar en varios mercados (por ejemplo, el oro está en Oro, Materias primas y "
                   "Futuros), por eso la suma por mercado es mayor que el total.")
    with st.popover("Modo claro / oscuro", icon=":material/contrast:", width="stretch"):
        st.markdown(f"Ahora estás en **modo {'claro' if ui.modo_claro() else 'oscuro'}**.")
        st.markdown("Para cambiarlo: toca el menú **⋮** (arriba a la derecha) → **Settings** → **Choose app theme** "
                    "→ **Light** (claro) o **Dark** (oscuro). Streamlit no deja que un botón de la app cambie el tema; "
                    "la app recuerda tu elección.")
    st.caption("Dinero virtual y análisis del pasado. No es una recomendación de inversión.")

# ---------- Barra inferior fija ----------
with st.container(horizontal=True, horizontal_alignment="distribute", key="barra_inferior"):
    for clave in ["inicio", "seguimiento", "simulador", "alertas", "aprende"]:
        st.page_link(paginas[clave], label=paginas[clave].title, icon=paginas[clave].icon)
# Estilo HUD ciberpunk (pedido expreso): bordes que brillan, números grandes con resplandor y entrada suave.
# Revisado para celular (títulos y números más pequeños, barra que respeta el borde del iPhone) y teclado.
# Los selectores data-testid son de Streamlit; si una versión futura los cambia, solo se pierde el brillo.
claro = ui.modo_claro()
st.html("""<style>
.st-key-barra_inferior {
  position: fixed; bottom: 0; left: 0; right: 0; z-index: 999;
  background: FONDO_BARRA; border-top: 1px solid #00E5FF;
  box-shadow: 0 -2px 14px rgba(0,229,255,0.2);
  padding: 0.25rem 1rem calc(0.5rem + env(safe-area-inset-bottom)) 1rem;
}
.st-key-barra_inferior a { min-height: 44px; }        /* Zona táctil cómoda (44 px) */
[data-testid="stVerticalBlockBorderWrapper"] {
  border-color: rgba(0,229,255,0.45) !important;
  box-shadow: 0 0 8px rgba(0,229,255,0.12);
  transition: box-shadow .3s ease;
}
[data-testid="stVerticalBlockBorderWrapper"]:hover { box-shadow: 0 0 14px rgba(255,43,214,0.24); }
[data-testid="stMetricValue"] { font-size: 2rem; text-shadow: 0 0 8px rgba(0,229,255,0.35); }
h1, h2, h3 { letter-spacing: .05em; text-shadow: 0 0 10px rgba(0,229,255,0.25); }
p, li { line-height: 1.55; }
:focus-visible { outline: 2px solid #FF2BD6 !important; outline-offset: 2px; }   /* Navegar con teclado */
[data-testid="stMain"] .block-container { animation: entrada .45s ease-out; }
@keyframes entrada { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: none; } }
@media (prefers-reduced-motion: reduce) { [data-testid="stMain"] .block-container { animation: none; } }
@media (max-width: 640px) {                             /* Celular */
  h1 { font-size: 1.45rem !important; letter-spacing: .02em; }
  h2 { font-size: 1.2rem !important; letter-spacing: .02em; }
  h3, h4 { font-size: 1.05rem !important; letter-spacing: .02em; }
  [data-testid="stMetricValue"] { font-size: 1.45rem; }
  .st-key-barra_inferior { padding-left: .25rem; padding-right: .25rem; }
  .st-key-barra_inferior p { font-size: .72rem; }
}
</style>""".replace("FONDO_BARRA", "rgba(243,247,250,0.97)" if claro else "rgba(5,7,13,0.96)"))

usuarios.menu_perfil(yo)
pagina.run()
