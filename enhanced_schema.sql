-- Enhanced Schema for Question-Level Word Mastery Tracking
-- This schema implements word mastery as percentage of questions mastered per word

-- Add new table to track mastery per individual question for each word
CREATE TABLE IF NOT EXISTS word_question_mastery (
    mastery_id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(user_id),
    word_id INT REFERENCES words(word_id),
    question_id INT REFERENCES questions(question_id),
    first_try_correct_count INT DEFAULT 0,
    total_attempts INT DEFAULT 0,
    last_attempted TIMESTAMP DEFAULT NOW(),
    is_mastered BOOLEAN DEFAULT FALSE,
    UNIQUE(user_id, word_id, question_id)
);

-- Enhanced word mastery table with percentage tracking
CREATE TABLE IF NOT EXISTS enhanced_word_mastery (
    mastery_id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(user_id),
    word_id INT REFERENCES words(word_id),
    total_questions INT DEFAULT 0,                -- Total questions containing this word
    mastered_questions INT DEFAULT 0,             -- Questions mastered for this word
    mastery_percentage DECIMAL(5,2) DEFAULT 0.00, -- Percentage of questions mastered
    last_updated TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, word_id)
);

-- Function to recalculate word mastery percentage based on question mastery
CREATE OR REPLACE FUNCTION recalculate_word_mastery(p_user_id INT, p_word_id INT)
RETURNS VOID AS $$
DECLARE
    v_total_questions INT;
    v_mastered_questions INT;
    v_mastery_percentage DECIMAL(5,2);
BEGIN
    -- Count total questions for this word
    SELECT COUNT(DISTINCT wqm.question_id) INTO v_total_questions
    FROM word_question_map wqm
    WHERE wqm.word_id = p_word_id;
    
    -- Count mastered questions for this user-word combination
    SELECT COUNT(*) INTO v_mastered_questions
    FROM word_question_mastery wqm
    WHERE wqm.user_id = p_user_id 
      AND wqm.word_id = p_word_id 
      AND wqm.is_mastered = TRUE;
    
    -- Calculate percentage
    IF v_total_questions > 0 THEN
        v_mastery_percentage := ROUND((v_mastered_questions::DECIMAL / v_total_questions::DECIMAL) * 100, 2);
    ELSE
        v_mastery_percentage := 0.00;
    END IF;
    
    -- Update or insert enhanced word mastery
    INSERT INTO enhanced_word_mastery (user_id, word_id, total_questions, mastered_questions, mastery_percentage, last_updated)
    VALUES (p_user_id, p_word_id, v_total_questions, v_mastered_questions, v_mastery_percentage, NOW())
    ON CONFLICT (user_id, word_id) DO UPDATE SET
        total_questions = v_total_questions,
        mastered_questions = v_mastered_questions,
        mastery_percentage = v_mastery_percentage,
        last_updated = NOW();
END;
$$ LANGUAGE plpgsql;

-- Enhanced function to update question-level mastery after inserting a response
CREATE OR REPLACE FUNCTION update_enhanced_word_mastery()
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

    -- Check if this is first try for this question across ALL attempts for this user
    -- We need to check if this specific question has been attempted before by this user
    SELECT (COUNT(*) = 1) INTO v_is_first_try
    FROM responses r
    JOIN quiz_attempts qa ON r.attempt_id = qa.attempt_id
    WHERE qa.user_id = v_user_id
      AND r.question_id = NEW.question_id;

    -- Process each word associated with this question
    FOR v_word_id IN
        SELECT wqm.word_id FROM word_question_map wqm WHERE wqm.question_id = NEW.question_id
    LOOP
        -- Update word-question mastery tracking
        IF v_is_first_try AND NEW.is_correct THEN
            -- This is a first-try correct answer for this question
            INSERT INTO word_question_mastery (user_id, word_id, question_id, first_try_correct_count, total_attempts, last_attempted, is_mastered)
            VALUES (v_user_id, v_word_id, NEW.question_id, 1, 1, NOW(), FALSE)
            ON CONFLICT (user_id, word_id, question_id) DO UPDATE SET
                first_try_correct_count = word_question_mastery.first_try_correct_count + 1,
                total_attempts = word_question_mastery.total_attempts + 1,
                last_attempted = NOW(),
                is_mastered = (word_question_mastery.first_try_correct_count + 1) >= 2;
        ELSE
            -- Either not first try, or not correct - just increment total attempts
            INSERT INTO word_question_mastery (user_id, word_id, question_id, first_try_correct_count, total_attempts, last_attempted, is_mastered)
            VALUES (v_user_id, v_word_id, NEW.question_id, 0, 1, NOW(), FALSE)
            ON CONFLICT (user_id, word_id, question_id) DO UPDATE SET
                total_attempts = word_question_mastery.total_attempts + 1,
                last_attempted = NOW();
        END IF;

        -- Recalculate overall word mastery percentage
        PERFORM recalculate_word_mastery(v_user_id, v_word_id);

        -- Also update legacy tables for backward compatibility
        IF NEW.is_correct AND v_is_first_try THEN
            -- Update global word mastery (legacy)
            INSERT INTO word_mastery (user_id, word_id, first_try_correct_count, last_practiced, mastered)
            VALUES (v_user_id, v_word_id, 1, NOW(), FALSE)
            ON CONFLICT (user_id, word_id) DO UPDATE SET
                first_try_correct_count = word_mastery.first_try_correct_count + 1,
                last_practiced = NOW(),
                mastered = (word_mastery.first_try_correct_count + 1) >= 2;

            -- Update per-type mastery (legacy)
            INSERT INTO word_mastery_by_type (user_id, word_id, quiz_type, first_try_correct_count, last_practiced, mastered)
            VALUES (v_user_id, v_word_id, v_quiz_type, 1, NOW(), FALSE)
            ON CONFLICT (user_id, word_id, quiz_type) DO UPDATE SET
                first_try_correct_count = word_mastery_by_type.first_try_correct_count + 1,
                last_practiced = NOW(),
                mastered = (word_mastery_by_type.first_try_correct_count + 1) >= 2;
        END IF;
    END LOOP;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Function to initialize mastery tracking for existing words when new questions are added
CREATE OR REPLACE FUNCTION initialize_word_mastery_for_new_questions()
RETURNS TRIGGER AS $$
DECLARE
    v_word_id INT;
    v_user_id INT;
BEGIN
    -- For each word associated with the new question
    FOR v_word_id IN
        SELECT wqm.word_id FROM word_question_map wqm WHERE wqm.question_id = NEW.question_id
    LOOP
        -- For each existing user, recalculate their mastery for this word
        FOR v_user_id IN
            SELECT user_id FROM users WHERE role = 'learner'
        LOOP
            PERFORM recalculate_word_mastery(v_user_id, v_word_id);
        END LOOP;
    END LOOP;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Enhanced views for question-level mastery tracking
CREATE OR REPLACE VIEW vw_enhanced_word_progress AS
SELECT 
    ewm.user_id,
    u.username,
    COUNT(*) AS total_words_encountered,
    SUM(ewm.total_questions) AS total_questions_encountered,
    SUM(ewm.mastered_questions) AS total_questions_mastered,
    ROUND(AVG(ewm.mastery_percentage), 2) AS average_word_mastery,
    COUNT(*) FILTER (WHERE ewm.mastery_percentage = 100.00) AS fully_mastered_words,
    COUNT(*) FILTER (WHERE ewm.mastery_percentage > 0.00 AND ewm.mastery_percentage < 100.00) AS partially_mastered_words,
    COUNT(*) FILTER (WHERE ewm.mastery_percentage = 0.00) AS unmastered_words,
    ROUND(100.0 * COUNT(*) FILTER (WHERE ewm.mastery_percentage = 100.00) / NULLIF(COUNT(*), 0), 2) AS fully_mastered_percentage
FROM enhanced_word_mastery ewm
JOIN users u ON ewm.user_id = u.user_id
GROUP BY ewm.user_id, u.username;

-- View showing detailed word mastery breakdown
CREATE OR REPLACE VIEW vw_word_mastery_detail AS
SELECT 
    ewm.user_id,
    u.username,
    w.word_text,
    ewm.total_questions,
    ewm.mastered_questions,
    ewm.mastery_percentage,
    ewm.last_updated,
    CASE 
        WHEN ewm.mastery_percentage = 100.00 THEN 'Fully Mastered'
        WHEN ewm.mastery_percentage > 50.00 THEN 'Well Practiced'
        WHEN ewm.mastery_percentage > 0.00 THEN 'Learning'
        ELSE 'Not Started'
    END AS mastery_status
FROM enhanced_word_mastery ewm
JOIN users u ON ewm.user_id = u.user_id
JOIN words w ON ewm.word_id = w.word_id
ORDER BY ewm.user_id, ewm.mastery_percentage DESC, w.word_text;

-- View showing words that need more practice
CREATE OR REPLACE VIEW vw_words_needing_practice AS
SELECT 
    ewm.user_id,
    u.username,
    w.word_text,
    ewm.mastery_percentage,
    ewm.total_questions,
    ewm.mastered_questions,
    (ewm.total_questions - ewm.mastered_questions) AS questions_remaining,
    ewm.last_updated
FROM enhanced_word_mastery ewm
JOIN users u ON ewm.user_id = u.user_id
JOIN words w ON ewm.word_id = w.word_id
WHERE ewm.mastery_percentage < 100.00
ORDER BY ewm.user_id, ewm.mastery_percentage ASC, ewm.last_updated ASC;

-- View showing question-level mastery details
CREATE OR REPLACE VIEW vw_question_mastery_detail AS
SELECT 
    wqm.user_id,
    u.username,
    w.word_text,
    q.question_text,
    qt.name AS quiz_type,
    wqm.first_try_correct_count,
    wqm.total_attempts,
    wqm.is_mastered,
    wqm.last_attempted,
    CASE 
        WHEN wqm.is_mastered THEN 'Mastered'
        WHEN wqm.first_try_correct_count > 0 THEN 'Progress'
        ELSE 'Not Attempted'
    END AS status
FROM word_question_mastery wqm
JOIN users u ON wqm.user_id = u.user_id
JOIN words w ON wqm.word_id = w.word_id
JOIN questions q ON wqm.question_id = q.question_id
JOIN quiz_types qt ON q.quiz_type_id = qt.quiz_type_id
ORDER BY wqm.user_id, w.word_text, qt.name;

-- Drop and recreate triggers
DROP TRIGGER IF EXISTS trg_update_word_mastery ON responses;
CREATE TRIGGER trg_update_enhanced_word_mastery
AFTER INSERT ON responses
FOR EACH ROW
EXECUTE FUNCTION update_enhanced_word_mastery();

-- Trigger to update mastery when new questions are added
DROP TRIGGER IF EXISTS trg_initialize_mastery_new_questions ON word_question_map;
CREATE TRIGGER trg_initialize_mastery_new_questions
AFTER INSERT ON word_question_map
FOR EACH ROW
EXECUTE FUNCTION initialize_word_mastery_for_new_questions();

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_word_question_mastery_user_word ON word_question_mastery(user_id, word_id);
CREATE INDEX IF NOT EXISTS idx_word_question_mastery_mastered ON word_question_mastery(user_id, is_mastered);
CREATE INDEX IF NOT EXISTS idx_enhanced_word_mastery_user ON enhanced_word_mastery(user_id);
CREATE INDEX IF NOT EXISTS idx_enhanced_word_mastery_percentage ON enhanced_word_mastery(mastery_percentage);

-- Function to migrate existing data to enhanced mastery tracking
CREATE OR REPLACE FUNCTION migrate_to_enhanced_mastery()
RETURNS VOID AS $$
DECLARE
    v_user_id INT;
    v_word_id INT;
BEGIN
    -- For each user-word combination that exists in legacy mastery
    FOR v_user_id, v_word_id IN
        SELECT DISTINCT user_id, word_id FROM word_mastery
    LOOP
        PERFORM recalculate_word_mastery(v_user_id, v_word_id);
    END LOOP;
    
    RAISE NOTICE 'Enhanced mastery migration completed successfully';
END;
$$ LANGUAGE plpgsql;

-- Comments explaining the enhanced system
COMMENT ON TABLE word_question_mastery IS 'Tracks mastery per individual question for each word. A question is mastered when answered correctly twice on first attempt.';
COMMENT ON TABLE enhanced_word_mastery IS 'Tracks overall word mastery as percentage of questions mastered for that word.';
COMMENT ON FUNCTION recalculate_word_mastery IS 'Recalculates word mastery percentage based on individual question mastery.';
COMMENT ON VIEW vw_enhanced_word_progress IS 'Shows comprehensive word mastery statistics including question-level details.';
COMMENT ON VIEW vw_words_needing_practice IS 'Identifies words that need more practice based on question mastery percentage.';
