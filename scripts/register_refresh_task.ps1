# Enregistre le rafraichissement quotidien de la plateforme dans le
# Planificateur de taches Windows.
#
# Frequence : une fois par jour. L'API NYC 311 publie ses donnees avec environ
# 48 h de decalage, un rythme plus soutenu ne rapporterait donc aucune donnee
# nouvelle tout en consommant du quota.
#
# Usage (PowerShell, depuis la racine du projet) :
#     .\scripts\register_refresh_task.ps1
#     .\scripts\register_refresh_task.ps1 -At "07:00" -Scope full
#
# Pour supprimer la tache :
#     Unregister-ScheduledTask -TaskName "ProcessMiningPME-Refresh" -Confirm:$false

param(
    [string]$At = "06:00",
    [ValidateSet("live", "full")]
    [string]$Scope = "live",
    [string]$TaskName = "ProcessMiningPME-Refresh"
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    throw "Interpreteur introuvable : $python. Creer l'environnement virtuel avant d'enregistrer la tache."
}

Write-Host "Projet : $projectRoot"
Write-Host "Tache  : $TaskName (perimetre '$Scope', tous les jours a $At)"

$action = New-ScheduledTaskAction `
    -Execute $python `
    -Argument "-m src.refresh --scope $Scope" `
    -WorkingDirectory $projectRoot

$trigger = New-ScheduledTaskTrigger -Daily -At $At

# Ne pas lancer sur batterie faible, et abandonner si l'execution depasse 1 h
# (signe qu'une etape est bloquee, par exemple une API qui ne repond pas).
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1)

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Write-Host "Tache existante detectee : remplacement."
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description "Process Mining PME : rafraichissement du flux de donnees et des analyses." | Out-Null

Write-Host ""
Write-Host "Tache enregistree." -ForegroundColor Green
Write-Host "  Lancer maintenant  : Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "  Consulter l'etat   : Get-ScheduledTaskInfo -TaskName '$TaskName'"
Write-Host "  Journal des runs   : logs\refresh.log"
