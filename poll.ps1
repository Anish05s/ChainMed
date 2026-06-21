$url = "https://chainmed-production-e8ff.up.railway.app/admin/run-migration"
for ($i = 0; $i -lt 30; $i++) {
    try {
        $response = Invoke-RestMethod -Uri $url -Method Get
        Write-Output $response
        if ($response.status -eq "success" -or $response.status -eq "error") {
            Write-Output "Migration executed successfully or returned expected format!"
            break
        }
    } catch {
        Write-Output "Endpoint not ready yet, waiting 15 seconds..."
    }
    Start-Sleep -Seconds 15
}
