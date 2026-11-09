# cursos.py - Fase 3: profesores, cursos, eventos, estudiantes, bitácora, ranking, notas, anuncios y fin del evento.
# Todo se guarda en Supabase (gratis) usando las tablas que ya existen:
# - ajustes: cursos ("curso:<id>"), eventos ("evento:<id>"), inscripciones ("part:<id>"), pedidos de conservar la
#   cuenta ("conservar") y estadísticas anónimas (correo "anonimo").
# - operaciones: el simulador de cada estudiante en cada evento (cartera "ev:<id>"); la bitácora va en la Nota.
# shortcut: guardar todo en "ajustes" evita crear tablas nuevas; si pasan de unos miles de estudiantes, hacer tablas propias.
# Prueba (sin internet):  python cursos.py

import json
import uuid
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd

import activos
import nube

JORNADAS = ["Mañana", "Tarde", "Noche"]
DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"]
RAZONES = ["Seguí la sugerencia", "Noticia", "Tendencia", "Intuición"]
MERCADOS = [m for m in activos.NOMBRE_MERCADO if m != "dividendos"]
DIAS_GRACIA = 30                          # Días después del fin del evento para descargar el Excel antes de borrar
RUBRICA = {"rangos": [[-100.0, 0.0], [0.0, 3.0], [5.0, 4.0], [15.0, 5.0]],     # [rendimiento %, nota]
           "pesos": {"rendimiento": 60, "riesgo": 20, "bitacora": 20}, "nota_min": 0.0, "nota_max": 5.0}


def semestres(hoy=None):
    hoy = hoy or date.today()
    return [f"{a}-{s}" for a in (hoy.year, hoy.year + 1) for s in (1, 2)]


def nombre_curso(c):
    """'Finanzas Internacionales · Grupo A · Mañana · 2026-2'."""
    return " · ".join(p for p in [c["materia"], f"Grupo {c['grupo']}" if c.get("grupo") else "", c["jornada"],
                                  c["semestre"]] if p)


# ---------- Guardar y leer (tabla ajustes) ----------
def _tabla():
    return nube.cliente().table("ajustes")


def _todos(prefijo):
    return [(f["email"], f["clave"], f["valor"]) for f in
            _tabla().select("email,clave,valor").like("clave", f"{prefijo}%").execute().data]


def _guardar(email, clave, valor):
    nube.guardar_ajuste(clave, valor, email)


def _borrar(email, clave):
    _tabla().delete().eq("email", email).eq("clave", clave).execute()


# ---------- Cursos ----------
def crear_curso(profesor, datos):
    c = {**datos, "id": uuid.uuid4().hex[:8], "profesor": profesor, "monitores": [], "creado": str(date.today())}
    _guardar(profesor, f"curso:{c['id']}", c)
    return c


def guardar_curso(c):
    _guardar(c["profesor"], f"curso:{c['id']}", c)


def cursos(profesor=None):
    return [v for e, _, v in _todos("curso:") if profesor is None or e == profesor]


def curso(id_):
    return next((c for c in cursos() if c["id"] == id_), None)


def cursos_que_ve(email, es_superadmin=False):
    """(propios, como monitor): los del profesor y los cursos donde es monitor (solo mirar)."""
    todos = cursos()
    if es_superadmin:
        return todos, []
    return [c for c in todos if c["profesor"] == email], [c for c in todos if email in c.get("monitores", [])]


# ---------- Eventos ----------
def crear_evento(profesor, datos):
    e = {"rubrica": RUBRICA, "anuncios": [], "anuncios_auto": True, "bitacora_obligatoria": False, "limite_pct": 0,
         "retos": {}, **datos, "id": uuid.uuid4().hex[:8], "profesor": profesor, "creado": str(date.today())}
    e["clave_acceso"] = e["clave_acceso"].strip().upper()
    _guardar(profesor, f"evento:{e['id']}", e)
    return e


def guardar_evento(e):
    _guardar(e["profesor"], f"evento:{e['id']}", e)


def eventos(profesor=None):
    return [v for e, _, v in _todos("evento:") if profesor is None or e == profesor]


def evento(id_):
    return next((e for e in eventos() if e["id"] == id_), None)


def por_clave(clave):
    clave = (clave or "").strip().upper()
    return next((e for e in eventos() if e["clave_acceso"] == clave and not e.get("borrado")), None)


def clave_libre(clave, excepto=None):
    return not any(e["clave_acceso"] == clave.strip().upper() and e["id"] != excepto for e in eventos())


def duplicar_evento(e, nueva_clave, inicio, fin):
    """Copia un evento como plantilla: mismas reglas, plan, retos y rúbrica; sin estudiantes ni anuncios manuales."""
    copia = {k: v for k, v in e.items() if k not in ("id", "creado", "borrado", "anuncios")}
    copia.update(nombre=f"{e['nombre']} (copia)", clave_acceso=nueva_clave, inicio=str(inicio), fin=str(fin))
    return crear_evento(e["profesor"], copia)


def fechas(e):
    return date.fromisoformat(e["inicio"]), date.fromisoformat(e["fin"])


def estado(e, hoy=None):
    hoy = hoy or date.today()
    inicio, fin = fechas(e)
    if e.get("borrado"):
        return "borrado"
    return "por empezar" if hoy < inicio else "activo" if hoy <= fin else "terminado"


def semanas(e):
    inicio, fin = fechas(e)
    return max(1, (fin - inicio).days // 7 + 1)


def semana_actual(e, hoy=None):
    hoy = hoy or date.today()
    inicio, _ = fechas(e)
    return min(max(1, (hoy - inicio).days // 7 + 1), semanas(e))


def mercados_hoy(e, hoy=None):
    """Los mercados abiertos esta semana según el plan (o todos los permitidos si no hay plan para la semana)."""
    plan = {int(k): v for k, v in (e.get("plan") or {}).items()}
    return plan.get(semana_actual(e, hoy)) or e["mercados"]


def reto_de_la_semana(e, hoy=None):
    return (e.get("retos") or {}).get(str(semana_actual(e, hoy)), "")


# ---------- Estudiantes ----------
def unirse(email, e, apodo="", curso_id=None):
    """Inscribe al estudiante en el evento (con su propio simulador). Devuelve un error o None."""
    if estado(e) in ("terminado", "borrado"):
        return "Ese evento ya terminó."
    if any(p["email"] == email for p in participantes(e["id"])):
        return "Ya estás en ese evento."
    curso_id = e.get("curso_id") or curso_id
    if not curso_id:
        return "Elige tu curso."
    _guardar(email, f"part:{e['id']}", {"evento": e["id"], "curso": curso_id, "apodo": apodo.strip()[:30],
                                        "unido": str(date.today())})
    return None


def participantes(evento_id):
    return [{"email": email, **v} for email, _, v in _todos(f"part:{evento_id}")]


def mis_eventos(email):
    """[(evento, inscripción)] del estudiante."""
    todos = {e["id"]: e for e in eventos()}
    return [(todos[v["evento"]], v) for _, _, v in [(e, c, v) for e, c, v in _todos("part:") if e == email]
            if v["evento"] in todos]


def cartera_de_evento(evento_id):
    return f"ev:{evento_id}"


def regla_de_compra(e, simbolo, monto_cop, total_cop, ya_invertido_cop):
    """Error si el activo no está abierto esta semana o si pasa el límite por activo; None si se puede."""
    abiertos = set(mercados_hoy(e))
    if not set(activos.mercados(simbolo)) & abiertos:
        return ("Esta semana el evento solo permite: " +
                ", ".join(activos.NOMBRE_MERCADO.get(m, m) for m in sorted(abiertos)) + ".")
    limite = float(e.get("limite_pct") or 0)
    if limite and total_cop and (ya_invertido_cop + monto_cop) / total_cop * 100 > limite + 1e-9:
        return (f"Límite del evento: máximo {limite:g}% del saldo en un solo activo. Con esta compra tendrías "
                f"{(ya_invertido_cop + monto_cop) / total_cop * 100:.0f}%.")
    return None


# ---------- Bitácora (va en la Nota de cada operación) ----------
def nota_bitacora(razon, frase, siguio):
    return json.dumps({"razon": razon, "frase": (frase or "").strip()[:200], "siguio": bool(siguio)}, ensure_ascii=False)


def leer_bitacora(nota):
    try:
        b = json.loads(nota) if isinstance(nota, str) and nota.startswith("{") else {}
        return b if isinstance(b, dict) else {}
    except ValueError:
        return {}


# ---------- Métricas de cada estudiante ----------
def metricas(ops, monto, precio_hoy, tasa_hoy, hoy=None):
    """Rendimiento, operaciones, aciertos, riesgo, bitácora y si siguió la sugerencia, desde sus operaciones."""
    import automatico
    hoy = hoy or date.today()
    if ops.empty:
        return {"Valor_COP": monto, "Rendimiento_%": 0.0, "Operaciones": 0, "Opero_hoy": False, "Ultima": None,
                "Aciertos_%": None, "Peor_%": 0.0, "Concentracion_%": 0.0, "Riesgo": 100.0, "Bitacora_%": None,
                "Siguio_%": None, "Racha": 0}
    ops = ops.copy()
    ops["Fecha"] = pd.to_datetime(ops["Fecha"], format="mixed")
    tasa = pd.to_numeric(ops["Tasa_COP"], errors="coerce").fillna(1)
    costo = pd.to_numeric(ops.get("Costo_COP"), errors="coerce").fillna(0)
    bruto = ops["Precio"] * ops["Cantidad"] * tasa
    compra = ops["Tipo"] == "COMPRA"
    efectivo = monto - (bruto + costo)[compra].sum() + (bruto - costo)[~compra].sum()
    tenencia = ops.assign(q=ops["Cantidad"].where(compra, -ops["Cantidad"])).groupby(["Activo", "Moneda"])["q"].sum()
    valores = {a: q * precio_hoy(a) * tasa_hoy(m) for (a, m), q in tenencia.items() if q > 1e-9}
    total = efectivo + sum(valores.values())
    t, _ = automatico.comparar(ops.assign(Origen="automático"), precio_hoy, tasa_hoy)   # Resultado de cada compra
    resultados = list(t["Automatico_%"]) if len(t) else []
    cerradas = t[t["Cerrada"]] if len(t) else t
    racha = mejor = 0
    for r in (cerradas.sort_values("Venta")["Automatico_%"] if len(cerradas) else []):
        racha = racha + 1 if r > 0 else 0
        mejor = max(mejor, racha)
    peor = min([0.0] + resultados)
    concentracion = max(valores.values()) / total * 100 if valores and total > 0 else 0.0
    bit = ops["Nota"].map(leer_bitacora)
    con_razon = bit.map(lambda b: bool(b.get("razon")))
    siguio = bit.map(lambda b: b.get("siguio")).dropna()
    return {"Valor_COP": total, "Rendimiento_%": (total / monto - 1) * 100, "Operaciones": len(ops),
            "Opero_hoy": bool((ops["Fecha"].dt.date == hoy).any()), "Ultima": ops["Fecha"].max(),
            "Aciertos_%": float((cerradas["Automatico_%"] > 0).mean() * 100) if len(cerradas) else None,
            "Peor_%": peor, "Concentracion_%": concentracion, "Riesgo": puntaje_riesgo(peor, concentracion),
            "Bitacora_%": float(con_razon.mean() * 100), "Siguio_%": float(siguio.mean() * 100) if len(siguio) else None,
            "Racha": mejor}


def puntaje_riesgo(peor_pct, concentracion_pct):
    """Control de riesgo de 0 a 100: resta 4 puntos por cada 1% de la peor pérdida en una operación y 1 punto por
    cada 1% que el activo más grande pase del 40% del portafolio (tener todo en uno solo es arriesgado)."""
    return float(np.clip(100 - 4 * max(0.0, -peor_pct) - max(0.0, concentracion_pct - 40), 0, 100))


def nota(m, rubrica=None):
    """Nota (0 a 5 por defecto): rendimiento según los rangos del profesor, riesgo y bitácora, con sus pesos.
    Si perdió toda la plata, la parte de rendimiento queda en la nota mínima."""
    r = rubrica or RUBRICA
    lo, hi = r["nota_min"], r["nota_max"]
    rangos = sorted(r["rangos"])
    rend = float(np.interp(m["Rendimiento_%"], [x for x, _ in rangos], [n for _, n in rangos]))
    if m["Rendimiento_%"] <= -99:
        rend = lo
    riesgo = lo + (hi - lo) * m["Riesgo"] / 100
    bitacora = lo + (hi - lo) * (m["Bitacora_%"] or 0) / 100
    p = r["pesos"]
    total = (rend * p["rendimiento"] + riesgo * p["riesgo"] + bitacora * p["bitacora"]) / max(1, sum(p.values()))
    return round(float(np.clip(total, lo, hi)), 1)


def tabla_evento(e, precio_hoy=None, tasa_hoy=None):
    """Una fila por estudiante: datos del curso, métricas, puestos (ganancia y riesgo) y nota."""
    import cartera
    import simulador
    precio_hoy = precio_hoy or cartera.ultimo_cierre
    tasa_hoy = tasa_hoy or simulador.tasa_a_pesos
    personas = {u["email"]: u for u in nube.cliente().table("usuarios").select("email,nombre,institucion").execute().data}
    cursos_ = {c["id"]: c for c in cursos()}
    filas = []
    for p in participantes(e["id"]):
        ops = nube.leer_operaciones(p["email"], cartera_de_evento(e["id"]))
        c = cursos_.get(p["curso"], {})
        m = metricas(ops, float(e["monto"]), precio_hoy, tasa_hoy)
        filas.append({"Estudiante": personas.get(p["email"], {}).get("nombre", p["email"]), "Apodo": p.get("apodo") or "",
                      "Correo": p["email"], "Universidad": c.get("universidad", ""),
                      "Curso": nombre_curso(c) if c else "", "Jornada": c.get("jornada", ""), **m,
                      "Nota": nota(m, e.get("rubrica"))})
    t = pd.DataFrame(filas)
    if len(t):
        t["Puesto_ganancia"] = t["Rendimiento_%"].rank(ascending=False, method="min").astype(int)
        t["Puesto_riesgo"] = t["Riesgo"].rank(ascending=False, method="min").astype(int)
    return t


def operaciones_evento(e):
    """Todas las operaciones del evento con la bitácora separada (para la ficha y el Excel)."""
    filas = []
    for p in participantes(e["id"]):
        ops = nube.leer_operaciones(p["email"], cartera_de_evento(e["id"]))
        for _, o in ops.iterrows():
            b = leer_bitacora(o.get("Nota"))
            filas.append({"Correo": p["email"], "Apodo": p.get("apodo") or "", "Fecha": o["Fecha"], "Activo": o["Activo"],
                          "Tipo": o["Tipo"], "Precio": o["Precio"], "Cantidad": o["Cantidad"], "Moneda": o["Moneda"],
                          "Razon": b.get("razon", ""), "Frase": b.get("frase", ""), "Siguio_sugerencia": b.get("siguio")})
    return pd.DataFrame(filas)


def siguieron_vs_por_su_cuenta(e, precio_hoy=None, tasa_hoy=None):
    """Resultado promedio de las compras que siguieron la sugerencia de la app vs. las hechas por su cuenta."""
    import automatico
    import cartera
    import simulador
    precio_hoy = precio_hoy or cartera.ultimo_cierre
    tasa_hoy = tasa_hoy or simulador.tasa_a_pesos
    filas = []
    for p in participantes(e["id"]):
        ops = nube.leer_operaciones(p["email"], cartera_de_evento(e["id"]))
        for c, v in automatico.pares(ops) if len(ops) else []:
            t, _ = automatico.comparar(pd.DataFrame([c] + ([v] if v is not None else [])).assign(Origen="automático"),
                                       precio_hoy, tasa_hoy)
            filas.append({"Siguio": bool(leer_bitacora(c.get("Nota")).get("siguio")), "Resultado_%": t["Automatico_%"].iloc[0]})
    t = pd.DataFrame(filas)
    if t.empty:
        return t
    return t.groupby("Siguio")["Resultado_%"].agg(["count", "mean"]).rename(
        index={True: "Siguieron la app", False: "Por su cuenta"}, columns={"count": "Compras", "mean": "Resultado promedio %"})


# ---------- Insignias ----------
def insignias(email, tabla):
    """Insignias del estudiante dentro de su evento."""
    if tabla.empty or email not in set(tabla["Correo"]):
        return []
    yo = tabla[tabla["Correo"] == email].iloc[0]
    lista = []
    if yo["Operaciones"] > 0:
        lista.append(("🥇", "Primera operación", "Ya hiciste tu primera operación."))
    if yo["Racha"] > 0 and yo["Racha"] == tabla["Racha"].max():
        lista.append(("🔥", "Mejor racha", f"La racha más larga del grupo: {int(yo['Racha'])} ventas seguidas con ganancia."))
    if yo["Operaciones"] > 0 and yo["Riesgo"] == tabla.loc[tabla["Operaciones"] > 0, "Riesgo"].max():
        lista.append(("🛡️", "Mejor control de riesgo", "Nadie del grupo cuidó mejor su plata."))
    return lista


# ---------- Anuncios ----------
def anuncios(e, hoy=None):
    """Anuncios manuales del profesor y, si los activó, los automáticos del calendario (próximos 2 días)."""
    hoy = hoy or date.today()
    lista = [(a["fecha"], "📣 " + a["texto"]) for a in e.get("anuncios", [])
             if date.fromisoformat(a["fecha"]) >= hoy - timedelta(days=7)]
    if e.get("anuncios_auto"):
        import calendario
        dias = {0: "Hoy", 1: "Mañana", 2: "Pasado mañana"}
        try:
            cal = calendario.proximos_eventos(dias=2)
            for _, f in cal.iterrows():
                d = (pd.Timestamp(f["Fecha"]).date() - hoy).days
                if d in dias and not str(f.get("Tipo", "")).startswith("Festivo"):
                    lista.append((str(pd.Timestamp(f["Fecha"]).date()), f"🗓️ {dias[d]}: {f['Evento']}"))
        except Exception:
            pass
    return sorted(lista, reverse=True)


# ---------- Fin del evento: conservar la cuenta y borrado ----------
def dias_para_borrar(email, hoy=None):
    """Días que le quedan a la cuenta de un estudiante (None si no se borra: está en un evento vigente o la conserva)."""
    hoy = hoy or date.today()
    mios = mis_eventos(email)
    if not mios or any(estado(e, hoy) in ("activo", "por empezar") for e, _ in mios):
        return None
    pedido = nube.leer_ajuste("conservar", email)
    if pedido and pedido.get("estado") == "aprobado":
        return None
    ultimo = max(fechas(e)[1] for e, _ in mios)
    return max(0, (ultimo + timedelta(days=DIAS_GRACIA) - hoy).days)


def pedir_conservar(email, motivo, contacto):
    _guardar(email, "conservar", {"motivo": motivo.strip()[:500], "contacto": bool(contacto), "estado": "pendiente",
                                  "fecha": str(date.today())})


def pedidos_conservar():
    return [{"email": e, **v} for e, _, v in _todos("conservar")]


def aprobar_conservar(email):
    v = nube.leer_ajuste("conservar", email) or {}
    _guardar(email, "conservar", {**v, "estado": "aprobado"})


def borrar_usuario(email):
    """Borra TODO lo de un usuario (cuenta, simuladores, ajustes y diario). Nunca al superadmin."""
    if email == nube.superadmin():
        raise ValueError("Nunca se borra al superadmin.")
    c = nube.cliente()
    for tabla in ("operaciones", "ajustes", "diario_errores", "usuarios"):
        c.table(tabla).delete().eq("email", email).execute()


def limpieza(hoy=None):
    """Corre cada mañana en la nube. Eventos terminados hace más de 30 días: guarda estadísticas ANÓNIMAS, borra las
    operaciones e inscripciones, y borra la cuenta de los estudiantes que no siguen en otro evento ni la conservan."""
    hoy = hoy or date.today()
    informe = []
    for e in eventos():
        if e.get("borrado") or fechas(e)[1] + timedelta(days=DIAS_GRACIA) >= hoy:
            continue
        tabla = tabla_evento(e)
        for i, f in tabla.reset_index(drop=True).iterrows():                     # Sin nombre ni correo
            _guardar("anonimo", f"stat:{e['id']}:{i}", {
                "evento": e["id"], "universidad": f["Universidad"], "jornada": f["Jornada"], "semestre": e.get("semestre", ""),
                "rendimiento": round(float(f["Rendimiento_%"]), 2), "operaciones": int(f["Operaciones"]),
                "aciertos": None if pd.isna(f["Aciertos_%"]) else round(float(f["Aciertos_%"]), 1),
                "riesgo": round(float(f["Riesgo"]), 1), "nota": float(f["Nota"]),
                "siguio": None if pd.isna(f["Siguio_%"]) else round(float(f["Siguio_%"]), 1)})
        estudiantes = [p["email"] for p in participantes(e["id"])]
        roles = {u["email"]: u["rol"] for u in nube.cliente().table("usuarios").select("email,rol").execute().data}
        # Se decide ANTES de quitar las inscripciones (si no, ya no se sabría que el evento terminó)
        a_borrar = [x for x in estudiantes if roles.get(x) == "estudiante" and dias_para_borrar(x, hoy) == 0]
        for correo in estudiantes:
            nube.reemplazar_operaciones(correo, cartera_de_evento(e["id"]), pd.DataFrame(columns=["Fecha"]))
            _borrar(correo, f"part:{e['id']}")
        guardar_evento({**e, "borrado": True})
        informe.append(f"Evento {e['nombre']}: {len(estudiantes)} estudiantes pasados a estadísticas anónimas.")
        for correo in a_borrar:
            borrar_usuario(correo)
            informe.append(f"Cuenta borrada: {correo[:3]}...")
    return informe


# ---------- Excel ----------
def excel(estudiantes, operaciones):
    """Archivo de Excel con dos hojas (Estudiantes y Operaciones) y filtros en los encabezados."""
    import io

    from openpyxl.utils import get_column_letter
    salida = io.BytesIO()
    with pd.ExcelWriter(salida, engine="openpyxl") as libro:
        for nombre, t in (("Estudiantes", estudiantes), ("Operaciones", operaciones)):
            t = t.copy()
            for c in t.columns:
                if pd.api.types.is_datetime64_any_dtype(t[c]):
                    t[c] = t[c].dt.tz_localize(None) if getattr(t[c].dt, "tz", None) else t[c]
            t.to_excel(libro, sheet_name=nombre, index=False)
            hoja = libro.sheets[nombre]
            if len(t.columns):
                hoja.auto_filter.ref = f"A1:{get_column_letter(len(t.columns))}{len(t) + 1}"
                for i, c in enumerate(t.columns, 1):
                    hoja.column_dimensions[get_column_letter(i)].width = max(10, min(40, len(str(c)) + 4))
            hoja.freeze_panes = "A2"
    return salida.getvalue()


if __name__ == "__main__":
    c = {"materia": "Finanzas Internacionales", "grupo": "A", "jornada": "Mañana", "semestre": "2026-2"}
    assert nombre_curso(c) == "Finanzas Internacionales · Grupo A · Mañana · 2026-2"
    assert nombre_curso({**c, "grupo": ""}) == "Finanzas Internacionales · Mañana · 2026-2"
    e = {"inicio": "2026-11-02", "fin": "2026-11-29", "mercados": ["colombia", "eeuu", "cripto"],
         "plan": {"1": ["colombia"], "4": ["colombia", "eeuu", "cripto"]}, "limite_pct": 30}
    assert semanas(e) == 4 and semana_actual(e, date(2026, 11, 3)) == 1 and semana_actual(e, date(2026, 11, 25)) == 4
    assert mercados_hoy(e, date(2026, 11, 3)) == ["colombia"] and mercados_hoy(e, date(2026, 11, 10)) == e["mercados"]
    assert estado(e, date(2026, 11, 1)) == "por empezar" and estado(e, date(2026, 12, 1)) == "terminado"
    import unittest.mock as m
    with m.patch.object(activos, "mercados", lambda s: ["colombia"] if s.endswith(".CL") else ["eeuu"]):
        hoy = date.today()
        e2 = {**e, "inicio": str(hoy), "fin": str(hoy + timedelta(days=27))}
        assert regla_de_compra(e2, "AAPL", 10, 100, 0).startswith("Esta semana")
        assert regla_de_compra(e2, "ECOPETROL.CL", 20, 100, 0) is None
        assert "Límite" in regla_de_compra(e2, "ECOPETROL.CL", 20, 100, 15)        # 35% > 30%
    assert puntaje_riesgo(0, 30) == 100 and puntaje_riesgo(-5, 60) == 60
    base = {"Rendimiento_%": 15.0, "Riesgo": 100.0, "Bitacora_%": 100.0}
    assert nota(base) == 5.0
    assert nota({**base, "Rendimiento_%": -100.0}) == 2.0                     # Rendimiento en 0; riesgo y bitácora 5
    assert nota({**base, "Rendimiento_%": 2.5, "Riesgo": 50.0, "Bitacora_%": 0.0}) == round((3.5 * 60 + 2.5 * 20) / 100, 1)
    b = nota_bitacora("Noticia", "  subió el petróleo ", True)
    assert leer_bitacora(b) == {"razon": "Noticia", "frase": "subió el petróleo", "siguio": True} and leer_bitacora("x") == {}
    ops = pd.DataFrame([
        {"Fecha": "2026-11-03 10:00", "Activo": "A", "Tipo": "COMPRA", "Precio": 100.0, "Cantidad": 1.0, "Moneda": "COP",
         "Nota": nota_bitacora("Tendencia", "", True), "Tasa_COP": 1.0, "Costo_COP": 0.0},
        {"Fecha": "2026-11-04 10:00", "Activo": "A", "Tipo": "VENTA", "Precio": 110.0, "Cantidad": 1.0, "Moneda": "COP",
         "Nota": "", "Tasa_COP": 1.0, "Costo_COP": 0.0}])
    mt = metricas(ops, 1000.0, lambda s: 110.0, lambda mo: 1.0, hoy=date(2026, 11, 4))
    assert abs(mt["Rendimiento_%"] - 1.0) < 1e-9 and mt["Aciertos_%"] == 100 and mt["Opero_hoy"] and mt["Racha"] == 1
    assert mt["Bitacora_%"] == 50 and mt["Siguio_%"] == 100
    datos = excel(pd.DataFrame({"a": [1]}), pd.DataFrame({"b": [2]}))
    assert datos[:2] == b"PK"                                                  # Es un archivo de Excel
    print("Cursos: pruebas OK")
