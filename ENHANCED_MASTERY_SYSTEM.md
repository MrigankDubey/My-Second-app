# Enhanced Question-Level Word Mastery System

## Overview

The enhanced word mastery system tracks mastery at the **question level** for each word, providing precise measurement of vocabulary learning progress. Word mastery is calculated as the **percentage of questions mastered** rather than just counting correct attempts.

## Key Features

### 🎯 Question-Level Mastery Tracking
- **Individual Question Tracking**: Each question associated with a word is tracked separately
- **Mastery Threshold**: A question is considered "mastered" when answered correctly **twice on first attempt**
- **Word Mastery Percentage**: Calculated as `(questions mastered / total questions for word) × 100`

### 📊 Example Mastery Calculation

**Word: "happy"**
- Appears in 4 questions across different quiz types:
  1. Synonym question: "What is a synonym for joyful?" → **Mastered** (2/2 correct first attempts)
  2. Antonym question: "What is the opposite of sad?" → **Not mastered** (1/2 correct first attempts)
  3. Fill-in-blank: "She felt _____ after good news" → **Mastered** (2/2 correct first attempts)
  4. Word meaning: "Choose the meaning of elated" → **Not mastered** (0/2 correct first attempts)

**Word Mastery for "happy"**: 2 mastered questions ÷ 4 total questions = **50% mastery**

## Database Schema

### Core Table: `word_question_mastery`
```sql
CREATE TABLE word_question_mastery (
    mastery_id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(user_id),
    word_id INT REFERENCES words(word_id),
    question_id INT REFERENCES questions(question_id),
    quiz_type VARCHAR(50) NOT NULL,
    first_attempt_correct_count INT DEFAULT 0,  -- Counts first-try correct answers
    total_attempts INT DEFAULT 0,               -- Total times attempted
    is_mastered BOOLEAN DEFAULT FALSE,          -- TRUE when first_attempt_correct_count >= 2
    first_correct_at TIMESTAMP NULL,            -- When first correct answer achieved
    last_attempted_at TIMESTAMP DEFAULT NOW(),  -- Last attempt timestamp
    UNIQUE(user_id, word_id, question_id)
);
```

### Aggregated Views

#### `word_mastery` - Word-Level Summary
```sql
SELECT 
    user_id,
    word_id,
    COUNT(*) as total_questions,
    COUNT(*) FILTER (WHERE is_mastered = TRUE) as questions_mastered,
    ROUND(100.0 * COUNT(*) FILTER (WHERE is_mastered = TRUE) / COUNT(*), 2) as mastery_percentage,
    CASE WHEN COUNT(*) FILTER (WHERE is_mastered = TRUE) = COUNT(*) THEN TRUE ELSE FALSE END as fully_mastered
FROM word_question_mastery
GROUP BY user_id, word_id;
```

#### `word_mastery_by_type` - Quiz Type Breakdown
```sql
SELECT 
    user_id,
    word_id,
    quiz_type,
    COUNT(*) as total_questions,
    COUNT(*) FILTER (WHERE is_mastered = TRUE) as questions_mastered,
    ROUND(100.0 * COUNT(*) FILTER (WHERE is_mastered = TRUE) / COUNT(*), 2) as mastery_percentage
FROM word_question_mastery
GROUP BY user_id, word_id, quiz_type;
```

## Automatic Updates

### Trigger Function: `update_question_mastery()`
```sql
-- Automatically updates mastery when a response is recorded
CREATE TRIGGER trg_update_question_mastery
AFTER INSERT ON responses
FOR EACH ROW
EXECUTE FUNCTION update_question_mastery();
```

**Logic**:
1. **First Attempt Detection**: Checks if this is the first try for the question in current quiz session
2. **Correct Answer Tracking**: Increments `first_attempt_correct_count` only for correct first attempts
3. **Mastery Determination**: Sets `is_mastered = TRUE` when `first_attempt_correct_count >= 2`
4. **Multi-Word Support**: Updates mastery for all words associated with the question

## Enhanced Quiz Generation

### Smart Question Selection
```sql
-- Excludes questions where ALL associated words are fully mastered
SELECT get_quiz_questions_excluding_mastered(user_id, quiz_type, limit);
```

**Benefits**:
- **Adaptive Learning**: Focuses on words that need practice
- **Efficient Studying**: Avoids repeating fully mastered content
- **Progressive Difficulty**: Gradually increases word mastery coverage

## Dashboard Analytics

### Global Progress View
```sql
CREATE VIEW vw_global_word_progress AS
SELECT 
    user_id,
    COUNT(DISTINCT word_id) as total_words_encountered,
    COUNT(DISTINCT word_id) FILTER (WHERE fully_mastered = TRUE) as words_fully_mastered,
    ROUND(100.0 * COUNT(DISTINCT word_id) FILTER (WHERE fully_mastered = TRUE) / COUNT(DISTINCT word_id), 2) as word_mastery_percentage,
    SUM(total_questions) as total_questions_encountered,
    SUM(questions_mastered) as questions_mastered
FROM word_mastery
GROUP BY user_id;
```

### Detailed Word Analysis
```sql
CREATE VIEW vw_detailed_word_mastery AS
SELECT 
    wqm.user_id,
    w.word_text,
    wqm.quiz_type,
    q.question_text,
    wqm.first_attempt_correct_count,
    wqm.total_attempts,
    wqm.is_mastered,
    CASE 
        WHEN wqm.is_mastered THEN 'Mastered'
        WHEN wqm.first_attempt_correct_count = 1 THEN 'One more correct needed'
        WHEN wqm.total_attempts > 0 THEN 'Needs practice'
        ELSE 'Not attempted'
    END as mastery_status
FROM word_question_mastery wqm
JOIN words w ON wqm.word_id = w.word_id
JOIN questions q ON wqm.question_id = q.question_id;
```

## Usage Examples

### Test Results Summary
From the recent test execution:

**Global Statistics**:
- Words encountered: 144
- Words fully mastered: 12 (8.33%)
- Questions mastered: 12/180 (6.67%)

**Word Examples**:
- **"book"**: 1/1 questions mastered → **100% mastery** ✅
- **"happy"**: 0/8 questions mastered → **0% mastery** (needs practice)
- **"large"**: 0/3 questions mastered → **0% mastery** (needs practice)

**Quiz Type Performance**:
- **Analogy**: 60% word mastery (12/20 words fully mastered)
- **Synonym**: 0% word mastery (0/38 words fully mastered)
- **Antonym**: 0% word mastery (0/35 words fully mastered)

## Advantages Over Previous System

### ✅ Enhanced Accuracy
- **Granular Tracking**: Tracks mastery per question, not just per word
- **Contextual Learning**: Different question contexts for the same word are tracked separately
- **Precise Metrics**: Exact percentage calculation based on actual question mastery

### ✅ Better Learning Insights
- **Question-Level Analysis**: Shows exactly which questions need more practice
- **Type-Specific Progress**: Tracks performance across different quiz types
- **Review Prioritization**: Identifies specific areas needing attention

### ✅ Adaptive System
- **Smart Quiz Generation**: Excludes fully mastered content automatically
- **Focused Practice**: Directs attention to words needing improvement
- **Progressive Learning**: Supports natural vocabulary acquisition patterns

## Implementation Benefits

1. **Automatic Updates**: No manual intervention required - triggers handle all updates
2. **Performance Optimized**: Efficient indexing and query structure
3. **Scalable Design**: Handles large vocabularies and user bases
4. **Detailed Analytics**: Comprehensive reporting and progress tracking
5. **Educational Value**: Aligns with proven vocabulary learning methodologies

This enhanced system provides a much more accurate and useful measurement of vocabulary mastery, supporting effective learning through precise tracking and adaptive content delivery.
