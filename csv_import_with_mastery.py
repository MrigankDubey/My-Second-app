#!/usr/bin/env python3
"""
CSV Question Import with Word Mastery Tracking
This script imports questions from sample_questions.csv and demonstrates:
1. Word mastery table creation during question import
2. Word mastery tracking during quiz execution
"""

import os
import csv
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost/vocab_app')

def import_csv_questions():
    """Import questions from sample_questions.csv using enhanced word management"""
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    print("=== IMPORTING CSV QUESTIONS WITH WORD MASTERY TRACKING ===")
    
    # Get or create testuser
    cur.execute("""
        INSERT INTO users (username, password_hash, role)
        VALUES ('testuser', 'hashed_password', 'learner')
        ON CONFLICT (username) DO NOTHING
        RETURNING user_id
    """)
    result = cur.fetchone()
    if result:
        user_id = result['user_id']
        print(f"Created new testuser with ID: {user_id}")
    else:
        cur.execute("SELECT user_id FROM users WHERE username = 'testuser'")
        user_id = cur.fetchone()['user_id']
        print(f"Using existing testuser with ID: {user_id}")
    
    # Show initial statistics
    cur.execute("SELECT COUNT(*) as count FROM words")
    initial_words = cur.fetchone()['count']
    
    cur.execute("SELECT COUNT(*) as count FROM questions")
    initial_questions = cur.fetchone()['count']
    
    cur.execute("SELECT COUNT(*) as count FROM word_question_map")
    initial_mappings = cur.fetchone()['count']
    
    print(f"\nInitial database state:")
    print(f"  Words: {initial_words}")
    print(f"  Questions: {initial_questions}")
    print(f"  Word-Question mappings: {initial_mappings}")
    
    # Read and import CSV questions
    imported_questions = []
    
    with open('/workspaces/My-Second-app/sample_questions.csv', 'r', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        
        print(f"\nImporting questions from CSV...")
        
        for i, row in enumerate(reader, 1):
            question_text = row['question_text']
            quiz_type = row['quiz_type']
            correct_answer = row['correct_answer']
            options = row['options'].split(',') if row['options'] else []
            
            print(f"\n--- Question {i}: {quiz_type.upper()} ---")
            print(f"Q: {question_text}")
            print(f"Answer: {correct_answer}")
            print(f"Options: {', '.join(options)}")
            
            # Use enhanced function to add question with word mastery tracking
            cur.execute("""
                SELECT add_question_with_mastery_tracking(%s, %s, %s, %s, %s) as question_id
            """, (quiz_type, question_text, correct_answer, options, user_id))
            
            result = cur.fetchone()
            question_id = result['question_id']
            
            imported_questions.append({
                'question_id': question_id,
                'quiz_type': quiz_type,
                'question_text': question_text,
                'correct_answer': correct_answer,
                'options': options
            })
            
            print(f"✓ Imported with question ID: {question_id}")
    
    # Show final statistics
    cur.execute("SELECT COUNT(*) as count FROM words")
    final_words = cur.fetchone()['count']
    
    cur.execute("SELECT COUNT(*) as count FROM questions")
    final_questions = cur.fetchone()['count']
    
    cur.execute("SELECT COUNT(*) as count FROM word_question_map")
    final_mappings = cur.fetchone()['count']
    
    print(f"\nFinal database state:")
    print(f"  Words: {final_words} (+{final_words - initial_words})")
    print(f"  Questions: {final_questions} (+{final_questions - initial_questions})")
    print(f"  Word-Question mappings: {final_mappings} (+{final_mappings - initial_mappings})")
    
    cur.close()
    conn.close()
    
    return imported_questions, user_id

def analyze_word_mastery_creation():
    """Analyze word mastery tracking created during question import"""
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    print(f"\n=== WORD MASTERY ANALYSIS AT CREATION ===")
    
    # Get testuser ID
    cur.execute("SELECT user_id FROM users WHERE username = 'testuser'")
    user_id = cur.fetchone()['user_id']
    
    # Show overall mastery tracking statistics
    cur.execute("""
        SELECT 
            COUNT(DISTINCT word_id) as words_tracked,
            COUNT(DISTINCT question_id) as questions_tracked,
            COUNT(*) as total_mastery_records
        FROM word_question_mastery
        WHERE user_id = %s
    """, (user_id,))
    
    stats = cur.fetchone()
    print(f"Mastery tracking initialized:")
    print(f"  Words tracked: {stats['words_tracked']}")
    print(f"  Questions tracked: {stats['questions_tracked']}")
    print(f"  Total mastery records: {stats['total_mastery_records']}")
    
    # Show top words by question count
    print(f"\nTop 10 words by question count:")
    cur.execute("""
        SELECT * FROM vw_word_statistics 
        WHERE total_questions > 0 
        ORDER BY total_questions DESC, word_text 
        LIMIT 10
    """)
    
    word_stats = cur.fetchall()
    for stat in word_stats:
        print(f"  '{stat['word_text']}': {stat['total_questions']} questions across {stat['quiz_types_count']} quiz types")
        print(f"    Quiz types: {', '.join(stat['quiz_types']) if stat['quiz_types'] else 'None'}")
    
    # Show mastery tracking by quiz type
    print(f"\nMastery tracking by quiz type:")
    cur.execute("""
        SELECT 
            quiz_type,
            COUNT(DISTINCT word_id) as words,
            COUNT(DISTINCT question_id) as questions,
            COUNT(*) as mastery_records
        FROM word_question_mastery
        WHERE user_id = %s
        GROUP BY quiz_type
        ORDER BY quiz_type
    """, (user_id,))
    
    type_stats = cur.fetchall()
    for stat in type_stats:
        print(f"  {stat['quiz_type']}: {stat['words']} words, {stat['questions']} questions, {stat['mastery_records']} records")
    
    # Show sample word details
    print(f"\nSample word details (showing 'clear'):")
    cur.execute("""
        SELECT 
            w.word_text,
            wqm.quiz_type,
            q.question_text,
            wqm.is_mastered,
            wqm.first_attempt_correct_count,
            wqm.total_attempts
        FROM word_question_mastery wqm
        JOIN words w ON wqm.word_id = w.word_id
        JOIN questions q ON wqm.question_id = q.question_id
        WHERE wqm.user_id = %s AND w.word_text = 'clear'
        ORDER BY wqm.quiz_type, q.question_id
    """, (user_id,))
    
    clear_details = cur.fetchall()
    for detail in clear_details:
        print(f"  [{detail['quiz_type']}] {detail['question_text']}")
        print(f"    Mastered: {detail['is_mastered']}, Correct attempts: {detail['first_attempt_correct_count']}")
    
    cur.close()
    conn.close()

def simulate_quiz_execution(imported_questions, user_id):
    """Simulate quiz execution and demonstrate word mastery tracking updates"""
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    print(f"\n=== SIMULATING QUIZ EXECUTION WITH MASTERY TRACKING ===")
    
    # Create a quiz attempt
    cur.execute("""
        INSERT INTO quiz_attempts (user_id, quiz_type_id, started_at)
        VALUES (%s, 1, NOW())
        RETURNING attempt_id
    """, (user_id,))
    
    attempt_id = cur.fetchone()['attempt_id']
    print(f"Created quiz attempt with ID: {attempt_id}")
    
    # Select some questions for the quiz (first 10)
    quiz_questions = imported_questions[:10]
    print(f"\nSelected {len(quiz_questions)} questions for quiz simulation")
    
    # Simulate answering questions
    correct_answers = 0
    for i, question in enumerate(quiz_questions, 1):
        question_id = question['question_id']
        correct_answer = question['correct_answer']
        
        # Simulate correct answer for first 7 questions, wrong for last 3
        is_correct = i <= 7
        selected_answer = correct_answer if is_correct else "wrong_answer"
        
        print(f"\n--- Question {i} ---")
        print(f"Q: {question['question_text']}")
        print(f"Selected: {selected_answer} ({'✓ CORRECT' if is_correct else '✗ WRONG'})")
        
        # Record the response (this triggers mastery updates)
        cur.execute("""
            INSERT INTO responses (attempt_id, question_id, selected_answer, is_correct)
            VALUES (%s, %s, %s, %s)
        """, (attempt_id, question_id, selected_answer, is_correct))
        
        if is_correct:
            correct_answers += 1
    
    print(f"\nQuiz completed: {correct_answers}/{len(quiz_questions)} correct")
    
    # Analyze mastery updates after quiz
    print(f"\n=== MASTERY UPDATES AFTER QUIZ ===")
    
    # Show words that gained mastery progress
    cur.execute("""
        SELECT 
            w.word_text,
            wqm.quiz_type,
            wqm.first_attempt_correct_count,
            wqm.total_attempts,
            wqm.is_mastered,
            CASE 
                WHEN wqm.is_mastered THEN 'Mastered'
                WHEN wqm.first_attempt_correct_count = 1 THEN 'One more correct needed'
                WHEN wqm.total_attempts > 0 THEN 'Needs practice'
                ELSE 'Not attempted'
            END as status
        FROM word_question_mastery wqm
        JOIN words w ON wqm.word_id = w.word_id
        WHERE wqm.user_id = %s 
          AND wqm.total_attempts > 0
        ORDER BY wqm.first_attempt_correct_count DESC, w.word_text
    """, (user_id,))
    
    mastery_updates = cur.fetchall()
    
    print(f"Words with mastery progress:")
    for update in mastery_updates:
        print(f"  '{update['word_text']}' [{update['quiz_type']}]: {update['status']}")
        print(f"    First attempts correct: {update['first_attempt_correct_count']}, Total attempts: {update['total_attempts']}")
    
    # Show global progress
    cur.execute("""
        SELECT * FROM vw_global_word_progress WHERE user_id = %s
    """, (user_id,))
    
    global_progress = cur.fetchone()
    if global_progress:
        print(f"\nGlobal progress after quiz:")
        print(f"  Words encountered: {global_progress['total_words_encountered']}")
        print(f"  Words fully mastered: {global_progress['words_fully_mastered']}")
        print(f"  Words partially mastered: {global_progress['words_partially_mastered']}")
        print(f"  Word mastery percentage: {global_progress['word_mastery_percentage']}%")
        print(f"  Questions mastered: {global_progress['questions_mastered']}/{global_progress['total_questions_encountered']}")
    
    cur.close()
    conn.close()
    
    return attempt_id

def simulate_mastery_achievement(user_id):
    """Simulate achieving mastery for some words by taking another quiz"""
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    print(f"\n=== SIMULATING MASTERY ACHIEVEMENT (2ND QUIZ) ===")
    
    # Create another quiz attempt
    cur.execute("""
        INSERT INTO quiz_attempts (user_id, quiz_type_id, started_at)
        VALUES (%s, 1, NOW())
        RETURNING attempt_id
    """, (user_id,))
    
    attempt_id = cur.fetchone()['attempt_id']
    print(f"Created second quiz attempt with ID: {attempt_id}")
    
    # Get questions that had correct answers in first quiz (to achieve mastery)
    cur.execute("""
        SELECT DISTINCT 
            q.question_id,
            q.question_text,
            q.correct_answer,
            w.word_text
        FROM responses r
        JOIN questions q ON r.question_id = q.question_id
        JOIN word_question_map wqm ON q.question_id = wqm.question_id
        JOIN words w ON wqm.word_id = w.word_id
        WHERE r.is_correct = TRUE 
          AND r.attempt_id = (
              SELECT attempt_id FROM quiz_attempts 
              WHERE user_id = %s 
              ORDER BY started_at DESC 
              LIMIT 1 OFFSET 1
          )
        LIMIT 5
    """, (user_id,))
    
    mastery_questions = cur.fetchall()
    
    print(f"Re-attempting {len(mastery_questions)} previously correct questions to achieve mastery:")
    
    for i, question in enumerate(mastery_questions, 1):
        print(f"\n--- Mastery Question {i} ---")
        print(f"Q: {question['question_text']}")
        print(f"Answer: {question['correct_answer']} (✓ CORRECT - aiming for mastery)")
        
        # Record correct response (this should achieve mastery for 2nd correct first attempt)
        cur.execute("""
            INSERT INTO responses (attempt_id, question_id, selected_answer, is_correct)
            VALUES (%s, %s, %s, %s)
        """, (attempt_id, question['question_id'], question['correct_answer'], True))
    
    # Check for newly mastered words
    print(f"\n=== MASTERY ACHIEVEMENTS ===")
    
    cur.execute("""
        SELECT 
            w.word_text,
            wqm.quiz_type,
            wqm.first_attempt_correct_count,
            wqm.is_mastered,
            q.question_text
        FROM word_question_mastery wqm
        JOIN words w ON wqm.word_id = w.word_id
        JOIN questions q ON wqm.question_id = q.question_id
        WHERE wqm.user_id = %s 
          AND wqm.is_mastered = TRUE
        ORDER BY w.word_text, wqm.quiz_type
    """, (user_id,))
    
    mastered_words = cur.fetchall()
    
    if mastered_words:
        print(f"Newly mastered word-question combinations:")
        current_word = None
        for mastery in mastered_words:
            if mastery['word_text'] != current_word:
                current_word = mastery['word_text']
                print(f"\n  Word: '{current_word}'")
            
            print(f"    [{mastery['quiz_type']}] {mastery['question_text']}")
            print(f"      ✓ MASTERED (2/2 first attempts correct)")
    else:
        print("No words achieved full mastery yet (need 2 correct first attempts per question)")
    
    # Show updated global progress
    cur.execute("""
        SELECT * FROM vw_global_word_progress WHERE user_id = %s
    """, (user_id,))
    
    final_progress = cur.fetchone()
    if final_progress:
        print(f"\nFinal global progress:")
        print(f"  Words encountered: {final_progress['total_words_encountered']}")
        print(f"  Words fully mastered: {final_progress['words_fully_mastered']}")
        print(f"  Word mastery percentage: {final_progress['word_mastery_percentage']}%")
        print(f"  Questions mastered: {final_progress['questions_mastered']}/{final_progress['total_questions_encountered']}")
    
    cur.close()
    conn.close()

def main():
    """Main execution function"""
    print("=== CSV IMPORT WITH COMPREHENSIVE WORD MASTERY DEMONSTRATION ===")
    
    try:
        # 1. Import CSV questions with word mastery tracking
        imported_questions, user_id = import_csv_questions()
        
        # 2. Analyze word mastery table creation
        analyze_word_mastery_creation()
        
        # 3. Simulate quiz execution with mastery tracking
        attempt_id1 = simulate_quiz_execution(imported_questions, user_id)
        
        # 4. Simulate achieving mastery through repeated correct answers
        simulate_mastery_achievement(user_id)
        
        print(f"\n=== DEMONSTRATION COMPLETE ===")
        print(f"✓ Imported {len(imported_questions)} questions from CSV")
        print(f"✓ Demonstrated word mastery table creation and initialization")
        print(f"✓ Showed real-time mastery tracking during quiz execution")
        print(f"✓ Illustrated mastery achievement through repeated correct answers")
        print(f"✓ Comprehensive word-level and question-level progress tracking")
        
        print(f"\nKey Features Demonstrated:")
        print(f"• Automatic word extraction and deduplication during CSV import")
        print(f"• Real-time mastery updates via database triggers")
        print(f"• Question-level mastery tracking (2 correct first attempts = mastered)")
        print(f"• Word mastery percentage calculation across all associated questions")
        print(f"• Comprehensive progress analytics and reporting")
        
    except Exception as e:
        print(f"Error during demonstration: {e}")
        raise

if __name__ == "__main__":
    main()
