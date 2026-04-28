
from flask import Flask, Response, request, redirect, render_template_string
from flask_cors import CORS
import psycopg2, psycopg2.extras
import json, os, hashlib
from decimal import Decimal
from datetime import date, datetime, time
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False
CORS(app)

def get_connection():
    url = os.getenv("DATABASE_URL")
    if url:
        conn = psycopg2.connect(url)
    else:
        conn = psycopg2.connect(
            host=os.getenv("PGHOST", "localhost"),
            database=os.getenv("PGDATABASE", "gye_food_app"),
            user=os.getenv("PGUSER", "postgres"),
            password=os.getenv("PGPASSWORD", "1234"),
            port=os.getenv("PGPORT", "5432")
        )
    conn.set_client_encoding("UTF8")
    return conn

def json_default(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, (datetime, date, time)):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

def json_response(data, status=200):
    return Response(json.dumps(data, ensure_ascii=False, default=json_default), status=status, content_type="application/json; charset=utf-8")

def legacy_sha256(password):
    return hashlib.sha256(password.encode()).hexdigest()

def password_matches(stored_hash, password):
    if not stored_hash:
        return False
    if stored_hash.startswith("pbkdf2:") or stored_hash.startswith("scrypt:"):
        return check_password_hash(stored_hash, password)
    return stored_hash == legacy_sha256(password)

HTML = """
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>GYE Food App</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
*{box-sizing:border-box}body{margin:0;font-family:Arial,sans-serif;background:#f4f6fb;color:#1f2937}.header{background:linear-gradient(135deg,#0f172a,#2563eb);color:white;padding:30px}.header h1{margin:0 0 10px 0;font-size:40px}.header p{margin:0;opacity:.95;font-size:18px}.container{max-width:1500px;margin:24px auto;padding:0 18px}.grid{display:grid;grid-template-columns:360px 1fr;gap:22px}.card{background:white;border-radius:18px;padding:22px;box-shadow:0 8px 26px rgba(15,23,42,.08);margin-bottom:22px}h2,h3{margin-top:0}label{display:block;font-weight:bold;margin-bottom:7px}input,select,textarea,button{width:100%;padding:12px 14px;margin-bottom:14px;border-radius:12px;border:1px solid #d1d5db;font-size:15px}button{background:#2563eb;color:white;border:none;cursor:pointer;font-weight:bold}button:hover{background:#1d4ed8}button.danger{background:#dc2626}textarea{min-height:95px;resize:vertical}.filters{display:grid;grid-template-columns:1.2fr 1fr 1fr;gap:14px}.lugares-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(285px,1fr));gap:16px}.lugar-card{background:white;border-radius:17px;padding:18px;box-shadow:0 8px 22px rgba(15,23,42,.07);border:2px solid transparent;cursor:pointer;transition:.2s}.lugar-card:hover,.lugar-card.active{border-color:#2563eb;transform:translateY(-2px)}.pill{display:inline-block;padding:5px 11px;border-radius:999px;background:#e0e7ff;color:#3730a3;font-size:12px;margin-right:6px;margin-bottom:6px}.stars{color:#f59e0b;font-size:20px;letter-spacing:1px}.muted{color:#6b7280;font-size:14px}#map{height:390px;border-radius:17px;overflow:hidden}.resultado{white-space:pre-wrap;background:#f8fafc;border:1px solid #e5e7eb;padding:13px;border-radius:13px}.success{color:#15803d;font-weight:bold}.error{color:#b91c1c;font-weight:bold}.comentario{border-bottom:1px solid #e5e7eb;padding:12px 0}.comentario:last-child{border-bottom:none}.topbar{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}.small-btn{width:auto;padding:10px 16px;margin-bottom:0}.kpi{text-align:center;background:#f8fafc}.kpi h3{font-size:32px;margin:0;color:#2563eb}.auth-box{background:#eff6ff;border:1px solid #bfdbfe}.hidden{display:none}.chart-wrap{height:280px;margin:16px 0}.info-row{display:grid;grid-template-columns:1fr 1fr;gap:8px}.price{font-weight:bold;color:#047857}@media(max-width:980px){.grid{grid-template-columns:1fr}.filters{grid-template-columns:1fr}.info-row{grid-template-columns:1fr}}
</style>
</head>
<body>
<div class="header"><h1>🍽️ GYE Food App</h1><p>Lugares de comida en Guayaquil con login, calificaciones, filtros, mapa y dashboard BI.</p></div>
<div class="container"><div class="grid">
<div>
<div class="card auth-box"><h2>🔐 Cuenta</h2><div id="session_box" class="resultado">Sin sesión iniciada.</div><div id="auth_forms"><h3>Iniciar sesión</h3><input id="login_email" placeholder="Email"><input id="login_password" type="password" placeholder="Contraseña"><button onclick="login()">Iniciar sesión</button><h3>Registro</h3><input id="reg_nombre" placeholder="Nombre"><input id="reg_email" placeholder="Email"><input id="reg_password" type="password" placeholder="Contraseña"><button onclick="register()">Crear cuenta</button></div><button id="btnLogout" onclick="logout()" class="danger hidden">Cerrar sesión</button></div>
<div class="card"><h2>⭐ Calificar lugar</h2><form id="form"><label>Usuario</label><select id="usuario_id"></select><label>Lugar</label><select id="lugar_id"></select><label>Puntuación</label><select id="puntuacion"><option value="5">5 - Excelente</option><option value="4">4 - Muy bueno</option><option value="3">3 - Bueno</option><option value="2">2 - Regular</option><option value="1">1 - Malo</option></select><label>Comentario</label><textarea id="comentario">Muy bueno</textarea><button type="submit">Guardar / actualizar calificación</button></form><h3>Resultado</h3><div id="resultado" class="resultado">Sin envíos todavía.</div></div>
<div class="card"><div class="topbar"><h2>🗺️ Mapa</h2><button id="btnVerTodosMapa" type="button" class="small-btn">Ver todos</button></div><div id="map"></div><p class="muted">Haz clic en un marcador o una tarjeta para ver detalle.</p></div>
</div>
<div>
<div class="card"><div class="topbar"><h2>🔍 Buscar lugares</h2><button id="btnRecargar" type="button" class="small-btn">Recargar</button></div><div class="filters"><div><label>Buscar por nombre</label><input type="text" id="buscar" placeholder="Ej: ceviche, pizza, parrilla"></div><div><label>Sector</label><select id="filtro_sector"><option value="">Todos</option></select></div><div><label>Categoría</label><select id="filtro_categoria"><option value="">Todas</option></select></div></div></div>
<div class="card"><h2>📊 Dashboard BI</h2><div id="dashboard_resumen" class="lugares-grid"></div><div class="chart-wrap"><canvas id="chartCategorias"></canvas></div><div class="chart-wrap"><canvas id="chartSectores"></canvas></div></div>
<div class="card"><h2>🏆 Top lugares</h2><div id="top_lugares" class="lugares-grid"></div></div>
<div class="card"><h2>📍 Todos los lugares</h2><div id="lista_lugares" class="lugares-grid"></div></div>
<div class="card"><h2>💬 Detalle y comentarios</h2><div id="detalle_lugar" class="resultado">Selecciona un lugar.</div><div id="comentarios" style="margin-top:16px;"></div></div>
</div>
</div></div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
let lugaresCache=[],topCache=[],currentLugarId=null,map,markersLayer,markers={},usuarioLogueado=null;let chartCategorias=null,chartSectores=null;
function estrellas(v){const n=Math.round(Number(v||0));return "★".repeat(n)+"☆".repeat(5-n);}
function escapeHtml(t){if(t===null||t===undefined)return "";return String(t).replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;").replaceAll("'","&#039;");}
async function fetchJSON(url){const r=await fetch(url);const data=await r.json();if(!r.ok){throw new Error(data.error||"Error en "+url)}return data;}
function initMap(){map=L.map("map").setView([-2.170998,-79.922359],12);L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",{attribution:"&copy; OpenStreetMap contributors"}).addTo(map);markersLayer=L.layerGroup().addTo(map);}
function pintarMapa(lugares){markersLayer.clearLayers();markers={}
