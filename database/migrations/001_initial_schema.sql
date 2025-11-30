-- Planning Precedent AI - Initial Database Schema
-- For Supabase with pgvector extension
--
-- This schema is designed for semantic search across planning decisions
-- using vector similarity search with OpenAI embeddings.

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- For fuzzy text search

-- ============================================
-- PLANNING DECISIONS TABLE
-- Core table storing all planning applications
-- ============================================

CREATE TABLE IF NOT EXISTS planning_decisions (
    id BIGSERIAL PRIMARY KEY,

    -- Core identifiers
    case_reference TEXT NOT NULL UNIQUE,  -- e.g., '2023/1234/P'
    address TEXT NOT NULL,
    ward TEXT NOT NULL,
    postcode TEXT,  -- UK postcode, e.g., 'NW3 1AB'

    -- Decision information
    decision_date DATE NOT NULL,
    outcome TEXT NOT NULL CHECK (outcome IN (
        'Granted', 'Refused', 'Withdrawn', 'Pending',
        'Appeal Allowed', 'Appeal Dismissed'
    )),

    -- Application details
    application_type TEXT NOT NULL,
    development_type TEXT,
    property_type TEXT,
    description TEXT NOT NULL,

    -- Location context
    conservation_area TEXT DEFAULT 'None',
    listed_building BOOLEAN DEFAULT FALSE,
    article_4 BOOLEAN DEFAULT FALSE,

    -- Document content
    full_text TEXT,  -- Extracted text from all documents

    -- Document URLs
    decision_notice_url TEXT,
    officer_report_url TEXT,

    -- Metadata
    raw_metadata JSONB,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Indexes are defined below
    CONSTRAINT valid_case_reference CHECK (
        case_reference ~ '^\d{4}/\d{4,5}/[A-Z]+$'
    )
);

-- ============================================
-- DOCUMENT CHUNKS TABLE
-- Stores chunked text with embeddings for vector search
-- ============================================

CREATE TABLE IF NOT EXISTS document_chunks (
    id BIGSERIAL PRIMARY KEY,

    -- Link to parent decision
    decision_id BIGINT NOT NULL REFERENCES planning_decisions(id) ON DELETE CASCADE,

    -- Chunk information
    chunk_index INTEGER NOT NULL,
    text TEXT NOT NULL,
    token_count INTEGER NOT NULL,

    -- Vector embedding (3072 dimensions for text-embedding-3-large)
    embedding vector(3072),

    -- Additional metadata
    metadata JSONB,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),

    -- Ensure unique chunks per decision
    UNIQUE (decision_id, chunk_index)
);

-- ============================================
-- INDEXES FOR PERFORMANCE
-- ============================================

-- Planning Decisions Indexes
CREATE INDEX IF NOT EXISTS idx_decisions_case_ref ON planning_decisions(case_reference);
CREATE INDEX IF NOT EXISTS idx_decisions_ward ON planning_decisions(ward);
CREATE INDEX IF NOT EXISTS idx_decisions_date ON planning_decisions(decision_date DESC);
CREATE INDEX IF NOT EXISTS idx_decisions_outcome ON planning_decisions(outcome);
CREATE INDEX IF NOT EXISTS idx_decisions_dev_type ON planning_decisions(development_type);
CREATE INDEX IF NOT EXISTS idx_decisions_conservation ON planning_decisions(conservation_area);
CREATE INDEX IF NOT EXISTS idx_decisions_postcode ON planning_decisions(postcode);

-- Full-text search index on description
CREATE INDEX IF NOT EXISTS idx_decisions_description_trgm
    ON planning_decisions USING gin (description gin_trgm_ops);

-- Full-text search index on address
CREATE INDEX IF NOT EXISTS idx_decisions_address_trgm
    ON planning_decisions USING gin (address gin_trgm_ops);

-- Document Chunks Indexes
CREATE INDEX IF NOT EXISTS idx_chunks_decision ON document_chunks(decision_id);
CREATE INDEX IF NOT EXISTS idx_chunks_order ON document_chunks(decision_id, chunk_index);

-- Vector similarity search index using HNSW (faster for large datasets)
CREATE INDEX IF NOT EXISTS idx_chunks_embedding
    ON document_chunks USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- ============================================
-- FUNCTIONS FOR VECTOR SEARCH
-- ============================================

-- Main vector search function with filtering
CREATE OR REPLACE FUNCTION search_planning_decisions(
    query_embedding vector(3072),
    match_threshold float DEFAULT 0.7,
    match_count int DEFAULT 10,
    filter_wards text[] DEFAULT NULL,
    filter_outcome text DEFAULT NULL,
    filter_development_types text[] DEFAULT NULL,
    filter_conservation_areas text[] DEFAULT NULL,
    filter_date_from date DEFAULT NULL,
    filter_date_to date DEFAULT NULL
)
RETURNS TABLE (
    decision_id bigint,
    chunk_id bigint,
    chunk_text text,
    similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        pd.id AS decision_id,
        dc.id AS chunk_id,
        dc.text AS chunk_text,
        1 - (dc.embedding <=> query_embedding) AS similarity
    FROM document_chunks dc
    JOIN planning_decisions pd ON dc.decision_id = pd.id
    WHERE
        -- Similarity threshold
        1 - (dc.embedding <=> query_embedding) > match_threshold
        -- Ward filter
        AND (filter_wards IS NULL OR pd.ward = ANY(filter_wards))
        -- Outcome filter
        AND (filter_outcome IS NULL OR pd.outcome = filter_outcome)
        -- Development type filter
        AND (filter_development_types IS NULL OR pd.development_type = ANY(filter_development_types))
        -- Conservation area filter
        AND (filter_conservation_areas IS NULL OR pd.conservation_area = ANY(filter_conservation_areas))
        -- Date filters
        AND (filter_date_from IS NULL OR pd.decision_date >= filter_date_from)
        AND (filter_date_to IS NULL OR pd.decision_date <= filter_date_to)
    ORDER BY similarity DESC
    LIMIT match_count;
END;
$$;

-- Function to find similar decisions to a given decision
CREATE OR REPLACE FUNCTION find_similar_decisions(
    source_decision_id bigint,
    match_count int DEFAULT 10,
    exclude_same_address boolean DEFAULT TRUE
)
RETURNS TABLE (
    decision_id bigint,
    case_reference text,
    address text,
    similarity float
)
LANGUAGE plpgsql
AS $$
DECLARE
    source_address text;
    avg_embedding vector(3072);
BEGIN
    -- Get source decision address
    SELECT pd.address INTO source_address
    FROM planning_decisions pd
    WHERE pd.id = source_decision_id;

    -- Calculate average embedding for the source decision
    SELECT AVG(dc.embedding) INTO avg_embedding
    FROM document_chunks dc
    WHERE dc.decision_id = source_decision_id;

    RETURN QUERY
    SELECT DISTINCT ON (pd.id)
        pd.id AS decision_id,
        pd.case_reference,
        pd.address,
        1 - (dc.embedding <=> avg_embedding) AS similarity
    FROM document_chunks dc
    JOIN planning_decisions pd ON dc.decision_id = pd.id
    WHERE
        pd.id != source_decision_id
        AND (NOT exclude_same_address OR pd.address != source_address)
    ORDER BY pd.id, similarity DESC
    LIMIT match_count;
END;
$$;

-- ============================================
-- STATISTICS FUNCTIONS
-- ============================================

-- Function to get database statistics
CREATE OR REPLACE FUNCTION get_database_stats()
RETURNS TABLE (
    total_decisions bigint,
    granted_count bigint,
    refused_count bigint,
    date_range_start date,
    date_range_end date,
    wards_covered text[],
    total_chunks bigint
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        COUNT(*)::bigint AS total_decisions,
        COUNT(*) FILTER (WHERE outcome = 'Granted')::bigint AS granted_count,
        COUNT(*) FILTER (WHERE outcome = 'Refused')::bigint AS refused_count,
        MIN(decision_date) AS date_range_start,
        MAX(decision_date) AS date_range_end,
        ARRAY_AGG(DISTINCT ward ORDER BY ward) AS wards_covered,
        (SELECT COUNT(*)::bigint FROM document_chunks) AS total_chunks
    FROM planning_decisions;
END;
$$;

-- Function to get ward statistics
CREATE OR REPLACE FUNCTION get_ward_stats(ward_name text)
RETURNS TABLE (
    name text,
    case_count bigint,
    approval_rate float,
    common_development_types text[],
    conservation_areas text[]
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        ward_name AS name,
        COUNT(*)::bigint AS case_count,
        (COUNT(*) FILTER (WHERE outcome = 'Granted')::float /
         NULLIF(COUNT(*), 0)) AS approval_rate,
        ARRAY(
            SELECT development_type
            FROM planning_decisions
            WHERE ward = ward_name AND development_type IS NOT NULL
            GROUP BY development_type
            ORDER BY COUNT(*) DESC
            LIMIT 5
        ) AS common_development_types,
        ARRAY(
            SELECT DISTINCT conservation_area
            FROM planning_decisions
            WHERE ward = ward_name AND conservation_area != 'None'
        ) AS conservation_areas
    FROM planning_decisions
    WHERE ward = ward_name;
END;
$$;

-- ============================================
-- ROW LEVEL SECURITY (Optional - for multi-tenant)
-- ============================================

-- Enable RLS on tables (uncomment if needed)
-- ALTER TABLE planning_decisions ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE document_chunks ENABLE ROW LEVEL SECURITY;

-- ============================================
-- TRIGGERS
-- ============================================

-- Trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_planning_decisions_updated_at
    BEFORE UPDATE ON planning_decisions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- VIEWS FOR COMMON QUERIES
-- ============================================

-- View for granted decisions (most commonly searched)
CREATE OR REPLACE VIEW granted_decisions AS
SELECT * FROM planning_decisions WHERE outcome = 'Granted';

-- View for conservation area decisions
CREATE OR REPLACE VIEW conservation_area_decisions AS
SELECT * FROM planning_decisions WHERE conservation_area != 'None';

-- View for recent decisions (last 2 years)
CREATE OR REPLACE VIEW recent_decisions AS
SELECT * FROM planning_decisions
WHERE decision_date >= CURRENT_DATE - INTERVAL '2 years';

-- ============================================
-- SAMPLE DATA INSERTION (for testing)
-- ============================================

-- Insert a sample decision (comment out in production)
/*
INSERT INTO planning_decisions (
    case_reference,
    address,
    ward,
    postcode,
    decision_date,
    outcome,
    application_type,
    development_type,
    description,
    conservation_area
) VALUES (
    '2024/0001/P',
    '123 Hampstead High Street, London',
    'Hampstead Town',
    'NW3 1AB',
    '2024-01-15',
    'Granted',
    'Householder',
    'Rear Extension',
    'Single storey rear extension with glazed roof',
    'Hampstead Conservation Area'
);
*/

-- ============================================
-- GRANTS FOR SERVICE ROLE
-- ============================================

-- Grant permissions to authenticated users (via Supabase)
GRANT SELECT ON planning_decisions TO authenticated;
GRANT SELECT ON document_chunks TO authenticated;
GRANT EXECUTE ON FUNCTION search_planning_decisions TO authenticated;
GRANT EXECUTE ON FUNCTION find_similar_decisions TO authenticated;
GRANT EXECUTE ON FUNCTION get_database_stats TO authenticated;
GRANT EXECUTE ON FUNCTION get_ward_stats TO authenticated;

-- Grant full access to service role
GRANT ALL ON planning_decisions TO service_role;
GRANT ALL ON document_chunks TO service_role;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO service_role;
