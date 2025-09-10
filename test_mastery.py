#!/usr/bin/env python3
"""
Word Mastery Test - Simulates a quiz attempt to demonstrate word mastery tracking
"""

import os
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost/vocab_app')

def simulate_quiz_attempt():
    """Simulate a user taking a quiz and demonstrate mastery tracking"""
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    # Get testuser ID
    cur.execute("SELECT user_id FROM users WHERE username = 'testuser'")
    user_id = cur.fetchone()['user_id']
    
    # Get a synonym quiz type
    cur.execute("SELECT quiz_type_id FROM quiz_types WHERE name = 'synonym'")
    quiz_type_id = cur.fetchone()['quiz_type_id']
    
    # Start a quiz attempt
    cur.execute("""
        INSERT INTO quiz_attempts (user_id, quiz_type_id)
        VALUES (%s, %s)
        RETURNING attempt_id
    """, (user_id, quiz_type_id))
    attempt_id = cur.fetchone()['attempt_id']
    
    print(f"Started quiz attempt {attempt_id} for user {user_id}")
    
    # Get some synonym questions
    cur.execute("""
        SELECT q.question_id, q.question_text, q.correct_answer
        FROM questions q
        JOIN quiz_types qt ON q.quiz_type_id = qt.quiz_type_id
        WHERE qt.name = 'synonym'
        LIMIT 3
    """)
    questions = cur.fetchall()
    
    print(f"\nSimulating answers to {len(questions)} questions:")
    
    for i, question in enumerate(questions):
        question_id = question['question_id']
        correct_answer = question['correct_answer']
        question_text = question['question_text']
        
        # Simulate correct answer for first 2 questions, wrong for 3rd
        is_correct = i < 2
        selected_answer = correct_answer if is_correct else "wrong_answer"
        
        print(f"  Q: {question_text}")
        print(f"  A: {selected_answer} ({'CORRECT' if is_correct else 'INCORRECT'})")
        
        # Record the response (this will trigger the mastery update trigger)
        cur.execute("""
            INSERT INTO responses (attempt_id, question_id, selected_answer, is_correct)
            VALUES (%s, %s, %s, %s)
        """, (attempt_id, question_id, selected_answer, is_correct))
    
    # Check word mastery updates
    print(f"\nChecking word mastery updates...")
    
    # Get words from the questions we just answered
    cur.execute("""
        SELECT DISTINCT w.word_text, wm.first_try_correct_count, wm.mastered
        FROM responses r
        JOIN questions q ON r.question_id = q.question_id
        JOIN word_question_map wqm ON q.question_id = wqm.question_id
        JOIN words w ON wqm.word_id = w.word_id
        JOIN word_mastery wm ON w.word_id = wm.word_id AND wm.user_id = %s
        WHERE r.attempt_id = %s
        ORDER BY w.word_text
    """, (user_id, attempt_id))
    
    mastery_updates = cur.fetchall()
    
    print(f"Word mastery updates for this quiz:")
    for update in mastery_updates:
        print(f"  {update['word_text']}: {update['first_try_correct_count']} correct attempts, mastered: {update['mastered']}")
    
    # Check by-type mastery
    cur.execute("""
        SELECT DISTINCT w.word_text, wmt.quiz_type, wmt.first_try_correct_count, wmt.mastered
        FROM responses r
        JOIN questions q ON r.question_id = q.question_id
        JOIN word_question_map wqm ON q.question_id = wqm.question_id
        JOIN words w ON wqm.word_id = w.word_id
        JOIN word_mastery_by_type wmt ON w.word_id = wmt.word_id AND wmt.user_id = %s
        WHERE r.attempt_id = %s AND wmt.quiz_type = 'synonym'
        ORDER BY w.word_text
    """, (user_id, attempt_id))
    
    type_mastery_updates = cur.fetchall()
    
    print(f"\nPer-type mastery updates (synonym):")
    for update in type_mastery_updates:
        print(f"  {update['word_text']}: {update['first_try_correct_count']} correct attempts, mastered: {update['mastered']}")
    
    cur.close()
    conn.close()
    
    return attempt_id

def show_current_mastery_status():
    """Show current mastery status for testuser"""
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    # Get testuser ID
    cur.execute("SELECT user_id FROM users WHERE username = 'testuser'")
    user_id = cur.fetchone()['user_id']
    
    # Show global progress
    cur.execute("""
        SELECT * FROM vw_global_word_progress WHERE user_id = %s
    """, (user_id,))
    
    global_progress = cur.fetchone()
    if global_progress:
        print(f"\nGLOBAL MASTERY PROGRESS:")
        print(f"  Total words encountered: {global_progress['total_words_encountered']}")
        print(f"  Words mastered: {global_progress['words_mastered']}")
        print(f"  Words pending: {global_progress['words_pending']}")
        print(f"  Mastery percentage: {global_progress['mastery_percentage']}%")
    
    # Show progress by type
    cur.execute("""
        SELECT * FROM vw_word_progress_by_type WHERE user_id = %s ORDER BY quiz_type
    """, (user_id,))
    
    type_progress = cur.fetchall()
    print(f"\nMASSTERY BY QUIZ TYPE:")
    for progress in type_progress:
        print(f"  {progress['quiz_type']}: {progress['words_mastered']}/{progress['total_words']} words ({progress['mastery_percentage']}%)")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    print("=== WORD MASTERY TRACKING DEMONSTRATION ===")
    
    print("\n1. Current mastery status (before quiz):")
    show_current_mastery_status()
    
    print(f"\n2. Simulating a quiz attempt...")
    attempt_id = simulate_quiz_attempt()
    
    print(f"\n3. Updated mastery status (after quiz):")
    show_current_mastery_status()
    
    print(f"\n=== Demo Complete ===")
    print(f"Quiz attempt ID: {attempt_id}")
    print(f"The word mastery tracking system automatically updated when responses were recorded!")
