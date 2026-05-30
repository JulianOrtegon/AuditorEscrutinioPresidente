-- ============================================================
-- Tablas y funciones para Seguimiento Escrutinio Presidencial 2026
-- ============================================================

-- Días de escrutinio (uno por fecha de acceso procesada)
CREATE TABLE IF NOT EXISTS dias_escrutinio_presidencial (
    numdia    INTEGER PRIMARY KEY,           -- 1, 2, 3, ...
    facceso   DATE NOT NULL UNIQUE,
    procesado BOOLEAN DEFAULT FALSE,
    fecha     TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_dias_pres_facceso ON dias_escrutinio_presidencial(facceso);

-- Seguimiento: 1 fila por (mesa, candidato), con preconteo + dia1..dia30
CREATE TABLE IF NOT EXISTS seguimiento_escrutinio_presidencial_2026 (
    id           BIGSERIAL PRIMARY KEY,
    idmesa       INTEGER NOT NULL,
    codpartido   INTEGER NOT NULL,
    codcandidato INTEGER NOT NULL,            -- 1..13 o 996/997/998
    preconteo    INTEGER DEFAULT 0,
    dia1         INTEGER, dia2  INTEGER, dia3  INTEGER, dia4  INTEGER, dia5  INTEGER,
    dia6         INTEGER, dia7  INTEGER, dia8  INTEGER, dia9  INTEGER, dia10 INTEGER,
    dia11        INTEGER, dia12 INTEGER, dia13 INTEGER, dia14 INTEGER, dia15 INTEGER,
    dia16        INTEGER, dia17 INTEGER, dia18 INTEGER, dia19 INTEGER, dia20 INTEGER,
    dia21        INTEGER, dia22 INTEGER, dia23 INTEGER, dia24 INTEGER, dia25 INTEGER,
    dia26        INTEGER, dia27 INTEGER, dia28 INTEGER, dia29 INTEGER, dia30 INTEGER,
    UNIQUE (idmesa, codpartido, codcandidato)
);
CREATE INDEX IF NOT EXISTS idx_seg_pres_mesa ON seguimiento_escrutinio_presidencial_2026(idmesa);
CREATE INDEX IF NOT EXISTS idx_seg_pres_cand ON seguimiento_escrutinio_presidencial_2026(codcandidato);

-- ============================================================
-- Función pobladora: para una fecha de acceso, asigna el numdia siguiente
-- y mete los votos en la columna diaN correspondiente.
-- ============================================================
CREATE OR REPLACE FUNCTION fn_poblar_escrutinio_presidencial(p_facceso DATE)
RETURNS text LANGUAGE plpgsql AS $$
DECLARE
    v_numdia       INTEGER;
    v_nuevas_filas INTEGER;
    v_actualizados INTEGER;
BEGIN
    -- 1. Asegurar registro en dias_escrutinio_presidencial. Si no existe → asignar siguiente numdia.
    SELECT numdia INTO v_numdia FROM dias_escrutinio_presidencial WHERE facceso = p_facceso;
    IF v_numdia IS NULL THEN
        SELECT COALESCE(MAX(numdia), 0) + 1 INTO v_numdia FROM dias_escrutinio_presidencial;
        INSERT INTO dias_escrutinio_presidencial (numdia, facceso, procesado)
        VALUES (v_numdia, p_facceso, FALSE);
    END IF;

    IF v_numdia > 30 THEN
        RETURN 'Error: máximo 30 días soportados en seguimiento (numdia=' || v_numdia || ')';
    END IF;

    -- 2. Tabla temporal con los votos del día desde escrutinio_presidencial_2026
    DROP TABLE IF EXISTS _tmp_esc_pres;
    CREATE TEMP TABLE _tmp_esc_pres AS
    SELECT dm.idmesa, e.codpartido, e.codcandidato, SUM(e.votos)::INTEGER AS votos
    FROM escrutinio_presidencial_2026 e
    JOIN divipol_presidencial_2026 d
        ON d.coddepto = e.coddepto AND d.codmipio = e.codmipio
       AND d.codzona = e.codzona  AND d.codpuesto = e.codpuesto
       AND d.clase = 'P'
    JOIN divipolmesa_presidencial_2026 dm
        ON dm.iddivipol = d.iddivipol AND dm.mesa = e.mesa
    WHERE e.facceso = p_facceso
      AND e.votos > 0
    GROUP BY dm.idmesa, e.codpartido, e.codcandidato;

    CREATE INDEX ON _tmp_esc_pres(idmesa, codpartido, codcandidato);
    ANALYZE _tmp_esc_pres;

    -- 3. Insertar filas faltantes en seguimiento
    INSERT INTO seguimiento_escrutinio_presidencial_2026 (idmesa, codpartido, codcandidato, preconteo)
    SELECT idmesa, codpartido, codcandidato, 0
    FROM _tmp_esc_pres
    ON CONFLICT (idmesa, codpartido, codcandidato) DO NOTHING;
    GET DIAGNOSTICS v_nuevas_filas = ROW_COUNT;

    -- 4. UPDATE la columna diaN correspondiente
    EXECUTE format(
        'UPDATE seguimiento_escrutinio_presidencial_2026 s
         SET %I = t.votos
         FROM _tmp_esc_pres t
         WHERE s.idmesa = t.idmesa
           AND s.codpartido = t.codpartido
           AND s.codcandidato = t.codcandidato',
        'dia' || v_numdia
    );
    GET DIAGNOSTICS v_actualizados = ROW_COUNT;

    DROP TABLE _tmp_esc_pres;

    -- 5. Marcar día procesado
    UPDATE dias_escrutinio_presidencial SET procesado = TRUE WHERE facceso = p_facceso;

    RETURN format('Día %s (%s) Presidencial: %s votos actualizados | %s filas nuevas',
                  v_numdia, p_facceso, v_actualizados, v_nuevas_filas);
END;
$$;
