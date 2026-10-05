# AC⚡DC Console
### Advanced Control & Deployment Console
**Un Fantasma en el Sistema** · [unfantasmaenelsistema.com](https://www.unfantasmaenelsistema.com)

---

## Capturas

| | |
|---|---|
| ![Dashboard](docs/screenshots/01-dashboard.jpg) | ![Procesos](docs/screenshots/02-procesos.jpg) |
| ![Usuarios](docs/screenshots/03-usuarios.jpg) | ![Paquetes](docs/screenshots/04-paquetes.jpg) |

---

## Instalación rápida

```bash
# 1. Copia la carpeta acdc-console a tu servidor Linux
# 2. Copia tu logo al directorio static/
cp icono.png static/logo.png

# 3. Instala con un comando (requiere sudo)
chmod +x install.sh
sudo ./install.sh install
#    El instalador te pedirá que fijes la contraseña de admin ANTES de
#    arrancar el servicio: no hay ventana en la que quede expuesto con
#    la contraseña de fábrica.

# 4. Abre el navegador en:
#    http://127.0.0.1:8080  (por defecto solo accesible desde este equipo)
#    Usuario: admin  /  Contraseña: la que acabas de fijar
```

> Por defecto el panel solo escucha en `127.0.0.1` (este mismo equipo). Da
> control de root completo del servidor, así que exponerlo en la red
> (`"host": "0.0.0.0"` en `config.json`) debe ser una decisión explícita
> tuya — ver [Seguridad](#seguridad).

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
  "host": "127.0.0.1",        // 0.0.0.0 para acceso desde otros equipos
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

Este panel da control de root completo del servidor (procesos, systemd,
firewall, cron, usuarios, ficheros, paquetes). Trátalo como tratarías una
clave root, no como una app más.

- `sudo ./install.sh install` **obliga** a fijar una contraseña antes de
  arrancar el servicio; no hay ventana expuesta con la contraseña de fábrica.
- El host por defecto es `127.0.0.1` (solo este equipo). Cambia
  `"host": "0.0.0.0"` en `config.json` únicamente si necesitas acceso desde
  otros equipos, y hazlo con conocimiento de causa.
- Considera poner nginx como proxy inverso con HTTPS para acceso remoto, en
  vez de exponer `0.0.0.0:8080` directamente.
- La sesión expira tras 60 minutos de inactividad real (configurable vía
  `session_timeout_minutes`) — cada petición autenticada renueva el
  temporizador.
- `/api/login` bloquea una IP durante 5 minutos tras 5 intentos fallidos.

---

## Changelog

**2026-10-05 — Verificación real de los fixes de seguridad**

Se montó el panel desde cero en un contenedor Debian 12 desechable (con systemd real para la instalación vía `install.sh`) y se reprodujeron en vivo, sobre el código previo a estos fixes, los tres hallazgos más graves antes de confirmarlos ya corregidos:

- 🐛 **La app no arrancaba en absoluto**: `/api/processes` estaba definido dos veces (copia/pega), y Flask se negaba a arrancar con `AssertionError: View function mapping is overwriting an existing endpoint function: api_processes`. Reproducido con el `install.sh install` real (vía systemd) y arrancando `app.py` directamente. Corregido eliminando el duplicado.
- 🔓 **RCE real en `./install.sh passwd`**: la contraseña se interpolaba sin escapar dentro de un script `python3 -c "..."`; una contraseña con una comilla simple permitía ejecutar código Python arbitrario. Confirmado con un payload que crea un fichero de prueba. Corregido pasando la contraseña como variable de entorno en vez de interpolarla en el código fuente.
- 🔓 **Sobrescritura de la contraseña de cualquier usuario (incluido root)**: `/api/users/create` y `/api/users/<u>/passwd` pasaban la contraseña sin validar a `chpasswd` vía stdin (`usuario:contraseña`); una contraseña con un salto de línea inyectaba una segunda línea y cambiaba la contraseña de *otro* usuario del sistema. Confirmado creando un usuario víctima y comprobando que su hash en `/etc/shadow` cambiaba al "crear" un usuario distinto con el payload en el campo contraseña. Corregido rechazando contraseñas con `\n`/`\r`.

También se verificó en vivo (no solo lectura de código) que tras el fix: el login bloquea tras 5 intentos fallidos (429, incluida la contraseña correcta mientras dura el bloqueo), y que el panel completo (Dashboard, Procesos, Usuarios, Archivos, Paquetes, Cron, Firewall) funciona de extremo a extremo con datos reales del sistema una vez corregido el bug de arranque.

**No se pudo verificar en esta pasada** (limitación del entorno de pruebas, no del código): los módulos que dependen de `systemctl`/`ufw` reales no se ejercitaron más allá de confirmar que responden sin error, al evitar un segundo contenedor con systemd tras encontrarse inestable la primera vez en este host.

---

*AC⚡DC Console · Un Fantasma en el Sistema*
