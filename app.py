"""
Auditor Escrutinio Presidencial 2026
Backend Flask minimo: sesion + login + healthcheck.
Módulos se van migrando del Auditor Congreso uno por uno.
"""
from flask import Flask, jsonify, send_from_directory, request, session
import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
import os
import hashlib
import time
import sys
import logging

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logging.basicConfig(level=logging.INFO, stream=sys.stderr,
                    format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger('presidencial')

app = Flask(__name__, static_folder='public')
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'tyse-escrutinio-presidencial-2026-secretkey')
app.config['MAX_CONTENT_LENGTH'] = 4 * 1024 * 1024 * 1024
app.config['MAX_FORM_MEMORY_SIZE'] = 100 * 1024 * 1024
app.config['MAX_FORM_PARTS'] = 1000

# ==================== BD ====================
DB_CONFIG = {
    'host':     os.environ.get('DB_HOST',     '192.168.0.54'),
    'port':     int(os.environ.get('DB_PORT', 5432)),
    'user':     os.environ.get('DB_USER',     'postgres'),
    'password': os.environ.get('DB_PASSWORD', 'postgres'),
    'dbname':   os.environ.get('DB_NAME',     'AuditorEscrutinioPresidencial2026_PROD'),
}

_conninfo = psycopg.conninfo.make_conninfo(**DB_CONFIG)
def _configure_conn(conn):
    conn.row_factory = dict_row

db_pool = ConnectionPool(_conninfo, min_size=2, max_size=10, open=False, configure=_configure_conn)
try:
    db_pool.open()
    logger.info(f"[bd] Pool conectado a {DB_CONFIG['host']}/{DB_CONFIG['dbname']}")
except Exception as e:
    logger.error(f"[bd] No se pudo abrir pool: {e}")

def get_db_connection():
    return db_pool.connection()

def hash_password(p):
    return hashlib.sha256(p.encode('utf-8')).hexdigest()

# ==================== MIDDLEWARE ====================
@app.before_request
def log_y_actividad():
    if request.path.startswith('/api/') and 'task-status' not in request.path:
        logger.info(f"[REQ] {request.method} {request.path} from={request.remote_addr} user={session.get('user_id','?')}")
    if 'user_id' in session:
        session['last_activity'] = time.time()

@app.after_request
def no_cache(response):
    if response.content_type and ('text/html' in response.content_type or 'application/javascript' in response.content_type):
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response

# ==================== STATIC ====================
@app.route('/')
def index():
    return send_from_directory('public', 'index.html')

@app.route('/<path:filename>')
def static_files(filename):
    return send_from_directory('public', filename)

# ==================== AUTH ====================
@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.get_json() or {}
        cedula = data.get('cedula', '').strip()
        contrasena = data.get('contrasena', '')
        if not cedula or not contrasena:
            return jsonify({'success': False, 'error': 'Cédula y contraseña son requeridos'}), 400
        hashed = hash_password(contrasena)
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('''
                    SELECT u.id, u.cedula, u.nombres, u.apellidos, u.correo,
                           u.id_perfil, p.nombre AS perfil_nombre
                    FROM usuarios u
                    LEFT JOIN perfiles p ON p.id = u.id_perfil
                    WHERE u.cedula = %s AND u.contrasena = %s
                ''', (cedula, hashed))
                user = cur.fetchone()
        if not user:
            return jsonify({'success': False, 'error': 'Cédula o contraseña incorrectos'}), 401

        session['user_id']   = user['id']
        session['cedula']    = user['cedula']
        session['nombres']   = user['nombres']
        session['apellidos'] = user['apellidos']
        session['perfil']    = user['perfil_nombre']
        session['id_perfil'] = user['id_perfil']
        session['last_activity'] = time.time()
        return jsonify({'success': True, 'data': {
            'id': user['id'], 'cedula': user['cedula'],
            'nombres': user['nombres'], 'apellidos': user['apellidos'],
            'perfil': user['perfil_nombre'], 'id_perfil': user['id_perfil']
        }})
    except Exception as e:
        logger.exception("[login] error")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'success': True})

@app.route('/api/session', methods=['GET'])
def get_session():
    if 'user_id' not in session:
        return jsonify({'success': False, 'session_expired': True}), 401
    return jsonify({'success': True, 'data': {
        'id': session['user_id'], 'cedula': session.get('cedula'),
        'nombres': session.get('nombres'), 'apellidos': session.get('apellidos'),
        'perfil': session.get('perfil'), 'id_perfil': session.get('id_perfil')
    }})

# ==================== DIVIPOL ====================
def _require_session():
    if 'user_id' not in session:
        return jsonify({'success': False, 'session_expired': True}), 401
    return None

@app.route('/api/divipol', methods=['GET'])
def divipol_listar():
    """Listado adaptativo según filtros (mismo shape que Congreso)."""
    err = _require_session()
    if err: return err
    coddepto = request.args.get('coddepto', type=int)
    codmipio = request.args.get('codmipio', type=int)
    codzona  = request.args.get('codzona', type=int)
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                if codzona is not None:
                    cur.execute('''
                        SELECT codpuesto, nompuesto,
                               COALESCE(potmasculino,0) AS hombre,
                               COALESCE(potfemenino,0)  AS mujeres,
                               COALESCE(pottotal,0)     AS total_potencial,
                               COALESCE(nummesas,0)     AS mesas
                        FROM divipol_presidencial_2026
                        WHERE clase='P' AND coddepto=%s AND codmipio=%s AND codzona=%s
                        ORDER BY codpuesto
                    ''', (coddepto, codmipio, codzona))
                elif codmipio is not None:
                    cur.execute('''
                        SELECT codzona,
                               COALESCE(SUM(potmasculino),0) AS hombre,
                               COALESCE(SUM(potfemenino),0)  AS mujeres,
                               COALESCE(SUM(pottotal),0)     AS total_potencial,
                               COALESCE(SUM(nummesas),0)     AS mesas
                        FROM divipol_presidencial_2026
                        WHERE clase='P' AND coddepto=%s AND codmipio=%s
                        GROUP BY codzona
                        ORDER BY codzona
                    ''', (coddepto, codmipio))
                elif coddepto is not None:
                    cur.execute('''
                        SELECT m.codmipio, m.nommipio,
                               (SELECT COALESCE(SUM(potmasculino),0) FROM divipol_presidencial_2026
                                WHERE clase='P' AND coddepto=m.coddepto AND codmipio=m.codmipio) AS hombre,
                               (SELECT COALESCE(SUM(potfemenino),0) FROM divipol_presidencial_2026
                                WHERE clase='P' AND coddepto=m.coddepto AND codmipio=m.codmipio) AS mujeres,
                               (SELECT COALESCE(SUM(pottotal),0) FROM divipol_presidencial_2026
                                WHERE clase='P' AND coddepto=m.coddepto AND codmipio=m.codmipio) AS total_potencial,
                               (SELECT COALESCE(SUM(nummesas),0) FROM divipol_presidencial_2026
                                WHERE clase='P' AND coddepto=m.coddepto AND codmipio=m.codmipio) AS mesas
                        FROM divipol_presidencial_2026 m
                        WHERE m.clase='M' AND m.coddepto=%s
                        ORDER BY m.codmipio
                    ''', (coddepto,))
                else:
                    cur.execute('''
                        SELECT d.coddepto, d.nomdepto,
                               (SELECT COALESCE(SUM(potmasculino),0) FROM divipol_presidencial_2026
                                WHERE clase='P' AND coddepto=d.coddepto) AS hombre,
                               (SELECT COALESCE(SUM(potfemenino),0) FROM divipol_presidencial_2026
                                WHERE clase='P' AND coddepto=d.coddepto) AS mujeres,
                               (SELECT COALESCE(SUM(pottotal),0) FROM divipol_presidencial_2026
                                WHERE clase='P' AND coddepto=d.coddepto) AS total_potencial,
                               (SELECT COALESCE(SUM(nummesas),0) FROM divipol_presidencial_2026
                                WHERE clase='P' AND coddepto=d.coddepto) AS mesas
                        FROM divipol_presidencial_2026 d
                        WHERE d.clase='D'
                        ORDER BY d.coddepto
                    ''')
                rows = cur.fetchall()
        return jsonify({'success': True, 'data': rows})
    except Exception as e:
        logger.exception('[divipol]')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/divipol/resumen', methods=['GET'])
def divipol_resumen():
    err = _require_session()
    if err: return err
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('''
                    SELECT
                      COUNT(*) FILTER (WHERE clase='D') AS deptos,
                      COUNT(*) FILTER (WHERE clase='M') AS municipios,
                      COUNT(*) FILTER (WHERE clase='Z') AS zonas,
                      COUNT(*) FILTER (WHERE clase='P') AS puestos,
                      COALESCE(SUM(nummesas) FILTER (WHERE clase='P'), 0) AS mesas,
                      COALESCE(SUM(pottotal) FILTER (WHERE clase='P'), 0) AS potencial
                    FROM divipol_presidencial_2026
                ''')
                row = cur.fetchone()
        return jsonify({'success': True, 'data': row})
    except Exception as e:
        logger.exception('[divipol/resumen]')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/divipol/departamentos', methods=['GET'])
def divipol_departamentos():
    err = _require_session()
    if err: return err
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Devolver depto con totales agregados
                cur.execute('''
                    SELECT d.coddepto, d.nomdepto,
                           COALESCE((SELECT COUNT(*) FROM divipol_presidencial_2026
                                     WHERE clase='M' AND coddepto = d.coddepto), 0) AS municipios,
                           COALESCE((SELECT SUM(nummesas) FROM divipol_presidencial_2026
                                     WHERE clase='P' AND coddepto = d.coddepto), 0) AS mesas,
                           COALESCE((SELECT SUM(pottotal) FROM divipol_presidencial_2026
                                     WHERE clase='P' AND coddepto = d.coddepto), 0) AS potencial
                    FROM divipol_presidencial_2026 d
                    WHERE d.clase='D'
                    ORDER BY d.coddepto
                ''')
                rows = cur.fetchall()
        return jsonify({'success': True, 'data': rows})
    except Exception as e:
        logger.exception('[divipol/departamentos]')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/divipol/municipios', methods=['GET'])
def divipol_municipios():
    err = _require_session()
    if err: return err
    coddepto = request.args.get('coddepto', type=int)
    if coddepto is None:
        return jsonify({'success': False, 'error': 'coddepto requerido'}), 400
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('''
                    SELECT m.coddepto, m.codmipio, m.nommipio,
                           COALESCE((SELECT COUNT(*) FROM divipol_presidencial_2026
                                     WHERE clase='Z' AND coddepto=m.coddepto AND codmipio=m.codmipio), 0) AS zonas,
                           COALESCE((SELECT COUNT(*) FROM divipol_presidencial_2026
                                     WHERE clase='P' AND coddepto=m.coddepto AND codmipio=m.codmipio), 0) AS puestos,
                           COALESCE((SELECT SUM(nummesas) FROM divipol_presidencial_2026
                                     WHERE clase='P' AND coddepto=m.coddepto AND codmipio=m.codmipio), 0) AS mesas,
                           COALESCE((SELECT SUM(pottotal) FROM divipol_presidencial_2026
                                     WHERE clase='P' AND coddepto=m.coddepto AND codmipio=m.codmipio), 0) AS potencial
                    FROM divipol_presidencial_2026 m
                    WHERE m.clase='M' AND m.coddepto=%s
                    ORDER BY m.codmipio
                ''', (coddepto,))
                rows = cur.fetchall()
        return jsonify({'success': True, 'data': rows})
    except Exception as e:
        logger.exception('[divipol/municipios]')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/divipol/zonas', methods=['GET'])
def divipol_zonas():
    err = _require_session()
    if err: return err
    coddepto = request.args.get('coddepto', type=int)
    codmipio = request.args.get('codmipio', type=int)
    if coddepto is None or codmipio is None:
        return jsonify({'success': False, 'error': 'coddepto y codmipio requeridos'}), 400
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('''
                    SELECT z.coddepto, z.codmipio, z.codzona,
                           COALESCE((SELECT COUNT(*) FROM divipol_presidencial_2026
                                     WHERE clase='P' AND coddepto=z.coddepto AND codmipio=z.codmipio AND codzona=z.codzona), 0) AS puestos,
                           COALESCE((SELECT SUM(nummesas) FROM divipol_presidencial_2026
                                     WHERE clase='P' AND coddepto=z.coddepto AND codmipio=z.codmipio AND codzona=z.codzona), 0) AS mesas,
                           COALESCE((SELECT SUM(pottotal) FROM divipol_presidencial_2026
                                     WHERE clase='P' AND coddepto=z.coddepto AND codmipio=z.codmipio AND codzona=z.codzona), 0) AS potencial
                    FROM divipol_presidencial_2026 z
                    WHERE z.clase='Z' AND z.coddepto=%s AND z.codmipio=%s
                    ORDER BY z.codzona
                ''', (coddepto, codmipio))
                rows = cur.fetchall()
        return jsonify({'success': True, 'data': rows})
    except Exception as e:
        logger.exception('[divipol/zonas]')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/divipol/puestos', methods=['GET'])
def divipol_puestos():
    err = _require_session()
    if err: return err
    coddepto = request.args.get('coddepto', type=int)
    codmipio = request.args.get('codmipio', type=int)
    codzona  = request.args.get('codzona', type=int)
    if coddepto is None or codmipio is None or codzona is None:
        return jsonify({'success': False, 'error': 'coddepto, codmipio, codzona requeridos'}), 400
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('''
                    SELECT iddivipol, coddepto, codmipio, codzona, codpuesto,
                           nompuesto, nummesas, potfemenino, potmasculino, pottotal,
                           jal, nomjal
                    FROM divipol_presidencial_2026
                    WHERE clase='P' AND coddepto=%s AND codmipio=%s AND codzona=%s
                    ORDER BY codpuesto
                ''', (coddepto, codmipio, codzona))
                rows = cur.fetchall()
        return jsonify({'success': True, 'data': rows})
    except Exception as e:
        logger.exception('[divipol/puestos]')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/divipol/mesas', methods=['GET'])
def divipol_mesas():
    err = _require_session()
    if err: return err
    iddivipol = request.args.get('iddivipol', type=int)
    if iddivipol is None:
        return jsonify({'success': False, 'error': 'iddivipol requerido'}), 400
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('''
                    SELECT idmesa, iddivipol, mesa, jornada
                    FROM divipolmesa_presidencial_2026
                    WHERE iddivipol=%s
                    ORDER BY mesa
                ''', (iddivipol,))
                rows = cur.fetchall()
        return jsonify({'success': True, 'data': rows})
    except Exception as e:
        logger.exception('[divipol/mesas]')
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== MMV PRECONTEO ====================
from datetime import date

@app.route('/api/mmv-preconteo/historial', methods=['GET'])
def mmv_preconteo_historial():
    err = _require_session()
    if err: return err
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('''
                    SELECT nombrearchivo, fecha, registros, estado, usuario
                    FROM control_mmv_presidencial_2026
                    ORDER BY fecha DESC, nombrearchivo
                ''')
                rows = cur.fetchall()
        return jsonify({'success': True, 'data': rows})
    except Exception as e:
        logger.exception('[mmv/historial]')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/mmv-preconteo/verificar', methods=['POST'])
def mmv_preconteo_verificar():
    err = _require_session()
    if err: return err
    try:
        data = request.get_json() or {}
        nombre = data.get('nombrearchivo', '')
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('''
                    SELECT nombrearchivo, fecha, registros, estado
                    FROM control_mmv_presidencial_2026
                    WHERE nombrearchivo = %s
                ''', (nombre,))
                row = cur.fetchone()
        if row:
            return jsonify({'success': True, 'existe': True, 'data': row})
        return jsonify({'success': True, 'existe': False})
    except Exception as e:
        logger.exception('[mmv/verificar]')
        return jsonify({'success': False, 'error': str(e)}), 500

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
PROCESADO_FOLDER = os.path.join(UPLOAD_FOLDER, 'PROCESADO')
os.makedirs(PROCESADO_FOLDER, exist_ok=True)

import re as _re
def _extraer_depto(nombre_archivo, primera_linea=''):
    """Extrae código de depto del nombre (patrón _<dd>_) o de la primera línea (primeros 2 chars)."""
    m = _re.search(r'_(\d{2})_', nombre_archivo)
    if m:
        return m.group(1)
    if primera_linea and len(primera_linea) >= 2 and primera_linea[:2].isdigit():
        return primera_linea[:2]
    return '00'  # depto desconocido

@app.route('/api/mmv-preconteo/cargar', methods=['POST'])
def mmv_preconteo_cargar():
    err = _require_session()
    if err: return err
    try:
        if 'archivo' not in request.files:
            return jsonify({'success': False, 'error': 'No se envió ningún archivo'}), 400
        archivo = request.files['archivo']
        if not archivo.filename:
            return jsonify({'success': False, 'error': 'Nombre de archivo vacío'}), 400

        nombre = archivo.filename
        tiene_encab = request.form.get('tiene_encabezado', 'true') == 'true'

        # Validar duplicado ANTES de procesar
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    'SELECT fecha, registros FROM control_mmv_presidencial_2026 WHERE nombrearchivo = %s',
                    (nombre,))
                ya = cur.fetchone()
        if ya:
            return jsonify({
                'success': False,
                'error': f'El archivo "{nombre}" ya fue cargado el {ya["fecha"]} con {ya["registros"]:,} registros. No se permite cargarlo nuevamente.',
                'duplicado': True,
                'data': {'fecha': str(ya['fecha']), 'registros': ya['registros']}
            }), 409

        contenido_bytes = archivo.read()
        contenido = contenido_bytes.decode('utf-8', errors='replace')
        lineas = [l for l in contenido.replace('\r', '').split('\n') if l.strip()]
        if tiene_encab and lineas:
            lineas = lineas[1:]
        registros = len(lineas)
        usuario = session.get('cedula', '')

        # Determinar depto y guardar copia en PROCESADO/<depto>/
        primera = lineas[0] if lineas else ''
        depto = _extraer_depto(nombre, primera)
        depto_dir = os.path.join(PROCESADO_FOLDER, depto)
        os.makedirs(depto_dir, exist_ok=True)
        ruta_dest = os.path.join(depto_dir, nombre)
        with open(ruta_dest, 'wb') as fout:
            fout.write(contenido_bytes)

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('''
                    INSERT INTO control_mmv_presidencial_2026 (nombrearchivo, fecha, registros, estado, usuario)
                    VALUES (%s, %s, %s, 0, %s)
                ''', (nombre, date.today(), registros, usuario))
                if lineas:
                    cur.executemany(
                        'INSERT INTO preconteo_cargue_presidencial_2026 (dato, archivo) VALUES (%s, %s)',
                        [(l.strip(), nombre) for l in lineas]
                    )
                conn.commit()

        return jsonify({
            'success': True,
            'message': f'Archivo "{nombre}" cargado: {registros:,} registros. Copia guardada en PROCESADO/{depto}/.',
            'data': {'nombrearchivo': nombre, 'fecha': date.today().isoformat(),
                     'registros': registros, 'estado': 0,
                     'depto': depto, 'ruta_procesado': f'PROCESADO/{depto}/{nombre}'}
        })
    except Exception as e:
        logger.exception('[mmv/cargar]')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/mmv-preconteo/eliminar-batch', methods=['POST'])
def mmv_preconteo_eliminar_batch():
    """Elimina múltiples archivos en una sola operación."""
    err = _require_session()
    if err: return err
    try:
        data = request.get_json() or {}
        archivos = data.get('archivos') or []
        if not archivos or not isinstance(archivos, list):
            return jsonify({'success': False, 'error': 'Lista de archivos requerida'}), 400

        eliminados = 0
        archivos_fisicos_borrados = 0
        errores = []

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('DELETE FROM preconteo_cargue_presidencial_2026 WHERE archivo = ANY(%s)', (archivos,))
                cur.execute('DELETE FROM preconteo_presidencial_2026 WHERE archivo = ANY(%s)', (archivos,))
                cur.execute('DELETE FROM control_mmv_presidencial_2026 WHERE nombrearchivo = ANY(%s)', (archivos,))
                eliminados = cur.rowcount
                conn.commit()

        # Borrar copias físicas
        for nombre in archivos:
            depto = _extraer_depto(nombre)
            ruta = os.path.join(PROCESADO_FOLDER, depto, nombre)
            if os.path.exists(ruta):
                try:
                    os.remove(ruta)
                    archivos_fisicos_borrados += 1
                except OSError as ex:
                    errores.append(f'{nombre}: {ex}')

        return jsonify({
            'success': True,
            'eliminados_bd': eliminados,
            'archivos_fisicos_borrados': archivos_fisicos_borrados,
            'errores': errores,
            'message': f'{eliminados} archivo(s) eliminados de la BD, {archivos_fisicos_borrados} copia(s) físicas borradas.'
        })
    except Exception as e:
        logger.exception('[mmv/eliminar-batch]')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/mmv-preconteo/<path:nombrearchivo>', methods=['DELETE'])
def mmv_preconteo_eliminar(nombrearchivo):
    err = _require_session()
    if err: return err
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('DELETE FROM preconteo_cargue_presidencial_2026 WHERE archivo = %s', (nombrearchivo,))
                cur.execute('DELETE FROM preconteo_presidencial_2026 WHERE archivo = %s', (nombrearchivo,))
                cur.execute('DELETE FROM control_mmv_presidencial_2026 WHERE nombrearchivo = %s', (nombrearchivo,))
                conn.commit()
        # Eliminar copia física en PROCESADO/<depto>/
        depto = _extraer_depto(nombrearchivo)
        ruta_dest = os.path.join(PROCESADO_FOLDER, depto, nombrearchivo)
        if os.path.exists(ruta_dest):
            try: os.remove(ruta_dest)
            except OSError: pass
        return jsonify({'success': True, 'message': f'Archivo "{nombrearchivo}" eliminado.'})
    except Exception as e:
        logger.exception('[mmv/eliminar]')
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== PROCESAR MMV (parser fixed-width) ====================
def _parse_mmv_line(linea):
    """
    Parsea una línea fixed-width MMV Preconteo Presidencial (38 chars).
      coddepto(2) codmipio(3) zona(2) puesto(2) mesa(6) codjal(2)
      comunicado(4) codcircunscripcion(1) codpartido(5) codcandidato(3) votos(8)
    """
    if len(linea) < 38:
        return None
    try:
        return {
            'coddepto':           int(linea[0:2]),
            'codmipio':           int(linea[2:5]),
            'codzona':            int(linea[5:7]),
            'codpuesto':          linea[7:9],
            'mesa':               int(linea[9:15]),
            'codjal':             int(linea[15:17] or 0),
            'comunicado':         int(linea[17:21] or 0),
            'codcircunscripcion': int(linea[21:22] or 0),
            'codpartido':         int(linea[22:27] or 0),
            'codcandidato':       int(linea[27:30] or 0),
            'votos':              int(linea[30:38] or 0),
        }
    except (ValueError, IndexError):
        return None

@app.route('/api/mmv-preconteo/procesar/<path:nombrearchivo>', methods=['POST'])
def mmv_preconteo_procesar(nombrearchivo):
    """Parsea líneas raw del archivo y las mete estructuradas en preconteo_presidencial_2026."""
    err = _require_session()
    if err: return err
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    'SELECT estado FROM control_mmv_presidencial_2026 WHERE nombrearchivo = %s',
                    (nombrearchivo,))
                row = cur.fetchone()
                if not row:
                    return jsonify({'success': False, 'error': 'Archivo no encontrado en historial'}), 404
                if row['estado'] == 1:
                    return jsonify({'success': False, 'error': 'El archivo ya fue procesado.'}), 409

                # Limpiar eventuales restos
                cur.execute('DELETE FROM preconteo_presidencial_2026 WHERE archivo = %s', (nombrearchivo,))

                # Leer todas las líneas raw
                cur.execute(
                    'SELECT dato FROM preconteo_cargue_presidencial_2026 WHERE archivo = %s ORDER BY id',
                    (nombrearchivo,))
                lineas = [r['dato'] for r in cur.fetchall()]

                # Parsear
                rows_validos = []
                rows_invalidos = 0
                for ln in lineas:
                    p = _parse_mmv_line(ln)
                    if p is None:
                        rows_invalidos += 1
                        continue
                    rows_validos.append((
                        p['coddepto'], p['codmipio'], p['codzona'], p['codpuesto'],
                        p['mesa'], p['comunicado'], p['codpartido'], p['codcandidato'],
                        p['votos'], nombrearchivo
                    ))

                # Bulk insert
                if rows_validos:
                    with cur.copy(
                        "COPY preconteo_presidencial_2026 (coddepto, codmipio, codzona, codpuesto, mesa, boletin, codpartido, codcandidato, votos, archivo) FROM STDIN"
                    ) as copy:
                        for r in rows_validos:
                            copy.write_row(r)

                # Marcar como procesado
                cur.execute(
                    'UPDATE control_mmv_presidencial_2026 SET estado = 1 WHERE nombrearchivo = %s',
                    (nombrearchivo,))
                conn.commit()

        return jsonify({
            'success': True,
            'message': f'Archivo "{nombrearchivo}" procesado.',
            'data': {
                'lineas_raw': len(lineas),
                'lineas_validas': len(rows_validos),
                'lineas_invalidas': rows_invalidos,
            }
        })
    except Exception as e:
        logger.exception('[mmv/procesar]')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/mmv-preconteo/procesar-todos', methods=['POST'])
def mmv_preconteo_procesar_todos():
    """Procesa todos los archivos con estado = 0."""
    err = _require_session()
    if err: return err
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT nombrearchivo FROM control_mmv_presidencial_2026 WHERE estado = 0 ORDER BY fecha, nombrearchivo")
                pendientes = [r['nombrearchivo'] for r in cur.fetchall()]
        procesados = 0
        errores = []
        for nombre in pendientes:
            try:
                # Reusa la lógica del endpoint individual
                with app.test_request_context():
                    pass
                with get_db_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute('DELETE FROM preconteo_presidencial_2026 WHERE archivo = %s', (nombre,))
                        cur.execute(
                            'SELECT dato FROM preconteo_cargue_presidencial_2026 WHERE archivo = %s ORDER BY id',
                            (nombre,))
                        lineas = [r['dato'] for r in cur.fetchall()]
                        rows_validos = []
                        for ln in lineas:
                            p = _parse_mmv_line(ln)
                            if p is None: continue
                            rows_validos.append((
                                p['coddepto'], p['codmipio'], p['codzona'], p['codpuesto'],
                                p['mesa'], p['comunicado'], p['codpartido'], p['codcandidato'],
                                p['votos'], nombre))
                        if rows_validos:
                            with cur.copy(
                                "COPY preconteo_presidencial_2026 (coddepto, codmipio, codzona, codpuesto, mesa, boletin, codpartido, codcandidato, votos, archivo) FROM STDIN"
                            ) as copy:
                                for r in rows_validos:
                                    copy.write_row(r)
                        cur.execute(
                            'UPDATE control_mmv_presidencial_2026 SET estado = 1 WHERE nombrearchivo = %s',
                            (nombre,))
                        conn.commit()
                procesados += 1
            except Exception as ex:
                errores.append(f'{nombre}: {ex}')
        return jsonify({
            'success': True,
            'procesados': procesados,
            'pendientes_antes': len(pendientes),
            'errores': errores,
            'message': f'Procesados {procesados} de {len(pendientes)} archivo(s) pendiente(s).'
        })
    except Exception as e:
        logger.exception('[mmv/procesar-todos]')
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== MMV ESCRUTINIO ====================
import tempfile, csv as _csv_mod, time as _time_mod

def _detectar_separador(ruta_archivo):
    """Devuelve ';' o ',' según primera línea no-encabezado."""
    try:
        with open(ruta_archivo, 'r', encoding='utf-8', errors='replace') as f:
            for _ in range(2):
                line = f.readline()
                if line and (';' in line or ',' in line):
                    return ';' if ';' in line else ','
        return ';'
    except Exception:
        return ';'

def _crear_particion_si_falta(cur, facceso):
    """Crea partición de escrutinio_presidencial_2026 para la facceso dada."""
    nombre_p = 'escrutiniopres_' + facceso.replace('-', '')
    cur.execute("SELECT 1 FROM pg_class WHERE relname = %s", (nombre_p,))
    if not cur.fetchone():
        cur.execute(
            f"CREATE TABLE {nombre_p} PARTITION OF escrutinio_presidencial_2026 FOR VALUES IN ('{facceso}')"
        )
        logger.info(f"[escrutinio] partición creada: {nombre_p}")

@app.route('/api/escrutinio/historial', methods=['GET'])
def escrutinio_historial():
    err = _require_session()
    if err: return err
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('''
                    SELECT id, facceso, nombrearchivo, registros, fecha, usuario_cargue,
                           tiempo_carga, estado, tamano_mb
                    FROM control_escrutinio_presidencial_2026
                    ORDER BY facceso DESC, nombrearchivo
                ''')
                rows = cur.fetchall()
        return jsonify({'success': True, 'data': rows})
    except Exception as e:
        logger.exception('[escrutinio/historial]')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/escrutinio/verificar', methods=['POST'])
def escrutinio_verificar():
    err = _require_session()
    if err: return err
    try:
        d = request.get_json() or {}
        nombre = d.get('nombrearchivo', '')
        facceso = d.get('facceso', '')
        if not nombre or not facceso:
            return jsonify({'success': False, 'error': 'nombrearchivo y facceso requeridos'}), 400
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    'SELECT facceso, registros, fecha FROM control_escrutinio_presidencial_2026 WHERE nombrearchivo = %s AND facceso = %s',
                    (nombre, facceso))
                row = cur.fetchone()
        if row:
            return jsonify({'success': True, 'existe': True, 'data': row})
        return jsonify({'success': True, 'existe': False})
    except Exception as e:
        logger.exception('[escrutinio/verificar]')
        return jsonify({'success': False, 'error': str(e)}), 500

def _poblar_seguimiento_dia(facceso):
    """Invoca fn_poblar_escrutinio_presidencial al terminar la carga del día."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT fn_poblar_escrutinio_presidencial(%s::date)", (facceso,))
                msg = cur.fetchone()
                conn.commit()
        logger.info(f"[seguimiento] {msg}")
        return msg
    except Exception as ex:
        logger.exception('[seguimiento]')
        return f'Error pobloando seguimiento: {ex}'

def _procesar_csv_a_bd(ruta_csv, nombre_archivo, facceso, tiene_encab):
    """Lee CSV streaming → COPY a tabla. Devuelve dict con stats."""
    t0 = _time_mod.time()
    sep = _detectar_separador(ruta_csv)
    tamano_mb = round(os.path.getsize(ruta_csv) / (1024 * 1024), 2)

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            _crear_particion_si_falta(cur, facceso)

            cols = ('facceso, idregistro, codcorporacion, nomcorporacion, '
                    'codcircunscripcion, nomcircunscripcion, coddepto, nomdepto, '
                    'codmipio, nommipio, codzona, nomzona, codpuesto, nompuesto, '
                    'mesa, codcomuna, nomcomuna, codpartido, nompartido, '
                    'cedulacandidato, nomcandidato, codcandidato, votos, archivo')

            registros = 0
            # Auto-detección de encabezado: si la primera línea no tiene un primer campo numérico, es encabezado
            ENCAB_TOKENS = {'id', 'corporacioncodigo', 'departamentocodigo', 'municipiocodigo', 'mesa', 'totalvotos'}
            with cur.copy(f"COPY escrutinio_presidencial_2026 ({cols}) FROM STDIN") as copy:
                with open(ruta_csv, 'r', encoding='utf-8', errors='replace') as fin:
                    rdr = _csv_mod.reader(fin, delimiter=sep)
                    primera = None
                    try: primera = next(rdr)
                    except StopIteration: pass
                    if primera:
                        # ¿Es encabezado? — si los campos contienen tokens conocidos O el primero no es numérico
                        es_encab = False
                        if tiene_encab:
                            es_encab = True
                        else:
                            joined = (','.join(c.lower() for c in primera[:6]) if primera else '')
                            if any(tok in joined for tok in ENCAB_TOKENS):
                                es_encab = True
                                logger.info("[escrutinio] encabezado detectado automáticamente, saltando primera línea")
                        if not es_encab:
                            # Re-procesar la primera línea como dato
                            rows_a_procesar = [primera]
                            for r in rdr: rows_a_procesar.append(r)
                            iter_rows = rows_a_procesar
                        else:
                            iter_rows = rdr
                    else:
                        iter_rows = rdr
                    for row in iter_rows:
                        if not row or len(row) < 22:
                            continue
                        # Normalizar 22 campos del CSV RNEC
                        def _ni(v):
                            try: return int(v) if v not in ('', None) else None
                            except (ValueError, TypeError): return None
                        def _ns(v): return (v or '').strip().replace('\t', ' ')
                        try:
                            valores = [
                                facceso,
                                _ns(row[0]),            # idregistro
                                _ni(row[1]),            # codcorporacion
                                _ns(row[2]),            # nomcorporacion
                                _ni(row[3]),            # codcircunscripcion
                                _ns(row[4]),            # nomcircunscripcion
                                _ni(row[5]),            # coddepto
                                _ns(row[6]),            # nomdepto
                                _ni(row[7]),            # codmipio
                                _ns(row[8]),            # nommipio
                                _ni(row[9]),            # codzona
                                _ns(row[10]),           # nomzona
                                _ns(row[11]),           # codpuesto
                                _ns(row[12]),           # nompuesto
                                _ni(row[13]),           # mesa
                                _ns(row[14]),           # codcomuna
                                _ns(row[15]),           # nomcomuna
                                _ni(row[16]),           # codpartido
                                _ns(row[17]),           # nompartido
                                _ns(row[18]),           # cedulacandidato
                                _ns(row[19]),           # nomcandidato
                                _ni(row[20]),           # codcandidato
                                _ni(row[21]) or 0,      # votos
                                nombre_archivo,
                            ]
                            copy.write_row(valores)
                            registros += 1
                        except (IndexError, ValueError):
                            continue

            conn.commit()

    tiempo = _time_mod.time() - t0
    return {
        'registros': registros, 'tamano_mb': tamano_mb,
        'tiempo_s': round(tiempo, 1),
        'tiempo_carga': f'{int(tiempo//60)}m {int(tiempo%60)}s' if tiempo >= 60 else f'{tiempo:.1f}s',
    }

@app.route('/api/escrutinio/cargar', methods=['POST'])
def escrutinio_cargar():
    err = _require_session()
    if err: return err
    if 'archivo' not in request.files:
        return jsonify({'success': False, 'error': 'No se envió ningún archivo'}), 400
    archivo = request.files['archivo']
    if not archivo.filename:
        return jsonify({'success': False, 'error': 'Nombre de archivo vacío'}), 400
    facceso = request.form.get('facceso', '').strip()
    if not facceso:
        return jsonify({'success': False, 'error': 'Debe indicar fecha de acceso (facceso)'}), 400
    nombre = archivo.filename
    tiene_encab = request.form.get('tiene_encabezado', 'true') == 'true'

    # Validar duplicado
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    'SELECT registros, fecha FROM control_escrutinio_presidencial_2026 WHERE nombrearchivo = %s AND facceso = %s',
                    (nombre, facceso))
                ya = cur.fetchone()
        if ya:
            return jsonify({
                'success': False, 'duplicado': True,
                'error': f'El archivo "{nombre}" ya fue cargado con facceso {facceso} ({ya["registros"]:,} registros).',
                'data': {'fecha': str(ya['fecha']), 'registros': ya['registros']}
            }), 409
    except Exception as e:
        logger.exception('[escrutinio/cargar verificar]')
        return jsonify({'success': False, 'error': str(e)}), 500

    # Guardar archivo en disco temporal (streaming)
    fd, ruta_temp = tempfile.mkstemp(suffix='.csv', prefix='esc_')
    os.close(fd)
    try:
        archivo.save(ruta_temp)
        stats = _procesar_csv_a_bd(ruta_temp, nombre, facceso, tiene_encab)

        # Guardar copia en PROCESADO y registrar en control
        depto = _extraer_depto(nombre)
        depto_dir = os.path.join(PROCESADO_FOLDER, depto)
        os.makedirs(depto_dir, exist_ok=True)
        import shutil
        shutil.copy2(ruta_temp, os.path.join(depto_dir, nombre))

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('''
                    INSERT INTO control_escrutinio_presidencial_2026
                        (facceso, nombrearchivo, registros, usuario_cargue, tiempo_carga, estado, tamano_mb)
                    VALUES (%s, %s, %s, %s, %s, 1, %s)
                ''', (facceso, nombre, stats['registros'], session.get('cedula', ''),
                      stats['tiempo_carga'], stats['tamano_mb']))
                conn.commit()

        # Disparar pobladora de seguimiento para esta facceso
        seg_msg = _poblar_seguimiento_dia(facceso)

        return jsonify({
            'success': True,
            'message': f'Archivo "{nombre}" cargado: {stats["registros"]:,} registros en {stats["tiempo_carga"]} ({stats["tamano_mb"]} MB).',
            'data': {'nombrearchivo': nombre, 'facceso': facceso,
                     'registros': stats['registros'], 'tamano_mb': stats['tamano_mb'],
                     'tiempo_carga': stats['tiempo_carga'], 'depto': depto,
                     'seguimiento': seg_msg}
        })
    except Exception as e:
        logger.exception('[escrutinio/cargar]')
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if os.path.exists(ruta_temp):
            try: os.remove(ruta_temp)
            except OSError: pass

@app.route('/api/escrutinio/cargar-ruta', methods=['POST'])
def escrutinio_cargar_ruta():
    """Carga desde una ruta local (server) sin upload — para archivos grandes."""
    err = _require_session()
    if err: return err
    try:
        d = request.get_json() or {}
        ruta = d.get('ruta', '').strip()
        facceso = d.get('facceso', '').strip()
        tiene_encab = d.get('tiene_encabezado', True)
        if not ruta or not facceso:
            return jsonify({'success': False, 'error': 'ruta y facceso requeridos'}), 400
        if not os.path.exists(ruta):
            return jsonify({'success': False, 'error': f'Archivo no encontrado en server: {ruta}'}), 404
        nombre = os.path.basename(ruta)

        # Validar duplicado
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    'SELECT registros FROM control_escrutinio_presidencial_2026 WHERE nombrearchivo = %s AND facceso = %s',
                    (nombre, facceso))
                if cur.fetchone():
                    return jsonify({
                        'success': False, 'duplicado': True,
                        'error': f'El archivo "{nombre}" ya fue cargado con facceso {facceso}.'
                    }), 409

        stats = _procesar_csv_a_bd(ruta, nombre, facceso, tiene_encab)

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('''
                    INSERT INTO control_escrutinio_presidencial_2026
                        (facceso, nombrearchivo, registros, usuario_cargue, tiempo_carga, estado, tamano_mb)
                    VALUES (%s, %s, %s, %s, %s, 1, %s)
                ''', (facceso, nombre, stats['registros'], session.get('cedula', ''),
                      stats['tiempo_carga'], stats['tamano_mb']))
                conn.commit()

        return jsonify({
            'success': True,
            'message': f'Archivo "{nombre}" cargado por ruta: {stats["registros"]:,} registros en {stats["tiempo_carga"]}.',
            'data': stats
        })
    except Exception as e:
        logger.exception('[escrutinio/cargar-ruta]')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/escrutinio/eliminar-batch', methods=['POST'])
def escrutinio_eliminar_batch():
    err = _require_session()
    if err: return err
    try:
        d = request.get_json() or {}
        items = d.get('items') or []  # [{nombrearchivo, facceso}]
        if not items:
            return jsonify({'success': False, 'error': 'items requerido'}), 400
        elim = 0
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                for it in items:
                    cur.execute(
                        'DELETE FROM escrutinio_presidencial_2026 WHERE archivo = %s AND facceso = %s',
                        (it['nombrearchivo'], it['facceso']))
                    cur.execute(
                        'DELETE FROM control_escrutinio_presidencial_2026 WHERE nombrearchivo = %s AND facceso = %s',
                        (it['nombrearchivo'], it['facceso']))
                    elim += cur.rowcount
                conn.commit()
        return jsonify({'success': True, 'eliminados': elim,
                        'message': f'{elim} archivo(s) eliminados.'})
    except Exception as e:
        logger.exception('[escrutinio/eliminar-batch]')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/escrutinio/estado-por-dia', methods=['GET'])
def escrutinio_estado_dia():
    err = _require_session()
    if err: return err
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('''
                    SELECT facceso,
                           COUNT(*) AS archivos,
                           SUM(registros)::BIGINT AS total_registros,
                           SUM(tamano_mb)::NUMERIC(12,2) AS total_mb,
                           MAX(fecha) AS ultima_carga
                    FROM control_escrutinio_presidencial_2026
                    GROUP BY facceso
                    ORDER BY facceso DESC
                ''')
                rows = cur.fetchall()
        return jsonify({'success': True, 'data': rows})
    except Exception as e:
        logger.exception('[escrutinio/estado-por-dia]')
        return jsonify({'success': False, 'error': str(e)}), 500

# Etiqueta SQL para mostrar nombre de candidato con casos especiales (996/997/998)
def _nomcandidato_sql(alias_origen):
    """Devuelve expresión SQL CASE para etiqueta legible del candidato.
    alias_origen: 'p' (preconteo) o 's' (seguimiento) — la tabla con codcandidato.
    """
    return (f"CASE {alias_origen}.codcandidato "
            f"WHEN 996 THEN 'VOTO EN BLANCO' "
            f"WHEN 997 THEN 'VOTO NULO' "
            f"WHEN 998 THEN 'VOTO NO MARCADO' "
            f"ELSE COALESCE(c.nomcandidato, '—') END")

# ==================== CONSULTA VOTACIÓN PRECONTEO ====================
@app.route('/api/consulta-preconteo/filtros/departamentos', methods=['GET'])
def consulta_pre_deptos():
    err = _require_session()
    if err: return err
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT coddepto, nomdepto FROM divipol_presidencial_2026
                WHERE clase='D' ORDER BY coddepto
            """)
            return jsonify({'success': True, 'data': cur.fetchall()})

@app.route('/api/consulta-preconteo/filtros/municipios', methods=['GET'])
def consulta_pre_municipios():
    err = _require_session()
    if err: return err
    coddepto = request.args.get('coddepto', type=int)
    if coddepto is None: return jsonify({'success': True, 'data': []})
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT codmipio, nommipio FROM divipol_presidencial_2026
                WHERE clase='M' AND coddepto=%s ORDER BY codmipio
            """, (coddepto,))
            return jsonify({'success': True, 'data': cur.fetchall()})

@app.route('/api/consulta-preconteo/filtros/zonas', methods=['GET'])
def consulta_pre_zonas():
    err = _require_session()
    if err: return err
    coddepto = request.args.get('coddepto', type=int)
    codmipio = request.args.get('codmipio', type=int)
    if coddepto is None or codmipio is None:
        return jsonify({'success': True, 'data': []})
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT codzona FROM divipol_presidencial_2026
                WHERE clase='Z' AND coddepto=%s AND codmipio=%s ORDER BY codzona
            """, (coddepto, codmipio))
            return jsonify({'success': True, 'data': cur.fetchall()})

@app.route('/api/consulta-preconteo/filtros/puestos', methods=['GET'])
def consulta_pre_puestos():
    err = _require_session()
    if err: return err
    coddepto = request.args.get('coddepto', type=int)
    codmipio = request.args.get('codmipio', type=int)
    codzona  = request.args.get('codzona', type=int)
    if coddepto is None or codmipio is None:
        return jsonify({'success': True, 'data': []})
    sql = """SELECT codpuesto, nompuesto FROM divipol_presidencial_2026
             WHERE clase='P' AND coddepto=%s AND codmipio=%s"""
    params = [coddepto, codmipio]
    if codzona is not None:
        sql += ' AND codzona=%s'; params.append(codzona)
    sql += ' ORDER BY codpuesto'
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return jsonify({'success': True, 'data': cur.fetchall()})

@app.route('/api/consulta-preconteo/filtros/candidatos', methods=['GET'])
def consulta_pre_candidatos():
    err = _require_session()
    if err: return err
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT c.codcandidato, c.nomcandidato, c.codpartido, p.nompartido
                FROM candidatos_presidencial_2026 c
                LEFT JOIN partidos_presidencial_2026 p USING (codpartido)
                ORDER BY c.num_tarjeton, c.codcandidato
            """)
            return jsonify({'success': True, 'data': cur.fetchall()})

@app.route('/api/consulta-preconteo/consultar', methods=['POST'])
def consulta_pre_consultar():
    """Agregación de votos según filtros. Adapta el tipo de respuesta por nivel."""
    err = _require_session()
    if err: return err
    try:
        data = request.get_json() or {}
        cd  = data.get('coddepto')
        cm  = data.get('codmipio')
        cz  = data.get('codzona')
        cp  = data.get('codpuesto')
        ccd = data.get('codcandidato')
        nomcand_sql = _nomcandidato_sql('p')

        where, params = [], []
        if cd  is not None: where.append('p.coddepto = %s');     params.append(int(cd))
        if cm  is not None: where.append('p.codmipio = %s');     params.append(int(cm))
        if cz  is not None: where.append('p.codzona = %s');      params.append(int(cz))
        if cp  is not None: where.append('p.codpuesto = %s');    params.append(str(cp).zfill(2))
        if ccd is not None: where.append('p.codcandidato = %s'); params.append(int(ccd))
        where.append('p.votos > 0')
        where_sql = ' AND '.join(where) if where else '1=1'

        # Detectar nivel para decidir agrupación
        sin_filtros = cd is None and cm is None and cz is None and cp is None and ccd is None
        solo_cand   = ccd is not None and cd is None and cm is None and cz is None and cp is None
        depto_only  = cd is not None and cm is None and cz is None and cp is None
        mpio_only   = cd is not None and cm is not None and cz is None and cp is None
        zona_only   = cd is not None and cm is not None and cz is not None and cp is None
        puesto_only = cd is not None and cm is not None and cz is not None and cp is not None

        base_join = """preconteo_presidencial_2026 p
            LEFT JOIN candidatos_presidencial_2026 c
                   ON c.codcandidato = p.codcandidato AND c.codpartido = p.codpartido
            LEFT JOIN partidos_presidencial_2026 pt
                   ON pt.codpartido = p.codpartido"""

        # Adaptar el GROUP BY al nivel
        if sin_filtros or solo_cand:
            sql = f"""SELECT p.codcandidato,
                            {nomcand_sql} AS nomcandidato,
                            COALESCE(pt.nompartido, '—') AS nompartido,
                            SUM(p.votos) AS total_votos
                     FROM {base_join}
                     WHERE {where_sql}
                     GROUP BY p.codcandidato, c.nomcandidato, pt.nompartido
                     ORDER BY total_votos DESC LIMIT 500"""
            tipo = 'resumen_nacional' if sin_filtros else 'candidato_nacional'

        elif depto_only:
            sql = f"""SELECT p.codcandidato,
                            {nomcand_sql} AS nomcandidato,
                            COALESCE(pt.nompartido, '—') AS nompartido,
                            SUM(p.votos) AS total_votos
                     FROM {base_join}
                     WHERE {where_sql}
                     GROUP BY p.codcandidato, c.nomcandidato, pt.nompartido
                     ORDER BY total_votos DESC LIMIT 500"""
            tipo = 'por_departamento'

        elif mpio_only:
            sql = f"""SELECT p.codcandidato,
                            {nomcand_sql} AS nomcandidato,
                            COALESCE(pt.nompartido, '—') AS nompartido,
                            SUM(p.votos) AS total_votos
                     FROM {base_join}
                     WHERE {where_sql}
                     GROUP BY p.codcandidato, c.nomcandidato, pt.nompartido
                     ORDER BY total_votos DESC LIMIT 500"""
            tipo = 'por_municipio'

        elif zona_only:
            sql = f"""SELECT p.codpuesto,
                            (SELECT nompuesto FROM divipol_presidencial_2026 dv
                             WHERE dv.clase='P' AND dv.coddepto=p.coddepto
                               AND dv.codmipio=p.codmipio AND dv.codzona=p.codzona
                               AND dv.codpuesto=p.codpuesto LIMIT 1) AS nompuesto,
                            p.codcandidato,
                            {nomcand_sql} AS nomcandidato,
                            SUM(p.votos) AS total_votos
                     FROM {base_join}
                     WHERE {where_sql}
                     GROUP BY p.codpuesto, p.codcandidato, c.nomcandidato, p.coddepto, p.codmipio, p.codzona
                     ORDER BY p.codpuesto, total_votos DESC LIMIT 1000"""
            tipo = 'por_zona'

        elif puesto_only:
            sql = f"""SELECT p.mesa, p.codcandidato,
                            {nomcand_sql} AS nomcandidato,
                            COALESCE(pt.nompartido, '—') AS nompartido,
                            SUM(p.votos) AS total_votos
                     FROM {base_join}
                     WHERE {where_sql}
                     GROUP BY p.mesa, p.codcandidato, c.nomcandidato, pt.nompartido
                     ORDER BY p.mesa, total_votos DESC LIMIT 5000"""
            tipo = 'por_puesto_mesas'

        else:
            sql = f"""SELECT p.coddepto, p.codmipio, p.codzona, p.codpuesto, p.mesa,
                            p.codcandidato,
                            {nomcand_sql} AS nomcandidato,
                            SUM(p.votos) AS total_votos
                     FROM {base_join}
                     WHERE {where_sql}
                     GROUP BY p.coddepto, p.codmipio, p.codzona, p.codpuesto, p.mesa,
                              p.codcandidato, c.nomcandidato
                     ORDER BY total_votos DESC LIMIT 500"""
            tipo = 'detalle'

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()

        return jsonify({'success': True, 'tipo_resultado': tipo, 'data': rows, 'total': len(rows)})
    except Exception as e:
        logger.exception('[consulta-preconteo/consultar]')
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== INVESTIGACIONES PRESIDENCIAL ====================

@app.route('/api/investigaciones-pres/comparar', methods=['POST'])
def inv_pres_comparar():
    """Compara 2 candidatos mesa a mesa: preconteo vs último día escrutinio."""
    err = _require_session()
    if err: return err
    try:
        d = request.get_json() or {}
        codcand1 = int(d.get('codcandidato1') or 0)
        codcand2 = int(d.get('codcandidato2') or 0)
        cd = d.get('coddepto')
        cm = d.get('codmipio')
        numdia = d.get('numdia')
        solo_pierde1 = bool(d.get('solo_pierde1', False))
        solo_gana1   = bool(d.get('solo_gana1', False))
        solo_pierde2 = bool(d.get('solo_pierde2', False))
        solo_gana2   = bool(d.get('solo_gana2', False))
        filtro_recl  = d.get('filtro_reclamacion', 'todas')   # todas/con_evidencia/sin_evidencia
        pagina = max(1, int(d.get('pagina', 1)))
        por_pagina = min(2000, max(20, int(d.get('por_pagina', 100))))

        if not codcand1 or not codcand2:
            return jsonify({'success': False, 'error': 'Debe seleccionar ambos candidatos'}), 400

        ultimo = _ultimo_dia_seguimiento()
        if ultimo == 0:
            return jsonify({'success': True, 'filas': [], 'total': 0,
                            'mensaje': 'No hay días de escrutinio procesados.'})
        numdia_use = int(numdia) if numdia else ultimo
        expr = _build_ultimo_valor_expr(numdia_use)

        # Obtener nombres y partidos de los candidatos
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT codcandidato, codpartido, nomcandidato,
                           (SELECT nompartido FROM partidos_presidencial_2026 WHERE codpartido=c.codpartido) AS nompartido
                    FROM candidatos_presidencial_2026 c
                    WHERE codcandidato = ANY(%s)
                """, ([codcand1, codcand2],))
                rows = cur.fetchall()
        cand_info = {r['codcandidato']: r for r in rows}
        nom1 = (cand_info.get(codcand1) or {}).get('nomcandidato') or f'Cand {codcand1}'
        nom2 = (cand_info.get(codcand2) or {}).get('nomcandidato') or f'Cand {codcand2}'
        part1 = (cand_info.get(codcand1) or {}).get('nompartido') or '—'
        part2 = (cand_info.get(codcand2) or {}).get('nompartido') or '—'

        # Where geo
        where_geo, params_geo = [], []
        if cd is not None: where_geo.append('dv.coddepto=%s');  params_geo.append(int(cd))
        if cm is not None: where_geo.append('dv.codmipio=%s');  params_geo.append(int(cm))
        geo_sql = ' AND '.join(where_geo) if where_geo else '1=1'

        # Sub-CTE: votos por candidato por mesa (preconteo + dia)
        sql = f"""
            WITH lado1 AS (
                SELECT s.idmesa, s.preconteo, {expr} AS dia_valor
                FROM seguimiento_escrutinio_presidencial_2026 s
                WHERE s.codcandidato = %s
            ),
            lado2 AS (
                SELECT s.idmesa, s.preconteo, {expr} AS dia_valor
                FROM seguimiento_escrutinio_presidencial_2026 s
                WHERE s.codcandidato = %s
            ),
            mesas AS (
                SELECT l1.idmesa,
                       l1.preconteo AS preconteo1, l1.dia_valor AS dia_valor1,
                       (l1.dia_valor - l1.preconteo) AS diferencia1,
                       l2.preconteo AS preconteo2, l2.dia_valor AS dia_valor2,
                       (l2.dia_valor - l2.preconteo) AS diferencia2,
                       dv.coddepto, dv.nomdepto, dv.codmipio, dv.nommipio,
                       dv.codzona, dv.codpuesto, dv.nompuesto, dm.mesa
                FROM lado1 l1
                JOIN lado2 l2 ON l2.idmesa = l1.idmesa
                JOIN divipolmesa_presidencial_2026 dm ON dm.idmesa = l1.idmesa
                JOIN divipol_presidencial_2026 dv ON dv.iddivipol = dm.iddivipol AND dv.clase='P'
                WHERE {geo_sql}
            )
            SELECT *,
                (SELECT COUNT(*) FROM evidencias_presidencial_2026 e
                  WHERE e.idmesa=mesas.idmesa AND e.codcandidato=%s
                    AND COALESCE(e.tipo_formulario,'') NOT IN ('NO_E14','SIN_EVIDENCIA')) AS num_evidencias1,
                (SELECT usuario FROM evidencias_presidencial_2026 e
                  WHERE e.idmesa=mesas.idmesa AND e.codcandidato=%s
                    AND COALESCE(e.tipo_formulario,'') NOT IN ('NO_E14','SIN_EVIDENCIA')
                  ORDER BY fecha ASC LIMIT 1) AS usuario_ev1,
                (SELECT COUNT(*) FROM evidencias_presidencial_2026 e
                  WHERE e.idmesa=mesas.idmesa AND e.codcandidato=%s
                    AND COALESCE(e.tipo_formulario,'') NOT IN ('NO_E14','SIN_EVIDENCIA')) AS num_evidencias2,
                (SELECT usuario FROM evidencias_presidencial_2026 e
                  WHERE e.idmesa=mesas.idmesa AND e.codcandidato=%s
                    AND COALESCE(e.tipo_formulario,'') NOT IN ('NO_E14','SIN_EVIDENCIA')
                  ORDER BY fecha ASC LIMIT 1) AS usuario_ev2,
                (SELECT usuario FROM reservas_mesa_presidencial_2026 r
                  WHERE r.idmesa=mesas.idmesa AND r.lado=1 LIMIT 1) AS reserva1,
                (SELECT usuario FROM reservas_mesa_presidencial_2026 r
                  WHERE r.idmesa=mesas.idmesa AND r.lado=2 LIMIT 1) AS reserva2,
                (SELECT 1 FROM evidencias_presidencial_2026 e
                  WHERE e.idmesa=mesas.idmesa AND e.tipo_formulario='SIN_EVIDENCIA' LIMIT 1) AS sin_evidencia
            FROM mesas
        """

        # Filtros pierde/gana (OR)
        filtros_pg = []
        if solo_pierde1: filtros_pg.append('diferencia1 < 0')
        if solo_gana1:   filtros_pg.append('diferencia1 > 0')
        if solo_pierde2: filtros_pg.append('diferencia2 < 0')
        if solo_gana2:   filtros_pg.append('diferencia2 > 0')
        having_pg = ''
        if filtros_pg:
            sql = f"SELECT * FROM ({sql}) sub WHERE (" + ' OR '.join(filtros_pg) + ")"

        # Filtro reclamacion
        if filtro_recl == 'con_evidencia':
            sql = f"SELECT * FROM ({sql}) sub2 WHERE num_evidencias1 > 0 OR num_evidencias2 > 0"
        elif filtro_recl == 'sin_evidencia':
            sql = f"SELECT * FROM ({sql}) sub2 WHERE num_evidencias1 = 0 AND num_evidencias2 = 0 AND sin_evidencia IS NULL"

        # Total
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"SELECT COUNT(*) AS n FROM ({sql}) tot",
                            [codcand1, codcand2] + params_geo + [codcand1, codcand1, codcand2, codcand2])
                total = cur.fetchone()['n']

                # Página
                offset = (pagina - 1) * por_pagina
                sql_pag = sql + ' ORDER BY ABS(COALESCE(diferencia1,0)) + ABS(COALESCE(diferencia2,0)) DESC LIMIT %s OFFSET %s'
                cur.execute(sql_pag,
                            [codcand1, codcand2] + params_geo +
                            [codcand1, codcand1, codcand2, codcand2, por_pagina, offset])
                filas = cur.fetchall()

        return jsonify({
            'success': True,
            'total': total, 'pagina': pagina, 'por_pagina': por_pagina,
            'paginas': (total + por_pagina - 1) // por_pagina,
            'numdia': numdia_use, 'ultimo_dia': ultimo,
            'candidato1': nom1, 'partido1': part1, 'codcandidato1': codcand1,
            'candidato2': nom2, 'partido2': part2, 'codcandidato2': codcand2,
            'filas': filas
        })
    except Exception as e:
        logger.exception('[inv-pres/comparar]')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/investigaciones-pres/crear', methods=['POST'])
def inv_pres_crear():
    """Crea registros de investigación a partir de mesas comparadas."""
    err = _require_session()
    if err: return err
    try:
        d = request.get_json() or {}
        mesas = d.get('mesas') or []
        codcand1 = int(d.get('codcandidato1') or 0)
        codcand2 = int(d.get('codcandidato2') or 0)
        nom1 = d.get('candidato1', '')
        nom2 = d.get('candidato2', '')
        part1 = d.get('partido1', '')
        part2 = d.get('partido2', '')
        codpart1 = d.get('codpartido1')
        codpart2 = d.get('codpartido2')
        numdia = int(d.get('numdia') or 0)
        usuario = session.get('cedula', '')

        if not mesas or not codcand1 or not codcand2:
            return jsonify({'success': False, 'error': 'mesas + candidatos requeridos'}), 400

        creadas = 0
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                for m in mesas:
                    cur.execute("""
                        INSERT INTO investigaciones_presidencial_2026 (
                            idmesa, nomdepto, nommipio, nompuesto, mesa,
                            coddepto, codmipio, codzona, codpuesto,
                            codcandidato1, nom_candidato1, codpartido1, nom_partido1,
                            preconteo1, dia_valor1, diferencia1,
                            codcandidato2, nom_candidato2, codpartido2, nom_partido2,
                            preconteo2, dia_valor2, diferencia2,
                            numdia, usuario_creacion
                        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,
                                  %s,%s,%s,%s,%s,%s,%s,
                                  %s,%s,%s,%s,%s,%s,%s,
                                  %s,%s)
                        ON CONFLICT (idmesa, codcandidato1, codcandidato2) DO NOTHING
                    """, (m.get('idmesa'), m.get('nomdepto'), m.get('nommipio'), m.get('nompuesto'), m.get('mesa'),
                          m.get('coddepto'), m.get('codmipio'), m.get('codzona'), m.get('codpuesto'),
                          codcand1, nom1, codpart1, part1,
                          m.get('preconteo1', 0), m.get('dia_valor1', 0), m.get('diferencia1', 0),
                          codcand2, nom2, codpart2, part2,
                          m.get('preconteo2', 0), m.get('dia_valor2', 0), m.get('diferencia2', 0),
                          numdia, usuario))
                    creadas += cur.rowcount
                conn.commit()
        return jsonify({'success': True, 'creadas': creadas, 'total': len(mesas)})
    except Exception as e:
        logger.exception('[inv-pres/crear]')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/investigaciones-pres/listar-agrupadas', methods=['GET'])
def inv_pres_listar_agrupadas():
    """Lista investigaciones agrupadas por par (cand1, cand2) y depto."""
    err = _require_session()
    if err: return err
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT i.codcandidato1, i.nom_candidato1, i.codpartido1, i.nom_partido1,
                           i.codcandidato2, i.nom_candidato2, i.codpartido2, i.nom_partido2,
                           i.coddepto, MIN(i.nomdepto) AS nomdepto,
                           COUNT(*) AS num_mesas,
                           COUNT(DISTINCT i.codmipio) AS num_mpios,
                           SUM(CASE WHEN EXISTS (
                               SELECT 1 FROM evidencias_presidencial_2026 e
                               WHERE e.idmesa=i.idmesa
                                 AND e.codcandidato IN (i.codcandidato1, i.codcandidato2)
                                 AND COALESCE(e.tipo_formulario,'') NOT IN ('NO_E14','SIN_EVIDENCIA')
                           ) THEN 1 ELSE 0 END) AS mesas_con_evidencia,
                           STRING_AGG(DISTINCT i.nommipio, ', ' ORDER BY i.nommipio) AS municipios
                    FROM investigaciones_presidencial_2026 i
                    GROUP BY i.codcandidato1, i.nom_candidato1, i.codpartido1, i.nom_partido1,
                             i.codcandidato2, i.nom_candidato2, i.codpartido2, i.nom_partido2, i.coddepto
                    ORDER BY i.coddepto, num_mesas DESC
                """)
                rows = cur.fetchall()
        return jsonify({'success': True, 'data': rows, 'total': len(rows)})
    except Exception as e:
        logger.exception('[inv-pres/listar]')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/investigaciones-pres/detalle-grupo', methods=['GET'])
def inv_pres_detalle_grupo():
    """Detalle de mesas de un grupo (par candidatos × depto)."""
    err = _require_session()
    if err: return err
    try:
        coddepto = request.args.get('coddepto', type=int)
        ccd1 = request.args.get('codcandidato1', type=int)
        ccd2 = request.args.get('codcandidato2', type=int)
        pagina = max(1, int(request.args.get('pagina', 1)))
        por_pagina = min(500, max(20, int(request.args.get('por_pagina', 100))))
        if not ccd1 or not ccd2:
            return jsonify({'success': False, 'error': 'codcandidato1 y codcandidato2 requeridos'}), 400

        where = ['codcandidato1=%s', 'codcandidato2=%s']
        params = [ccd1, ccd2]
        if coddepto is not None:
            where.append('coddepto=%s'); params.append(coddepto)

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"SELECT COUNT(*) AS n FROM investigaciones_presidencial_2026 WHERE {' AND '.join(where)}", params)
                total = cur.fetchone()['n']
                offset = (pagina - 1) * por_pagina
                cur.execute(f"""
                    SELECT i.idmesa, i.coddepto, i.nomdepto, i.codmipio, i.nommipio,
                           i.codzona, i.codpuesto, i.nompuesto, i.mesa,
                           i.preconteo1, i.dia_valor1, i.diferencia1,
                           i.preconteo2, i.dia_valor2, i.diferencia2,
                           i.estado_reclamacion, i.usuario_asignado,
                           (SELECT COUNT(*) FROM evidencias_presidencial_2026 e
                             WHERE e.idmesa=i.idmesa
                               AND e.codcandidato IN (i.codcandidato1, i.codcandidato2)
                               AND COALESCE(e.tipo_formulario,'') NOT IN ('NO_E14','SIN_EVIDENCIA')) AS num_evidencias
                    FROM investigaciones_presidencial_2026 i
                    WHERE {' AND '.join(where)}
                    ORDER BY i.nommipio, i.codzona, i.codpuesto, i.mesa
                    LIMIT %s OFFSET %s
                """, params + [por_pagina, offset])
                filas = cur.fetchall()
        return jsonify({'success': True, 'data': filas, 'total': total,
                        'pagina': pagina, 'por_pagina': por_pagina,
                        'paginas': (total + por_pagina - 1) // por_pagina})
    except Exception as e:
        logger.exception('[inv-pres/detalle]')
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/investigaciones-pres/eliminar-grupo', methods=['POST'])
def inv_pres_eliminar_grupo():
    """Elimina todas las mesas de un grupo (par candidatos [× depto])."""
    err = _require_session()
    if err: return err
    try:
        d = request.get_json() or {}
        ccd1 = int(d.get('codcandidato1') or 0)
        ccd2 = int(d.get('codcandidato2') or 0)
        coddepto = d.get('coddepto')
        if not ccd1 or not ccd2:
            return jsonify({'success': False, 'error': 'candidatos requeridos'}), 400
        where = ['codcandidato1=%s', 'codcandidato2=%s']
        params = [ccd1, ccd2]
        if coddepto is not None:
            where.append('coddepto=%s'); params.append(int(coddepto))
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"DELETE FROM investigaciones_presidencial_2026 WHERE {' AND '.join(where)}", params)
                eliminadas = cur.rowcount
                conn.commit()
        return jsonify({'success': True, 'eliminadas': eliminadas})
    except Exception as e:
        logger.exception('[inv-pres/eliminar]')
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== CONSULTA VOTACIÓN ESCRUTINIO ====================

@app.route('/api/escrutinio/dias-procesados', methods=['GET'])
def escrutinio_dias_procesados():
    """Lista los días con seguimiento poblado (numdia + facceso)."""
    err = _require_session()
    if err: return err
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT numdia, facceso, procesado, fecha
                    FROM dias_escrutinio_presidencial
                    ORDER BY numdia
                """)
                rows = cur.fetchall()
        return jsonify({'success': True, 'data': rows})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/escrutinio/repoblar-seguimiento/<facceso>', methods=['POST'])
def escrutinio_repoblar_seguimiento(facceso):
    """Vuelve a invocar fn_poblar_escrutinio_presidencial para una facceso."""
    err = _require_session()
    if err: return err
    msg = _poblar_seguimiento_dia(facceso)
    return jsonify({'success': True, 'message': msg})

def _ultimo_dia_seguimiento():
    """Devuelve el último numdia con datos en seguimiento (o 0)."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COALESCE(MAX(numdia),0) AS m FROM dias_escrutinio_presidencial WHERE procesado=TRUE")
            return cur.fetchone()['m']

@app.route('/api/consulta-escrutinio/filtros/departamentos', methods=['GET'])
def consulta_esc_deptos():
    err = _require_session()
    if err: return err
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT coddepto, nomdepto FROM divipol_presidencial_2026 WHERE clase='D' ORDER BY coddepto")
            return jsonify({'success': True, 'data': cur.fetchall()})

@app.route('/api/consulta-escrutinio/filtros/municipios', methods=['GET'])
def consulta_esc_mpios():
    err = _require_session()
    if err: return err
    coddepto = request.args.get('coddepto', type=int)
    if coddepto is None: return jsonify({'success': True, 'data': []})
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT codmipio, nommipio FROM divipol_presidencial_2026 WHERE clase='M' AND coddepto=%s ORDER BY codmipio", (coddepto,))
            return jsonify({'success': True, 'data': cur.fetchall()})

@app.route('/api/consulta-escrutinio/filtros/zonas', methods=['GET'])
def consulta_esc_zonas():
    err = _require_session()
    if err: return err
    cd = request.args.get('coddepto', type=int)
    cm = request.args.get('codmipio', type=int)
    if cd is None or cm is None: return jsonify({'success': True, 'data': []})
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT codzona FROM divipol_presidencial_2026 WHERE clase='Z' AND coddepto=%s AND codmipio=%s ORDER BY codzona", (cd, cm))
            return jsonify({'success': True, 'data': cur.fetchall()})

@app.route('/api/consulta-escrutinio/filtros/puestos', methods=['GET'])
def consulta_esc_puestos():
    err = _require_session()
    if err: return err
    cd = request.args.get('coddepto', type=int)
    cm = request.args.get('codmipio', type=int)
    cz = request.args.get('codzona', type=int)
    if cd is None or cm is None: return jsonify({'success': True, 'data': []})
    sql = "SELECT codpuesto, nompuesto FROM divipol_presidencial_2026 WHERE clase='P' AND coddepto=%s AND codmipio=%s"
    params = [cd, cm]
    if cz is not None:
        sql += ' AND codzona=%s'; params.append(cz)
    sql += ' ORDER BY codpuesto'
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return jsonify({'success': True, 'data': cur.fetchall()})

@app.route('/api/consulta-escrutinio/filtros/candidatos', methods=['GET'])
def consulta_esc_candidatos():
    err = _require_session()
    if err: return err
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT codcandidato, nomcandidato, codpartido,
                       (SELECT nompartido FROM partidos_presidencial_2026 WHERE codpartido=c.codpartido LIMIT 1) AS nompartido
                FROM candidatos_presidencial_2026 c
                ORDER BY num_tarjeton, codcandidato
            """)
            return jsonify({'success': True, 'data': cur.fetchall()})

def _build_ultimo_valor_expr(numdia_max):
    """Construye COALESCE(diaN, diaN-1, ..., dia1) para tomar el último día válido."""
    if numdia_max <= 0:
        return '0'
    cols = [f'dia{i}' for i in range(numdia_max, 0, -1)]
    return f"COALESCE({','.join(cols)}, 0)"

@app.route('/api/consulta-escrutinio/consultar', methods=['POST'])
def consulta_esc_consultar():
    """Consulta votación por escrutinio: agrega según filtros. Lee de seguimiento_escrutinio_presidencial_2026."""
    err = _require_session()
    if err: return err
    try:
        d = request.get_json() or {}
        cd  = d.get('coddepto')
        cm  = d.get('codmipio')
        cz  = d.get('codzona')
        cp  = d.get('codpuesto')
        ccd = d.get('codcandidato')
        numdia = d.get('numdia')   # día específico, opcional. Si None → último

        ultimo = _ultimo_dia_seguimiento()
        if ultimo == 0:
            return jsonify({'success': True, 'data': [], 'tipo_resultado': 'sin_datos',
                            'message': 'No hay días de escrutinio procesados.'})
        if numdia is None or numdia == '':
            numdia_use = ultimo
        else:
            numdia_use = int(numdia)

        ultimo_expr = _build_ultimo_valor_expr(numdia_use)
        nomcand_sql = _nomcandidato_sql('s')

        # Join: seguimiento → divipol/mesa para geo, candidatos para nombres
        base_from = f"""seguimiento_escrutinio_presidencial_2026 s
            JOIN divipolmesa_presidencial_2026 dm ON dm.idmesa = s.idmesa
            JOIN divipol_presidencial_2026 dv ON dv.iddivipol = dm.iddivipol AND dv.clase = 'P'
            LEFT JOIN candidatos_presidencial_2026 c
                   ON c.codcandidato = s.codcandidato AND c.codpartido = s.codpartido
            LEFT JOIN partidos_presidencial_2026 pt
                   ON pt.codpartido = s.codpartido"""

        where, params = [], []
        if cd  is not None: where.append('dv.coddepto = %s');     params.append(int(cd))
        if cm  is not None: where.append('dv.codmipio = %s');     params.append(int(cm))
        if cz  is not None: where.append('dv.codzona = %s');      params.append(int(cz))
        if cp  is not None: where.append('dv.codpuesto = %s');    params.append(str(cp).zfill(2))
        if ccd is not None: where.append('s.codcandidato = %s');  params.append(int(ccd))
        where.append(f'({ultimo_expr}) > 0')
        where_sql = ' AND '.join(where)

        sin_filtros = not any([cd, cm, cz, cp, ccd])
        solo_cand   = ccd is not None and not any([cd, cm, cz, cp])
        depto_only  = cd is not None and not any([cm, cz, cp])
        mpio_only   = cd is not None and cm is not None and not any([cz, cp])
        zona_only   = cd is not None and cm is not None and cz is not None and cp is None
        puesto_only = cd is not None and cm is not None and cz is not None and cp is not None

        if sin_filtros or solo_cand:
            sql = f"""SELECT s.codcandidato,
                            {nomcand_sql} AS nomcandidato,
                            COALESCE(pt.nompartido, '—') AS nompartido,
                            SUM({ultimo_expr}) AS total_votos
                     FROM {base_from}
                     WHERE {where_sql}
                     GROUP BY s.codcandidato, c.nomcandidato, pt.nompartido
                     ORDER BY total_votos DESC LIMIT 500"""
            tipo = 'resumen_nacional' if sin_filtros else 'candidato_nacional'
        elif depto_only or mpio_only:
            sql = f"""SELECT s.codcandidato,
                            {nomcand_sql} AS nomcandidato,
                            COALESCE(pt.nompartido, '—') AS nompartido,
                            SUM({ultimo_expr}) AS total_votos
                     FROM {base_from}
                     WHERE {where_sql}
                     GROUP BY s.codcandidato, c.nomcandidato, pt.nompartido
                     ORDER BY total_votos DESC LIMIT 500"""
            tipo = 'por_departamento' if depto_only else 'por_municipio'
        elif zona_only:
            sql = f"""SELECT dv.codpuesto, dv.nompuesto, s.codcandidato,
                            {nomcand_sql} AS nomcandidato,
                            SUM({ultimo_expr}) AS total_votos
                     FROM {base_from}
                     WHERE {where_sql}
                     GROUP BY dv.codpuesto, dv.nompuesto, s.codcandidato, c.nomcandidato
                     ORDER BY dv.codpuesto, total_votos DESC LIMIT 1000"""
            tipo = 'por_zona'
        elif puesto_only:
            sql = f"""SELECT dm.mesa, s.codcandidato,
                            {nomcand_sql} AS nomcandidato,
                            COALESCE(pt.nompartido, '—') AS nompartido,
                            SUM({ultimo_expr}) AS total_votos
                     FROM {base_from}
                     WHERE {where_sql}
                     GROUP BY dm.mesa, s.codcandidato, c.nomcandidato, pt.nompartido
                     ORDER BY dm.mesa, total_votos DESC LIMIT 5000"""
            tipo = 'por_puesto_mesas'
        else:
            sql = f"""SELECT dv.coddepto, dv.codmipio, dv.codzona, dv.codpuesto, dm.mesa,
                            s.codcandidato,
                            {nomcand_sql} AS nomcandidato,
                            SUM({ultimo_expr}) AS total_votos
                     FROM {base_from}
                     WHERE {where_sql}
                     GROUP BY dv.coddepto, dv.codmipio, dv.codzona, dv.codpuesto, dm.mesa,
                              s.codcandidato, c.nomcandidato
                     ORDER BY total_votos DESC LIMIT 500"""
            tipo = 'detalle'

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()

        return jsonify({'success': True, 'tipo_resultado': tipo, 'data': rows,
                        'total': len(rows), 'numdia': numdia_use, 'ultimo_dia': ultimo})
    except Exception as e:
        logger.exception('[consulta-escrutinio/consultar]')
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== HEALTHCHECK ====================
@app.route('/api/health')
def health():
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT 1 AS ok')
                cur.fetchone()
        return jsonify({'success': True, 'db': 'ok', 'app': 'auditor-presidencial-2026'})
    except Exception as e:
        return jsonify({'success': False, 'db': 'error', 'error': str(e)}), 500

# ==================== MAIN ====================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5002))
    if '--waitress' in sys.argv:
        from waitress import serve
        logger.info(f"[main] Waitress en :{port}")
        serve(app, host='0.0.0.0', port=port, threads=8)
    else:
        logger.info(f"[main] Flask dev en :{port}")
        app.run(host='0.0.0.0', port=port, debug=True)
