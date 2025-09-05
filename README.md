## Servicio de Streaming

Este proyecto consiste en el desarrollo de una plataforma de streaming que permite a los usuarios registrarse, autenticar su cuenta y acceder a un catálogo de contenidos audiovisuales (películas, series y documentales).

## 🗂️ Arquitectura del Proyecto  

La organización del proyecto sigue una estructura modular que facilita la escalabilidad y el mantenimiento del código:  

```bash
APP-SERVICES/
│── api/v1/              # Contiene los endpoints de la API (versión 1)
│   │── __init__.py      # Marca el directorio como un paquete de Python
│   │── users.py         # Rutas y controladores relacionados con usuarios
│
│── schemas/             # Definición de modelos y validaciones (Pydantic)
│   │── __init__.py      # Inicializa el paquete schemas
│   │── users.py         # Esquema de datos para usuarios
│
│── main.py              # Punto de entrada principal de la aplicación FastAPI
│── requirements.txt     # Dependencias del proyecto
│── README.md            # Documentación del proyecto
│── .gitignore           # Archivos/carpetas ignoradas por Git
│── .venv/               # Entorno virtual de Python
│── __pycache__/         # Archivos compilados automáticamente por Python
```

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
        python3 -m venv .venv
        source .venv/bin/activate
        ```

## Ejecución

Ejecuta el servidor con Uvicorn desde la raíz del proyecto:

``` bash
fastapi dev main.py
```

-   Base URL: `http://127.0.0.1:8000`
-   Swagger UI: `http://127.0.0.1:8000/docs`
-   ReDoc: `http://127.0.0.1:8000/redoc`


## Endpoints

## Endpoints de la API

La API expone endpoints para la gestión de **usuarios**.  
Todos los endpoints están bajo el prefijo:  

### 1. Obtener todos los usuarios
**GET** `/users/`  
Devuelve la lista de todos los usuarios.  
- Parámetro opcional: `activo` (`true` o `false`) para filtrar usuarios.  

**Ejemplo de uso:**  
```bash
GET http://localhost:8000/users/
GET http://localhost:8000/users/?activo=true
```
### 2. Obtener un usuario por ID
**GET** `/users/{user_id}`
Devuelve un usuario específico por su id.

**Ejemplo de uso:** 

-   Obtener usuario con `id=1`:

    ``` bash
    GET  http://127.0.0.1:8000/users/1
    ```

### 3. Crear un nuevo usuario
Crea un nuevo usuario.

**Ejemplo de uso:** 
```bash
POST http://localhost:8000/users/
Content-Type: application/json
```
-   Body
```bash
{
  "id": 4,
  "nombre": "Laura",
  "email": "laura@example.com",
  "activo": true
}
```

### 4. Actualizar un usuario

**PUT** `/users/{user_id}`

Actualiza los datos de un usuario existente.

**Ejemplo de uso:** 
```bash
PUT http://localhost:8000/users/1
```
```
Content-Type: application/json
```
-   Body
```
{
  "id": 1,
  "nombre": "Alex González",
  "email": "alexg@example.com",
  "activo": true
}
```

### 5. Eliminar un usuario

**DELETE** `/users/{user_id}`

Elimina un usuario por id.

**Ejemplo de uso:** 
```bash
DELETE http://localhost:8000/users/2
```
## Autores
ALEXSANDER GONZALEZ

JEIFERSON SANTILLANA
