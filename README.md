# Mini API (FastAPI)

API de ejemplo muy sencilla hecha con **FastAPI**. Expone dos endpoints
básicos y sirve como punto de partida para proyectos más grandes.

## Características

-   **Root**: mensaje de bienvenida
-   **Items**: obtener un ítem por ID, con opción de query param

## Requisitos

-   Python 3.10+
-   pip

## Instalación

1.  Abre una terminal en la carpeta raíz del proyecto.

2.  Crea y activa un entorno virtual:

    -   Windows (PowerShell):

        ``` powershell
        python -m venv .venv
        .venv\Scripts\Activate.ps1
        ```

    -   Linux / macOS (bash/zsh):

        ``` bash
        python -m venv .venv
        source .venv/bin/activate
        ```

3.  Instala dependencias:

    ``` bash
    pip install fastapi uvicorn
    ```

## Ejecución

Ejecuta el servidor con Uvicorn desde la raíz del proyecto:

``` bash
uvicorn main:app --reload
```

-   Base URL: `http://127.0.0.1:8000`
-   Swagger UI: `http://127.0.0.1:8000/docs`
-   ReDoc: `http://127.0.0.1:8000/redoc`

## Estructura

``` text
.
├── main.py
└── README.md
```

## Endpoints

-   **Root**
    -   `GET /`: retorna `{"Hello": "World"}`
-   **Items**
    -   `GET /items/{item_id}`: retorna el `item_id` y opcionalmente un
        query param `q`

## Ejemplos rápidos (cURL)

-   Obtener root:

    ``` bash
    curl "http://127.0.0.1:8000/"
    ```

-   Obtener item con `id=5`:

    ``` bash
    curl "http://127.0.0.1:8000/items/5"
    ```

-   Obtener item con query param:

    ``` bash
    curl "http://127.0.0.1:8000/items/10?q=ejemplo"
    ```

## Notas

-   Este proyecto es solo una base mínima.
-   Se puede extender fácilmente con más rutas, modelos de datos y
    persistencia.

## Mejoras sugeridas

-   Agregar modelos Pydantic para validar datos.
-   Crear endpoints para CRUD de recursos.
-   Añadir autenticación.
-   Persistencia con SQLite/PostgreSQL.
-   Tests automatizados.
