param(
  [string]$ApiBase   = "http://127.0.0.1:8000",
  [int]   $UserId    = 6,
  [string]$FeedUrl   = "https://techcrunch.com/feed/",
  [int]   $PickIndex = 1,              # <-- 0 = latest, 1 = second latest, etc.
  [string]$Tone      = "professional",
  [string]$Angle     = "leadership",
  [int]   $MaxWords  = 180,
  [switch]$AddUtm                       # adds a small utm so the link is “new”
)

function Get-ItemOrThrow {
  param([object]$feed, [int]$idx)
  if (-not $feed -or -not $feed.items -or $feed.items.Count -eq 0) {
    throw "No RSS items returned."
  }
  if ($idx -ge $feed.items.Count) {
    throw "PickIndex $idx out of range. Feed only returned $($feed.items.Count) items."
  }
  return $feed.items[$idx]
}

# 1) Pull a few items, pick the Nth (default: second newest = 1)
$feed = Invoke-RestMethod -Uri "$($ApiBase)/rss/test?url=$([uri]::EscapeDataString($FeedUrl))&limit=5"
$item = Get-ItemOrThrow -feed $feed -idx $PickIndex

$link  = $item.link
$title = $item.title
$raw   = $item.summary
if (-not $raw) { $raw = $item.description }
if (-not $raw) { $raw = "$title - $link" }

# Optional: add a tiny UTM so LinkedIn treats it as a fresh attachment
if ($AddUtm) {
  if ($link -match "\?") { $link = "$link&utm_source=autopost" } else { $link = "$link?utm_source=autopost" }
}

# 2) Draft (slightly varied prompt by adding a small instruction)
$req = @{
  text         = $raw + "`n`n(Write this with a fresh angle; do not repeat earlier phrasing.)"
  tone         = $Tone
  angle        = $Angle
  max_words    = $MaxWords
  source_title = $title
  source_link  = $link
} | ConvertTo-Json

$draft = (Invoke-RestMethod -Method Post -Uri "$($ApiBase)/generate/thoughtpost" -Body $req -ContentType 'application/json').draft
if (-not $draft) { throw "Draft was empty." }

# 3) Post with the (possibly UTM’d) link attached
$payload = @{
  user_id = $UserId
  text    = $draft
  link    = $link
} | ConvertTo-Json -Depth 4

$resp = Invoke-RestMethod -Method Post -Uri "$($ApiBase)/linkedin/post" -Body $payload -ContentType 'application/json'
$resp
