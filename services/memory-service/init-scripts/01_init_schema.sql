-- ============================================================
-- CASIOPY MEMORY SERVICE - DATABASE INITIALIZATION
-- ============================================================

-- Habilitar extensiones necesarias
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================
-- CAPA 0: CORE MEMORY (Inmutable)
-- ============================================================

CREATE TABLE core_memory (
    id SERIAL PRIMARY KEY,
    category VARCHAR(50) NOT NULL,
    key VARCHAR(100) NOT NULL,
    value TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    is_mutable BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(category, key)
);

CREATE INDEX idx_core_memory_category ON core_memory(category);
CREATE INDEX idx_core_memory_mutable ON core_memory(is_mutable);

-- ============================================================
-- SESSIONS: Agrupación de conversaciones
-- ============================================================

CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(100),
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    ended_at TIMESTAMP WITH TIME ZONE,
    total_turns INTEGER DEFAULT 0,
    avg_quality_score FLOAT,
    dominant_topics TEXT[],
    session_summary TEXT,
    opt_out_training BOOLEAN DEFAULT false
);

CREATE INDEX idx_sessions_started ON sessions(started_at DESC);
CREATE INDEX idx_sessions_user ON sessions(user_id);

-- ============================================================
-- INTERACTIONS: Registro de cada interacción
-- ============================================================

CREATE TABLE interactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL,
    user_id VARCHAR(100),
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Input
    input_text TEXT NOT NULL,
    input_method VARCHAR(20), -- 'text', 'voice'
    input_emotion VARCHAR(50),

    -- Output
    output_text TEXT NOT NULL,
    output_emotion VARCHAR(50),
    output_confidence FLOAT,

    -- Context
    conversation_turn INTEGER,
    previous_topic VARCHAR(100),

    -- Metadata
    latency_ms INTEGER,
    model_version VARCHAR(50),

    -- Embeddings (pgvector) - all-MiniLM-L6-v2 = 384 dimensiones
    input_embedding vector(384),
    output_embedding vector(384),

    -- Quality & Classification
    quality_score FLOAT,
    is_training_ready BOOLEAN DEFAULT false,
    training_export_id INTEGER,

    CONSTRAINT interactions_session_fk FOREIGN KEY (session_id)
        REFERENCES sessions(id) ON DELETE CASCADE
);

CREATE INDEX idx_interactions_timestamp ON interactions(timestamp DESC);
CREATE INDEX idx_interactions_session ON interactions(session_id);
CREATE INDEX idx_interactions_training_ready ON interactions(is_training_ready) WHERE is_training_ready = true;
CREATE INDEX idx_interactions_quality ON interactions(quality_score DESC) WHERE quality_score IS NOT NULL;

-- Índice de vectores para búsqueda de similitud
CREATE INDEX idx_interactions_input_embedding ON interactions
    USING ivfflat (input_embedding vector_cosine_ops)
    WITH (lists = 100);

CREATE INDEX idx_interactions_output_embedding ON interactions
    USING ivfflat (output_embedding vector_cosine_ops)
    WITH (lists = 100);

-- ============================================================
-- TOPICS: Temas emergentes detectados
-- ============================================================

CREATE TABLE topics (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    embedding vector(384),
    occurrence_count INTEGER DEFAULT 0,
    last_seen TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_topics_occurrence ON topics(occurrence_count DESC);
CREATE INDEX idx_topics_last_seen ON topics(last_seen DESC);

-- ============================================================
-- FEEDBACK: Retroalimentación del usuario
-- ============================================================

CREATE TABLE feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    interaction_id UUID NOT NULL,
    feedback_type VARCHAR(50), -- 'positive', 'negative', 'correction'
    user_reaction VARCHAR(50), -- 'liked', 'disliked', 'neutral'
    corrected_response TEXT,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    CONSTRAINT feedback_interaction_fk FOREIGN KEY (interaction_id)
        REFERENCES interactions(id) ON DELETE CASCADE
);

CREATE INDEX idx_feedback_interaction ON feedback(interaction_id);
CREATE INDEX idx_feedback_type ON feedback(feedback_type);

-- ============================================================
-- TRAINING_EXPORTS: Registro de exportaciones para fine-tuning
-- ============================================================

CREATE TABLE training_exports (
    id SERIAL PRIMARY KEY,
    export_date TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    export_type VARCHAR(50), -- 'personality_initial', 'episodic_weekly'
    format VARCHAR(50), -- 'chatml', 'alpaca', 'hermes'
    total_samples INTEGER,
    quality_threshold FLOAT,
    date_range_start TIMESTAMP WITH TIME ZONE,
    date_range_end TIMESTAMP WITH TIME ZONE,
    file_path TEXT,
    model_version VARCHAR(50),
    lora_rank INTEGER,
    training_completed BOOLEAN DEFAULT false,
    notes TEXT
);

CREATE INDEX idx_training_exports_date ON training_exports(export_date DESC);
CREATE INDEX idx_training_exports_type ON training_exports(export_type);

-- ============================================================
-- LORA_VERSIONS: Control de versiones de LoRA
-- ============================================================

CREATE TABLE lora_versions (
    id SERIAL PRIMARY KEY,
    version_name VARCHAR(100) UNIQUE NOT NULL,
    lora_type VARCHAR(50) NOT NULL, -- 'personality_core', 'episodic', 'technical'
    training_export_id INTEGER,
    file_path TEXT NOT NULL,
    base_model VARCHAR(100),
    lora_rank INTEGER,
    lora_alpha INTEGER,
    training_samples INTEGER,
    validation_passed BOOLEAN DEFAULT false,
    is_active BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    notes TEXT,

    CONSTRAINT lora_training_export_fk FOREIGN KEY (training_export_id)
        REFERENCES training_exports(id) ON DELETE SET NULL
);

CREATE INDEX idx_lora_versions_type ON lora_versions(lora_type);
CREATE INDEX idx_lora_versions_active ON lora_versions(is_active) WHERE is_active = true;

-- ============================================================
-- PERSONALITY_METRICS: Seguimiento de dimensiones de personalidad
-- ============================================================

CREATE TABLE personality_metrics (
    id SERIAL PRIMARY KEY,
    measured_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    sarcasm_level FLOAT,
    friendliness FLOAT,
    verbosity FLOAT,
    technical_depth FLOAT,
    humor_frequency FLOAT,
    sample_size INTEGER,
    week_number INTEGER,
    notes TEXT
);

CREATE INDEX idx_personality_metrics_date ON personality_metrics(measured_at DESC);

-- ============================================================
-- TRIGGERS: Actualización automática de timestamps
-- ============================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_core_memory_updated_at
    BEFORE UPDATE ON core_memory
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================
-- VISTAS ÚTILES
-- ============================================================

-- Vista de estadísticas de sesiones
CREATE VIEW session_stats AS
SELECT
    s.id,
    s.user_id,
    s.started_at,
    s.ended_at,
    s.total_turns,
    s.avg_quality_score,
    COUNT(i.id) as actual_interactions,
    COUNT(CASE WHEN i.is_training_ready THEN 1 END) as training_ready_count,
    AVG(i.quality_score) as calculated_avg_quality,
    MAX(i.timestamp) as last_interaction
FROM sessions s
LEFT JOIN interactions i ON s.id = i.session_id
GROUP BY s.id;

-- Vista de interacciones listas para entrenamiento
CREATE VIEW training_ready_interactions AS
SELECT
    i.id,
    i.session_id,
    i.timestamp,
    i.input_text,
    i.output_text,
    i.input_emotion,
    i.output_emotion,
    i.quality_score,
    s.user_id,
    s.opt_out_training
FROM interactions i
JOIN sessions s ON i.session_id = s.id
WHERE i.is_training_ready = true
  AND i.quality_score >= 0.6
  AND s.opt_out_training = false
  AND i.training_export_id IS NULL
ORDER BY i.timestamp DESC;

-- ============================================================
-- COMENTARIOS
-- ============================================================

COMMENT ON TABLE core_memory IS 'Capa 0: Memoria inmutable - identidad, creador, gustos permanentes';
COMMENT ON TABLE sessions IS 'Agrupación de conversaciones por sesión de usuario';
COMMENT ON TABLE interactions IS 'Registro completo de cada interacción input/output';
COMMENT ON TABLE topics IS 'Temas emergentes detectados automáticamente';
COMMENT ON TABLE feedback IS 'Retroalimentación y correcciones del usuario';
COMMENT ON TABLE training_exports IS 'Registro de datasets exportados para fine-tuning';
COMMENT ON TABLE lora_versions IS 'Control de versiones de adaptadores LoRA';
COMMENT ON TABLE personality_metrics IS 'Evolución de dimensiones de personalidad en el tiempo';
