-- Peblo Quiz Engine — SQLite Database Schema
-- Auto-created by SQLAlchemy on startup via Base.metadata.create_all()

CREATE TABLE source_documents (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id   VARCHAR NOT NULL UNIQUE,   -- e.g. "SRC_A1B2C3"
    filename    VARCHAR NOT NULL,
    grade       INTEGER NOT NULL,
    subject     VARCHAR NOT NULL,
    file_path   VARCHAR NOT NULL,
    status      VARCHAR NOT NULL DEFAULT 'pending',  -- pending | processing | processed | failed
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE content_chunks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    chunk_id    VARCHAR NOT NULL UNIQUE,   -- e.g. "SRC_A1B2C3_CH_01"
    source_id   VARCHAR NOT NULL REFERENCES source_documents(source_id),
    grade       INTEGER NOT NULL,
    subject     VARCHAR NOT NULL,
    topic       VARCHAR NOT NULL,
    text        TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE quiz_questions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    question_id VARCHAR NOT NULL UNIQUE,  -- e.g. "Q_SRC_A1B2C3_CH_01_001"
    chunk_id    VARCHAR NOT NULL REFERENCES content_chunks(chunk_id),
    source_id   VARCHAR NOT NULL,
    question    TEXT NOT NULL,
    type        VARCHAR NOT NULL,         -- MCQ | TRUE_FALSE | FILL_BLANK
    options     TEXT,                     -- JSON array string, null for FILL_BLANK
    answer      VARCHAR NOT NULL,
    difficulty  VARCHAR NOT NULL,         -- easy | medium | hard
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE student_answers (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id            VARCHAR NOT NULL,
    question_id           VARCHAR NOT NULL REFERENCES quiz_questions(question_id),
    selected_answer       VARCHAR NOT NULL,
    is_correct            BOOLEAN NOT NULL,
    difficulty_at_attempt VARCHAR NOT NULL,
    created_at            DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE student_profiles (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id            VARCHAR NOT NULL UNIQUE,
    current_difficulty    VARCHAR NOT NULL DEFAULT 'easy',
    consecutive_correct   INTEGER NOT NULL DEFAULT 0,
    consecutive_incorrect INTEGER NOT NULL DEFAULT 0,
    total_correct         INTEGER NOT NULL DEFAULT 0,
    total_answered        INTEGER NOT NULL DEFAULT 0,
    updated_at            DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for common query patterns
CREATE INDEX idx_chunks_source_id     ON content_chunks(source_id);
CREATE INDEX idx_questions_chunk_id   ON quiz_questions(chunk_id);
CREATE INDEX idx_questions_difficulty ON quiz_questions(difficulty);
CREATE INDEX idx_answers_student_id   ON student_answers(student_id);
