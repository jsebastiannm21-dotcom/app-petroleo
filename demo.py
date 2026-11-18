# demo.py - MODO DEMOSTRACIÓN aislado: datos ficticios para presentar la app sin tocar NADA real.
#
# Cómo se aísla:
#  - Mientras el modo está activo (nube.DEMO), nube.cliente() entrega una base de datos DE MENTIRA en memoria
#    (esta, FakeCliente) en vez de Supabase. Todo lo que la app lee o escribe (usuarios, operaciones, ajustes,
#    cursos, eventos, notas) va ahí. Se pierde al reiniciar la app, y nunca llega a Supabase.
#  - El almacenamiento de archivos de la nube no sube nada en demo; las notificaciones de Telegram no se envían.
#  - Los activos de la demo usan precios FIJOS (PRECIOS_DEMO) para que las cifras cuadren siempre igual.
#
# Contenido:
#  - Perfil Juanse: 10.000.000 COP del 1 al 13 de nov 2026, operaciones con comisiones de Trii -> 10.925.000 (+9,25%).
#  - "Curso Prueba 1" y "Evento Prueba 1" (Universidad Santo Tomás, 1 ago - 30 nov 2026), 1 profesor y 5 estudiantes.
# Prueba:  python demo.py

import copy
import json
import re
from datetime import date
from types import SimpleNamespace

import numpy as np
import pandas as pd

import comisiones

DOMINIO = "demo.quantpulse"
SUPERADMIN = f"juanse@{DOMINIO}"
PROFESOR = f"profesor@{DOMINIO}"
CAPITAL = 10_000_000.0
META_FINAL = 10_925_000.0
EVENTO_ID, CURSO_ID, MONTO_EVENTO = "demoev01", "democu01", 5_000_000.0
BANDA = "DATOS DE DEMOSTRACIÓN – no son resultados reales"

PERFILES = {
    SUPERADMIN: {"nombre": "Juanse", "rol": "inversionista", "etiqueta": "Juanse (superadmin)"},
    PROFESOR: {"nombre": "Profesora Ana Ruiz (ficticia)", "rol": "profesor", "etiqueta": "Profesora (profesor)"},
    **{f"estudiante{i}@{DOMINIO}": {"nombre": n, "rol": "estudiante", "etiqueta": f"{n.split(' (')[0]} (estudiante)"}
       for i, n in enumerate(["Camila Torres (ficticia)", "Mateo Díaz (ficticio)", "Valentina Gómez (ficticia)",
                              "Santiago López (ficticio)", "Isabella Mora (ficticia)"], 1)},
}

# ---------- Precios fijos de los activos de la demo (COP). Entre puntos: interpolación con una onda suave ----------
ANCLAS = {
    "ECOPETROL.CL": {"2026-08-03": 2300, "2026-09-01": 2380, "2026-10-01": 2250, "2026-10-20": 2400,
                     "2026-11-03": 2450, "2026-11-06": 2650, "2026-11-12": 2520, "2026-11-13": 2610},
    "CIBEST.CL": {"2026-08-03": 78000, "2026-09-01": 82000, "2026-10-01": 80000, "2026-10-20": 83000,
                  "2026-11-03": 84000, "2026-11-11": 92500, "2026-11-13": 91800},
    "ISA.CL": {"2026-08-03": 24000, "2026-09-01": 25500, "2026-10-01": 26800, "2026-10-20": 25800,
               "2026-11-04": 26500, "2026-11-13": 29200},
    "GEB.CL": {"2026-08-03": 2800, "2026-09-01": 2750, "2026-10-01": 2900, "2026-10-20": 3000,
               "2026-11-09": 2950, "2026-11-13": 3250},
    "CELSIA.CL": {"2026-08-03": 4600, "2026-09-01": 4400, "2026-10-01": 4100, "2026-10-20": 3900, "2026-11-13": 4000},
    "GRUPOARGOS.CL": {"2026-08-03": 17500, "2026-09-01": 18800, "2026-10-01": 19500, "2026-10-20": 20500,
                      "2026-11-13": 20900},
}
FIN = pd.Timestamp("2026-11-13")


def _serie(anclas):
    puntos = pd.Series({pd.Timestamp(k): float(v) for k, v in anclas.items()}).sort_index()
    dias = pd.bdate_range(puntos.index[0] - pd.Timedelta(days=14), FIN)
    valores = []
    for d in dias:
        if d <= puntos.index[0]:
            valores.append(puntos.iloc[0])
            continue
        j = puntos.index.searchsorted(d)
        if j >= len(puntos) or puntos.index[j] == d:
            valores.append(puntos.iloc[min(j, len(puntos) - 1)])
            continue
        a, b = puntos.index[j - 1], puntos.index[j]
        f = (d - a) / (b - a)
        base = puntos.iloc[j - 1] + (puntos.iloc[j] - puntos.iloc[j - 1]) * f
        valores.append(round(base * (1 + 0.012 * np.sin(2 * np.pi * f)), 2))   # Onda: 0 en cada punto fijo
    return pd.Series(valores, index=dias, name="Cierre")


PRECIOS_DEMO = {s: _serie(a) for s, a in ANCLAS.items()}


def precio_en(simbolo, fecha):
    s = PRECIOS_DEMO[simbolo]
    return float(s[s.index <= pd.Timestamp(fecha).normalize()].iloc[-1])


def cierre_demo(simbolo):
    """Último precio fijo de un activo de la demo, o None si no es de la demo."""
    return float(PRECIOS_DEMO[simbolo].iloc[-1]) if simbolo in PRECIOS_DEMO else None


# ---------- Operaciones ficticias ----------
def _op(fecha, activo, tipo, cantidad, nota="", origen="manual"):
    precio = precio_en(activo, fecha)
    bruto = precio * cantidad
    return {"Fecha": f"{fecha} 10:00:00", "Activo": activo, "Tipo": tipo, "Precio": precio, "Cantidad": cantidad,
            "Moneda": "COP", "Nota": nota, "Tasa_COP": 1.0, "Costo_COP": round(comisiones.costo(bruto, "COP",
                                                                                                 comisiones.BASE)["total"], 2),
            "Origen": origen, "Precio_COP": precio, "Precio_USD": precio / 4000}


def _secuencia(pasos):
    """pasos: (fecha, activo, 'COMPRA', monto_bruto_COP | 'VENTA', None=todo, nota). Devuelve las operaciones."""
    ops, tengo = [], {}
    for fecha, activo, tipo, monto, nota in pasos:
        cantidad = monto / precio_en(activo, fecha) if tipo == "COMPRA" else tengo[activo]
        tengo[activo] = tengo.get(activo, 0) + (cantidad if tipo == "COMPRA" else -cantidad)
        ops.append(_op(fecha, activo, tipo, cantidad, nota))
    return ops


def total_cuenta(ops, inicial):
    """Efectivo + valor de lo que queda abierto a precios fijos: lo mismo que calcula el simulador."""
    efectivo, tengo = inicial, {}
    for o in ops:
        bruto = o["Precio"] * o["Cantidad"] * o["Tasa_COP"]
        efectivo += -(bruto + o["Costo_COP"]) if o["Tipo"] == "COMPRA" else bruto - o["Costo_COP"]
        tengo[o["Activo"]] = tengo.get(o["Activo"], 0) + (o["Cantidad"] if o["Tipo"] == "COMPRA" else -o["Cantidad"])
    return efectivo + sum(q * cierre_demo(a) for a, q in tengo.items() if q > 1e-9)


def ops_juanse():
    base = [("2026-11-03", "ECOPETROL.CL", "COMPRA", 3_000_000, "Rebote en soporte"),
            ("2026-11-03", "CIBEST.CL", "COMPRA", 3_000_000, "Resultados trimestrales"),
            ("2026-11-04", "ISA.CL", "COMPRA", 2_000_000, "Tendencia al alza"),
            ("2026-11-06", "ECOPETROL.CL", "VENTA", None, "Llegó al objetivo"),
            ("2026-11-09", "GEB.CL", "COMPRA", 2_500_000, "Dividendo atractivo"),
            ("2026-11-11", "CIBEST.CL", "VENTA", None, "Toma de ganancias")]
    sin_ultima = _secuencia(base)
    # La última compra se ajusta para que, con comisiones y precios fijos, el total sea exactamente 10.925.000
    p_compra, p_hoy = precio_en("ECOPETROL.CL", "2026-11-12"), cierre_demo("ECOPETROL.CL")
    fee = comisiones.costo(1_000_000, "COP", comisiones.BASE)["total"]          # Fija (monto bajo 5 millones)
    falta = META_FINAL - (total_cuenta(sin_ultima, CAPITAL) - fee)
    monto = falta / (p_hoy / p_compra - 1)
    assert 100_000 < monto < 5_000_000, monto
    return sin_ultima + [_op("2026-11-12", "ECOPETROL.CL", "COMPRA", monto / p_compra, "Entrada en retroceso")]


def _bit(razon, frase, siguio):
    return json.dumps({"razon": razon, "frase": frase, "siguio": siguio}, ensure_ascii=False) if razon else ""


ESTUDIANTES = {   # Cada uno con un estilo distinto: resultados, riesgo y bitácora diferentes -> notas diferentes
    1: [("2026-08-04", "GRUPOARGOS.CL", "COMPRA", 1_500_000, ("Tendencia", "Media de 50 al alza", True)),
        ("2026-08-05", "ISA.CL", "COMPRA", 1_500_000, ("Seguí la sugerencia", "La app dijo COMPRAR", True)),
        ("2026-10-01", "ISA.CL", "VENTA", None, ("Seguí la sugerencia", "Llegó al objetivo", True)),
        ("2026-10-02", "CIBEST.CL", "COMPRA", 1_500_000, ("Noticia", "Buenos resultados", True)),
        ("2026-11-11", "CIBEST.CL", "VENTA", None, ("Seguí la sugerencia", "Objetivo cumplido", True))],
    2: [("2026-08-10", "ECOPETROL.CL", "COMPRA", 2_000_000, ("Noticia", "Sube el petróleo", True)),
        ("2026-09-01", "ECOPETROL.CL", "VENTA", None, ("Tendencia", "Ganancia rápida", False)),
        ("2026-09-02", "GEB.CL", "COMPRA", 2_000_000, ("Intuición", "", False)),
        ("2026-10-20", "ISA.CL", "COMPRA", 1_000_000, None)],
    3: [("2026-08-12", "CIBEST.CL", "COMPRA", 1_500_000, ("Seguí la sugerencia", "", True)),
        ("2026-10-01", "CIBEST.CL", "VENTA", None, None),
        ("2026-10-02", "ECOPETROL.CL", "COMPRA", 2_000_000, ("Intuición", "Está barata", False)),
        ("2026-10-21", "ECOPETROL.CL", "VENTA", None, None)],
    4: [("2026-08-18", "CELSIA.CL", "COMPRA", 3_500_000, ("Intuición", "Me gusta la empresa", False)),
        ("2026-09-15", "ECOPETROL.CL", "COMPRA", 1_000_000, None),
        ("2026-10-01", "ECOPETROL.CL", "VENTA", None, None),
        ("2026-10-15", "GEB.CL", "COMPRA", 400_000, None)],
    5: [("2026-09-01", "CELSIA.CL", "COMPRA", 4_000_000, None),
        ("2026-10-20", "CELSIA.CL", "VENTA", None, None),
        ("2026-11-06", "ECOPETROL.CL", "COMPRA", 3_000_000, None),
        ("2026-11-12", "ECOPETROL.CL", "VENTA", None, None)],
}


def _datos():
    usuarios = [{"email": e, "nombre": p["nombre"], "institucion": "Universidad Santo Tomás", "genero": None,
                 "edad": None, "rol": p["rol"], "aprobado": True, "acepta_terminos": True, "acepta_datos": True,
                 "acepta_contacto": False, "creado": "2026-07-25T08:00:00"} for e, p in PERFILES.items()]
    import cursos
    curso = {"id": CURSO_ID, "universidad": "Universidad Santo Tomás", "materia": "Curso Prueba 1", "grupo": "A",
             "jornada": "Mañana", "dias": ["Martes", "Jueves"], "hora_inicio": "07:00", "hora_fin": "09:00",
             "semestre": "2026-2", "profesor": PROFESOR, "monitores": [], "creado": "2026-07-25"}
    evento = {"rubrica": cursos.RUBRICA, "anuncios": [], "anuncios_auto": True, "bitacora_obligatoria": False,
              "limite_pct": 0, "retos": {}, "nombre": "Evento Prueba 1", "curso_id": CURSO_ID, "clave_acceso": "PRUEBA1",
              "inicio": "2026-08-01", "fin": "2026-11-30", "monto": MONTO_EVENTO, "mercados": ["colombia"],
              "id": EVENTO_ID, "profesor": PROFESOR, "creado": "2026-07-25"}
    ajustes = [{"email": PROFESOR, "clave": f"curso:{CURSO_ID}", "valor": curso},
               {"email": PROFESOR, "clave": f"evento:{EVENTO_ID}", "valor": evento},
               {"email": SUPERADMIN, "clave": "simulador_config", "valor": {"saldo_inicial": CAPITAL, "modo": "manual",
                                                                            "meta_%": 15, "inicio": "2026-11-01"}},
               {"email": SUPERADMIN, "clave": "tutorial_visto", "valor": True}]
    operaciones = [{**o, "email": SUPERADMIN, "cartera": "sim"} for o in ops_juanse()]
    for i, pasos in ESTUDIANTES.items():
        email = f"estudiante{i}@{DOMINIO}"
        apodo = PERFILES[email]["nombre"].split()[0]
        ajustes += [{"email": email, "clave": f"part:{EVENTO_ID}", "valor": {"evento": EVENTO_ID, "curso": CURSO_ID,
                                                                           "apodo": apodo, "unido": "2026-08-01"}},
                    {"email": email, "clave": "tutorial_visto", "valor": True}]
        ops = _secuencia([(f, a, t, m, _bit(*b) if b else "") for f, a, t, m, b in pasos])
        operaciones += [{**o, "email": email, "cartera": f"ev:{EVENTO_ID}"} for o in ops]
    for n, o in enumerate(operaciones, 1):
        o["id"] = n
    return {"usuarios": usuarios, "ajustes": ajustes, "operaciones": operaciones, "diario_errores": []}


# ---------- Base de datos de mentira con la misma forma de uso que el cliente de Supabase ----------
LLAVES = {"usuarios": ("email",), "ajustes": ("email", "clave"), "operaciones": ("id",), "diario_errores": ("id",)}


class _Consulta:
    def __init__(self, base, tabla):
        self.base, self.tabla = base, tabla
        self.accion, self.carga, self.columnas, self.filtros = "select", None, "*", []
        self.orden, self.tope = None, None

    def select(self, columnas="*", **_):
        self.accion, self.columnas = "select", columnas
        return self

    def insert(self, filas, **_):
        self.accion, self.carga = "insert", filas
        return self

    def upsert(self, filas, **_):
        self.accion, self.carga = "upsert", filas
        return self

    def update(self, cambios, **_):
        self.accion, self.carga = "update", cambios
        return self

    def delete(self, **_):
        self.accion = "delete"
        return self

    def eq(self, col, valor):
        self.filtros.append(lambda f: f.get(col) == valor)
        return self

    def gte(self, col, valor):
        self.filtros.append(lambda f: f.get(col) is not None and str(f.get(col)) >= str(valor))
        return self

    def like(self, col, patron):
        regex = re.compile("^" + ".*".join(map(re.escape, patron.split("%"))) + "$", re.S)
        self.filtros.append(lambda f: regex.match(str(f.get(col, ""))) is not None)
        return self

    def order(self, col, desc=False):
        self.orden = (col, desc)
        return self

    def limit(self, n):
        self.tope = (0, n - 1)
        return self

    def range(self, desde, hasta):
        self.tope = (desde, hasta)
        return self

    def _cumple(self, f):
        return all(c(f) for c in self.filtros)

    def execute(self):
        filas = self.base.setdefault(self.tabla, [])
        if self.accion in ("insert", "upsert"):
            nuevas = self.carga if isinstance(self.carga, list) else [self.carga]
            llave = LLAVES.get(self.tabla, ("id",))
            for f in copy.deepcopy(nuevas):
                if llave == ("id",) and "id" not in f:
                    f["id"] = max([x.get("id", 0) for x in filas] + [0]) + 1
                if self.accion == "upsert":
                    filas[:] = [x for x in filas if any(x.get(k) != f.get(k) for k in llave)]
                filas.append(f)
            return SimpleNamespace(data=copy.deepcopy(nuevas))
        elegidas = [f for f in filas if self._cumple(f)]
        if self.accion == "update":
            for f in elegidas:
                f.update(copy.deepcopy(self.carga))
            return SimpleNamespace(data=copy.deepcopy(elegidas))
        if self.accion == "delete":
            filas[:] = [f for f in filas if not self._cumple(f)]
            return SimpleNamespace(data=copy.deepcopy(elegidas))
        if self.orden:
            col, desc = self.orden
            elegidas = sorted(elegidas, key=lambda f: (f.get(col) is None, str(f.get(col))), reverse=desc)
        if self.tope:
            elegidas = elegidas[self.tope[0]:self.tope[1] + 1]
        if self.columnas.strip() != "*":
            cols = [c.strip().strip('"') for c in self.columnas.split(",")]
            elegidas = [{c: f.get(c) for c in cols} for f in elegidas]
        return SimpleNamespace(data=copy.deepcopy(elegidas))


class _Almacen:
    """Almacenamiento de archivos en demo: no lista ni baja nada y NUNCA sube (lo real queda intacto)."""
    def list(self, *_, **__):
        return []

    def download(self, nombre):
        raise FileNotFoundError(f"En modo demostración no se bajan archivos de la nube ({nombre}).")

    def upload(self, *_, **__):
        return None


class FakeCliente:
    def __init__(self):
        self.base = _datos()
        self.storage = SimpleNamespace(from_=lambda _bucket: _Almacen())

    def table(self, nombre):
        return _Consulta(self.base, nombre)


_cliente = None


def cliente():
    global _cliente
    if _cliente is None:
        _cliente = FakeCliente()
    return _cliente


def perfil(email):
    """El usuario de la demo con la forma de una fila de la tabla usuarios."""
    filas = cliente().table("usuarios").select("*").eq("email", email).execute().data
    return filas[0] if filas else None


COMISIONES = {}                    # Cambios de comisiones hechos en demo: solo en memoria


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    import demo as d                    # El mismo módulo que usa nube.py (este archivo corre como __main__)
    import nube
    real_antes = nube.DEMO.get()
    nube.DEMO.set(True)
    try:
        assert nube.cliente() is d.cliente() and nube.conectado() and nube.superadmin() == SUPERADMIN
        nube.USUARIO.set(SUPERADMIN)
        import simulador
        r = simulador.resumen()
        print(f"Juanse: total {r['total']:,.2f} ({r['ganancia_%']:+.2f}%) · meta {r['meta']:,.0f} · "
              f"progreso {r['progreso_meta']:.1%} · posiciones {r['posiciones']} · operaciones {r['operaciones']}")
        assert abs(r["total"] - META_FINAL) < 0.01 and abs(r["ganancia_%"] - 9.25) < 1e-6
        assert abs(r["meta"] - 11_500_000) < 0.01
        costo_total = sum(o["Costo_COP"] for o in ops_juanse())
        print(f"Comisiones de Juanse: {costo_total:,.0f} COP en {len(ops_juanse())} operaciones")
        import cursos
        e = cursos.evento(EVENTO_ID)
        t = cursos.tabla_evento(e)
        print(t[["Estudiante", "Rendimiento_%", "Riesgo", "Bitacora_%", "Nota", "Puesto_ganancia"]].to_string())
        assert len(t) == 5 and t["Nota"].nunique() == 5 and t["Rendimiento_%"].round(2).nunique() == 5
        assert cursos.curso(CURSO_ID)["universidad"] == "Universidad Santo Tomás"
        # Escribir en demo no llega a lo real
        nube.guardar_ajuste("prueba_demo", True, SUPERADMIN)
        assert nube.leer_ajuste("prueba_demo", SUPERADMIN) is True
    finally:
        nube.DEMO.set(real_antes)
        nube.USUARIO.set(None)
    assert not d.FakeCliente.__instancecheck__(nube.cliente()) if nube.conectado() else True
    print("Demo: pruebas OK")
