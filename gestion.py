# gestion.py - Fase 4: panel del superadmin. Configuración general, registro de actividad, visitas, mensajes de
# contacto, cifras generales, salud del sistema, límites gratis, Telegram de admin y sentimiento de la comunidad.
# Todo en la tabla "ajustes" de Supabase (gratis, sin tablas nuevas):
#   correo "*"         -> configuración general (mantenimiento, automático para todos, universidades, uso de Actions)
#   correo del usuario -> "bloqueado", "visita:<fecha>"
#   correo "registro"  -> "log:<fecha y hora>:<id>"   (quién cambió qué y cuándo)
#   correo "contacto"  -> "msg:<fecha y hora>:<id>"   (Reportar problema y Contacto)
# Uso:  python gestion.py prueba | fuentes | uso-actions

import json
import os
import sys
import time
import uuid
from datetime import date, datetime, timedelta

import pandas as pd
import requests

import nube

GENERAL = "*"


# ---------- Configuración general ----------
def ajuste(clave, defecto=None):
    try:
        v = nube.leer_ajuste(clave, GENERAL)
        return defecto if v is None else v
    except Exception:
        return defecto


def poner(clave, valor, quien=None):
    nube.guardar_ajuste(clave, valor, GENERAL)
    registrar(quien or nube.usuario(), f"Cambió «{clave}»", valor)


def mantenimiento():
    """{'activo': bool, 'mensaje': str, 'bloquear': bool}."""
    return ajuste("mantenimiento", {"activo": False, "mensaje": "", "bloquear": False})


def automatico_global():
    """False = el modo automático está apagado para TODOS (interruptor del superadmin)."""
    return bool(ajuste("automatico_global", True))


def universidades(base):
    """La lista de universidades del superadmin (o la de siempre si nunca la cambió)."""
    return ajuste("universidades", None) or base


def bloqueado(email):
    try:
        return bool(nube.leer_ajuste("bloqueado", email))
    except Exception:
        return False


def bloquear(email, si=True, quien=None):
    if email == nube.superadmin():
        raise ValueError("No puedes bloquearte a ti mismo.")
    nube.guardar_ajuste("bloqueado", bool(si), email)
    registrar(quien or nube.usuario(), "Bloqueó una cuenta" if si else "Desbloqueó una cuenta", email)


# ---------- Registro de actividad y visitas ----------
def registrar(quien, que, detalle=None):
    """Quién cambió qué y cuándo. Nunca detiene la app si falla."""
    try:
        ahora = datetime.now()
        nube.guardar_ajuste(f"log:{ahora:%Y-%m-%d %H:%M:%S}:{uuid.uuid4().hex[:6]}",
                            {"fecha": f"{ahora:%Y-%m-%d %H:%M:%S}", "quien": quien, "que": que,
                             "detalle": detalle if isinstance(detalle, (str, int, float, bool, type(None))) else json.dumps(
                                 detalle, ensure_ascii=False, default=str)[:500]}, "registro")
    except Exception:
        pass


def actividad(dias=30):
    desde = f"log:{date.today() - timedelta(days=dias)}"
    filas = nube.cliente().table("ajustes").select("valor").eq("email", "registro").gte("clave", desde).execute().data
    t = pd.DataFrame([f["valor"] for f in filas])
    return t.sort_values("fecha", ascending=False) if len(t) else pd.DataFrame(columns=["fecha", "quien", "que", "detalle"])


def visita(email, pagina=""):
    """Anota que el usuario usó la app hoy (una fila por día; cuenta las páginas que abrió)."""
    try:
        clave = f"visita:{date.today()}"
        actual = nube.leer_ajuste(clave, email) or {"paginas": 0}
        nube.guardar_ajuste(clave, {"paginas": actual.get("paginas", 0) + 1, "ultima": pagina}, email)
    except Exception:
        pass


def uso(que):
    """Cuenta el uso de una función (por ejemplo, abrir las predicciones), por día."""
    try:
        clave = f"uso:{date.today()}"
        actual = nube.leer_ajuste(clave, GENERAL) or {}
        actual[que] = actual.get(que, 0) + 1
        nube.guardar_ajuste(clave, actual, GENERAL)
    except Exception:
        pass


# ---------- Mensajes de contacto ----------
TIPOS_PERSONA = ["Estudiante", "Profesor", "Inversionista", "Otro"]


def mensaje(tipo, nombre, correo, persona, texto, pagina=""):
    """Guarda un 'Reportar problema' o 'Contacto' y avisa por el Telegram de admin."""
    ahora = datetime.now()
    m = {"fecha": f"{ahora:%Y-%m-%d %H:%M:%S}", "tipo": tipo, "nombre": nombre.strip()[:80],
         "correo": correo.strip()[:120], "persona": persona, "texto": texto.strip()[:2000], "pagina": pagina,
         "leido": False}
    nube.guardar_ajuste(f"msg:{ahora:%Y-%m-%d %H:%M:%S}:{uuid.uuid4().hex[:6]}", m, "contacto")
    alerta_admin(f"{'🐞' if tipo == 'Problema' else '✉️'} {tipo} de {m['nombre']} ({m['persona']}, {m['correo']}):\n"
                 f"{m['texto'][:800]}" + (f"\nPantalla: {pagina}" if pagina else ""))


def mensajes():
    filas = nube.cliente().table("ajustes").select("clave,valor").eq("email", "contacto").execute().data
    t = pd.DataFrame([{**f["valor"], "clave": f["clave"]} for f in filas])
    return t.sort_values("fecha", ascending=False) if len(t) else t


def marcar_leido(clave):
    v = nube.leer_ajuste(clave, "contacto")
    nube.guardar_ajuste(clave, {**v, "leido": True}, "contacto")


# ---------- Telegram de admin (segundo bot, solo para ti) ----------
def alerta_admin(texto):
    """Manda un mensaje al bot de admin. Sin bot de admin configurado, queda solo en el panel."""
    token, chat = nube.secreto("ADMIN_TELEGRAM_TOKEN"), nube.secreto("ADMIN_TELEGRAM_CHAT_ID")
    if not (token and chat):
        return False
    try:
        r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                          data={"chat_id": chat, "text": f"🛠️ ADMIN\n{texto}"[:4000]}, timeout=15)
        return r.ok
    except Exception:
        return False


def chat_del_bot_admin():
    """Busca tu número de chat en el bot de admin (después de escribirle «hola»)."""
    token = nube.secreto("ADMIN_TELEGRAM_TOKEN")
    if not token:
        return None
    r = requests.get(f"https://api.telegram.org/bot{token}/getUpdates", timeout=15).json()
    chats = [u["message"]["chat"]["id"] for u in r.get("result", []) if "message" in u]
    return str(chats[-1]) if chats else None


# ---------- Cifras generales ----------
def cifras(hoy=None):
    """Lo que muestra el panel y el modo presentación."""
    import activos
    hoy = hoy or date.today()
    c = nube.cliente()
    usuarios_ = c.table("usuarios").select("email,rol,creado").execute().data
    visitas = pd.DataFrame([{"email": f["email"], "dia": f["clave"].split(":", 1)[1]} for f in
                            c.table("ajustes").select("email,clave").like("clave", "visita:%").execute().data])
    ops = pd.DataFrame(c.table("operaciones").select("email,cartera,Fecha,Tipo,Precio,Cantidad,Tasa_COP,Activo")
                       .execute().data)
    semana = str(hoy - timedelta(days=6))
    activos_hoy = visitas.loc[visitas["dia"] == str(hoy), "email"].nunique() if len(visitas) else 0
    activos_semana = visitas.loc[visitas["dia"] >= semana, "email"].nunique() if len(visitas) else 0
    vuelven = int((visitas.groupby("email")["dia"].nunique() >= 2).sum()) if len(visitas) else 0
    if len(ops):
        ops["dia"] = pd.to_datetime(ops["Fecha"], format="mixed").dt.date
    del_dia = ops[ops["dia"] == hoy] if len(ops) else ops
    operaron = set(ops["email"]) if len(ops) else set()
    nunca = [u["email"] for u in usuarios_ if u["email"] not in operaron]
    ganancias, perdidas = resultados_por_usuario(ops)
    usos = {}
    for f in c.table("ajustes").select("valor").eq("email", GENERAL).like("clave", "uso:%").execute().data:
        for k, v in (f["valor"] or {}).items():
            usos[k] = usos.get(k, 0) + v
    tipos = pd.Series([activos.tipo_nombre(s) for s in activos.ACTIVOS]).value_counts()
    return {"usuarios": len(usuarios_), "roles": pd.Series([u["rol"] for u in usuarios_]).value_counts().to_dict(),
            "activos_hoy": activos_hoy, "activos_semana": activos_semana, "vuelven": vuelven,
            "compras_hoy": int((del_dia["Tipo"] == "COMPRA").sum()) if len(del_dia) else 0,
            "ventas_hoy": int((del_dia["Tipo"] == "VENTA").sum()) if len(del_dia) else 0,
            "ganancia_promedio": ganancias, "perdida_promedio": perdidas, "uso_predicciones": usos,
            "nunca_operaron": len(nunca), "activos_por_tipo": tipos.to_dict(),
            "visitas_por_dia": visitas.groupby("dia")["email"].nunique().sort_index() if len(visitas) else pd.Series(dtype=int),
            "operaciones_por_dia": ops.groupby(["dia", "Tipo"]).size().unstack(fill_value=0) if len(ops) else pd.DataFrame()}


def resultados_por_usuario(ops):
    """(ganancia promedio, pérdida promedio) en pesos, de las ventas de todos (costo promedio, como la app)."""
    if ops is None or not len(ops):
        return 0.0, 0.0
    resultados = []
    for (_, _), g in ops.groupby(["email", "cartera"]):
        g = g.sort_values("Fecha")
        cant, costo = {}, {}
        for _, o in g.iterrows():
            a = o["Activo"]
            if o["Tipo"] == "COMPRA":
                cant[a] = cant.get(a, 0) + o["Cantidad"]
                costo[a] = costo.get(a, 0) + o["Precio"] * o["Cantidad"]
            elif cant.get(a):
                prom = costo[a] / cant[a]
                resultados.append((o["Precio"] - prom) * o["Cantidad"] * float(o["Tasa_COP"] or 1))
                cant[a] -= o["Cantidad"]
                costo[a] -= prom * o["Cantidad"]
    r = pd.Series(resultados, dtype=float)
    return float(r[r > 0].mean()) if (r > 0).any() else 0.0, float(r[r < 0].mean()) if (r < 0).any() else 0.0


def perfil(email):
    """Compras, rendimiento y ganancias de un usuario (todas sus carteras: personal y eventos)."""
    t = nube.cliente().table("operaciones").select("cartera,Fecha,Activo,Tipo,Precio,Cantidad,Moneda,Tasa_COP,Nota") \
        .eq("email", email).execute().data
    ops = pd.DataFrame(t)
    if ops.empty:
        return ops, {}
    g, p = resultados_por_usuario(ops.assign(email=email))
    return ops.sort_values("Fecha", ascending=False), {"operaciones": len(ops), "carteras": ops["cartera"].nunique(),
                                                      "ganancia_promedio": g, "perdida_promedio": p,
                                                      "ultima": str(ops["Fecha"].max())[:16]}


# ---------- Salud del sistema ----------
def revisar_fuentes():
    """{fuente: (ok, segundos, detalle)} para Yahoo Finance, Google Noticias, Binance y Supabase."""
    def medir(nombre, funcion):
        t = time.time()
        try:
            detalle = funcion()
            return nombre, (True, round(time.time() - t, 1), detalle)
        except Exception as error:
            return nombre, (False, round(time.time() - t, 1), str(error)[:120])

    def yahoo():
        import yfinance as yf
        d = yf.download("SPY", period="5d", progress=False)
        assert not d.empty, "sin datos"
        return f"SPY {float(d['Close'].iloc[-1].iloc[0] if hasattr(d['Close'].iloc[-1], 'iloc') else d['Close'].iloc[-1]):.2f}"

    def noticias_():
        r = requests.get("https://news.google.com/rss/search", params={"q": "oil", "hl": "en-US", "gl": "US",
                                                                       "ceid": "US:en"}, timeout=15)
        assert r.ok and "<item>" in r.text, f"HTTP {r.status_code}"
        return f"{r.text.count('<item>')} titulares"

    def binance_():
        import binance
        p = binance.precio("BTC-USD")
        assert p, "sin respuesta"
        return f"BTC {p:,.0f}"

    def supabase_():
        nube.cliente().table("usuarios").select("email").limit(1).execute()
        return "responde"
    return dict(medir(n, f) for n, f in (("Yahoo Finance (precios)", yahoo), ("Google Noticias", noticias_),
                                         ("Binance (cripto en vivo)", binance_), ("Supabase (base de datos)", supabase_)))


def avisar_fuentes_caidas():
    """En la vigilancia de la nube: si una fuente falla, avisa al Telegram de admin (una vez por día y fuente)."""
    caidas = [n for n, (ok, _, _) in revisar_fuentes().items() if not ok]
    enviados = ajuste("fuentes_avisadas", {}) or {}
    hoy = str(date.today())
    nuevas = [n for n in caidas if enviados.get(n) != hoy]
    if nuevas:
        alerta_admin("⚠️ Fuente caída: " + ", ".join(nuevas))
        nube.guardar_ajuste("fuentes_avisadas", {**enviados, **{n: hoy for n in nuevas}}, GENERAL)
    return caidas


def limites():
    """Cuánto llevas de los límites gratis (lo que se puede medir desde la app)."""
    c = nube.cliente()
    archivos = c.storage.from_(nube.BUCKET).list("", {"limit": 1000})
    almacen = sum((a.get("metadata") or {}).get("size", 0) for a in archivos) / 1e6
    filas = {t: len(c.table(t).select("email").execute().data) for t in ("usuarios", "operaciones", "ajustes")}
    memoria = None
    try:
        with open("/proc/self/status") as f:                 # Solo en Linux (la nube de Streamlit)
            memoria = next(int(l.split()[1]) / 1024 for l in f if l.startswith("VmRSS"))
    except Exception:
        pass
    return {"Supabase almacenamiento (MB de 1.000)": round(almacen, 1),
            "Supabase filas (usuarios / operaciones / ajustes)": f"{filas['usuarios']} / {filas['operaciones']} / {filas['ajustes']}",
            "GitHub Actions (minutos este mes de 2.000)": (ajuste("uso_actions", {}) or {}).get("minutos"),
            "Streamlit memoria de la app (MB de ~1.000)": None if memoria is None else round(memoria)}


def guardar_uso_actions():
    """Lo corre GitHub Actions cada mañana: suma los minutos de las tareas del mes (aprox., redondeando por tarea)."""
    repo, token = os.getenv("GITHUB_REPOSITORY"), os.getenv("GITHUB_TOKEN")
    inicio = date.today().replace(day=1)
    minutos, pagina = 0, 1
    while True:
        r = requests.get(f"https://api.github.com/repos/{repo}/actions/runs", timeout=30,
                         headers={"Authorization": f"Bearer {token}"},
                         params={"created": f">={inicio}", "per_page": 100, "page": pagina}).json()
        corridas = r.get("workflow_runs", [])
        for x in corridas:
            if x.get("run_started_at") and x.get("updated_at"):
                seg = (pd.Timestamp(x["updated_at"]) - pd.Timestamp(x["run_started_at"])).total_seconds()
                minutos += max(1, int(-(-seg // 60)))
        if len(corridas) < 100:
            break
        pagina += 1
    nube.guardar_ajuste("uso_actions", {"minutos": minutos, "fecha": str(date.today())}, GENERAL)
    return minutos


# ---------- Sentimiento de la comunidad (anónimo y agregado) ----------
def comunidad(dias=7):
    """Qué compró la comunidad en los últimos días, por mercado (anónimo): [(mercado, % de las compras)]."""
    import activos
    desde = str(date.today() - timedelta(days=dias))
    filas = nube.cliente().table("operaciones").select("Activo,Tipo,Fecha").eq("Tipo", "COMPRA").gte("Fecha", desde) \
        .execute().data
    if not filas:
        return pd.Series(dtype=float), 0
    mercados = pd.Series([activos.mercados(f["Activo"])[0] if activos.mercados(f["Activo"]) else "otros" for f in filas])
    return (mercados.value_counts(normalize=True) * 100).round(0), len(filas)


def comunidad_validada(minimo=30, mejora=5.0):
    """Backtest: ¿las compras de la comunidad aciertan más que la app? Solo entonces se usa como señal extra.
    Acierto = el precio subió en los 5 días de mercado siguientes. Devuelve (usar, texto)."""
    import aciertos
    import activos
    filas = nube.cliente().table("operaciones").select("Activo,Fecha").eq("Tipo", "COMPRA").execute().data
    resultados = []
    for f in filas:
        try:
            c = pd.read_csv(activos.ruta_precios(f["Activo"]), index_col="Fecha", parse_dates=True)["Cierre"]
            i = c.index.searchsorted(pd.Timestamp(f["Fecha"]).normalize())
            if i + 5 < len(c):
                resultados.append(c.iloc[i + 5] > c.iloc[i])
        except Exception:
            continue
    app = aciertos.resumen().get("app_%")
    if len(resultados) < minimo or app is None:
        return False, (f"Aún no hay datos suficientes para el backtest ({len(resultados)} compras revisadas de "
                       f"{minimo} necesarias): se muestra solo como información.")
    comunidad_pct = sum(resultados) / len(resultados) * 100
    usar = comunidad_pct >= app + mejora
    return usar, (f"Backtest: la comunidad acertó {comunidad_pct:.0f}% vs. la app {app:.0f}% en {len(resultados)} "
                  f"compras. {'Se usa como señal extra.' if usar else 'No mejora los aciertos: solo información.'}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    orden = sys.argv[1] if len(sys.argv) > 1 else "prueba"
    if orden == "fuentes":
        for n, (ok, s, d) in revisar_fuentes().items():
            print(f"{'OK ' if ok else 'MAL'} {n}: {s} s · {d}")
    elif orden == "uso-actions":
        print("Minutos de GitHub Actions este mes:", guardar_uso_actions())
    else:
        ops = pd.DataFrame([{"email": "a", "cartera": "sim", "Fecha": "2026-11-01", "Activo": "X", "Tipo": "COMPRA",
                             "Precio": 100.0, "Cantidad": 2.0, "Tasa_COP": 1.0},
                            {"email": "a", "cartera": "sim", "Fecha": "2026-11-02", "Activo": "X", "Tipo": "VENTA",
                             "Precio": 110.0, "Cantidad": 1.0, "Tasa_COP": 1.0},
                            {"email": "b", "cartera": "sim", "Fecha": "2026-11-01", "Activo": "Y", "Tipo": "COMPRA",
                             "Precio": 50.0, "Cantidad": 1.0, "Tasa_COP": 1.0},
                            {"email": "b", "cartera": "sim", "Fecha": "2026-11-03", "Activo": "Y", "Tipo": "VENTA",
                             "Precio": 40.0, "Cantidad": 1.0, "Tasa_COP": 1.0}])
        assert resultados_por_usuario(ops) == (10.0, -10.0), resultados_por_usuario(ops)
        assert resultados_por_usuario(pd.DataFrame()) == (0.0, 0.0)
        print("Gestión: pruebas OK")
