#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# deploy.sh - Skrip deployment untuk server produksi
# Usage: ./deploy.sh
# ============================================================================

IMAGE_NAME="${DOCKERHUB_USERNAME:-namauser}/pdf-analyzer:latest"
CONTAINER_NAME="pdf-analyzer"
ENV_FILE=".env"

echo "🚀 Memulai deployment PDF Analyzer..."

# 1. Pastikan .env ada
if [[ ! -f "$ENV_FILE" ]]; then
  echo "❌ File $ENV_FILE tidak ditemukan. Buat terlebih dahulu dari .env.example"
  exit 1
fi

# 2. Pull image terbaru
echo "📥 Mengunduh image Docker: $IMAGE_NAME"
docker pull "$IMAGE_NAME"

# 3. Stop dan hapus container lama jika ada
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
  echo "🛑 Menghentikan container lama: $CONTAINER_NAME"
  docker stop "$CONTAINER_NAME" || true
  docker rm "$CONTAINER_NAME" || true
fi

# 4. Jalankan container baru
echo "▶️ Menjalankan container baru: $CONTAINER_NAME"
docker run -d \
  --name "$CONTAINER_NAME" \
  -p 8000:8000 \
  --env-file "$ENV_FILE" \
  --restart unless-stopped \
  "$IMAGE_NAME"

# 5. Tunggu health check siap
echo "⏳ Menunggu aplikasi siap..."
for i in {1..30}; do
  if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ Aplikasi siap di http://localhost:8000/health"
    echo "🎉 Deployment selesai!"
    exit 0
  fi
  echo "   Percobaan $i/30..."
  sleep 2
done

echo "❌ Aplikasi tidak siap setelah 60 detik. Periksa log:"
docker logs "$CONTAINER_NAME" --tail 50
exit 1