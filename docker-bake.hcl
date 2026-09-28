# The three images of ADR 0104, built for the registry:
#   docker buildx bake                 # build all three
#   docker buildx bake --push          # and push them
#   TAG=2026-09-28 docker buildx bake --push backend
# The names are the ones Compose gives its local builds. amd64 only:
# praat-parselmouth ships no Linux aarch64 wheel (see compose.yaml), and the
# frontend follows so every image matches the host. The frontend image carries
# no issuer; its container reads OIDC_ISSUER at runtime (frontend/spa.conf.template).

variable "REGISTRY" {
  default = "registry.internal.efre-direkt.de"
}

variable "TAG" {
  default = "latest"
}

group "default" {
  targets = ["frontend", "backend", "worker"]
}

target "_amd64" {
  platforms = ["linux/amd64"]
}

target "frontend" {
  inherits   = ["_amd64"]
  context    = "frontend"
  dockerfile = "Dockerfile"
  tags       = ["${REGISTRY}/direkt-calltrainer-frontend:${TAG}"]
}

target "backend" {
  inherits   = ["_amd64"]
  context    = "."
  dockerfile = "backend/Dockerfile"
  tags       = ["${REGISTRY}/direkt-calltrainer-backend:${TAG}"]
}

target "worker" {
  inherits   = ["_amd64"]
  context    = "."
  dockerfile = "backend/worker.Dockerfile"
  tags       = ["${REGISTRY}/direkt-calltrainer-worker:${TAG}"]
}
