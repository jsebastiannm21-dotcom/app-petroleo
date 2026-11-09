# Aprende: explicación sencilla y con un ejemplo de cada análisis de la app

import streamlit as st

import tutorial

st.title("Aprende")
st.caption("Cada análisis de la app explicado en sencillo y con un ejemplo. En cada sección de la app también hay un "
           "botón «¿Qué es esto?» que abre su explicación.")
for clave, (titulo, que_es, ejemplo) in tutorial.TUTORIAL.items():
    with st.expander(titulo, icon=":material/school:", expanded=clave == "time_machine"):
        st.markdown(que_es)
        st.markdown(f"**Ejemplo:** {ejemplo}")
