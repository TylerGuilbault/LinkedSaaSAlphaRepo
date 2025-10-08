function Final-Scrub($t) {
  if (-not $t) { return $t }
  # Drop CP1252 controls (0x80–0x9F)
  $t = [regex]::Replace($t, '[\x80-\x9F]', '')
  # Normalize "hashtag #Word" / "hashtag#Word" → "#Word"
  $t = [regex]::Replace($t, '(?i)\bhashtag\s*#?(\w+)', '#$1')
  return $t.Trim()
}
