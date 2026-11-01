# PEI-CEPLAN

Generador local de documentos del Plan Estratégico Institucional (PEI) para gobiernos locales. El flujo permite completar los datos del municipio, consultar el catálogo UE, seleccionar y priorizar OEI/AEI, registrar metas y generar un documento Word.

## Estructura

```text
frontend/
  index.html             Interfaz activa y JavaScript inline
  app.js                 JavaScript heredado, no usado por index.html
  styles.css             Estilos de la interfaz
  matriz_estandar.json    Fuente única de OEI, AEI e indicadores
backend/
  generador.py           Servidor HTTP, validación y generación DOCX
  catalogo.py            Lectura segura de IT_PEI.xlsx
  fichas_tecnicas.json    Fichas técnicas consumidas por el generador
  requirements.txt        Dependencias reproducibles
tests/test_proyecto.py    Pruebas de generación, HTTP y navegador
requirements-dev.txt     Dependencias adicionales para las pruebas
plantillas/               DOCX fuente
archivos-gen/             Salidas DOCX generadas
IT_PEI.xlsx               Catálogo UE configurado por defecto
```

La matriz vive en `frontend/matriz_estandar.json` porque también es un recurso público del formulario. Las fichas viven en `backend/fichas_tecnicas.json` porque solo las consume el generador. No se mantienen copias alternativas de esos JSON.

## Instalación

Desde la raíz del proyecto, en PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
```

El servidor no instala dependencias durante una solicitud. Si falta una dependencia, debe instalarse antes de arrancar el proceso.

## Ejecución

```powershell
.\.venv\Scripts\python.exe backend/generador.py
```

Abrir `http://127.0.0.1:8000/`. Las rutas de plantillas, JSON, catálogo y salidas se resuelven desde `__file__`, por lo que el comando no depende del directorio actual.
El puerto se configura con `PORT` y usa `8000` por defecto; el servidor escucha en `0.0.0.0`. En desarrollo local, el formulario usa el mismo origen y puerto desde el que se abrió.

## Contrato HTTP

| Método | Ruta | Uso |
|---|---|---|
| `GET` | `/` o `/index.html` | Frontend público |
| `GET` | `/matriz_estandar.json` | Matriz pública usada por el frontend |
| `GET` | `/api/ue/<codigo>` | Consulta segura del catálogo UE |
| `POST` | `/generar` | Valida el payload y devuelve el DOCX como descarga |
| `GET` | `/downloads/<archivo>.docx` | Descarga controlada desde `archivos-gen/` |

El servidor no expone el backend, las plantillas, `IT_PEI.xlsx`, `fichas_tecnicas.json` ni listados arbitrarios del sistema de archivos. Las descargas solo aceptan nombres de salida saneados que existan en `archivos-gen/`.

## Autocompletado UE

En el campo `Código UE`, presionar **Enter** consulta `/api/ue/<codigo>` y completa municipio, provincia, región y período cuando el catálogo los contiene. En local, la URL usa el origen actual. Si el frontend se aloja por separado, utiliza el servidor Render configurado en `index.html`; puede reemplazarse mediante `window.PEI_API_BASE_URL` antes del script.

`IT_PEI.xlsx` se busca por defecto en la raíz del proyecto. También puede configurarse una ruta explícita con `PEI_IT_PEI_PATH`; las rutas relativas se resuelven desde la raíz del proyecto, no desde el cwd. Si no existe, el catálogo queda vacío y la API devuelve un error claro para códigos no encontrados.

## Generación y reglas de negocio

- El payload se valida completamente antes de abrir una plantilla: tipos, formatos, jerarquía OEI/AEI, indicadores, prioridades, período y valores no negativos.
- Se conservan los códigos e IDs originales en payload, JSON y lookups.
- El DOCX muestra OEI secuenciales según el orden elegido y AEI secuenciales desde `01` dentro de cada OEI visible.
- Solo se generan los OEI, AEI e indicadores seleccionados, respetando sus ordinales.
- La prioridad de AEI se conserva al cerrar y reabrir la lista, cambiar indicadores y agregar o retirar AEI. Las AEI nuevas se agregan al final del orden existente.
- Los años del período se expanden dinámicamente. La línea base enviada por el formulario prevalece sobre el JSON cuando contiene año y valor.
- La oración de Anexo B.1 que comienza con `El PEI está articulado al` se formatea en Arial Narrow de 12 puntos.
- El número de ordenanza reemplaza el placeholder correspondiente.
- Las notas de fichas quedan fuera de la tabla; se limpian placeholders, párrafos sobrantes y saltos de página innecesarios, y se normalizan los bordes T0.
- Los temporales se crean con `tempfile` y se eliminan aun cuando la generación falla. Las salidas se escriben en `archivos-gen/`.

## Pruebas

Desde la raíz:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
python -m py_compile backend/generador.py backend/catalogo.py
git diff --check
```

La suite ejecuta Chromium sin ventana y un servidor local en un puerto libre. Verifica conservación de prioridades, arrastre sin manejadores duplicados, autocompletado UE por Enter, rutas HTTP y rechazo de payloads inválidos, descarga desde el formulario, metas del período y orden/códigos de la ruta estratégica en Word, incluso con todos los OEI y AEI en orden inverso. No requiere pytest.
