"""Flask application factory for GESTINOVA PEI."""

import hmac
import os
import secrets
import uuid
from functools import wraps
from pathlib import Path

from flask import Flask, Response, abort, g, jsonify, redirect, render_template, request, send_file, session, url_for
from sqlalchemy import extract, func, select
from sqlalchemy.exc import IntegrityError

from models import Base, Generation, User, create_database, hash_password, verify_password


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def create_app(config=None):
    config = dict(config or {})
    testing = bool(config.get("TESTING"))
    database_url = config.get("DATABASE_URL") or os.environ.get("DATABASE_URL")
    secret_key = config.get("SECRET_KEY") or os.environ.get("SECRET_KEY")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required.")
    if not secret_key and not testing:
        raise RuntimeError("SECRET_KEY is required.")

    app = Flask(__name__, template_folder="templates", static_folder=None)
    app.config.update(
        TESTING=testing,
        SECRET_KEY=secret_key or "test-only-secret",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=not testing,
        MAX_CONTENT_LENGTH=1024 * 1024,
    )
    app.config.update(config)
    engine, session_factory = create_database(database_url)
    app.extensions["db_engine"] = engine
    app.extensions["db_session_factory"] = session_factory
    app.extensions["document_generator"] = config.get("DOCUMENT_GENERATOR", generate_document)
    if testing or config.get("CREATE_TABLES"):
        Base.metadata.create_all(engine)

    @app.before_request
    def load_identity():
        g.db = session_factory()
        g.user = None
        user_id = session.get("user_id")
        if user_id is not None:
            user = g.db.get(User, user_id)
            if user and user.is_active:
                g.user = user
            else:
                session.clear()

    @app.teardown_request
    def close_database(_error):
        database = g.pop("db", None)
        if database is not None:
            database.close()

    @app.context_processor
    def template_context():
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_urlsafe(32)
        return {"current_user": g.get("user"), "csrf_token": session["csrf_token"]}

    @app.get("/login")
    def login_form():
        if g.user:
            return redirect(url_for("home"))
        return render_template("login.html", error=None)

    @app.post("/login")
    def login():
        validate_csrf()
        username = request.form.get("username", "").strip().lower()
        user = g.db.scalar(select(User).where(User.username == username))
        if not user or not user.is_active or not verify_password(
            request.form.get("password", ""), user.password_hash
        ):
            return render_template("login.html", error="Credenciales inválidas."), 401
        session.clear()
        session["user_id"] = user.id
        session["csrf_token"] = secrets.token_urlsafe(32)
        return redirect(url_for("home"))

    @app.post("/logout")
    def logout():
        validate_csrf()
        session.clear()
        return redirect(url_for("login_form"))

    @app.get("/")
    @login_required
    def home():
        return render_template("home.html")

    @app.get("/ui.css")
    def application_styles():
        return send_file(Path(__file__).parent / "ui.css", mimetype="text/css")

    @app.get("/generator")
    @login_required
    def generator_ui():
        html = (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
        csrf_meta = f'<meta name="csrf-token" content="{session["csrf_token"]}">'
        return Response(html.replace("</head>", f"{csrf_meta}</head>"), mimetype="text/html")

    @app.get("/styles.css")
    @login_required
    def generator_styles():
        return send_file(PROJECT_ROOT / "frontend" / "styles.css", mimetype="text/css")

    @app.get("/matriz_estandar.json")
    @login_required
    def matrix_data():
        return send_file(PROJECT_ROOT / "frontend" / "matriz_estandar.json", mimetype="application/json")

    @app.get("/api/ue/<ue_id>")
    @login_required
    def executing_unit(ue_id):
        from catalogo import obtener_ue

        try:
            unit = obtener_ue(ue_id)
        except ValueError as error:
            return jsonify(success=False, error=str(error)), 400
        if unit is None:
            return jsonify(success=False, error="Unidad ejecutora no encontrada."), 404
        return jsonify(success=True, data=unit)

    @app.post("/generar")
    @login_required
    def generate():
        validate_csrf()
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify(success=False, error="Solicitud JSON inválida."), 400
        try:
            request_id = str(uuid.UUID(str(data.get("generation_request_id", ""))))
        except ValueError:
            return jsonify(success=False, error="generation_request_id inválido."), 422
        existing = g.db.scalar(
            select(Generation).where(Generation.generation_request_id == request_id)
        )
        if existing:
            if existing.user_id != g.user.id and not g.user.is_admin:
                abort(403)
            return jsonify(generation_response(existing, idempotent=True))

        municipality = str(data.get("nombre_municipio", ""))[:120]
        output_name = f"PEI_{request_id}.docx"
        output_path = PROJECT_ROOT / "archivos-gen" / output_name
        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            app.extensions["document_generator"](data, output_path)
            if not output_path.is_file():
                raise RuntimeError("The document generator did not save an output.")
            generation = Generation(
                generation_request_id=request_id,
                user_id=g.user.id,
                output_name=output_name,
                municipality=municipality,
            )
            g.db.add(generation)
            g.db.commit()
        except IntegrityError:
            g.db.rollback()
            generation = g.db.scalar(
                select(Generation).where(Generation.generation_request_id == request_id)
            )
            if generation is None:
                output_path.unlink(missing_ok=True)
                raise
        except Exception:
            g.db.rollback()
            output_path.unlink(missing_ok=True)
            raise
        return jsonify(generation_response(generation, idempotent=False)), 201

    @app.get("/downloads/<path:output_name>")
    @login_required
    def download(output_name):
        generation = g.db.scalar(select(Generation).where(Generation.output_name == output_name))
        if not generation or (generation.user_id != g.user.id and not g.user.is_admin):
            abort(404)
        output_path = PROJECT_ROOT / "archivos-gen" / generation.output_name
        if not output_path.is_file():
            abort(404)
        return send_file(output_path, as_attachment=True, download_name=generation.output_name)

    @app.get("/admin/users")
    @admin_required
    def admin_users():
        users = g.db.scalars(select(User).order_by(User.username)).all()
        return render_template("admin_users.html", users=users, error=None)

    @app.post("/admin/users")
    @admin_required
    def admin_create_user():
        validate_csrf()
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        if not username or len(username) > 80 or not username.replace("-", "").replace("_", "").isalnum():
            abort(400, "Invalid username")
        if g.db.scalar(select(User).where(User.username == username)):
            abort(409, "Username already exists")
        try:
            password_hash = hash_password(password)
        except ValueError as error:
            abort(400, str(error))
        g.db.add(User(username=username, password_hash=password_hash, is_admin=False))
        g.db.commit()
        return redirect(url_for("admin_users"))

    @app.post("/admin/users/<int:user_id>/status")
    @admin_required
    def admin_user_status(user_id):
        validate_csrf()
        if user_id == g.user.id:
            abort(400, "Administrators cannot disable their own account.")
        user = g.db.get(User, user_id)
        if not user:
            abort(404)
        user.is_active = request.form.get("active") == "true"
        g.db.commit()
        return redirect(url_for("admin_users"))

    @app.post("/admin/users/<int:user_id>/password")
    @admin_required
    def admin_user_password(user_id):
        validate_csrf()
        user = g.db.get(User, user_id)
        if not user:
            abort(404)
        try:
            user.password_hash = hash_password(request.form.get("password", ""))
        except ValueError as error:
            abort(400, str(error))
        g.db.commit()
        return redirect(url_for("admin_users"))

    @app.get("/admin/dashboard")
    @admin_required
    def admin_dashboard():
        total = g.db.scalar(select(func.count(Generation.id))) or 0
        by_user = g.db.execute(
            select(User.username, func.count(Generation.id))
            .outerjoin(Generation)
            .group_by(User.id, User.username)
            .order_by(User.username)
        ).all()
        by_month = g.db.execute(
            select(
                extract("year", Generation.completed_at).label("year"),
                extract("month", Generation.completed_at).label("month"),
                func.count(Generation.id),
            )
            .group_by("year", "month")
            .order_by("year", "month")
        ).all()
        return render_template(
            "admin_dashboard.html", total=total, by_user=by_user, by_month=by_month
        )

    @app.cli.command("create-admin")
    def create_admin():
        """Create the first administrator from environment variables."""
        username = os.environ.get("GESTINOVA_ADMIN_USERNAME", "").strip().lower()
        password = os.environ.get("GESTINOVA_ADMIN_PASSWORD", "")
        if not username or not password:
            raise RuntimeError("GESTINOVA_ADMIN_USERNAME and GESTINOVA_ADMIN_PASSWORD are required.")
        with session_factory() as database:
            if database.scalar(select(User).where(User.username == username)):
                raise RuntimeError("The administrator username already exists.")
            database.add(User(username=username, password_hash=hash_password(password), is_admin=True))
            database.commit()

    @app.cli.command("init-db")
    def init_db():
        """Create application tables in the configured PostgreSQL database."""
        Base.metadata.create_all(engine)

    return app


def validate_csrf():
    expected = session.get("csrf_token", "")
    supplied = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token", "")
    if not expected or not hmac.compare_digest(expected, supplied):
        abort(400, "Invalid CSRF token")


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not g.user:
            return redirect(url_for("login_form"))
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if not g.user.is_admin:
            abort(403)
        return view(*args, **kwargs)

    return wrapped


def generation_response(generation, idempotent):
    return {
        "success": True,
        "generation_request_id": generation.generation_request_id,
        "download_url": url_for("download", output_name=generation.output_name),
        "idempotent": idempotent,
    }


def generate_document(data, output_path):
    """Call the existing document implementation while controlling its final path."""
    from generador import PEIHandler, validar_payload

    validar_payload(data)
    handler = object.__new__(PEIHandler)
    handler.generar_documento(data, output_path=output_path)


if __name__ == "__main__":
    create_app().run(host=os.environ.get("PEI_HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "8000")))
