import time
import subprocess
import socket
import platform
import configparser
import os
import json
import logging
from logging.handlers import RotatingFileHandler

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

import psutil


# ============================================================
# CONFIGURACIÓN DE LA APLICACIÓN
# ============================================================

app = FastAPI(
    title="Servidor Metricas API - Configurable PoC MX"
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# ARCHIVOS
# ============================================================

CONFIG_FILE = "monjson.conf"

LOG_FILE = "/var/log/monjson.log"


# ============================================================
# CACHE
# ============================================================

cache_datos = {}

ultima_actualizacion = 0


# ============================================================
# LOGGER
# ============================================================

def crear_logger():

    logger = logging.getLogger("monjson")

    logger.setLevel(logging.INFO)

    if logger.handlers:
        return logger

    try:

        os.makedirs(
            os.path.dirname(LOG_FILE),
            exist_ok=True
        )

        handler = RotatingFileHandler(
            LOG_FILE,
            maxBytes=50 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8"
        )

        handler.setFormatter(
            logging.Formatter("%(message)s")
        )

        logger.addHandler(handler)

    except Exception as error:

        console_handler = logging.StreamHandler()

        console_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] %(message)s"
            )
        )

        logger.addHandler(console_handler)

        logger.error(
            "No se pudo abrir %s: %s",
            LOG_FILE,
            error
        )

    return logger


logger = crear_logger()


# ============================================================
# CARGAR CONFIGURACIÓN
# ============================================================

def cargar_configuracion():

    config = configparser.ConfigParser()

    if not os.path.exists(CONFIG_FILE):

        return {
            "refresco": 30,
            "usuarios_ocultos": [
                "root",
                "mngsrv"
            ],
            "procesos": [
                "apache2",
                "nginx",
                "sshd",
                "python3"
            ],
            "secciones": {},
            "subsecciones": {},
        }

    try:

        config.read(CONFIG_FILE)

    except Exception as error:

        logger.error(
            "Error leyendo %s: %s",
            CONFIG_FILE,
            error
        )

        return {
            "refresco": 30,
            "usuarios_ocultos": [
                "root",
                "mngsrv"
            ],
            "procesos": [
                "apache2",
                "nginx",
                "sshd",
                "python3"
            ],
            "secciones": {},
            "subsecciones": {},
        }

    # --------------------------------------------------------
    # GLOBAL
    # --------------------------------------------------------

    refresco = config.getint(
        "GLOBAL",
        "TIEMPO_REFRESCO_SEGUNDOS",
        fallback=30
    )

    if refresco < 1:

        refresco = 30

    u_ocultos = [
        u.strip()
        for u in config.get(
            "GLOBAL",
            "USUARIOS_OCULTOS",
            fallback="root,mngsrv"
        ).split(",")
        if u.strip()
    ]

    p_monitoreados = [
        p.strip()
        for p in config.get(
            "GLOBAL",
            "PROCESOS_MONITOREADOS",
            fallback="apache2,nginx,sshd,python3"
        ).split(",")
        if p.strip()
    ]

    # --------------------------------------------------------
    # VISIBILIDAD
    # --------------------------------------------------------

    secciones = {}

    if config.has_section(
        "VISIBILIDAD_SECCIONES"
    ):

        secciones = {
            opcion:
                config.getboolean(
                    "VISIBILIDAD_SECCIONES",
                    opcion,
                    fallback=True
                )
            for opcion in config.options(
                "VISIBILIDAD_SECCIONES"
            )
        }

    subsecciones = {}

    if config.has_section(
        "VISIBILIDAD_SUBSECCIONES"
    ):

        subsecciones = {
            opcion:
                config.getboolean(
                    "VISIBILIDAD_SUBSECCIONES",
                    opcion,
                    fallback=True
                )
            for opcion in config.options(
                "VISIBILIDAD_SUBSECCIONES"
            )
        }

    return {
        "refresco": refresco,
        "usuarios_ocultos": u_ocultos,
        "procesos": p_monitoreados,
        "secciones": secciones,
        "subsecciones": subsecciones,
    }


# ============================================================
# INFORMACIÓN DEL SERVIDOR
# ============================================================

def obtener_detales_servidor():

    hostname = socket.gethostname()

    try:

        fqdn = socket.getfqdn()

    except Exception:

        fqdn = hostname

    try:

        os_version = subprocess.check_output(
            [
                "lsb_release",
                "-ds"
            ],
            text=True,
            stderr=subprocess.DEVNULL
        ).strip()

    except Exception:

        os_version = (
            f"{platform.system()} "
            f"{platform.release()}"
        )

    uptime_segundos = (
        time.time()
        -
        psutil.boot_time()
    )

    dias = int(
        uptime_segundos // 86400
    )

    horas = int(
        (
            uptime_segundos % 86400
        ) // 3600
    )

    minutos = int(
        (
            uptime_segundos % 3600
        ) // 60
    )

    return {

        "timestamp_utc":
            time.strftime(
                "%Y-%m-%d %H:%M:%S",
                time.gmtime()
            ),

        "hostname":
            hostname,

        "fqdn":
            fqdn,

        "os_distribution":
            os_version,

        "kernel_version":
            platform.release(),

        "architecture":
            platform.machine(),

        "python_version":
            platform.python_version(),

        "uptime":
            f"{dias}d {horas}h {minutos}m",

        "boot_time":
            time.strftime(
                "%Y-%m-%d %H:%M:%S",
                time.gmtime(
                    psutil.boot_time()
                )
            ),

    }


# ============================================================
# OBTENER STORAGE / PUNTOS DE MONTAJE
# ============================================================

def obtener_storage():

    montajes = []

    # Filesystems virtuales que no queremos mostrar
    # como almacenamiento real.
    filesystems_excluidos = {

        "proc",
        "sysfs",
        "devtmpfs",
        "devpts",
        "tmpfs",
        "cgroup",
        "cgroup2",
        "overlay",
        "squashfs",
        "pstore",
        "debugfs",
        "tracefs",
        "securityfs",
        "configfs",
        "fusectl",
        "efivarfs",
        "hugetlbfs",
        "mqueue",
        "autofs",
        "binfmt_misc",
    }

    try:

        particiones = psutil.disk_partitions(
            all=False
        )

    except Exception as error:

        logger.error(
            "No se pudieron obtener los puntos de montaje: %s",
            error
        )

        particiones = []

    for particion in particiones:

        try:

            punto_montaje = (
                particion.mountpoint
            )

            dispositivo = (
                particion.device
            )

            filesystem = (
                particion.fstype
            )

            # ------------------------------------------------
            # Evitar pseudo-filesystems
            # ------------------------------------------------

            if (
                filesystem
                and
                filesystem.lower()
                in filesystems_excluidos
            ):

                continue

            # ------------------------------------------------
            # Obtener utilización
            # ------------------------------------------------

            uso = psutil.disk_usage(
                punto_montaje
            )

            montaje = {

                "mountpoint":
                    punto_montaje,

                "device":
                    dispositivo
                    if dispositivo
                    else "Desconocido",

                "filesystem":
                    filesystem
                    if filesystem
                    else "Desconocido",

                "total_gb":
                    round(
                        uso.total
                        /
                        (1024 ** 3),
                        2
                    ),

                "used_gb":
                    round(
                        uso.used
                        /
                        (1024 ** 3),
                        2
                    ),

                "available_gb":
                    round(
                        uso.free
                        /
                        (1024 ** 3),
                        2
                    ),

                "percentage_used":
                    uso.percent,

            }

            montajes.append(
                montaje
            )

        except (
            PermissionError,
            FileNotFoundError,
            OSError,
            ValueError
        ):

            # Un montaje problemático no debe impedir
            # que se devuelva el resto del JSON.
            continue

        except Exception as error:

            logger.warning(
                "Error procesando montaje: %s",
                error
            )

            continue

    # ========================================================
    # ASEGURAR QUE / EXISTA
    # ========================================================

    root_encontrado = False

    for montaje in montajes:

        if montaje["mountpoint"] == "/":

            root_encontrado = True

            break

    if not root_encontrado:

        try:

            uso_root = psutil.disk_usage("/")

            montajes.insert(
                0,
                {

                    "mountpoint": "/",

                    "device": "Desconocido",

                    "filesystem": "Desconocido",

                    "total_gb":
                        round(
                            uso_root.total
                            /
                            (1024 ** 3),
                            2
                        ),

                    "used_gb":
                        round(
                            uso_root.used
                            /
                            (1024 ** 3),
                            2
                        ),

                    "available_gb":
                        round(
                            uso_root.free
                            /
                            (1024 ** 3),
                            2
                        ),

                    "percentage_used":
                        uso_root.percent,

                }
            )

        except Exception:

            pass

    # ========================================================
    # ORDENAR
    # ========================================================

    montajes.sort(
        key=lambda x: (
            0
            if x["mountpoint"] == "/"
            else 1,
            x["mountpoint"]
        )
    )

    # ========================================================
    # STORAGE PRINCIPAL
    # ========================================================

    storage_root = None

    for montaje in montajes:

        if montaje["mountpoint"] == "/":

            storage_root = montaje

            break

    if storage_root is None:

        storage_root = {

            "mountpoint": "/",

            "device": "Desconocido",

            "filesystem": "Desconocido",

            "total_gb": 0,

            "used_gb": 0,

            "available_gb": 0,

            "percentage_used": 0,

        }

    return {

        "mountpoint":
            storage_root[
                "mountpoint"
            ],

        "device":
            storage_root[
                "device"
            ],

        "filesystem":
            storage_root[
                "filesystem"
            ],

        "total_gb":
            storage_root[
                "total_gb"
            ],

        "used_gb":
            storage_root[
                "used_gb"
            ],

        "available_gb":
            storage_root[
                "available_gb"
            ],

        "percentage_used":
            storage_root[
                "percentage_used"
            ],

        "mounts":
            montajes,

    }


# ============================================================
# INTENTOS FALLIDOS
# ============================================================

def obtener_intentos_fallidos():

    intentos = []

    # --------------------------------------------------------
    # journalctl
    # --------------------------------------------------------

    try:

        resultado = subprocess.check_output(
            [
                "journalctl",
                "--since",
                "today",
                "--no-pager",
                "-o",
                "short-iso"
            ],
            text=True,
            stderr=subprocess.DEVNULL
        )

        for linea in resultado.splitlines():

            if (
                "Failed password"
                not in linea
                and
                "authentication failure"
                not in linea
            ):

                continue

            partes = linea.split()

            usuario = "desconocido"

            ip = "desconocida"

            # ------------------------------------------------
            # Usuario
            # ------------------------------------------------

            try:

                indice = partes.index(
                    "for"
                )

                if (
                    indice + 1
                    <
                    len(partes)
                ):

                    if (
                        partes[
                            indice + 1
                        ]
                        ==
                        "invalid"
                    ):

                        if (
                            indice + 2
                            <
                            len(partes)
                        ):

                            usuario = (
                                partes[
                                    indice + 2
                                ]
                            )

                    else:

                        usuario = (
                            partes[
                                indice + 1
                            ]
                        )

            except ValueError:

                pass

            # ------------------------------------------------
            # IP
            # ------------------------------------------------

            try:

                indice = partes.index(
                    "from"
                )

                if (
                    indice + 1
                    <
                    len(partes)
                ):

                    ip = (
                        partes[
                            indice + 1
                        ]
                    )

            except ValueError:

                pass

            # ------------------------------------------------
            # Hora
            # ------------------------------------------------

            hora = (
                linea[:19]
                if len(linea) >= 19
                else "--"
            )

            intentos.append(
                {
                    "usuario":
                        usuario,

                    "ip_origen":
                        ip,

                    "hora":
                        hora,

                    "servicio":
                        "SSH",
                }
            )

    except Exception:

        pass

    # --------------------------------------------------------
    # Fallback auth.log
    # --------------------------------------------------------

    if not intentos:

        try:

            resultado = subprocess.check_output(
                "grep 'Failed password' "
                "/var/log/auth.log 2>/dev/null",
                shell=True,
                text=True
            )

            ahora = time.localtime()

            mes_actual = time.strftime(
                "%b",
                ahora
            )

            dia_actual = str(
                ahora.tm_mday
            )

            for linea in resultado.splitlines():

                if (
                    mes_actual
                    not in linea
                    or
                    f" {dia_actual} "
                    not in linea
                ):

                    continue

                partes = linea.split()

                usuario = "desconocido"

                ip = "desconocida"

                try:

                    indice = partes.index(
                        "for"
                    )

                    if (
                        indice + 1
                        <
                        len(partes)
                    ):

                        if (
                            partes[
                                indice + 1
                            ]
                            ==
                            "invalid"
                        ):

                            if (
                                indice + 2
                                <
                                len(partes)
                            ):

                                usuario = (
                                    partes[
                                        indice + 2
                                    ]
                                )

                        else:

                            usuario = (
                                partes[
                                    indice + 1
                                ]
                            )

                except (
                    ValueError,
                    IndexError
                ):

                    pass

                try:

                    indice = partes.index(
                        "from"
                    )

                    if (
                        indice + 1
                        <
                        len(partes)
                    ):

                        ip = (
                            partes[
                                indice + 1
                            ]
                        )

                except (
                    ValueError,
                    IndexError
                ):

                    pass

                intentos.append(
                    {
                        "usuario":
                            usuario,

                        "ip_origen":
                            ip,

                        "hora":
                            " ".join(
                                partes[:3]
                            ),

                        "servicio":
                            "SSH",
                    }
                )

        except Exception:

            pass

    return intentos


# ============================================================
# USUARIOS DEL DÍA
# ============================================================

def obtener_usuarios_linux(
    usuarios_ocultos
):

    usuarios_hoy = []

    usuarios_activos = {}

    # --------------------------------------------------------
    # who
    # --------------------------------------------------------

    try:

        resultado_who = subprocess.check_output(
            ["who"],
            text=True
        )

        for linea in resultado_who.splitlines():

            partes = linea.split()

            if len(partes) < 2:

                continue

            usuario = partes[0]

            if usuario in usuarios_ocultos:

                continue

            terminal = partes[1]

            origen = "local"

            for parte in partes[2:]:

                if (
                    "(" in parte
                    and
                    ")" in parte
                ):

                    origen = (
                        parte
                        .replace(
                            "(",
                            ""
                        )
                        .replace(
                            ")",
                            ""
                        )
                    )

                    break

            usuarios_activos[
                (
                    usuario,
                    terminal
                )
            ] = origen

    except Exception:

        pass

    # --------------------------------------------------------
    # Logins SSH de hoy
    # --------------------------------------------------------

    try:

        resultado = subprocess.check_output(
            [
                "journalctl",
                "--since",
                "today",
                "--no-pager",
                "-o",
                "short-iso"
            ],
            text=True,
            stderr=subprocess.DEVNULL
        )

    except Exception:

        resultado = ""

    for linea in resultado.splitlines():

        if "Accepted" not in linea:

            continue

        partes = linea.split()

        usuario = "desconocido"

        ip = "local"

        metodo = "SSH"

        terminal = "-"

        # ----------------------------------------------------
        # Usuario
        # ----------------------------------------------------

        try:

            indice = partes.index(
                "for"
            )

            if (
                indice + 1
                <
                len(partes)
            ):

                usuario = (
                    partes[
                        indice + 1
                    ]
                )

        except ValueError:

            pass

        if usuario in usuarios_ocultos:

            continue

        # ----------------------------------------------------
        # IP
        # ----------------------------------------------------

        try:

            indice = partes.index(
                "from"
            )

            if (
                indice + 1
                <
                len(partes)
            ):

                ip = (
                    partes[
                        indice + 1
                    ]
                )

        except ValueError:

            pass

        # ----------------------------------------------------
        # Método
        # ----------------------------------------------------

        if "publickey" in linea:

            metodo = (
                "SSH / Public Key"
            )

        elif "password" in linea:

            metodo = (
                "SSH / Password"
            )

        # ----------------------------------------------------
        # Hora
        # ----------------------------------------------------

        hora = (
            linea[:19]
            if len(linea) >= 19
            else "--"
        )

        usuarios_hoy.append(
            {

                "usuario":
                    usuario,

                "terminal":
                    terminal,

                "host_origen":
                    ip,

                "hora_inicio":
                    hora,

                "metodo":
                    metodo,

                "activo":
                    False,

            }
        )

    # --------------------------------------------------------
    # Usuarios locales activos
    # --------------------------------------------------------

    for (
        usuario,
        terminal
    ), origen in usuarios_activos.items():

        encontrado = False

        for usuario_data in usuarios_hoy:

            if (
                usuario_data["usuario"]
                ==
                usuario
                and
                (
                    usuario_data[
                        "host_origen"
                    ]
                    ==
                    origen
                    or
                    origen == "local"
                )
            ):

                usuario_data[
                    "activo"
                ] = True

                usuario_data[
                    "terminal"
                ] = terminal

                encontrado = True

                break

        if not encontrado:

            usuarios_hoy.append(
                {

                    "usuario":
                        usuario,

                    "terminal":
                        terminal,

                    "host_origen":
                        origen,

                    "hora_inicio":
                        "Sesión local",

                    "metodo":
                        "Local",

                    "activo":
                        True,

                }
            )

    return usuarios_hoy


# ============================================================
# MÉTRICAS DEL SISTEMA
# ============================================================

def obtener_metricas_sistema(
    cfg
):

    # ========================================================
    # STORAGE
    # ========================================================

    storage = obtener_storage()

    # ========================================================
    # RED / DISK I/O
    # ========================================================

    net_io_1 = (
        psutil.net_io_counters()
    )

    disk_io_1 = (
        psutil.disk_io_counters()
    )

    time.sleep(1)

    net_io_2 = (
        psutil.net_io_counters()
    )

    disk_io_2 = (
        psutil.disk_io_counters()
    )

    mb_recibidos_sec = round(
        (
            net_io_2.bytes_recv
            -
            net_io_1.bytes_recv
        )
        /
        (1024 * 1024),
        2
    )

    mb_enviados_sec = round(
        (
            net_io_2.bytes_sent
            -
            net_io_1.bytes_sent
        )
        /
        (1024 * 1024),
        2
    )

    kb_leidos_sec = round(
        (
            disk_io_2.read_bytes
            -
            disk_io_1.read_bytes
        )
        /
        1024,
        2
    )

    kb_escritos_sec = round(
        (
            disk_io_2.write_bytes
            -
            disk_io_1.write_bytes
        )
        /
        1024,
        2
    )

    # ========================================================
    # CONEXIONES
    # ========================================================

    try:

        conexiones = (
            psutil.net_connections()
        )

        con_establecidas = len(
            [
                c
                for c in conexiones
                if c.status
                == "ESTABLISHED"
            ]
        )

        con_escucha = len(
            [
                c
                for c in conexiones
                if c.status
                == "LISTEN"
            ]
        )

    except Exception:

        con_establecidas = 0

        con_escucha = 0

    # ========================================================
    # JSON
    # ========================================================

    json_salida = {}

    visibles = (
        cfg["secciones"]
    )

    sub_visibles = (
        cfg["subsecciones"]
    )

    # ========================================================
    # SERVER INFO
    # ========================================================

    if visibles.get(
        "server_info",
        True
    ):

        json_salida[
            "server_info"
        ] = obtener_detales_servidor()

    # ========================================================
    # STORAGE
    # ========================================================

    if visibles.get(
        "storage",
        True
    ):

        json_salida[
            "storage"
        ] = {

            "mountpoint":
                storage[
                    "mountpoint"
                ],

            "device":
                storage[
                    "device"
                ],

            "filesystem":
                storage[
                    "filesystem"
                ],

            "total_gb":
                storage[
                    "total_gb"
                ],

            "used_gb":
                storage[
                    "used_gb"
                ],

            "available_gb":
                storage[
                    "available_gb"
                ],

            "percentage_used":
                storage[
                    "percentage_used"
                ],

            "performance": {

                "read_speed_kb_sec":
                    kb_leidos_sec,

                "write_speed_kb_sec":
                    kb_escritos_sec,

            },

        }

        # ----------------------------------------------------
        # PUNTOS DE MONTAJE
        # ----------------------------------------------------

        if sub_visibles.get(
            "storage_mounts",
            True
        ):

            json_salida[
                "storage"
            ][
                "mounts"
            ] = storage[
                "mounts"
            ]

    # ========================================================
    # CPU
    # ========================================================

    if visibles.get(
        "cpu",
        True
    ):

        json_salida[
            "cpu"
        ] = {

            "usage_percentage":
                psutil.cpu_percent(
                    interval=None
                ),

            "load_average":
                psutil.getloadavg(),

        }

    # ========================================================
    # RAM
    # ========================================================

    if visibles.get(
        "ram",
        True
    ):

        ram = (
            psutil.virtual_memory()
        )

        json_salida[
            "ram"
        ] = {

            "total_mb":
                round(
                    ram.total
                    /
                    (1024**2),
                    2
                ),

            "used_mb":
                round(
                    ram.used
                    /
                    (1024**2),
                    2
                ),

            "available_mb":
                round(
                    ram.available
                    /
                    (1024**2),
                    2
                ),

            "percentage_used":
                ram.percent,

        }

    # ========================================================
    # SWAP
    # ========================================================

    if visibles.get(
        "swap",
        True
    ):

        swap = (
            psutil.swap_memory()
        )

        json_salida[
            "swap"
        ] = {

            "total_mb":
                round(
                    swap.total
                    /
                    (1024**2),
                    2
                ),

            "used_mb":
                round(
                    swap.used
                    /
                    (1024**2),
                    2
                ),

            "free_mb":
                round(
                    swap.free
                    /
                    (1024**2),
                    2
                ),

            "percentage_used":
                swap.percent,

        }

    # ========================================================
    # NETWORK
    # ========================================================

    if visibles.get(
        "network",
        True
    ):

        json_salida[
            "network"
        ] = {

            "bytes_received_total":
                net_io_2.bytes_recv,

            "bytes_sent_total":
                net_io_2.bytes_sent,

            "speed_download_mb_sec":
                mb_recibidos_sec,

            "speed_upload_mb_sec":
                mb_enviados_sec,

            "active_connections": {

                "established":
                    con_establecidas,

                "listening":
                    con_escucha,

            },

        }

    # ========================================================
    # SECURITY
    # ========================================================

    if visibles.get(
        "security_metrics",
        True
    ):

        intentos_fallidos = (
            obtener_intentos_fallidos()
        )

        json_salida[
            "security_metrics"
        ] = {

            "failed_login_attempts_total":
                len(
                    intentos_fallidos
                ),

            "failed_login_attempts_today":
                intentos_fallidos,

        }

    # ========================================================
    # USERS
    # ========================================================

    if visibles.get(
        "users_online",
        True
    ):

        usuarios_hoy = (
            obtener_usuarios_linux(
                cfg[
                    "usuarios_ocultos"
                ]
            )
        )

        sesiones_activas = [
            usuario
            for usuario in usuarios_hoy
            if usuario.get(
                "activo"
            ) is True
        ]

        json_salida[
            "users_online"
        ] = {

            "total_sessions":
                len(
                    sesiones_activas
                ),

            "users_today_total":
                len(
                    usuarios_hoy
                ),

            "users_today":
                usuarios_hoy,

            "active_users":
                sesiones_activas,

        }

    # ========================================================
    # PROCESSES
    # ========================================================

    if visibles.get(
        "processes",
        True
    ):

        procesos_especificos = []

        todos_los_procesos = []

        for proc in psutil.process_iter(
            [
                "pid",
                "name",
                "cpu_percent",
                "memory_info"
            ]
        ):

            try:

                p_info = {

                    "pid":
                        proc.info[
                            "pid"
                        ],

                    "name":
                        proc.info[
                            "name"
                        ],

                    "cpu_percentage":
                        proc.info[
                            "cpu_percent"
                        ]
                        or 0.0,

                    "ram_mb":
                        round(
                            proc.info[
                                "memory_info"
                            ].rss
                            /
                            (
                                1024 *
                                1024
                            ),
                            2
                        )
                        if proc.info[
                            "memory_info"
                        ]
                        else 0.0,

                }

                todos_los_procesos.append(
                    p_info
                )

                if (
                    p_info["name"]
                    in cfg["procesos"]
                ):

                    procesos_especificos.append(
                        p_info
                    )

            except (
                psutil.NoSuchProcess,
                psutil.AccessDenied
            ):

                pass

        json_salida[
            "processes"
        ] = {}

        if sub_visibles.get(
            "monitored_services",
            True
        ):

            json_salida[
                "processes"
            ][
                "monitored_services"
            ] = (
                procesos_especificos
            )

        if sub_visibles.get(
            "top_3_consumers",
            True
        ):

            json_salida[
                "processes"
            ][
                "top_3_consumers"
            ] = sorted(
                todos_los_procesos,
                key=lambda x:
                    x["cpu_percentage"],
                reverse=True
            )[:3]

    return json_salida


# ============================================================
# ESCRIBIR JSON AL LOG
# ============================================================

def guardar_json_log(
    datos
):

    try:

        registro = dict(
            datos
        )

        registro[
            "timestamp_log"
        ] = time.strftime(
            "%Y-%m-%d %H:%M:%S",
            time.localtime()
        )

        linea_json = json.dumps(
            registro,
            ensure_ascii=False,
            separators=(
                ",",
                ":"
            )
        )

        logger.info(
            linea_json
        )

    except Exception as error:

        logger.error(
            json.dumps(
                {

                    "timestamp_log":
                        time.strftime(
                            "%Y-%m-%d %H:%M:%S"
                        ),

                    "error":
                        "No se pudo guardar "
                        "la métrica en el log",

                    "detalle":
                        str(error),

                },
                ensure_ascii=False
            )
        )


# ============================================================
# API JSON
# ============================================================

@app.get("/v1/status")
def obtener_estado():

    global cache_datos

    global ultima_actualizacion

    tiempo_actual = time.time()

    cfg = (
        cargar_configuracion()
    )

    refresco_limite = (
        cfg["refresco"]
    )

    # ========================================================
    # CACHE EXPIRADA
    # ========================================================

    if (
        not cache_datos
        or
        (
            tiempo_actual
            -
            ultima_actualizacion
        )
        >=
        refresco_limite
    ):

        nuevas_metricas = (
            obtener_metricas_sistema(
                cfg
            )
        )

        cache_datos = (
            nuevas_metricas
        )

        ultima_actualizacion = (
            tiempo_actual
        )

        guardar_json_log(
            nuevas_metricas
        )

    # ========================================================
    # DATOS DESDE CACHE
    # ========================================================

    tiempo_desde_actualizacion = (
        tiempo_actual
        -
        ultima_actualizacion
    )

    segundos_restantes = max(
        0,
        round(
            refresco_limite
            -
            tiempo_desde_actualizacion
        )
    )

    respuesta = dict(
        cache_datos
    )

    if (
        tiempo_desde_actualizacion
        >=
        refresco_limite
    ):

        respuesta[
            "origen_dato"
        ] = (
            "Caché pendiente de actualización"
        )

    else:

        respuesta[
            "origen_dato"
        ] = (
            "Entregado desde Caché "
            f"(Próximo refresco en "
            f"{segundos_restantes}s)"
        )

    return respuesta


# ============================================================
# DASHBOARD
# ============================================================

@app.get(
    "/v1/dash",
    response_class=HTMLResponse
)
def dashboard():

    return """
<!DOCTYPE html>

<html lang="es">

<head>

<meta charset="UTF-8">

<meta
    name="viewport"
    content="width=device-width, initial-scale=1.0"
>

<title>
    Server Server Dashboard
</title>

<script
    src="https://cdn.jsdelivr.net/npm/chart.js">
</script>

<style>

* {
    box-sizing: border-box;
}

body {

    margin: 0;

    background: #0f172a;

    color: #e2e8f0;

    font-family:
        Arial,
        Helvetica,
        sans-serif;
}

header {

    background: #1e293b;

    padding: 20px 30px;

    border-bottom:
        1px solid #334155;

    position: sticky;

    top: 0;

    z-index: 100;
}

header h1 {

    margin: 0;

    font-size: 26px;
}

#estado {

    margin-top: 8px;

    color: #22c55e;

    font-size: 14px;
}

main {

    padding: 20px;

    max-width: 1800px;

    margin: auto;
}

.section-title {

    margin-top: 30px;

    margin-bottom: 15px;

    font-size: 21px;

    color: #f8fafc;

    border-left:
        4px solid #38bdf8;

    padding-left: 10px;
}

.grid {

    display: grid;

    grid-template-columns:
        repeat(
            auto-fit,
            minmax(300px, 1fr)
        );

    gap: 18px;
}

.card {

    background: #1e293b;

    border:
        1px solid #334155;

    border-radius: 12px;

    padding: 18px;

    box-shadow:
        0 5px 20px
        rgba(0,0,0,.20);
}

.card h2 {

    margin-top: 0;

    font-size: 18px;

    color: #f8fafc;
}

.big-value {

    font-size: 34px;

    font-weight: bold;

    color: #38bdf8;

    margin: 10px 0;
}

.metric {

    display: flex;

    justify-content:
        space-between;

    padding: 8px 0;

    border-bottom:
        1px solid #334155;

    gap: 15px;
}

.metric:last-child {

    border-bottom: none;
}

.metric-name {

    color: #94a3b8;
}

.metric-value {

    color: #f8fafc;

    text-align: right;

    font-weight: bold;
}

.chart-container {

    position: relative;

    height: 250px;
}

table {

    width: 100%;

    border-collapse:
        collapse;

    font-size: 14px;
}

th {

    text-align: left;

    background: #0f172a;

    color: #94a3b8;

    padding: 10px;

}

td {

    padding: 9px 10px;

    border-top:
        1px solid #334155;

}

tr:hover {

    background: #263449;
}

.online {

    color: #22c55e;
}

.danger {

    color: #ef4444;
}

.status-badge {

    display: inline-block;

    padding: 5px 10px;

    border-radius: 20px;

    background: #14532d;

    color: #86efac;

    font-size: 12px;
}

.storage-mount {

    color: #38bdf8;

    font-weight: bold;
}

.storage-device {

    color: #cbd5e1;

}

.storage-usage {

    font-weight: bold;

}

@media(max-width:700px) {

    main {

        padding: 10px;

    }

    .grid {

        grid-template-columns: 1fr;

    }

}

</style>

</head>

<body>

<header>

<h1>
    🖥️ Server Server Dashboard
</h1>

<div id="estado">

<span class="status-badge">
    Conectando...
</span>

</div>

</header>

<main>


<!-- SERVER -->

<div class="section-title">
    🖥️ Información del servidor
</div>

<div class="grid">

<div class="card">

<div class="metric">

<span class="metric-name">
Hostname
</span>

<span
    class="metric-value"
    id="hostname"
>
--
</span>

</div>

<div class="metric">

<span class="metric-name">
FQDN
</span>

<span
    class="metric-value"
    id="fqdn"
>
--
</span>

</div>

<div class="metric">

<span class="metric-name">
Sistema operativo
</span>

<span
    class="metric-value"
    id="os"
>
--
</span>

</div>

<div class="metric">

<span class="metric-name">
Kernel
</span>

<span
    class="metric-value"
    id="kernel"
>
--
</span>

</div>

<div class="metric">

<span class="metric-name">
Arquitectura
</span>

<span
    class="metric-value"
    id="architecture"
>
--
</span>

</div>

<div class="metric">

<span class="metric-name">
Python
</span>

<span
    class="metric-value"
    id="python"
>
--
</span>

</div>

<div class="metric">

<span class="metric-name">
Uptime
</span>

<span
    class="metric-value"
    id="uptime"
>
--
</span>

</div>

<div class="metric">

<span class="metric-name">
Boot
</span>

<span
    class="metric-value"
    id="boot"
>
--
</span>

</div>

</div>

</div>


<!-- RECURSOS -->

<div class="section-title">
    📊 Recursos del sistema
</div>

<div class="grid">


<div class="card">

<h2>CPU</h2>

<div
    class="big-value"
    id="cpuValor"
>
-- %
</div>

<div class="metric">

<span class="metric-name">
Load average
</span>

<span
    class="metric-value"
    id="loadAverage"
>
--
</span>

</div>

</div>


<div class="card">

<h2>RAM</h2>

<div
    class="big-value"
    id="ramValor"
>
-- %
</div>

<div class="metric">

<span class="metric-name">
Total
</span>

<span
    class="metric-value"
    id="ramTotal"
>
--
</span>

</div>

<div class="metric">

<span class="metric-name">
Usada
</span>

<span
    class="metric-value"
    id="ramUsed"
>
--
</span>

</div>

<div class="metric">

<span class="metric-name">
Disponible
</span>

<span
    class="metric-value"
    id="ramAvailable"
>
--
</span>

</div>

</div>


<!-- STORAGE -->

<div class="card">

<h2>💾 Storage /</h2>

<div
    class="big-value"
    id="diskValor"
>
-- %
</div>

<div class="metric">

<span class="metric-name">
Punto de montaje
</span>

<span
    class="metric-value"
    id="diskMountpoint"
>
--
</span>

</div>

<div class="metric">

<span class="metric-name">
Dispositivo
</span>

<span
    class="metric-value"
    id="diskDevice"
>
--
</span>

</div>

<div class="metric">

<span class="metric-name">
Filesystem
</span>

<span
    class="metric-value"
    id="diskFilesystem"
>
--
</span>

</div>

<div class="metric">

<span class="metric-name">
Total
</span>

<span
    class="metric-value"
    id="diskTotal"
>
--
</span>

</div>

<div class="metric">

<span class="metric-name">
Usado
</span>

<span
    class="metric-value"
    id="diskUsed"
>
--
</span>

</div>

<div class="metric">

<span class="metric-name">
Disponible
</span>

<span
    class="metric-value"
    id="diskAvailable"
>
--
</span>

</div>

</div>


<div class="card">

<h2>🔄 Swap</h2>

<div
    class="big-value"
    id="swapValor"
>
-- %
</div>

<div class="metric">

<span class="metric-name">
Total
</span>

<span
    class="metric-value"
    id="swapTotal"
>
--
</span>

</div>

<div class="metric">

<span class="metric-name">
Usada
</span>

<span
    class="metric-value"
    id="swapUsed"
>
--
</span>

</div>

<div class="metric">

<span class="metric-name">
Libre
</span>

<span
    class="metric-value"
    id="swapFree"
>
--
</span>

</div>

</div>

</div>


<!-- PUNTOS DE MONTAJE -->

<div class="section-title">
    💽 Puntos de montaje
</div>

<div class="grid">

<div class="card">

<h2>
    Almacenamientos detectados
</h2>

<div style="overflow-x:auto;">

<table>

<thead>

<tr>

<th>Montaje</th>

<th>Dispositivo</th>

<th>Filesystem</th>

<th>Total</th>

<th>Usado</th>

<th>Disponible</th>

<th>Uso</th>

</tr>

</thead>

<tbody
    id="storageMountsTable"
>
</tbody>

</table>

</div>

</div>

</div>


<!-- GRÁFICAS -->

<div class="section-title">
    📈 Monitorización en tiempo real
</div>

<div class="grid">

<div class="card">

<h2>CPU</h2>

<div class="chart-container">

<canvas id="cpuChart"></canvas>

</div>

</div>


<div class="card">

<h2>RAM</h2>

<div class="chart-container">

<canvas id="ramChart"></canvas>

</div>

</div>


<div class="card">

<h2>Network</h2>

<div class="chart-container">

<canvas id="networkChart"></canvas>

</div>

</div>


<div class="card">

<h2>Disk I/O</h2>

<div class="chart-container">

<canvas id="diskIOChart"></canvas>

</div>

</div>


<div class="card">

<h2>Storage /</h2>

<div class="chart-container">

<canvas id="storageChart"></canvas>

</div>

</div>

</div>


<!-- NETWORK -->

<div class="section-title">
    🌐 Red
</div>

<div class="grid">

<div class="card">

<h2>Tráfico</h2>

<div class="metric">

<span class="metric-name">
Download
</span>

<span
    class="metric-value"
    id="download"
>
--
</span>

</div>

<div class="metric">

<span class="metric-name">
Upload
</span>

<span
    class="metric-value"
    id="upload"
>
--
</span>

</div>

<div class="metric">

<span class="metric-name">
Bytes recibidos
</span>

<span
    class="metric-value"
    id="bytesReceived"
>
--
</span>

</div>

<div class="metric">

<span class="metric-name">
Bytes enviados
</span>

<span
    class="metric-value"
    id="bytesSent"
>
--
</span>

</div>

</div>


<div class="card">

<h2>🔌 Conexiones</h2>

<div
    class="big-value"
    id="established"
>
--
</div>

<div class="metric">

<span class="metric-name">
ESTABLISHED
</span>

<span
    class="metric-value"
    id="established2"
>
--
</span>

</div>

<div class="metric">

<span class="metric-name">
LISTEN
</span>

<span
    class="metric-value"
    id="listening"
>
--
</span>

</div>

</div>

</div>


<!-- SEGURIDAD -->

<div class="section-title">
    🔐 Intentos de acceso fallidos — Hoy
</div>

<div class="grid">

<div class="card">

<h2>
Intentos fallidos
</h2>

<div
    class="big-value danger"
    id="failedLogins"
>
0
</div>

<div style="overflow-x:auto;">

<table>

<thead>

<tr>

<th>Hora</th>

<th>Usuario</th>

<th>IP origen</th>

<th>Servicio</th>

</tr>

</thead>

<tbody
    id="failedLoginsTable"
>
</tbody>

</table>

</div>

</div>

</div>


<!-- USUARIOS -->

<div class="section-title">
    👥 Usuarios del día
</div>

<div class="grid">

<div class="card">

<h2>

Usuarios detectados hoy:
<span id="usersTodayTotal">
0
</span>

</h2>

<div style="overflow-x:auto;">

<table>

<thead>

<tr>

<th>Usuario</th>

<th>Hora inicio</th>

<th>Terminal</th>

<th>Origen</th>

<th>Método</th>

<th>Estado</th>

</tr>

</thead>

<tbody
    id="usersTable"
>
</tbody>

</table>

</div>

</div>

</div>


<!-- PROCESOS -->

<div class="section-title">
    ⚙️ Procesos
</div>

<div class="grid">

<div class="card">

<h2>
Servicios monitorizados
</h2>

<div style="overflow-x:auto;">

<table>

<thead>

<tr>

<th>PID</th>

<th>Proceso</th>

<th>CPU %</th>

<th>RAM MB</th>

</tr>

</thead>

<tbody
    id="servicesTable"
>
</tbody>

</table>

</div>

</div>


<div class="card">

<h2>
Top 3 consumidores CPU
</h2>

<div style="overflow-x:auto;">

<table>

<thead>

<tr>

<th>PID</th>

<th>Proceso</th>

<th>CPU %</th>

<th>RAM MB</th>

</tr>

</thead>

<tbody
    id="topProcessesTable"
>
</tbody>

</table>

</div>

</div>

</div>

</main>


<script>

// ============================================================
// CONFIGURACIÓN
// ============================================================

const MAX_DATOS = 30;

const labels = [];

const cpuData = [];

const ramData = [];

const downloadData = [];

const uploadData = [];

const readData = [];

const writeData = [];


// ============================================================
// LIMITAR DATOS
// ============================================================

function limitarDatos(array) {

    while (
        array.length > MAX_DATOS
    ) {

        array.shift();

    }

}


// ============================================================
// CREAR GRÁFICA
// ============================================================

function crearChart(
    id,
    datasets,
    yTitle = ""
) {

    return new Chart(

        document.getElementById(id),

        {

            type: "line",

            data: {

                labels: labels,

                datasets: datasets

            },

            options: {

                responsive: true,

                maintainAspectRatio: false,

                animation: false,

                interaction: {

                    intersect: false,

                    mode: "index"

                },

                scales: {

                    y: {

                        beginAtZero: true,

                        title: {

                            display: true,

                            text: yTitle

                        }

                    }

                }

            }

        }

    );

}


// ============================================================
// GRÁFICAS
// ============================================================

const cpuChart = crearChart(

    "cpuChart",

    [

        {

            label: "CPU %",

            data: cpuData,

            borderColor: "#38bdf8",

            backgroundColor:
                "#38bdf833",

            fill: true,

            tension: .3

        }

    ],

    "%"

);


const ramChart = crearChart(

    "ramChart",

    [

        {

            label: "RAM %",

            data: ramData,

            borderColor: "#a78bfa",

            backgroundColor:
                "#a78bfa33",

            fill: true,

            tension: .3

        }

    ],

    "%"

);


const networkChart = crearChart(

    "networkChart",

    [

        {

            label:
                "Download MB/s",

            data:
                downloadData,

            borderColor:
                "#22c55e",

            tension: .3

        },

        {

            label:
                "Upload MB/s",

            data:
                uploadData,

            borderColor:
                "#f59e0b",

            tension: .3

        }

    ],

    "MB/s"

);


const diskIOChart = crearChart(

    "diskIOChart",

    [

        {

            label:
                "Read KB/s",

            data:
                readData,

            borderColor:
                "#06b6d4",

            tension: .3

        },

        {

            label:
                "Write KB/s",

            data:
                writeData,

            borderColor:
                "#ef4444",

            tension: .3

        }

    ],

    "KB/s"

);


const storageChart = new Chart(

    document.getElementById(
        "storageChart"
    ),

    {

        type: "doughnut",

        data: {

            labels: [
                "Usado",
                "Disponible"
            ],

            datasets: [

                {

                    data: [
                        0,
                        100
                    ],

                    backgroundColor: [

                        "#ef4444",

                        "#22c55e"

                    ]

                }

            ]

        },

        options: {

            responsive: true,

            maintainAspectRatio: false

        }

    }

);


// ============================================================
// VALOR
// ============================================================

function valor(
    id,
    value
) {

    const elemento =
        document.getElementById(id);

    if (elemento) {

        elemento.textContent =
            value ?? "--";

    }

}


// ============================================================
// BYTES
// ============================================================

function formatoBytes(
    bytes
) {

    if (
        bytes === null ||
        bytes === undefined
    ) {

        return "--";

    }

    if (bytes < 1024) {

        return (
            bytes.toFixed(0)
            +
            " B"
        );

    }

    if (
        bytes <
        1024 * 1024
    ) {

        return (
            (
                bytes / 1024
            ).toFixed(2)
            +
            " KB"
        );

    }

    if (
        bytes <
        1024 *
        1024 *
        1024
    ) {

        return (
            (
                bytes /
                (
                    1024 *
                    1024
                )
            ).toFixed(2)
            +
            " MB"
        );

    }

    return (
        (
            bytes /
            (
                1024 *
                1024 *
                1024
            )
        ).toFixed(2)
        +
        " GB"
    );

}


// ============================================================
// STORAGE / PUNTOS DE MONTAJE
// ============================================================

function actualizarStorageMontajes(
    datos
) {

    const tabla =
        document.getElementById(
            "storageMountsTable"
        );

    if (!tabla) {

        return;

    }

    tabla.innerHTML = "";

    const montajes =
        datos.storage?.mounts || [];

    montajes.forEach(
        montaje => {

            const fila =
                document.createElement(
                    "tr"
                );

            const porcentaje =
                Number(
                    montaje.percentage_used
                    ?? 0
                );

            let colorUso =
                "#22c55e";

            if (
                porcentaje >= 90
            ) {

                colorUso =
                    "#ef4444";

            }
            else if (
                porcentaje >= 75
            ) {

                colorUso =
                    "#f59e0b";

            }

            fila.innerHTML = `

                <td>

                    <span
                        class="storage-mount"
                    >

                        ${montaje.mountpoint ?? "--"}

                    </span>

                </td>

                <td>

                    <span
                        class="storage-device"
                    >

                        ${montaje.device ?? "--"}

                    </span>

                </td>

                <td>

                    ${montaje.filesystem ?? "--"}

                </td>

                <td>

                    ${montaje.total_gb ?? 0}
                    GB

                </td>

                <td>

                    ${montaje.used_gb ?? 0}
                    GB

                </td>

                <td>

                    ${montaje.available_gb ?? 0}
                    GB

                </td>

                <td>

                    <span
                        class="storage-usage"
                        style="
                            color:${colorUso};
                        "
                    >

                        ${porcentaje.toFixed(1)}%

                    </span>

                </td>

            `;

            tabla.appendChild(
                fila
            );

        }
    );

    if (
        montajes.length === 0
    ) {

        const fila =
            document.createElement(
                "tr"
            );

        fila.innerHTML = `

            <td
                colspan="7"
                style="
                    text-align:center;
                    color:#94a3b8;
                "
            >

                No se encontraron
                puntos de montaje.

            </td>

        `;

        tabla.appendChild(
            fila
        );

    }

}


// ============================================================
// USUARIOS
// ============================================================

function actualizarUsuarios(
    datos
) {

    const tabla =
        document.getElementById(
            "usersTable"
        );

    tabla.innerHTML = "";

    const usuarios =
        datos.users_online
        ?.users_today || [];

    valor(
        "usersTodayTotal",
        usuarios.length
    );

    usuarios.forEach(
        usuario => {

            const fila =
                document.createElement(
                    "tr"
                );

            const estado =
                usuario.activo

                ?

                '<span class="online">● Conectado</span>'

                :

                '<span style="color:#94a3b8">○ Cerrado</span>';

            fila.innerHTML = `

                <td>

                    <strong>

                        ${usuario.usuario ?? "--"}

                    </strong>

                </td>

                <td>

                    ${usuario.hora_inicio ?? "--"}

                </td>

                <td>

                    ${usuario.terminal ?? "--"}

                </td>

                <td>

                    ${usuario.host_origen ?? "--"}

                </td>

                <td>

                    ${usuario.metodo ?? "--"}

                </td>

                <td>

                    ${estado}

                </td>

            `;

            tabla.appendChild(
                fila
            );

        }
    );

}


// ============================================================
// INTENTOS FALLIDOS
// ============================================================

function actualizarIntentosFallidos(
    datos
) {

    const tabla =
        document.getElementById(
            "failedLoginsTable"
        );

    tabla.innerHTML = "";

    const intentos =
        datos.security_metrics
        ?.failed_login_attempts_today
        || [];

    valor(
        "failedLogins",
        intentos.length
    );

    intentos.forEach(
        intento => {

            const fila =
                document.createElement(
                    "tr"
                );

            fila.innerHTML = `

                <td>

                    ${intento.hora ?? "--"}

                </td>

                <td>

                    <strong>

                        ${intento.usuario ?? "--"}

                    </strong>

                </td>

                <td>

                    ${intento.ip_origen ?? "--"}

                </td>

                <td>

                    ${intento.servicio ?? "--"}

                </td>

            `;

            tabla.appendChild(
                fila
            );

        }
    );

}


// ============================================================
// PROCESOS
// ============================================================

function actualizarProcesos(
    datos
) {

    const servicesTable =
        document.getElementById(
            "servicesTable"
        );

    const topTable =
        document.getElementById(
            "topProcessesTable"
        );

    servicesTable.innerHTML =
        "";

    topTable.innerHTML =
        "";

    const servicios =
        datos.processes
        ?.monitored_services
        || [];

    servicios.forEach(
        proc => {

            const fila =
                document.createElement(
                    "tr"
                );

            fila.innerHTML = `

                <td>

                    ${proc.pid ?? "--"}

                </td>

                <td>

                    ${proc.name ?? "--"}

                </td>

                <td>

                    ${Number(
                        proc.cpu_percentage
                        ?? 0
                    ).toFixed(2)}

                </td>

                <td>

                    ${Number(
                        proc.ram_mb
                        ?? 0
                    ).toFixed(2)}

                </td>

            `;

            servicesTable.appendChild(
                fila
            );

        }
    );

    const top =
        datos.processes
        ?.top_3_consumers
        || [];

    top.forEach(
        proc => {

            const fila =
                document.createElement(
                    "tr"
                );

            fila.innerHTML = `

                <td>

                    ${proc.pid ?? "--"}

                </td>

                <td>

                    ${proc.name ?? "--"}

                </td>

                <td>

                    ${Number(
                        proc.cpu_percentage
                        ?? 0
                    ).toFixed(2)}

                </td>

                <td>

                    ${Number(
                        proc.ram_mb
                        ?? 0
                    ).toFixed(2)}

                </td>

            `;

            topTable.appendChild(
                fila
            );

        }
    );

}


// ============================================================
// ACTUALIZAR DASHBOARD
// ============================================================

async function actualizarDashboard() {

    try {

        const respuesta =
            await fetch(
                "/v1/status",
                {
                    cache:
                        "no-store"
                }
            );

        if (!respuesta.ok) {

            throw new Error(
                "HTTP "
                +
                respuesta.status
            );

        }

        const datos =
            await respuesta.json();

        const ahora =
            new Date()
            .toLocaleTimeString();

        // ----------------------------------------------------
        // SERVER
        // ----------------------------------------------------

        const server =
            datos.server_info;

        if (server) {

            valor(
                "hostname",
                server.hostname
            );

            valor(
                "fqdn",
                server.fqdn
            );

            valor(
                "os",
                server.os_distribution
            );

            valor(
                "kernel",
                server.kernel_version
            );

            valor(
                "architecture",
                server.architecture
            );

            valor(
                "python",
                server.python_version
            );

            valor(
                "uptime",
                server.uptime
            );

            valor(
                "boot",
                server.boot_time
            );

        }

        // ----------------------------------------------------
        // CPU
        // ----------------------------------------------------

        const cpu =
            datos.cpu
            ?.usage_percentage
            ?? 0;

        valor(
            "cpuValor",
            Number(cpu).toFixed(1)
            + " %"
        );

        const load =
            datos.cpu
            ?.load_average;

        valor(
            "loadAverage",

            load

                ?

                load
                .map(
                    x =>
                        Number(x)
                        .toFixed(2)
                )
                .join(" / ")

                :

                "--"
        );

        // ----------------------------------------------------
        // RAM
        // ----------------------------------------------------

        const ram =
            datos.ram;

        if (ram) {

            valor(
                "ramValor",
                Number(
                    ram.percentage_used
                ).toFixed(1)
                + " %"
            );

            valor(
                "ramTotal",
                ram.total_mb
                + " MB"
            );

            valor(
                "ramUsed",
                ram.used_mb
                + " MB"
            );

            valor(
                "ramAvailable",
                ram.available_mb
                + " MB"
            );

        }

        // ----------------------------------------------------
        // STORAGE
        // ----------------------------------------------------

        const storage =
            datos.storage;

        if (storage) {

            const porcentaje =
                Number(
                    storage.percentage_used
                    ?? 0
                );

            valor(
                "diskValor",
                porcentaje.toFixed(1)
                + " %"
            );

            valor(
                "diskMountpoint",
                storage.mountpoint
            );

            valor(
                "diskDevice",
                storage.device
            );

            valor(
                "diskFilesystem",
                storage.filesystem
            );

            valor(
                "diskTotal",
                storage.total_gb
                + " GB"
            );

            valor(
                "diskUsed",
                storage.used_gb
                + " GB"
            );

            valor(
                "diskAvailable",
                storage.available_gb
                + " GB"
            );

            storageChart
                .data
                .datasets[0]
                .data = [

                    porcentaje,

                    Math.max(
                        0,
                        100 - porcentaje
                    )

                ];

        }

        // ----------------------------------------------------
        // PUNTOS DE MONTAJE
        // ----------------------------------------------------

        actualizarStorageMontajes(
            datos
        );

        // ----------------------------------------------------
        // SWAP
        // ----------------------------------------------------

        const swap =
            datos.swap;

        if (swap) {

            valor(
                "swapValor",
                Number(
                    swap.percentage_used
                ).toFixed(1)
                + " %"
            );

            valor(
                "swapTotal",
                swap.total_mb
                + " MB"
            );

            valor(
                "swapUsed",
                swap.used_mb
                + " MB"
            );

            valor(
                "swapFree",
                swap.free_mb
                + " MB"
            );

        }

        // ----------------------------------------------------
        // NETWORK
        // ----------------------------------------------------

        const network =
            datos.network;

        if (network) {

            valor(
                "download",
                network
                    .speed_download_mb_sec
                + " MB/s"
            );

            valor(
                "upload",
                network
                    .speed_upload_mb_sec
                + " MB/s"
            );

            valor(
                "bytesReceived",
                formatoBytes(
                    network
                        .bytes_received_total
                )
            );

            valor(
                "bytesSent",
                formatoBytes(
                    network
                        .bytes_sent_total
                )
            );

            const conexiones =
                network
                    .active_connections;

            if (conexiones) {

                valor(
                    "established",
                    conexiones.established
                );

                valor(
                    "established2",
                    conexiones.established
                );

                valor(
                    "listening",
                    conexiones.listening
                );

            }

        }

        // ----------------------------------------------------
        // GRÁFICAS
        // ----------------------------------------------------

        labels.push(
            ahora
        );

        cpuData.push(
            cpu
        );

        ramData.push(
            datos.ram
                ?.percentage_used
                ?? 0
        );

        downloadData.push(
            datos.network
                ?.speed_download_mb_sec
                ?? 0
        );

        uploadData.push(
            datos.network
                ?.speed_upload_mb_sec
                ?? 0
        );

        readData.push(
            datos.storage
                ?.performance
                ?.read_speed_kb_sec
                ?? 0
        );

        writeData.push(
            datos.storage
                ?.performance
                ?.write_speed_kb_sec
                ?? 0
        );

        limitarDatos(
            labels
        );

        limitarDatos(
            cpuData
        );

        limitarDatos(
            ramData
        );

        limitarDatos(
            downloadData
        );

        limitarDatos(
            uploadData
        );

        limitarDatos(
            readData
        );

        limitarDatos(
            writeData
        );

        cpuChart.update();

        ramChart.update();

        networkChart.update();

        diskIOChart.update();

        storageChart.update();

        // ----------------------------------------------------
        // USUARIOS
        // ----------------------------------------------------

        actualizarUsuarios(
            datos
        );

        // ----------------------------------------------------
        // SEGURIDAD
        // ----------------------------------------------------

        actualizarIntentosFallidos(
            datos
        );

        // ----------------------------------------------------
        // PROCESOS
        // ----------------------------------------------------

        actualizarProcesos(
            datos
        );

        // ----------------------------------------------------
        // ESTADO
        // ----------------------------------------------------

        document.getElementById(
            "estado"
        ).innerHTML = `

            <span class="status-badge">

                ● EN LÍNEA

            </span>

            Última actualización:
            ${ahora}

            |

            ${datos.origen_dato ?? "API"}

        `;

    }
    catch (error) {

        console.error(
            "Error obteniendo métricas:",
            error
        );

        document.getElementById(
            "estado"
        ).innerHTML = `

            <span
                class="status-badge"
                style="
                    background:#7f1d1d;
                    color:#fecaca;
                "
            >

                ● SIN CONEXIÓN

            </span>

            Error consultando
            /v1/status

        `;

    }

}


// ============================================================
// INICIO
// ============================================================

actualizarDashboard();


// ============================================================
// ACTUALIZACIÓN DEL DASHBOARD
// ============================================================

setInterval(
    actualizarDashboard,
    2000
);

</script>

</body>

</html>
"""


# ============================================================
# ARRANQUE
# ============================================================

if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8080,
        log_level="info",
        reload=False
    )
