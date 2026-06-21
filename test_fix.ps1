$content = Get-Content -Path "d:\Project PharmaChain\backend\main.py" -Raw
$content = $content -replace '(?s)@app\.get\(''/admin/run-migration''\).*?except subprocess\.CalledProcessError as e:.*?return \{.*?\}', ""
Set-Content -Path "d:\Project PharmaChain\backend\main.py" -Value $content
