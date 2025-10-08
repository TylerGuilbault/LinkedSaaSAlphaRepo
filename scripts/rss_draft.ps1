param(
    [string]$FeedUrl = "https://techcrunch.com/feed/",
    [int]$Limit = 1,
    [switch]$Summarize,
    [string]$Tone = "professional",
    [int]$UserId = 6,
    [switch]$PostToLinkedIn,
    [string]$ApiBase = "http://127.0.0.1:8000",
    [string]$OutFile = ""
)

$ErrorActionPreference = "Stop"

function Sanitize-Draft([string]$text) {
    if (-not $text) { return $text }
    $lines = $text -split "(`r`n|`n|`r)" |
        Where-Object { $_.Trim() -and ($_ -notmatch '^(?i)(keep it under|rewrite the input|linkedin ghostwriter|tone:|use this article)') } |
        ForEach-Object { $_.Trim() } |
        Where-Object { $_ -ne "" }
    $t = ($lines -join "`n")
    $t = $t.Replace([char]0x2019, "'").Replace([char]0x2018, "'")
    $t = $t.Replace([char]0x201C, '"').Replace([char]0x201D, '"')
    $t = $t.Replace([char]0x2013, '-').Replace([char]0x2014, '-')
    $t = ($t -replace '[\t ]+',' ').Trim()
    $t = $t -replace "rival to Microsoft'?s OpenAI rival","rival to OpenAI"
    $sentences = $t -split "(\.|\?|!)\s+"
    $clean = @()
    foreach ($s in $sentences) {
        if (-not $s) { continue }
        if ($s -match '^(?i)(use this article|keep it under|rewrite the input|linkedin ghostwriter|tone:)') { continue }
        $clean += $s
    }
    if ($clean.Count -gt 0) { $t = ($clean -join ". ").Trim() }
    $words = $t -split '\s+'
    if ($words.Count -gt 180) { $t = ($words[0..179] -join ' ') }
    $hashtags = [Regex]::Matches($t, '(?<=\s|^)#\w+')
    if ($hashtags.Count -gt 3) {
        $tNoTags = [Regex]::Replace($t, '(?<=\s|^)#\w+', '').Trim()
        $keep = $hashtags | Select-Object -First 3 | ForEach-Object { $_.Value }
        $t = ($tNoTags + "`n`n" + ($keep -join ' ')).Trim()
    }
    return $t
}

# 1) RSS
$feedUrlEncoded = [Uri]::EscapeDataString($FeedUrl)
$feed = Invoke-RestMethod -Uri "$ApiBase/rss/test?url=$feedUrlEncoded&limit=$Limit"
if (-not $feed.items -or $feed.items.Count -eq 0) { throw "No items returned from RSS feed." }
$item = $feed.items[0]
$txt = $item.summary
if (-not $txt) { $txt = $item.description }
if (-not $txt) { $txt = "$($item.title) - $($item.link)" }

# 2) Optional summarize
if ($Summarize) {
    $sumReq  = @{ text = $txt; max_length = 100; min_length = 50 } | ConvertTo-Json
    $sumResp = Invoke-RestMethod -Method Post -Uri "$ApiBase/generate/summary" -Body $sumReq -ContentType "application/json"
    if ($sumResp.summary) { $txt = $sumResp.summary }
}

# 3) Rewrite
$gwReq  = @{ text = $txt; tone = $Tone } | ConvertTo-Json
$gwResp = Invoke-RestMethod -Method Post -Uri "$ApiBase/generate/post" -Body $gwReq -ContentType "application/json"
$draft = $gwResp.draft; if (-not $draft) { $draft = $gwResp.post }
$draft = Sanitize-Draft $draft
if (-not $draft) { $draft = "Key takeaway: $txt`n`n#Tech #AI" }

# 4) Append source (if not present)
if ($item.title -and $item.link -and ($draft -notmatch [Regex]::Escape($item.link))) {
    $draft = ($draft.Trim() + "`n`nSource: $($item.title)`n$($item.link)")
}

# 5) Output
Write-Host "`n--- DRAFT ---`n$draft`n"
if ($OutFile -and $OutFile.Trim() -ne "") {
    $outPath = [IO.Path]::GetFullPath($OutFile)
    New-Item -ItemType Directory -Force -Path ([IO.Path]::GetDirectoryName($outPath)) | Out-Null
    Set-Content -Path $outPath -Value $draft -Encoding UTF8
    Write-Host "Saved draft to: $outPath"
}

# 6) Optional post
if ($PostToLinkedIn) {
    $postReq  = @{ user_id = $UserId; text = $draft } | ConvertTo-Json
    $postResp = Invoke-RestMethod -Method Post -Uri "$ApiBase/linkedin/post" -Body $postReq -ContentType "application/json"
    Write-Host "`n--- POSTED ---`nstatus: $($postResp.status)  ref: $($postResp.ref)`n"
    $postResp | Out-Null
}
