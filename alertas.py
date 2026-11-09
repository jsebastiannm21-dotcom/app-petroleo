# alertas.py - Alertas y reportes por Telegram
# La clave del bot se lee del archivo .env (nunca se escribe en el código).
#
# Formas de usarlo:
#   python alertas.py --chat-id     -> busca tu número de chat y lo guarda en .env
#   python alertas.py --prueba      -> manda un mensaje de prueba
#   python alertas.py               -> actualiza datos y manda las alertas nuevas
#   python alertas.py --momento X   -> igual, más el mensaje de ese horario (días hábiles, hora de Bogotá):
#       manana (8:00)    reporte del día, top 5 y dividendos próximos
#       apertura (9:45)  qué comprar y qué vender hoy (+ órdenes para Trii)
#       mediodia (12:00) revisión por si algo tocó el stop o el objetivo
#       cierre (15:30)   última llamada antes del cierre
#       noche (20:00)    resumen del día y noticias de la noche
#       vigilar          cada 15 minutos con el mercado abierto: avisa al momento si una posición
#                        (real o simulada) toca el stop loss o el objetivo
#
# Qué se vigila:
#   - Activos "vigilados" (los del simulador + Mis activos): cambios de zona de probabilidad,
#     patrones de gráfica y cercanía al stop loss u objetivo.
#   - Todos los demás: solo cuando llegan a COMPRAR (en un solo mensaje).
#   - Eventos del calendario de hoy y mañana.

import argparse
import json
import math
import os
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv, set_key

CARPETA = Path(__file__).resolve().parent
os.chdir(CARPETA)                    # Para que funcione aunque Windows lo corra desde otra carpeta
sys.stdout.reconfigure(encoding="utf-8", errors="replace")   # Para que se vean los emojis
ENV = CARPETA / ".env"
ESTADO = CARPETA / "estado_alertas.json"       # Recuerda qué alertas ya se mandaron
HISTORIAL = CARPETA / "historial_alertas.csv"  # Todas las alertas (la app muestra las de hoy)
CERCA = 1.0    # "Cerca" del stop o del objetivo = a 1 punto porcentual o menos

import activos  # noqa: E402  (después del chdir)
import calendario  # noqa: E402
import estrategia  # noqa: E402


# ---------- Telegram ----------
def config():
    load_dotenv(ENV, override=True)
    return os.getenv("TELEGRAM_TOKEN", "").strip(), os.getenv("TELEGRAM_CHAT_ID", "").strip()


def telegram_listo():
    token, chat = config()
    return bool(token and chat)


def tiene_token():
    return bool(config()[0])


def enviar(texto):
    token, chat = config()
    if not (token and chat):
        print("[Telegram no configurado] " + texto.replace("\n", " | "))
        return False
    # Telegram acepta máximo 4096 caracteres por mensaje: partimos por líneas
    partes, actual = [], ""
    for linea in texto.split("\n"):
        if len(actual) + len(linea) + 1 > 3900:
            partes.append(actual)
            actual = ""
        actual += linea + "\n"
    partes.append(actual)
    for parte in partes:
        try:
            r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", timeout=20,
                              data={"chat_id": chat, "text": parte[:4096], "disable_web_page_preview": "true"})
        except requests.RequestException as error:
            print(f"No se pudo conectar con Telegram: {error}")
            return False
        if not r.ok:
            print(f"Telegram respondió con error {r.status_code}: {r.json().get('description', '')}")
            return False
    return True


def obtener_chat_id():
    token, _ = config()
    if not token:
        raise SystemExit("Primero pon TELEGRAM_TOKEN en el archivo .env")
    r = requests.get(f"https://api.telegram.org/bot{token}/getUpdates", timeout=20).json()
    if not r.get("ok"):
        raise SystemExit(f"Telegram rechazó la clave: {r.get('description')}. Revisa el TELEGRAM_TOKEN.")
    chats = [u["message"]["chat"] for u in r["result"] if "message" in u]
    if not chats:
        raise SystemExit("No encontré mensajes. Abre tu bot en Telegram, escríbele 'hola' y vuelve a correr esto.")
    chat = chats[-1]
    set_key(str(ENV), "TELEGRAM_CHAT_ID", str(chat["id"]))
    print(f"Listo: chat de {chat.get('first_name', '')} guardado en .env (número {chat['id']})")


def anotar(textos):
    """Guarda las alertas en el historial para que la app muestre las de hoy."""
    if not textos:
        return
    nuevas = pd.DataFrame({"Fecha_hora": datetime.now().strftime("%Y-%m-%d %H:%M"), "Alerta": textos})
    viejas = pd.read_csv(HISTORIAL, encoding="utf-8-sig") if HISTORIAL.exists() else None
    tabla = pd.concat([viejas, nuevas]) if viejas is not None else nuevas
    tabla.tail(2000).to_csv(HISTORIAL, index=False, encoding="utf-8-sig")


def alertas_de_hoy():
    if not HISTORIAL.exists():
        return pd.DataFrame(columns=["Fecha_hora", "Alerta"])
    tabla = pd.read_csv(HISTORIAL, encoding="utf-8-sig")
    return tabla[tabla["Fecha_hora"].str.startswith(datetime.now().strftime("%Y-%m-%d"))].iloc[::-1]


# ---------- Qué vigilar ----------
def zona(r):
    if not r["suficiente"] or r["prob"] is None or math.isnan(r["prob"]):
        return "esperar"
    if r["prob"] >= estrategia.UMBRAL_COMPRA:
        return "compra"
    if r["prob"] > estrategia.ALERTA_ALTA:
        return "alta"
    if r["prob"] < estrategia.ALERTA_BAJA:
        return "baja"
    return "neutral"


MENSAJE_ZONA = {
    "compra": "🟢 {a}: COMPRAR, la probabilidad de subida llegó a {p:.1f}% (56% o más).",
    "alta": "🟡 {a}: la probabilidad de subida pasó de 55% ({p:.1f}%). Cerca de señal de compra.",
    "baja": "🔴 {a}: la probabilidad de subida bajó de 50% ({p:.1f}%). Sesgo a bajar.",
    "neutral": "⚪ {a}: la probabilidad volvió a zona neutral ({p:.1f}%, entre 50% y 55%).",
}


def detectar_patrones(datos, simbolo=activos.PRINCIPAL):
    """Patrones técnicos que aparecieron en el último día. Devuelve [(clave, texto)]."""
    d = datos.dropna(subset=["MM50", "MM200", "RSI14"])
    if len(d) < 2:
        return []
    hoy, ayer, fecha = d.iloc[-1], d.iloc[-2], d.index[-1].date()
    a = activos.etiqueta(simbolo)
    clave = f"{simbolo}:{fecha}"
    p = []
    alcista_hoy, alcista_ayer = hoy["MM50"] > hoy["MM200"], ayer["MM50"] > ayer["MM200"]
    if alcista_hoy and not alcista_ayer:
        p.append((f"{clave}:cruce", f"✨ {a}: cruce dorado, la media de 50 días cruzó por ENCIMA de la de 200."))
    elif alcista_ayer and not alcista_hoy:
        p.append((f"{clave}:cruce", f"⚠️ {a}: cruce de la muerte, la media de 50 días cruzó por DEBAJO de la de 200."))
    if hoy["RSI14"] > 70 >= ayer["RSI14"]:
        p.append((f"{clave}:rsi", f"📈 {a}: RSI en sobrecompra ({hoy['RSI14']:.0f} > 70), subió muy rápido."))
    elif hoy["RSI14"] < 30 <= ayer["RSI14"]:
        p.append((f"{clave}:rsi", f"📉 {a}: RSI en sobreventa ({hoy['RSI14']:.0f} < 30), cayó muy rápido."))
    if (hoy["Cierre"] > hoy["MM200"]) != (ayer["Cierre"] > ayer["MM200"]):
        lado = "por encima" if hoy["Cierre"] > hoy["MM200"] else "por debajo"
        p.append((f"{clave}:mm200", f"↕️ {a}: el precio cruzó {lado} de la media de 200 días ({hoy['MM200']:,.2f})."))
    cambio = (hoy["Cierre"] / ayer["Cierre"] - 1) * 100
    if abs(cambio) >= 5:
        p.append((f"{clave}:movimiento", f"💥 {a}: movimiento fuerte, {'subió' if cambio > 0 else 'bajó'} "
                                         f"{abs(cambio):.1f}% en un día."))
    return p


def eventos_cercanos():
    """Aviso el día antes de cada evento del calendario (con su hora de Bogotá)."""
    manana = calendario.hoy_colombia() + pd.Timedelta(days=1)
    p = []
    for _, ev in calendario.proximos_eventos(dias=0, desde=manana).iterrows():
        hora = "" if ev["Hora Colombia"] == "todo el día" else f" a las {ev['Hora Colombia']} (hora de Bogotá)"
        p.append((f"{ev['Fecha']}:{ev['Tipo']}:dia_antes", f"📅 MAÑANA{hora} · {ev['Tipo']}: {ev['Evento']}"))
    return p


def eventos_en_una_hora():
    """Aviso una hora antes de los eventos que tienen hora (CPI, empleo, Fed, inventarios, resultados...)."""
    ahora = pd.Timestamp.now(tz=calendario.COLOMBIA).tz_localize(None)
    p = []
    for _, ev in calendario.proximos_eventos(dias=0).iterrows():
        if pd.notna(ev["Momento"]) and pd.Timedelta(0) < ev["Momento"] - ahora <= pd.Timedelta(minutes=75):
            p.append((f"{ev['Fecha']}:{ev['Tipo']}:1h", f"⏰ EN UNA HORA ({ev['Hora Colombia']}, hora de Bogotá) · "
                                                         f"{ev['Tipo']}: {ev['Evento']}"))
    return p


def posiciones_abiertas():
    """Compras abiertas: las reales (Mis activos) y las del simulador. [(origen, activo, ganancia %, fecha)]"""
    import mis_activos
    import simulador
    salida = []
    for _, p in mis_activos.abiertas().iterrows():
        if pd.notna(p["Ganancia_%"]):
            salida.append(("Mis activos", p["Activo"], float(p["Ganancia_%"]), "real"))
    for _, p in simulador.cartera.posiciones().iterrows():
        if pd.notna(p["Ganancia_%"]):
            salida.append(("Simulador", p["Activo"], float(p["Ganancia_%"]), str(p["Fecha_compra"])))
    return salida


def vigilados():
    import mis_activos
    import simulador
    sim = list(simulador.cartera.posiciones(con_precio=False).get("Activo", []))
    return list(dict.fromkeys(activos.SIMULAR + sim + list(mis_activos.abiertas().get("Activo", []))))


# ---------- Estado (para no repetir alertas) ----------
def leer_estado():
    estado = json.loads(ESTADO.read_text(encoding="utf-8")) if ESTADO.exists() else {}
    if not isinstance(estado.get("zonas"), dict):        # Versión anterior del archivo
        estado["zonas"] = {}
    estado.setdefault("enviados", [])
    return estado


def guardar_estado(estado):
    estado.pop("zona", None)
    estado["enviados"] = estado["enviados"][-3000:]
    ESTADO.write_text(json.dumps(estado, ensure_ascii=False, indent=1), encoding="utf-8")


def revisar_alertas(resultados):
    """Manda solo las alertas nuevas. 'resultados' = {símbolo: estrategia.analizar(símbolo)}."""
    estado = leer_estado()
    mensajes, nuevas_compras = [], []
    cerca = set(vigilados())
    for simbolo, r in resultados.items():
        z = zona(r)
        antes = estado["zonas"].get(simbolo)
        if z != antes:
            if simbolo in cerca and z in MENSAJE_ZONA:
                mensajes.append(MENSAJE_ZONA[z].format(a=activos.etiqueta(simbolo), p=r["prob"]))
            elif z == "compra" and antes is not None:          # Los demás: solo cuando llegan a COMPRAR
                nuevas_compras.append(f"{simbolo} ({r['prob']:.0f}%)")
        estado["zonas"][simbolo] = z
        if simbolo in cerca:
            for clave, texto in detectar_patrones(r["datos"], simbolo):
                if clave not in estado["enviados"]:
                    mensajes.append(texto)
                    estado["enviados"].append(clave)
    if nuevas_compras:
        mensajes.append("🟢 Nuevas señales de COMPRAR: " + ", ".join(nuevas_compras))
    for origen, simbolo, g, fecha in posiciones_abiertas():
        for nivel, condicion, texto in [
            ("stop", g <= -(estrategia.stop_de(simbolo) - CERCA),
             f"⚠️ {origen} · {simbolo}: va {g:+.1f}%, cerca del stop loss de -{estrategia.stop_de(simbolo):g}%."),
            ("objetivo", g >= estrategia.OBJETIVO - CERCA,
             f"🎯 {origen} · {simbolo}: va {g:+.1f}%, cerca del objetivo de +{estrategia.OBJETIVO}%.")]:
            clave = f"{origen}:{simbolo}:{fecha}:{nivel}"
            if condicion and clave not in estado["enviados"]:
                mensajes.append(texto)
                estado["enviados"].append(clave)
    for clave, texto in eventos_cercanos():
        if clave not in estado["enviados"]:
            mensajes.append(texto)
            estado["enviados"].append(clave)
    for m in mensajes:
        enviar(m)
    if telegram_listo():       # Si Telegram no está listo, no las marcamos como enviadas
        guardar_estado(estado)
        anotar(mensajes)
    return mensajes


def pesos(x):
    return f"${x:,.0f}".replace(",", ".")


def usd(x):
    return "—" if x is None or pd.isna(x) else f"US$ {x:,.2f}"


def _real_y_simulado():
    """Bloques REAL (Mis activos) y SIMULADO (simulador), siempre separados."""
    import mis_activos
    import simulador
    lineas = ["💼 REAL (Mis activos):"]
    mios = mis_activos.abiertas()
    if mios.empty:
        lineas.append("• No tienes compras registradas.")
    for _, p in mios.iterrows():
        g = "sin precio" if pd.isna(p["Ganancia_%"]) else f"{p['Ganancia_%']:+.1f}%"
        lineas.append(f"• {p['Activo']}: {p['Cantidad']:g} a {usd(p['Precio_compra'])} → {g}. {p['Sugerencia']}")
    lineas += ["", f"🧪 SIMULADO (modo {simulador.modo()}):"]
    for _, p in simulador.cartera.posiciones().iterrows():
        g = "sin precio" if pd.isna(p["Ganancia_%"]) else f"{p['Ganancia_%']:+.1f}%"
        lineas.append(f"• {p['Activo']}: {g}. {p['Sugerencia']}")
    s = simulador.resumen()
    lineas.append(f"• Disponible {pesos(s['disponible'])} · invertido {pesos(s['invertido'])} · total "
                  f"{pesos(s['total'])} ({s['ganancia_%']:+.1f}%) · meta del mes {pesos(s['meta'])}")
    return lineas


def _consejo(enviar_ordenes=False):
    """'Hoy compra estos' y 'Hoy vende estos'. Con COMPRAR CONFIRMADO manda la orden para Trii."""
    import consejo
    compra = consejo.comprar_hoy()
    lineas = ["🛒 HOY COMPRA ESTOS:"]
    if compra.empty:
        lineas.append("• Hoy no hay oportunidades.")
    for _, f in compra.iterrows():
        icono = "🟢" if f["Decision"] == "COMPRAR CONFIRMADO" else "🟡"
        lineas.append(f"{icono} {f['Activo']} ({f['Nombre']}): {f['Decision']} · precio {usd(f['Precio'])} · "
                      f"stop {usd(f['Stop'])} · objetivo {usd(f['Objetivo'])} · vender a más tardar el {f['Vender_el']:%d/%m}")
        if f["Dudas"]:
            lineas.append(f"   Duda: {f['Dudas'][0][:160]}")
        if enviar_ordenes and f["Decision"] == "COMPRAR CONFIRMADO":
            enviar(consejo.orden_trii(f))
    vende = consejo.vender_hoy()
    lineas += ["", "💰 HOY VENDE ESTOS:"]
    if vende.empty:
        lineas.append("• Nada para vender.")
    for _, f in vende.iterrows():
        lineas.append(f"• {f['Origen']} · {f['Activo']}: {f['Motivo']}")
    return lineas


def _simulador_automatico():
    """Corre el simulador de cada usuario en modo automático (el tuyo y el de los inversionistas que lo activaron).
    Telegram solo te avisa de TU simulador."""
    import nube
    if nube.conectado():
        import gestion
        if not gestion.automatico_global():          # El superadmin apagó el modo automático para todos
            print("Modo automático apagado para todos por el superadmin.")
            return
    correos = [nube.superadmin()]
    if nube.conectado():
        filas = nube.cliente().table("ajustes").select("email,valor").eq("clave", "simulador_config").execute().data
        correos += [f["email"] for f in filas if (f.get("valor") or {}).get("modo") == "automatico"]
    for correo in dict.fromkeys(correos):
        marca = nube.USUARIO.set(correo)
        try:
            _simulador_de_un_usuario(avisar=correo == nube.superadmin())
        except Exception as error:
            print(f"Simulador de {correo}: {error}")
        finally:
            nube.USUARIO.reset(marca)


def _simulador_de_un_usuario(avisar):
    import simulador
    for a in simulador.revisar():
        if avisar and a["Tipo"] in ("COMPRA", "VENTA") and not a.get("Error"):
            icono = "🛒" if a["Tipo"] == "COMPRA" else "💰"
            enviar(f"{icono} SIMULADO · {activos.etiqueta(a['Activo'])}: {a['Tipo']} a {usd(a['Precio'])} "
                   f"({pesos(a['Monto_COP'])}). {str(a.get('Motivo', ''))[:120]}"
                   + ("" if a["Abierto"] else " (mercado cerrado: precio del último cierre)"))


def alertas_dividendos():
    """Avisos 3 días antes de la fecha de corte y el día del pago (tus activos + la lista de dividendos)."""
    import dividendos
    import mis_activos
    tabla = dividendos.leer()
    if tabla.empty:
        return []
    mios = set(mis_activos.abiertas().get("Activo", [])) | set(activos.DIVIDENDOS)
    hoy = pd.Timestamp(calendario.hoy_colombia())
    salida = []
    for _, d in tabla[tabla["Activo"].isin(mios)].iterrows():
        if pd.notna(d["Proximo_corte"]) and 0 <= (d["Proximo_corte"] - hoy).days <= 3:
            estimada = " (fecha estimada)" if d["Corte_estimado"] else ""
            salida.append((f"div:{d['Activo']}:{d['Proximo_corte'].date()}:corte",
                           f"💵 {d['Activo']}: fecha de corte del dividendo el {d['Proximo_corte']:%d/%m}{estimada}. "
                           f"Para recibirlo debes tener la acción ANTES de ese día. Rendimiento {d['Rendimiento_%']:.1f}% anual."))
        if pd.notna(d["Proximo_pago"]) and d["Proximo_pago"].normalize() == hoy:
            salida.append((f"div:{d['Activo']}:{d['Proximo_pago'].date()}:pago",
                           f"💵 {d['Activo']}: HOY pagan el dividendo."))
    return salida


def dividendos_proximos(dias=14):
    import dividendos
    t = dividendos.leer()
    if t.empty:
        return ["• Sin datos de dividendos."]
    hoy = pd.Timestamp(calendario.hoy_colombia())
    t = t[t["Activo"].isin(activos.DIVIDENDOS) & (t["Proximo_corte"] <= hoy + pd.Timedelta(days=dias))]
    return [f"• {d['Activo']}: corte {d['Proximo_corte']:%d/%m} · {d['Rendimiento_%']:.1f}% anual · {d['Frecuencia']}"
            for _, d in t.sort_values("Proximo_corte").iterrows()] or [f"• Ninguno en los próximos {dias} días."]


def mensajes_noticias(horas=24):
    """'Noticias para ti' (top 5 con su impacto) y 'Titulares de medios' agrupados por medio."""
    import noticias
    top = noticias.para_mi(horas)
    lineas = ["📰 NOTICIAS PARA TI (tus activos reales y simulados y tus mercados):"]
    if top.empty:
        lineas.append("• Sin noticias relevantes.")
    for (_, n), frase in zip(top.iterrows(), noticias.impacto_con_claude(top) if len(top) else []):
        lineas += [f"• {n['Titular']} ({n['Fuente']})", f"  → {frase}", f"  {n['URL']}"]
    medios = noticias.titulares_por_medio(horas)
    titulares = ["🗞️ TITULARES DE MEDIOS:"]
    if not medios:
        titulares.append("• Sin titulares relevantes.")
    for medio, filas in medios.items():
        titulares.append(f"\n{medio} dice:")
        for _, n in filas.iterrows():
            titulares += [f"• {n['Titular']}", f"  {n['URL']}"]
    return "\n".join(lineas), "\n".join(titulares)


def noticias_graves(horas=3, maximo=3):
    """Noticias fuertes (OPEP, Fed, Trump, guerra, caída fuerte) de las últimas horas, aún no avisadas."""
    import noticias
    t = noticias.leer()
    t = t[t["Fecha"] >= pd.Timestamp.now() - pd.Timedelta(hours=horas)]
    simbolos = noticias.mis_simbolos()
    t = t[t["Titular"].map(noticias.es_grave) & t["Titular"].map(lambda x: noticias.relevancia(x, simbolos)[0] > 0)]
    estado = leer_estado()
    salida = []
    for _, n in t.sort_values("Fecha", ascending=False).drop_duplicates("Titular").iterrows():
        clave = f"grave:{str(n['Titular'])[:80]}"
        if clave in estado["enviados"]:
            continue
        salida.append((clave, f"🚨 NOTICIA FUERTE ({n['Fuente']}): {n['Titular']}\n→ {noticias.impacto_simple(n)}\n{n['URL']}"))
        if len(salida) >= maximo:
            break
    return salida


def vigilar():
    """Precio en vivo de cada posición abierta: avisa al momento si toca el stop loss o el objetivo.
    También busca noticias y avisa al momento las fuertes."""
    import mis_activos
    import noticias
    import simulador
    try:
        noticias.actualizar()
    except Exception as error:
        print(f"No pude actualizar noticias: {error}")
    estado = leer_estado()
    mensajes = []
    for clave, texto in noticias_graves() + eventos_en_una_hora():
        if clave not in estado["enviados"]:
            mensajes.append(texto)
            estado["enviados"].append(clave)
    for origen, pos in [("REAL", mis_activos.abiertas()), ("SIMULADO", simulador.cartera.posiciones())]:
        for _, p in pos.iterrows():
            try:
                precio = activos.precio_y_moneda(p["Activo"])[0]
            except Exception:
                continue
            nivel = "stop" if precio <= p["Stop"] else "objetivo" if precio >= p["Objetivo"] else None
            clave = f"toque:{origen}:{p['Activo']}:{p['Fecha_compra']}:{nivel}"
            if not nivel or clave in estado["enviados"]:
                continue
            texto = (f"{'🛑' if nivel == 'stop' else '🎯'} {origen} · {p['Activo']} tocó el "
                     f"{'STOP LOSS' if nivel == 'stop' else 'OBJETIVO'}: precio {usd(precio)} (compra a {usd(p['Precio_compra'])}).")
            if origen == "SIMULADO" and simulador.modo() == "automatico":
                simulador.vender(p["Activo"], origen="automático", nota=f"Tocó el {nivel}")
                texto += " El simulador vendió automáticamente."
            elif origen == "REAL":
                texto += " Si estás de acuerdo, véndelo en Trii y regístralo en Mis activos."
            mensajes.append(texto)
            estado["enviados"].append(clave)
    for m in mensajes:
        enviar(m)
    if telegram_listo():
        guardar_estado(estado)
        anotar(mensajes)
    return mensajes


def reporte(momento, tabla, resultados):
    """El mensaje de cada horario. Siempre separa REAL de SIMULADO."""
    import aciertos
    import analisis_claude
    import noticias
    titulos = {"manana": "☀️ Reporte del día (8:00 a.m.)", "apertura": "🔔 Qué comprar y vender hoy (9:45 a.m.)",
               "mediodia": "🕛 Revisión del mediodía (12:00 m.)", "cierre": "⏳ Última llamada antes del cierre (3:30 p.m.)",
               "noche": "🌙 Resumen del día (8:00 p.m.)"}
    lineas = [titulos[momento], ""]
    if momento == "manana":
        lineas.append("🏆 Top 5 (probabilidad de subida a 5 días):")
        for _, f in tabla.head(5).iterrows():
            r = resultados.get(f["Activo"])
            dec = analisis_claude.decision_unificada(r)[0] if r else f["Decision"]
            prob = "sin datos" if pd.isna(f["Probabilidad_%"]) else f"{f['Probabilidad_%']:.1f}%"
            lineas.append(f"{f['Puesto']}. {f['Activo']} ({f['Nombre']}): {prob} · {dec}")
        lineas += ["", "🧭 Sugerencia por mercado:"]
        for mercado, simbolo in activos.REFERENCIAS_MERCADO.items():
            r = resultados.get(simbolo)
            if r and mercado not in ("etf", "dividendos"):
                prob = "" if math.isnan(r["prob"]) else f" ({r['prob']:.0f}%)"
                lineas.append(f"• {activos.NOMBRE_MERCADO[mercado]}: {analisis_claude.decision_unificada(r)[0]}{prob}, "
                              f"tendencia {r['estado']}")
        lineas += ["", "💵 Dividendos próximos (14 días):"] + dividendos_proximos()
    if momento in ("apertura", "cierre"):
        lineas += _consejo(enviar_ordenes=momento == "apertura")
    if momento == "mediodia":
        vende = __import__("consejo").vender_hoy()
        lineas += ["🔎 ¿Algo tocó el stop o el objetivo?"] + (
            [f"• {f['Origen']} · {f['Activo']}: {f['Motivo']}" for _, f in vende.iterrows()] or ["• Nada por ahora."])
    if momento == "noche":
        r = aciertos.resumen()
        if r["app_n"]:
            lineas.append(f"🎯 Aciertos: app {r['app_%']:.0f}% ({r['app_n']}) · confirmados "
                          + (f"{r['unificada_%']:.0f}% ({r['unificada_n']})" if r["unificada_n"] else "sin datos aún"))
        tarde = pd.Timestamp.now().normalize() + pd.Timedelta(hours=16)
        noche = noticias.leer()
        noche = noche[(noche["Fecha"] >= tarde) & (noche["Grupo"] != "empresa")]
        lineas += ["", "📰 Noticias de la noche:"] + (
            [f"• [{n['Tipo']}] {n['Titular'][:110]} ({n['Fuente']})" for _, n in noche.head(8).iterrows()]
            or ["• Sin noticias nuevas desde las 4 p.m."])
    if momento == "noche":
        import automatico
        lineas += ["", automatico.resumen_diario()]
    lineas += [""] + _real_y_simulado() + ["", "Herramienta de análisis. No es una recomendación de inversión."]
    enviar("\n".join(lineas))
    if momento in ("manana", "noche"):
        for texto in mensajes_noticias(24 if momento == "manana" else 12):
            enviar(texto)


CRIPTO_FINDE = ["BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD", "BNB-USD", "DOGE-USD"]


def reporte_finde():
    """Sábado y domingo por la tarde: noticias, cripto (opera 24/7) y lo que podría mover el mercado el lunes."""
    import calendario
    import noticias
    try:
        noticias.actualizar()
        noticias.actualizar_medios()
    except Exception as error:
        print(f"No pude actualizar noticias: {error}")
    hoy = pd.Timestamp.now()
    lineas = [f"🗓️ RESUMEN DE FIN DE SEMANA ({'sábado' if hoy.weekday() == 5 else 'domingo'} {hoy:%d/%m})", "",
              "📰 Lo más importante de las últimas 24 horas:"]
    top = noticias.para_mi(horas=24, n=6)
    lineas += [f"• {n['Titular'][:120]} ({n['Fuente']})" for _, n in top.iterrows()] or ["• Sin noticias relevantes."]
    activos.actualizar_varios(CRIPTO_FINDE, periodo="1mo")
    lineas += ["", "🪙 Cripto (opera también el fin de semana):"]
    for simbolo in CRIPTO_FINDE:
        try:
            c = pd.read_csv(activos.ruta_precios(simbolo), usecols=["Cierre"])["Cierre"]
            lineas.append(f"• {activos.nombre(simbolo)}: {usd(c.iloc[-1])} · 24 h {(c.iloc[-1] / c.iloc[-2] - 1) * 100:+.1f}% "
                          f"· 7 días {(c.iloc[-1] / c.iloc[-8] - 1) * 100:+.1f}%")
        except Exception:
            continue
    lineas += ["", "📅 Lo que podría mover el mercado el lunes:"]
    eventos = calendario.proximos_eventos(dias=3)
    dias = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    lineas += [f"• {dias[pd.Timestamp(e['Fecha']).weekday()]} {pd.Timestamp(e['Fecha']):%d/%m} {e['Hora Colombia']}: "
               f"{e['Evento'][:110]}"
               for _, e in eventos.head(6).iterrows()] or ["• Sin eventos programados en el calendario."]
    t = noticias.leer()
    graves = t[(t["Fecha"] >= hoy - pd.Timedelta(hours=48)) & t["Titular"].map(noticias.es_grave)].drop_duplicates("Titular")
    if len(graves):
        lineas += ["", "⚠️ Noticias fuertes del fin de semana (pueden mover la apertura del lunes):"]
        lineas += [f"• {n['Titular'][:120]} ({n['Fuente']})" for _, n in graves.head(5).iterrows()]
    lineas += ["", "Herramienta de análisis. No es una recomendación de inversión."]
    enviar("\n".join(lineas))
    return lineas


# ---------- Programa principal ----------
def main():
    parser = argparse.ArgumentParser(description="Alertas por Telegram")
    parser.add_argument("--chat-id", action="store_true", help="Guardar tu número de chat en .env")
    parser.add_argument("--prueba", action="store_true", help="Mandar un mensaje de prueba")
    parser.add_argument("--momento", choices=["manana", "apertura", "mediodia", "cierre", "noche", "vigilar", "finde"])
    args = parser.parse_args()

    if args.chat_id:
        return obtener_chat_id()
    if args.prueba:
        ok = enviar("✅ Prueba: tu bot de análisis funciona. Recibirás mensajes de lunes a viernes a las 8:00, 9:45, "
                    "12:00, 3:30 y 8:00 p.m., la vigilancia cada 15 minutos, el resumen de fin de semana el sábado y el "
                    "domingo a las 4:00 p.m. y el backtest los domingos a las 6:00 p.m.")
        return print("Mensaje enviado. Revisa Telegram." if ok else "No se pudo enviar.")
    if args.momento == "vigilar":
        import nube
        if nube.conectado():                         # Salud: si una fuente se cae, avisa al Telegram de admin
            import gestion
            print("Fuentes caídas:", gestion.avisar_fuentes_caidas() or "ninguna")
        return print(f"Toques de stop/objetivo: {len(vigilar())}")
    if args.momento == "finde":
        return print("\n".join(reporte_finde()))

    import aciertos
    import noticias
    import ranking
    tabla = ranking.calcular(actualizar=True)        # Actualiza los precios de todos los activos
    noticias.actualizar()
    if args.momento == "manana":
        import dividendos
        dividendos.actualizar()
        import nube
        if nube.conectado():                         # Fin de eventos: borra a los 30 días (quedan estadísticas anónimas)
            import cursos
            for linea in cursos.limpieza():
                print(linea)
    resultados = {}
    for simbolo in tabla["Activo"]:
        try:
            resultados[simbolo] = estrategia.analizar(simbolo)
        except Exception as error:
            print(f"No pude analizar {simbolo}: {error}")
    aciertos.registrar(resultados)
    aciertos.evaluar()
    import predicciones
    import semanal
    semanal.actualizar()
    predicciones.evaluar()
    if args.momento == "manana":                   # Predicciones a 5 días para lo que sigues
        import mis_activos
        sigue = list(activos.REFERENCIAS.values()) + activos.SIMULAR + list(mis_activos.abiertas().get("Activo", []))
        predicciones.registrar(list(dict.fromkeys(sigue)))
    if args.momento in ("apertura", "mediodia", "cierre"):
        _simulador_automatico()
    if args.momento:
        reporte(args.momento, tabla, resultados)
    nuevas = revisar_alertas(resultados)
    estado = leer_estado()
    dividendos_nuevos = [(c, t) for c, t in alertas_dividendos() if c not in estado["enviados"]]
    for clave, texto in dividendos_nuevos:
        enviar(texto)
        estado["enviados"].append(clave)
        nuevas.append(texto)
    if telegram_listo():
        guardar_estado(estado)
        anotar([t for _, t in dividendos_nuevos])
    print(f"Alertas nuevas: {len(nuevas)}")
    for m in nuevas:
        print("  " + m)


if __name__ == "__main__":
    main()
