-- ============================================================
-- Tablas para Investigaciones, Evidencias, Reservas y AGE — Presidencial 2026
-- ============================================================

-- Investigaciones: cada fila es UN grupo de mesas a investigar (1 par de candidatos)
CREATE TABLE IF NOT EXISTS investigaciones_presidencial_2026 (
    id              BIGSERIAL PRIMARY KEY,
    idmesa          INTEGER NOT NULL,
    nomdepto        VARCHAR(80),
    nommipio        VARCHAR(80),
    nompuesto       VARCHAR(200),
    mesa            INTEGER,
    coddepto        INTEGER,
    codmipio        INTEGER,
    codzona         INTEGER,
    codpuesto       VARCHAR(10),
    -- Lado A
    codcandidato1   INTEGER,
    nom_candidato1  VARCHAR(200),
    codpartido1     INTEGER,
    nom_partido1    VARCHAR(200),
    preconteo1      INTEGER,
    dia_valor1      INTEGER,
    diferencia1     INTEGER,
    -- Lado B
    codcandidato2   INTEGER,
    nom_candidato2  VARCHAR(200),
    codpartido2     INTEGER,
    nom_partido2    VARCHAR(200),
    preconteo2      INTEGER,
    dia_valor2      INTEGER,
    diferencia2     INTEGER,
    -- Meta
    numdia          INTEGER,
    estado_reclamacion VARCHAR(30) DEFAULT 'pendiente',
    usuario_creacion VARCHAR(50),
    usuario_asignado VARCHAR(50),
    fecha_creacion  TIMESTAMP DEFAULT NOW(),
    UNIQUE (idmesa, codcandidato1, codcandidato2)
);
CREATE INDEX IF NOT EXISTS idx_invpres_idmesa ON investigaciones_presidencial_2026(idmesa);
CREATE INDEX IF NOT EXISTS idx_invpres_cand1  ON investigaciones_presidencial_2026(codcandidato1);
CREATE INDEX IF NOT EXISTS idx_invpres_cand2  ON investigaciones_presidencial_2026(codcandidato2);
CREATE INDEX IF NOT EXISTS idx_invpres_asig   ON investigaciones_presidencial_2026(usuario_asignado);
CREATE INDEX IF NOT EXISTS idx_invpres_depto  ON investigaciones_presidencial_2026(coddepto);

-- Evidencias por mesa
CREATE TABLE IF NOT EXISTS evidencias_presidencial_2026 (
    id              BIGSERIAL PRIMARY KEY,
    idmesa          INTEGER NOT NULL,
    codcandidato    INTEGER,
    codpartido      INTEGER,
    tipo_formulario VARCHAR(20),     -- E14 / E24 / NO_E14 / SIN_EVIDENCIA / OTRO
    observacion     TEXT,
    nombre_archivo  VARCHAR(300),
    ruta_archivo    VARCHAR(600),
    imagen_base64   TEXT,            -- inline para vista previa rápida
    usuario         VARCHAR(50),
    fecha           TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_evpres_mesa ON evidencias_presidencial_2026(idmesa);
CREATE INDEX IF NOT EXISTS idx_evpres_cand ON evidencias_presidencial_2026(idmesa, codcandidato);
CREATE INDEX IF NOT EXISTS idx_evpres_tipo ON evidencias_presidencial_2026(tipo_formulario);

-- Reservas de mesa (lock por usuario)
CREATE TABLE IF NOT EXISTS reservas_mesa_presidencial_2026 (
    id              BIGSERIAL PRIMARY KEY,
    idmesa          INTEGER NOT NULL,
    lado            INTEGER NOT NULL DEFAULT 1,   -- 1 o 2 (para comparación)
    codcandidato    INTEGER,
    codpartido      INTEGER,
    usuario         VARCHAR(50) NOT NULL,
    fecha           TIMESTAMP DEFAULT NOW(),
    UNIQUE (idmesa, lado, codcandidato)
);
CREATE INDEX IF NOT EXISTS idx_respres_mesa ON reservas_mesa_presidencial_2026(idmesa);
CREATE INDEX IF NOT EXISTS idx_respres_user ON reservas_mesa_presidencial_2026(usuario);

-- AGE: Acta General de Escrutinio (observaciones por mesa, importadas de RNEC)
CREATE TABLE IF NOT EXISTS age_presidencial_2026 (
    id              BIGSERIAL PRIMARY KEY,
    coddepto        VARCHAR(3),
    codmipio        VARCHAR(4),
    codzona         VARCHAR(3),
    codpuesto       VARCHAR(3),
    mesa            VARCHAR(10),
    tipo_observacion VARCHAR(50),    -- modificacion, observacion_mesa, etc.
    observacion     TEXT,
    archivo_origen  VARCHAR(300),
    fecha_cargue    TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_agepres_geo ON age_presidencial_2026(coddepto, codmipio, codzona, codpuesto, mesa);

-- Asignaciones (mesas asignadas a analistas)
CREATE TABLE IF NOT EXISTS asignaciones_presidencial_2026 (
    id              BIGSERIAL PRIMARY KEY,
    idmesa          INTEGER NOT NULL,
    codcandidato    INTEGER,
    codpartido      INTEGER,
    usuario_asignado VARCHAR(50) NOT NULL,
    estado          VARCHAR(20) DEFAULT 'pendiente',  -- pendiente / completada
    usuario_asigno  VARCHAR(50),
    fecha_asignacion TIMESTAMP DEFAULT NOW(),
    fecha_completado TIMESTAMP,
    UNIQUE (idmesa, codcandidato, usuario_asignado)
);
CREATE INDEX IF NOT EXISTS idx_asigpres_user ON asignaciones_presidencial_2026(usuario_asignado);
CREATE INDEX IF NOT EXISTS idx_asigpres_mesa ON asignaciones_presidencial_2026(idmesa);
