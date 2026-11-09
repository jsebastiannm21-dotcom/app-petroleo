# estrategia.py - ¿Qué pasó en el pasado en días parecidos a hoy?
# Busca días del histórico con la misma situación que el último día y mira cuánto se movió
# el precio 5 días de mercado después. Con eso da una decisión:
#   COMPRAR     -> probabilidad de subida de 56% o más, con al menos 30 casos parecidos
#   NO COMPRAR  -> probabilidad menor a 56%, con al menos 30 casos
#   ESPERAR     -> ni aflojando los filtros se llega a 30 casos (datos insuficientes)
# Otros programas (simulador.py, alertas.py, la app) usan la función analizar().
# AVISO: esto es un ejercicio de análisis, no una recomendación de inversión.

import argparse
import zlib

from pathlib import Path

import numpy as np
import pandas as pd

import activos

# ---------- Reglas (puedes cambiarlas) ----------
DIAS_ADELANTE = 5        # Horizonte: 5 días de mercado
UMBRAL_COMPRA = 56       # COMPRAR solo si la probabilidad de subida es >= 56%
ALERTA_ALTA = 55         # Alerta si la probabilidad pasa de 55%
ALERTA_BAJA = 50         # Alerta si la probabilidad baja de 50%
MIN_CASOS = 30           # Mínimo de casos parecidos para decidir
STOP_LOSS = 3            # Vender si una compra pierde 3%
OBJETIVO = 6             # Vender si una compra gana 6%
COSTO = 0.005            # 0,5% de costo por operación (compra + venta)
STOPS_PERSONALES = Path(__file__).resolve().parent / "stops_personales.json"   # {símbolo: %} que eliges tú
MARGEN_A_FAVOR = 0.25    # La Time Machine solo dice "a favor" si gana más de 0,25% ya restado el costo
SIMULACIONES = 10_000    # Recorridos de la Time Machine
# Filtros, del más estricto al más flojo: (RSI ± puntos, ¿mismo mes?)
NIVELES_FILTRO = [(5, True), (5, False), (10, False), (15, False), (20, False)]


def cargar_datos(simbolo=activos.PRINCIPAL):
    """Junta precios e indicadores y calcula qué pasó en los 5 días siguientes a cada día."""
    activos.asegurar_datos(simbolo)
    precios = pd.read_csv(activos.ruta_precios(simbolo), index_col="Fecha", parse_dates=True)
    ind = pd.read_csv(activos.ruta_indicadores(simbolo), index_col="Fecha", parse_dates=True)
    datos = ind.join(precios[["Apertura", "Maximo", "Minimo"]]).dropna(subset=["MM50", "MM200", "RSI14"])
    if len(datos) < 2:
        raise ValueError(f"{simbolo}: hacen falta al menos 200 días de historia para la media de 200")
    datos["Tendencia"] = (datos["MM50"] > datos["MM200"]).map({True: "alcista", False: "bajista"})
    cierre, minimo = datos["Cierre"], datos["Minimo"]
    datos["Retorno_5d_%"] = (cierre.shift(-DIAS_ADELANTE) / cierre - 1) * 100
    minimo_sig = pd.concat([minimo.shift(-k) for k in range(1, DIAS_ADELANTE + 1)], axis=1).min(axis=1)
    datos["Perdida_max_%"] = (minimo_sig / cierre - 1) * 100
    datos.loc[datos.index[-DIAS_ADELANTE:], "Perdida_max_%"] = float("nan")  # Aún no hay 5 días
    return datos


def buscar_parecidos(datos, usar_mes=True, rango_rsi=5):
    hoy, fecha_hoy = datos.iloc[-1], datos.index[-1]
    historia = datos.dropna(subset=["Retorno_5d_%"])            # Solo días con 5 días de futuro
    filtro = (historia["Tendencia"] == hoy["Tendencia"]) & \
             (historia["RSI14"].between(hoy["RSI14"] - rango_rsi, hoy["RSI14"] + rango_rsi))
    if usar_mes:
        filtro &= historia.index.month == fecha_hoy.month
    return historia[filtro]


def buscar_adaptativo(datos):
    """Prueba los filtros del más estricto al más flojo hasta tener 30 casos."""
    for rango, mes in NIVELES_FILTRO:
        casos = buscar_parecidos(datos, usar_mes=mes, rango_rsi=rango)
        if len(casos) >= MIN_CASOS:
            return casos, rango, mes
    return casos, rango, mes                    # El más flojo, aunque no llegue a 30


def contar_episodios(casos):
    # Días seguidos casi siempre son "el mismo episodio"; contamos grupos separados por más de 7 días
    if casos.empty:
        return 0
    return int((casos.index.to_series().diff().dt.days.fillna(999) > 7).sum())


def probabilidad(casos):
    return (casos["Retorno_5d_%"] > 0).mean() * 100 if len(casos) else float("nan")


def escenarios(casos):
    """Parte los casos en 3 grupos iguales, de peor a mejor."""
    ordenados = casos.sort_values("Retorno_5d_%")
    n = len(ordenados)
    filas = []
    for i, nombre in enumerate(["Pesimista", "Base", "Optimista"]):
        grupo = ordenados.iloc[i * n // 3:(i + 1) * n // 3]
        filas.append({"Escenario": nombre,
                      "Retorno esperado %": grupo["Retorno_5d_%"].mean() if len(grupo) else None,
                      "Pérdida máxima %": grupo["Perdida_max_%"].min() if len(grupo) else None,
                      "Casos": len(grupo)})
    return pd.DataFrame(filas)


def barras(datos):
    """Cada día como [apertura, máximo, mínimo, cierre] relativos al cierre del día anterior."""
    previo = datos["Cierre"].shift(1)
    return np.column_stack([datos["Apertura"] / previo, datos["Maximo"] / previo,
                            datos["Minimo"] / previo, datos["Cierre"] / previo])


def time_machine(pool, n=SIMULACIONES, semilla=0, stop_loss=None, objetivo=None):
    """Simula n veces una compra de 5 días armando cada recorrido con días reales al azar del 'pool'.
    Vende con la primera de: stop loss, objetivo o fin del plazo. Devuelve probabilidades y resultados."""
    rng = np.random.default_rng(semilla)
    b = pool[rng.integers(0, len(pool), size=(n, DIAS_ADELANTE))]          # (n, días, 4)
    cierres = np.cumprod(b[:, :, 3], axis=1)                               # Precio relativo a la compra
    previo = np.hstack([np.ones((n, 1)), cierres[:, :-1]])
    apertura, maximo, minimo = b[:, :, 0] * previo, b[:, :, 1] * previo, b[:, :, 2] * previo
    stop, meta = 1 - (stop_loss or STOP_LOSS) / 100, 1 + (objetivo or OBJETIVO) / 100
    toca_stop, toca_meta = minimo <= stop, maximo >= meta
    hubo = (toca_stop | toca_meta).any(axis=1)
    dia = (toca_stop | toca_meta).argmax(axis=1)
    fila = np.arange(n)
    es_stop = toca_stop[fila, dia]                                         # Si toca los dos, gana el stop
    a = apertura[fila, dia]
    salida = np.where(hubo, np.where(es_stop, np.minimum(a, stop), np.maximum(a, meta)), cierres[:, -1])
    retorno = (salida * (1 - COSTO) - 1) * 100
    p_stop = (hubo & es_stop).mean() * 100
    p_objetivo = (hubo & ~es_stop).mean() * 100
    dias_salida = np.where(hubo, dia + 1, DIAS_ADELANTE)                  # Día (1 a 5) en que se vendió
    llego = hubo & ~es_stop
    caida = (np.minimum.accumulate(minimo, axis=1)[fila, dias_salida - 1] - 1) * 100   # Peor caída antes de vender
    grupos = {"Optimista": llego, "Base": ~hubo, "Pesimista": hubo & es_stop}
    escenarios_tm = {nombre: {"probabilidad": m.mean() * 100,
                              "retorno": retorno[m].mean() if m.any() else None,
                              "precio_factor": salida[m].mean() if m.any() else None,
                              "perdida_max": caida[m].min() if m.any() else None,
                              "dias": dias_salida[m].mean() if m.any() else None} for nombre, m in grupos.items()}
    return {"escenarios": escenarios_tm, "rango_5d": tuple(np.percentile(cierres[:, -1], [10, 50, 90])),
            "dia_venta": int(np.ceil(np.median(dias_salida))),
            "dia_objetivo": int(np.ceil(np.median(dias_salida[llego]))) if llego.any() else None,
            "p_objetivo": p_objetivo, "p_stop": p_stop, "p_plazo": 100 - p_objetivo - p_stop,
            "ganancia_esperada": retorno.mean(), "peor_caso": retorno.min(),
            "percentil_5": np.percentile(retorno, 5), "a_favor": bool(retorno.mean() > MARGEN_A_FAVOR), "simulaciones": n}


def pool_de_casos(datos, casos):
    """Los días reales que vinieron después de cada caso parecido (los 5 siguientes)."""
    pos = datos.index.get_indexer(casos.index)
    filas = (pos[:, None] + np.arange(1, DIAS_ADELANTE + 1)).ravel()
    filas = filas[filas < len(datos)]
    pool = barras(datos)[filas]
    return pool[~np.isnan(pool).any(axis=1)]


def estado_tendencia(hoy):
    """Alcista si precio > MM50 > MM200; bajista si precio < MM50 < MM200; si no, neutral."""
    if hoy["Cierre"] > hoy["MM50"] > hoy["MM200"]:
        return "alcista"
    if hoy["Cierre"] < hoy["MM50"] < hoy["MM200"]:
        return "bajista"
    return "neutral"


def stops_personales():
    import json

    import nube
    if nube.conectado():
        return nube.leer_ajuste("stops_personales", defecto={}) or {}
    return json.loads(STOPS_PERSONALES.read_text(encoding="utf-8")) if STOPS_PERSONALES.exists() else {}


def stop_de(simbolo):
    """Stop loss (%) para tus compras de este activo: el personal si lo pusiste; si no, la regla base de 3%."""
    return float(stops_personales().get(simbolo, STOP_LOSS))


def guardar_stop(simbolo, pct):
    """Guarda tu stop personal (None = volver a la regla base)."""
    import json
    t = stops_personales()
    if pct is None:
        t.pop(simbolo, None)
    else:
        t[simbolo] = round(float(pct), 2)
    import nube
    if nube.conectado():
        nube.guardar_ajuste("stops_personales", t)
    else:
        STOPS_PERSONALES.write_text(json.dumps(t), encoding="utf-8")


def texto_filtro(rango, mes):
    return f"RSI ±{rango}" + (" y mismo mes" if mes else ", cualquier mes")


def cayendo_bajo_mm200(datos):
    """Protección: precio por debajo de la media de 200 días Y más bajo que hace 5 días (sigue cayendo)."""
    hoy = datos.iloc[-1]
    return bool(hoy["Cierre"] < hoy["MM200"] and hoy["Cierre"] < datos["Cierre"].iloc[-1 - DIAS_ADELANTE])


def razon(r):
    """La razón de la decisión en una frase sencilla."""
    if r["decision"] == "SOLO MIRAR":
        return "Activo solo para mirar (precio y gráfica): la app no da señales de compra ni alertas para él."
    if r.get("cerrado"):
        return (f"Los casos parecidos dan {r['prob']:.0f}% y la Time Machine sale a favor, pero hoy el mercado está "
                "cerrado (fin de semana o festivo): no se sugiere comprar en días sin mercado.")
    if r.get("proteccion"):
        return (f"Los casos parecidos dan {r['prob']:.0f}% y la Time Machine sale a favor, pero el precio está por "
                "debajo de su media de 200 días y sigue cayendo: mejor esperar una señal de rebote (que deje de "
                "caer frente a hace 5 días).")
    if r["decision"] == "ESPERAR":
        return (f"Solo hay {len(r['casos'])} días parecidos en el historial (hacen falta {MIN_CASOS}), "
                "así que no hay datos suficientes para decidir.")
    subieron = int((r["casos"]["Retorno_5d_%"] > 0).sum())
    base = f"En {len(r['casos'])} días parecidos ({texto_filtro(r['rango_rsi'], r['usar_mes'])}), el precio subió " \
           f"5 días después en {subieron} ({r['prob']:.0f}%)"
    tm = r["tm"]
    if r["decision"] == "COMPRAR":
        return base + f", por encima del {UMBRAL_COMPRA}%; y la Time Machine da ganancia esperada de " \
                      f"{tm['ganancia_esperada']:+.2f}% (a favor)."
    if r["prob"] >= UMBRAL_COMPRA:
        return base + f", pero la Time Machine da ganancia esperada de {tm['ganancia_esperada']:+.2f}% " \
                      "(en contra), así que no conviene."
    return base + f", por debajo del {UMBRAL_COMPRA}% que exige la regla."


def _historia_corta(simbolo):
    """Activos con menos de 200 días de historia (recién salidos a bolsa): siempre ESPERAR."""
    ind = pd.read_csv(activos.ruta_indicadores(simbolo), index_col="Fecha", parse_dates=True)
    hoy, precio = ind.iloc[-1], float(ind["Cierre"].iloc[-1])
    vacio = pd.DataFrame(columns=["Cierre", "RSI14", "Retorno_5d_%", "Perdida_max_%"])
    return {"simbolo": simbolo, "datos": ind, "hoy": hoy, "fecha": ind.index[-1], "precio": precio,
            "casos": vacio, "episodios": 0, "prob": float("nan"), "suficiente": False,
            "rango_rsi": NIVELES_FILTRO[-1][0], "usar_mes": False, "escenarios": escenarios(vacio),
            "decision": "SOLO MIRAR" if simbolo in activos.SOLO_MIRAR else "ESPERAR", "tm": None,
            "proteccion": False, "cerrado": False, "fecha_venta": None,
            "comprar": False, "alerta": None, "estado": "neutral",
            "prediccion_5d": None,
            "stop": precio * (1 - STOP_LOSS / 100), "objetivo": precio * (1 + OBJETIVO / 100),
            "cambio_dia_%": (precio / float(ind["Cierre"].iloc[-2]) - 1) * 100 if len(ind) > 1 else 0.0,
            "razon": f"Tiene solo {len(ind)} días en bolsa; hacen falta al menos 200 para analizarlo."}


def analizar(simbolo=activos.PRINCIPAL):
    """Calcula todo para el último día del activo y lo devuelve en un diccionario."""
    try:
        datos = cargar_datos(simbolo)
    except ValueError:
        if activos.ruta_indicadores(simbolo).exists():
            return _historia_corta(simbolo)
        raise
    casos, rango, mes = buscar_adaptativo(datos)
    suficiente = len(casos) >= MIN_CASOS
    prob = probabilidad(casos) if suficiente else float("nan")
    pool = pool_de_casos(datos, casos) if suficiente else np.empty((0, 4))
    tm = time_machine(pool, semilla=zlib.crc32(simbolo.encode())) if len(pool) else None
    if not suficiente or tm is None:
        decision = "ESPERAR"
    elif prob >= UMBRAL_COMPRA and tm["a_favor"]:
        decision = "COMPRAR"
    else:
        decision = "NO COMPRAR"
    proteccion = decision == "COMPRAR" and cayendo_bajo_mm200(datos)
    if proteccion:
        decision = "ESPERAR"
    import calendario
    cerrado = decision == "COMPRAR" and calendario.mercado_cerrado(calendario.hoy_colombia(), simbolo)
    if cerrado:
        decision = "ESPERAR"
    if simbolo in activos.SOLO_MIRAR:
        decision, suficiente, prob = "SOLO MIRAR", False, float("nan")
    if suficiente and prob > ALERTA_ALTA:
        alerta = "alta"
    elif suficiente and prob < ALERTA_BAJA:
        alerta = "baja"
    else:
        alerta = None
    hoy = datos.iloc[-1]
    esc = escenarios(casos) if suficiente else escenarios(casos.iloc[0:0])
    base = esc.loc[esc["Escenario"] == "Base", "Retorno esperado %"].iloc[0]
    precio = float(hoy["Cierre"])
    r = {
        "simbolo": simbolo, "datos": datos, "hoy": hoy, "fecha": datos.index[-1], "precio": precio,
        "casos": casos, "episodios": contar_episodios(casos), "prob": prob, "suficiente": suficiente,
        "rango_rsi": rango, "usar_mes": mes, "escenarios": esc, "decision": decision, "tm": tm,
        "proteccion": proteccion, "cerrado": cerrado,
        "fecha_venta": (datos.index[-1] + pd.offsets.BDay(tm["dia_venta"])).date() if tm else None,
        "comprar": decision == "COMPRAR", "alerta": alerta, "estado": estado_tendencia(hoy),
        "prediccion_5d": precio * (1 + base / 100) if base is not None and pd.notna(base) else None,
        "stop": precio * (1 - STOP_LOSS / 100), "objetivo": precio * (1 + OBJETIVO / 100),
        "cambio_dia_%": (precio / float(datos["Cierre"].iloc[-2]) - 1) * 100,
    }
    r["razon"] = razon(r)
    return r


def main():
    parser = argparse.ArgumentParser(description="Señal de la estrategia para un activo")
    parser.add_argument("--activo", default=activos.PRINCIPAL)
    simbolo = activos.limpiar(parser.parse_args().activo)
    r = analizar(simbolo)
    hoy, casos = r["hoy"], r["casos"]
    print("=" * 64)
    print(f"{activos.etiqueta(simbolo)} - {r['fecha'].date()}")
    print(f"  Precio: {r['precio']:,.2f}   MM50: {hoy['MM50']:,.2f}   MM200: {hoy['MM200']:,.2f}   "
          f"RSI: {hoy['RSI14']:.1f}   Estado: {r['estado']}")
    print(f"  Filtro usado: {texto_filtro(r['rango_rsi'], r['usar_mes'])} -> {len(casos)} casos "
          f"en {r['episodios']} episodios")
    print("=" * 64)
    print(f"DECISIÓN: {r['decision']}" + ("" if r["suficiente"] else ": datos insuficientes"))
    print(f"  {r['razon']}")
    if r["suficiente"]:
        print(f"\nPrecio de compra {r['precio']:,.2f} | stop loss {r['stop']:,.2f} (-{STOP_LOSS}%) | "
              f"objetivo {r['objetivo']:,.2f} (+{OBJETIVO}%)")
        print(f"Predicción a 5 días (escenario base): {r['prediccion_5d']:,.2f}")
        tm = r["tm"]
        print(f"Time Machine ({tm['simulaciones']:,} simulaciones): objetivo {tm['p_objetivo']:.1f}% · "
              f"stop {tm['p_stop']:.1f}% · plazo {tm['p_plazo']:.1f}% | ganancia esperada "
              f"{tm['ganancia_esperada']:+.2f}% | peor caso {tm['peor_caso']:+.2f}% -> "
              f"{'A FAVOR' if tm['a_favor'] else 'EN CONTRA'}")
        print("\nESCENARIOS (cada uno es un tercio de los casos, de peor a mejor):")
        print(r["escenarios"].round(2).to_string(index=False))
        casos.round(2).to_csv("casos_parecidos.csv")
    print("\nRecuerda: el pasado no garantiza el futuro. No es una recomendación de inversión.")


if __name__ == "__main__":
    main()
