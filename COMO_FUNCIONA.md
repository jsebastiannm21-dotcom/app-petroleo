# Cómo funciona la app

La app analiza unos **1.180 activos**:
- **Estados Unidos:** las 500 del S&P 500 y el Nasdaq 100.
- **Europa:** Euro Stoxx 50, FTSE 100 y DAX 40.
- **Asia:** las más grandes de Japón, Hong Kong, Corea, Taiwán e India.
- **Sectores:** 50 de petróleo y gas, 30 mineras de oro, plata y cobre.
- **Materias primas:** energía, metales, agrícolas y ganado.
- **Latinoamérica (sin Colombia):** Brasil, México, Chile, Perú y Argentina.
- **Divisas:** dólar/peso colombiano, euro/dólar, dólar/peso mexicano, dólar/real, dólar/yen y más.
- **Otros:** 50 criptomonedas, bonos, Colombia, fondos y dividendos.

Mira qué pasó en el pasado en días parecidos a hoy, le pide una segunda opinión a Claude y te da una
sugerencia. El conteo exacto está en la barra izquierda, en «¿Cuántos activos hay?».

> **Importante:** es una herramienta de análisis. **No es una recomendación de inversión.** En las pruebas con
> datos del pasado (backtest), la estrategia **no le ganó a comprar y mantener** en el último año. Úsala para
> aprender y para tener una segunda mirada, no como única razón para invertir.

---

## Tus datos están protegidos
- **`python respaldo.py`** copia todos tus registros a `respaldo\<fecha y hora>`: Mis activos, simulador,
  historial de alertas, cierres semanales, eventos y configuración. No copia `.env`, porque tiene tus claves.
- **Reiniciar el simulador** desde la app crea un respaldo antes de borrar.
- **Para recuperar algo:** copia el archivo desde la carpeta de respaldo a la carpeta de la app.

## Inicio en carrusel
Arriba del Inicio hay **flechas ◀ ▶** (o los nombres) para pasar entre seis paneles: **Estados Unidos, Europa,
Asia, Colombia, Materias primas y Cripto**. Cada panel trae dos cosas:
- **La tendencia del mercado** y **4 gráficas**, con precio, cambio del día, estado y decisión.
- **"Hoy compra estos" y "Hoy vende estos" solo de ese mercado.**

## La lista de activos (actualizar_listas.py)
`python actualizar_listas.py` arma la lista y la guarda en `catalogo_ampliado.json`:
1. Baja de Wikipedia las listas del S&P 500, Euro Stoxx 50, FTSE 100, DAX 40, Hang Seng, Nifty 50 y los
   aristócratas del dividendo.
2. Les suma listas hechas a mano con las más grandes de Japón, Corea y Taiwán, petróleo y gas, mineras,
   materias primas, cripto, bonos y fondos de dividendos.
3. **Verifica cada símbolo en Yahoo Finance** y descarta los que no tienen al menos 30 días de precios recientes.
4. De Hong Kong deja las 40 más grandes. De petróleo y gas deja 50 en total.

Las listas cambian con el tiempo: córrelo cada pocos meses. Tarda unos 2 minutos.

**Descartados porque no tienen datos en Yahoo:**
- Toncoin y Celestia (cripto);
- Hess, comprada por Chevron;
- Kenvue y New Gold;
- el ETF de TES de Colombia;
- una empresa recién salida a bolsa (VYLR).

**Sin monedas estables:** USDT, USDC y similares no se incluyen, porque siempre valen 1 dólar.

**Rapidez:** cada pestaña carga solo cuando la abres, y los cálculos se guardan en memoria. El ranking de
todos los activos tarda poco más de un minuto, y la descarga de precios unos 2 minutos.

## Barra izquierda
- **Filtro por mercado, encima del selector de activo:** si marcas uno, el selector solo muestra sus activos.
  Si no marcas ninguno, salen todos.
- **«¿Cuántos activos hay?»:** el conteo por tipo (acciones, ETFs, futuros, cripto, índices) y por mercado.

## Explicación de cada decisión (para estudiantes)
Toca **Comprar, No comprar o Esperar** en cualquier lista (o el botón «¿Por qué esta decisión?») y se abre una
ventana con los pasos. Por ejemplo: "Se encontraron 76 días parecidos a hoy. En 58 el precio subió en 5 días
(76%). Supera la regla del 56%. La Time Machine dio +0,9% a favor. Por eso: COMPRAR".
- **Las palabras subrayadas** se explican al pasar el mouse.
- **En Mis activos y en el simulador,** tocar **Mantener** o **Vender** explica por qué.

## Casos parecidos con clic
En la tabla de casos parecidos:
- **Toca la fecha** para ver las noticias de esos días.
- **Toca una columna** para ver su gráfica:
  - el cierre de esas semanas,
  - el RSI de ese mes,
  - los 5 días siguientes,
  - la peor caída, con el punto más bajo marcado.

## Mercados
En **Seguimiento** hay una pestaña por mercado: **Estados Unidos, Nasdaq, Petróleo, Oro, Materias primas,
Colombia, Europa, Asia, Cripto, Futuros, ETFs y Bonos**, además de Bolsas, Dividendos, Semanal y Mis activos. Arriba de cada mercado aparecen tres cosas:
- **Consejo de tendencia:**
  - "Este mercado está **AL ALZA**": el precio está sobre sus medias de 50 y 200 días y subió en el último mes.
  - "**A LA BAJA**": todo lo contrario.
  - "**LATERAL**": las señales están mezcladas.

  Viene con la razón en una frase.
- **Estacionalidad y calendario** de ese mercado, en un desplegable: el retorno promedio de cada mes, el % de
  años en que subió y los próximos eventos que lo mueven.
- **Una nota** para los mercados especiales.

### Estados Unidos y Europa
- **Estados Unidos:** S&P 500, Dow Jones, Russell 2000, Nasdaq Composite y Nasdaq 100. Los índices no se
  compran directamente, sino con sus ETF (SPY o QQQ).
- **Estados Unidos (acciones):** las 500 empresas del S&P 500, con su sector.
- **Europa:** los índices FTSE 100 (Londres), DAX (Frankfurt), CAC 40 (París) y Euro Stoxx 50, y todas sus
  empresas. También están las bolsas de Ámsterdam, Milán, Madrid, Bruselas y Helsinki.
  - **Horario:** abren de madrugada en hora de Bogotá.
  - **Peniques:** las acciones de Londres cotizan en peniques (100 = 1 libra), y la app lo tiene en cuenta al
    pasar a dólares.

### Bolsas del mundo
Pestaña **Bolsas**: cada bolsa con su índice, el último valor, el cambio del día, su **horario en hora de
Bogotá**, si está **abierta ahora** y sus acciones grandes. El MSCI COLCAP no tiene datos en Yahoo, así que
Colombia usa el ETF que lo copia (ICOLCAP).

### Materias primas
Petróleo WTI y Brent, gas natural, oro, plata, cobre y **café**. El café también aparece en Colombia. El carbón,
el níquel y las flores no tienen datos diarios gratuitos en Yahoo, así que no se incluyeron.

### Colombia
Las acciones más líquidas de la Bolsa de Colombia: Ecopetrol, Grupo Cibest (antes Bancolombia), Grupo Aval,
Davivienda, Banco de Bogotá, Corficolombiana, Grupo Sura, ISA, Celsia, GEB, Promigas, Grupo Argos, Cementos
Argos, Mineros, Terpel, Canacol, Nutresa, Enka, la BVC y el ETF iShares COLCAP. También sus ADR en Nueva York:
**CIB, AVAL y EC**.
- **Precios:** en **pesos** y su equivalente en **dólares**.
- **Noticias y eventos:** noticias de Colombia, decisiones del **Banco de la República** (estimadas), la
  **inflación del DANE** (estimada) y los **festivos**.
- **Dónde comprar:** en **Trii**.

### Asia
- **Índices:** Nikkei (Japón), KOSPI (Corea), Taiex (Taiwán), Hang Seng (Hong Kong), Shanghái (China) y Nifty
  (India).
- **Empresas:** Toyota, Sony, Samsung, Hyundai, TSMC, Alibaba, Tencent, BYD, Reliance, Infosys y HDFC.
- **ETFs:** EWJ, EWY, FXI e INDA.

Para cada uno se muestra el **horario de su bolsa en hora de Bogotá** (abren de noche) y **dónde se puede
comprar**:
- Los ADR y ETF de Nueva York, en eToro, o en Trii si los tiene en su lista internacional.
- Las acciones locales, en eToro (algunas) o solo para mirar.
- Los índices, solo para mirar.

### Cripto
Bitcoin, Ethereum, XRP, BNB, Solana, Dogecoin, Cardano, Tron y Chainlink.
- **Horario:** operan **24/7**, así que nunca cuentan como "mercado cerrado".
- **Señales:** tienen las mismas que las acciones. Bitcoin dejó de ser "solo mirar".
- **Calendario:** el vencimiento mensual de opciones (último viernes) y los datos de EE.UU. que las mueven
  (Fed, inflación, empleo).
- **Dónde comprar:** en eToro; no están en Trii.

### Bonos (pestaña nueva)
**Un bono es un préstamo:** le prestas plata al gobierno o a una empresa, te devuelve lo prestado en una fecha
fija y mientras tanto te paga intereses. La **tasa** es ese interés.

**Regla de oro: cuando las tasas suben, el precio de los bonos que ya existen baja.** Si hoy salen bonos nuevos
que pagan 5%, nadie paga lo mismo por tu bono viejo que paga 3%. Los bonos largos (20 a 30 años) se mueven más.

La pestaña muestra:
- **Las tasas del Tesoro de EE.UU.** a 3 meses, 5, 10 y 30 años (^IRX, ^FVX, ^TNX, ^TYX), con su cambio del mes.
- **Una gráfica de la regla de oro:** la tasa a 10 años contra el ETF de bonos largos TLT. Se mueven al revés.
- **Los ETFs de bonos:**
  - **TLT, IEF y SHY:** Tesoro de EE.UU., de largo a corto plazo.
  - **AGG y BND:** bonos de EE.UU. en general.
  - **LQD:** empresas grandes.
  - **HYG:** alto rendimiento, más riesgoso.
  - **TIP:** protegidos contra la inflación.
  - **EMB:** países emergentes, incluye Colombia.

**TES de Colombia:** Yahoo Finance no tiene datos diarios gratuitos de los TES ni de un ETF de TES, así que no
están. EMB es lo más cercano.

### Futuros
WTI, Brent, gasolina, diésel, gas natural, oro, plata, cobre, platino, paladio, aluminio, café, cacao, azúcar,
maíz, trigo, soya (y su aceite y harina), algodón, avena, arroz, jugo de naranja, ganado y cerdo, además de
Nasdaq 100, S&P 500 y Dow Jones, con su descripción y su horario
(domingo 6 p.m. a viernes 5 p.m. en Bogotá, con una pausa diaria). **Son para expertos y no se compran en
Trii.**

### Dividendos
Solo aparecen los activos que **de verdad pagaron dividendos** en los últimos 12 meses (unos 860, revisados en
Yahoo Finance). Cripto, futuros e índices no aparecen. El mercado «Dividendos» es una lista especial con:
- los aristócratas del dividendo del S&P 500, que llevan más de 25 años subiendo su dividendo;
- los fondos SCHD, VYM, VIG, DVY, HDV, SDY y NOBL;
- KO, JNJ, PG y Ecopetrol.

Las colombianas que pagan (Ecopetrol, Grupo Cibest, ISA, Grupo Argos, Celsia y otras) aparecen con el filtro
**Colombia**.

## Ficha de cada activo
Arriba de la página de cada activo hay una **ficha** que aparece al instante con:
- **Tipo:** Acción, ETF, Índice, Futuro, Cripto, Bono o Divisa. Al pasar el mouse dice en una frase qué es.
  - Al cargar, la app compara el tipo de **todos** los activos con el que dice Yahoo Finance y corrige los que no
    coinciden.
  - En la revisión de noviembre de 2026 no hubo que corregir ninguno: ninguna cripto aparece como ETF.
- **Sector real:** tecnología, petróleo y gas, bancos, etc.
  - Ya no aparece «Empresa».
  - Los índices dicen «Varios sectores», los futuros su materia prima y las divisas «Divisas».
- **País**, en español.
- **Tamaño:** la capitalización de mercado, explicada al pasar el mouse.
  - Si Yahoo no la trae, se calcula con **precio × número de acciones**.
  - Solo 3 activos quedan sin tamaño, porque Yahoo no trae ni el número de acciones: la preferencial de Cementos
    Argos, el ETF ICOLCAP y Banorte.
- **Dividendos.** En los índices dice «El índice no paga, pero sus ETFs (por ejemplo SPY, VOO) sí, ~X% al año».
- **El horario** de su bolsa y **dónde comprarlo**.
- **«A qué se dedica y principales riesgos»:** una sección que se abre con un clic. La descripción la escribe
  Claude la primera vez (tarda unos segundos) y queda guardada en `fichas.json`.
  - Los años de crisis (2008, 2020 y los que mencione) son **botones que abren la gráfica de ese año**, con cuánto
    cambió y su peor caída.

## Íconos y leyenda
La columna **Sector** usa un ícono **con su nombre** al lado: 💻 Tecnología, 🛢️ Petróleo y gas, ⛏️ Minería,
🏦 Bancos, ⚡ Energía eléctrica, 🛒 Consumo, 💊 Salud, 🏭 Industria, 🪙 Cripto, 📜 Futuros, 🧺 ETF y 📊 Índice.
- **Leyenda:** arriba de cada tabla.
- **Al pasar el mouse** por el título de las columnas sale su explicación.
- **La casilla de la izquierda** de cada fila sirve para **abrir la página del activo**.

## Gráficas
- **Franjas de tendencia:** en la gráfica de cada activo, una franja **verde suave** marca los periodos al alza
  (precio sobre la media de 50 y esta sobre la de 200) y una **roja suave**, los periodos a la baja.
- **Filtro por mercado:** en **Semanal** y en **Comparar con otros activos** hay un filtro por mercado. Si no
  marcas ninguno, salen todos.

## Diseño
La app usa un estilo **HUD de ciencia ficción**:
- fondo casi negro,
- acentos **cian** y **magenta**,
- **verde neón** para lo que sube y **rojo** para lo que baja,
- paneles con bordes finos que brillan,
- títulos en **Orbitron** (futurista), texto en **Exo 2** (futurista pero fácil de leer) y números grandes.

**Revisión de diseño (noviembre de 2026):**
- **Contraste:** el texto se lee bien sobre el fondo oscuro, según la norma de accesibilidad WCAG AA. Los bordes
  de las casillas ahora se ven: antes casi no se distinguían.
- **Celular:** los títulos y los números grandes se achican en pantallas pequeñas. La barra de abajo respeta el
  borde de los iPhone y sus botones son fáciles de tocar.
- **Jerarquía:** los avisos azules quedan solo para lo importante. Los mensajes menores ahora son texto gris
  pequeño.
- **Teclado:** al moverte con la tecla Tab, lo seleccionado se marca con un borde magenta.

Si en tu computador tienes activada la opción de reducir movimientos, las animaciones se apagan solas.

## Análisis avanzados
En la página de cada activo (pestaña «Señal de hoy») y en el simulador hay cinco secciones **cerradas**. Cada una
calcula solo cuando la abres y trae un **?** con su explicación al pasar el mouse.
- **Volatilidad (ATR):** cuánto se mueve el precio en un día normal.
  - La sección pone lado a lado el stop loss fijo de 3% y un **stop sugerido de 2 veces el ATR**.
  - Si el activo se mueve mucho, el 3% te puede sacar por un movimiento normal.
  - **La regla no cambia sola:** si quieres cambiarla, pídelo.
- **Soportes y resistencias:** una gráfica del último año con líneas verdes (soportes, pisos donde rebotó) y
  rojas (resistencias, techos donde se frenó). Línea más gruesa = nivel tocado más veces.
- **Sentimiento de noticias:** cada titular de la semana marcado como 🟢 positivo, 🔴 negativo o ⚪ neutro, con el
  balance. El balance también aparece como **señal extra** en «¿Por qué esta decisión?». Es una pista: se cuenta
  con palabras y no entiende ironías.
- **Correlación:** qué tanto se mueven juntos tus activos, reales y simulados. Si dos pasan de 0,8, la app avisa
  que tener los dos no reparte el riesgo. Por ejemplo, Exxon y Chevron están en 0,88.
- **Valor en riesgo (VaR) al 95%:** cuánto podría perder cada portafolio (Mis activos y Simulador) en un día
  malo, en US$ y en pesos. Solo 1 de cada 20 días se pierde más que eso.

## Índices: se compran con su ETF
Un índice (S&P 500, Nasdaq 100...) no se compra directamente. En la página de un índice:
- **«Comprar / No comprar» se refiere a su ETF**, y la app lo aclara debajo de la decisión.
- **El botón de comprar ofrece su ETF:**
  - S&P 500 → SPY o VOO;
  - Nasdaq 100 → QQQ;
  - Dow Jones → DIA;
  - Russell 2000 → IWM;
  - Bovespa → EWZ;
  - y así con los demás.

## Cuándo vender: plazo y hora
La app mira qué pasó en los días parecidos si se vendía a los **1, 2, 3 o 5 días de mercado**, siempre en días y
nunca en minutos. Elige el plazo que dio más ganancia promedio, ya restado el costo.
- **Hora sugerida:**
  - **Antes de la apertura** (deja la orden programada), si vender al abrir dio más.
  - **Al cierre**, si vender al final del día dio más.
  - **En la apertura**, si dio casi lo mismo.
- **Tabla de aciertos de cada plazo:** el % de días parecidos que terminó más arriba y la ganancia promedio
  vendiendo al cierre o en la apertura.

## Time Machine (cambios)
- **Solo dice «a favor»** si la ganancia esperada, ya restada la comisión, es **claramente positiva** (más de
  +0,25%). Ganar 0,05% no compensa el riesgo. Esto también cambia la decisión: sin «a favor» no hay COMPRAR.
- **Ganancia esperada en verde** si es positiva y **en rojo** si es negativa.
- **Si toca el stop más veces que el objetivo**, lo avisa en un recuadro naranja.
- **El peor caso puede ser peor que el stop de -3%:** el stop no garantiza el precio. Si sale una noticia de
  noche, el precio puede **abrir** mucho más abajo (un «gap») y la venta se hace a ese precio.

## Tu stop loss personal
Junto a la decisión de cada activo:
- **La regla base:** 3%.
- **Un campo para tu stop personal** de ese activo.
- **El botón «Usar el sugerido por volatilidad (ATR)»,** que pone 2 veces el movimiento diario normal. Al pasar el
  mouse explica qué es el ATR.

Al guardarlo se usa en **tus compras de ese activo**, reales y simuladas: columna Stop, sugerencia de vender y
alertas. La regla de la estrategia (los 3% de la Time Machine y del ranking) no cambia. Se guarda en
`stops_personales.json`.

## Comisiones de Trii en el simulador
Cada compra y venta del simulador descuenta:
- **14.875 COP** (IVA incluido) por operación de hasta **5.000.000 COP**;
- **0,25% + IVA** por encima de ese monto;
- en los activos en US$, además, el **spread cambiario** (1% por defecto).

Todo se puede cambiar en **Simulador → Comisiones de Trii**, y queda guardado en `comisiones.json`. Las
operaciones viejas conservan el costo con el que se hicieron.

**Calculadora de comisiones:** antes de cada compra muestra la comisión de compra, la de venta y **cuánto tiene que
subir el activo solo para empatar**.
- Con montos pequeños la comisión fija pesa muchísimo: con 100.000 COP, el activo tiene que subir 35% (acción
  colombiana) o 38% (acción en dólares, por el spread) solo para empatar.
- Si las comisiones se comen más que el objetivo de +6%, la app lo avisa.

## Comprar y vender desde cualquier activo (un solo simulador)
- **Al final de la página de cada activo** hay un botón rápido para comprar o vender. Va al **mismo saldo e
  historial** de la pantalla Simulador.
- **Antes de cada compra o venta sale una ventana de confirmación** en lenguaje sencillo. Por ejemplo: «Vas a
  comprar 2 unidades de SPY, un ETF que sigue al S&P 500, por US$ X (COP Y). Comisión estimada: Z. ¿Confirmas?».
  Siempre dice qué tipo de activo es, con una frase.
- **Si el saldo no alcanza**, dice «Saldo insuficiente: tienes X disponibles» en la moneda que elegiste, en vez del
  error de antes.

## Modo automático
- **Sigue operando solo:** a las 9:45 a.m., 12:00 m. y 3:30 p.m., y en la vigilancia de cada 15 minutos, si toca el
  stop o el objetivo.
- **Telegram te avisa cada compra y venta con su razón** y, en el resumen de las 8:00 p.m., la **ganancia o pérdida
  del día** del simulador. Cada noche guarda una foto del total en `simulador_historial.csv`.
- **En Alertas, «Aciertos del modo automático» (uso del superadmin)** compara el automático con comprar y mantener:
  rendimiento, operaciones, aciertos y peor caída. Las mismas compras, pero sin vender hasta hoy.
- **Al pasar el mouse sobre el modo** (pantalla Simulador) se explica qué hacen Automático y Manual.

## Días parecidos
- La columna «Casos» ahora se llama **«Días parecidos»**. Al pasar el mouse explica que son días de los últimos 5
  años con una situación parecida a hoy (el filtro).
- Debajo dice la muestra: «Muestra: últimos 5 años, del [fecha] al [fecha]».

## Ranking (en la página del activo)
- **Abre directo en el puesto del activo** que estás viendo, resaltado, con 10 puestos arriba y 10 abajo. Un
  interruptor muestra el ranking completo.
- Columnas **Tipo** y **nombre completo**, con ancho justo y todo centrado.
- **Decisión con color:** Comprar en verde, No comprar en rojo y Esperar en gris.

## Página del activo: más rápida
- Lo básico carga primero: ficha, decisión y gráfica.
- Lo pesado carga **solo al abrir su sección**:
  - la descripción de Claude;
  - el abanico de Monte Carlo;
  - la estacionalidad;
  - los análisis avanzados.
- **Antes**, un activo abierto por primera vez tardaba de 25 a 28 segundos, porque esperaba a que Claude escribiera
  la descripción. **Ahora** tarda unos pocos segundos (ver la medición en la sección de pruebas).
- **Estacionalidad** (meses y días de la semana) en la página de **cada** activo, incluidos los índices.
- **Botón «Ver noticias»** grande, debajo del nombre.
- **Gráfica con filtro «1 día»:** usa precios **por hora** del último día de mercado, en hora de Bogotá.

## Sentimiento con caras
Cada titular lleva 😊 si es positivo, 😞 si es negativo o 😐 si es neutro. **A la derecha, el balance de la semana**
muestra la cara feliz o la triste según cuál pese más (😐 si empatan).

## Contador según el filtro
En la barra izquierda, «¿Cuántos activos hay?» cuenta **solo los del filtro** que elegiste, por tipo y por mercado.

## Carrusel del Inicio
Tiene los mismos mercados de Seguimiento:
- **Por región**, cada uno con sus índices, bonos, **banco central** (y su próxima reunión si está en el calendario)
  y **moneda**:
  - **Estados Unidos:** S&P 500, Nasdaq, Dow, Russell, tasa del Tesoro, Fed y dólar.
  - **Europa:** BCE, euro y libra.
  - **Asia:** Banco de Japón y yen.
  - **Latinoamérica.**
  - **Colombia:** Banco de la República y peso. Los TES no tienen datos gratuitos.
- **Por tipo:** Materias primas, Cripto, Futuros, Divisas, ETFs y Bonos globales.

Mis activos va aparte, debajo del carrusel.

## Latinoamérica y Divisas (pestañas nuevas)
- **Latinoamérica:** Brasil, México, Chile, Perú y Argentina, **sin Colombia**.
  - Bovespa, IPC de México y las ADR grandes (Itaú, Nubank, Petrobras, América Móvil, FEMSA, SQM, Credicorp, Galicia,
    YPF, Mercado Libre...).
  - Chile, Perú y Argentina no tienen su índice en Yahoo (el Merval dejó de actualizarse), así que se usan sus ETFs
    ECH, EPU y ARGT.
- **Divisas:** USD/COP, EUR/USD, USD/MXN, USD/BRL, USD/JPY, GBP/USD, USD/CLP, USD/PEN, USD/ARS, USD/CNY, USD/CAD,
  USD/CHF, AUD/USD, EUR/COP y el índice del dólar (DXY).
  - Tienen todo el análisis. No se compran en Trii.
  - Las divisas guardadas también sirven para pasar de una moneda a otra sin internet.
- **Cada mercado es un bloque independiente:** en `activos.py`, `MERCADOS_ACTIVOS`, pon `False` para apagar uno.
  Desaparece de las pestañas, los filtros y el carrusel.

## Aprende (tutorial)
La página **Aprende** (barra de abajo) explica en sencillo y con un ejemplo:
- volatilidad (ATR);
- soportes y resistencias;
- correlación;
- sentimiento;
- valor en riesgo;
- Monte Carlo y sus bandas;
- Prophet;
- Time Machine.

En cada sección de la app, el botón **«¿Qué es esto?»** abre su explicación.

## Modo claro y oscuro
La app tiene un tema **oscuro** (el HUD de siempre) y uno **claro**.
- **Para cambiar:** menú **⋮** (arriba a la derecha) → **Settings** → **Choose app theme** → **Light** o **Dark**.
  El botón «Modo claro / oscuro» de la barra izquierda te recuerda dónde está: Streamlit no deja que un botón de la
  app cambie el tema por su cuenta.
- **En modo claro**, las gráficas quedan como paneles oscuros, porque el neón no se lee sobre blanco.

## Diario de errores
Cuando una venta (real o simulada) cierra en pérdida, en Mis activos y en el Simulador aparece la pregunta
**«¿Qué pasó?»**. Respondes con un clic:
- Entré tarde
- Ignoré la señal
- Noticia inesperada
- Stop muy ajustado
- Otra

La app muestra una gráfica con **tus errores más repetidos**. Se guarda en `diario_errores.csv`.

## La app en la nube (gratis)
- **Enlace:** https://app-petroleo-2jsrncgu76vcg3kdfxjqyc.streamlit.app/ (Streamlit Community Cloud).
- **Código:** repositorio privado https://github.com/jsebastiannm21-dotcom/app-petroleo
  - El `.env`, los secrets y tus datos **nunca** se suben: lo impide `.gitignore`.
- **Datos:** en Supabase.
  - Compras, ventas, el simulador de cada usuario, ajustes, diario de errores y usuarios van en tablas.
  - Ranking, noticias y precios van en el almacenamiento privado `datos`.
  - Las claves están en los "secrets" de Streamlit y de GitHub, no en el código.
- **Login con Google** (el oficial de Streamlit). La primera vez se piden nombre, institución, tipo de cuenta y,
  opcionales, género y edad. También la aceptación de términos y de datos (Ley 1581 de 2012), con casilla aparte
  para «acepto que me contacten».
- **Roles:**

  | Rol | Qué puede hacer |
  |---|---|
  | Superadmin (tú) | Ve todo, incluido Mis activos, el modo automático y los usuarios |
  | Profesor | Tú lo apruebas en Alertas → Usuarios registrados; mientras tanto usa la app como estudiante |
  | Estudiante | Análisis y simulador manual |
  | Inversionista | Todo el análisis y el simulador manual y automático |

  Cada usuario tiene **su propio simulador**. Mis activos, Telegram y los aciertos del automático solo los ves tú.
- **Menú de perfil** (arriba a la derecha): tus datos, activos, ganancias, pérdidas, desde cuándo operas, última
  operación y «Cerrar sesión».
- **En tu PC** la app entra directo como superadmin: `abrir_app.bat` pone `APP_LOCAL=1`. En la nube siempre se pide
  el login, y sin login configurado la app se bloquea.

### Tareas en la nube (GitHub Actions, con tu PC apagado)
- Reportes de 8:00, 9:45, 12:00, 3:30 y 8:00 p.m.
- Vigilancia **cada 30 minutos** de 7:15 a.m. a 9:45 p.m. Cada 15 minutos se pasaría de los 2.000 minutos gratis
  al mes.
- Resumen de fin de semana (sábado y domingo, 4:00 p.m.) y backtest de los domingos (6:00 p.m.).
- Una visita a la app cada 4 horas para que no se duerma.

Se ven en GitHub → pestaña **Actions**, y desde ahí se puede correr cualquiera a mano (**Run workflow**). GitHub a
veces las atrasa unos minutos. Los precios completos se suben 2 veces al día (mañana y cierre), para no pasar el
límite gratis de descargas de Supabase.

### En tu PC (Programador de tareas)
Solo dos tareas, que guardan sus resultados en Supabase. Si el PC está apagado, corren apenas lo prendas.
- **Claude en la nube:** 7:30 a.m.
- **Kronos en la nube:** 8:20 a.m.

### Cómo actualizar la app
1. Pídele el cambio a Claude en esta carpeta (o edita los archivos).
2. Claude lo prueba y lo sube a GitHub. Si lo haces tú, en la carpeta de la app:
   `git add -A` → `git commit -m "qué cambiaste"` → `git push`.
3. **Streamlit actualiza la app sola** en 2 a 5 minutos. Si no, en la app: **⋮ → Reboot app**.
4. Tus datos no se tocan: viven en Supabase, no en el código.

- **Si cambias una clave:** ponla en `.env` y en los Secrets de Streamlit, y doble clic en `poner_claves_github.bat`.
- **Para actualizar la lista de activos:** `python actualizar_listas.py` y luego súbelo a GitHub.

## Cómo abrir la app

**Doble clic en el ícono «App Petróleo» del escritorio.** Se abre en **http://localhost:8501**. Aparece también
una ventana negra minimizada en la barra de tareas: déjala abierta, porque si la cierras la app se apaga.

---

## Las pantallas

Abajo hay una barra fija con **Inicio, Seguimiento, Simulador y Alertas**. A la izquierda está el **selector
de activo** y, debajo, la casilla **Sugerencia**, con la decisión, la probabilidad y la razón en una frase.

### Inicio
- **Arriba, el consejo del día:**
  - **Hoy compra estos:** los activos que dicen COMPRAR, con su precio, stop loss, objetivo y la fecha en que
    conviene vender.
  - **Hoy vende estos:** tus compras reales y las del simulador que tocaron el stop loss o el objetivo, o
    cuya probabilidad bajó de 50%.
- **Tres tarjetas, una por mercado (Nasdaq, Petróleo y Oro):** precio, cambio del día, estado (alcista,
  bajista o neutral), sugerencia y próximo evento.
- **Abajo:** el top 5 del ranking, Mis activos y las alertas de hoy.
- **Actualizar datos:** descarga precios y noticias nuevas.

### Seguimiento
Tiene siete pestañas: **Todo, Nasdaq, Petróleo, Oro, ETFs, Dividendos y Mis activos**.
- **En las listas de activos:**
  - Debajo de las pestañas eliges el **periodo** del cambio y de la mini gráfica: 1 día, 1 semana, 15, 30,
    60, 90 o 180 días, 1 año o 5 años.
  - Toca una fila para abrir la página del activo.
- **Dividendos** y **Mis activos:** se explican más abajo.

### Página de un activo
- **Toca el nombre de la empresa** para ver **todas sus noticias**, de la más reciente a la más antigua, con
  titular, fuente, fecha, hora y enlace. Puedes filtrar por hoy, la última semana, el último mes o todas.
- **Arriba, la decisión en grande.** Se explica más abajo.
- **Pestañas:**
  - **Señal de hoy:** gráfica con filtros de fechas, comparación con otros activos y los **casos parecidos**
    (en verde los que subieron y en rojo los que bajaron), con una nota de por qué comprar o no hoy.
  - **Pronóstico:** proyección a 30 días.
  - **Simulador:** comprar o vender ese activo con plata virtual.
  - **Calendario:** los próximos eventos de su mercado.
  - **Ranking:** el puesto del activo entre todos.
  - **Análisis de Claude:** todos los análisis de Claude sobre ese activo, con su fecha.

---

## La decisión

### Paso 1: la app

| Decisión de la app | Cuándo |
|---|---|
| **COMPRAR** | Hay 30 casos parecidos o más, la probabilidad de subida es **56% o más** y la **Time Machine sale a favor** |
| **NO COMPRAR** | La probabilidad es menor a 56%, o la Time Machine sale en contra |
| **ESPERAR** | No hay datos suficientes (menos de 30 casos), el precio está **por debajo de su media de 200 días y sigue cayendo**, o **hoy no hay mercado** (fin de semana o festivo de Wall Street) |
| **SOLO MIRAR** | Solo para Bitcoin: sin señales de compra |

**La protección del último caso:** aunque todo lo demás diga COMPRAR, si el precio está por debajo de su
tendencia de largo plazo y sigue más bajo que hace 5 días, la app espera. La **señal de rebote** es que el
precio deje de caer, es decir, que vuelva a estar por encima del de hace 5 días.

### Paso 2: Claude revisa (decisión unificada)

A las **7:30 a.m.**, Claude analiza los activos que dicen COMPRAR y los que tienes:
- sus resultados recientes,
- cómo está frente a sus pares,
- las noticias.

Usa las skills financial-analysis y equity-research. Con eso, la decisión final queda así:

| Decisión final | Color | Cuándo |
|---|---|---|
| **COMPRAR CONFIRMADO** | Verde | La app dice COMPRAR y Claude está de acuerdo |
| **COMPRAR CON CAUTELA** | Amarillo | La app dice COMPRAR pero Claude tiene dudas (las verás escritas), o todavía no lo ha revisado |
| **NO COMPRAR** | Rojo | Lo dice la app |
| **ESPERAR** | Gris | Lo dice la app |

Un análisis de Claude vale por 3 días. También puedes pedir uno al momento en la pestaña **Análisis de
Claude** de cada activo. Tarda de 1 a 5 minutos y **consume uso de tu plan de Claude**, por eso cada
mañana revisa como máximo 8 activos.

## Cómo leer la probabilidad
La app busca en los últimos 5 años los días parecidos a hoy. Son parecidos si tienen la misma tendencia de
las medias de 50 y 200 días y un RSI similar. Luego cuenta en cuántos de esos días el precio estaba más
arriba 5 días después.

> "74%" = de cada 100 días parecidos, 74 terminaron más arriba 5 días después.

Exige **al menos 30 casos**. Si no los encuentra, afloja los filtros: primero quita el mes y después amplía
el RSI. Si ni así llega a 30, dice ESPERAR.

## Cómo leer los escenarios
La app ordena los casos parecidos del peor al mejor y los parte en tres grupos iguales: **pesimista**,
**base** y **optimista**. Cada uno muestra dos números:
- **Retorno esperado:** el promedio de ese grupo.
- **Pérdida máxima:** la peor caída que tocó el precio durante esos 5 días, aunque después se recuperara.

La **predicción a 5 días** usa el escenario base.

## Cómo leer la Time Machine
1. Repite **10.000 veces** la compra de hoy, armando recorridos de 5 días con días reales que vinieron
   después de los casos parecidos.
2. En cada recorrido vende con la primera de estas tres:
   - Toca el **stop loss** (-3%).
   - Toca el **objetivo** (+6%).
   - Pasan **5 días**.
3. Te muestra:
   - **Cuántas veces** llegó al objetivo, tocó el stop o vendió a los 5 días.
   - **Ganancia esperada:** el promedio, ya descontado el 0,5% de costo. **Si es negativa, la decisión es NO
     COMPRAR.**
   - **Peor caso:** la peor de las 10.000 simulaciones.
   - **Cuándo vender:**
     - El plazo de la ganancia esperada: hasta 5 días de mercado.
     - A los cuántos días suele venderse.
     - Una **fecha sugerida** de venta.

## Predicción a 5 días y sus escenarios
En la decisión grande, **Predicción a 5 días** muestra el precio esperado y, debajo, su **rango**: entre qué
precios termina el activo en 8 de cada 10 simulaciones.

Toca **Ver escenarios** para abrir el análisis completo. Cada escenario trae su **probabilidad**, el
**precio esperado**, el **retorno**, la **pérdida máxima** antes de vender, el **plazo en días** y una frase de
**qué tendría que pasar** para que ocurra:
- **Optimista:** llega al objetivo (+6%).
- **Base:** pasan los 5 días sin tocar ni el objetivo ni el stop loss.
- **Pesimista:** toca el stop loss (-3%).

## Abanico de predicciones (Monte Carlo)
En **Señal de hoy**, debajo de la gráfica del precio:
- **Los caminos:** desde el último precio salen **100 caminos posibles**, armados con cambios diarios reales de
  los últimos 2 años. En **verde** los que terminan arriba y en **rojo** los que terminan abajo.
- **Las líneas guía:** la **línea blanca** es la mediana y las **punteadas magenta**, las bandas del 10% y del
  90%.
- **El panel de abajo:** la mediana, el rango y **cuántos caminos suben y cuántos bajan**.
- **El plazo:** puedes mirar 5, 10 o 20 días hacia adelante.

## Pronóstico: Prophet, método sencillo y Kronos
En la pestaña **Pronóstico** la banda magenta es el rango probable. Antes no se veía; ya está arreglada.
- **Kronos** es un modelo de código abierto entrenado con velas de mercado (versión small). Aparece como una
  **línea verde punteada** al lado del pronóstico actual. Corre en tu computador: la primera vez tarda unos
  20 segundos y después unos pocos.
- **Interruptor:** puedes apagarlo con «Kronos como segundo pronóstico».

## Tasa de aciertos de las predicciones
Cada mañana la app guarda la predicción a 5 días de **Prophet, Monte Carlo y Kronos** para los activos que
sigues. Cuando se cumple el plazo, la compara con el precio real y mide tres cosas:
- si acertó la **dirección** (sube o baja),
- si el precio quedó **dentro del rango**,
- el **error promedio**.

Lo ves por activo en **Pronóstico → Tasa de aciertos**. Los primeros resultados aparecen 5 días de mercado
después de la primera predicción guardada.

## Precio de compra, stop loss y objetivo
- **Precio de compra:** el último precio.
- **Stop loss (-3%):** si el precio baja hasta aquí, se vende para que la pérdida no crezca.
- **Objetivo (+6%):** si el precio sube hasta aquí, se vende para asegurar la ganancia.

Las mismas reglas se usan en la app, el simulador, el backtest, las alertas y Mis activos.

---

## Mis activos (real)
Aquí anotas lo que **compras y vendes de verdad** en Trii. La app no compra ni vende nada; solo lleva la
cuenta. Está en **Seguimiento → Mis activos**.

1. **Compra:**
   - Elige el activo. Puedes filtrar por mercado; si no marcas ninguno, salen todos.
   - **Fecha y hora de Colombia (Bogotá):** son obligatorias y vienen con la de ahora.
   - **Registrar por:**
     - **Monto invertido:** por ejemplo 20.000 COP. La app calcula sola la cantidad o fracción con el precio de
       ese momento.
     - **Cantidad:** escribes cuántas acciones compraste.
   - **Números:** escríbelos en **formato colombiano** (20.000 o 1.234,56). Debajo ves cómo los leyó la app
     mientras escribes.
   - **El aviso de "se aleja más de 5%"** compara siempre en la misma moneda. Antes salía 98,8% porque los
     20.000 se habían escrito en la casilla del precio; ahora van en «Monto invertido».
   - **Moneda:** elige **«Precio en: US$ o COP»**. La app convierte con la **tasa del dólar del día de la
     operación** y guarda el precio en las dos monedas.
   - **Precio:** la app **rellena sola el precio real** a esa fecha y hora, en la moneda que elegiste. Si
     escribes uno que se aleja más de 5%, te avisa.
2. **Venta:** solo aparecen los activos que tienes, con la cantidad disponible. No te deja vender más.
3. **Arriba ves cuatro números, en US$ y en COP:**
   - **Invertido:** con la tasa del día de cada compra.
   - **Valor actual:** con la tasa de hoy.
   - **Ganancia en papel:** de lo que todavía tienes.
   - **Ganancia realizada:** de lo que ya vendiste.
4. **Cada compra muestra** su stop loss, su objetivo y **Mantener** o **Vender**.
5. **Gráfica:**
   - Una línea por activo y otra del **total en US$**.
   - Debajo, el precio de un activo con su precio de compra, stop loss y objetivo como líneas horizontales,
     y el momento de la compra marcado.
   - Periodo de 1 a 360 días, con la ganancia o pérdida de ese periodo.
6. **¿Te equivocaste?** En la tabla del historial:
   - **Para corregir,** toca una celda.
   - **Para eliminar,** marca la fila y toca la basura.
   - **Al terminar,** toca **Guardar cambios**.
7. **Saldo real para Trii:** escríbelo en «Mi saldo real para invertir». La app lo usa para sugerir cuántas
   acciones comprar.

## Dividendos (largo plazo)
En **Seguimiento → Dividendos**:
- **La lista de activos que pagan dividendos, ordenada por rendimiento anual,** con dos filtros: **por mercado**
  y **por frecuencia de pago** (mensual, trimestral, semestral o anual). El precio y el dividendo están en la
  moneda de cada activo (columna Moneda). Cada fila trae:
  - **Rendimiento anual:** lo pagado en 12 meses dividido por el precio.
  - **Frecuencia:** mensual, trimestral, etc.
  - **Próxima fecha de corte y de pago.** La **fecha de corte** (ex-dividendo) es la que importa: para
    cobrar, debes tener la acción **antes** de ese día. Si dice «estimada», la app la calculó con los pagos
    anteriores.
- **En Mis activos:** cuánto te han pagado y cuánto esperas en los próximos 12 meses.
- **Proyección:**
  1. Escribe cuánto aportarías cada mes.
  2. La app calcula cuánto tendrías en **10 y 20 años** reinvirtiendo los dividendos.

  Es una guía, no una promesa.

## Cierres semanales
En **Seguimiento → Semanal**: el precio de cierre de **cada viernes** (o del último día hábil de la semana) de
todos los activos.
- Se guardan en `cierres_semanales.csv` **sin borrar los anteriores**: cada semana se agrega la nueva.
- Ves una tabla del último año y una gráfica, en precio o en porcentaje para comparar.

## Estacionalidad
Ya no hay una pestaña suelta: está **dentro de cada mercado**, en el desplegable «Estacionalidad y calendario»,
junto con los **próximos eventos**. Petróleo muestra WTI y Brent; Colombia, el COLCAP y el café; Materias
primas, el petróleo, el oro y el café.
- **Por mes:** retorno promedio y % de años en que subió, en los **últimos 10 años**.
- **Por día de la semana:** retorno promedio de cada día.
- **Por qué antes decía "9 años":** los datos empezaban a mitad de mes y el primer mes no se podía medir.
  Ahora se baja un poco más de historia, así que cada mes aparece exactamente 10 veces.

Ejemplo (WTI y Brent):
- **Por mes:** el retorno promedio de cada mes y en qué porcentaje de los años subió. El **mes en curso** tiene
  borde blanco.
- **Por día de la semana:** el retorno promedio de cada día.
- **La frase de arriba** dice qué suele pasar en el mes actual. Por ejemplo, en noviembre el petróleo **suele
  bajar**: subió solo 3 de los últimos 9 años.

Se quitaron los días de abril de 2020 en que el WTI llegó a valer menos de cero, porque deformaban los
promedios.

## Bitcoin (solo para mirar)
Bitcoin (BTC-USD) está en el selector de activos para ver su **precio, gráfica, abanico y pronóstico**. No da
señales de compra, no entra al ranking y no manda alertas. Su decisión siempre dice **SOLO MIRAR**, hasta que
decidas cambiarlo.

## Predicciones de tus activos
En **Mis activos** y en el **Simulador** hay una sección de **Predicciones**:
- **Todos mis activos juntos:** el abanico de Monte Carlo del **valor total de tu cartera** en 20 días, en
  US$, con la mediana, el rango y una tabla por activo.
- **Un activo:** el abanico del activo que elijas.

**Cómo leer las bandas:** las líneas del 10% y el 90% son los **escenarios extremos y poco probables**. Solo 1
de cada 10 caminos termina por debajo de la del 10%, y 1 de cada 10 por encima de la del 90%. La **mediana**
(línea blanca) es el **caso más típico**.

## Cripto en vivo
En la página de cada cripto hay una **gráfica en tiempo real** de Binance (API pública, sin cuenta ni clave):
- Se actualiza cada 1,5 segundos.
- **Toca un punto** para ver el precio exacto de ese momento.
- Las compras y ventas del **simulador** en cripto usan este precio en vivo.
- Las señales y sugerencias **siguen siendo diarias**.

## Backtest automático (domingos)
Cada **domingo a las 6:00 p.m.** la app prueba la estrategia y te manda por Telegram, por mercado:
- el resultado de la última **semana** y del último **mes**, contra **comprar y mantener**,
- los aciertos.

**Cuándo avisa:**
- **3 semanas malas seguidas** (rindió menos que comprar y mantener): te manda una **alerta**.
- **4 semanas malas, o el último mes peor que comprar y mantener:** prueba 12 variantes de la regla (umbral
  54-60%, stop y objetivo 3/6, 4/8 o 5/10) en el **año guardado** y te **sugiere** la mejor, si es mejor que la
  actual.

**La app nunca cambia las reglas sola:** tú decides si quieres el cambio, y hace como máximo una sugerencia al
mes. Para activarlo, vuelve a correr `programar_revisiones.ps1`.

## Simulador (juego con plata virtual)
- **Análisis del activo elegido:** al escoger un activo en el formulario, aparece debajo su análisis completo
  (decisión, Time Machine, escenarios, abanico y el botón «¿Por qué esta decisión?»).
- **Saldo:** empieza con 100.000 COP. Lo puedes cambiar; al cambiarlo, la app pregunta si quieres reiniciar.
- **Modo automático:** compra (con el 20% del saldo total) y vende solo con las señales.
- **Moneda:** al comprar eliges si el monto está en **COP o US$**. Cada operación guarda su tasa del día y el
  precio en las dos monedas.
- **Modo manual:** tú tocas **Comprar** o **Vender**. Es al **precio real del momento**; si el mercado está
  cerrado, usa el último cierre y te lo dice.
- **Igual que Mis activos:** el mismo formulario, las compras abiertas con Mantener o Vender, la gráfica y el
  historial con el resultado de cada venta. Todo marcado como **SIMULACIÓN**.
- **Saldo:** disponible, invertido y total, en **COP y US$**.
- **Meta del mes:** pasar de 100.000 a 115.000 (+15%), con barra de progreso y los días que faltan. Se mide
  desde el saldo inicial: para medirla mes a mes, reinicia el simulador cada 1.º del mes.

---

## Noticias automáticas
- **De dónde salen:** de **Google Noticias** (gratis, sin clave). GDELT bloqueaba casi todas las consultas
  desde tu conexión.
- **Cuándo se actualizan:** solas en cada horario de Telegram, y cuando tocas **Actualizar datos**.
- **Cómo se ordenan:** por grupo y tipo:
  - Petróleo: OPEP, Irán, Ormuz y Trump.
  - Colombia: Ecopetrol, dólar, gobierno y política petrolera.
  - Oro: Fed, tasas, inflación y geopolítica.
  - Nasdaq: Fed, tecnológicas y empleo.
- **Sin duplicados.** La fecha de la última actualización aparece en el Inicio.

`eventos.csv` sigue guardando solo los **eventos grandes** que se marcan en las gráficas. Los titulares del
día van en `noticias.csv`, porque cientos de puntos taparían la gráfica.

### Titulares de medios
Además de Google Noticias, la app lee los titulares de estos medios:
- **Investing.com**, **Bloomberg**, **Washington Post** y **Yahoo Finance** (Yahoo, con los activos que sigues).
- **Reuters**, a través de Google Noticias.
- **Portafolio**, **La República** y **Valora Analitik**, para Colombia y Ecopetrol.

**Solo se guardan los titulares relacionados** con tus activos (reales y simulados) o con tus mercados
(petróleo, oro, Nasdaq y Colombia).

### Noticias para ti (8 a.m. y 8 p.m.)
En esos dos reportes llegan dos mensajes más:
1. **Noticias para ti:** las 5 más relevantes del día.
   - **Cómo se eligen:** primero las de tus activos, después las de tus mercados, y suman puntos las noticias
     fuertes.
   - **Qué trae cada una:** una frase de **cómo podría afectar el precio** (sube, baja o incierto, y por qué)
     y su enlace. La frase la escribe Claude; si Claude no responde, va una frase sencilla.
2. **Titulares de medios:** agrupados por medio ("Bloomberg dice:", "Investing.com dice:"...), con el titular
   y el enlace.

### Avisos al momento de noticias fuertes
Cada 15 minutos, de 7 a.m. a 10 p.m. en días hábiles, la app busca noticias nuevas. Si una de tus activos o
mercados habla de **OPEP, Fed, Trump, guerra o ataques, sanciones o una caída fuerte**, te llega al momento un
**🚨 NOTICIA FUERTE**:
- Trae el titular, la frase de impacto y el enlace.
- Cada noticia llega una sola vez.
- Llegan máximo 3 por revisión, para no llenarte de mensajes.

---

## Calendario automático
El calendario de cada mercado se llena solo hacia el futuro:
- **Inventarios de petróleo (EIA):** cada miércoles a las 10:30 a.m. de Nueva York. En noviembre eso es 10:30
  a.m. en Bogotá; con el horario de verano de EE.UU. pasa a 9:30 a.m. Si hay un festivo del gobierno de EE.UU.,
  se corre al jueves (por ejemplo, el **jueves 12 de noviembre** por el Día de los Veteranos).
- **Inflación (CPI):** a mediados de mes, 8:30 a.m. El **martes 10 de noviembre** está confirmado; las
  siguientes son **estimadas** (confirmar en bls.gov).
- **Empleo de EE.UU.:** el primer viernes del mes, 8:30 a.m. (el **4 de diciembre**). Si ese día es festivo, el
  viernes siguiente.
- **Fed:** el **9 de diciembre a las 2:00 p.m.** y las fechas tentativas de 2027.
- **OPEP+:** el **29 de noviembre** (confirmada por la OPEP); las mensuales siguientes son **estimadas** el
  primer domingo del mes.
- **Resultados de Nvidia:** el **martes 17 de noviembre** después del cierre (confirmado por Nvidia).
- **Festivos de Colombia:** la Bolsa de Colombia cierra y EE.UU. sí opera (**16 de noviembre** y **8 de
  diciembre**).
- **Wall Street cerrado o medio día:** Acción de Gracias el **26 de noviembre** (cerrado), el **27** cierra a
  la 1:00 p.m., y además Navidad y Año Nuevo.

**Avisos por Telegram:** el **día antes** de cada evento (en el reporte de las 8 a.m.) y **una hora antes** de
los que tienen hora.

**Días sin mercado:** en fines de semana y festivos de Wall Street la app **no sugiere comprar**: dice ESPERAR.

## Telegram

| Hora (días hábiles, Bogotá) | Qué llega |
|---|---|
| 7:30 a.m. | (Sin mensaje) Claude analiza los activos con COMPRAR y los tuyos |
| **8:00 a.m.** | Reporte del día, top 5, sugerencia por mercado y dividendos próximos, más **Noticias para ti** y **Titulares de medios** |
| **9:45 a.m.** | Qué comprar y qué vender hoy. Si hay **COMPRAR CONFIRMADO**, llega también la **orden lista para Trii** |
| **12:00 m.** | Revisión: ¿algo tocó el stop o el objetivo? |
| **3:30 p.m.** | Última llamada antes del cierre |
| **8:00 p.m.** | Resumen del día, aciertos y noticias de la noche, más **Noticias para ti** y **Titulares de medios** |
| Cada 15 min (7:00 a.m. a 10:00 p.m.) | **Al momento** si una posición real o simulada toca el stop loss o el objetivo, si sale una **noticia fuerte**, o si falta **una hora** para un evento del calendario |

- **Separación:** cada mensaje separa **REAL** (Mis activos) de **SIMULADO**.
- **Sin compras:** si no hay qué comprar, dice "Hoy no hay oportunidades".
- **Orden para Trii:** trae el activo, la cantidad sugerida (el 20% de tu saldo real), el precio, el stop loss,
  el objetivo y la fecha límite de venta. **La ejecutas tú en Trii** y después la registras en Mis activos.

### Qué significa cada alerta
| Alerta | Qué significa |
|---|---|
| 🟢 COMPRAR | La probabilidad llegó a 56% o más |
| 🟡 Pasó de 55% | Está cerca de la señal de compra |
| 🔴 Bajó de 50% | Es más probable que baje a que suba |
| ⚪ Zona neutral | La probabilidad volvió a estar entre 50% y 55% |
| ✨ / ⚠️ Cruce de medias | La media de 50 días cruzó por encima o por debajo de la de 200 |
| 📈 / 📉 RSI | Sobrecompra (más de 70) o sobreventa (menos de 30) |
| ↕️ Media de 200 | El precio cruzó su tendencia de largo plazo |
| 💥 Movimiento fuerte | Subió o bajó 5% o más en un día |
| ⚠️ / 🎯 Cerca | Una compra va cerca del stop loss o del objetivo |
| 🛑 / 🎯 Tocó | Una compra **tocó** el stop loss o el objetivo |
| 💵 Dividendo | Faltan 3 días o menos para la fecha de corte, o hoy es el pago |
| 📅 / 📊 Evento | Hoy o mañana hay OPEP, Fed, inflación, empleo o inventarios |
| 🚨 Noticia fuerte | Salió una noticia de OPEP, Fed, Trump, guerra o caída fuerte que afecta tus activos o mercados |

### Cómo activar los horarios
Ya están activas en el Programador de tareas de Windows (carpeta «Petroleo»):

| Tarea | Cuándo |
|---|---|
| Análisis de Claude | lunes a viernes, 7:30 a.m. |
| Reporte del día | lunes a viernes, 8:00 a.m. |
| Qué comprar y vender | lunes a viernes, 9:45 a.m. |
| Revisión del mediodía | lunes a viernes, 12:00 m. |
| Última llamada | lunes a viernes, 3:30 p.m. |
| Resumen del día (con ganancia o pérdida del simulador) | lunes a viernes, 8:00 p.m. |
| Vigilancia de stop, objetivo y noticias fuertes | lunes a viernes, cada 15 minutos de 7:00 a.m. a 10:00 p.m. |
| **Resumen de fin de semana** | **sábado y domingo, 4:00 p.m.** |
| Backtest semanal | domingo, 6:00 p.m. |

El computador tiene que estar encendido y con la hora de Bogotá. Si alguna vez hay que volver a crearlas:
```
! powershell -ExecutionPolicy Bypass -File programar_revisiones.ps1
```

### Resumen de fin de semana
El sábado y el domingo a las 4:00 p.m. llega a Telegram:
- **las noticias más importantes** de las últimas 24 horas;
- **cómo va la cripto** (Bitcoin, Ethereum, Solana, XRP, BNB y Dogecoin), con su cambio en 24 horas y en 7 días;
- **lo que podría mover el mercado el lunes:** eventos del calendario y noticias fuertes del fin de semana.

## Registro de aciertos
Cada mañana la app anota las sugerencias de COMPRAR con su fecha y precio. A los 5 días de mercado revisa si
el precio subió. En **Alertas** ves el porcentaje de aciertos:
- de la **app sola**,
- de **COMPRAR CONFIRMADO** (cuando la app y Claude coincidieron).

---

## Qué hago cada día
1. **8:00 a.m.:** lee el reporte. Revisa el top 5, si alguno de tus activos dice "Vender" y si viene algún
   dividendo.
2. **9:45 a.m.:** mira "Hoy compra estos". Antes de comprar, abre la página del activo y revisa:
   - ¿Es **CONFIRMADO** o **CON CAUTELA**? Si es con cautela, lee las dudas de Claude.
   - ¿Cuál es el **peor caso** de la Time Machine? ¿Podrías aguantar esa pérdida?
   - ¿Qué dicen las **noticias**? Toca el nombre de la empresa para verlas.
3. **Si compras en Trii,** regístralo enseguida en **Mis activos**. Así te llegan las alertas de stop loss y
   objetivo.
4. **12:00 m. y 3:30 p.m.:** si algo tuyo dice "Vender", decide tú en Trii y regístralo.
5. **8:00 p.m.:** lee el resumen y las noticias de la noche.
6. **Cada semana:** revisa en **Alertas** el porcentaje de aciertos, para saber cuánto confiar en las
   sugerencias.

## Archivos que puedes editar
| Archivo | Para qué |
|---|---|
| `eventos.csv` | Eventos grandes que se marcan en las gráficas |
| `calendario_eventos.csv` | Fechas futuras: OPEP, Fed, inflación y empleo |
| `estrategia.py` | Las reglas: 56%, 30 casos, stop loss 3%, objetivo 6% (al principio del archivo) |
| `activos.py` | La lista de activos principal y `MERCADOS_ACTIVOS` (encender o apagar cada mercado) |
| `comisiones.json` | Comisiones de Trii del simulador (también se editan desde la app) |
| `stops_personales.json` | Tu stop loss personal por activo (se edita desde la página del activo) |
| `diario_errores.csv` | Tus razones de las operaciones con pérdida |
| `actualizar_listas.py` | Las listas a mano (Japón, Corea, Taiwán, petróleo, mineras, materias, cripto, bonos) |
| `analisis_claude.py` | `MAX_ACTIVOS`: cuántos activos revisa Claude cada mañana |
| `.env` | Las claves (Telegram, eToro). **No lo compartas** |
