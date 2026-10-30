# Least-privilege KV read access for the application.
# Attach this policy to a dedicated AppRole; do not use a root token.
path "secret/data/garcar/production/keys" {
  capabilities = ["read"]
}

path "secret/metadata/garcar/production/keys" {
  capabilities = ["read"]
}
