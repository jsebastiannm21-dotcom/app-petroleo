# legal.py - Términos de uso y Política de tratamiento de datos personales (ley colombiana).
# Base: Ley 1581 de 2012 (protección de datos), Decreto 1377 de 2013 (compilado en el Decreto 1074 de 2015)
# y las guías de la Superintendencia de Industria y Comercio (SIC).
# IMPORTANTE: completa RESPONSABLE con tu nombre o el de tu organización y tu ciudad (la ley exige identificarlo).

import nube

ACTUALIZADO = "9 de noviembre de 2026"
RESPONSABLE = "el administrador de la app «Análisis de mercados»"   # Cámbialo por tu nombre completo o razón social
CIUDAD = "Bogotá D.C., Colombia"


def contacto():
    correo = nube.superadmin()
    return correo if "@" in correo else "el correo de contacto de la app (botón «Contacto»)"


def terminos():
    return f"""### Términos de uso
*Última actualización: {ACTUALIZADO}.*

1. **Qué es la app.** «Análisis de mercados» es una **herramienta educativa**. Muestra análisis de datos del pasado,
   predicciones y un simulador con **dinero ficticio**. **No es una recomendación de inversión** ni asesoría financiera,
   y no es una entidad vigilada por la Superintendencia Financiera.
2. **Tus decisiones son tuyas.** Lo que hagas con tu dinero real es tu responsabilidad. Los resultados del pasado y del
   simulador no garantizan resultados futuros. Los precios pueden tener retrasos o errores de las fuentes (Yahoo Finance,
   Binance, Google Noticias).
3. **Tu cuenta.** Entras con tu cuenta de Google. Debes dar datos reales y ser mayor de edad, o contar con la autorización
   de tu representante legal. No compartas tu cuenta.
4. **Uso correcto.** No intentes entrar a datos de otros, dañar la app ni usarla para fines ilegales. El administrador
   puede bloquear cuentas que incumplan estos términos.
5. **Cursos y eventos.** Si entras a un evento de un profesor, tu profesor verá tus operaciones, tu bitácora, tu riesgo
   y tu nota dentro de ese evento. Los demás estudiantes solo ven tu apodo (o tu primer nombre) en el ranking.
6. **Disponibilidad.** La app es gratuita y puede tener pausas por mantenimiento o fallas de servicios externos.
7. **Cambios.** Si estos términos cambian, lo avisaremos en la app.
8. **Ley aplicable.** Estos términos se rigen por las leyes de la República de Colombia.
"""


def privacidad():
    return f"""### Política de tratamiento de datos personales
*Última actualización: {ACTUALIZADO}. Ley 1581 de 2012 y Decreto 1377 de 2013 (compilado en el Decreto 1074 de 2015).*

**1. Responsable.** {RESPONSABLE}, {CIUDAD}. Contacto: **{contacto()}** (o el botón «Contacto» de la app).

**2. Qué datos recogemos.**
- Obligatorios: correo y nombre (de tu cuenta de Google), institución y tipo de cuenta.
- Opcionales: género y edad.
- De uso de la app: tus operaciones en el simulador, tu bitácora, tus visitas (día y páginas) y los mensajes que nos
  envíes.
- **No recogemos datos sensibles** (salud, religión, orientación sexual, biometría, etc.) ni datos de pago.

**3. Para qué los usamos (finalidades).** Crear y administrar tu cuenta; guardar tus simuladores; mostrar tu progreso y
el ranking de tu evento; permitir que tu profesor evalúe tu desempeño en sus eventos; responder tus mensajes; mejorar la
app; y hacer **estadísticas anónimas y agregadas** (por ejemplo, «el 70% de las compras de esta semana fueron de oro»),
que nunca identifican a nadie.

**4. Analítica de uso (Microsoft Clarity).** Usamos Microsoft Clarity, que con cookies registra de forma anónima cómo se
usa la app: clics, desplazamientos, tiempo por pantalla, mapas de calor, grabaciones de la sesión y si usas celular o
computador. Clarity oculta lo que escribes. No se usa para publicidad.

**5. Dónde se guardan (transferencia y transmisión internacional).** Tus datos se guardan y procesan en servicios con
servidores fuera de Colombia, principalmente en Estados Unidos, que cuentan con medidas de seguridad: **Supabase** (base
de datos), **Streamlit Community Cloud** (la app), **GitHub** (tareas automáticas), **Google** (inicio de sesión) y
**Microsoft Clarity** (analítica). Al aceptar esta política autorizas esa transferencia. **No vendemos ni compartimos
tus datos** con terceros para fines comerciales.

**6. Tus derechos (artículo 8 de la Ley 1581).** Puedes, gratis: **conocer, actualizar y rectificar** tus datos; pedir
prueba de tu autorización; saber cómo se han usado; **revocar la autorización y pedir que se borren** (cuando no exista
un deber legal de conservarlos); y presentar quejas ante la **Superintendencia de Industria y Comercio**, después de
haber hecho tu solicitud ante nosotros.

**7. Cómo ejercerlos.** Escribe a **{contacto()}** o usa el botón «Contacto». Las **consultas** se responden en máximo
**10 días hábiles** (prorrogables 5 más) y los **reclamos** en máximo **15 días hábiles** (prorrogables 8 más), como
dice la ley.

**8. Cuánto tiempo los guardamos (eliminación de cuentas).**
- Cuando termina tu evento, tu profesor tiene 30 días para descargar sus notas.
- Pasados esos **30 días**, tu cuenta de estudiante se **borra**, salvo que estés en otro evento o hayas pedido
  conservarla con el botón «Quiero conservar mi cuenta» y el administrador lo haya aprobado.
- Al borrarla quedan solo **estadísticas anónimas** (sin nombre ni correo).
- Puedes pedir que borremos tu cuenta en cualquier momento.

**9. Seguridad.** Las tablas tienen seguridad por fila (RLS) y solo la app puede leerlas con una clave que no está en el
código. Cada rol ve solo lo suyo. Hacemos copias de seguridad.

**10. Menores de edad.** La app está pensada para estudiantes universitarios. Si eres menor de edad, necesitas la
autorización de tu representante legal.

**11. Vigencia.** Esta política rige desde su publicación. Si cambia, lo avisaremos en la app y, si cambian las
finalidades, te pediremos una nueva autorización.
"""
