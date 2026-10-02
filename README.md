# AC⚡DC Console
### Advanced Control & Deployment Console
**Un Fantasma en el Sistema** · [unfantasmaenelsistema.com](https://www.unfantasmaenelsistema.com)

---

## Instalación rápida

```bash
# 1. Copia la carpeta acdc-console a tu servidor Linux
# 2. Copia tu logo al directorio static/
cp icono.png static/logo.png

# 3. Instala con un comando (requiere sudo)
chmod +x install.sh
sudo ./install.sh install

# 4. Abre el navegador en:
#    http://TU-IP:8080
#    Usuario: admin  /  Contraseña: admin

# 5. ¡Cambia la contraseña!
./install.sh passwd
```

---

## Módulos incluidos

| Módulo | Descripción |
|--------|-------------|
| **Dashboard** | CPU, RAM, disco, uptime, info del sistema en tiempo real |
| **Procesos** | Lista de procesos con CPU/MEM, filtro, kill |
| **Logs** | Visor de journalctl (syslog, kernel, auth, nginx, docker) |
| **Systemd** | Start / stop / restart de servicios |
| **Firewall** | Estado de UFW, añadir/eliminar reglas ALLOW/DENY |
| **Cron** | Ver, añadir y eliminar tareas cron del usuario |
| **Usuarios** | Lista de usuarios y grupos del sistema |
| **Archivos** | Explorador de archivos, visor de texto, eliminar |
| **Paquetes** | Buscar, instalar, eliminar, actualizar paquetes APT |
| **Red** | Interfaces de red, IPs, MAC, estadísticas TX/RX |

---

## Gestión del servicio

```bash
sudo ./install.sh start      # Arrancar
sudo ./install.sh stop       # Parar
sudo ./install.sh restart    # Reiniciar
./install.sh status          # Ver estado
./install.sh logs            # Ver logs en tiempo real
./install.sh passwd          # Cambiar contraseña
sudo ./install.sh uninstall  # Desinstalar
```

---

## Configuración

Edita `config.json`:

```json
{
  "username": "admin",
  "password_hash": "...",     // SHA-256 de la contraseña
  "port": 8080,               // Puerto de escucha
  "host": "0.0.0.0",          // 127.0.0.1 para solo local
  "session_timeout_minutes": 60,
  "site_url": "https://www.unfantasmaenelsistema.com"
}
```

Tras cambiar config.json: `sudo ./install.sh restart`

---

## Requisitos

- Linux (Ubuntu/Debian recomendado, también funciona en Fedora/Arch)
- Python 3.8+
- systemd (para gestión de servicios)
- ufw (para módulo de firewall)
- apt (para módulo de paquetes)
- Ejecutar con permisos suficientes (idealmente root o sudo)

---

## Seguridad

- Cambia la contraseña por defecto inmediatamente
- Configura `"host": "127.0.0.1"` si solo necesitas acceso local
- Considera poner nginx como proxy inverso con HTTPS para acceso remoto
- La sesión expira tras 60 minutos de inactividad (configurable)

---

*AC⚡DC Console · Un Fantasma en el Sistema*
