# ranking.py - Probabilidad de subida de todos los activos, de mayor a menor
# Uso:  python ranking.py                 (actualiza los datos y muestra el top 20)
#       python ranking.py --sin-actualizar
# AVISO: herramienta de análisis. No es una recomendación de inversión.

import argparse
import json
import sys
from datetime import date

import pandas as pd

import activos
import estrategia

ARCHIVO = activos.CARPETA / "ranking.csv"
ORDEN_DECISION = {"COMPRAR": 0, "NO COMPRAR": 1, "ESPERAR": 2}


def fila_de(r):
    s = r["simbolo"]
    return {"Activo": s, "Nombre": activos.nombre(s), "Icono": activos.icono(s), "Tipo": activos.tipo_nombre(s), "Sector": activos.etiqueta_sector(s),
            "Moneda": activos.moneda(s),
            "Mercados": ";".join(activos.mercados(s)), "Fecha_datos": r["fecha"].date(),
            "Precio": round(r["precio"], 4), "Cambio_dia_%": round(r["cambio_dia_%"], 2),
            "Probabilidad_%": round(r["prob"], 1) if pd.notna(r["prob"]) else None,
            "Decision": r["decision"], "Casos": len(r["casos"]), "Episodios": r["episodios"],
            "Filtro": estrategia.texto_filtro(r["rango_rsi"], r["usar_mes"]), "Estado": r["estado"],
            "Ultimos_30": json.dumps([round(float(x), 4) for x in r["datos"]["Cierre"].tail(30)])}


def calcular(actualizar=True, simbolos=None):
    simbolos = simbolos or list(activos.ACTIVOS)
    if actualizar:
        fallidos = activos.actualizar_varios(simbolos)
        if fallidos:
            print(f"No pude actualizar: {', '.join(fallidos)}")
    filas = []
    for simbolo in simbolos:
        if simbolo in activos.SOLO_MIRAR:          # Activos solo para mirar: sin señales
            continue
        try:
            filas.append(fila_de(estrategia.analizar(simbolo)))
        except Exception as error:                      # Un activo con problemas no detiene el resto
            print(f"No pude analizar {simbolo}: {error}")
    tabla = pd.DataFrame(filas)
    tabla["_orden"] = tabla["Decision"].map(ORDEN_DECISION)
    tabla = tabla.sort_values(["_orden", "Probabilidad_%"], ascending=[True, False], na_position="last")
    tabla = tabla.drop(columns="_orden").reset_index(drop=True)
    tabla.insert(0, "Puesto", range(1, len(tabla) + 1))
    tabla.to_csv(ARCHIVO, index=False, encoding="utf-8-sig")
    return tabla


def leer():
    """El último ranking guardado (o None si nunca se ha calculado)."""
    if not ARCHIVO.exists():
        return None
    return pd.read_csv(ARCHIVO, encoding="utf-8-sig")


def texto_top(tabla, n=5):
    lineas = [f"🏆 Top {n} del día ({date.today():%d/%m/%Y}), probabilidad de subida a 5 días:"]
    for _, f in tabla.head(n).iterrows():
        prob = "sin datos" if pd.isna(f["Probabilidad_%"]) else f"{f['Probabilidad_%']:.1f}%"
        marca = " 🟢 COMPRAR" if f["Decision"] == "COMPRAR" else ""
        lineas.append(f"{f['Puesto']}. {f['Activo']} ({f['Nombre']}): {prob}{marca}")
    if not (tabla["Decision"] == "COMPRAR").any():
        lineas.append("Ningún activo llega a 56% hoy.")
    return "\n".join(lineas)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")   # Para mostrar emojis en cualquier consola
    parser = argparse.ArgumentParser(description="Ranking de probabilidad de subida")
    parser.add_argument("--sin-actualizar", action="store_true")
    tabla = calcular(actualizar=not parser.parse_args().sin_actualizar)
    columnas = ["Puesto", "Activo", "Nombre", "Precio", "Cambio_dia_%", "Probabilidad_%", "Decision", "Casos", "Filtro"]
    print(tabla[columnas].head(20).to_string(index=False))
    print(f"\n{(tabla['Decision'] == 'COMPRAR').sum()} de {len(tabla)} activos dicen COMPRAR. Guardado en {ARCHIVO.name}")
