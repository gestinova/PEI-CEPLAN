# PEI-CEPLAN

Generador local de documentos del Plan Estratégico Institucional (PEI) para gobiernos locales. El flujo permite completar los datos del municipio, consultar el catálogo UE, seleccionar y priorizar OEI/AEI, registrar metas y generar un documento Word.

## Estructura

```text
frontend/
  index.html              Interfaz activa y estado completo del formulario
  matriz_estandar.json    Fuente única de OEI, AEI e indicadores
backend/
  generador_pei_fase4.py  Servidor HTTP, validación y generación DOCX
  catalogo_ue.py          Lectura segura de IT_PEI.xlsx
  fichas_tecnicas.json    Fichas técnicas consumidas por el generador
  requirements.txt        Dependencias reproducibles
  test_*.py               Pruebas backend y del script inline
plantillas/               DOCX fuente
archivos-gen/             Salidas DOCX generadas
IT_PEI.xlsx               Catálogo UE configurado por defecto
```

La matriz vive en `frontend/matriz_estandar.json` porque también es un recurso público del formulario. Las fichas viven en `backend/fichas_tecnicas.json` porque solo las consume el generador. No se mantienen copias alternativas de esos JSON.

## Instalación

Desde la raíz del worktree:

```bash
python -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
```

El servidor no instala dependencias durante una solicitud. Si falta una dependencia, debe instalarse antes de arrancar el proceso.

## Ejecución

```bash
.venv/bin/python backend/generador_pei_fase4.py
```

Abrir `http://127.0.0.1:8000/`. Las rutas de plantillas, JSON, catálogo y salidas se resuelven desde `__file__`, por lo que el comando no depende del directorio actual.
El puerto se configura con `PORT` y usa `8000` por defecto; el host usa `0.0.0.0` para Render y puede cambiarse con `PEI_HOST`.

## Contrato HTTP

| Método | Ruta | Uso |
|---|---|---|
| `GET` | `/` o `/index.html` | Frontend público |
| `GET` | `/matriz_estandar.json` | Matriz pública usada por el frontend |
| `GET` | `/api/ue/<codigo>` | Consulta segura del catálogo UE |
| `POST` | `/generar` | Valida el payload y genera el DOCX |
| `GET` | `/downloads/<archivo>.docx` | Descarga controlada desde `archivos-gen/` |

El servidor no expone el backend, las plantillas, `IT_PEI.xlsx`, `fichas_tecnicas.json` ni listados arbitrarios del sistema de archivos. Las descargas solo aceptan nombres de salida saneados que existan en `archivos-gen/`.

El frontend usa el origen actual por defecto. Para desplegarlo separado en Vercel, definí explícitamente `window.PEI_API_BASE_URL` antes del script inline de `frontend/index.html` y configurá el backend con `PEI_ALLOWED_ORIGIN` con el origen exacto de Vercel. No se usa una URL Render fija ni un fallback implícito.

## Despliegue separado

### Vercel

La configuración versionada está en `frontend/vercel.json`. Usá estos valores en el proyecto de Vercel:

- **Production Branch:** `main`.
- **Root Directory:** `frontend`.
- **Framework Preset:** `Other` / sitio estático.
- **Build Command:** vacío, sin build.
- **Output Directory:** `.`.

Con `Root Directory=frontend`, Vercel carga `frontend/vercel.json` y sirve `frontend/index.html` como raíz. Los únicos rewrites configurados son:

- `/api/:path*` hacia `https://pei-ceplan-vr1m.onrender.com/api/:path*`.
- `/generar` hacia `https://pei-ceplan-vr1m.onrender.com/generar`.
- `/downloads/:path*` hacia `https://pei-ceplan-vr1m.onrender.com/downloads/:path*`.

No se proxyean archivos fuente, la matriz, plantillas, Excel ni archivos del backend. Con estos rewrites el navegador usa rutas relativas y el flujo es same-origin; no agregues `PEI_API_BASE_URL` al despliegue normal de Vercel.

Para un despliegue estático sin rewrites, el override debe ser explícito y estar antes del script inline, por ejemplo:

```html
<script>window.PEI_API_BASE_URL = 'https://pei-ceplan-vr1m.onrender.com';</script>
```

La aplicación estática no transforma automáticamente una variable de entorno de Vercel en `window.PEI_API_BASE_URL`. Ese modo directo requiere CORS en Render y no debe sustituir el fallback same-origin.

### Render

- **Root Directory:** raíz del repositorio, no `backend`.
- **Build Command:** `pip install -r backend/requirements.txt`.
- **Branch:** `main`.
- **Start Command:** `python backend/generador_pei_fase4.py`.
- **`PEI_HOST`:** `0.0.0.0`.
- **`PORT`:** dejar que Render lo inyecte; el servidor lo lee y usa `8000` solo como default local.
- **`PEI_ALLOWED_ORIGIN`:** `https://pei-ceplan.vercel.app` si el frontend accede directamente a Render; debe ser el origen exacto, sin `*`.

El backend responde JSON en `/generar` con `{success,file,message}` y el DOCX se obtiene después desde `/downloads/<archivo>`. CORS se envía únicamente cuando `Origin` coincide con `PEI_ALLOWED_ORIGIN`, también para `/matriz_estandar.json`; el modo same-origin no depende de CORS.

## Autocompletado UE

En el campo `Código UE`, presionar **Enter** consulta `/api/ue/<codigo>` y completa municipio, provincia, región y período cuando el catálogo los contiene. La URL usa el origen actual; puede configurarse un prefijo mediante `window.PEI_API_BASE_URL` antes del script para autocompletado, generación y descargas si el frontend se sirve separado.

`IT_PEI.xlsx` se busca por defecto en la raíz del proyecto. También puede configurarse una ruta explícita con `PEI_IT_PEI_PATH`; las rutas relativas se resuelven desde la raíz del proyecto, no desde el cwd. Si no existe, el catálogo queda vacío y la API devuelve un error claro para códigos no encontrados.

## Generación y reglas de negocio

- El payload se valida completamente antes de abrir una plantilla: tipos, formatos, jerarquía OEI/AEI, indicadores, prioridades, período y valores no negativos.
- Se conservan los códigos e IDs originales en payload, JSON y lookups.
- El DOCX muestra OEI secuenciales según el orden elegido y AEI secuenciales desde `01` dentro de cada OEI visible.
- Solo se generan los OEI, AEI e indicadores seleccionados, respetando sus ordinales.
- Los años del período se expanden dinámicamente. La línea base enviada por el formulario prevalece sobre el JSON cuando contiene año y valor.
- La oración de Anexo B.1 que comienza con `El PEI está articulado al` se formatea en Arial Narrow de 12 puntos.
- El número de ordenanza reemplaza el placeholder correspondiente.
- Las notas de fichas quedan fuera de la tabla; se limpian placeholders, párrafos sobrantes y saltos de página innecesarios, y se normalizan los bordes T0.
- Los temporales se crean con `tempfile` y se eliminan aun cuando la generación falla. Las salidas se escriben en `archivos-gen/`.

## Pruebas

Desde la raíz:

```bash
pytest -q
python -m py_compile backend/generador_pei_fase4.py backend/catalogo_ue.py
git diff --check
```

La suite cubre validación de payload, catálogo y `/api/ue`, autocompletado por Enter, estado del frontend, períodos, ordinales, generación DOCX, líneas base, tipografía, notas, limpieza XML, temporales y exposición de archivos.
