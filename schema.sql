-- Schema for Word Mastery App
-- Create tables, functions, triggers, and views needed to run the app.

-- Core tables
CREATE TABLE IF NOT EXISTS users (
    user_id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role VARCHAR(20) DEFAULT 'learner',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS words (
    word_id SERIAL PRIMARY KEY,
    word_text VARCHAR(255) UNIQUE NOT NULL,
    meaning TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS quiz_types (
    quiz_type_id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS questions (
    question_id SERIAL PRIMARY KEY,
    quiz_type_id INT REFERENCES quiz_types(quiz_type_id) ON DELETE SET NULL,
    question_text TEXT NOT NULL,
    correct_answer VARCHAR(255) NOT NULL,
    created_by INT REFERENCES users(user_id),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS options (
    option_id SERIAL PRIMARY KEY,
    question_id INT REFERENCES questions(question_id) ON DELETE CASCADE,
    option_text VARCHAR(255) NOT NULL
);

CREATE TABLE IF NOT EXISTS word_question_map (
    map_id SERIAL PRIMARY KEY,
    word_id INT REFERENCES words(word_id),
    question_id INT REFERENCES questions(question_id) ON DELETE CASCADE,
    UNIQUE(word_id, question_id)
);

-- Progress tracking
CREATE TABLE IF NOT EXISTS quiz_attempts (
    attempt_id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(user_id),
    quiz_type_id INT REFERENCES quiz_types(quiz_type_id),
    started_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS quiz_attempt_items (
    attempt_item_id SERIAL PRIMARY KEY,
    attempt_id INT REFERENCES quiz_attempts(attempt_id) ON DELETE CASCADE,
    question_id INT REFERENCES questions(question_id),
    user_answer TEXT,
    is_correct BOOLEAN,
    time_taken_ms INT
);

CREATE TABLE IF NOT EXISTS responses (
    response_id SERIAL PRIMARY KEY,
    attempt_id INT REFERENCES quiz_attempts(attempt_id) ON DELETE CASCADE,
    question_id INT REFERENCES questions(question_id),
    selected_answer VARCHAR(255),
    is_correct BOOLEAN,
    answered_at TIMESTAMP DEFAULT NOW()
);

-- Mastery tracking
CREATE TABLE IF NOT EXISTS word_mastery (
    mastery_id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(user_id),
    word_id INT REFERENCES words(word_id),
    first_try_correct_count INT DEFAULT 0,
    last_practiced TIMESTAMP DEFAULT NOW(),
    mastered BOOLEAN DEFAULT FALSE,
    UNIQUE(user_id, word_id)
);

CREATE TABLE IF NOT EXISTS word_mastery_by_type (
    mastery_type_id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(user_id),
    word_id INT REFERENCES words(word_id),
    quiz_type VARCHAR(50) NOT NULL,
    first_try_correct_count INT DEFAULT 0,
    last_practiced TIMESTAMP DEFAULT NOW(),
    mastered BOOLEAN DEFAULT FALSE,
    UNIQUE(user_id, word_id, quiz_type)
);

-- Recent question window: helps enforce "no repeats in last 5 attempts"
CREATE TABLE IF NOT EXISTS recent_question_window (
    user_id INT REFERENCES users(user_id),
    question_id INT REFERENCES questions(question_id),
    last_seen_attempt_id INT REFERENCES quiz_attempts(attempt_id),
    last_seen_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (user_id, question_id)
);

-- Function to insert question + options + map words
CREATE OR REPLACE FUNCTION insert_question_with_words(
    p_question_text TEXT,
    p_quiz_type VARCHAR,
    p_correct_answer VARCHAR,
    p_options TEXT[],
    p_created_by INT
)
RETURNS VOID AS $$
DECLARE
    v_quiz_type_id INT;
    v_question_id INT;
    v_option TEXT;
    v_word TEXT;
    v_word_id INT;
    v_all_words TEXT[] := ARRAY[]::TEXT[];
BEGIN
    -- Ensure quiz type exists
    SELECT quiz_type_id INTO v_quiz_type_id FROM quiz_types WHERE name = p_quiz_type;
    IF v_quiz_type_id IS NULL THEN
        INSERT INTO quiz_types (name) VALUES (p_quiz_type) RETURNING quiz_type_id INTO v_quiz_type_id;
    END IF;

    -- Insert question
    INSERT INTO questions (quiz_type_id, question_text, correct_answer, created_by)
    VALUES (v_quiz_type_id, p_question_text, p_correct_answer, p_created_by)
    RETURNING question_id INTO v_question_id;

    -- Insert options
    IF p_options IS NOT NULL THEN
        FOREACH v_option IN ARRAY p_options LOOP
            IF v_option IS NOT NULL AND TRIM(v_option) <> '' THEN
                INSERT INTO options (question_id, option_text) VALUES (v_question_id, TRIM(v_option));
            END IF;
        END LOOP;
    END IF;

    -- Combine options and correct answer into a single array
    IF p_options IS NOT NULL THEN
        v_all_words := p_options || ARRAY[p_correct_answer];
    ELSE
        v_all_words := ARRAY[p_correct_answer];
    END IF;

    -- Insert words (lowercased) and map them to the question
    FOREACH v_word IN ARRAY v_all_words LOOP
        v_word := TRIM(LOWER(v_word));
        IF v_word IS NULL OR v_word = '' THEN
            CONTINUE;
        END IF;

        INSERT INTO words (word_text) VALUES (v_word)
        ON CONFLICT (word_text) DO NOTHING;

        SELECT word_id INTO v_word_id FROM words WHERE word_text = v_word;

        -- Map word to question (ignore duplicates)
        INSERT INTO word_question_map (word_id, question_id)
        VALUES (v_word_id, v_question_id)
        ON CONFLICT (word_id, question_id) DO NOTHING;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- Function & trigger to update mastery after inserting a response
CREATE OR REPLACE FUNCTION update_word_mastery()
RETURNS TRIGGER AS $$
DECLARE
    v_word_id INT;
    v_user_id INT;
    v_quiz_type VARCHAR;
    v_is_first_try BOOLEAN;
BEGIN
    -- Get user and quiz type for this attempt
    SELECT qa.user_id, qt.name INTO v_user_id, v_quiz_type
    FROM quiz_attempts qa
    LEFT JOIN quiz_types qt ON qa.quiz_type_id = qt.quiz_type_id
    WHERE qa.attempt_id = NEW.attempt_id;

    -- safety: if no user found, bail out
    IF v_user_id IS NULL THEN
        RETURN NEW;
    END IF;

    -- Check if this is first try for this question in this attempt
    SELECT (COUNT(*) = 1) INTO v_is_first_try
    FROM responses r
    WHERE r.attempt_id = NEW.attempt_id
      AND r.question_id = NEW.question_id;

    -- Only update on correct first tries
    IF NEW.is_correct AND v_is_first_try THEN
        FOR v_word_id IN
            SELECT wqm.word_id FROM word_question_map wqm WHERE wqm.question_id = NEW.question_id
        LOOP
            -- Update global word mastery
            INSERT INTO word_mastery (user_id, word_id, first_try_correct_count, last_practiced, mastered)
            VALUES (v_user_id, v_word_id, 1, NOW(), FALSE)
            ON CONFLICT (user_id, word_id) DO UPDATE SET
                first_try_correct_count = word_mastery.first_try_correct_count + 1,
                last_practiced = NOW(),
                mastered = (word_mastery.first_try_correct_count + 1) >= 2;

            -- Update per-type mastery
            INSERT INTO word_mastery_by_type (user_id, word_id, quiz_type, first_try_correct_count, last_practiced, mastered)
            VALUES (v_user_id, v_word_id, v_quiz_type, 1, NOW(), FALSE)
            ON CONFLICT (user_id, word_id, quiz_type) DO UPDATE SET
                first_try_correct_count = word_mastery_by_type.first_try_correct_count + 1,
                last_practiced = NOW(),
                mastered = (word_mastery_by_type.first_try_correct_count + 1) >= 2;
        END LOOP;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_update_word_mastery ON responses;
CREATE TRIGGER trg_update_word_mastery
AFTER INSERT ON responses
FOR EACH ROW
EXECUTE FUNCTION update_word_mastery();

-- Views for dashboards
CREATE OR REPLACE VIEW vw_global_word_progress AS
SELECT 
    wm.user_id,
    COUNT(*) AS total_words_encountered,
    COUNT(*) FILTER (WHERE wm.mastered = TRUE) AS words_mastered,
    COUNT(*) FILTER (WHERE wm.mastered = FALSE) AS words_pending,
    ROUND(100.0 * COUNT(*) FILTER (WHERE wm.mastered = TRUE) / NULLIF(COUNT(*),0), 2) AS mastery_percentage
FROM word_mastery wm
GROUP BY wm.user_id;

CREATE OR REPLACE VIEW vw_word_progress_by_type AS
SELECT 
    wm.user_id,
    wm.quiz_type,
    COUNT(*) AS total_words,
    COUNT(*) FILTER (WHERE wm.mastered = TRUE) AS words_mastered,
    ROUND(100.0 * COUNT(*) FILTER (WHERE wm.mastered = TRUE) / NULLIF(COUNT(*),0), 2) AS mastery_percentage
FROM word_mastery_by_type wm
GROUP BY wm.user_id, wm.quiz_type;

-- A convenience index for faster lookups
CREATE INDEX IF NOT EXISTS idx_word_question_map_question_id ON word_question_map(question_id);
CREATE INDEX IF NOT EXISTS idx_word_mastery_user_id ON word_mastery(user_id);
CREATE INDEX IF NOT EXISTS idx_word_mastery_by_type_user_id ON word_mastery_by_type(user_id);

-- End of schema
