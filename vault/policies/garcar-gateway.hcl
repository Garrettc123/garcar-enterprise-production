# Garcar production keys policy (example)
# Mount: secret/data/garcar/production/keys

path "secret/data/garcar/production/keys" {
  capabilities = ["read"]
}

path "secret/metadata/garcar/production/keys" {
  capabilities = ["list", "read"]
}
