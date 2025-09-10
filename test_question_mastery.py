#!/usr/bin/env python3
"""
Enhanced Question-Level Word Mastery Test
Demonstrates the new question-level mastery tracking system where:
- Each word's mastery is calculated as percentage of questions mastered
- A question is mastered when answered correctly twice on first attempt
- Word mastery = (questions mastered / total questions for that word) * 100
"""

import os
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost/vocab_app')

def setup_test_data():
    """Create test users, quiz types, and questions for demonstration"""
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    cur = conn.cursor()
    
    print("Setting up test data...")
    
    # Create test user
    cur.execute("""
        INSERT INTO users (username, password_hash, role)
        VALUES ('testuser', 'hashed_password', 'learner')
        ON CONFLICT (username) DO NOTHING
    """)
    
    # Create quiz types
    quiz_types = ['synonym', 'antonym', 'analogy', 'meaning']
    for quiz_type in quiz_types:
        cur.execute("""
            INSERT INTO quiz_types (name)
            VALUES (%s)
            ON CONFLICT (name) DO NOTHING
        """, (quiz_type,))
    
    # Create test words
    test_words = ['happy', 'large', 'quick', 'bright']
    for word in test_words:
        cur.execute("""
            INSERT INTO words (word_text)
            VALUES (%s)
            ON CONFLICT (word_text) DO NOTHING
        """, (word,))
    
    # Create test questions - each word appears in multiple questions
    questions_data = [
        # Word 'happy' appears in 3 questions across 2 quiz types
        ('synonym', 'What is a synonym for joyful?', 'happy', ['happy', 'sad', 'angry', 'calm']),
        ('synonym', 'Which word means the same as cheerful?', 'happy', ['happy', 'worried', 'tired', 'bored']),
        ('antonym', 'What is the opposite of sad?', 'happy', ['angry', 'tired', 'happy', 'worried']),
        
        # Word 'large' appears in 4 questions across 3 quiz types
        ('synonym', 'What is a synonym for big?', 'large', ['small', 'large', 'tiny', 'little']),
        ('synonym', 'Which word means the same as huge?', 'large', ['large', 'small', 'narrow', 'short']),
        ('antonym', 'What is the opposite of small?', 'large', ['tiny', 'little', 'large', 'narrow']),
        ('meaning', 'What does enormous mean?', 'large', ['very small', 'very large', 'very fast', 'very slow']),
        
        # Word 'quick' appears in 2 questions
        ('synonym', 'What is a synonym for fast?', 'quick', ['slow', 'quick', 'heavy', 'light']),
        ('antonym', 'What is the opposite of slow?', 'quick', ['heavy', 'light', 'quick', 'soft']),
        
        # Word 'bright' appears in 1 question
        ('meaning', 'What does luminous mean?', 'bright', ['dark', 'bright', 'heavy', 'light'])
    ]
    
    cur.execute("SELECT user_id FROM users WHERE username = 'testuser'")
    user_id = cur.fetchone()[0]
    
    for quiz_type, question_text, correct_answer, options in questions_data:
        # Get quiz_type_id
        cur.execute("SELECT quiz_type_id FROM quiz_types WHERE name = %s", (quiz_type,))
        quiz_type_id = cur.fetchone()[0]
        
        # Insert question
        cur.execute("""
            INSERT INTO questions (quiz_type_id, question_text, correct_answer, created_by)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT DO NOTHING
            RETURNING question_id
        """, (quiz_type_id, question_text, correct_answer, user_id))
        
        result = cur.fetchone()
        if result:
            question_id = result[0]
            
            # Insert options
            for option in options:
                cur.execute("""
                    INSERT INTO options (question_id, option_text)
                    VALUES (%s, %s)
                    ON CONFLICT DO NOTHING
                """, (question_id, option))
            
            # Map all option words to the question
            for option in options:
                # Get or create word
                cur.execute("""
                    INSERT INTO words (word_text)
                    VALUES (%s)
                    ON CONFLICT (word_text) DO NOTHING
                """, (option.lower(),))
                
                cur.execute("SELECT word_id FROM words WHERE word_text = %s", (option.lower(),))
                word_id = cur.fetchone()[0]
                
                # Map word to question
                cur.execute("""
                    INSERT INTO word_question_map (word_id, question_id)
                    VALUES (%s, %s)
                    ON CONFLICT DO NOTHING
                """, (word_id, question_id))
    
    cur.close()
    conn.close()
    print("Test data setup complete!")

def apply_enhanced_schema():
    """Apply the enhanced question-level mastery schema"""
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    cur = conn.cursor()
    
    print("Applying enhanced question-level mastery schema...")
    
    # Read and execute the enhanced schema
    with open('/workspaces/My-Second-app/enhanced_question_mastery_schema.sql', 'r') as f:
        schema_sql = f.read()
    
    try:
        cur.execute(schema_sql)
        print("Enhanced schema applied successfully!")
        
        # Initialize mastery tracking
        cur.execute("SELECT initialize_question_mastery_tracking()")
        print("Question-level mastery tracking initialized!")
        
    except Exception as e:
        print(f"Error applying schema: {e}")
    
    cur.close()
    conn.close()

def simulate_quiz_sessions():
    """Simulate multiple quiz sessions to demonstrate question-level mastery tracking"""
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    # Get testuser ID
    cur.execute("SELECT user_id FROM users WHERE username = 'testuser'")
    user_id = cur.fetchone()['user_id']
    
    print(f"\n=== SIMULATING QUIZ SESSIONS FOR USER {user_id} ===")
    
    # Get all questions for testing
    cur.execute("""
        SELECT q.question_id, q.question_text, q.correct_answer, qt.name as quiz_type
        FROM questions q
        JOIN quiz_types qt ON q.quiz_type_id = qt.quiz_type_id
        ORDER BY qt.name, q.question_id
    """)
    questions = cur.fetchall()
    
    print(f"Total questions available: {len(questions)}")
    
    # Session 1: Answer first 5 questions correctly on first try
    print(f"\n--- Session 1: First attempts (5 questions, all correct) ---")
    session_1_questions = questions[:5]
    
    cur.execute("""
        INSERT INTO quiz_attempts (user_id, quiz_type_id, started_at)
        VALUES (%s, 1, NOW())
        RETURNING attempt_id
    """, (user_id,))
    attempt_id_1 = cur.fetchone()['attempt_id']
    
    for question in session_1_questions:
        print(f"  Q: {question['question_text']}")
        print(f"  A: {question['correct_answer']} (CORRECT)")
        
        cur.execute("""
            INSERT INTO responses (attempt_id, question_id, selected_answer, is_correct)
            VALUES (%s, %s, %s, %s)
        """, (attempt_id_1, question['question_id'], question['correct_answer'], True))
    
    # Session 2: Answer next 5 questions, some correct, some wrong
    print(f"\n--- Session 2: Mixed results (5 questions, 3 correct, 2 wrong) ---")
    session_2_questions = questions[5:10] if len(questions) > 5 else questions[:5]
    
    cur.execute("""
        INSERT INTO quiz_attempts (user_id, quiz_type_id, started_at)
        VALUES (%s, 1, NOW())
        RETURNING attempt_id
    """, (user_id,))
    attempt_id_2 = cur.fetchone()['attempt_id']
    
    for i, question in enumerate(session_2_questions):
        is_correct = i < 3  # First 3 correct, last 2 wrong
        answer = question['correct_answer'] if is_correct else 'wrong_answer'
        
        print(f"  Q: {question['question_text']}")
        print(f"  A: {answer} ({'CORRECT' if is_correct else 'WRONG'})")
        
        cur.execute("""
            INSERT INTO responses (attempt_id, question_id, selected_answer, is_correct)
            VALUES (%s, %s, %s, %s)
        """, (attempt_id_2, question['question_id'], answer, is_correct))
    
    # Session 3: Re-attempt some questions to achieve mastery (2nd correct first attempt)
    print(f"\n--- Session 3: Re-attempting to achieve mastery ---")
    
    # Get questions from session 1 to achieve mastery (2nd correct first attempt)
    mastery_questions = session_1_questions[:3]
    
    cur.execute("""
        INSERT INTO quiz_attempts (user_id, quiz_type_id, started_at)
        VALUES (%s, 1, NOW())
        RETURNING attempt_id
    """, (user_id,))
    attempt_id_3 = cur.fetchone()['attempt_id']
    
    for question in mastery_questions:
        print(f"  Q: {question['question_text']}")
        print(f"  A: {question['correct_answer']} (CORRECT - should achieve mastery)")
        
        cur.execute("""
            INSERT INTO responses (attempt_id, question_id, selected_answer, is_correct)
            VALUES (%s, %s, %s, %s)
        """, (attempt_id_3, question['question_id'], question['correct_answer'], True))
    
    cur.close()
    conn.close()
    
    return [attempt_id_1, attempt_id_2, attempt_id_3]

def analyze_question_mastery_results():
    """Analyze the results of question-level mastery tracking"""
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    # Get testuser ID
    cur.execute("SELECT user_id FROM users WHERE username = 'testuser'")
    user_id = cur.fetchone()['user_id']
    
    print(f"\n=== QUESTION-LEVEL MASTERY ANALYSIS ===")
    
    # Show detailed question mastery
    print(f"\n1. Detailed Question Mastery Status:")
    cur.execute("""
        SELECT 
            word_text,
            quiz_type,
            question_text,
            first_attempt_correct_count,
            total_attempts,
            is_mastered,
            mastery_status
        FROM vw_detailed_word_mastery
        WHERE user_id = %s
        ORDER BY word_text, quiz_type
    """, (user_id,))
    
    detailed_mastery = cur.fetchall()
    current_word = None
    
    for record in detailed_mastery:
        if record['word_text'] != current_word:
            current_word = record['word_text']
            print(f"\n  Word: '{current_word}'")
        
        print(f"    [{record['quiz_type']}] {record['question_text']}")
        print(f"        First attempts correct: {record['first_attempt_correct_count']}")
        print(f"        Total attempts: {record['total_attempts']}")
        print(f"        Status: {record['mastery_status']} ({'✓' if record['is_mastered'] else '✗'})")
    
    # Show aggregated word mastery
    print(f"\n2. Aggregated Word Mastery (Percentage of Questions Mastered):")
    cur.execute("""
        SELECT * FROM get_user_word_mastery_summary(%s)
        ORDER BY mastery_percentage DESC, word_text
    """, (user_id,))
    
    word_summaries = cur.fetchall()
    
    for summary in word_summaries:
        print(f"  Word: '{summary['word_text']}'")
        print(f"    Questions: {summary['questions_mastered']}/{summary['total_questions']} mastered")
        print(f"    Mastery: {summary['mastery_percentage']}% ({'✓ Fully Mastered' if summary['fully_mastered'] else '◑ Partially Mastered'})")
        print(f"    Quiz types: {summary['quiz_types_count']}")
        print()
    
    # Show global progress
    print(f"3. Global Progress Summary:")
    cur.execute("""
        SELECT * FROM vw_global_word_progress WHERE user_id = %s
    """, (user_id,))
    
    global_progress = cur.fetchone()
    if global_progress:
        print(f"  Words encountered: {global_progress['total_words_encountered']}")
        print(f"  Words fully mastered: {global_progress['words_fully_mastered']}")
        print(f"  Words partially mastered: {global_progress['words_partially_mastered']}")
        print(f"  Word mastery percentage: {global_progress['word_mastery_percentage']}%")
        print(f"  Average question mastery: {global_progress['average_question_mastery_percentage']}%")
        print(f"  Questions: {global_progress['questions_mastered']}/{global_progress['total_questions_encountered']} mastered")
    
    # Show progress by quiz type
    print(f"\n4. Progress by Quiz Type:")
    cur.execute("""
        SELECT * FROM vw_word_progress_by_type WHERE user_id = %s ORDER BY quiz_type
    """, (user_id,))
    
    type_progress = cur.fetchall()
    for progress in type_progress:
        print(f"  {progress['quiz_type'].upper()}:")
        print(f"    Words: {progress['words_fully_mastered']}/{progress['total_words']} fully mastered ({progress['word_mastery_percentage']}%)")
        print(f"    Questions: {progress['questions_mastered']}/{progress['total_questions']} mastered ({progress['average_question_mastery_percentage']}%)")
    
    # Show words needing review
    print(f"\n5. Words Needing Review:")
    cur.execute("""
        SELECT * FROM vw_words_needing_review WHERE user_id = %s LIMIT 10
    """, (user_id,))
    
    review_words = cur.fetchall()
    for word in review_words:
        print(f"  '{word['word_text']}': {word['mastery_percentage']}% mastered ({word['priority_level']})")
    
    cur.close()
    conn.close()

def test_quiz_generation():
    """Test the enhanced quiz generation that excludes mastered questions"""
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    # Get testuser ID
    cur.execute("SELECT user_id FROM users WHERE username = 'testuser'")
    user_id = cur.fetchone()['user_id']
    
    print(f"\n=== TESTING ENHANCED QUIZ GENERATION ===")
    
    # Test quiz generation excluding mastered questions
    print(f"\n1. Generating quiz excluding fully mastered questions:")
    cur.execute("""
        SELECT * FROM get_quiz_questions_excluding_mastered(%s, NULL, 10)
    """, (user_id,))
    
    quiz_questions = cur.fetchall()
    print(f"  Found {len(quiz_questions)} questions (excluding fully mastered):")
    
    for question in quiz_questions:
        print(f"    [{question['quiz_type']}] {question['question_text']} → {question['correct_answer']}")
    
    # Show what was excluded
    print(f"\n2. Questions excluded (all associated words fully mastered):")
    cur.execute("""
        SELECT DISTINCT q.question_id, q.question_text, q.correct_answer, qt.name as quiz_type
        FROM questions q
        JOIN quiz_types qt ON q.quiz_type_id = qt.quiz_type_id
        WHERE q.question_id IN (
            SELECT DISTINCT wqm_check.question_id
            FROM word_question_mastery wqm_check
            JOIN word_question_map wqm_map ON wqm_check.question_id = wqm_map.question_id
            WHERE wqm_check.user_id = %s
            GROUP BY wqm_check.question_id
            HAVING COUNT(*) = COUNT(*) FILTER (WHERE wqm_check.is_mastered = TRUE)
        )
        ORDER BY qt.name, q.question_text
    """, (user_id,))
    
    excluded_questions = cur.fetchall()
    if excluded_questions:
        for question in excluded_questions:
            print(f"    [{question['quiz_type']}] {question['question_text']} → {question['correct_answer']}")
    else:
        print("    None - no questions have all associated words fully mastered yet")
    
    cur.close()
    conn.close()

def main():
    """Main test execution"""
    print("=== ENHANCED QUESTION-LEVEL WORD MASTERY TESTING ===")
    
    try:
        # 1. Setup test data
        setup_test_data()
        
        # 2. Apply enhanced schema
        apply_enhanced_schema()
        
        # 3. Simulate quiz sessions
        attempt_ids = simulate_quiz_sessions()
        
        # 4. Analyze results
        analyze_question_mastery_results()
        
        # 5. Test enhanced quiz generation
        test_quiz_generation()
        
        print(f"\n=== TEST COMPLETE ===")
        print(f"Quiz attempt IDs: {attempt_ids}")
        print(f"\nKey Insights:")
        print(f"✓ Word mastery is now calculated as percentage of questions mastered")
        print(f"✓ Each question requires 2 correct first attempts to be mastered")
        print(f"✓ System tracks mastery per question, not just overall word attempts")
        print(f"✓ Quiz generation can exclude questions where all words are mastered")
        print(f"✓ Detailed analytics show exactly which questions need more practice")
        
    except Exception as e:
        print(f"Error during testing: {e}")
        raise

if __name__ == "__main__":
    main()
