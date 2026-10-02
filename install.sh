#!/bin/bash
# ─────────────────────────────────────────────────────────────
#   AC⚡DC Console — Script de instalación y gestión
#   Un Fantasma en el Sistema · unfantasmaenelsistema.com
# ─────────────────────────────────────────────────────────────

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$APP_DIR/.venv"
SERVICE_FILE="/etc/systemd/system/acdc-console.service"
APP_USER="$(whoami)"

RED='\033[0;31m'
ORANGE='\033[0;33m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

banner() {
echo -e "${ORANGE}"
echo "  ___   ____   ____  ____   ____   ___  "
echo " /   | / ___| |  _ \|  _ \ / ___| /   | "
echo "/ /| || |     | | | | |    | |    / /| | "
echo "/ ___ || |___  | |_| | |___ | |___/ ___ | "
echo "/_/  |_|\____| |____/|____/ \____/_/  |_| "
echo -e "${BOLD}  AC${RED}⚡${ORANGE}DC${NC} ${CYAN}Advanced Control & Deployment Console${NC}"
echo ""
}

usage() {
  banner
  echo -e "  Uso: ${BOLD}./install.sh${NC} [comando]"
  echo ""
  echo "  Comandos:"
  echo "    install     Instala dependencias y configura el servicio systemd"
  echo "    start       Arranca la aplicación"
  echo "    stop        Para la aplicación"
  echo "    restart     Reinicia la aplicación"
  echo "    status      Muestra el estado"
  echo "    logs        Muestra los logs en tiempo real"
  echo "    passwd      Cambia la contraseña de admin"
  echo "    uninstall   Desinstala el servicio"
  echo ""
}

check_root() {
  if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Este comando requiere permisos de root. Usa: sudo ./install.sh $1${NC}"
    exit 1
  fi
}

# Pide una contraseña nueva (con confirmacion) y la guarda hasheada en
# config.json. La usan tanto la instalacion (obligatoria, antes de arrancar
# el servicio) como "./install.sh passwd" (para cambiarla despues).
prompt_set_password() {
  local min_attempts=3
  for _ in $(seq 1 $min_attempts); do
    echo -n "Nueva contraseña de admin (mín. 4 caracteres): "
    read -s PASS1
    echo ""
    if [ -z "$PASS1" ] || [ "${#PASS1}" -lt 4 ]; then
      echo -e "${RED}La contraseña debe tener al menos 4 caracteres.${NC}"
      continue
    fi
    echo -n "Confirmar contraseña: "
    read -s PASS2
    echo ""
    if [ "$PASS1" != "$PASS2" ]; then
      echo -e "${RED}Las contraseñas no coinciden.${NC}"
      continue
    fi
    HASH=$(python3 -c "import hashlib,sys; print(hashlib.sha256(sys.argv[1].encode()).hexdigest())" "$PASS1")
    python3 -c "
import json
with open('$APP_DIR/config.json') as f:
    c = json.load(f)
c['password_hash'] = '$HASH'
with open('$APP_DIR/config.json', 'w') as f:
    json.dump(c, f, indent=2)
"
    unset PASS1 PASS2 HASH
    return 0
  done
  echo -e "${RED}Demasiados intentos fallidos. Puedes fijarla luego con: sudo ./install.sh passwd${NC}"
  return 1
}

cmd_install() {
  check_root install
  banner
  echo -e "${CYAN}[1/6]${NC} Verificando Python 3 y dependencias del sistema..."
  if ! command -v python3 &>/dev/null; then
    echo -e "${ORANGE}Python 3 no encontrado. Instalando...${NC}"
    apt-get update -qq
    apt-get install -y python3 python3-pip python3-venv
  else
    # Python existe pero python3-venv puede no estar instalado (Ubuntu/Debian lo separa)
    PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    echo -e "  Detectado Python ${PY_VER}. Instalando python3-venv..."
    apt-get install -y python3-venv "python3.${PY_VER##*.}-venv" 2>/dev/null || \
    apt-get install -y python3-venv 2>/dev/null || true
  fi
  echo -e "${GREEN}✓ Python $(python3 --version)${NC}"

  echo -e "${CYAN}[2/6]${NC} Creando entorno virtual..."
  # Eliminar venv roto si existe
  [ -d "$VENV_DIR" ] && rm -rf "$VENV_DIR"
  python3 -m venv "$VENV_DIR"
  if [ ! -f "$VENV_DIR/bin/pip" ]; then
    echo -e "${RED}Error: no se pudo crear el entorno virtual.${NC}"
    echo -e "Prueba manualmente: apt-get install python3-venv python3.$(python3 -c 'import sys; print(sys.version_info.minor)')-venv"
    exit 1
  fi
  echo -e "${GREEN}✓ Entorno virtual en $VENV_DIR${NC}"

  echo -e "${CYAN}[3/6]${NC} Instalando dependencias..."
  "$VENV_DIR/bin/pip" install --quiet --upgrade pip
  "$VENV_DIR/bin/pip" install --quiet -r "$APP_DIR/requirements.txt"
  echo -e "${GREEN}✓ Flask y psutil instalados${NC}"

  echo -e "${CYAN}[4/6]${NC} Creando servicio systemd..."
  cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=ACDC Console — Advanced Control & Deployment Console
After=network.target

[Service]
Type=simple
User=$APP_USER
WorkingDirectory=$APP_DIR
ExecStart=$VENV_DIR/bin/python $APP_DIR/app.py
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

  # Sudoers: allow app user to run ufw and kill without password
  SUDOERS_FILE="/etc/sudoers.d/acdc-console"
  cat > "$SUDOERS_FILE" <<EOF
# ACDC Console — permisos necesarios para firewall y gestión de procesos
$APP_USER ALL=(ALL) NOPASSWD: /usr/sbin/ufw, /bin/kill, /usr/bin/kill
EOF
  chmod 440 "$SUDOERS_FILE"
  echo -e "${GREEN}✓ Permisos sudo configurados (ufw, kill)${NC}"

  systemctl daemon-reload
  systemctl enable acdc-console
  echo -e "${GREEN}✓ Servicio systemd configurado${NC}"

  # Este panel da control de root completo del servidor (procesos, systemd,
  # firewall, cron, usuarios, ficheros, paquetes). No arrancamos el servicio
  # con la contraseña de fábrica "admin" ni un segundo: se exige fijar una
  # nueva ANTES de iniciarlo, no después con un aviso que se puede ignorar.
  echo -e "${CYAN}[5/6]${NC} Fijando contraseña de administrador..."
  echo -e "${ORANGE}Por seguridad, el panel no arrancará con la contraseña de fábrica.${NC}"
  if ! prompt_set_password; then
    echo -e "${RED}No se fijó una contraseña: el servicio no se arrancará todavía.${NC}"
    echo -e "Ejecuta ${CYAN}sudo ./install.sh passwd${NC} y luego ${CYAN}sudo ./install.sh start${NC}."
    exit 1
  fi
  echo -e "${GREEN}✓ Contraseña de administrador configurada${NC}"

  echo -e "${CYAN}[6/6]${NC} Arrancando servicio..."
  systemctl start acdc-console
  sleep 2
  if systemctl is-active --quiet acdc-console; then
    PORT=$(python3 -c "import json; c=json.load(open('$APP_DIR/config.json')); print(c.get('port',8080))" 2>/dev/null || echo 8080)
    HOST=$(python3 -c "import json; c=json.load(open('$APP_DIR/config.json')); print(c.get('host','127.0.0.1'))" 2>/dev/null || echo 127.0.0.1)
    echo ""
    echo -e "${GREEN}${BOLD}✓ ACDC Console instalado y funcionando!${NC}"
    echo ""
    if [ "$HOST" = "0.0.0.0" ]; then
      echo -e "  URL (red local):  ${ORANGE}http://$(hostname -I | awk '{print $1}'):${PORT}${NC}"
    else
      echo -e "  URL: ${ORANGE}http://${HOST}:${PORT}${NC}  (solo accesible desde este equipo)"
      echo -e "  ${CYAN}Para acceder desde otro equipo, edita \"host\" en config.json a \"0.0.0.0\"${NC}"
      echo -e "  ${CYAN}y haz 'sudo ./install.sh restart' — o, mejor, pon nginx con HTTPS delante.${NC}"
    fi
    echo -e "  Usuario: ${CYAN}admin${NC}"
    echo -e "  Contraseña: la que acabas de fijar."
    echo ""
  else
    echo -e "${RED}Error al arrancar. Comprueba: journalctl -u acdc-console -n 20${NC}"
  fi
}

cmd_passwd() {
  if prompt_set_password; then
    echo -e "${GREEN}Contraseña actualizada.${NC}"
    systemctl restart acdc-console 2>/dev/null || true
  else
    exit 1
  fi
}

cmd_uninstall() {
  check_root uninstall
  systemctl stop acdc-console 2>/dev/null
  systemctl disable acdc-console 2>/dev/null
  rm -f "$SERVICE_FILE"
  rm -f "/etc/sudoers.d/acdc-console"
  systemctl daemon-reload
  echo -e "${GREEN}Servicio desinstalado. Los archivos de la aplicación se mantienen en $APP_DIR${NC}"
}

case "${1:-help}" in
  install)   cmd_install ;;
  start)     check_root start; systemctl start acdc-console; echo -e "${GREEN}Iniciado.${NC}" ;;
  stop)      check_root stop;  systemctl stop acdc-console;  echo -e "${GREEN}Detenido.${NC}" ;;
  restart)   check_root restart; systemctl restart acdc-console; echo -e "${GREEN}Reiniciado.${NC}" ;;
  status)    systemctl status acdc-console ;;
  logs)      journalctl -u acdc-console -f ;;
  passwd)    cmd_passwd ;;
  uninstall) cmd_uninstall ;;
  *)         usage ;;
esac
