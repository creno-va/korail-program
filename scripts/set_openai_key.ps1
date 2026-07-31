param(
    [Parameter(Mandatory = $true)]
    [string]$ApiKey
)

$ErrorActionPreference = "Stop"

[Environment]::SetEnvironmentVariable("OPENAI_API_KEY", $ApiKey, "User")
$env:OPENAI_API_KEY = $ApiKey

Write-Host "OPENAI_API_KEY has been saved to the current Windows user environment."
Write-Host "Restart the app if it is already open."
