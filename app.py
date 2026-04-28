from flask import Flask, Response, request, render_template, redirect
from flask_cors import CORS
import psycopg2
import psycopg2.extras
import json
import os
from decimal import Decimal
from datetime import date, datetime, time

app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False
CORS(app)


def get_connection():
    database_url = os.environ.get("DATABASE_URL")

    if not database_url:
        raise Exception("DATABASE_URL no está configurada en Railway")

    conn = psycopg2.connect(database_url)
    conn.set_client_encoding("UTF8")
    return conn


def json_default(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, (datetime, date, time)):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def json_response(data, status=200):
    return Response(
        json.dumps(data, ensure_ascii=False, default=json_default),
        status=status,
        content_type="application/json; charset=utf-8"
    )


@app.route("/", methods=["GET"])
def index():
    return redirect("/formulario")


@app.route("/formulario", methods=["GET"])
def formulario():
    return render_template("formulario.html")


@app.route("/usuarios", methods=["GET"])
def get_usuarios():
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
        SELECT id, nombre, email
        FROM usuarios
        ORDER BY id;
    """)

    usuarios = cur.fetchall()

    cur.close()
    conn.close()

    return json_response(usuarios)


@app.route("/categorias", methods=["GET"])
def get_categorias():
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
        SELECT id, nombre
        FROM categorias
        ORDER BY nombre;
    """)

    categorias = cur.fetchall()

    cur.close()
    conn.close()

    return json_response(categorias)


@app.route("/sectores", methods=["GET"])
def get_sectores():
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
        SELECT DISTINCT sector
        FROM lugares
        WHERE sector IS NOT NULL AND sector <> ''
        ORDER BY sector;
    """)

    sectores = cur.fetchall()

    cur.close()
    conn.close()

    return json_response(sectores)


@app.route("/lugares", methods=["GET"])
def get_lugares():
    q = request.args.get("q", "").strip()
    sector = request.args.get("sector", "").strip()
    categoria = request.args.get("categoria", "").strip()

    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    query = """
        SELECT *
        FROM vw_lugares_resumen
        WHERE 1=1
    """

    params = []

    if q:
        query += " AND nombre ILIKE %s"
        params.append(f"%{q}%")

    if sector:
        query += " AND sector ILIKE %s"
        params.append(sector)

    if categoria:
        query += " AND categoria ILIKE %s"
        params.append(categoria)

    query += """
        ORDER BY promedio_calificacion DESC NULLS LAST,
                 total_calificaciones DESC,
                 nombre ASC;
    """

    cur.execute(query, params)
    lugares = cur.fetchall()

    cur.close()
    conn.close()

    return json_response(lugares)


@app.route("/lugares/top", methods=["GET"])
def get_top_lugares():
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
        SELECT *
        FROM vw_lugares_resumen
        ORDER BY promedio_calificacion DESC NULLS LAST,
                 total_calificaciones DESC,
                 nombre ASC
        LIMIT 10;
    """)

    lugares = cur.fetchall()

    cur.close()
    conn.close()

    return json_response(lugares)


@app.route("/lugares/<int:id_lugar>", methods=["GET"])
def get_lugar_por_id(id_lugar):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
        SELECT
            l.id,
            l.nombre,
            c.nombre AS categoria,
            l.direccion,
            l.sector,
            l.ciudad,
            l.descripcion,
            l.latitud,
            l.longitud,
            ROUND(AVG(cal.puntuacion), 2) AS promedio_calificacion,
            COUNT(cal.id) AS total_calificaciones
        FROM lugares l
        LEFT JOIN categorias c ON l.categoria_id = c.id
        LEFT JOIN calificaciones cal ON cal.lugar_id = l.id
        WHERE l.id = %s
        GROUP BY l.id, l.nombre, c.nombre, l.direccion, l.sector,
                 l.ciudad, l.descripcion, l.latitud, l.longitud;
    """, (id_lugar,))

    lugar = cur.fetchone()

    cur.close()
    conn.close()

    if lugar is None:
        return json_response({"error": "Lugar no encontrado"}, status=404)

    return json_response(lugar)


@app.route("/lugares/<int:id_lugar>/comentarios", methods=["GET"])
def get_comentarios_por_lugar(id_lugar):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
        SELECT
            cal.id,
            u.nombre AS usuario,
            cal.puntuacion,
            cal.comentario,
            cal.fecha_calificacion
        FROM calificaciones cal
        JOIN usuarios u ON cal.usuario_id = u.id
        WHERE cal.lugar_id = %s
        ORDER BY cal.fecha_calificacion DESC;
    """, (id_lugar,))

    comentarios = cur.fetchall()

    cur.close()
    conn.close()

    return json_response(comentarios)


@app.route("/calificaciones", methods=["POST"])
def crear_calificacion():
    conn = None
    cur = None

    try:
        data = request.get_json()

        if not data:
            return json_response({"error": "Debes enviar JSON"}, status=400)

        usuario_id = data.get("usuario_id")
        lugar_id = data.get("lugar_id")
        puntuacion = data.get("puntuacion")
        comentario = data.get("comentario", "")

        if usuario_id is None or lugar_id is None or puntuacion is None:
            return json_response(
                {"error": "usuario_id, lugar_id y puntuacion son obligatorios"},
                status=400
            )

        conn = get_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute("""
            INSERT INTO calificaciones (usuario_id, lugar_id, puntuacion, comentario)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (usuario_id, lugar_id)
            DO UPDATE SET
                puntuacion = EXCLUDED.puntuacion,
                comentario = EXCLUDED.comentario,
                fecha_calificacion = CURRENT_TIMESTAMP
            RETURNING id, usuario_id, lugar_id, puntuacion, comentario, fecha_calificacion;
        """, (usuario_id, lugar_id, puntuacion, comentario))

        calificacion = cur.fetchone()
        conn.commit()

        return json_response({
            "message": "Calificación guardada correctamente",
            "data": calificacion
        }, status=201)

    except Exception as e:
        if conn:
            conn.rollback()
        return json_response({"error": str(e)}, status=500)

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


@app.route("/dashboard/resumen", methods=["GET"])
def dashboard_resumen():
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
        SELECT
            (SELECT COUNT(*) FROM lugares) AS total_lugares,
            (SELECT COUNT(*) FROM usuarios) AS total_usuarios,
            (SELECT COUNT(*) FROM calificaciones) AS total_calificaciones,
            (SELECT ROUND(AVG(puntuacion), 2) FROM calificaciones) AS promedio_general;
    """)

    data = cur.fetchone()

    cur.close()
    conn.close()

    return json_response(data)


@app.route("/dashboard/categorias", methods=["GET"])
def dashboard_categorias():
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
        SELECT
            c.nombre AS categoria,
            ROUND(AVG(cal.puntuacion), 2) AS promedio,
            COUNT(cal.id) AS total_calificaciones
        FROM categorias c
        LEFT JOIN lugares l ON l.categoria_id = c.id
        LEFT JOIN calificaciones cal ON cal.lugar_id = l.id
        GROUP BY c.id, c.nombre
        ORDER BY promedio DESC NULLS LAST, total_calificaciones DESC;
    """)

    data = cur.fetchall()

    cur.close()
    conn.close()

    return json_response(data)


@app.route("/dashboard/sectores", methods=["GET"])
def dashboard_sectores():
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
        SELECT
            l.sector,
            ROUND(AVG(cal.puntuacion), 2) AS promedio,
            COUNT(cal.id) AS total_calificaciones
        FROM lugares l
        LEFT JOIN calificaciones cal ON cal.lugar_id = l.id
        WHERE l.sector IS NOT NULL AND l.sector <> ''
        GROUP BY l.sector
        ORDER BY total_calificaciones DESC, promedio DESC NULLS LAST;
    """)

    data = cur.fetchall()

    cur.close()
    conn.close()

    return json_response(data)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
