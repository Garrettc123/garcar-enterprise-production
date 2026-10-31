# Read only the exact production runtime secret path.
path "secret/data/garcar/production/keys" {
  capabilities = ["read"]
}
