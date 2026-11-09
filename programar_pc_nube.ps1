# programar_pc_nube.ps1 - Cuando la app ya está en la nube: tu PC solo hace Kronos y el análisis con Claude
# (lo demás lo hace GitHub Actions). Borra las tareas viejas del PC para que no lleguen mensajes repetidos.
#   7:30 a.m.  análisis con Claude (claude -p), guardado en Supabase
#   8:20 a.m.  predicciones de Kronos, guardadas en Supabase
# Si el PC está apagado a esa hora, la tarea corre apenas lo prendas.

$python = (Get-Command python).Source
$nube = Join-Path $PSScriptRoot "nube.py"
foreach ($vieja in "1 Manana", "2 Apertura", "3 Mediodia", "4 Cierre", "5 Noche", "Vigilar stop y objetivo",
                   "Backtest semanal", "Fin de semana", "Analisis Claude") {
    schtasks /Delete /TN "Petroleo\$vieja" /F 2>$null | Out-Null
}
foreach ($t in @(@("Claude en la nube", "07:30", "tarea claude"), @("Kronos en la nube", "08:20", "kronos"))) {
    $accion = New-ScheduledTaskAction -Execute $python -Argument "`"$nube`" $($t[2])" -WorkingDirectory $PSScriptRoot
    $cuando = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At $t[1]
    $ajustes = New-ScheduledTaskSettingsSet -StartWhenAvailable
    Register-ScheduledTask -TaskPath "\Petroleo\" -TaskName $t[0] -Action $accion -Trigger $cuando -Settings $ajustes -Force | Out-Null
    Write-Output "Programado en tu PC: $($t[0]) a las $($t[1]) (lunes a viernes)"
}
