# backtest_semanal.py - Backtest automático de cada domingo, con resultado por Telegram.
# - Por mercado: cómo le fue a la estrategia la última semana y el último mes vs. comprar y mantener.
# - 3 semanas malas seguidas -> alerta.
# - 4 semanas malas, o el último mes peor que comprar y mantener -> SUGIERE un ajuste de regla probado en el año
#   guardado (el último año). NUNCA cambia las reglas solo: tú decides, y como máximo una sugerencia al mes.
# Uso:  python backtest_semanal.py             (lo corre la tarea programada del domingo)
#       python backtest_semanal.py --sin-enviar

import argparse
import itertools
import json
import sys
from datetime import datetime

import numpy as np
import pandas as pd

import activos
import backtest
import estrategia

ARCHIVO = activos.CARPETA / "backtest_semanal.csv"
ESTADO = activos.CARPETA / "backtest_semanal_estado.json"
MERCADOS = [m for m in activos.REFERENCIAS_MERCADO if m not in ("etf", "dividendos")]
# Variantes: umbral de compra y pares (stop loss, objetivo) manteniendo el objetivo en el doble del stop
UMBRALES = [54, 56, 58, 60]
NIVELES = [(3, 6), (4, 8), (5, 10)]


def medir(simbolo, dias_historia=150):
    """Rendimiento de la estrategia y de comprar y mantener en la última semana (5 días) y el último mes (21)."""
    bt = backtest.Backtest(simbolo)
    n = len(bt.fechas)
    curva, ops = bt.simular(max(0, n - dias_historia), n)
    curva = curva.reindex(bt.fechas[max(0, n - dias_historia):]).ffill()
    c = pd.Series(bt.cierre, index=bt.fechas)
    cambio = lambda s, d: (s.iloc[-1] / s.iloc[-1 - d] - 1) * 100
    recientes = ops[pd.to_datetime(ops["Venta"]) >= bt.fechas[-21]] if len(ops) else ops
    return {"Estrategia_sem_%": cambio(curva, 5), "CyM_sem_%": cambio(c, 5),
            "Estrategia_mes_%": cambio(curva, 21), "CyM_mes_%": cambio(c, 21),
            "Operaciones_mes": len(recientes),
            "Aciertos_mes_%": (recientes["Resultado_neto_%"] > 0).mean() * 100 if len(recientes) else None}


def semanas_malas_seguidas(historial):
    """Cuántas semanas seguidas (las más recientes) la estrategia rindió menos que comprar y mantener."""
    por_semana = historial.groupby("Fecha").apply(lambda g: (g["Estrategia_sem_%"] < g["CyM_sem_%"]).mean() > 0.5)
    seguidas = 0
    for mala in reversed(por_semana.sort_index().tolist()):
        if not mala:
            break
        seguidas += 1
    return seguidas


def probar_ajustes(simbolos):
    """Prueba variantes de la regla en el año guardado (último año) y devuelve la mejor frente a la actual."""
    resultados = []
    for umbral, (stop, objetivo) in itertools.product(UMBRALES, NIVELES):
        total = []
        for s in simbolos:
            bt = backtest.Backtest(s, umbral=umbral, stop=stop / 100, objetivo=objetivo / 100)
            curva, _ = bt.simular(bt.corte, len(bt.fechas))
            total.append((curva.iloc[-1] / backtest.CAPITAL - 1) * 100)
        resultados.append({"umbral": umbral, "stop": stop, "objetivo": objetivo, "resultado_%": float(np.mean(total))})
    t = pd.DataFrame(resultados).sort_values("resultado_%", ascending=False)
    actual = t[(t["umbral"] == estrategia.UMBRAL_COMPRA) & (t["stop"] == estrategia.STOP_LOSS) &
               (t["objetivo"] == estrategia.OBJETIVO)].iloc[0]
    return t.iloc[0], actual


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Backtest semanal")
    parser.add_argument("--sin-enviar", action="store_true")
    args = parser.parse_args()
    import alertas
    enviar = print if args.sin_enviar else alertas.enviar

    hoy = datetime.now().strftime("%Y-%m-%d")
    filas = []
    for m in MERCADOS:
        s = activos.REFERENCIAS_MERCADO[m]
        try:
            filas.append({"Fecha": hoy, "Mercado": activos.NOMBRE_MERCADO[m], "Activo": s, **medir(s)})
        except Exception as error:
            print(f"No pude medir {s}: {error}")
    nuevas = pd.DataFrame(filas)
    historial = pd.read_csv(ARCHIVO) if ARCHIVO.exists() else pd.DataFrame()
    historial = pd.concat([historial[historial.get("Fecha", pd.Series(dtype=str)) != hoy] if len(historial) else historial,
                           nuevas], ignore_index=True)
    if not args.sin_enviar:                       # En modo prueba no se guarda nada
        historial.to_csv(ARCHIVO, index=False, encoding="utf-8-sig")

    lineas = ["📊 BACKTEST SEMANAL (estrategia vs. comprar y mantener)", ""]
    for _, f in nuevas.iterrows():
        icono = "✅" if f["Estrategia_sem_%"] >= f["CyM_sem_%"] else "❌"
        aciertos = "sin operaciones" if pd.isna(f["Aciertos_mes_%"]) else f"aciertos del mes {f['Aciertos_mes_%']:.0f}%"
        lineas.append(f"{icono} {f['Mercado']} ({f['Activo']}): semana {f['Estrategia_sem_%']:+.1f}% vs "
                      f"{f['CyM_sem_%']:+.1f}% · mes {f['Estrategia_mes_%']:+.1f}% vs {f['CyM_mes_%']:+.1f}% · {aciertos}")
    malas = semanas_malas_seguidas(historial)
    mes_peor = nuevas["Estrategia_mes_%"].mean() < nuevas["CyM_mes_%"].mean()
    lineas += ["", f"Semanas malas seguidas: {malas}. Último mes: estrategia {nuevas['Estrategia_mes_%'].mean():+.1f}% "
               f"vs comprar y mantener {nuevas['CyM_mes_%'].mean():+.1f}%."]
    enviar("\n".join(lineas))

    if malas >= 3:
        enviar(f"⚠️ ALERTA: la estrategia lleva {malas} semanas seguidas rindiendo menos que comprar y mantener.")
    estado = json.loads(ESTADO.read_text()) if ESTADO.exists() else {}
    ultima = estado.get("ultima_sugerencia")
    puede = not ultima or (datetime.now() - datetime.fromisoformat(ultima)).days >= 30     # Máximo una al mes
    if (malas >= 4 or mes_peor) and puede and not args.sin_enviar:
        print("Probando ajustes de la regla en el año guardado (tarda unos minutos)...")
        mejor, actual = probar_ajustes([activos.REFERENCIAS_MERCADO[m] for m in MERCADOS])
        if mejor["resultado_%"] > actual["resultado_%"]:
            enviar(f"🔧 SUGERENCIA DE AJUSTE (tú decides; la app no cambia nada sola):\n"
                   f"En el año guardado, la regla actual (umbral {estrategia.UMBRAL_COMPRA}%, stop "
                   f"{estrategia.STOP_LOSS}%, objetivo {estrategia.OBJETIVO}%) dio {actual['resultado_%']:+.1f}% en "
                   f"promedio. La mejor variante (umbral {mejor['umbral']}%, stop {mejor['stop']}%, objetivo "
                   f"{mejor['objetivo']}%) dio {mejor['resultado_%']:+.1f}%.\nOjo: que haya funcionado en el pasado no "
                   "garantiza que funcione después. Si quieres cambiarla, pídemelo (máximo un cambio al mes).")
        else:
            enviar("🔧 Probé otras variantes de la regla en el año guardado y ninguna fue mejor que la actual.")
        estado["ultima_sugerencia"] = datetime.now().isoformat(timespec="minutes")
        ESTADO.write_text(json.dumps(estado))
    print("\n".join(lineas))


if __name__ == "__main__":
    if "--prueba" in sys.argv:                    # Prueba del conteo de semanas malas
        h = pd.DataFrame({"Fecha": ["1", "2", "3", "4"], "Estrategia_sem_%": [1, -1, -2, -3], "CyM_sem_%": [0, 0, 0, 0]})
        assert semanas_malas_seguidas(h) == 3
        assert semanas_malas_seguidas(h.iloc[:1]) == 0
        print("Semanas malas: pruebas OK")
    else:
        main()
