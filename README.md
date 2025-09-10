# Vocabulary Learning Quiz Application

A comprehensive vocabulary learning system for CAT exam preparation with adaptive learning and progress tracking. Features smart quiz generation, word mastery tracking, and a complete REST API backend.

🌐 **API Documentation available at: http://localhost:8000/docs**
🔧 **Interactive API at: http://localhost:8000/redoc**

## � Quick Start Guide

### Option 1: Full Development Setup (Recommended)
```bash
# Start database and API server
make dev
```

### Option 2: Step-by-Step Setup
```bash
# 1. Start the database
make docker-up

# 2. Start the API server
make api
# Or use: ./start-api.sh
```

### Option 3: Manual Setup
```bash
# Install dependencies
make deps

# Start database manually
docker compose up -d

# Start API server
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

Access the application:
- **API Documentation**: http://localhost:8000/docs
- **Interactive API**: http://localhost:8000/redoc  
- **Health Check**: http://localhost:8000/api/health

## 🔧 Development Commands

```bash
# Database operations
make docker-up          # Start PostgreSQL container
make schema            # Create database schema locally
make seed              # Populate with sample data
make clean             # Clean up containers and volumes

# API development  
make api               # Start FastAPI development server
make dev               # Full development setup (database + API)
make test              # Run comprehensive API tests
make deps              # Install Python dependencies
```

## 📡 REST API Endpoints

### Authentication
- `POST /api/auth/register` - User registration with JWT token
- `POST /api/auth/login` - User login and authentication

### Quiz Operations (Repetitive Learning Mode)
- `GET /api/quiz/types` - Get available quiz types and descriptions
- `POST /api/quiz/session/create` - Create a new repetitive quiz session
- `POST /api/quiz/session/{session_id}/submit` - Submit round responses (auto-retries incorrect answers)
- `GET /api/quiz/session/{session_id}` - Get quiz session status

### Quiz Operations (Legacy Single-Attempt Mode)
- `POST /api/quiz/create` - Create a traditional single-attempt quiz
- `POST /api/quiz/{attempt_id}/submit` - Submit quiz responses and get final results
- `GET /api/quiz/{attempt_id}` - Get detailed quiz attempt information

### Progress & Analytics
- `GET /api/progress` - Get comprehensive user progress and statistics

### System Health
- `GET /api/health` - API and database health check

## 📊 Sample API Usage

### 1. Register a New User
```bash
curl -X POST "http://localhost:8000/api/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "student",
    "password": "securepass123", 
    "email": "student@example.com"
  }'
```

**Response:**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer",
  "expires_in": 86400
}
```

### 2. Create a Repetitive Quiz Session
```bash
curl -X POST "http://localhost:8000/api/quiz/session/create" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "target_question_count": 20,
    "exclude_recent_attempts": 5
  }'
```

**Response:**
```json
{
  "session_id": "123e4567-e89b-12d3-a456-426614174000",
  "user_id": 45,
  "current_round": 1,
  "questions": [
    {
      "question_id": 1,
      "question_text": "Choose the synonym for 'abundant':",
      "options": ["plentiful", "scarce", "rare", "limited"],
      "quiz_type": "synonym"
    }
  ],
  "started_at": "2024-01-15T10:30:00",
  "total_questions": 20,
  "is_first_attempt": true
}
```

### 3. Submit Quiz Round Responses
```bash
curl -X POST "http://localhost:8000/api/quiz/session/123e4567-e89b-12d3-a456-426614174000/submit" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "responses": [
      {"question_id": 1, "answer": "plentiful"},
      {"question_id": 2, "answer": "incorrect_answer"}
    ]
  }'
```

**Response (Round with Incorrect Answers):**
```json
{
  "session_id": "123e4567-e89b-12d3-a456-426614174000",
  "current_round": 2,
  "round_result": {
    "attempt_id": 456,
    "round_number": 1,
    "total_questions": 20,
    "correct_answers": 18,
    "score_percentage": 90.0,
    "is_perfect_score": false,
    "individual_results": [...]
  },
  "is_session_completed": false,
  "next_questions": [
    {
      "question_id": 2,
      "question_text": "Choose the antonym for 'abundant':",
      "options": ["plentiful", "scarce", "rare", "similar"],
      "quiz_type": "antonym"
    }
  ]
}
```

**Response (Perfect Round - Session Complete):**
```json
{
  "session_id": "123e4567-e89b-12d3-a456-426614174000",
  "current_round": 3,
  "round_result": {
    "attempt_id": 789,
    "round_number": 2,
    "total_questions": 2,
    "correct_answers": 2,
    "score_percentage": 100.0,
    "is_perfect_score": true,
    "individual_results": [...]
  },
  "is_session_completed": true,
  "next_questions": null,
  "session_summary": {
    "session_id": "123e4567-e89b-12d3-a456-426614174000",
    "total_rounds": 2,
    "original_question_count": 20,
    "first_attempt_score": 90.0,
    "words_mastered_first_try": 18,
    "rounds_summary": [...],
    "mastery_updates": [...],
    "is_completed": true
  }
}
```

## �📱 Demo Credentials

### User Account
- **Username:** `testuser`
- **Password:** `user123`

### Admin Account  
- **Username:** `admin`
- **Password:** `admin123`

---

## 🚀 Key Features

### **For Learners**
- **Six Quiz Types:** Synonyms, Antonyms, Odd man out, Analogies, Word meanings, Fill in the blanks
- **Smart Question Selection:** 20 questions per quiz with intelligent mix of new and review words
- **Learning by Repition:** Quiz restarts with incorrect attempts until all the attempts are right 
- **Dual Mastery Tracking:** Global word mastery + per-quiz-type mastery for comprehensive learning
- **Adaptive Learning:** System focuses on words you need to practice most
- **Real-time Progress:** Automatic mastery updates via database triggers
- **Responsive Design:** Works seamlessly on desktop, tablet, and mobile

### **For Admins**
- **CSV Upload:** Bulk upload questions with automatic word extraction
- **Auto Word Management:** System automatically populates words table from uploaded questions
- **Dual Analytics:** Global system stats + per-quiz-type performance metrics
- **Content Management:** View question counts, user progress, and system health

---

## 🗄️ Advanced Database Schema

The application uses a sophisticated PostgreSQL schema with automatic triggers and functions:

### **Core Tables**

#### `users` - User Management
```sql
CREATE TABLE users (
    user_id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) DEFAULT 'learner', -- 'learner' or 'admin'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### `words` - Master Vocabulary List
```sql
CREATE TABLE words (
    word_id SERIAL PRIMARY KEY,
    word_text VARCHAR(100) UNIQUE NOT NULL,
    meaning TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### `quiz_types` - Quiz Categories
```sql
CREATE TABLE quiz_types (
    quiz_type_id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL -- synonym, antonym, analogy, etc.
);
```

#### `questions` - Quiz Questions
```sql
CREATE TABLE questions (
    question_id SERIAL PRIMARY KEY,
    quiz_type_id INT REFERENCES quiz_types(quiz_type_id),
    question_text TEXT NOT NULL,
    correct_answer VARCHAR(255) NOT NULL,
    created_by INT REFERENCES users(user_id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### `options` - Multiple Choice Options
```sql
CREATE TABLE options (
    option_id SERIAL PRIMARY KEY,
    question_id INT REFERENCES questions(question_id) ON DELETE CASCADE,
    option_text VARCHAR(255) NOT NULL
);
```

#### `word_question_map` - Word-Question Linking
```sql
CREATE TABLE word_question_map (
    map_id SERIAL PRIMARY KEY,
    word_id INT REFERENCES words(word_id),
    question_id INT REFERENCES questions(question_id) ON DELETE CASCADE
);
```

### **Progress Tracking Tables**

#### `quiz_attempts` - Quiz Sessions
```sql
CREATE TABLE quiz_attempts (
    attempt_id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(user_id),
    quiz_type_id INT REFERENCES quiz_types(quiz_type_id),
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);
```

#### `responses` - Individual Answers
```sql
CREATE TABLE responses (
    response_id SERIAL PRIMARY KEY,
    attempt_id INT REFERENCES quiz_attempts(attempt_id),
    question_id INT REFERENCES questions(question_id),
    selected_answer VARCHAR(255),
    is_correct BOOLEAN
);
```

### **Dual Mastery Tracking**

#### `word_mastery` - Global Word Mastery
```sql
CREATE TABLE word_mastery (
    mastery_id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(user_id),
    word_id INT REFERENCES words(word_id),
    first_try_correct_count INT DEFAULT 0,
    last_practiced TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    mastered BOOLEAN DEFAULT FALSE,
    UNIQUE(user_id, word_id)
);
```

#### `word_mastery_by_type` - Per-Quiz-Type Mastery
```sql
CREATE TABLE word_mastery_by_type (
    mastery_type_id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(user_id),
    word_id INT REFERENCES words(word_id),
    quiz_type VARCHAR(50) NOT NULL,
    first_try_correct_count INT DEFAULT 0,
    last_practiced TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    mastered BOOLEAN DEFAULT FALSE,
    UNIQUE(user_id, word_id, quiz_type)
);
```

---

## 🤖 Automated Functions & Triggers

### **Automatic Word Extraction Function**
```sql
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
    v_word_id INT;
    v_option TEXT;
    v_word TEXT;
    v_all_words TEXT[];
BEGIN
    -- Get or create quiz type
    SELECT quiz_type_id INTO v_quiz_type_id 
    FROM quiz_types WHERE name = p_quiz_type;
    
    IF v_quiz_type_id IS NULL THEN
        INSERT INTO quiz_types (name) VALUES (p_quiz_type) 
        RETURNING quiz_type_id INTO v_quiz_type_id;
    END IF;
    
    -- Insert question
    INSERT INTO questions (quiz_type_id, question_text, correct_answer, created_by)
    VALUES (v_quiz_type_id, p_question_text, p_correct_answer, p_created_by)
    RETURNING question_id INTO v_question_id;
    
    -- Insert options
    FOREACH v_option IN ARRAY p_options LOOP
        INSERT INTO options (question_id, option_text) VALUES (v_question_id, v_option);
    END LOOP;
    
    -- Combine all words: correct answer + options
    v_all_words := array_append(p_options, p_correct_answer);
    
    -- Process each word
    FOREACH v_word IN ARRAY v_all_words LOOP
        v_word := TRIM(LOWER(v_word));
        
        -- Insert word if not exists
        INSERT INTO words (word_text) VALUES (v_word)
        ON CONFLICT (word_text) DO NOTHING;
        
        -- Get word_id
        SELECT word_id INTO v_word_id FROM words WHERE word_text = v_word;
        
        -- Map word to question
        INSERT INTO word_question_map (word_id, question_id) 
        VALUES (v_word_id, v_question_id);
    END LOOP;
END;
$$ LANGUAGE plpgsql;
```

### **Automatic Mastery Update Trigger**
```sql
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
    JOIN quiz_types qt ON qa.quiz_type_id = qt.quiz_type_id
    WHERE qa.attempt_id = NEW.attempt_id;
    
    -- Check if this is first try for this question in this attempt
    SELECT COUNT(*) = 1 INTO v_is_first_try
    FROM responses r
    WHERE r.attempt_id = NEW.attempt_id 
    AND r.question_id = NEW.question_id;
    
    -- Only update on correct first tries
    IF NEW.is_correct AND v_is_first_try THEN
        -- Update mastery for all words linked to this question
        FOR v_word_id IN 
            SELECT wqm.word_id 
            FROM word_question_map wqm 
            WHERE wqm.question_id = NEW.question_id
        LOOP
            -- Update global word mastery
            INSERT INTO word_mastery (user_id, word_id, first_try_correct_count, last_practiced)
            VALUES (v_user_id, v_word_id, 1, NOW())
            ON CONFLICT (user_id, word_id) DO UPDATE SET
                first_try_correct_count = word_mastery.first_try_correct_count + 1,
                last_practiced = NOW(),
                mastered = (word_mastery.first_try_correct_count + 1) >= 2;
            
            -- Update per-type mastery
            INSERT INTO word_mastery_by_type (user_id, word_id, quiz_type, first_try_correct_count, last_practiced)
            VALUES (v_user_id, v_word_id, v_quiz_type, 1, NOW())
            ON CONFLICT (user_id, word_id, quiz_type) DO UPDATE SET
                first_try_correct_count = word_mastery_by_type.first_try_correct_count + 1,
                last_practiced = NOW(),
                mastered = (word_mastery_by_type.first_try_correct_count + 1) >= 2;
        END LOOP;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger
CREATE TRIGGER trg_update_word_mastery
AFTER INSERT ON responses
FOR EACH ROW
EXECUTE FUNCTION update_word_mastery();
```

---

## 📊 Dashboard Views & Analytics

### **Global Progress View**
```sql
CREATE OR REPLACE VIEW vw_global_word_progress AS
SELECT 
    wm.user_id,
    COUNT(*) AS total_words_encountered,
    COUNT(*) FILTER (WHERE wm.mastered = TRUE) AS words_mastered,
    COUNT(*) FILTER (WHERE wm.mastered = FALSE) AS words_pending,
    ROUND(100.0 * COUNT(*) FILTER (WHERE wm.mastered = TRUE) / COUNT(*), 2) AS mastery_percentage
FROM word_mastery wm
GROUP BY wm.user_id;
```

### **Progress by Quiz Type**
```sql
CREATE OR REPLACE VIEW vw_word_progress_by_type AS
SELECT 
    wm.user_id,
    wm.quiz_type,
    COUNT(*) AS total_words,
    COUNT(*) FILTER (WHERE wm.mastered = TRUE) AS words_mastered,
    ROUND(100.0 * COUNT(*) FILTER (WHERE wm.mastered = TRUE) / COUNT(*), 2) AS mastery_percentage
FROM word_mastery_by_type wm
GROUP BY wm.user_id, wm.quiz_type;
```

### **Words Needing Review**
```sql
-- Words for review (not yet mastered)
SELECT 
    w.word_id,
    w.word_text,
    wm.first_try_correct_count,
    wm.last_practiced
FROM word_mastery wm
JOIN words w ON wm.word_id = w.word_id
WHERE wm.user_id = ? 
  AND wm.mastered = FALSE
ORDER BY wm.first_try_correct_count ASC, wm.last_practiced ASC
LIMIT 20;
```

---

## 🛠️ Tech Stack

- **Backend:** FastAPI (Python) with SQLAlchemy ORM
- **Database:** PostgreSQL with advanced triggers and functions
- **Frontend:** HTML5, CSS3, Bootstrap 5, Vanilla JavaScript
- **Authentication:** JWT tokens with bcrypt password hashing
- **File Processing:** CSV handling with pandas and automated word extraction
- **Real-time Updates:** Database triggers for instant mastery tracking

---

## 🎯 Enhanced Quiz Flow

1. **Quiz Selection:** User chooses from 6 quiz types
2. **Smart Generation:** System creates 20 questions excluding globally mastered words
3. **Real-time Tracking:** Every response triggers automatic mastery updates
4. **Dual Progress:** Updates both global and per-type mastery simultaneously
5. **Adaptive Learning:** Future quizzes adapt based on comprehensive mastery data

---

## 🔧 Setup Instructions

### Prerequisites
- Python 3.8+
- PostgreSQL 12+
- Git

### Installation

1. **Clone the repository:**
```bash
git clone <repository-url>
cd My-first-app
```

2. **Create virtual environment:**
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate
```

3. **Install dependencies:**
```bash
pip install -r requirements.txt
```

4. **Setup PostgreSQL database:**
```bash
# Create database
createdb vocab_app

# Run schema setup
psql vocab_app < schema.sql
```

5. **Configure environment:**
```bash
# Create .env file
DATABASE_URL=postgresql://username:password@localhost/vocab_app
SECRET_KEY=your-secret-key
```

6. **Initialize sample data:**
```bash
python create_sample_data.py
```

7. **Start the application:**
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8002
```

8. **Open in browser:**
Visit `http://localhost:8002`

---

## 🗂️ CSV Upload Format

Admins can upload questions using this precise CSV format:

```csv
question_text,quiz_type,correct_answer,options
"What is a synonym of 'altruistic'?",synonym,generous,"selfish,generous,arrogant,indifferent"
"What is the antonym of 'lucid'?",antonym,obscure,"clear,bright,obvious,obscure"
"What does 'ameliorate' mean?",word_meanings,to improve,"to improve,to worsen,to ignore,to delay"
"Which word is the odd one out?",odd_man_out,destroy,"create,build,construct,destroy"
"Happy is to joyful as sad is to _____",analogies,melancholy,"cheerful,excited,melancholy,energetic"
"The professor's _____ lecture was engaging.",fill_in_blanks,fascinating,"boring,tedious,fascinating,dull"
```

### Automatic Processing:
- **Word Extraction:** System automatically extracts all words from questions, answers, and options
- **Database Updates:** Auto-populates `words` table with new vocabulary
- **Question Mapping:** Creates word-question relationships for mastery tracking
- **Duplicate Handling:** Prevents duplicate words and maintains data integrity

---

## 📈 Python CSV Upload Script

```python
import psycopg2
import pandas as pd

def upload_questions_csv(csv_file, admin_user_id=1):
    """Upload questions from CSV with automatic word extraction"""
    
    # Database connection
    conn = psycopg2.connect("postgresql://user:pass@localhost/vocab_app")
    cur = conn.cursor()
    
    # Read CSV
    df = pd.read_csv(csv_file)
    
    for _, row in df.iterrows():
        options = row['options'].split(',')
        options = [opt.strip() for opt in options]
        
        # Call stored procedure
        cur.execute("""
            SELECT insert_question_with_words(%s, %s, %s, %s, %s)
        """, (
            row['question_text'],
            row['quiz_type'], 
            row['correct_answer'],
            options,
            admin_user_id
        ))
    
    conn.commit()
    cur.close()
    conn.close()
    print(f"Successfully uploaded {len(df)} questions!")

# Usage
upload_questions_csv('sample_questions.csv')
```

---

## 🎮 API Endpoints

### **Authentication**
- `POST /api/register` - User registration
- `POST /api/token` - User login  
- `GET /api/users/me` - Current user info

### **Quiz System**
- `GET /api/quiz-types/` - Available quiz types
- `POST /api/quiz/generate` - Generate new quiz (20 questions)
- `POST /api/quiz/submit-answer` - Submit answer with auto-mastery update
- `POST /api/quiz/complete/{session_id}` - Complete quiz session
- `GET /api/progress` - User progress dashboard
- `GET /api/progress/by-type` - Progress breakdown by quiz type

### **Admin Functions**
- `POST /api/admin/upload-csv` - Bulk upload with word extraction
- `GET /api/admin/stats` - System-wide statistics
- `GET /api/admin/words` - Master words list
- `GET /api/admin/analytics` - Advanced analytics dashboard

---

## 🏆 Mastery System

### **Global Mastery**
- Word is **globally mastered** after 2 correct first-try answers across any quiz type
- Once globally mastered, word won't appear in future quizzes
- Provides overall vocabulary strength measure

### **Per-Type Mastery**  
- Word is **type-mastered** after 2 correct first-try answers within specific quiz type
- Allows targeted practice (e.g., practicing "lucid" in analogies even if mastered in synonyms)
- Enables fine-grained learning analytics

### **Smart Quiz Generation**
- Excludes globally mastered words
- Prioritizes words with low per-type mastery counts
- Balances new words with review words
- Adapts difficulty based on user performance

---

## 🔮 Advanced Features

- **Real-time Analytics:** Live dashboards for learners and admins
- **Spaced Repetition:** Optional next_review_date for optimized learning
- **Automated Reports:** Weekly progress summaries
- **Performance Metrics:** Detailed word difficulty rankings
- **Bulk Operations:** CSV export/import for content management
- **API-First Design:** Easy integration with mobile apps

---

## 🐛 Production Considerations

- **Database Indexing:** Optimize queries with proper indexes on user_id, word_id
- **Connection Pooling:** Use connection pools for high concurrent usage  
- **Trigger Performance:** Monitor trigger execution time with large datasets
- **Backup Strategy:** Regular backups of quiz data and user progress
- **Scaling:** Consider read replicas for analytics queries

---

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

---

**Built with ❤️ for comprehensive vocabulary mastery through intelligent adaptive learning!**
