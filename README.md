# Servicio de Streaming

Este proyecto consiste en el desarrollo de una plataforma de streaming que permite a los usuarios registrarse, autenticar su cuenta y acceder a un catálogo de contenidos audiovisuales (películas, series y documentales).

---

## Tabla de contenido
- [Estructura del proyecto](#estructura-del-proyecto)
- [Características principales](#características-principales)
- [Requisitos](#requisitos)
- [Instalación](#instalación)
- [Ejecución](#ejecución)
- [Migraciones de base de datos](#migraciones-de-base-de-datos)
- [Licencia](#licencia)
- [Autores](#autores)

---

## Estructura del proyecto

La organización del proyecto sigue una estructura modular que facilita la escalabilidad y el mantenimiento del código:  

```plaintext
APP-SERVICES/
│── .env                         # Variables de entorno (configuración sensible)
│── .env.example.txt             # Ejemplo de configuración para otros devs
│── .gitignore                   # Archivos/carpetas que no deben subirse a git
│── alembic.ini                  # Configuración de Alembic para migraciones DB
│── docker-compose.yml           # Orquestador de contenedores (servicios DB, app)
│── Dockerfile                   # Imagen de la app para Docker
│── README.md                    # Documentación principal del proyecto
│── requirements.txt             # Dependencias de Python
│
├── app/                         # Código principal de la aplicación
│   │── main.py                  # Punto de entrada de la app FastAPI
│   │── cli.py                   # Comandos de línea (scripts auxiliares)
│   │
│   ├── api/                     # Rutas de la API (endpoints)
│   │   ├── v1/                  # Versionamiento de la API (v1 actual)
│   │   │   ├── auth.py          # Autenticación y login
│   │   │   ├── contents.py      # Rutas para contenidos (series, películas)
│   │   │   ├── episodes.py      # Rutas para episodios
│   │   │   ├── payments.py      # Rutas para pagos
│   │   │   ├── plans.py         # Rutas para planes de suscripción
│   │   │   ├── playbacks.py     # Rutas para reproducciones
│   │   │   ├── profiles.py      # Rutas para perfiles de usuario
│   │   │   ├── subscriptions.py # Rutas para suscripciones
│   │   │   ├── users.py         # Rutas para usuarios
│   │   │   ├── watchlist.py     # Rutas para listas de seguimiento
│   │   │   └── __init__.py
│   │   └── deps.py              # Dependencias comunes para los endpoints
│   │
│   ├── core/                    # Configuración central y utilidades globales
│   │   ├── config.py            # Variables de configuración (env vars)
│   │   ├── database.py          # Conexión con la base de datos
│   │   ├── security.py          # Seguridad (JWT, hashing, permisos)
│   │   └── __init__.py
│   │
│   ├── models/                  # Modelos de SQLAlchemy (tablas de la DB)
│   │   ├── auditmixin.py        # Campos de auditoría (created_at, updated_at, etc.)
│   │   ├── content.py
│   │   ├── episode.py
│   │   ├── payment.py
│   │   ├── plan.py
│   │   ├── playback.py
│   │   ├── profile.py
│   │   ├── subscription.py
│   │   ├── user.py
│   │   ├── watchlist.py
│   │   └── __init__.py
│   │
│   ├── schemas/                 # Validaciones y serialización (Pydantic)
│   │   ├── base.py              # Esquemas base reutilizables
│   │   ├── content.py
│   │   ├── episode.py
│   │   ├── payment.py
│   │   ├── plan.py
│   │   ├── playback.py
│   │   ├── profile.py
│   │   ├── subscriptions.py
│   │   ├── token.py             # Respuesta del login con JWT
│   │   ├── user.py
│   │   ├── watchlist.py
│   │   └── __init__.py
│
├── migration/                   # Migraciones de base de datos (Alembic)
│   ├── versions/                # Archivos de migración generados
│   ├── env.py                   # Config principal de Alembic
│   ├── README
│   └── script.py.mako
│
└── scripts/                     # Scripts auxiliares
    ├── plantuml.txt             # Diagrama de arquitectura (PlantUML)
    └── seed_admin.py            # Script para crear usuario admin inicial
```

## Características principales

- **API REST con FastAPI**  
  Endpoints organizados por versión (`api/v1`), con módulos para usuarios, planes, pagos, contenidos, perfiles, etc.

- **Arquitectura modular y escalable**  
  Separación clara: `api` (rutas), `models` (SQLAlchemy), `schemas` (Pydantic), `core` (configuración y seguridad).

- **Base de datos versionada**  
  Modelos tipados con SQLAlchemy y migraciones controladas con Alembic.

- **Seguridad integrada**  
  Autenticación con JWT y manejo seguro de contraseñas.

- **Configuración flexible**  
  Variables de entorno (`.env`, `.env.example`) y ajustes centralizados en `core/config.py`.

- **Preparado para contenedores**  
  Despliegue rápido con `Dockerfile` y `docker-compose.yml`.

- **Scripts de soporte**  
  Utilidades como creación de administrador inicial y diagramas de arquitectura.

## Requisitos

- Python 3.10+
- pip
- Docker (opcional, para contenedores)
- Docker Compose (opcional, para orquestar servicios)
- PostgreSQL (si corres la base de datos localmente en vez de usar Docker)
- Alembic (para migraciones de base de datos)
- PlantUML (opcional, para generar diagramas desde `scripts/plantuml.txt`)

## Instalación

1.  **Abre una terminal en la carpeta raíz del proyecto.**

2.  **Crea y activa un entorno virtual:**

    -   Windows (PowerShell):

        ``` powershell
        python -m venv .venv
        .venv\Scripts\Activate.ps1
        ```

    -   Linux / macOS (bash/zsh):

        ``` bash
        python3 -m venv .venv
        source .venv/bin/activate
        ```
3.  **Instalar dependencias**

``` bash
pip install -r requirements.txt
```

4. **Configurar variables de entorno**
- Copia `.env.example.txt` a `.env`
- Ajusta los valores según tu entorno (DB, secretos JWT, etc.)

5. **USAR DOCKER COMPOSE (OPCIONAL)**
- **Con Docker Compose**
```bash
docker compose --profile dev up
docker compose --profile serve up
```


## Ejecución

Ejecuta el servidor con Uvicorn desde la raíz del proyecto:

``` bash
fastapi dev main.py
```

-   Base URL: `http://127.0.0.1:8000`
-   Swagger UI: `http://127.0.0.1:8000/docs`
-   ReDoc: `http://127.0.0.1:8000/redoc`

## Migraciones de base de datos

Este proyecto usa **Alembic** para gestionar cambios en el esquema de la base de datos de forma controlada.

### Comandos básicos

- **Crear una nueva migración**
```bash
alembic revision --autogenerate -m "mensaje_descriptivo"
```

- **Aplicar migraciones pendientes**
```bash
alembic upgrade head
```

- **Revertir la última migración**
```bash
alembic downgrade -1
```

### Sincronizar el esquema

1. Asegúrate de que tus modelos de SQLAlchemy reflejan el estado actual deseado.
2. Crea una nueva migración con `--autogenerate`.
3. Revisa el archivo generado en `migration/versions/` y ajusta si es necesario.
4. Aplica los cambios con:
```bash
alembic upgrade head
```

## Licencia

Este proyecto está bajo la licencia **MIT**.  
Puedes usar, copiar, modificar y distribuir el código libremente siempre que incluyas el aviso de copyright y la licencia original.

## Autores
ALEXSANDER GONZALEZ (AlexF6)

JEIFERSON SANTILLANA (JeifersonSantillana)
