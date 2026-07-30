-- REC Database Initialization
-- Runs on first PostgreSQL startup

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;

-- Events
CREATE TABLE IF NOT EXISTS events (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            VARCHAR(255) NOT NULL,
    venue           VARCHAR(255),
    start_time      TIMESTAMP NOT NULL,
    end_time        TIMESTAMP,
    status          VARCHAR(20) DEFAULT 'active',
    settings        JSONB DEFAULT '{}',
    created_at      TIMESTAMP DEFAULT NOW()
);

-- Cameras
CREATE TABLE IF NOT EXISTS cameras (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_id        UUID REFERENCES events(id) ON DELETE CASCADE,
    camera_type     VARCHAR(20) NOT NULL,
    camera_model    VARCHAR(100),
    connection_type VARCHAR(20) NOT NULL,
    location_label  VARCHAR(100),
    config          JSONB DEFAULT '{}',
    status          VARCHAR(20) DEFAULT 'connected',
    created_at      TIMESTAMP DEFAULT NOW()
);

-- Images
CREATE TABLE IF NOT EXISTS images (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_id        UUID REFERENCES events(id) ON DELETE CASCADE,
    camera_id       UUID REFERENCES cameras(id),
    file_path       VARCHAR(500),
    thumbnail_path  VARCHAR(500),
    original_width  INT,
    original_height INT,
    capture_mode    VARCHAR(20),
    iqg_blur_score  FLOAT,
    iqg_nima_score  FLOAT,
    iqg_face_count  INT,
    iqg_passed      BOOLEAN DEFAULT FALSE,
    rejection_stage VARCHAR(50),
    captured_at     TIMESTAMP NOT NULL,
    processed_at    TIMESTAMP,
    metadata        JSONB DEFAULT '{}'
);

-- Face clusters (anonymous identity clusters)
CREATE TABLE IF NOT EXISTS face_clusters (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_id                UUID REFERENCES events(id) ON DELETE CASCADE,
    centroid                VECTOR(512),
    face_count              INT DEFAULT 0,
    representative_face_id  UUID,
    created_at              TIMESTAMP DEFAULT NOW()
);

-- Face embeddings
CREATE TABLE IF NOT EXISTS face_embeddings (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    image_id        UUID REFERENCES images(id) ON DELETE CASCADE,
    face_index      INT NOT NULL,
    embedding       VECTOR(512) NOT NULL,
    bbox            JSONB,
    landmarks       JSONB,
    det_score       FLOAT,
    yaw_angle       FLOAT,
    cluster_id      UUID REFERENCES face_clusters(id),
    created_at      TIMESTAMP DEFAULT NOW()
);

-- HNSW index for fast ANN cosine search
CREATE INDEX IF NOT EXISTS idx_face_embeddings_hnsw
    ON face_embeddings
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 200);

-- Portal users
CREATE TABLE IF NOT EXISTS portal_users (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_id            UUID REFERENCES events(id) ON DELETE CASCADE,
    display_name        VARCHAR(100),
    selfie_path         VARCHAR(500),
    selfie_embedding    VECTOR(512),
    matched_cluster_id  UUID REFERENCES face_clusters(id),
    consent_given_at    TIMESTAMP,
    registered_at       TIMESTAMP DEFAULT NOW()
);

-- Users (admin/photographer portal)
CREATE TABLE IF NOT EXISTS users (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email           VARCHAR(255) UNIQUE NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,
    role            VARCHAR(20) DEFAULT 'viewer',
    created_at      TIMESTAMP DEFAULT NOW()
);
