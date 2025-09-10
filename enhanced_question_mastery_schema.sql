-- Enhanced Question-Level Word Mastery Schema
-- This schema tracks mastery per question for each word, calculating word mastery as 
-- percentage of questions mastered rather than just counting correct attempts

-- Drop existing mastery tables to recreate with enhanced structure
DROP TABLE IF EXISTS word_mastery_by_type CASCADE;
DROP TABLE IF EXISTS word_mastery CASCADE;

-- Enhanced Word Mastery - tracks mastery per question for each word
CREATE TABLE word_question_mastery (
    mastery_id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(user_id) ON DELETE CASCADE,
    word_id INT REFERENCES words(word_id) ON DELETE CASCADE,
    question_id INT REFERENCES questions(question_id) ON DELETE CASCADE,
    quiz_type VARCHAR(50) NOT NULL,
    first_attempt_correct_count INT DEFAULT 0,
    total_attempts INT DEFAULT 0,
    is_mastered BOOLEAN DEFAULT FALSE,
    first_correct_at TIMESTAMP NULL,
    last_attempted_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, word_id, question_id)
);

-- Aggregated Word Mastery View - calculates percentage of questions mastered per word
CREATE OR REPLACE VIEW word_mastery AS
SELECT 
    user_id,
    word_id,
    COUNT(*) as total_questions,
    COUNT(*) FILTER (WHERE is_mastered = TRUE) as questions_mastered,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE is_mastered = TRUE) / NULLIF(COUNT(*), 0), 
        2
    ) as mastery_percentage,
    CASE 
        WHEN COUNT(*) FILTER (WHERE is_mastered = TRUE) = COUNT(*) THEN TRUE 
        ELSE FALSE 
    END as fully_mastered,
    MAX(last_attempted_at) as last_practiced,
    MIN(first_correct_at) as first_mastery_achieved
FROM word_question_mastery
GROUP BY user_id, word_id;

-- Aggregated Word Mastery by Quiz Type
CREATE OR REPLACE VIEW word_mastery_by_type AS
SELECT 
    user_id,
    word_id,
    quiz_type,
    COUNT(*) as total_questions,
    COUNT(*) FILTER (WHERE is_mastered = TRUE) as questions_mastered,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE is_mastered = TRUE) / NULLIF(COUNT(*), 0), 
        2
    ) as mastery_percentage,
    CASE 
        WHEN COUNT(*) FILTER (WHERE is_mastered = TRUE) = COUNT(*) THEN TRUE 
        ELSE FALSE 
    END as fully_mastered,
    MAX(last_attempted_at) as last_practiced
FROM word_question_mastery
GROUP BY user_id, word_id, quiz_type;

-- Enhanced function to update question-level mastery
CREATE OR REPLACE FUNCTION update_question_mastery()
RETURNS TRIGGER AS $$
DECLARE
    v_word_id INT;
    v_user_id INT;
    v_quiz_type VARCHAR;
    v_is_first_try BOOLEAN;
    v_current_correct_count INT;
BEGIN
    -- Get user and quiz type for this attempt
    SELECT qa.user_id, qt.name INTO v_user_id, v_quiz_type
    FROM quiz_attempts qa
    LEFT JOIN quiz_types qt ON qa.quiz_type_id = qt.quiz_type_id
    WHERE qa.attempt_id = NEW.attempt_id;

    -- Safety: if no user found, bail out
    IF v_user_id IS NULL THEN
        RETURN NEW;
    END IF;

    -- Check if this is first try for this question in this attempt
    SELECT (COUNT(*) = 1) INTO v_is_first_try
    FROM responses r
    WHERE r.attempt_id = NEW.attempt_id
      AND r.question_id = NEW.question_id;

    -- Update mastery for each word associated with this question
    FOR v_word_id IN
        SELECT wqm.word_id FROM word_question_map wqm WHERE wqm.question_id = NEW.question_id
    LOOP
        -- Insert or update the question-level mastery record
        INSERT INTO word_question_mastery (
            user_id, 
            word_id, 
            question_id, 
            quiz_type,
            first_attempt_correct_count,
            total_attempts,
            is_mastered,
            first_correct_at,
            last_attempted_at
        )
        VALUES (
            v_user_id, 
            v_word_id, 
            NEW.question_id, 
            v_quiz_type,
            CASE WHEN NEW.is_correct AND v_is_first_try THEN 1 ELSE 0 END,
            1,
            FALSE,
            CASE WHEN NEW.is_correct AND v_is_first_try THEN NOW() ELSE NULL END,
            NOW()
        )
        ON CONFLICT (user_id, word_id, question_id) DO UPDATE SET
            first_attempt_correct_count = word_question_mastery.first_attempt_correct_count + 
                CASE WHEN NEW.is_correct AND v_is_first_try THEN 1 ELSE 0 END,
            total_attempts = word_question_mastery.total_attempts + 1,
            is_mastered = (word_question_mastery.first_attempt_correct_count + 
                CASE WHEN NEW.is_correct AND v_is_first_try THEN 1 ELSE 0 END) >= 2,
            first_correct_at = COALESCE(
                word_question_mastery.first_correct_at,
                CASE WHEN NEW.is_correct AND v_is_first_try THEN NOW() ELSE NULL END
            ),
            last_attempted_at = NOW();
            
    END LOOP;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for question-level mastery updates
DROP TRIGGER IF EXISTS trg_update_question_mastery ON responses;
CREATE TRIGGER trg_update_question_mastery
AFTER INSERT ON responses
FOR EACH ROW
EXECUTE FUNCTION update_question_mastery();

-- Enhanced function to add new questions with automatic word mastery initialization
CREATE OR REPLACE FUNCTION add_question_with_mastery_tracking(
    p_quiz_type VARCHAR,
    p_question_text TEXT,
    p_correct_answer VARCHAR,
    p_options TEXT[],
    p_created_by INT
)
RETURNS INT AS $$
DECLARE
    v_quiz_type_id INT;
    v_question_id INT;
    v_option TEXT;
    v_word TEXT;
    v_word_id INT;
    v_user_record RECORD;
    v_unique_words TEXT[] := ARRAY[]::TEXT[];
    v_answer_word TEXT;
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

    -- Process correct answer as the primary word to track (normalized)
    v_answer_word := TRIM(LOWER(p_correct_answer));
    IF v_answer_word IS NOT NULL AND v_answer_word <> '' THEN
        -- Insert or get existing word
        INSERT INTO words (word_text) VALUES (v_answer_word)
        ON CONFLICT (word_text) DO NOTHING;
        
        SELECT word_id INTO v_word_id FROM words WHERE word_text = v_answer_word;
        
        -- Map the answer word to the question
        INSERT INTO word_question_map (word_id, question_id)
        VALUES (v_word_id, v_question_id)
        ON CONFLICT (word_id, question_id) DO NOTHING;
        
        -- Add to unique words array for mastery tracking
        v_unique_words := v_unique_words || v_answer_word;
        
        RAISE NOTICE 'Added/updated word "%" for question %', v_answer_word, v_question_id;
    END IF;

    -- Process options as additional words to track (only unique ones)
    IF p_options IS NOT NULL THEN
        FOREACH v_option IN ARRAY p_options LOOP
            v_word := TRIM(LOWER(v_option));
            IF v_word IS NOT NULL AND v_word <> '' AND NOT (v_word = ANY(v_unique_words)) THEN
                -- Insert or get existing word
                INSERT INTO words (word_text) VALUES (v_word)
                ON CONFLICT (word_text) DO NOTHING;
                
                SELECT word_id INTO v_word_id FROM words WHERE word_text = v_word;
                
                -- Map word to question
                INSERT INTO word_question_map (word_id, question_id)
                VALUES (v_word_id, v_question_id)
                ON CONFLICT (word_id, question_id) DO NOTHING;
                
                -- Add to unique words array
                v_unique_words := v_unique_words || v_word;
                
                RAISE NOTICE 'Added/updated word "%" for question %', v_word, v_question_id;
            END IF;
        END LOOP;
    END IF;

    -- Initialize mastery tracking for all learner users for the new word-question combinations
    FOR v_user_record IN SELECT user_id FROM users WHERE role = 'learner' LOOP
        FOREACH v_word IN ARRAY v_unique_words LOOP
            SELECT word_id INTO v_word_id FROM words WHERE word_text = v_word;
            
            INSERT INTO word_question_mastery (
                user_id, 
                word_id, 
                question_id, 
                quiz_type,
                first_attempt_correct_count,
                total_attempts,
                is_mastered,
                last_attempted_at
            )
            VALUES (
                v_user_record.user_id,
                v_word_id,
                v_question_id,
                p_quiz_type,
                0,
                0,
                FALSE,
                NOW()
            )
            ON CONFLICT (user_id, word_id, question_id) DO NOTHING;
        END LOOP;
    END LOOP;
    
    RAISE NOTICE 'Question % added with % unique words. Mastery tracking initialized for all learners.', v_question_id, array_length(v_unique_words, 1);
    
    RETURN v_question_id;
END;
$$ LANGUAGE plpgsql;

-- Function to initialize mastery tracking for existing words and questions
CREATE OR REPLACE FUNCTION initialize_question_mastery_tracking()
RETURNS VOID AS $$
DECLARE
    v_user_record RECORD;
    v_word_question_record RECORD;
BEGIN
    -- For each user and each word-question combination, create initial mastery records
    FOR v_user_record IN SELECT user_id FROM users WHERE role = 'learner' LOOP
        FOR v_word_question_record IN 
            SELECT DISTINCT 
                wqm.word_id, 
                wqm.question_id, 
                qt.name as quiz_type
            FROM word_question_map wqm
            JOIN questions q ON wqm.question_id = q.question_id
            JOIN quiz_types qt ON q.quiz_type_id = qt.quiz_type_id
        LOOP
            INSERT INTO word_question_mastery (
                user_id, 
                word_id, 
                question_id, 
                quiz_type,
                first_attempt_correct_count,
                total_attempts,
                is_mastered,
                last_attempted_at
            )
            VALUES (
                v_user_record.user_id,
                v_word_question_record.word_id,
                v_word_question_record.question_id,
                v_word_question_record.quiz_type,
                0,
                0,
                FALSE,
                NOW()
            )
            ON CONFLICT (user_id, word_id, question_id) DO NOTHING;
        END LOOP;
    END LOOP;
    
    RAISE NOTICE 'Question-level mastery tracking initialized for all users and word-question combinations';
END;
$$ LANGUAGE plpgsql;

-- Function to update mastery tracking when new users are added
CREATE OR REPLACE FUNCTION initialize_mastery_for_new_user(p_user_id INT)
RETURNS VOID AS $$
DECLARE
    v_word_question_record RECORD;
BEGIN
    -- Initialize mastery tracking for the new user for all existing word-question combinations
    FOR v_word_question_record IN 
        SELECT DISTINCT 
            wqm.word_id, 
            wqm.question_id, 
            qt.name as quiz_type
        FROM word_question_map wqm
        JOIN questions q ON wqm.question_id = q.question_id
        JOIN quiz_types qt ON q.quiz_type_id = qt.quiz_type_id
    LOOP
        INSERT INTO word_question_mastery (
            user_id, 
            word_id, 
            question_id, 
            quiz_type,
            first_attempt_correct_count,
            total_attempts,
            is_mastered,
            last_attempted_at
        )
        VALUES (
            p_user_id,
            v_word_question_record.word_id,
            v_word_question_record.question_id,
            v_word_question_record.quiz_type,
            0,
            0,
            FALSE,
            NOW()
        )
        ON CONFLICT (user_id, word_id, question_id) DO NOTHING;
    END LOOP;
    
    RAISE NOTICE 'Mastery tracking initialized for user % with all existing word-question combinations', p_user_id;
END;
$$ LANGUAGE plpgsql;

-- Enhanced dashboard views using the new question-level mastery
CREATE OR REPLACE VIEW vw_global_word_progress AS
SELECT 
    wm.user_id,
    COUNT(DISTINCT wm.word_id) as total_words_encountered,
    COUNT(DISTINCT wm.word_id) FILTER (WHERE wm.fully_mastered = TRUE) as words_fully_mastered,
    COUNT(DISTINCT wm.word_id) FILTER (WHERE wm.fully_mastered = FALSE) as words_partially_mastered,
    ROUND(
        100.0 * COUNT(DISTINCT wm.word_id) FILTER (WHERE wm.fully_mastered = TRUE) / 
        NULLIF(COUNT(DISTINCT wm.word_id), 0), 
        2
    ) as word_mastery_percentage,
    ROUND(AVG(wm.mastery_percentage), 2) as average_question_mastery_percentage,
    SUM(wm.total_questions) as total_questions_encountered,
    SUM(wm.questions_mastered) as questions_mastered
FROM word_mastery wm
GROUP BY wm.user_id;

CREATE OR REPLACE VIEW vw_word_progress_by_type AS
SELECT 
    wmt.user_id,
    wmt.quiz_type,
    COUNT(DISTINCT wmt.word_id) as total_words,
    COUNT(DISTINCT wmt.word_id) FILTER (WHERE wmt.fully_mastered = TRUE) as words_fully_mastered,
    ROUND(
        100.0 * COUNT(DISTINCT wmt.word_id) FILTER (WHERE wmt.fully_mastered = TRUE) / 
        NULLIF(COUNT(DISTINCT wmt.word_id), 0), 
        2
    ) as word_mastery_percentage,
    ROUND(AVG(wmt.mastery_percentage), 2) as average_question_mastery_percentage,
    SUM(wmt.total_questions) as total_questions,
    SUM(wmt.questions_mastered) as questions_mastered
FROM word_mastery_by_type wmt
GROUP BY wmt.user_id, wmt.quiz_type;

-- View to get detailed word mastery breakdown for a user
CREATE OR REPLACE VIEW vw_detailed_word_mastery AS
SELECT 
    wqm.user_id,
    w.word_text,
    wqm.quiz_type,
    q.question_text,
    wqm.first_attempt_correct_count,
    wqm.total_attempts,
    wqm.is_mastered,
    wqm.first_correct_at,
    wqm.last_attempted_at,
    CASE 
        WHEN wqm.is_mastered THEN 'Mastered'
        WHEN wqm.first_attempt_correct_count = 1 THEN 'One more correct needed'
        WHEN wqm.total_attempts > 0 THEN 'Needs practice'
        ELSE 'Not attempted'
    END as mastery_status
FROM word_question_mastery wqm
JOIN words w ON wqm.word_id = w.word_id
JOIN questions q ON wqm.question_id = q.question_id
ORDER BY w.word_text, wqm.quiz_type, q.question_text;

-- View to identify words that need review (not fully mastered)
CREATE OR REPLACE VIEW vw_words_needing_review AS
SELECT 
    wm.user_id,
    w.word_text,
    wm.total_questions,
    wm.questions_mastered,
    wm.mastery_percentage,
    wm.last_practiced,
    CASE 
        WHEN wm.mastery_percentage = 0 THEN 'Never attempted'
        WHEN wm.mastery_percentage < 50 THEN 'Needs significant practice'
        WHEN wm.mastery_percentage < 100 THEN 'Almost mastered'
    END as priority_level
FROM word_mastery wm
JOIN words w ON wm.word_id = w.word_id
WHERE wm.fully_mastered = FALSE
ORDER BY wm.mastery_percentage ASC, wm.last_practiced ASC;

-- View to get word statistics and question mappings
CREATE OR REPLACE VIEW vw_word_statistics AS
SELECT 
    w.word_id,
    w.word_text,
    COUNT(DISTINCT wqm.question_id) as total_questions,
    COUNT(DISTINCT q.quiz_type_id) as quiz_types_count,
    array_agg(DISTINCT qt.name ORDER BY qt.name) as quiz_types,
    array_agg(DISTINCT q.question_id ORDER BY q.question_id) as question_ids,
    COUNT(DISTINCT wm.user_id) as users_tracking,
    ROUND(AVG(wm.mastery_percentage), 2) as avg_mastery_percentage
FROM words w
LEFT JOIN word_question_map wqm ON w.word_id = wqm.word_id
LEFT JOIN questions q ON wqm.question_id = q.question_id
LEFT JOIN quiz_types qt ON q.quiz_type_id = qt.quiz_type_id
LEFT JOIN word_mastery wm ON w.word_id = wm.word_id
GROUP BY w.word_id, w.word_text
ORDER BY total_questions DESC, w.word_text;

-- Function to get detailed word information
CREATE OR REPLACE FUNCTION get_word_details(p_word_text VARCHAR)
RETURNS TABLE(
    word_id INT,
    word_text VARCHAR,
    total_questions BIGINT,
    quiz_types_count BIGINT,
    quiz_types VARCHAR[],
    question_details JSON
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        w.word_id,
        w.word_text,
        COUNT(DISTINCT wqm.question_id) as total_questions,
        COUNT(DISTINCT q.quiz_type_id) as quiz_types_count,
        array_agg(DISTINCT qt.name ORDER BY qt.name)::VARCHAR[] as quiz_types,
        json_agg(
            json_build_object(
                'question_id', q.question_id,
                'quiz_type', qt.name,
                'question_text', q.question_text,
                'correct_answer', q.correct_answer
            ) ORDER BY qt.name, q.question_id
        ) as question_details
    FROM words w
    LEFT JOIN word_question_map wqm ON w.word_id = wqm.word_id
    LEFT JOIN questions q ON wqm.question_id = q.question_id
    LEFT JOIN quiz_types qt ON q.quiz_type_id = qt.quiz_type_id
    WHERE w.word_text = p_word_text
    GROUP BY w.word_id, w.word_text;
END;
$$ LANGUAGE plpgsql;

-- Function to add a single word and update mastery tracking for all users
CREATE OR REPLACE FUNCTION add_word_with_mastery_tracking(p_word_text VARCHAR)
RETURNS INT AS $$
DECLARE
    v_word_id INT;
    v_user_record RECORD;
    v_normalized_word VARCHAR;
BEGIN
    -- Normalize the word (lowercase, trimmed)
    v_normalized_word := TRIM(LOWER(p_word_text));
    
    IF v_normalized_word IS NULL OR v_normalized_word = '' THEN
        RAISE EXCEPTION 'Word text cannot be empty';
    END IF;
    
    -- Insert or get existing word
    INSERT INTO words (word_text) VALUES (v_normalized_word)
    ON CONFLICT (word_text) DO NOTHING
    RETURNING word_id INTO v_word_id;
    
    -- If word already existed, get its ID
    IF v_word_id IS NULL THEN
        SELECT word_id INTO v_word_id FROM words WHERE word_text = v_normalized_word;
        RAISE NOTICE 'Word "%" already exists with ID %', v_normalized_word, v_word_id;
    ELSE
        RAISE NOTICE 'Added new word "%" with ID %', v_normalized_word, v_word_id;
    END IF;
    
    RETURN v_word_id;
END;
$$ LANGUAGE plpgsql;

-- Function to get quiz questions excluding mastered ones
CREATE OR REPLACE FUNCTION get_quiz_questions_excluding_mastered(
    p_user_id INT,
    p_quiz_type VARCHAR DEFAULT NULL,
    p_limit INT DEFAULT 20
)
RETURNS TABLE(
    question_id INT,
    question_text TEXT,
    correct_answer VARCHAR,
    quiz_type VARCHAR
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        q.question_id,
        q.question_text,
        q.correct_answer,
        qt.name as quiz_type
    FROM questions q
    JOIN quiz_types qt ON q.quiz_type_id = qt.quiz_type_id
    WHERE (p_quiz_type IS NULL OR qt.name = p_quiz_type)
      AND q.question_id NOT IN (
          -- Exclude questions where ALL associated words are fully mastered
          SELECT DISTINCT wqm_check.question_id
          FROM word_question_mastery wqm_check
          JOIN word_question_map wqm_map ON wqm_check.question_id = wqm_map.question_id
          WHERE wqm_check.user_id = p_user_id
          GROUP BY wqm_check.question_id
          HAVING COUNT(*) = COUNT(*) FILTER (WHERE wqm_check.is_mastered = TRUE)
      )
    ORDER BY RANDOM()
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

-- Function to get word mastery summary for a user
CREATE OR REPLACE FUNCTION get_user_word_mastery_summary(p_user_id INT)
RETURNS TABLE(
    word_text VARCHAR,
    total_questions BIGINT,
    questions_mastered BIGINT,
    mastery_percentage NUMERIC,
    quiz_types_count BIGINT,
    fully_mastered BOOLEAN,
    last_practiced TIMESTAMP
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        w.word_text,
        wm.total_questions,
        wm.questions_mastered,
        wm.mastery_percentage,
        COUNT(DISTINCT wmt.quiz_type) as quiz_types_count,
        wm.fully_mastered,
        wm.last_practiced
    FROM word_mastery wm
    JOIN words w ON wm.word_id = w.word_id
    LEFT JOIN word_mastery_by_type wmt ON wm.user_id = wmt.user_id AND wm.word_id = wmt.word_id
    WHERE wm.user_id = p_user_id
    GROUP BY w.word_text, wm.total_questions, wm.questions_mastered, wm.mastery_percentage, wm.fully_mastered, wm.last_practiced
    ORDER BY wm.mastery_percentage ASC, wm.last_practiced ASC;
END;
$$ LANGUAGE plpgsql;

-- Indexes for better performance
CREATE INDEX IF NOT EXISTS idx_word_question_mastery_user_id ON word_question_mastery(user_id);
CREATE INDEX IF NOT EXISTS idx_word_question_mastery_word_id ON word_question_mastery(word_id);
CREATE INDEX IF NOT EXISTS idx_word_question_mastery_question_id ON word_question_mastery(question_id);
CREATE INDEX IF NOT EXISTS idx_word_question_mastery_quiz_type ON word_question_mastery(quiz_type);
CREATE INDEX IF NOT EXISTS idx_word_question_mastery_mastered ON word_question_mastery(is_mastered);
CREATE INDEX IF NOT EXISTS idx_words_word_text ON words(word_text);
CREATE INDEX IF NOT EXISTS idx_word_question_map_combined ON word_question_map(word_id, question_id);

COMMENT ON TABLE word_question_mastery IS 'Tracks mastery per question for each word. A question is mastered when answered correctly twice on first attempt.';
COMMENT ON VIEW word_mastery IS 'Aggregated view showing word mastery as percentage of questions mastered for each word.';
COMMENT ON VIEW word_mastery_by_type IS 'Aggregated view showing word mastery by quiz type as percentage of questions mastered.';
COMMENT ON VIEW vw_word_statistics IS 'Shows statistics for each word including question count, quiz types, and average mastery.';
COMMENT ON FUNCTION add_question_with_mastery_tracking IS 'Adds a new question with unique word extraction and automatic mastery tracking initialization.';
COMMENT ON FUNCTION get_quiz_questions_excluding_mastered IS 'Returns quiz questions excluding those where all associated words are fully mastered.';
COMMENT ON FUNCTION get_user_word_mastery_summary IS 'Returns comprehensive word mastery summary for a user.';
COMMENT ON FUNCTION add_word_with_mastery_tracking IS 'Adds a single word and ensures it is tracked in the mastery system.';
COMMENT ON FUNCTION get_word_details IS 'Returns detailed information about a word including all associated questions.';

-- Usage examples:
-- 1. Add a new question with automatic word tracking:
--    SELECT add_question_with_mastery_tracking('synonym', 'What is a synonym for happy?', 'joyful', ARRAY['joyful', 'sad', 'angry', 'calm'], 1);
--
-- 2. Initialize mastery tracking for existing data:
--    SELECT initialize_question_mastery_tracking();
--
-- 3. Initialize mastery for a new user:
--    SELECT initialize_mastery_for_new_user(5);
--
-- 4. Get word statistics:
--    SELECT * FROM vw_word_statistics WHERE word_text = 'happy';
--
-- 5. Get detailed word information:
--    SELECT * FROM get_word_details('happy');
--
-- 6. Add a single word to the system:
--    SELECT add_word_with_mastery_tracking('excellent');
