# Modo presentación (solo el superadmin): las cifras generales en grande, con gráficas animadas, para proyectar

import pandas as pd
import plotly.express as px
import streamlit as st

import gestion
import nube
import ui
import usuarios

if usuarios.rol(ui.yo()) != "superadmin":
    st.error("Esta página es solo para el superadmin.")
    st.stop()
if not nube.conectado():
    st.info("El modo presentación funciona con la app conectada a Supabase.")
    st.stop()
# Números grandes para proyectar (pedido expreso de estilo; solo dentro de esta página)
st.html("""<style>.st-key-proyectar [data-testid="stMetricValue"] { font-size: 4.2rem; }
.st-key-proyectar [data-testid="stMetricLabel"] p { font-size: 1.3rem; }</style>""")
st.title("Análisis de mercados en cifras")
st.caption("Herramienta educativa con dinero ficticio · se actualiza sola cada minuto · pantalla completa: F11")


@st.fragment(run_every=60)
def cifras_en_grande():
    c = gestion.cifras()
    with st.container(key="proyectar"):
        fila = st.container(horizontal=True)
        fila.metric("Usuarios", c["usuarios"])
        fila.metric("Activos hoy", c["activos_hoy"])
        fila.metric("Esta semana", c["activos_semana"])
        fila.metric("Vuelven", c["vuelven"])
        fila = st.container(horizontal=True)
        fila.metric("Compras hoy", c["compras_hoy"])
        fila.metric("Ventas hoy", c["ventas_hoy"])
        fila.metric("Activos analizados", sum(c["activos_por_tipo"].values()))
        fila.metric("Usos de predicciones", sum(c["uso_predicciones"].values()))
    col = st.columns(2)
    tipos = pd.DataFrame(list(c["activos_por_tipo"].items()), columns=["Tipo", "Activos"])
    # Animación: las barras crecen desde cero (cuadros de la animación con el total cada vez mayor)
    cuadros = pd.concat([tipos.assign(Activos=tipos["Activos"] * k / 10, Paso=k) for k in range(1, 11)])
    fig = px.bar(cuadros, x="Activos", y="Tipo", orientation="h", animation_frame="Paso", range_x=[0, tipos["Activos"].max() * 1.1],
                 color="Tipo", color_discrete_sequence=ui.PALETA)
    fig.layout.updatemenus[0].buttons[0].args[1]["frame"]["duration"] = 80
    col[0].plotly_chart(ui.estilo(fig, 420, leyenda=False), width="stretch", key="pres_tipos")
    visitas = c["visitas_por_dia"]
    if len(visitas):
        v = visitas.reset_index()
        v.columns = ["Día", "Usuarios"]
        cuadros = pd.concat([v.iloc[: i + 1].assign(Paso=i) for i in range(len(v))])
        fig = px.line(cuadros, x="Día", y="Usuarios", animation_frame="Paso", markers=True,
                      range_y=[0, max(1, v["Usuarios"].max()) * 1.2], range_x=[v["Día"].min(), v["Día"].max()])
        col[1].plotly_chart(ui.estilo(fig, 420, leyenda=False), width="stretch", key="pres_visitas")
    else:
        col[1].caption("La gráfica de usuarios por día aparece cuando haya visitas.")


cifras_en_grande()
