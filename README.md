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
.
├── Dockerfile
├── README.md
├── alembic.ini
├── app
│   ├── __init__.py
│   ├── api
│   │   ├── deps.py
│   │   └── v1
│   │       ├── __init__.py
│   │       ├── auth.py
│   │       ├── contents.py
│   │       ├── episodes.py
│   │       ├── me_contents.py
│   │       ├── me_episodes.py
│   │       ├── me_payments.py
│   │       ├── me_plans.py
│   │       ├── me_playbacks.py
│   │       ├── me_profiles.py
│   │       ├── me_subscriptions.py
│   │       ├── me_users.py
│   │       ├── me_watchlist.py
│   │       ├── payments.py
│   │       ├── plans.py
│   │       ├── playbacks.py
│   │       ├── profiles.py
│   │       ├── public_contents.py
│   │       ├── subscriptions.py
│   │       ├── users.py
│   │       └── watchlist.py
│   ├── cli.py
│   ├── core
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── database.py
│   │   └── security.py
│   ├── main.py
│   ├── media
│   │   ├── thumbs
│   │   │   └── 
│   │   └── videos
│   │       ├── 
│   ├── models
│   │   ├── __init__.py
│   │   ├── auditmixin.py
│   │   ├── content.py
│   │   ├── episode.py
│   │   ├── payment.py
│   │   ├── plan.py
│   │   ├── playback.py
│   │   ├── profile.py
│   │   ├── subscription.py
│   │   ├── user.py
│   │   └── watchlist.py
│   └── schemas
│       ├── __init__.py
│       ├── base.py
│       ├── content.py
│       ├── episode.py
│       ├── payment.py
│       ├── plan.py
│       ├── playback.py
│       ├── profile.py
│       ├── subscriptions.py
│       ├── token.py
│       ├── user.py
│       └── watchlist.py
├── docker-compose.override.yml
├── docker-compose.yml
├── env.example.txt
├── migration
│   ├── README
│   ├── env.py
│   ├── script.py.mako
│   └── versions
│       └── b4880c330a66_local_db.py
├── ops
│   └── nginx
│       ├── cloudflared
│       │   ├── config.yml
│       │   └── credentials.json
│       ├── conf.d
│       │   └── app.conf
│       └── nginx.conf
├── requirements.txt
├── scripts
│   ├── plantuml.txt
│   └── seed_admin.py
├── secrets
│   ├── pgadmin_password.txt
│   └── postgres_password.txt
└── tests
    ├── __init__.py
    ├── api
    │   ├── __init__.py
    │   ├── test_auth.py
    │   ├── test_contents.py
    │   ├── test_me_contents.py
    │   └── test_users.py
    ├── conftest.py
    ├── crud
    │   ├── __init__.py
    │   └── test_crud_user.py
    ├── media
    │   └── videos
    └── security
        ├── __init__.py
        └── test_security.py

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
