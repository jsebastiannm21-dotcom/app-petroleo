# nube.py - Conexión con Supabase (base de datos y archivos), gratis.
# - Tablas: usuarios, operaciones (Mis activos y el simulador de cada usuario), ajustes y diario de errores.
# - Archivos compartidos (ranking, noticias, dividendos...) y precios: en el almacenamiento "datos" de Supabase.
# - Las claves se leen de los "secrets" de Streamlit o del archivo .env. NUNCA están en el código.
# - Sin claves (tu PC como antes), todo sigue funcionando con los archivos locales.
# Uso:  python nube.py migrar                      (sube tus datos de este PC a Supabase y verifica que llegó todo)
#       python nube.py tarea manana                 (GitHub Actions: baja datos, corre la tarea y sube los resultados)
#       python nube.py kronos                       (en tu PC: predicciones de Kronos, guardadas en Supabase)

import contextvars
import io
import json
import os
import runpy
import sys
from pathlib import Path

import pandas as pd

CARPETA = Path(__file__).resolve().parent
BUCKET = "datos"
# Archivos que escriben las tareas (GitHub Actions o tu PC) y que lee la app
COMPARTIDOS = ["ranking.csv", "noticias.csv", "noticias_estado.json", "dividendos.csv", "analisis_claude.csv",
               "predicciones.csv", "historial_alertas.csv", "estado_alertas.json", "registro_sugerencias.csv",
               "cierres_semanales.csv", "backtest_semanal.csv", "backtest_semanal_estado.json",
               "simulador_historial.csv", "comisiones.json", "fichas.json", "indicadores.csv", "precios_petroleo.csv"]
PRECIOS = "precios.parquet"                # Todos los precios diarios en un solo archivo comprimido
COLUMNAS_PRECIO = ("Apertura", "Maximo", "Minimo", "Cierre")   # El volumen solo lo usa Kronos, que vive en tu PC
USUARIO = contextvars.ContextVar("usuario", default=None)   # El usuario de esta sesión (cada pestaña del navegador)
EVENTO = contextvars.ContextVar("evento", default=None)     # El evento (dict) cuyo simulador se está usando, o None
_cliente = None


def secreto(nombre):
    """Una clave: primero el entorno (.env o GitHub Actions), luego los secrets de Streamlit."""
    if not os.getenv(nombre):
        try:
            from dotenv import load_dotenv
            load_dotenv(CARPETA / ".env")
        except Exception:
            pass
    valor = os.getenv(nombre)
    if valor:
        return valor.strip()
    try:
        import streamlit as st
        return str(st.secrets.get(nombre, "")).strip() or None
    except Exception:
        return None


def conectado():
    return bool(secreto("SUPABASE_URL") and secreto("SUPABASE_KEY"))


def cliente():
    global _cliente
    if _cliente is None:
        from supabase import create_client
        _cliente = create_client(secreto("SUPABASE_URL"), secreto("SUPABASE_KEY"))
    return _cliente


def superadmin():
    return (secreto("SUPERADMIN_EMAIL") or "superadmin").lower()


def usuario():
    """Correo del usuario de esta sesión. En tu PC y en las tareas programadas, el superadmin."""
    return (USUARIO.get() or superadmin()).lower()


# ---------- Memoria corta: una misma carga de página pide los mismos datos varias veces ----------
_MEMORIA, _SEGUNDOS = {}, 3.0


def _recordado(clave, leer):
    """Devuelve lo leído hace menos de 3 segundos (cada clave incluye el correo: nunca se cruzan usuarios)."""
    import copy
    import time
    hora, valor = _MEMORIA.get(clave, (0, None))
    if time.time() - hora > _SEGUNDOS:
        valor = leer()
        _MEMORIA[clave] = (time.time(), valor)
    return copy.deepcopy(valor)


def _olvidar(email):
    for clave in [k for k in _MEMORIA if k[1] == email]:
        _MEMORIA.pop(clave, None)


# ---------- Operaciones (compras y ventas) ----------
def leer_operaciones(email, cartera):
    return _recordado(("ops", email, cartera), lambda: _leer_operaciones(email, cartera))


def _leer_operaciones(email, cartera):
    filas = cliente().table("operaciones").select("*").eq("email", email).eq("cartera", cartera).order("id").execute().data
    t = pd.DataFrame(filas)
    return t.drop(columns=["id", "email", "cartera"], errors="ignore")


def reemplazar_operaciones(email, cartera, tabla):
    """Guarda la tabla completa de una cartera (borra la anterior y escribe la nueva, en ese orden)."""
    filas = json.loads(tabla.assign(Fecha=pd.to_datetime(tabla["Fecha"]).dt.strftime("%Y-%m-%d %H:%M:%S.%f"))
                       .to_json(orient="records", force_ascii=False))
    for f in filas:
        f.update(email=email, cartera=cartera)
    _olvidar(email)
    c = cliente().table("operaciones")
    c.delete().eq("email", email).eq("cartera", cartera).execute()
    if filas:
        c.insert(filas).execute()


# ---------- Ajustes (configuración del simulador, stops personales, comisiones) ----------
def leer_ajuste(clave, email=None, defecto=None):
    email = email or usuario()
    filas = _recordado(("ajuste", email, clave), lambda: cliente().table("ajustes").select("valor").eq("email", email)
                       .eq("clave", clave).execute().data)
    return filas[0]["valor"] if filas else defecto


def guardar_ajuste(clave, valor, email=None):
    email = email or usuario()
    _olvidar(email)
    cliente().table("ajustes").upsert({"email": email, "clave": clave, "valor": valor}).execute()


# ---------- Archivos compartidos y precios ----------
def subir(nombres=COMPARTIDOS):
    almacen = cliente().storage.from_(BUCKET)
    for n in nombres:
        ruta = CARPETA / n
        if ruta.exists():
            almacen.upload(n, ruta.read_bytes(), {"upsert": "true", "content-type": "application/octet-stream"})


_VERSIONES = CARPETA / ".versiones_nube.json"            # Qué versión de cada archivo ya está bajada


def bajar(nombres=COMPARTIDOS):
    """Baja SOLO los archivos que cambiaron desde la última vez (así no se gasta el límite gratis de Supabase)."""
    almacen = cliente().storage.from_(BUCKET)
    en_nube = {a["name"]: a.get("updated_at") for a in almacen.list("", {"limit": 1000})}
    tengo = json.loads(_VERSIONES.read_text()) if _VERSIONES.exists() else {}
    cambiados = []
    for n in nombres:
        if n in en_nube and (tengo.get(n) != en_nube[n] or not (CARPETA / n).exists()):
            (CARPETA / n).write_bytes(almacen.download(n))
            tengo[n] = en_nube[n]
            cambiados.append(n)
    _VERSIONES.write_text(json.dumps(tengo))
    return cambiados


def empacar_precios():
    """Todos los precios_*.csv de la carpeta datos en un solo archivo comprimido (unos 15 MB en vez de 211 MB)."""
    import activos
    partes = []
    for s in activos.ACTIVOS:
        ruta = activos.ruta_precios(s)
        if ruta.exists():
            t = pd.read_csv(ruta, parse_dates=["Fecha"], usecols=lambda c: c in ("Fecha", *COLUMNAS_PRECIO))
            t[[c for c in COLUMNAS_PRECIO if c in t]] = t[[c for c in COLUMNAS_PRECIO if c in t]].astype("float32")
            t.insert(0, "Simbolo", s)
            partes.append(t)
    pd.concat(partes).to_parquet(CARPETA / PRECIOS, index=False, compression="zstd")


def desempacar_precios():
    """Vuelve a escribir los precios y los indicadores de cada activo desde el archivo comprimido."""
    import activos
    for s, t in pd.read_parquet(CARPETA / PRECIOS).groupby("Simbolo"):
        t = t.drop(columns="Simbolo").dropna(axis=1, how="all").set_index("Fecha")
        t.to_csv(activos.ruta_precios(s))
        activos.calcular_indicadores(t["Cierre"]).to_csv(activos.ruta_indicadores(s))


def preparar_app():
    """En la app de la nube: baja los archivos compartidos y los precios que cambiaron."""
    if PRECIOS in bajar(COMPARTIDOS + [PRECIOS]):
        desempacar_precios()


# Tareas de GitHub Actions: (programa, argumentos, archivos que usa, ¿actualiza los precios de todos los activos?)
ALERTAS_LIVIANAS = ["estado_alertas.json", "noticias.csv", "noticias_estado.json", "historial_alertas.csv",
                    "comisiones.json"]
TAREAS = {"vigilar": ("alertas.py", ["--momento", "vigilar"], ALERTAS_LIVIANAS, False),
          "finde": ("alertas.py", ["--momento", "finde"], ALERTAS_LIVIANAS, False),
          "backtest": ("backtest_semanal.py", [], ["backtest_semanal.csv", "backtest_semanal_estado.json"], False),
          "claude": ("analisis_claude.py", [], ["ranking.csv", "noticias.csv", "analisis_claude.csv"], False),
          # Los precios completos (19 MB) solo se suben 2 veces al día para no gastar el límite gratis de descargas;
          # los otros horarios igual actualizan el ranking (que trae el precio y el cambio del día)
          **{m: ("alertas.py", ["--momento", m], COMPARTIDOS, m in ("manana", "cierre"))
             for m in ("manana", "apertura", "mediodia", "cierre", "noche")}}


def tarea(nombre):
    """Baja lo que la tarea necesita, la corre y sube los resultados."""
    script, argumentos, archivos, precios = TAREAS[nombre]
    bajar(archivos)
    sys.argv = [script] + argumentos
    try:
        runpy.run_path(str(CARPETA / script), run_name="__main__")
    finally:
        if precios:                                    # Solo las que bajaron los precios de todos los activos
            empacar_precios()
        subir(archivos + ([PRECIOS] if precios else []))


# ---------- Migración de los datos de este PC ----------
def _normalizar(t):
    t = t.copy()
    t["Fecha"] = pd.to_datetime(t["Fecha"]).dt.strftime("%Y-%m-%d %H:%M:%S")
    for c in t.columns:
        if c != "Fecha":
            num = pd.to_numeric(t[c], errors="coerce")
            t[c] = num.round(6) if num.notna().sum() == t[c].notna().sum() else t[c].fillna("").astype(str)
    return t.reset_index(drop=True)


def migrar():
    """Sube a Supabase tus compras, ventas, simulador, ajustes, diario y archivos, y comprueba que llegó todo."""
    import errores
    import mis_activos
    import simulador
    yo = superadmin()
    informe = []
    for nombre, archivo, cartera_bd in [("Mis activos (compras y ventas reales)", CARPETA / "mis_operaciones.csv", "real"),
                                        ("Simulador", CARPETA / "simulador_operaciones.csv", "sim")]:
        local = pd.read_csv(archivo, encoding="utf-8-sig") if archivo.exists() else pd.DataFrame()
        if len(local):
            reemplazar_operaciones(yo, cartera_bd, local)
        nube = leer_operaciones(yo, cartera_bd)
        iguales = len(local) == len(nube) and (not len(local) or _normalizar(local).equals(
            _normalizar(nube[list(local.columns)])))
        informe.append((nombre, len(local), len(nube), iguales))
    for clave, archivo in [("simulador_config", "simulador_config.json"), ("stops_personales", "stops_personales.json")]:
        ruta = CARPETA / archivo
        if ruta.exists():
            valor = json.loads(ruta.read_text(encoding="utf-8"))
            guardar_ajuste(clave, valor, yo)
            informe.append((archivo, 1, 1, leer_ajuste(clave, yo) == valor))
    if errores.ARCHIVO.exists():
        local = pd.read_csv(errores.ARCHIVO, encoding="utf-8-sig")
        cliente().table("diario_errores").delete().eq("email", yo).execute()
        if len(local):
            cliente().table("diario_errores").insert(
                [{**f, "email": yo} for f in json.loads(local.to_json(orient="records", force_ascii=False))]).execute()
        informe.append(("Diario de errores", len(local), len(errores.leer()), True))
    empacar_precios()
    subir(COMPARTIDOS + [PRECIOS])
    almacen = {a["name"] for a in cliente().storage.from_(BUCKET).list()}
    faltan = [n for n in COMPARTIDOS + [PRECIOS] if (CARPETA / n).exists() and n not in almacen]
    informe.append((f"Archivos compartidos y precios ({len(almacen)} en la nube)", len(almacen) + len(faltan),
                    len(almacen), not faltan))
    del mis_activos, simulador
    return informe


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    orden = sys.argv[1] if len(sys.argv) > 1 else ""
    if orden == "migrar":
        todo_bien = True
        for nombre, local, nube, ok in migrar():
            todo_bien &= ok
            print(f"{'OK ' if ok else 'MAL'} {nombre}: en tu PC {local}, en Supabase {nube}")
        print("Todo llegó completo." if todo_bien else "ATENCIÓN: algo no coincide. Tus archivos locales siguen intactos.")
    elif orden == "tarea":
        tarea(sys.argv[2])
    elif orden == "kronos":
        def _kronos():
            import activos
            import mis_activos
            import predicciones
            sigue = list(activos.REFERENCIAS.values()) + activos.SIMULAR + list(mis_activos.abiertas().get("Activo", []))
            print(f"Predicciones nuevas: {predicciones.registrar(list(dict.fromkeys(sigue)))}")
        bajar(["predicciones.csv"])
        import activos
        import mis_activos
        activos.actualizar_varios(list(activos.REFERENCIAS.values()) + activos.SIMULAR +
                                  list(mis_activos.abiertas().get("Activo", [])))   # Precios frescos en este PC
        _kronos()
        subir(["predicciones.csv"])                     # shortcut: si la nube escribió en este minuto, gana el PC
    else:
        print("Uso: python nube.py migrar | tarea <" + "|".join(TAREAS) + "> | kronos")
