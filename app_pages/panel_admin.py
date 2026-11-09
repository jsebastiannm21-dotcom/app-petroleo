# Panel admin (solo el superadmin): gestión, perfiles, cifras, salud del sistema, actividad, mensajes y comunidad

import pandas as pd
import plotly.express as px
import streamlit as st

import cursos
import gestion
import nube
import ui
import usuarios

yo = ui.yo()
if usuarios.rol(yo) != "superadmin":                      # Doble candado: esta página solo existe para ti
    st.error("Esta página es solo para el superadmin.")
    st.stop()
st.title("Panel admin")
if not nube.conectado():
    st.info("El panel funciona con la app conectada a Supabase.")
    st.stop()

pestanas = st.tabs(["Gestión", "Usuarios", "Cifras", "Salud", "Actividad", "Mensajes", "Comunidad"], key="admin_tab",
                   on_change="rerun")


def gestion_general():
    col = st.columns(2)
    with col[0].container(border=True):
        st.markdown("#### :material/construction: Modo mantenimiento")
        m = gestion.mantenimiento()
        activo = st.toggle("Activar el aviso de mantenimiento", value=bool(m.get("activo")))
        mensaje = st.text_input("Mensaje para todos", value=m.get("mensaje") or "Estamos actualizando la app. "
                                                                               "Vuelve en unos minutos.")
        bloquear = st.checkbox("Además, no dejar usar la app mientras dure (tú sí entras)", value=bool(m.get("bloquear")))
        if st.button("Guardar mantenimiento", type="primary"):
            gestion.poner("mantenimiento", {"activo": activo, "mensaje": mensaje, "bloquear": bloquear}, yo["email"])
            st.rerun()
    with col[1].container(border=True):
        st.markdown("#### :material/smart_toy: Modo automático")
        encendido = gestion.automatico_global()
        nuevo = st.toggle("Modo automático encendido para todos", value=encendido,
                          help="Apagado: nadie puede usar el modo automático y las tareas de la nube no operan solas.")
        if nuevo != encendido:
            gestion.poner("automatico_global", nuevo, yo["email"])
            st.rerun()
        st.caption("Encendido" if encendido else "APAGADO para todos (incluido tu simulador).")
    with st.container(border=True):
        st.markdown("#### :material/school: Profesores, roles y cuentas a conservar")
        usuarios.panel_admin()
        pedidos = [p for p in cursos.pedidos_conservar() if p["estado"] == "pendiente"]
        if pedidos:
            st.markdown("**Pedidos de «Quiero conservar mi cuenta»** (con su desempeño en el último evento)")
            filas = []
            for p in pedidos:
                fila = {"Correo": p["email"], "Motivo": p["motivo"], "Acepta contacto": p["contacto"], "Pedido": p["fecha"]}
                eventos = cursos.mis_eventos(p["email"])
                if eventos:
                    e = max((e for e, _ in eventos), key=lambda x: x["fin"])
                    t = cursos.tabla_evento(e)
                    if len(t) and p["email"] in set(t["Correo"]):
                        f = t[t["Correo"] == p["email"]].iloc[0]
                        fila.update({"Evento": e["nombre"], "Rendimiento %": round(f["Rendimiento_%"], 2),
                                     "Aciertos %": f["Aciertos_%"], "Bitácora %": f["Bitacora_%"], "Nota": f["Nota"]})
                filas.append(fila)
            st.dataframe(pd.DataFrame(filas), hide_index=True, alt="Pedidos de conservar la cuenta")
    with st.container(border=True):
        st.markdown("#### :material/block: Bloquear cuentas")
        todos = [u["email"] for u in nube.cliente().table("usuarios").select("email").execute().data
                 if u["email"] != nube.superadmin()]
        if todos:
            col = st.columns([3, 1, 1], vertical_alignment="bottom")
            quien = col[0].selectbox("Cuenta", todos, key="bloq_quien")
            if col[1].button("Bloquear"):
                gestion.bloquear(quien, True, yo["email"])
                st.rerun()
            if col[2].button("Desbloquear"):
                gestion.bloquear(quien, False, yo["email"])
                st.rerun()
            bloqueadas = [x for x in todos if gestion.bloqueado(x)]
            st.caption("Bloqueadas: " + (", ".join(bloqueadas) if bloqueadas else "ninguna"))
        else:
            st.caption("Todavía no hay otras cuentas.")
    with st.container(border=True):
        st.markdown("#### :material/account_balance: Lista de universidades")
        lista = gestion.universidades(usuarios.UNIVERSIDADES)
        editada = st.data_editor(pd.DataFrame({"Universidad": lista}), num_rows="dynamic", hide_index=True,
                                 key="unis", height=300)
        col = st.columns(2)
        if col[0].button("Guardar lista", type="primary"):
            gestion.poner("universidades", [u.strip() for u in editada["Universidad"].dropna() if u.strip()], yo["email"])
            st.rerun()
        if col[1].button("Volver a la lista original"):
            gestion.poner("universidades", None, yo["email"])
            st.rerun()
    with st.container(border=True):
        st.markdown("#### :material/send: Telegram de admin (segundo bot, solo para ti)")
        token, chat = nube.secreto("ADMIN_TELEGRAM_TOKEN"), nube.secreto("ADMIN_TELEGRAM_CHAT_ID")
        if not token:
            st.caption("Falta configurarlo: crea un segundo bot con @BotFather y pon su clave como ADMIN_TELEGRAM_TOKEN.")
        elif not chat:
            st.caption("Escríbele «hola» a tu bot de admin y toca el botón.")
            if st.button("Buscar mi chat"):
                st.code(gestion.chat_del_bot_admin() or "No encontré mensajes: escríbele «hola» primero.")
        else:
            st.caption("Conectado: te avisa si la app se cae o se pone lenta, si una fuente falla y los mensajes de contacto.")
            if st.button("Enviar prueba"):
                st.toast("Enviado" if gestion.alerta_admin("✅ Prueba del bot de admin.") else "No se pudo enviar")


def perfiles():
    import simulador
    gente = nube.cliente().table("usuarios").select("email,nombre,rol,institucion,creado").execute().data
    if not gente:
        st.caption("Todavía no hay usuarios registrados.")
        return
    filas = []
    for u in gente:
        ops, r = gestion.perfil(u["email"])
        marca = nube.USUARIO.set(u["email"])
        try:
            s = simulador.resumen()
            rend = s["ganancia_%"]
        except Exception:
            rend = None
        finally:
            nube.USUARIO.reset(marca)
        filas.append({"Nombre": u["nombre"], "Correo": u["email"], "Rol": u["rol"], "Institución": u["institucion"],
                      "Operaciones": r.get("operaciones", 0), "Rendimiento simulador %": rend,
                      "Ganancia promedio": r.get("ganancia_promedio"), "Pérdida promedio": r.get("perdida_promedio"),
                      "Última operación": r.get("ultima"), "Desde": str(u["creado"])[:10],
                      "Bloqueada": gestion.bloqueado(u["email"])})
    t = pd.DataFrame(filas)
    st.dataframe(t, hide_index=True, alt="Perfiles de todos los usuarios",
                 column_config={"Rendimiento simulador %": st.column_config.NumberColumn(format="%+.2f%%"),
                                "Ganancia promedio": st.column_config.NumberColumn(format="$ %,.0f"),
                                "Pérdida promedio": st.column_config.NumberColumn(format="$ %,.0f")})
    quien = st.selectbox("Ver las compras de", t["Correo"], key="perfil_de")
    ops, _ = gestion.perfil(quien)
    st.dataframe(ops, hide_index=True, alt="Operaciones del usuario")


def cifras():
    c = gestion.cifras()
    fila = st.container(horizontal=True)
    fila.metric("Usuarios registrados", c["usuarios"])
    fila.metric("Activos hoy", c["activos_hoy"])
    fila.metric("Activos esta semana", c["activos_semana"])
    fila.metric("Vuelven (2 días o más)", c["vuelven"])
    fila.metric("Nunca operaron", c["nunca_operaron"])
    fila = st.container(horizontal=True)
    fila.metric("Compras hoy", c["compras_hoy"])
    fila.metric("Ventas hoy", c["ventas_hoy"])
    fila.metric("Ganancia promedio por venta", ui.pesos(c["ganancia_promedio"]) + " COP")
    fila.metric("Pérdida promedio por venta", ui.pesos(c["perdida_promedio"]) + " COP")
    st.markdown("**Uso de las predicciones** (veces que se abrieron)")
    st.dataframe(pd.DataFrame(list(c["uso_predicciones"].items()), columns=["Función", "Veces"]), hide_index=True,
                 alt="Uso de las predicciones")
    col = st.columns(2)
    col[0].markdown("**Activos por tipo**")
    col[0].bar_chart(pd.Series(c["activos_por_tipo"]), horizontal=True, alt="Activos por tipo")
    if len(c["visitas_por_dia"]):
        col[1].markdown("**Usuarios por día**")
        col[1].line_chart(c["visitas_por_dia"], alt="Usuarios por día")
    if len(c["operaciones_por_dia"]):
        st.markdown("**Compras y ventas por día**")
        st.bar_chart(c["operaciones_por_dia"], alt="Compras y ventas por día")


def salud():
    s = ui.salud()
    tiempos = pd.DataFrame(list(s["tiempos"]))
    st.markdown("#### Velocidad de las páginas (desde el último arranque de la app)")
    if len(tiempos):
        resumen = tiempos.groupby("pagina")["segundos"].agg(["count", "mean", "max"]).round(2)
        st.dataframe(resumen.rename(columns={"count": "Visitas", "mean": "Promedio (s)", "max": "Más lenta (s)"}),
                     alt="Velocidad por página")
    else:
        st.caption("Sin datos todavía.")
    st.markdown("#### Errores recientes")
    errores = pd.DataFrame(list(s["errores"]))
    st.dataframe(errores, hide_index=True, alt="Errores recientes") if len(errores) else st.caption("Ninguno. 🎉")
    st.markdown("#### Fuentes de datos")
    if st.button("Revisar las fuentes ahora", icon=":material/network_check:"):
        st.session_state["fuentes"] = gestion.revisar_fuentes()
    for n, (ok, seg, detalle) in st.session_state.get("fuentes", {}).items():
        st.markdown(f"{'🟢' if ok else '🔴'} **{n}**: {seg} s · {detalle}")
    st.caption("La vigilancia de la nube las revisa cada 30 minutos y te avisa por el Telegram de admin si alguna cae.")
    st.markdown("#### Límites gratis")
    lim = gestion.limites()
    st.dataframe(pd.DataFrame([{"Servicio": k, "Uso": "—" if v is None else str(v)} for k, v in lim.items()]),
                 hide_index=True, alt="Uso de los límites gratis")
    st.caption("Lo que la app no puede medir sola (descargas de Supabase, consumo detallado) está en: "
               "[Supabase → Usage](https://supabase.com/dashboard/org/_/usage) · "
               "[GitHub → Actions](https://github.com/jsebastiannm21-dotcom/app-petroleo/actions) · "
               "[Streamlit → tus apps](https://share.streamlit.io).")


def actividad():
    t = gestion.actividad(30)
    if t.empty:
        st.caption("Todavía no hay actividad registrada.")
        return
    quien = st.multiselect("Quién", sorted(t["quien"].unique()))
    st.dataframe(t[t["quien"].isin(quien)] if quien else t, hide_index=True, alt="Registro de actividad")


def mensajes_():
    t = gestion.mensajes()
    if t.empty:
        st.caption("No hay mensajes.")
        return
    st.metric("Sin leer", int((~t["leido"]).sum()))
    for _, m in t.iterrows():
        with st.container(border=True):
            st.markdown(f"{'🐞' if m['tipo'] == 'Problema' else '✉️'} **{m['tipo']}** · {m['fecha']} · {m['nombre']} "
                        f"({m['persona']}) · {m['correo']}" + ("" if m["leido"] else " · :orange[nuevo]"))
            st.markdown(m["texto"])
            if m.get("pagina"):
                st.caption(f"Pantalla: {m['pagina']}")
            if not m["leido"] and st.button("Marcar como leído", key=f"leido_{m['clave']}"):
                gestion.marcar_leido(m["clave"])
                st.rerun()


def comunidad_():
    ui.tarjeta_comunidad()
    pct, n, usar, texto = ui.comunidad()
    if n:
        st.bar_chart(pct.rename(index=lambda m: ui.activos.NOMBRE_MERCADO.get(m, m)), horizontal=True,
                     alt="Compras de la comunidad por mercado")
    st.caption("Es anónimo y agregado: nunca muestra quién compró. Solo entra como señal extra en la explicación de "
               "las decisiones si el backtest demuestra que mejora los aciertos.")


for pestana, seccion in zip(pestanas, [gestion_general, perfiles, cifras, salud, actividad, mensajes_, comunidad_]):
    if pestana.open:
        with pestana:
            seccion()
