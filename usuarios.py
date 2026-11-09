# usuarios.py - Login con Google (el oficial de Streamlit), roles, registro y menú de perfil.
# Roles: superadmin (tú) · profesor (lo apruebas tú) · estudiante (simulador manual) · inversionista (todo el
# análisis y simulador manual y automático). Cada usuario tiene su propio simulador.
# Sin login configurado (la app en tu PC), entras directo como superadmin.

import pandas as pd
import streamlit as st

import nube

ROLES = {"estudiante": "Estudiante", "inversionista": "Inversionista", "profesor": "Profesor"}
UNIVERSIDADES = sorted([
    "Universidad Nacional de Colombia", "Universidad de los Andes", "Pontificia Universidad Javeriana",
    "Universidad del Rosario", "Universidad Externado de Colombia", "Universidad de La Sabana",
    "Universidad EAN", "Universidad Sergio Arboleda", "Universidad Central", "Universidad Militar Nueva Granada",
    "Universidad Distrital Francisco José de Caldas", "Universidad Pedagógica Nacional", "Universidad de La Salle",
    "Universidad Santo Tomás", "Universidad Piloto de Colombia", "Universidad Jorge Tadeo Lozano",
    "Universidad Católica de Colombia", "Universidad Antonio Nariño", "Universidad El Bosque",
    "Universidad de América", "Universidad Libre", "Universidad Cooperativa de Colombia", "Universidad ECCI",
    "Universidad Manuela Beltrán", "Politécnico Grancolombiano", "Escuela Colombiana de Ingeniería Julio Garavito",
    "Fundación Universitaria Konrad Lorenz", "CESA - Colegio de Estudios Superiores de Administración",
    "Universidad Nacional Abierta y a Distancia (UNAD)", "Uniminuto", "Fundación Universitaria del Área Andina",
    "Universidad INCCA de Colombia", "Universidad Agustiniana", "Universidad de San Buenaventura",
    "Fundación Universitaria Los Libertadores", "Unipanamericana", "Corporación Unificada Nacional (CUN)",
    "SENA"]) + ["Otra institución", "No estudio actualmente"]
GENEROS = ["Mujer", "Hombre", "No binario", "Prefiero no decirlo"]
TERMINOS = """**Términos de uso.** Esta app es una herramienta educativa de análisis de mercados. Todo lo que muestra son
análisis del pasado y simulaciones con dinero virtual: **no es una recomendación de inversión** ni asesoría financiera.
Las decisiones que tomes con tu dinero real son tuyas.

**Autorización de tratamiento de datos personales (Ley 1581 de 2012 y Decreto 1377 de 2013).** Autorizo al
administrador de la app a recoger y guardar mi correo, nombre, institución y, si los doy, mi género y edad, con estas
finalidades: crear y administrar mi cuenta, guardar mi simulador y hacer estadísticas educativas sin identificarme.
Mis datos se guardan en un servidor seguro (Supabase) y no se venden ni se comparten con terceros. Como titular puedo
**conocer, actualizar, rectificar y pedir que se borren** mis datos, y revocar esta autorización, escribiendo al
correo del administrador. Los datos opcionales (género y edad) son voluntarios. No se recogen datos sensibles."""


def login_configurado():
    try:
        return "auth" in st.secrets
    except Exception:
        return False


def obtener(email):
    filas = nube.cliente().table("usuarios").select("*").eq("email", email).execute().data
    return filas[0] if filas else None


def rol(u):
    """Rol con el que se usa la app. Un profesor sin aprobar usa la app como estudiante mientras tanto."""
    if u["email"] == nube.superadmin():
        return "superadmin"
    if u["rol"] == "profesor" and not u.get("aprobado"):
        return "estudiante"
    return u["rol"]


def puede(u, que):
    permisos = {"mis_activos": {"superadmin"}, "admin": {"superadmin"}, "actualizar": {"superadmin"},
                "automatico": {"superadmin", "inversionista"}}
    return rol(u) in permisos[que]


def _registro(email):
    """La primera vez: nombre, institución, rol, opcionales y aceptación de términos y datos."""
    st.title("Bienvenido")
    st.caption(f"Entraste como {email}. Completa tu registro (solo esta vez).")
    with st.form("registro"):
        nombre = st.text_input("Nombre completo *", value=getattr(st.user, "name", "") or "")
        institucion = st.selectbox("Institución *", UNIVERSIDADES, index=None, placeholder="Elige tu universidad")
        tipo = st.segmented_control("¿Cómo vas a usar la app? *", list(ROLES), format_func=ROLES.get, default="estudiante",
                                    help="Estudiante: simulador manual. Inversionista: todo el análisis y simulador "
                                         "manual y automático. Profesor: el administrador debe aprobarte.")
        col = st.columns(2)
        genero = col[0].selectbox("Género (opcional)", GENEROS, index=None, placeholder="Opcional")
        edad = col[1].number_input("Edad (opcional)", min_value=0, max_value=110, value=None, step=1, placeholder="Opcional")
        with st.expander("Leer los términos y la autorización de datos"):
            st.markdown(TERMINOS)
        terminos = st.checkbox("Acepto los términos de uso *")
        datos = st.checkbox("Autorizo el tratamiento de mis datos personales (Ley 1581 de 2012) *")
        contacto = st.checkbox("Acepto que me contacten por correo (opcional)")
        if st.form_submit_button("Crear mi cuenta", type="primary"):
            if not nombre.strip() or not institucion or not tipo:
                st.error("Falta tu nombre, tu institución o cómo vas a usar la app.")
            elif not (terminos and datos):
                st.error("Para crear la cuenta debes aceptar los términos y la autorización de datos.")
            else:
                nube.cliente().table("usuarios").insert({
                    "email": email, "nombre": nombre.strip(), "institucion": institucion, "genero": genero,
                    "edad": int(edad) if edad else None, "rol": tipo, "aprobado": tipo != "profesor",
                    "acepta_terminos": True, "acepta_datos": True, "acepta_contacto": contacto}).execute()
                st.rerun()


def sesion():
    """Pide el login con Google y el registro. Devuelve el usuario (dict) con su rol, o detiene la página."""
    if not login_configurado() or not nube.conectado():
        return {"email": nube.superadmin(), "nombre": "Superadmin (este PC)", "rol": "superadmin", "aprobado": True}
    if not st.user.is_logged_in:
        st.title("Análisis de mercados")
        st.markdown("Herramienta educativa: análisis de más de 1.100 activos, predicciones y un simulador con dinero "
                    "virtual. **No es una recomendación de inversión.**")
        st.button("Entrar con Google", icon=":material/login:", type="primary", on_click=st.login, args=("google",))
        st.stop()
    email = str(st.user.email).lower()
    nube.USUARIO.set(email)                                  # De aquí en adelante, todo es de este usuario
    u = obtener(email)
    if u is None:
        _registro(email)
        st.stop()
    return u


def resumen_operaciones():
    """Activos abiertos, ganancias, pérdidas, desde cuándo opera y última operación (de su simulador)."""
    import simulador
    ops = simulador.cartera.con_resultado()
    res = pd.to_numeric(ops["Resultado"], errors="coerce") * pd.to_numeric(ops.get("Tasa_COP"), errors="coerce").fillna(1)
    abiertos = simulador.cartera.posiciones(con_precio=False)
    return {"activos": len(abiertos), "ganancias": float(res[res > 0].sum()), "perdidas": float(res[res < 0].sum()),
            "desde": pd.to_datetime(ops["Fecha"]).min() if len(ops) else None,
            "ultima": pd.to_datetime(ops["Fecha"]).max() if len(ops) else None}


def menu_perfil(u):
    """Menú desplegable a la derecha, sin foto, con Cerrar sesión abajo."""
    fila = st.container(horizontal=True, horizontal_alignment="right")
    with fila.popover(u["nombre"].split(" ")[0], icon=":material/account_circle:"):
        st.markdown(f"**{u['nombre']}**  \n{u['email']}")
        st.badge({"superadmin": "Superadmin", **ROLES}.get(rol(u), rol(u)), color="violet")
        if u.get("rol") == "profesor" and not u.get("aprobado"):
            st.caption("Tu cuenta de profesor espera aprobación. Mientras tanto usas la app como estudiante.")
        st.markdown(f"**Género:** {u.get('genero') or '—'}  \n**Edad:** {u.get('edad') or '—'}  \n"
                    f"**Institución:** {u.get('institucion') or '—'}")
        try:
            r = resumen_operaciones()
            fecha = lambda f: f"{f:%d/%m/%Y}" if f is not None and pd.notna(f) else "—"
            st.markdown(f"**Activos en mi simulador:** {r['activos']}  \n"
                        f"**Ganancias:** :green[${r['ganancias']:,.0f}]  \n**Pérdidas:** :red[${r['perdidas']:,.0f}]  \n"
                        f"**Opera desde:** {fecha(r['desde'])}  \n**Última operación:** {fecha(r['ultima'])}".replace(",", "."))
        except Exception:
            st.caption("Todavía no tienes operaciones.")
        if login_configurado():
            st.button("Cerrar sesión", icon=":material/logout:", on_click=st.logout, width="stretch")


def panel_admin():
    """Para el superadmin: usuarios registrados, aprobar profesores y cambiar roles."""
    if not nube.conectado():
        st.caption("Los usuarios aparecen aquí cuando la app está conectada a Supabase (en la nube).")
        return
    t = pd.DataFrame(nube.cliente().table("usuarios").select("*").order("creado").execute().data)
    if t.empty:
        st.caption("Todavía no hay usuarios registrados.")
        return
    st.dataframe(t[["nombre", "email", "institucion", "rol", "aprobado", "genero", "edad", "acepta_contacto", "creado"]],
                 hide_index=True, alt="Usuarios registrados")
    pendientes = t[(t["rol"] == "profesor") & (~t["aprobado"])]
    for _, p in pendientes.iterrows():
        fila = st.container(horizontal=True, vertical_alignment="center")
        fila.markdown(f"**{p['nombre']}** ({p['email']}, {p['institucion']}) pide ser profesor.")
        if fila.button("Aprobar", key=f"aprobar_{p['email']}", type="primary"):
            nube.cliente().table("usuarios").update({"aprobado": True}).eq("email", p["email"]).execute()
            st.rerun()
    col = st.columns([2, 1, 1], vertical_alignment="bottom")
    quien = col[0].selectbox("Cambiar el rol de", t["email"], key="admin_quien")
    nuevo = col[1].selectbox("Nuevo rol", list(ROLES), format_func=ROLES.get, key="admin_rol")
    if col[2].button("Guardar rol"):
        nube.cliente().table("usuarios").update({"rol": nuevo, "aprobado": True}).eq("email", quien).execute()
        st.rerun()
