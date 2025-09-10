Vocabulary Learning App – Technical Blueprint
1. Overview

The app is designed for learners aged 18-24 to build vocabulary for short-term exams. Users are expected to use the app daily. The app supports two types of users:

Learners

Can take quizzes, track progress, and view a dashboard with performance insights.

Admins

Can upload questions via CSV, view analytics, and generate reports.

Key Features

6 types of quiz questions: Synonyms, Antonyms, Odd One Out, Analogies, Word Meanings, Fill in the Blanks.

Mastery tracking for individual words, globally and by quiz type.

Automatic word updates when new questions are added.

Repetition system ensures users focus on words they struggle with.

Dashboards for learners and admins.

Weekly automated reports and real-time analytics.

2. Database Schema
2.1 Users
CREATE TABLE users (
    user_id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role VARCHAR(20) CHECK (role IN ('learner', 'admin')) NOT NULL
);

2.2 Words
CREATE TABLE words (
    word_id SERIAL PRIMARY KEY,
    word_text VARCHAR(100) UNIQUE NOT NULL
);

2.3 Questions
CREATE TABLE questions (
    question_id SERIAL PRIMARY KEY,
    quiz_type VARCHAR(50) CHECK (quiz_type IN 
        ('synonym', 'antonym', 'odd_one_out', 'analogy', 'meaning', 'fill_blank')) NOT NULL,
    question_text TEXT NOT NULL,
    correct_answer TEXT NOT NULL
);

2.4 Question-Word Mapping
CREATE TABLE word_question_map (
    map_id SERIAL PRIMARY KEY,
    word_id INT REFERENCES words(word_id) ON DELETE CASCADE,
    question_id INT REFERENCES questions(question_id) ON DELETE CASCADE,
    UNIQUE(word_id, question_id)
);

2.5 Quiz Attempts
CREATE TABLE quiz_attempts (
    attempt_id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(user_id) ON DELETE CASCADE,
    quiz_type VARCHAR(50),
    started_at TIMESTAMP DEFAULT NOW()
);

2.6 Responses
CREATE TABLE responses (
    response_id SERIAL PRIMARY KEY,
    attempt_id INT REFERENCES quiz_attempts(attempt_id) ON DELETE CASCADE,
    question_id INT REFERENCES questions(question_id) ON DELETE CASCADE,
    is_correct BOOLEAN NOT NULL,
    answered_at TIMESTAMP DEFAULT NOW()
);

2.7 Word Mastery (Global)
CREATE TABLE word_mastery (
    mastery_id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(user_id) ON DELETE CASCADE,
    word_id INT REFERENCES words(word_id) ON DELETE CASCADE,
    first_try_correct_count INT DEFAULT 0,
    last_practiced TIMESTAMP,
    mastered BOOLEAN DEFAULT FALSE,
    UNIQUE(user_id, word_id)
);

2.8 Word Mastery by Quiz Type
CREATE TABLE word_mastery_by_type (
    mastery_type_id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(user_id) ON DELETE CASCADE,
    word_id INT REFERENCES words(word_id) ON DELETE CASCADE,
    quiz_type VARCHAR(50),
    first_try_correct_count INT DEFAULT 0,
    last_practiced TIMESTAMP,
    mastered BOOLEAN DEFAULT FALSE,
    UNIQUE(user_id, word_id, quiz_type)
);

3. Functions and Triggers
3.1 Insert Word if New (Automatic Update)
CREATE OR REPLACE FUNCTION insert_word_if_new(word_text TEXT)
RETURNS INT AS $$
DECLARE
    v_word_id INT;
BEGIN
    SELECT word_id INTO v_word_id FROM words WHERE word_text = LOWER(word_text);
    IF v_word_id IS NULL THEN
        INSERT INTO words(word_text) VALUES (LOWER(word_text)) RETURNING word_id INTO v_word_id;
    END IF;
    RETURN v_word_id;
END;
$$ LANGUAGE plpgsql;

3.2 Update Word Mastery
CREATE OR REPLACE FUNCTION update_word_mastery()
RETURNS TRIGGER AS $$
DECLARE
    v_word_id INT;
    v_user_id INT;
    v_quiz_type VARCHAR(50);
    v_is_first_try BOOLEAN;
BEGIN
    SELECT qa.user_id, q.quiz_type
    INTO v_user_id, v_quiz_type
    FROM quiz_attempts qa
    JOIN questions q ON q.quiz_type = qa.quiz_type
    WHERE qa.attempt_id = NEW.attempt_id
      AND q.question_id = NEW.question_id;

    SELECT (COUNT(*) = 1) INTO v_is_first_try
    FROM responses
    WHERE attempt_id = NEW.attempt_id
      AND question_id = NEW.question_id;

    IF NEW.is_correct = TRUE THEN
        FOR v_word_id IN
            SELECT word_id FROM word_question_map
            WHERE question_id = NEW.question_id
        LOOP
            -- Global Mastery
            INSERT INTO word_mastery (user_id, word_id, first_try_correct_count, last_practiced, mastered)
            VALUES (
                v_user_id,
                v_word_id,
                CASE WHEN v_is_first_try THEN 1 ELSE 0 END,
                NOW(),
                FALSE
            )
            ON CONFLICT (user_id, word_id) DO UPDATE
            SET first_try_correct_count = word_mastery.first_try_correct_count + CASE WHEN v_is_first_try THEN 1 ELSE 0 END,
                last_practiced = NOW(),
                mastered = (word_mastery.first_try_correct_count + CASE WHEN v_is_first_try THEN 1 ELSE 0 END) >= 2;

            -- Mastery by Quiz Type
            INSERT INTO word_mastery_by_type (user_id, word_id, quiz_type, first_try_correct_count, last_practiced, mastered)
            VALUES (
                v_user_id,
                v_word_id,
                v_quiz_type,
                CASE WHEN v_is_first_try THEN 1 ELSE 0 END,
                NOW(),
                FALSE
            )
            ON CONFLICT (user_id, word_id, quiz_type) DO UPDATE
            SET first_try_correct_count = word_mastery_by_type.first_try_correct_count + CASE WHEN v_is_first_try THEN 1 ELSE 0 END,
                last_practiced = NOW(),
                mastered = (word_mastery_by_type.first_try_correct_count + CASE WHEN v_is_first_try THEN 1 ELSE 0 END) >= 2;
        END LOOP;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

Trigger for Responses
CREATE TRIGGER trg_update_word_mastery
AFTER INSERT ON responses
FOR EACH ROW
EXECUTE FUNCTION update_word_mastery();

4. Learner Dashboard Views
4.1 Global Progress
CREATE OR REPLACE VIEW vw_global_word_progress AS
SELECT 
    wm.user_id,
    COUNT(*) FILTER (WHERE wm.mastered = TRUE) AS mastered_count,
    COUNT(*) FILTER (WHERE wm.mastered = FALSE) AS not_mastered_count,
    COUNT(*) AS total_tracked,
    ROUND(100.0 * COUNT(*) FILTER (WHERE wm.mastered = TRUE) / COUNT(*), 2) AS mastery_percentage
FROM word_mastery wm
GROUP BY wm.user_id;

4.2 Progress by Quiz Type
CREATE OR REPLACE VIEW vw_word_progress_by_type AS
SELECT 
    wm.user_id,
    wm.quiz_type,
    COUNT(*) FILTER (WHERE wm.mastered = TRUE) AS mastered_count,
    COUNT(*) FILTER (WHERE wm.mastered = FALSE) AS not_mastered_count,
    COUNT(*) AS total_tracked,
    ROUND(100.0 * COUNT(*) FILTER (WHERE wm.mastered = TRUE) / COUNT(*), 2) AS mastery_percentage
FROM word_mastery_by_type wm
GROUP BY wm.user_id, wm.quiz_type;

5. Admin Dashboard Views
5.1 Word Difficulty
CREATE OR REPLACE VIEW vw_word_difficulty AS
SELECT 
    w.word_id,
    w.word_text,
    COUNT(*) AS total_attempts,
    SUM(CASE WHEN r.is_correct THEN 1 ELSE 0 END) AS correct_attempts,
    ROUND(100.0 * SUM(CASE WHEN r.is_correct THEN 1 ELSE 0 END) / COUNT(*), 2) AS accuracy_rate
FROM responses r
JOIN questions q ON r.question_id = q.question_id
JOIN word_question_map wqm ON q.question_id = wqm.question_id
JOIN words w ON wqm.word_id = w.word_id
GROUP BY w.word_id, w.word_text
ORDER BY accuracy_rate ASC;

5.2 Quiz Type Performance
CREATE OR REPLACE VIEW vw_quiz_type_performance AS
SELECT 
    q.quiz_type,
    COUNT(*) AS total_attempts,
    SUM(CASE WHEN r.is_correct THEN 1 ELSE 0 END) AS correct_attempts,
    ROUND(100.0 * SUM(CASE WHEN r.is_correct THEN 1 ELSE 0 END) / COUNT(*), 2) AS accuracy_rate
FROM responses r
JOIN questions q ON r.question_id = q.question_id
GROUP BY q.quiz_type
ORDER BY accuracy_rate ASC;

5.3 Learner Progress
CREATE OR REPLACE VIEW vw_learner_progress AS
SELECT 
    u.user_id,
    u.username,
    COUNT(*) FILTER (WHERE wm.mastered = TRUE) AS mastered_words,
    COUNT(*) FILTER (WHERE wm.mastered = FALSE) AS pending_words,
    ROUND(100.0 * COUNT(*) FILTER (WHERE wm.mastered = TRUE) / NULLIF(COUNT(*),0), 2) AS mastery_percentage
FROM users u
LEFT JOIN word_mastery wm ON u.user_id = wm.user_id
GROUP BY u.user_id, u.username
ORDER BY mastery_percentage DESC;

6. Automated Weekly Reports

Use views: vw_word_difficulty, vw_quiz_type_performance, vw_learner_progress.

Export to CSV via Postgres \COPY or backend scripts.

Optional: schedule weekly export with pg_cron or backend job.

Example metrics:

Hardest words

Weakest quiz types

Top learners

Struggling learners (<20% mastery)

7. Real-Time Admin Dashboard

Components:

Global Overview (Cards: total learners, total words, overall mastery %)

Mastery Trend (Line chart: mastered vs pending words over time)

Quiz Type Performance (Bar chart)

Hardest Words Table

Leaderboard (Top learners)

Filters: date range, quiz type, mastery percentage

Live updates via polling or WebSockets

Frontend: React + Tailwind + Recharts or any UI framework.

8. Quiz Flow

Learner selects a quiz type.

App pulls 20 questions from database (mix of new + incorrect previous attempts).

Learner answers questions.

Responses are inserted into responses table.

Trigger updates word_mastery and word_mastery_by_type.

Quiz summary displayed (correct, incorrect, mastery status).

Incorrect questions are repeated until all mastered (first-try count ≥2).

Daily use encourages mastery over all 6000 words.

9. Admin Flow

Upload questions via CSV.

Words table auto-updates with new words.

View dashboards (word difficulty, quiz type performance, learner progress).

Weekly reports generated automatically or manually exported.

10. Spaced Repetition / Review (Optional Enhancement)

Extend word_mastery with next_review_date.

Schedule words for review based on first-try success and mastery count

ChatGPT said:

.

Ensures learners see weak words more frequently.

11. Sample Questions Table (Example)
Quiz Type	Question	Correct Answer
Synonym	Large	Big
Antonym	Hot	Cold
Odd One Out	Cat, Dog, Car, Lion	Car
Analogy	Bird : Fly :: Fish : ?	Swim
Meaning	Abundant	Plentiful
Fill Blank	The sky is ___	Blue

Each word linked in word_question_map.

Used to calculate mastery.

12. Conclusion

This document provides a complete blueprint for building the app:

Database schema

Functions and triggers for mastery tracking

Learner and Admin dashboard views

Automated reports

Real-time dashboards and quiz flow

It’s structured for scalable daily use, automated tracking, and exam preparation for young adults.

I can also create a diagrammatic ERD + dashboard mockup so your developers have a visual guide for database relations and UI layout.

Do you want me to prepare that next?

You said:
Yes
ChatGPT said:

Perfect ✅ — here’s a detailed plan for an ERD (Entity-Relationship Diagram) + Dashboard Mockup for your vocabulary learning app. This will help developers visualize database relations and UI layout.

1. ERD (Entity-Relationship Diagram)

Entities and Relationships:

Users

user_id (PK)

username

password_hash

role (learner/admin)

Relationships:

One-to-many → quiz_attempts

One-to-many → word_mastery

Words

word_id (PK)

word_text

Relationships:

Many-to-many → questions (via word_question_map)

One-to-many → word_mastery

Questions

question_id (PK)

quiz_type

question_text

correct_answer

Relationships:

Many-to-many → words (via word_question_map)

One-to-many → responses

Word_Question_Map

map_id (PK)

word_id (FK → words.word_id)

question_id (FK → questions.question_id)

Quiz_Attempts

attempt_id (PK)

user_id (FK → users.user_id)

quiz_type

started_at

Relationships:

One-to-many → responses

Responses

response_id (PK)

attempt_id (FK → quiz_attempts.attempt_id)

question_id (FK → questions.question_id)

is_correct

answered_at

Word_Mastery

mastery_id (PK)

user_id (FK → users.user_id)

word_id (FK → words.word_id)

first_try_correct_count

last_practiced

mastered (boolean)

Word_Mastery_by_Quiz_Type

mastery_type_id (PK)

user_id (FK → users.user_id)

word_id (FK → words.word_id)

quiz_type

first_try_correct_count

last_practiced

mastered (boolean)

Relationships Overview:

Users 1---* Quiz_Attempts 1---* Responses
Users 1---* Word_Master
Users 1---* Word_Master_by_Quiz_Type
Words *---* Questions via Word_Question_Map
Questions 1---* Responses

2. Dashboard Mockup
2.1 Learner Dashboard

Components:

Global Stats Cards

Total Words Mastered

Total Words Pending

Mastery % Progress Bar

Quiz Type Progress

Bar chart per quiz type (Synonyms, Antonyms…)

Review List

Table: Word | Quiz Type | Last Attempt | First-Try Count

Daily Quiz Button

Starts 20-question quiz (mix of new + incorrect words)

Layout:

+-----------------------------+
| Mastery Cards               |
+-----------------------------+
| Quiz Type Bar Chart         |
+-----------------------------+
| Review List Table           |
+-----------------------------+
| Start Daily Quiz Button     |
+-----------------------------+

2.2 Admin Dashboard

Components:

Global Stats Cards

Total Learners

Total Words

Overall Mastery %

Quiz Type Performance

Bar chart with accuracy %

Hardest Words

Table sorted by first-try accuracy

Leaderboard

Top learners by mastery %

Filters

Date range

Quiz type

Mastery % threshold

Layout:

+-----------------------------+
| Global Stats Cards          |
+-----------------------------+
| Quiz Type Performance Chart |
+-----------------------------+
| Hardest Words Table         | Leaderboard Table
+-----------------------------+
| Filters Panel               |
+-----------------------------+

2.3 Real-Time Update Design

Learners: quiz results update immediately; dashboard reflects mastery in real-time.

Admins: hard words, quiz accuracy, and top/struggling learners update dynamically using polling or WebSocket push.

Optional: heatmaps for words most frequently answered incorrectly.

3. Next Steps for Developers

Implement the SQL schema provided earlier.

Create API endpoints:

/quiz/start → fetch 20 questions (mix new + incorrect)

/quiz/submit → record responses (triggers update to mastery)

/dashboard/learner → global + quiz type progress

/dashboard/admin → word difficulty + learner leaderboard

Build frontend dashboards with React + Tailwind or any UI framework.

Implement real-time updates via polling or WebSockets.

Set up weekly report generator for admins.