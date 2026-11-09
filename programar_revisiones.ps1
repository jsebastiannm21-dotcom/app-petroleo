# programar_revisiones.ps1 - Programa las tareas automáticas en Windows (lunes a viernes, hora del computador).
# El computador debe estar encendido a esas horas y con la hora de Bogotá.
#   7:30  análisis de Claude (para que el reporte de las 8:00 ya lo incluya)
#   8:00  reporte del día  |  9:45 qué comprar/vender  |  12:00 revisión  |  15:30 última llamada  |  20:00 resumen
#   Cada 15 minutos de 7:00 a 22:00: vigilancia de stop loss, objetivo y noticias fuertes (avisa al momento)
#   Sábado y domingo 4:00 p.m.: resumen de fin de semana · Domingo 6:00 p.m.: backtest semanal
# Para quitarlas: abre el "Programador de tareas" de Windows y borra la carpeta "Petroleo".

$python = (Get-Command python).Source
$alertas = Join-Path $PSScriptRoot "alertas.py"
$claude = Join-Path $PSScriptRoot "analisis_claude.py"
$dias = "MON,TUE,WED,THU,FRI"

# Tareas de la versión anterior (si existen)
foreach ($vieja in "manana", "tarde", "noche") {
    schtasks /Delete /TN "Petroleo\Revision $vieja" /F 2>$null | Out-Null
}

$tareas = @(
    @("Analisis Claude", "07:30", "`"$python`" `"$claude`""),
    @("1 Manana",        "08:00", "`"$python`" `"$alertas`" --momento manana"),
    @("2 Apertura",      "09:45", "`"$python`" `"$alertas`" --momento apertura"),
    @("3 Mediodia",      "12:00", "`"$python`" `"$alertas`" --momento mediodia"),
    @("4 Cierre",        "15:30", "`"$python`" `"$alertas`" --momento cierre"),
    @("5 Noche",         "20:00", "`"$python`" `"$alertas`" --momento noche")
)
foreach ($t in $tareas) {
    schtasks /Create /F /SC WEEKLY /D $dias /TN "Petroleo\$($t[0])" /ST $t[1] /TR $t[2] | Out-Null
    Write-Output "Programado: $($t[0]) a las $($t[1])"
}
schtasks /Create /F /SC WEEKLY /D $dias /TN "Petroleo\Vigilar stop y objetivo" /ST 07:00 /RI 15 /DU 15:00 `
    /TR "`"$python`" `"$alertas`" --momento vigilar" | Out-Null
Write-Output "Programado: vigilancia cada 15 minutos de 7:00 a 22:00 (stop/objetivo y noticias fuertes)"
$semanal = Join-Path $PSScriptRoot "backtest_semanal.py"
schtasks /Create /F /SC WEEKLY /D SUN /TN "Petroleo\Backtest semanal" /ST 18:00 /TR "`"$python`" `"$semanal`"" | Out-Null
Write-Output "Programado: backtest semanal los domingos a las 6:00 p.m."
schtasks /Create /F /SC WEEKLY /D SAT,SUN /TN "Petroleo\Fin de semana" /ST 16:00 /TR "`"$python`" `"$alertas`" --momento finde" | Out-Null
Write-Output "Programado: resumen de fin de semana (noticias, cripto y lo que mueve el lunes) sábado y domingo a las 4:00 p.m."
