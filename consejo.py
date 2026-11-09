# consejo.py - "Hoy compra estos" y "Hoy vende estos" (mercado, Mis activos reales y simulador),
# y la orden lista para ejecutar a mano en Trii.

import json
import math

import pandas as pd

import activos
import analisis_claude
import estrategia
import mis_activos
import ranking
import simulador

CONFIG = activos.CARPETA / "mi_config.json"
FRACCION_REAL = 0.20       # La orden sugiere invertir el 20% de tu saldo real disponible


def saldo_real_usd():
    return json.loads(CONFIG.read_text()).get("saldo_real_usd", 0.0) if CONFIG.exists() else 0.0


def guardar_saldo_real_usd(monto):
    CONFIG.write_text(json.dumps({"saldo_real_usd": float(monto)}))


def _de_mercados(simbolo, mercados):
    return not mercados or bool(set(activos.mercados(simbolo)) & set(mercados))


def comprar_hoy(maximo=5, analizar=estrategia.analizar, mercados=None):
    """Activos con COMPRAR (solo de esos mercados, si se indican), con decisión unificada, precio, stop y objetivo."""
    tabla = ranking.leer()
    if tabla is None:
        return pd.DataFrame()
    filas = []
    candidatos = [s for s in tabla.loc[tabla["Decision"] == "COMPRAR", "Activo"] if _de_mercados(s, mercados)]
    for simbolo in candidatos[:maximo]:
        r = analizar(simbolo)
        decision, color, dudas = analisis_claude.decision_unificada(r)
        filas.append({"Activo": simbolo, "Nombre": activos.nombre(simbolo), "Decision": decision, "Color": color,
                      "Dudas": dudas, "Probabilidad_%": r["prob"], "Precio": r["precio"], "Stop": r["stop"],
                      "Objetivo": r["objetivo"], "Vender_el": r["fecha_venta"]})
    return pd.DataFrame(filas)


def vender_hoy(mercados=None):
    """Lo que conviene vender: tus activos reales y los del simulador con sugerencia 'Vender' (de esos mercados)."""
    filas = []
    for origen, pos in [("REAL", mis_activos.abiertas()), ("SIMULADO", simulador.cartera.posiciones())]:
        for _, p in pos.iterrows():
            if p.get("Sugerencia") == "Vender" and _de_mercados(p["Activo"], mercados):
                filas.append({"Origen": origen, "Activo": p["Activo"], "Nombre": p["Nombre"], "Cantidad": p["Cantidad"],
                              "Precio": p["Precio_actual"], "Stop": p["Stop"], "Objetivo": p["Objetivo"],
                              "Motivo": p["Motivo"]})
    return pd.DataFrame(filas)


def orden_trii(fila):
    """Texto de la orden para ejecutar a mano en Trii (solo para COMPRAR CONFIRMADO)."""
    monto = saldo_real_usd() * FRACCION_REAL
    if monto <= 0:
        cantidad_txt = "escribe tu saldo real en la app (Seguimiento → Mis activos) para sugerirte una cantidad"
    else:
        enteras = math.floor(monto / fila["Precio"])
        cantidad_txt = (f"{enteras} acciones (US$ {enteras * fila['Precio']:,.2f})" if enteras >= 1
                        else f"US$ {monto:,.2f} en fracción ({monto / fila['Precio']:.4f} acciones)")
    return (f"🧾 ORDEN PARA TRII · {fila['Activo']} ({fila['Nombre']})\n"
            f"• Tipo: COMPRA (ejecútala tú en Trii)\n• Cantidad sugerida: {cantidad_txt}\n"
            f"• Precio de referencia: US$ {fila['Precio']:,.2f}\n"
            f"• Stop loss: US$ {fila['Stop']:,.2f} (-{estrategia.STOP_LOSS}%)\n"
            f"• Objetivo: US$ {fila['Objetivo']:,.2f} (+{estrategia.OBJETIVO}%)\n"
            f"• Vender a más tardar: {fila['Vender_el']:%d/%m/%Y}\n"
            "Recuerda registrarla en Mis activos cuando la hagas.")
