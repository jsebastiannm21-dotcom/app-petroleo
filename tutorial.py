# tutorial.py - Explicación sencilla, con un ejemplo, de cada análisis de la app.
# La usan la página "Aprende" y los botones "¿Qué es esto?" de cada sección.

TUTORIAL = {
    "atr": ("Volatilidad (ATR)",
            "El **ATR** (rango verdadero promedio) mide cuánto se mueve el precio en un día normal, mirando las últimas "
            "2 semanas. Es como saber qué tan «nervioso» es un activo.",
            "Si Bitcoin tiene un ATR de 2,9%, en un día normal sube o baja unos 2,9%. Con un stop loss de 3% te sacaría "
            "casi cualquier día por puro ruido. Por eso la app sugiere un stop de 2 × ATR = 5,8%. Si usas un stop más "
            "amplio, compra menos cantidad para arriesgar la misma plata."),
    "sr": ("Soportes y resistencias",
           "Un **soporte** es un precio donde antes el activo dejó de caer y rebotó, como un piso. Una **resistencia** "
           "es un precio donde antes dejó de subir, como un techo. Cuantas más veces lo tocó, más fuerte es.",
           "Si Linde rebotó 3 veces en US$ 490, ese es un soporte. Si hoy vale 515, hay un «colchón» hasta 490. Si lo "
           "rompe hacia abajo, suele seguir cayendo, y ese piso se vuelve techo."),
    "corr": ("Correlación",
             "La **correlación** (de -1 a 1) dice qué tanto se mueven juntos dos activos. Cerca de 1: suben y bajan casi "
             "igual. Cerca de 0: no tienen que ver. Negativa: cuando uno sube, el otro baja.",
             "Exxon y Chevron tienen 0,88: son dos petroleras que se mueven casi igual. Tener las dos es casi como tener "
             "el doble de una sola: si el petróleo cae, caen ambas. Bitcoin y Exxon tienen -0,2: no tienen que ver, "
             "así que juntos reparten mejor el riesgo."),
    "sent": ("Sentimiento de noticias",
             "La app lee los titulares de la semana y marca cada uno como 😊 positivo (habla de subidas, ganancias, "
             "récords), 😞 negativo (caídas, pérdidas, crisis) o 😐 neutro. El balance dice qué pesa más.",
             "Si de 10 titulares sobre el petróleo, 6 hablan de recortes de la OPEP y caídas y 2 de subidas, el balance "
             "es 😞 negativo. Es una pista extra, no cambia la decisión: cuenta palabras y no entiende ironías."),
    "var": ("Valor en riesgo (VaR)",
            "El **VaR al 95%** es la pérdida de un día malo: la que solo se supera 1 de cada 20 días. Se calcula "
            "aplicándole a tu portafolio de hoy los movimientos reales de cada día de los últimos 2 años.",
            "Si tu portafolio vale US$ 100 y el VaR es US$ 2, en 19 de cada 20 días perderías menos de US$ 2. Pero el "
            "día 20 puede ser peor, por ejemplo en una crisis."),
    "montecarlo": ("Monte Carlo y sus bandas",
                   "El **Monte Carlo** dibuja miles de caminos posibles del precio, armados con movimientos reales del "
                   "pasado elegidos al azar. Las **bandas** resumen esos caminos: la línea del medio es el camino típico "
                   "(mediana), y las del 10% y el 90% son los extremos poco probables.",
                   "Si hoy vale 100 y en 20 días la banda del 10% está en 92 y la del 90% en 109, en 8 de cada 10 "
                   "caminos el precio terminó entre 92 y 109. Solo 1 de cada 10 terminó por debajo de 92."),
    "prophet": ("Prophet (pronóstico)",
                "**Prophet** es un programa de Meta que separa el precio en dos partes: la **tendencia** (hacia dónde va "
                "en los últimos meses) y la **estacionalidad** (lo que suele pasar en ciertas épocas del año o días de "
                "la semana). Luego las proyecta hacia adelante.",
                "Si el café viene subiendo y además suele subir en noviembre, Prophet sumará las dos cosas y pronosticará "
                "una subida. Falla cuando pasa algo nuevo, como una helada en Brasil o una guerra."),
    "time_machine": ("Time Machine",
                     "La **Time Machine** repite 10.000 veces la compra de hoy usando lo que pasó de verdad después de "
                     "los días parecidos a hoy, aplicando el stop loss (-3%) y el objetivo (+6%). Así se ve cuánto se "
                     "ganaría o perdería en promedio, ya restada la comisión.",
                     "Si en 10.000 repeticiones 3.000 llegan al objetivo (+6%), 4.000 tocan el stop (-3%) y el resto vende "
                     "a los 5 días, la ganancia esperada puede salir en -0,4%: **en contra**, aunque la probabilidad de "
                     "subir sea alta, porque las caídas fueron más grandes que las subidas. Solo dice «a favor» si pasa "
                     "de +0,25%."),
}
