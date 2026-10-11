# GESTINOVA PEI

Aplicación autenticada para generar documentos del Plan Estratégico Institucional y contabilizar las generaciones completadas para facturación.

## Inicio rápido

1. Crear un entorno e instalar dependencias:

   ```bash
   python -m venv .venv
   .venv/bin/python -m pip install -r backend/requirements.txt
   ```

2. Configurar secretos y PostgreSQL:

   ```bash
   export DATABASE_URL='postgresql+psycopg://usuario:contraseña@host/base'
   export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
   export FLASK_APP=backend/app.py
   ```

3. Crear tablas y el primer administrador:

   ```bash
   flask init-db
   export GESTINOVA_ADMIN_USERNAME='admin'
   export GESTINOVA_ADMIN_PASSWORD='una-contraseña-larga-y-única'
   flask create-admin
   unset GESTINOVA_ADMIN_PASSWORD
   ```

4. Iniciar la aplicación:

   ```bash
   python backend/app.py
   ```

La aplicación escucha en `127.0.0.1:8000` por defecto. `PEI_HOST` y `PORT` permiten cambiar esos valores. En producción debe ejecutarse detrás de HTTPS para que la cookie de sesión `Secure` sea transmitida.

## Seguridad y operación

| Área | Comportamiento |
|---|---|
| Contraseñas | Argon2id con salt aleatorio; nunca se almacena texto plano. |
| Sesión | Cookie `HttpOnly`, `SameSite=Lax` y `Secure` fuera de pruebas. |
| CSRF | Login, logout, generación y administración requieren token. |
| Usuarios | Solo un administrador puede crear, activar, desactivar o restablecer contraseñas. |
| Base de datos | Producción exige `DATABASE_URL`; no existe fallback SQLite. |
| Archivos | Backend, base, secretos, plantillas y salidas no son recursos estáticos públicos. |
| Descargas | Requieren sesión y propiedad del documento; administradores pueden auditar. |

No se ofrece una ruta pública para crear el primer administrador. Las variables `GESTINOVA_ADMIN_*` se usan únicamente por el comando CLI y la contraseña debe eliminarse del entorno inmediatamente después.

## Facturación e idempotencia

Una generación se registra únicamente después de guardar correctamente el DOCX final. Cada solicitud debe incluir un UUID `generation_request_id`; repetirlo devuelve la generación existente sin crear otro cargo. El nombre final usa ese UUID (`PEI_<uuid>.docx`), evitando que dos documentos del mismo municipio se sobrescriban.

El panel **Facturación** está restringido a administradores y presenta el total histórico, el total por usuario y el total por mes calendario.

## Pruebas

Las pruebas inyectan SQLite en memoria exclusivamente como base aislada y determinista; producción no lo usa.

```bash
python -m unittest -v
python -m unittest -v backend.test_auth backend.test_admin backend.test_generation_accounting backend.test_dashboard
node --check frontend/app.js
python -m py_compile backend/app.py backend/models.py backend/generador.py backend/catalogo.py
git diff --check
```

La lógica histórica de armado del DOCX permanece en `backend/generador.py`. Flask controla autenticación, autorización, persistencia, idempotencia y nombres de salida, y llama esa implementación con una ruta final explícita.
