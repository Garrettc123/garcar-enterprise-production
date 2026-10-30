# Read only the production runtime secret path. Attach via workload identity, not a root token.
path "secret/data/garcar/production/keys" {
  capabilities = ["read"]
}
path "secret/metadata/garcar/production/keys" {
  capabilities = ["read"]
}
