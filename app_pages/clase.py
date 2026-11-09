# Clase: profesores (cursos, eventos, panel, notas, Excel y anuncios), monitores (solo mirar) y estudiantes (eventos)

import secrets
from datetime import date, datetime, time, timedelta

import pandas as pd
import streamlit as st

import activos
import cursos
import nube
import ui
import usuarios

st.title("Clase")
yo = ui.yo()
correo = yo["email"]
if not nube.conectado():
    st.info("Los cursos y eventos funcionan con la app en la nube (Supabase).", icon=":material/cloud_off:")
    st.stop()
rol = usuarios.rol(yo)
es_super = rol == "superadmin"
es_profe = rol in ("profesor", "superadmin")              # Un profesor sin aprobar usa la app como estudiante
propios, acompano = cursos.cursos_que_ve(correo, es_super)
NOMBRE_MERCADO = {m: activos.NOMBRE_MERCADO[m] for m in cursos.MERCADOS}


@st.cache_data(ttl=60, show_spinner="Calculando resultados del grupo...")
def tabla(evento_id, _version):
    return cursos.tabla_evento(cursos.evento(evento_id))


def ver(e):
    return tabla(e["id"], datetime.now().strftime("%H:%M")[:4])   # Se recalcula cada ~10 minutos o al tocar "Actualizar"


def apodo_o_nombre(t):
    return t["Apodo"].where(t["Apodo"] != "", t["Estudiante"].str.split(" ").str[0])


def eventos_que_veo():
    """Eventos del profesor (o todos, para el superadmin) y los de los cursos que acompaña como monitor."""
    todos = cursos.eventos()
    mios = todos if es_super else [e for e in todos if e["profesor"] == correo]
    ids = {c["id"] for c in acompano}
    como_monitor = [e for e in todos if e not in mios and (e.get("curso_id") in ids or (
        not e.get("curso_id") and any(c["profesor"] == e["profesor"] for c in acompano)))]
    return [e for e in mios + como_monitor if not e.get("borrado")], {e["id"] for e in mios}


# ---------- Estudiante ----------
@st.dialog("Bienvenido a tu clase", width="large")
def tutorial_inicial():
    st.markdown("""
1. **Únete a tu evento** con la clave que te dio tu profesor. Puedes usar un apodo en el ranking.
2. **Elige el simulador del evento** en la barra izquierda («Simulador que estás usando»). Empiezas con el monto que
   fijó tu profesor; no se puede reiniciar.
3. **Compra y vende** desde la página de cualquier activo (botón al final) o desde el Simulador. Solo puedes usar los
   mercados abiertos de esa semana.
4. **Llena la bitácora**: por qué compras o vendes. La app anota si seguiste o no su sugerencia.
5. **Mira tu progreso** aquí: tu puesto por ganancia y por control de riesgo, tus insignias y los anuncios.
6. **¿No entiendes algo?** Pasa el mouse por las palabras subrayadas o toca «¿Qué es esto?». Todo está en «Aprende».

Es dinero ficticio y es para aprender: **no es una recomendación de inversión.**""")
    if st.button("Entendido", type="primary"):
        nube.guardar_ajuste("tutorial_visto", True, correo)
        st.rerun()


def seccion_estudiante():
    if not nube.leer_ajuste("tutorial_visto", correo):
        tutorial_inicial()
    if st.button("Ver el tutorial otra vez", icon=":material/school:", type="tertiary"):
        tutorial_inicial()
    # 12: fin del evento
    quedan = cursos.dias_para_borrar(correo)
    if quedan is not None and rol == "estudiante":
        pedido = nube.leer_ajuste("conservar", correo)
        st.warning(f"Tu evento terminó. **Tu cuenta se borrará en {quedan} días** (quedan solo estadísticas anónimas), "
                   "salvo que entres a otro evento o pidas conservarla.", icon=":material/schedule:")
        if pedido:
            st.caption(f":material/hourglass_top: Pediste conservar tu cuenta el {pedido['fecha']}: "
                       f"{'aprobado' if pedido['estado'] == 'aprobado' else 'esperando aprobación'}.")
        else:
            with st.form("conservar"):
                motivo = st.text_area("¿Por qué quieres conservar tu cuenta?", max_chars=500)
                contacto = st.checkbox("Acepto que me contacten por correo")
                if st.form_submit_button("Quiero conservar mi cuenta", type="primary"):
                    if motivo.strip():
                        cursos.pedir_conservar(correo, motivo, contacto)
                        st.rerun()
                    st.error("Cuéntanos brevemente por qué.")
    # Unirse con la clave
    with st.expander("Unirme a un evento con la clave", icon=":material/key:", expanded=not cursos.mis_eventos(correo)):
        col = st.columns([1, 1, 1], vertical_alignment="bottom")
        clave = col[0].text_input("Clave del evento", max_chars=20).strip().upper()
        apodo = col[1].text_input("Apodo para el ranking (opcional)", max_chars=30)
        e = cursos.por_clave(clave) if clave else None
        curso_id = None
        if clave and not e:
            st.caption(":material/error: No hay ningún evento con esa clave.")
        elif e and not e.get("curso_id"):
            de_profe = cursos.cursos(e["profesor"])
            curso_id = col[2].selectbox("Tu curso", [c["id"] for c in de_profe],
                                        format_func=lambda i: cursos.nombre_curso(cursos.curso(i)))
        if e and st.button(f"Unirme a «{e['nombre']}»", type="primary", icon=":material/login:"):
            error = cursos.unirse(correo, e, apodo, curso_id)
            if error:
                st.error(error)
            else:
                st.session_state["evento_activo"] = e["id"]
                st.cache_data.clear()
                st.rerun()
    for e, part in cursos.mis_eventos(correo):
        if cursos.estado(e) == "borrado":
            continue
        tarjeta_evento(e, part)


def tarjeta_evento(e, part):
    import cartera as motor
    import simulador
    est = cursos.estado(e)
    with st.container(border=True):
        cab = st.container(horizontal=True, vertical_alignment="center")
        cab.markdown(f"### {e['nombre']}")
        cab.badge(est, color={"activo": "green", "por empezar": "blue"}.get(est, "gray"))
        c = cursos.curso(part["curso"])
        inicio, fin = cursos.fechas(e)
        st.caption(f"{cursos.nombre_curso(c) if c else ''} · del {inicio:%d/%m/%Y} al {fin:%d/%m/%Y} · semana "
                   f"{cursos.semana_actual(e)} de {cursos.semanas(e)} · monto inicial {ui.pesos(float(e['monto']))} COP")
        st.markdown("**Mercados abiertos esta semana:** " + ", ".join(NOMBRE_MERCADO.get(m, m) for m in cursos.mercados_hoy(e))
                    + (f" · **Límite:** máximo {e['limite_pct']:g}% del saldo por activo" if e.get("limite_pct") else "")
                    + (" · **Bitácora obligatoria**" if e.get("bitacora_obligatoria") else ""))
        if cursos.reto_de_la_semana(e):
            st.info(cursos.reto_de_la_semana(e), title="Reto de la semana", icon=":material/flag:")
        for _, texto in cursos.anuncios(e)[:5]:
            st.markdown(texto)
        t = ver(e)
        if len(t) and correo in set(t["Correo"]):
            mi = t[t["Correo"] == correo].iloc[0]
            fila = st.container(horizontal=True)
            fila.metric("Mi saldo total", ui.pesos(mi["Valor_COP"]) + " COP", f"{mi['Rendimiento_%']:+.2f}%")
            fila.metric("Puesto por ganancia", f"{mi['Puesto_ganancia']} de {len(t)}")
            fila.metric("Puesto por control de riesgo", f"{mi['Puesto_riesgo']} de {len(t)}",
                        help=cursos.puntaje_riesgo.__doc__)
            fila.metric("Operaciones", int(mi["Operaciones"]),
                        f"aciertos {mi['Aciertos_%']:.0f}%" if pd.notna(mi["Aciertos_%"]) else None, delta_color="off")
            if est == "activo" and not mi["Opero_hoy"] and date.today().weekday() < 5:
                st.warning("Hoy no has operado en este evento.", icon=":material/notifications_active:")
            # Resumen semanal
            ops = nube.leer_operaciones(correo, cursos.cartera_de_evento(e["id"]))
            semana = pd.to_datetime(ops["Fecha"], format="mixed") >= pd.Timestamp(date.today() - timedelta(days=date.today().weekday())) \
                if len(ops) else pd.Series(dtype=bool)
            st.caption(f":material/calendar_view_week: Esta semana: {int(semana.sum()) if len(ops) else 0} operaciones · "
                       f"vas de {mi['Puesto_ganancia']} de {len(t)} por ganancia.")
            # Alertas de stop y objetivo de sus compras del evento
            pos = motor.Cartera(activos.CARPETA / "_no_usar.csv", extra=["Tasa_COP", "Costo_COP", "Origen", "Precio_COP",
                                                                          "Precio_USD"],
                                nube=(correo, cursos.cartera_de_evento(e["id"]))).posiciones()
            for _, p in pos[pos["Sugerencia"] == "Vender"].iterrows() if len(pos) else []:
                st.warning(f"{p['Activo']}: {p['Motivo']}", icon=":material/warning:")
            for icono, nombre_ins, texto in cursos.insignias(correo, t):
                st.markdown(f"{icono} **{nombre_ins}** · {texto}")
            with st.expander("Ranking del evento", icon=":material/leaderboard:"):
                rk = t.assign(Nombre=apodo_o_nombre(t)).sort_values("Puesto_ganancia")
                st.dataframe(rk[["Puesto_ganancia", "Nombre", "Rendimiento_%", "Puesto_riesgo", "Riesgo", "Operaciones"]],
                             hide_index=True, alt="Ranking del evento",
                             column_config={"Puesto_ganancia": "Puesto (ganancia)", "Puesto_riesgo": "Puesto (riesgo)",
                                            "Rendimiento_%": st.column_config.NumberColumn("Rendimiento", format="%+.2f%%"),
                                            "Riesgo": st.column_config.ProgressColumn("Control de riesgo", min_value=0,
                                                                                      max_value=100, format="%.0f")})
        if est != "terminado" and st.button("Usar el simulador de este evento", key=f"usar_{e['id']}",
                                            icon=":material/play_arrow:"):
            st.session_state["evento_activo"] = e["id"]
            st.switch_page("app_pages/simulacion.py")


# ---------- Profesor ----------
def seccion_cursos():
    with st.expander("Crear un curso", icon=":material/add:", expanded=not propios):
        with st.form("nuevo_curso", clear_on_submit=True):
            universidad = st.selectbox("Universidad *", usuarios.UNIVERSIDADES, index=None, placeholder="Elige")
            col = st.columns(2)
            materia = col[0].text_input("Materia *", placeholder="Finanzas Internacionales")
            grupo = col[1].text_input("Grupo (opcional)", placeholder="A")
            jornada = st.segmented_control("Jornada *", cursos.JORNADAS)
            dias = st.pills("Días *", cursos.DIAS, selection_mode="multi")
            col = st.columns(3)
            ini = col[0].time_input("Hora de inicio *", value=time(7, 0))
            fin = col[1].time_input("Hora de fin *", value=time(9, 0))
            semestre = col[2].selectbox("Semestre *", cursos.semestres())
            if st.form_submit_button("Crear curso", type="primary"):
                if not (universidad and materia.strip() and jornada and dias and semestre) or fin <= ini:
                    st.error("Llena los campos con * (y la hora de fin debe ser después de la de inicio).")
                else:
                    c = cursos.crear_curso(correo, {"universidad": universidad, "materia": materia.strip(),
                                                    "grupo": grupo.strip(), "jornada": jornada, "dias": dias,
                                                    "hora_inicio": ini.strftime("%H:%M"), "hora_fin": fin.strftime("%H:%M"),
                                                    "semestre": semestre})
                    st.toast(f"Curso creado: {cursos.nombre_curso(c)}")
                    st.rerun()
    if propios:
        st.dataframe(pd.DataFrame([{"Curso": cursos.nombre_curso(c), "Universidad": c["universidad"],
                                    "Horario": f"{', '.join(c['dias'])} · {c['hora_inicio']} a {c['hora_fin']}",
                                    "Monitores": ", ".join(c.get("monitores", []))} for c in propios]),
                     hide_index=True, alt="Mis cursos")
        st.markdown("**Monitores** (ven el curso, pero no cambian reglas)")
        col = st.columns([2, 2, 1], vertical_alignment="bottom")
        cid = col[0].selectbox("Curso", [c["id"] for c in propios], format_func=lambda i: cursos.nombre_curso(cursos.curso(i)),
                               key="mon_curso")
        nuevo = col[1].text_input("Correo de Google del monitor", key="mon_correo").strip().lower()
        if col[2].button("Agregar monitor") and "@" in nuevo:
            c = cursos.curso(cid)
            cursos.guardar_curso({**c, "monitores": sorted(set(c.get("monitores", [])) | {nuevo})})
            st.rerun()
        c = cursos.curso(cid)
        for m in c.get("monitores", []):
            fila = st.container(horizontal=True, vertical_alignment="center")
            fila.markdown(f"- {m}")
            if fila.button("Quitar", key=f"quitar_{cid}_{m}", type="tertiary"):
                cursos.guardar_curso({**c, "monitores": [x for x in c["monitores"] if x != m]})
                st.rerun()
    if acompano:
        st.markdown("**Cursos que acompañas como monitor:** " + "; ".join(cursos.nombre_curso(c) for c in acompano))


def seccion_eventos(mios):
    if not propios:
        st.caption("Primero crea un curso.")
        return
    with st.expander("Crear un evento", icon=":material/add:", expanded=not mios):
        with st.form("nuevo_evento"):
            nombre = st.text_input("Nombre del evento *", placeholder="Reto de inversión 2026-2")
            alcance = st.segmented_control("¿Para quién? *", ["Un curso", "Todos mis cursos"], default="Un curso")
            cid = st.selectbox("Curso (si es para un curso)", [c["id"] for c in propios],
                               format_func=lambda i: cursos.nombre_curso(cursos.curso(i)))
            col = st.columns(3)
            clave = col[0].text_input("Clave de acceso *", value=st.session_state.setdefault(
                "clave_sugerida", secrets.token_hex(3).upper()), max_chars=20)
            inicio = col[1].date_input("Inicio *", value=date.today(), format="DD/MM/YYYY")
            fin = col[2].date_input("Fin *", value=date.today() + timedelta(weeks=8), format="DD/MM/YYYY")
            col = st.columns(2)
            monto = col[0].number_input("Monto inicial fijo (COP) *", min_value=100_000.0, value=10_000_000.0,
                                        step=1_000_000.0, format="%.0f",
                                        help="Con montos pequeños, la comisión fija de Trii pesa muchísimo.")
            limite = col[1].number_input("Límite por activo (% del saldo, 0 = sin límite)", min_value=0, max_value=100,
                                         value=30)
            mercados = st.multiselect("Mercados permitidos *", list(NOMBRE_MERCADO), format_func=NOMBRE_MERCADO.get,
                                      default=["colombia", "eeuu", "materias", "cripto"])
            obligatoria = st.checkbox("La bitácora es obligatoria al comprar y vender")
            auto = st.checkbox("Anuncios automáticos del calendario", value=True)
            if st.form_submit_button("Crear evento", type="primary"):
                if not (nombre.strip() and clave.strip() and mercados) or fin < inicio:
                    st.error("Llena los campos con * (y el fin debe ser después del inicio).")
                elif not cursos.clave_libre(clave):
                    st.error("Esa clave ya existe: usa otra.")
                else:
                    cursos.crear_evento(correo, {"nombre": nombre.strip(), "curso_id": cid if alcance == "Un curso" else None,
                                                 "clave_acceso": clave, "inicio": str(inicio), "fin": str(fin),
                                                 "monto": float(monto), "limite_pct": int(limite), "mercados": mercados,
                                                 "bitacora_obligatoria": obligatoria, "anuncios_auto": auto})
                    st.session_state.pop("clave_sugerida", None)
                    st.rerun()
    propios_ev = [e for e in mios if e["profesor"] == correo or es_super]
    if not propios_ev:
        return
    e = cursos.evento(st.selectbox("Evento", [x["id"] for x in propios_ev],
                                   format_func=lambda i: next(x["nombre"] for x in propios_ev if x["id"] == i), key="ev_edit"))
    st.caption(f"Clave de acceso: **{e['clave_acceso']}** · {len(cursos.participantes(e['id']))} estudiantes · "
               f"{'un curso' if e.get('curso_id') else 'todos tus cursos'} · {cursos.estado(e)}")
    with st.form(f"plan_{e['id']}"):
        st.markdown("**Plan por semanas** (qué mercados se abren cada semana) **y retos semanales**")
        plan, retos = {}, {}
        for n in range(1, cursos.semanas(e) + 1):
            col = st.columns([2, 3])
            plan[str(n)] = col[0].multiselect(f"Semana {n}", e["mercados"], format_func=NOMBRE_MERCADO.get,
                                              default=(e.get("plan") or {}).get(str(n), e["mercados"]), key=f"pl_{e['id']}_{n}")
            retos[str(n)] = col[1].text_input(f"Reto de la semana {n}", value=(e.get("retos") or {}).get(str(n), ""),
                                              key=f"re_{e['id']}_{n}", placeholder="Ej.: compra un activo de Colombia")
        if st.form_submit_button("Guardar plan y retos", type="primary"):
            cursos.guardar_evento({**e, "plan": {k: v for k, v in plan.items() if v}, "retos": {k: v for k, v in retos.items() if v}})
            st.toast("Plan guardado")
    with st.expander("Duplicar este evento como plantilla", icon=":material/content_copy:"):
        col = st.columns(3)
        nueva = col[0].text_input("Clave nueva", value=secrets.token_hex(3).upper(), key=f"dup_clave_{e['id']}")
        d_ini = col[1].date_input("Inicio", value=date.today(), key=f"dup_ini_{e['id']}", format="DD/MM/YYYY")
        d_fin = col[2].date_input("Fin", value=date.today() + timedelta(weeks=8), key=f"dup_fin_{e['id']}", format="DD/MM/YYYY")
        if st.button("Duplicar", key=f"dup_{e['id']}"):
            if not cursos.clave_libre(nueva):
                st.error("Esa clave ya existe.")
            else:
                cursos.duplicar_evento(e, nueva, d_ini, d_fin)
                st.rerun()


def elegir_evento(lista, clave):
    if not lista:
        st.caption("Todavía no hay eventos.")
        return None
    return cursos.evento(st.selectbox("Evento", [x["id"] for x in lista], key=clave,
                                      format_func=lambda i: next(x["nombre"] for x in lista if x["id"] == i)))


def filtrar_por_curso(t, clave):
    """Varios cursos por separado: el profesor elige cuál mirar. El monitor solo ve los cursos que acompaña."""
    if t.empty:
        return t
    if not es_profe or (acompano and not propios):
        t = t[t["Curso"].isin([cursos.nombre_curso(c) for c in acompano])]
    opciones = sorted(t["Curso"].unique())
    if len(opciones) > 1:
        elegido = st.segmented_control("Curso", ["Todos"] + opciones, default="Todos", key=clave)
        if elegido != "Todos":
            t = t[t["Curso"] == elegido]
    return t


def seccion_panel(lista):
    e = elegir_evento(lista, "panel_ev")
    if not e:
        return
    if st.button("Actualizar", icon=":material/refresh:", type="tertiary"):
        st.cache_data.clear()
    t = filtrar_por_curso(ver(e), "panel_curso")
    if t.empty:
        st.caption(f"Nadie se ha unido todavía. Clave de acceso: **{e['clave_acceso']}**")
        return
    fila = st.container(horizontal=True)
    fila.metric("Estudiantes", len(t))
    fila.metric("Operaron hoy", f"{int(t['Opero_hoy'].sum())} de {len(t)}")
    fila.metric("Rendimiento promedio", f"{t['Rendimiento_%'].mean():+.2f}%")
    fila.metric("Control de riesgo promedio", f"{t['Riesgo'].mean():.0f}/100", help=cursos.puntaje_riesgo.__doc__)
    fila.metric("Nota promedio", f"{t['Nota'].mean():.1f}")
    no_hoy = t[~t["Opero_hoy"]]
    if len(no_hoy):
        st.caption(":material/person_off: Hoy no han operado: " + ", ".join(apodo_o_nombre(no_hoy)))
    st.dataframe(t.sort_values("Puesto_ganancia")[["Puesto_ganancia", "Estudiante", "Apodo", "Curso", "Opero_hoy",
                                                    "Operaciones", "Rendimiento_%", "Riesgo", "Bitacora_%", "Siguio_%",
                                                    "Nota", "Puesto_riesgo"]],
                 hide_index=True, alt="Resultados del grupo",
                 column_config={"Puesto_ganancia": "Puesto", "Opero_hoy": st.column_config.CheckboxColumn("¿Operó hoy?"),
                                "Rendimiento_%": st.column_config.NumberColumn("Rendimiento", format="%+.2f%%"),
                                "Riesgo": st.column_config.NumberColumn("Control de riesgo", format="%.0f"),
                                "Bitacora_%": st.column_config.NumberColumn("Bitácora", format="%.0f%%"),
                                "Siguio_%": st.column_config.NumberColumn("Siguió la app", format="%.0f%%"),
                                "Puesto_riesgo": "Puesto (riesgo)"})
    st.markdown("**¿Les fue mejor siguiendo a la app o por su cuenta?**")
    comp = cursos.siguieron_vs_por_su_cuenta(e)
    if comp.empty:
        st.caption("Todavía no hay compras con bitácora.")
    else:
        st.dataframe(comp, alt="Siguieron la app vs. por su cuenta",
                     column_config={"Resultado promedio %": st.column_config.NumberColumn(format="%+.2f%%")})
    st.markdown("**Ficha de un estudiante**")
    quien = st.selectbox("Estudiante", t["Correo"], format_func=lambda c: t.loc[t["Correo"] == c, "Estudiante"].iloc[0],
                         key="ficha_est")
    f = t[t["Correo"] == quien].iloc[0]
    fila = st.container(horizontal=True)
    fila.metric("Rendimiento", f"{f['Rendimiento_%']:+.2f}%")
    fila.metric("Peor operación", f"{f['Peor_%']:+.2f}%")
    fila.metric("Activo más grande", f"{f['Concentracion_%']:.0f}% del portafolio")
    fila.metric("Siguió la app", "—" if pd.isna(f["Siguio_%"]) else f"{f['Siguio_%']:.0f}%")
    ops = cursos.operaciones_evento(e)
    st.dataframe(ops[ops["Correo"] == quien].drop(columns=["Correo"]) if len(ops) else ops, hide_index=True,
                 alt="Operaciones y bitácora del estudiante",
                 column_config={"Fecha": st.column_config.DatetimeColumn(format="DD/MM/YYYY hh:mm a"),
                                "Siguio_sugerencia": st.column_config.CheckboxColumn("¿Siguió la app?")})


def seccion_notas(lista, mios_ids):
    e = elegir_evento(lista, "notas_ev")
    if not e:
        return
    puede_editar = e["id"] in mios_ids
    r = e.get("rubrica") or cursos.RUBRICA
    with st.expander("Rúbrica", icon=":material/rule:", expanded=puede_editar):
        rangos = st.data_editor(pd.DataFrame(r["rangos"], columns=["Rendimiento %", "Nota"]), num_rows="dynamic",
                                disabled=not puede_editar, key=f"rangos_{e['id']}", hide_index=True,
                                column_config={"Rendimiento %": st.column_config.NumberColumn(format="%.1f%%")})
        st.caption("Entre dos filas, la nota se calcula en proporción. Si un estudiante pierde toda la plata, la parte de "
                   "rendimiento queda en la nota mínima.")
        col = st.columns(5)
        p = r["pesos"]
        pr = col[0].number_input("Peso rendimiento (%)", 0, 100, int(p["rendimiento"]), disabled=not puede_editar)
        pk = col[1].number_input("Peso riesgo (%)", 0, 100, int(p["riesgo"]), disabled=not puede_editar)
        pb = col[2].number_input("Peso bitácora (%)", 0, 100, int(p["bitacora"]), disabled=not puede_editar)
        lo = col[3].number_input("Nota mínima", 0.0, 10.0, float(r["nota_min"]), 0.5, disabled=not puede_editar)
        hi = col[4].number_input("Nota máxima", 0.0, 10.0, float(r["nota_max"]), 0.5, disabled=not puede_editar)
        if puede_editar and st.button("Guardar rúbrica", type="primary"):
            if pr + pk + pb != 100:
                st.error("Los pesos deben sumar 100%.")
            else:
                cursos.guardar_evento({**e, "rubrica": {"rangos": rangos.dropna().values.tolist(),
                                                        "pesos": {"rendimiento": pr, "riesgo": pk, "bitacora": pb},
                                                        "nota_min": lo, "nota_max": hi}})
                st.cache_data.clear()
                st.rerun()
    t = filtrar_por_curso(ver(e), "notas_curso")
    if t.empty:
        st.caption("Sin estudiantes todavía.")
        return
    col = st.columns(3)
    unis = col[0].multiselect("Universidad", sorted(t["Universidad"].unique()))
    curs = col[1].multiselect("Curso", sorted(t["Curso"].unique()))
    jors = col[2].multiselect("Jornada", sorted(t["Jornada"].unique()))
    for columna, valores in (("Universidad", unis), ("Curso", curs), ("Jornada", jors)):
        if valores:
            t = t[t[columna].isin(valores)]
    vista = t[["Estudiante", "Apodo", "Correo", "Universidad", "Curso", "Jornada", "Operaciones", "Aciertos_%",
               "Rendimiento_%", "Valor_COP", "Riesgo", "Bitacora_%", "Siguio_%", "Nota", "Puesto_ganancia", "Puesto_riesgo"]]
    st.dataframe(vista, hide_index=True, alt="Notas del evento",
                 column_config={"Rendimiento_%": st.column_config.NumberColumn("Ganancia/pérdida", format="%+.2f%%"),
                                "Valor_COP": st.column_config.NumberColumn("Saldo final", format="$ %,.0f")})
    ops = cursos.operaciones_evento(e)
    ops = ops[ops["Correo"].isin(vista["Correo"])] if len(ops) else ops
    fin = cursos.fechas(e)[1]
    if cursos.estado(e) == "terminado":
        st.warning(f"El evento terminó. Descarga tu Excel antes del {fin + timedelta(days=cursos.DIAS_GRACIA):%d/%m/%Y}: "
                   "después los datos se borran y quedan solo estadísticas anónimas.", icon=":material/schedule:")
    st.download_button("Descargar Excel", cursos.excel(vista, ops), icon=":material/download:", type="primary",
                       file_name=f"{e['nombre']} {date.today():%Y-%m-%d}.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


def seccion_anuncios(mios):
    e = elegir_evento([x for x in mios if x["profesor"] == correo or es_super], "anun_ev")
    if not e:
        return
    auto = st.toggle("Anuncios automáticos del calendario (ej. «mañana sale la inflación de EE. UU.»)",
                     value=bool(e.get("anuncios_auto")), key=f"auto_{e['id']}")
    if auto != bool(e.get("anuncios_auto")):
        cursos.guardar_evento({**e, "anuncios_auto": auto})
        st.rerun()
    with st.form(f"anuncio_{e['id']}", clear_on_submit=True):
        texto = st.text_input("Anuncio manual", max_chars=300)
        if st.form_submit_button("Publicar", type="primary") and texto.strip():
            cursos.guardar_evento({**e, "anuncios": e.get("anuncios", []) + [{"fecha": str(date.today()), "texto": texto.strip()}]})
            st.rerun()
    for i, a in enumerate(e.get("anuncios", [])):
        fila = st.container(horizontal=True, vertical_alignment="center")
        fila.markdown(f"{a['fecha']} · {a['texto']}")
        if fila.button("Borrar", key=f"borrar_an_{e['id']}_{i}", type="tertiary"):
            cursos.guardar_evento({**e, "anuncios": [x for j, x in enumerate(e["anuncios"]) if j != i]})
            st.rerun()
    st.markdown("**Así lo ven tus estudiantes ahora:**")
    for _, t in cursos.anuncios(e) or [("", "Sin anuncios por ahora.")]:
        st.markdown(t)


# ---------- Qué ve cada quien ----------
lista, mios_ids = eventos_que_veo() if (es_profe or acompano) else ([], set())
if es_profe:
    pestanas = st.tabs(["Panel", "Cursos", "Eventos", "Notas y Excel", "Anuncios", "Mis eventos"], key="clase_tab",
                       on_change="rerun")
    secciones = [lambda: seccion_panel(lista), seccion_cursos, lambda: seccion_eventos(lista),
                 lambda: seccion_notas(lista, mios_ids), lambda: seccion_anuncios(lista), seccion_estudiante]
elif acompano:
    pestanas = st.tabs(["Mis eventos", "Panel de mi curso (monitor)", "Notas (solo mirar)"], key="clase_tab", on_change="rerun")
    secciones = [seccion_estudiante, lambda: seccion_panel(lista), lambda: seccion_notas(lista, set())]
else:
    pestanas, secciones = [st.container()], [seccion_estudiante]
for pestana, seccion in zip(pestanas, secciones):
    if getattr(pestana, "open", True):
        with pestana:
            seccion()

if not es_profe:
    st.divider()
    if yo.get("rol") == "profesor":
        st.caption(":material/hourglass_top: Pediste ser profesor: el administrador debe aprobarte.")
    elif st.button("Quiero ser profesor", icon=":material/co_present:", type="tertiary"):
        nube.cliente().table("usuarios").update({"rol": "profesor", "aprobado": False}).eq("email", correo).execute()
        st.toast("Listo: el administrador debe aprobarte.")
        st.rerun()
