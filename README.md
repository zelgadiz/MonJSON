# MonJSON
# 📊 MonJSON - Monitor de Sistema

## ⚙️ Operaciones del Servicio

### Comprobar estado
```bash
sudo systemctl status monjson.service
```
*Debería aparecer algo similar a:*
```text
● monjson.service
   Loaded: loaded
   Active: active (running)
```

### 📜 Ver logs del servicio
```bash
sudo journalctl -u monjson.service
```

**Seguir los logs en tiempo real:**
```bash
sudo journalctl -u monjson.service -f
```

### 🔄 Reiniciar el servicio
Después de modificar `main.py`:
```bash
sudo systemctl restart monjson.service
```

Después de modificar el archivo de configuración `monjson.conf`, también se recomienda reiniciar:
```bash
sudo systemctl restart monjson.service
```

### 🛑 Detener el servicio
```bash
sudo systemctl stop monjson.service
```

---

## 🔌 Red y Firewall

### Comprobar el puerto
El servidor utiliza el puerto **8080**. Puedes comprobarlo con:
```bash
sudo ss -lntp | grep 8080
```
*Deberías obtener algo similar a:*
```text
LISTEN 0 128 0.0.0.0:8080
```

### 🔥 Firewall
Si el servidor utiliza UFW y necesitas acceder al dashboard desde otra máquina:
```bash
sudo ufw allow 8080/tcp
```

Comprobar el estado del firewall:
```bash
sudo ufw status
```

> ⚠️ **Nota:** Si el dashboard solamente debe estar disponible dentro de una red privada, se recomienda limitar el acceso al puerto 8080 a esa red en lugar de abrirlo globalmente.

---

## 🩺 Solución de problemas

* **El servicio no inicia:**  
  Consultar los estados y los últimos logs del sistema:
  ```bash
  sudo systemctl status monjson.service
  sudo journalctl -u monjson.service -n 100
  ```

* **No se puede acceder al dashboard:**  
  Comprobar que el proceso esté escuchando:
  ```bash
  sudo ss -lntp | grep 8080
  ```
  Comprobar localmente:
  ```bash
  curl http://127.0.0
  ```
  *Si funciona localmente pero no desde otro equipo, revisar el firewall y las reglas de red.*

* **No se genera `/var/log/monjson.log`:**  
  Comprobar la existencia del archivo y los permisos del directorio:
  ```bash
  ls -lah /var/log/monjson.log
  ls -ld /var/log
  ```
  Revisar también las trazas del servicio:
  ```bash
  sudo journalctl -u monjson.service -n 100
  ```

* **No aparecen usuarios o intentos fallidos:**  
  La información depende de los mecanismos de autenticación y de los logs disponibles en el sistema Linux.  
  Comprobar los logs generales de hoy:
  ```bash
  sudo journalctl --since today
  ```
  Y en sistemas que utilicen el registro tradicional (como Debian con `rsyslog` instalado):
  ```bash
  sudo tail -n 50 /var/log/auth.log
  ```

---

## 🛡️ Consideraciones de seguridad

El endpoint `/v1/status` expone información del sistema. Entre los datos potencialmente sensibles se encuentran:
* Hostname
* Información del sistema operativo
* Procesos y usuarios activos
* Direcciones IP de origen e información de red
* Intentos de autenticación

Por este motivo, **no se recomienda exponer directamente el puerto 8080 a Internet** sin controles adicionales. En un entorno de producción se recomienda utilizar:
* Firewall
* Red privada / VPN
* Reverse proxy (Proxy inverso)
* HTTPS
* Autenticación y restricción de acceso por IP

---

## 📌 Endpoints disponibles

| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| **GET** | `/v1/status` | Devuelve las métricas del servidor en JSON |
| **GET** | `/v1/dash` | Dashboard web de monitorización |

---

## 📂 Archivos importantes

| Archivo | Descripción |
| :--- | :--- |
| `main.py` | Aplicación principal |
| `monjson.conf` | Configuración del monitor |
| `requirements.txt` | Dependencias de Python |
| `systemd/monjson.service` | Servicio systemd |
| `/var/log/monjson.log` | Historial de métricas |

---

## 🧰 Tecnologías utilizadas

* Python
* FastAPI
* Uvicorn
* psutil
* Chart.js
* Systemd
* Linux

---

## 👤 Información del Proyecto

* **Autor:** Rubén C
* **Fecha de creación:** 30 de septiembre de 2026

### 📄 Licencia
Este proyecto puede distribuirse bajo la licencia que determine el autor. Si se publica como software libre, se recomienda agregar un archivo `LICENSE` con la licencia correspondiente.

---

## 🚀 Inicio rápido

### 1. Instalación rápida
```bash
git clone <URL_DEL_REPOSITORIO>
cd monjson
pip3 install -r requirimientos.txt
python3 main.py
```
Después, abrir en tu navegador: `http://IP_DEL_SERVIDOR:8080/v1/dash`

### 2. Instalar como servicio del sistema
```bash
sudo cp systemd/monjson.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable monjson.service
sudo systemctl start monjson.service
sudo systemctl status monjson.service
```
El monitor quedará ejecutándose automáticamente como servicio de Linux.

### 3. Si tienen error de FastAPI
Luego podria dar error al ejecutar luego de la instalación de los requerimientos.txt.
Para eso solo seria cambiar un punto en el servicio y ejecutarlo desde el env..
```bash
sudo nano/etc/systemd/system/monjson.service 
# Comando para ejecutar el script (usa la ruta absoluta de python3)
ExecStart=/opt/monjson/venv/bin/python main.py
```
Con este cambio debe funcionar.
