#!/bin/bash
# ============================================================
# Despliegue Auditor Escrutinio Presidencial 2026
# Servidor: 192.168.0.58 — puerto 5002
# ============================================================
set -e
SERVER="root@192.168.0.58"
REMOTE_PATH="/opt/softwareEscrutinios/auditor-presidencial-2026"
SERVICE="auditorpresidencial"
LOCAL_PATH="$(cd "$(dirname "$0")" && pwd)"

echo "=============================================="
echo "  DESPLIEGUE - Auditor Presidencial 2026"
echo "=============================================="
echo "Servidor: $SERVER"
echo "Ruta:     $REMOTE_PATH"
echo ""

echo "[1/4] Asegurando directorio remoto..."
ssh $SERVER "mkdir -p $REMOTE_PATH/public $REMOTE_PATH/uploads $REMOTE_PATH/db"

echo "[2/4] Copiando archivos..."
scp "$LOCAL_PATH/app.py"               "$SERVER:$REMOTE_PATH/app.py"
scp "$LOCAL_PATH/public/index.html"    "$SERVER:$REMOTE_PATH/public/index.html"
scp "$LOCAL_PATH/requirements.txt"     "$SERVER:$REMOTE_PATH/requirements.txt"
scp "$LOCAL_PATH/.env.example"         "$SERVER:$REMOTE_PATH/.env.example"
echo "  ✓ Archivos copiados"

echo "[3/4] Instalando dependencias (si falta)..."
ssh $SERVER "cd $REMOTE_PATH && [ ! -f .env ] && cp .env.example .env || true; pip3 install --quiet -r requirements.txt"

echo "[4/4] Reiniciando servicio..."
ssh $SERVER "systemctl restart $SERVICE && sleep 2 && systemctl is-active $SERVICE"

echo ""
echo "Verificando HTTP..."
for i in 1 2 3 4 5 6 7 8 9 10; do
  CODE=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 http://192.168.0.58:5002/api/health 2>/dev/null || echo 000)
  if [ "$CODE" = "200" ]; then
    echo "  ✓ Flask responde (HTTP 200)"
    exit 0
  fi
  echo "  intento $i: HTTP $CODE..."
  sleep 6
done
echo "  ✗ Flask no respondió a tiempo. Revisar: ssh $SERVER 'journalctl -u $SERVICE -n 30 --no-pager'"
exit 1
