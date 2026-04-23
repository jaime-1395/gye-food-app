from flask import Flask, Response, request, redirect, render_template_string
from flask_cors import CORS
import psycopg2, psycopg2.extras, json, hashlib
from decimal import Decimal
from datetime import date, datetime, time

app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False
CORS(app)

def get_connection():
    conn = psycopg2.connect(host="localhost", database="gye_food_app", user="postgres", password="1234", port="5432")
    conn.set_client_encoding("UTF8")
    return conn

def json_default(obj):
    if isinstance(obj, Decimal): return float(obj)
    if isinstance(obj, (datetime, date, time)): return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

def json_response(data, status=200):
    return Response(json.dumps(data, ensure_ascii=False, default=json_default), status=status, content_type="application/json; charset=utf-8")

HTML = r"""
<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8"><title>GYE Food App</title><meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<style>
*{box-sizing:border-box}body{margin:0;font-family:Arial;background:#f4f6fb;color:#1f2937}.header{background:linear-gradient(135deg,#0f172a,#2563eb);color:white;padding:28px}.container{max-width:1350px;margin:24px auto;padding:0 18px}.grid{display:grid;grid-template-columns:340px 1fr;gap:22px}.card{background:white;border-radius:18px;padding:20px;box-shadow:0 8px 26px rgba(15,23,42,.08);margin-bottom:22px}input,select,textarea,button{width:100%;padding:11px 13px;margin-bottom:14px;border-radius:11px;border:1px solid #d1d5db;font-size:15px}button{background:#2563eb;color:white;border:none;cursor:pointer;font-weight:bold}button:hover{background:#1d4ed8}textarea{min-height:90px}.filters{display:grid;grid-template-columns:1.2fr 1fr 1fr;gap:14px}.lugares-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px}.lugar-card{background:white;border-radius:17px;padding:17px;box-shadow:0 8px 22px rgba(15,23,42,.07);border:2px solid transparent;cursor:pointer}.lugar-card:hover,.lugar-card.active{border-color:#2563eb}.pill{display:inline-block;padding:5px 11px;border-radius:999px;background:#e0e7ff;color:#3730a3;font-size:12px;margin-right:6px;margin-bottom:6px}.stars{color:#f59e0b;font-size:19px}.muted{color:#6b7280;font-size:14px}#map{height:390px;border-radius:17px}.resultado{white-space:pre-wrap;background:#f8fafc;border:1px solid #e5e7eb;padding:13px;border-radius:13px}.success{color:#15803d;font-weight:bold}.error{color:#b91c1c;font-weight:bold}.comentario{border-bottom:1px solid #e5e7eb;padding:11px 0}.topbar{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}.small-btn{width:auto;padding:10px 16px;margin-bottom:0}.kpi{text-align:center;background:#f8fafc}.kpi h3{font-size:30px;margin:0;color:#2563eb}hr{border:none;border-top:1px solid #e5e7eb;margin:12px 0 18px}@media(max-width:980px){.grid{grid-template-columns:1fr}.filters{grid-template-columns:1fr}}
</style></head><body>
<div class="header"><h1>🍽️ GYE Food App</h1><p>Lugares de comida en Guayaquil con login, sesión guardada, calificaciones, mapa y dashboard BI.</p></div>
<div class="container"><div class="grid"><div>
<div class="card"><h2>🔐 Login / Registro</h2>
<label>Email</label><input id="login_email" placeholder="Email"><label>Contraseña</label><input id="login_password" type="password" placeholder="Contraseña">
<button onclick="login()">Iniciar sesión</button><button onclick="logout()" type="button">Cerrar sesión</button><hr>
<label>Nombre</label><input id="reg_nombre" placeholder="Nombre"><label>Email</label><input id="reg_email" placeholder="Email"><label>Contraseña</label><input id="reg_password" type="password" placeholder="Contraseña">
<button onclick="register()">Crear cuenta</button><div id="auth_result" class="resultado">Sin sesión iniciada.</div></div>
<div class="card"><h2>⭐ Calificar lugar</h2><form id="form"><label>Usuario</label><select id="usuario_id"></select><label>Lugar</label><select id="lugar_id"></select><label>Puntuación</label><select id="puntuacion"><option value="5">5 - Excelente</option><option value="4">4 - Muy bueno</option><option value="3">3 - Bueno</option><option value="2">2 - Regular</option><option value="1">1 - Malo</option></select><label>Comentario</label><textarea id="comentario">Muy bueno</textarea><button type="submit">Enviar calificación</button></form><h3>Resultado</h3><div id="resultado" class="resultado">Sin envíos todavía.</div></div>
<div class="card"><div class="topbar"><h2>🗺️ Mapa</h2><button id="btnVerTodosMapa" type="button" class="small-btn">Ver todos</button></div><div id="map"></div></div></div>
<div><div class="card"><div class="topbar"><h2>🔍 Buscar lugares</h2><button id="btnRecargar" type="button" class="small-btn">Recargar</button></div><div class="filters"><div><label>Buscar</label><input type="text" id="buscar" placeholder="Ej: ceviche"></div><div><label>Sector</label><select id="filtro_sector"><option value="">Todos</option></select></div><div><label>Categoría</label><select id="filtro_categoria"><option value="">Todas</option></select></div></div></div>
<div class="card"><h2>📊 Dashboard BI</h2><div id="dashboard_resumen" class="lugares-grid"></div><h3>Promedio por categoría</h3><div id="dashboard_categorias" class="resultado"></div><h3>Calificaciones por sector</h3><div id="dashboard_sectores" class="resultado"></div></div>
<div class="card"><h2>🏆 Top lugares</h2><div id="top_lugares" class="lugares-grid"></div></div><div class="card"><h2>📍 Todos los lugares</h2><div id="lista_lugares" class="lugares-grid"></div></div><div class="card"><h2>💬 Detalle y comentarios</h2><div id="detalle_lugar" class="resultado">Selecciona un lugar.</div><div id="comentarios"></div></div>
</div></div></div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
let lugaresCache=[],topCache=[],currentLugarId=null,map,markersLayer,markers={},usuarioLogueado=null;
function estrellas(v){const n=Math.round(Number(v||0));return "★".repeat(n)+"☆".repeat(5-n);}
function escapeHtml(t){if(t===null||t===undefined)return "";return String(t).replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;").replaceAll("'","&#039;");}
async function fetchJSON(url){const r=await fetch(url);return await r.json();}
function initMap(){map=L.map("map").setView([-2.170998,-79.922359],12);L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",{attribution:"&copy; OpenStreetMap contributors"}).addTo(map);markersLayer=L.layerGroup().addTo(map);}
function pintarMapa(lugares){markersLayer.clearLayers();markers={};const puntos=[];lugares.forEach(l=>{if(l.latitud&&l.longitud){const lat=Number(l.latitud),lng=Number(l.longitud);puntos.push([lat,lng]);const marker=L.marker([lat,lng]).addTo(markersLayer);marker.bindPopup(`<strong>${escapeHtml(l.nombre)}</strong><br>${escapeHtml(l.categoria||"Sin categoría")}<br>${escapeHtml(l.sector||"Sin sector")}<br>⭐ ${l.promedio_calificacion??"Sin calificar"}`);marker.on("click",()=>seleccionarLugar(l.id));markers[l.id]=marker;}});if(puntos.length>1)map.fitBounds(puntos,{padding:[40,40]});}
async function cargarUsuarios(){const usuarios=await fetchJSON("/usuarios");const s=document.getElementById("usuario_id");s.innerHTML="";usuarios.forEach(u=>{const o=document.createElement("option");o.value=u.id;o.textContent=`${u.nombre} (${u.email})`;s.appendChild(o);});}
async function cargarCategorias(){const data=await fetchJSON("/categorias");const s=document.getElementById("filtro_categoria");s.innerHTML='<option value="">Todas</option>';data.forEach(x=>{const o=document.createElement("option");o.value=x.nombre;o.textContent=x.nombre;s.appendChild(o);});}
async function cargarSectores(){const data=await fetchJSON("/sectores");const s=document.getElementById("filtro_sector");s.innerHTML='<option value="">Todos</option>';data.forEach(x=>{const o=document.createElement("option");o.value=x.sector;o.textContent=x.sector;s.appendChild(o);});}
async function cargarLugaresParaFormulario(){const s=document.getElementById("lugar_id");s.innerHTML="";lugaresCache.forEach(l=>{const o=document.createElement("option");o.value=l.id;o.textContent=`${l.nombre} | ${l.categoria||"Sin categoría"} | ${l.sector||""}`;s.appendChild(o);});}
function renderLugarCard(l,isTop=false){return `<div class="lugar-card ${currentLugarId===l.id?"active":""}" onclick="seleccionarLugar(${l.id})">${isTop?'<div class="pill">Top</div>':""}<div class="pill">${escapeHtml(l.categoria||"Sin categoría")}</div><div class="pill">${escapeHtml(l.sector||"Sin sector")}</div><h3>${escapeHtml(l.nombre)}</h3><div class="stars">${estrellas(l.promedio_calificacion||0)}</div><p><strong>Promedio:</strong> ${l.promedio_calificacion??"Sin calificar"}</p><p><strong>Calificaciones:</strong> ${l.total_calificaciones??0}</p><p class="muted">${escapeHtml(l.direccion||"")}</p><p>${escapeHtml(l.descripcion||"")}</p></div>`;}
function pintarLugares(l){document.getElementById("lista_lugares").innerHTML=l.length?l.map(x=>renderLugarCard(x)).join(""):"<p>No se encontraron lugares.</p>";}
function pintarTop(l){document.getElementById("top_lugares").innerHTML=l.length?l.map(x=>renderLugarCard(x,true)).join(""):"<p>No hay lugares calificados.</p>";}
async function cargarTop(){topCache=await fetchJSON("/lugares/top");pintarTop(topCache);}
async function cargarDashboard(){const r=await fetchJSON("/dashboard/resumen"),c=await fetchJSON("/dashboard/categorias"),s=await fetchJSON("/dashboard/sectores");document.getElementById("dashboard_resumen").innerHTML=`<div class="lugar-card kpi"><h3>${r.total_lugares}</h3><p>Total lugares</p></div><div class="lugar-card kpi"><h3>${r.total_usuarios}</h3><p>Total usuarios</p></div><div class="lugar-card kpi"><h3>${r.total_calificaciones}</h3><p>Total calificaciones</p></div><div class="lugar-card kpi"><h3>${r.promedio_general??"N/A"}</h3><p>Promedio general</p></div>`;document.getElementById("dashboard_categorias").innerHTML=c.map(x=>`<p><strong>${escapeHtml(x.categoria)}</strong> | Promedio: ${x.promedio??"N/A"} | Calificaciones: ${x.total_calificaciones}</p>`).join("");document.getElementById("dashboard_sectores").innerHTML=s.map(x=>`<p><strong>${escapeHtml(x.sector)}</strong> | Promedio: ${x.promedio??"N/A"} | Calificaciones: ${x.total_calificaciones}</p>`).join("");}
async function cargarLugares(){const q=buscar.value.trim(),sector=filtro_sector.value,categoria=filtro_categoria.value;const p=new URLSearchParams();if(q)p.append("q",q);if(sector)p.append("sector",sector);if(categoria)p.append("categoria",categoria);lugaresCache=await fetchJSON(`/lugares?${p.toString()}`);pintarLugares(lugaresCache);pintarMapa(lugaresCache);await cargarLugaresParaFormulario();if(lugaresCache.length&&!lugaresCache.some(x=>x.id===currentLugarId))await seleccionarLugar(lugaresCache[0].id);}
async function seleccionarLugar(id){currentLugarId=Number(id);const d=await fetchJSON(`/lugares/${id}`),com=await fetchJSON(`/lugares/${id}/comentarios`);lugar_id.value=String(id);detalle_lugar.innerHTML=`<h3>${escapeHtml(d.nombre)}</h3><p><strong>Categoría:</strong> ${escapeHtml(d.categoria||"Sin categoría")}</p><p><strong>Sector:</strong> ${escapeHtml(d.sector||"Sin sector")}</p><p><strong>Dirección:</strong> ${escapeHtml(d.direccion||"")}</p><p><strong>Ciudad:</strong> ${escapeHtml(d.ciudad||"")}</p><p><strong>Promedio:</strong> ${d.promedio_calificacion??"Sin calificar"} <span class="stars">${estrellas(d.promedio_calificacion||0)}</span></p><p><strong>Total:</strong> ${d.total_calificaciones??0}</p><p>${escapeHtml(d.descripcion||"")}</p>`;comentarios.innerHTML=com.length?com.map(c=>`<div class="comentario"><strong>${escapeHtml(c.usuario)}</strong><div class="stars">${estrellas(c.puntuacion)}</div><div>${escapeHtml(c.comentario||"")}</div><div class="muted">${escapeHtml(c.fecha_calificacion||"")}</div></div>`).join(""):"<p>No hay comentarios todavía.</p>";pintarLugares(lugaresCache);pintarTop(topCache);if(d.latitud&&d.longitud){map.setView([Number(d.latitud),Number(d.longitud)],15);if(markers[id])markers[id].openPopup();}}
async function login(){const res=await fetch("/auth/login",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({email:login_email.value,password:login_password.value})});const data=await res.json();if(res.ok){usuarioLogueado=data;usuario_id.value=data.id;localStorage.setItem("usuario",JSON.stringify(data));auth_result.innerHTML=`<span class="success">✔ Bienvenido ${escapeHtml(data.nombre)}</span>`;}else{auth_result.innerHTML=`<span class="error">✘ ${escapeHtml(data.error)}</span>`;}}
async function register(){const res=await fetch("/auth/register",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({nombre:reg_nombre.value,email:reg_email.value,password:reg_password.value})});const data=await res.json();if(res.ok){usuarioLogueado=data;localStorage.setItem("usuario",JSON.stringify(data));auth_result.innerHTML=`<span class="success">✔ Usuario creado: ${escapeHtml(data.nombre)}</span>`;await cargarUsuarios();usuario_id.value=data.id;await cargarDashboard();}else{auth_result.innerHTML=`<span class="error">✘ ${escapeHtml(data.error)}</span>`;}}
function cargarSesionGuardada(){const user=localStorage.getItem("usuario");if(user){const data=JSON.parse(user);usuarioLogueado=data;usuario_id.value=data.id;auth_result.innerHTML=`<span class="success">✔ Sesión activa: ${escapeHtml(data.nombre)}</span>`;}}
function logout(){localStorage.removeItem("usuario");usuarioLogueado=null;auth_result.innerHTML="Sin sesión iniciada.";location.reload();}
async function enviarCalificacion(e){e.preventDefault();const payload={usuario_id:parseInt(usuario_id.value),lugar_id:parseInt(lugar_id.value),puntuacion:parseInt(puntuacion.value),comentario:comentario.value};const res=await fetch("/calificaciones",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});const data=await res.json();resultado.innerHTML=res.ok?`<span class="success">✔ ${escapeHtml(data.message)}</span>`:`<span class="error">✘ ${escapeHtml(data.error||"Error")}</span>`;await cargarTop();await cargarLugares();await cargarDashboard();await seleccionarLugar(payload.lugar_id);}
function verTodosMapa(){const puntos=lugaresCache.filter(l=>l.latitud&&l.longitud).map(l=>[Number(l.latitud),Number(l.longitud)]);if(puntos.length>1)map.fitBounds(puntos,{padding:[40,40]});}
function conectarEventos(){form.addEventListener("submit",enviarCalificacion);buscar.addEventListener("input",cargarLugares);filtro_sector.addEventListener("change",cargarLugares);filtro_categoria.addEventListener("change",cargarLugares);btnRecargar.addEventListener("click",async()=>{await cargarTop();await cargarLugares();await cargarDashboard();});btnVerTodosMapa.addEventListener("click",verTodosMapa);lugar_id.addEventListener("change",function(){seleccionarLugar(this.value);});}
async function init(){initMap();conectarEventos();await cargarUsuarios();cargarSesionGuardada();await cargarCategorias();await cargarSectores();await cargarTop();await cargarDashboard();await cargarLugares();setTimeout(()=>map.invalidateSize(),300);}
init();
</script></body></html>
"""

@app.route("/")
def index():
    return redirect("/formulario")

@app.route("/formulario")
def formulario():
    return render_template_string(HTML)

@app.route("/usuarios")
def get_usuarios():
    conn=get_connection(); cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT id, nombre, email FROM usuarios ORDER BY id;")
    data=cur.fetchall(); cur.close(); conn.close()
    return json_response(data)

@app.route("/categorias")
def get_categorias():
    conn=get_connection(); cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT id, nombre FROM categorias ORDER BY nombre;")
    data=cur.fetchall(); cur.close(); conn.close()
    return json_response(data)

@app.route("/sectores")
def get_sectores():
    conn=get_connection(); cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT DISTINCT sector FROM lugares WHERE sector IS NOT NULL AND sector <> '' ORDER BY sector;")
    data=cur.fetchall(); cur.close(); conn.close()
    return json_response(data)

@app.route("/lugares")
def get_lugares():
    q=request.args.get("q","").strip(); sector=request.args.get("sector","").strip(); categoria=request.args.get("categoria","").strip()
    conn=get_connection(); cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    query="SELECT * FROM vw_lugares_resumen WHERE 1=1"; params=[]
    if q: query+=" AND nombre ILIKE %s"; params.append(f"%{q}%")
    if sector: query+=" AND sector ILIKE %s"; params.append(sector)
    if categoria: query+=" AND categoria ILIKE %s"; params.append(categoria)
    query+=" ORDER BY promedio_calificacion DESC NULLS LAST, total_calificaciones DESC, nombre ASC;"
    cur.execute(query, params); data=cur.fetchall(); cur.close(); conn.close()
    return json_response(data)

@app.route("/lugares/top")
def get_top_lugares():
    conn=get_connection(); cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM vw_lugares_resumen ORDER BY promedio_calificacion DESC NULLS LAST, total_calificaciones DESC, nombre ASC LIMIT 10;")
    data=cur.fetchall(); cur.close(); conn.close()
    return json_response(data)

@app.route("/lugares/<int:id_lugar>")
def get_lugar_por_id(id_lugar):
    conn=get_connection(); cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT l.id,l.nombre,c.nombre AS categoria,l.direccion,l.sector,l.ciudad,l.descripcion,l.latitud,l.longitud,
               ROUND(AVG(cal.puntuacion),2) AS promedio_calificacion, COUNT(cal.id) AS total_calificaciones
        FROM lugares l
        LEFT JOIN categorias c ON l.categoria_id = c.id
        LEFT JOIN calificaciones cal ON cal.lugar_id = l.id
        WHERE l.id = %s
        GROUP BY l.id,l.nombre,c.nombre,l.direccion,l.sector,l.ciudad,l.descripcion,l.latitud,l.longitud;
    """,(id_lugar,))
    data=cur.fetchone(); cur.close(); conn.close()
    if data is None: return json_response({"error":"Lugar no encontrado"},404)
    return json_response(data)

@app.route("/lugares/<int:id_lugar>/comentarios")
def get_comentarios_por_lugar(id_lugar):
    conn=get_connection(); cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT cal.id, u.nombre AS usuario, cal.puntuacion, cal.comentario, cal.fecha_calificacion
        FROM calificaciones cal JOIN usuarios u ON cal.usuario_id = u.id
        WHERE cal.lugar_id = %s
        ORDER BY cal.fecha_calificacion DESC;
    """,(id_lugar,))
    data=cur.fetchall(); cur.close(); conn.close()
    return json_response(data)

@app.route("/calificaciones", methods=["POST"])
def crear_calificacion():
    conn=None; cur=None
    try:
        data=request.get_json()
        usuario_id=data.get("usuario_id"); lugar_id=data.get("lugar_id"); puntuacion=data.get("puntuacion"); comentario=data.get("comentario","")
        if usuario_id is None or lugar_id is None or puntuacion is None:
            return json_response({"error":"usuario_id, lugar_id y puntuacion son obligatorios"},400)
        if not isinstance(puntuacion, int) or puntuacion < 1 or puntuacion > 5:
            return json_response({"error":"puntuacion debe ser un entero entre 1 y 5"},400)
        conn=get_connection(); cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT id FROM usuarios WHERE id = %s;", (usuario_id,))
        if cur.fetchone() is None: return json_response({"error":"Usuario no existe"},404)
        cur.execute("SELECT id FROM lugares WHERE id = %s;", (lugar_id,))
        if cur.fetchone() is None: return json_response({"error":"Lugar no existe"},404)
        cur.execute("""
            INSERT INTO calificaciones (usuario_id,lugar_id,puntuacion,comentario)
            VALUES (%s,%s,%s,%s)
            ON CONFLICT (usuario_id,lugar_id)
            DO UPDATE SET puntuacion=EXCLUDED.puntuacion, comentario=EXCLUDED.comentario, fecha_calificacion=CURRENT_TIMESTAMP
            RETURNING id, usuario_id, lugar_id, puntuacion, comentario, fecha_calificacion;
        """,(usuario_id,lugar_id,puntuacion,comentario))
        calificacion=cur.fetchone(); conn.commit()
        return json_response({"message":"Calificación guardada correctamente","data":calificacion},201)
    except Exception as e:
        if conn: conn.rollback()
        return json_response({"error":str(e)},500)
    finally:
        if cur: cur.close()
        if conn: conn.close()

@app.route("/auth/register", methods=["POST"])
def register():
    conn=None; cur=None
    try:
        data=request.get_json()
        nombre=data.get("nombre"); email=data.get("email"); password=data.get("password")
        if not nombre or not email or not password:
            return json_response({"error":"Nombre, email y contraseña son obligatorios"},400)
        password_hash=hashlib.sha256(password.encode()).hexdigest()
        conn=get_connection(); cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("INSERT INTO usuarios (nombre,email,password_hash) VALUES (%s,%s,%s) RETURNING id,nombre,email;", (nombre,email,password_hash))
        user=cur.fetchone(); conn.commit()
        return json_response(user,201)
    except psycopg2.errors.UniqueViolation:
        if conn: conn.rollback()
        return json_response({"error":"Ese email ya existe"},400)
    except Exception as e:
        if conn: conn.rollback()
        return json_response({"error":str(e)},500)
    finally:
        if cur: cur.close()
        if conn: conn.close()

@app.route("/auth/login", methods=["POST"])
def login():
    conn=None; cur=None
    try:
        data=request.get_json()
        email=data.get("email"); password=data.get("password")
        if not email or not password:
            return json_response({"error":"Email y contraseña son obligatorios"},400)
        password_hash=hashlib.sha256(password.encode()).hexdigest()
        conn=get_connection(); cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT id,nombre,email FROM usuarios WHERE email = %s AND password_hash = %s;", (email,password_hash))
        user=cur.fetchone()
        if user is None: return json_response({"error":"Credenciales incorrectas"},401)
        return json_response(user)
    except Exception as e:
        return json_response({"error":str(e)},500)
    finally:
        if cur: cur.close()
        if conn: conn.close()

@app.route("/dashboard/resumen")
def dashboard_resumen():
    conn=get_connection(); cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT (SELECT COUNT(*) FROM lugares) AS total_lugares,
               (SELECT COUNT(*) FROM usuarios) AS total_usuarios,
               (SELECT COUNT(*) FROM calificaciones) AS total_calificaciones,
               (SELECT ROUND(AVG(puntuacion),2) FROM calificaciones) AS promedio_general;
    """)
    data=cur.fetchone(); cur.close(); conn.close()
    return json_response(data)

@app.route("/dashboard/categorias")
def dashboard_categorias():
    conn=get_connection(); cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT c.nombre AS categoria, ROUND(AVG(cal.puntuacion),2) AS promedio, COUNT(cal.id) AS total_calificaciones
        FROM categorias c
        LEFT JOIN lugares l ON l.categoria_id = c.id
        LEFT JOIN calificaciones cal ON cal.lugar_id = l.id
        GROUP BY c.id, c.nombre
        ORDER BY promedio DESC NULLS LAST, total_calificaciones DESC;
    """)
    data=cur.fetchall(); cur.close(); conn.close()
    return json_response(data)

@app.route("/dashboard/sectores")
def dashboard_sectores():
    conn=get_connection(); cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT l.sector, ROUND(AVG(cal.puntuacion),2) AS promedio, COUNT(cal.id) AS total_calificaciones
        FROM lugares l
        LEFT JOIN calificaciones cal ON cal.lugar_id = l.id
        WHERE l.sector IS NOT NULL AND l.sector <> ''
        GROUP BY l.sector
        ORDER BY total_calificaciones DESC, promedio DESC NULLS LAST;
    """)
    data=cur.fetchall(); cur.close(); conn.close()
    return json_response(data)

if __name__ == "__main__":
    app.run(debug=True)
