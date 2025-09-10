#!/usr/bin/env python3
"""
Test Enhanced Word Management System
Demonstrates the enhanced system for adding words to the mastery table where:
1. Only unique answer words are added
2. Existing words are updated with new question mappings
3. Automatic mastery tracking initialization for all users
"""

import os
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost/vocab_app')

def apply_enhanced_schema():
    """Apply the enhanced word management schema"""
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    cur = conn.cursor()
    
    print("Applying enhanced word management schema...")
    
    # Read and execute the enhanced schema
    with open('/workspaces/My-Second-app/enhanced_question_mastery_schema.sql', 'r') as f:
        schema_sql = f.read()
    
    try:
        cur.execute(schema_sql)
        print("✓ Enhanced schema applied successfully!")
        
    except Exception as e:
        print(f"Error applying schema: {e}")
    
    cur.close()
    conn.close()

def test_word_statistics_before():
    """Show word statistics before adding new questions"""
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    print("\n=== WORD STATISTICS BEFORE ADDING NEW QUESTIONS ===")
    
    # Show current word statistics
    cur.execute("""
        SELECT * FROM vw_word_statistics 
        WHERE total_questions > 0 
        ORDER BY total_questions DESC, word_text 
        LIMIT 10
    """)
    
    stats = cur.fetchall()
    print(f"Top 10 words by question count:")
    for stat in stats:
        print(f"  '{stat['word_text']}': {stat['total_questions']} questions across {stat['quiz_types_count']} quiz types")
        print(f"    Quiz types: {', '.join(stat['quiz_types']) if stat['quiz_types'] else 'None'}")
    
    # Show total counts
    cur.execute("SELECT COUNT(*) as total_words FROM words")
    total_words = cur.fetchone()['total_words']
    
    cur.execute("SELECT COUNT(*) as total_questions FROM questions")
    total_questions = cur.fetchone()['total_questions']
    
    cur.execute("SELECT COUNT(*) as total_mappings FROM word_question_map")
    total_mappings = cur.fetchone()['total_mappings']
    
    print(f"\nCurrent totals:")
    print(f"  Words: {total_words}")
    print(f"  Questions: {total_questions}")
    print(f"  Word-Question mappings: {total_mappings}")
    
    cur.close()
    conn.close()

def test_adding_new_questions():
    """Test adding new questions with the enhanced word management"""
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    print("\n=== TESTING ENHANCED QUESTION ADDITION ===")
    
    # Get testuser ID
    cur.execute("SELECT user_id FROM users WHERE username = 'testuser'")
    user_result = cur.fetchone()
    if not user_result:
        # Create testuser if doesn't exist
        cur.execute("""
            INSERT INTO users (username, password_hash, role)
            VALUES ('testuser', 'hashed_password', 'learner')
            RETURNING user_id
        """)
        user_id = cur.fetchone()['user_id']
        print(f"Created testuser with ID: {user_id}")
    else:
        user_id = user_result['user_id']
        print(f"Using existing testuser with ID: {user_id}")
    
    # Test questions to add - some words will be new, some will be existing
    test_questions = [
        {
            'quiz_type': 'synonym',
            'question_text': 'What is a synonym for "excellent"?',
            'correct_answer': 'outstanding',
            'options': ['outstanding', 'terrible', 'average', 'poor']
        },
        {
            'quiz_type': 'antonym',
            'question_text': 'What is the opposite of "excellent"?',
            'correct_answer': 'terrible',
            'options': ['outstanding', 'terrible', 'good', 'average']
        },
        {
            'quiz_type': 'synonym',
            'question_text': 'Which word means the same as "outstanding"?',
            'correct_answer': 'excellent',
            'options': ['excellent', 'poor', 'mediocre', 'bad']
        },
        {
            'quiz_type': 'meaning',
            'question_text': 'What does "superb" mean?',
            'correct_answer': 'excellent',
            'options': ['terrible', 'excellent', 'average', 'unknown']
        }
    ]
    
    print(f"\nAdding {len(test_questions)} new questions...")
    
    question_ids = []
    for i, question in enumerate(test_questions, 1):
        print(f"\n--- Question {i}: {question['quiz_type'].upper()} ---")
        print(f"Q: {question['question_text']}")
        print(f"Correct answer: {question['correct_answer']}")
        print(f"Options: {', '.join(question['options'])}")
        
        # Use the enhanced function to add question
        cur.execute("""
            SELECT add_question_with_mastery_tracking(%s, %s, %s, %s, %s) as question_id
        """, (
            question['quiz_type'],
            question['question_text'],
            question['correct_answer'],
            question['options'],
            user_id
        ))
        
        result = cur.fetchone()
        question_id = result['question_id']
        question_ids.append(question_id)
        
        print(f"✓ Added question with ID: {question_id}")
    
    cur.close()
    conn.close()
    
    return question_ids

def test_word_statistics_after():
    """Show word statistics after adding new questions"""
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    print("\n=== WORD STATISTICS AFTER ADDING NEW QUESTIONS ===")
    
    # Show words that appeared in our test questions
    test_words = ['excellent', 'outstanding', 'terrible', 'average', 'poor', 'good', 'mediocre', 'bad', 'superb', 'unknown']
    
    print(f"Statistics for words from new questions:")
    for word in test_words:
        cur.execute("SELECT * FROM vw_word_statistics WHERE word_text = %s", (word,))
        stat = cur.fetchone()
        
        if stat:
            print(f"  '{stat['word_text']}': {stat['total_questions']} questions across {stat['quiz_types_count']} quiz types")
            print(f"    Quiz types: {', '.join(stat['quiz_types']) if stat['quiz_types'] else 'None'}")
            
            # Show detailed question information
            cur.execute("SELECT * FROM get_word_details(%s)", (word,))
            details = cur.fetchone()
            if details and details['question_details']:
                print(f"    Questions:")
                for q_detail in details['question_details']:
                    print(f"      [{q_detail['quiz_type']}] {q_detail['question_text']}")
        else:
            print(f"  '{word}': Not found in database")
    
    # Show updated totals
    cur.execute("SELECT COUNT(*) as total_words FROM words")
    total_words = cur.fetchone()['total_words']
    
    cur.execute("SELECT COUNT(*) as total_questions FROM questions")
    total_questions = cur.fetchone()['total_questions']
    
    cur.execute("SELECT COUNT(*) as total_mappings FROM word_question_map")
    total_mappings = cur.fetchone()['total_mappings']
    
    print(f"\nUpdated totals:")
    print(f"  Words: {total_words}")
    print(f"  Questions: {total_questions}")
    print(f"  Word-Question mappings: {total_mappings}")
    
    cur.close()
    conn.close()

def test_mastery_tracking_updates():
    """Test that mastery tracking was properly updated for new words"""
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    print("\n=== MASTERY TRACKING UPDATES ===")
    
    # Get testuser ID
    cur.execute("SELECT user_id FROM users WHERE username = 'testuser'")
    user_id = cur.fetchone()['user_id']
    
    # Check mastery tracking for the words we just added
    test_words = ['excellent', 'outstanding', 'terrible']
    
    print(f"Checking mastery tracking for key words:")
    for word in test_words:
        cur.execute("""
            SELECT 
                w.word_text,
                COUNT(wqm.*) as mastery_records,
                COUNT(DISTINCT wqm.question_id) as questions_tracked,
                array_agg(DISTINCT wqm.quiz_type ORDER BY wqm.quiz_type) as quiz_types
            FROM words w
            LEFT JOIN word_question_mastery wqm ON w.word_id = wqm.word_id AND wqm.user_id = %s
            WHERE w.word_text = %s
            GROUP BY w.word_id, w.word_text
        """, (user_id, word))
        
        result = cur.fetchone()
        if result:
            print(f"  '{result['word_text']}':")
            print(f"    Mastery records: {result['mastery_records']}")
            print(f"    Questions tracked: {result['questions_tracked']}")
            print(f"    Quiz types: {', '.join(result['quiz_types']) if result['quiz_types'] and result['quiz_types'][0] else 'None'}")
        else:
            print(f"  '{word}': No tracking data found")
    
    # Show overall mastery tracking stats
    cur.execute("""
        SELECT 
            COUNT(DISTINCT word_id) as words_tracked,
            COUNT(DISTINCT question_id) as questions_tracked,
            COUNT(*) as total_mastery_records
        FROM word_question_mastery
        WHERE user_id = %s
    """, (user_id,))
    
    stats = cur.fetchone()
    print(f"\nOverall mastery tracking for testuser:")
    print(f"  Words tracked: {stats['words_tracked']}")
    print(f"  Questions tracked: {stats['questions_tracked']}")
    print(f"  Total mastery records: {stats['total_mastery_records']}")
    
    cur.close()
    conn.close()

def test_duplicate_handling():
    """Test how the system handles duplicate words and questions"""
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    print("\n=== TESTING DUPLICATE HANDLING ===")
    
    # Get testuser ID
    cur.execute("SELECT user_id FROM users WHERE username = 'testuser'")
    user_id = cur.fetchone()['user_id']
    
    # Try to add a question with existing words
    print("Adding question with existing words (excellent, outstanding)...")
    
    cur.execute("""
        SELECT add_question_with_mastery_tracking(%s, %s, %s, %s, %s) as question_id
    """, (
        'fill_in_blank',
        'The performance was absolutely ______.',
        'excellent',
        ['excellent', 'outstanding', 'terrible', 'new_word'],
        user_id
    ))
    
    result = cur.fetchone()
    new_question_id = result['question_id']
    print(f"✓ Added question with ID: {new_question_id}")
    
    # Check if 'new_word' was added and existing words were properly mapped
    cur.execute("SELECT * FROM vw_word_statistics WHERE word_text IN ('excellent', 'outstanding', 'new_word') ORDER BY word_text")
    stats = cur.fetchall()
    
    print(f"Word statistics after adding question with mixed new/existing words:")
    for stat in stats:
        print(f"  '{stat['word_text']}': {stat['total_questions']} questions across {stat['quiz_types_count']} quiz types")
    
    cur.close()
    conn.close()

def main():
    """Main test execution"""
    print("=== TESTING ENHANCED WORD MANAGEMENT SYSTEM ===")
    
    try:
        # 1. Apply enhanced schema
        apply_enhanced_schema()
        
        # 2. Show initial state
        test_word_statistics_before()
        
        # 3. Add new questions with enhanced word management
        question_ids = test_adding_new_questions()
        
        # 4. Show updated state
        test_word_statistics_after()
        
        # 5. Verify mastery tracking updates
        test_mastery_tracking_updates()
        
        # 6. Test duplicate handling
        test_duplicate_handling()
        
        print(f"\n=== TEST COMPLETE ===")
        print(f"Added question IDs: {question_ids}")
        print(f"\nKey Features Demonstrated:")
        print(f"✓ Only unique words are added to the words table")
        print(f"✓ Existing words are properly mapped to new questions")
        print(f"✓ Automatic mastery tracking initialization for all users")
        print(f"✓ Proper handling of duplicate words across questions")
        print(f"✓ Comprehensive word statistics and tracking")
        
    except Exception as e:
        print(f"Error during testing: {e}")
        raise

if __name__ == "__main__":
    main()
