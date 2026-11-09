# app.py - Entrada de la app. Para abrirla:  streamlit run app.py
# Pantallas (carpeta app_pages): Inicio, Seguimiento (mercados y Mis activos), Simulador, Alertas
# y la página de cada activo. Barra izquierda: selector de activo + casilla "Sugerencia".
# AVISO: herramienta de análisis. No es una recomendación de inversión.

import time
from datetime import datetime

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


@st.cache_data(ttl=60, show_spinner=False)
def _mis_eventos(email):
    import cursos
    return [(e, p) for e, p in cursos.mis_eventos(email) if cursos.estado(e) != "borrado"]


if nube.conectado():                                        # Simulador del evento (cada evento tiene el suyo)
    mios = _mis_eventos(yo["email"])
    if mios:
        nombres_ev = {"personal": "Mi simulador personal", **{e["id"]: e["nombre"] for e, _ in mios}}
        if "evento_activo" not in st.session_state and usuarios.rol(yo) == "estudiante":
            st.session_state["evento_activo"] = mios[0][0]["id"]    # Al estudiante le abre su evento
        if st.session_state.get("evento_activo") not in nombres_ev:
            st.session_state["evento_activo"] = "personal"
        elegido_ev = st.sidebar.selectbox("Simulador que estás usando", list(nombres_ev), format_func=nombres_ev.get,
                                          key="evento_activo", help="Cada evento tiene su propio simulador, separado.")
        if elegido_ev != "personal":
            nube.EVENTO.set(next(e for e, _ in mios if e["id"] == elegido_ev))

paginas = {
    "inicio": st.Page("app_pages/inicio.py", title="Inicio", icon=":material/home:", default=True,
                      help="Resumen de Nasdaq, petróleo y oro, el top 5 del ranking, tus activos y las alertas de hoy."),
    "seguimiento": st.Page("app_pages/seguimiento.py", title="Seguimiento", icon=":material/list:",
                           help="Listas de activos por mercado, bolsas, dividendos y cierres semanales."),
    "simulador": st.Page("app_pages/simulacion.py", title="Simulador", icon=":material/science:",
                         help="Cuentas virtuales de 100.000 pesos que siguen la estrategia."),
    "alertas": st.Page("app_pages/avisos.py", title="Alertas", icon=":material/notifications:",
                       help="Alertas de hoy y qué significa cada una."),
    "clase": st.Page("app_pages/clase.py", title="Clase", icon=":material/groups:",
                     help="Cursos, eventos, ranking del grupo y panel del profesor."),
    "aprende": st.Page("app_pages/tutorial.py", title="Aprende", icon=":material/school:",
                       help="Cada análisis explicado en sencillo y con un ejemplo."),
    "legal": st.Page("app_pages/legal.py", title="Términos y privacidad", icon=":material/gavel:",
                     help="Términos de uso y política de tratamiento de datos (ley colombiana)."),
    "activo": st.Page("app_pages/activo.py", title="Activo", icon=":material/insights:", visibility="hidden",
                      help="Página de un activo: decisión, pronóstico, simulador, calendario y ranking."),
}
if usuarios.rol(yo) == "superadmin":                       # Páginas que solo existen para el superadmin
    paginas["admin"] = st.Page("app_pages/panel_admin.py", title="Panel admin", icon=":material/admin_panel_settings:")
    paginas["presentacion"] = st.Page("app_pages/presentacion.py", title="Presentación", icon=":material/slideshow:")
pagina = st.navigation(list(paginas.values()), position="hidden")
st.session_state["pagina_actual"] = pagina.title

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
    if "admin" in paginas:
        st.page_link(paginas["admin"], label="Panel admin", icon=":material/admin_panel_settings:")
        st.page_link(paginas["presentacion"], label="Modo presentación", icon=":material/slideshow:")
    usuarios.botones_ayuda(yo)
    st.page_link(paginas["legal"], label="Términos y privacidad", icon=":material/gavel:")
    st.caption("Dinero virtual y análisis del pasado. No es una recomendación de inversión.")

# ---------- Barra inferior fija ----------
with st.container(horizontal=True, horizontal_alignment="distribute", key="barra_inferior"):
    for clave in ["inicio", "seguimiento", "simulador", "clase", "alertas", "aprende"]:
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
st.caption(":material/gavel: **Herramienta educativa con dinero ficticio. No es una recomendación de inversión.**",
           text_alignment="right")

clarity = nube.secreto("CLARITY_ID") or "zavfkzec2r"   # Project ID de Microsoft Clarity (no es secreto: va en la página)
if clarity and nube.conectado():                            # Microsoft Clarity (gratis): analítica de uso anónima
    st.html(f"""<script>(function(c,l,a,r,i,t,y){{c[a]=c[a]||function(){{(c[a].q=c[a].q||[]).push(arguments)}};
t=l.createElement(r);t.async=1;t.src="https://www.clarity.ms/tag/"+i;y=l.getElementsByTagName(r)[0];
y.parentNode.insertBefore(t,y);}})(window,document,"clarity","script","{clarity}");</script>""",
            unsafe_allow_javascript=True)


_inicio = time.time()
try:
    pagina.run()
except Exception as _error:                                 # Se anota y se avisa; Streamlit igual muestra el error
    import traceback

    import gestion
    ui.salud()["errores"].append({"fecha": f"{datetime.now():%Y-%m-%d %H:%M:%S}", "pagina": pagina.title,
                                "error": f"{type(_error).__name__}: {_error}"[:300],
                                "detalle": traceback.format_exc()[-1500:]})
    gestion.registrar(yo["email"], f"Error en {pagina.title}", f"{type(_error).__name__}: {_error}"[:300])
    gestion.alerta_admin(f"❌ Error en la página {pagina.title}: {type(_error).__name__}: {_error}"[:600])
    st.error("Algo salió mal en esta pantalla. Ya le avisamos al administrador. Intenta de nuevo en un momento o "
             "usa «Reportar problema» en la barra izquierda.", title="Lo sentimos", icon=":material/error:")
    if usuarios.rol(yo) == "superadmin":                    # Solo tú ves el detalle técnico
        with st.expander("Detalle técnico (solo superadmin)"):
            st.code(traceback.format_exc()[-3000:])
finally:
    _seg = time.time() - _inicio
    _s = ui.salud()
    _s["tiempos"].append({"fecha": f"{datetime.now():%Y-%m-%d %H:%M:%S}", "pagina": pagina.title, "segundos": round(_seg, 2)})
    if _seg > 20 and time.time() - _s["avisados"].get(pagina.title, 0) > 3600:   # Lenta: máximo un aviso por hora
        _s["avisados"][pagina.title] = time.time()
        __import__("gestion").alerta_admin(f"🐢 La página {pagina.title} tardó {_seg:.0f} segundos en cargar.")
