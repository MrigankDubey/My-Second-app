#!/usr/bin/env python3
"""
Enhanced Word Mastery Test - Demonstrates question-level word mastery tracking
This script shows how word mastery is calculated as percentage of questions mastered per word.
"""

import os
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost/vocab_app')

def setup_enhanced_mastery_system():
    """Setup the enhanced mastery tracking system"""
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    cur = conn.cursor()
    
    print("Setting up enhanced mastery tracking system...")
    
    # Read and execute the enhanced schema
    with open('enhanced_schema.sql', 'r') as f:
        enhanced_schema = f.read()
    
    try:
        cur.execute(enhanced_schema)
        print("✅ Enhanced schema applied successfully")
    except Exception as e:
        print(f"❌ Error applying enhanced schema: {e}")
        return False
    
    # Migrate existing data
    try:
        cur.execute("SELECT migrate_to_enhanced_mastery()")
        print("✅ Existing data migrated to enhanced mastery system")
    except Exception as e:
        print(f"❌ Error migrating data: {e}")
    
    cur.close()
    conn.close()
    return True

def create_sample_questions_for_word():
    """Create multiple questions containing the same word to demonstrate percentage tracking"""
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    cur = conn.cursor()
    
    print("\nCreating sample questions for demonstration...")
    
    # Create questions where "happy" appears as the correct answer in multiple contexts
    sample_questions = [
        {
            'question_text': 'What is a synonym for joyful?',
            'quiz_type': 'synonym',
            'correct_answer': 'happy',
            'options': ['happy', 'sad', 'angry', 'confused']
        },
        {
            'question_text': 'Choose the antonym of sad:',
            'quiz_type': 'antonym', 
            'correct_answer': 'happy',
            'options': ['happy', 'depressed', 'melancholy', 'gloomy']
        },
        {
            'question_text': 'She felt _____ after receiving good news.',
            'quiz_type': 'fill_in_blank',
            'correct_answer': 'happy',
            'options': ['happy', 'upset', 'worried', 'nervous']
        },
        {
            'question_text': 'What does "elated" mean?',
            'quiz_type': 'meaning',
            'correct_answer': 'happy',
            'options': ['happy', 'tired', 'confused', 'hungry']
        }
    ]
    
    for question in sample_questions:
        try:
            cur.execute("""
                SELECT insert_question_with_words(%s, %s, %s, %s, %s)
            """, (
                question['question_text'],
                question['quiz_type'],
                question['correct_answer'],
                question['options'],
                1  # created_by admin user
            ))
            print(f"✅ Created {question['quiz_type']} question: {question['question_text'][:50]}...")
        except Exception as e:
            print(f"❌ Error creating question: {e}")
    
    cur.close()
    conn.close()

def simulate_progressive_mastery():
    """Simulate a user progressively mastering questions for a word"""
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    # Get testuser ID
    cur.execute("SELECT user_id FROM users WHERE username = 'testuser'")
    result = cur.fetchone()
    if not result:
        print("❌ Testuser not found. Please run schema setup first.")
        return
    user_id = result['user_id']
    
    # Get questions containing the word "happy"
    cur.execute("""
        SELECT DISTINCT q.question_id, q.question_text, qt.name as quiz_type
        FROM questions q
        JOIN quiz_types qt ON q.quiz_type_id = qt.quiz_type_id
        JOIN word_question_map wqm ON q.question_id = wqm.question_id
        JOIN words w ON wqm.word_id = w.word_id
        WHERE w.word_text = 'happy'
        ORDER BY q.question_id
    """)
    questions = cur.fetchall()
    
    if not questions:
        print("❌ No questions found for word 'happy'. Creating sample questions first...")
        create_sample_questions_for_word()
        return simulate_progressive_mastery()
    
    print(f"\n🎯 Simulating progressive mastery for word 'happy' across {len(questions)} questions:")
    
    # Show initial mastery state
    show_word_mastery_detail(user_id, 'happy')
    
    # Simulate mastering questions progressively
    for i, question in enumerate(questions):
        print(f"\n📝 Question {i+1}: {question['question_text']}")
        
        # Create a quiz attempt
        cur.execute("""
            INSERT INTO quiz_attempts (user_id, quiz_type_id)
            SELECT %s, qt.quiz_type_id 
            FROM quiz_types qt 
            WHERE qt.name = %s
            RETURNING attempt_id
        """, (user_id, question['quiz_type']))
        attempt_id = cur.fetchone()['attempt_id']
        
        # Answer correctly twice to master this question
        for attempt in range(2):
            print(f"   Attempt {attempt + 1}: Answering correctly...")
            
            cur.execute("""
                INSERT INTO responses (attempt_id, question_id, selected_answer, is_correct)
                VALUES (%s, %s, %s, %s)
            """, (attempt_id, question['question_id'], 'happy', True))
            
            # Check mastery after each attempt
            cur.execute("""
                SELECT is_mastered, first_try_correct_count
                FROM word_question_mastery wqm
                JOIN words w ON wqm.word_id = w.word_id
                WHERE wqm.user_id = %s 
                  AND w.word_text = 'happy'
                  AND wqm.question_id = %s
            """, (user_id, question['question_id']))
            
            mastery_result = cur.fetchone()
            if mastery_result:
                mastered = mastery_result['is_mastered']
                correct_count = mastery_result['first_try_correct_count']
                print(f"      Question mastery: {correct_count}/2 correct attempts, Mastered: {mastered}")
                
                if mastered:
                    print(f"      ✅ Question mastered!")
                    break
        
        # Show updated word mastery percentage
        show_word_mastery_detail(user_id, 'happy')
    
    print(f"\n🎊 Mastery simulation complete!")
    show_comprehensive_mastery_report(user_id)
    
    cur.close()
    conn.close()

def show_word_mastery_detail(user_id, word_text):
    """Show detailed mastery information for a specific word"""
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    # Get enhanced word mastery details
    cur.execute("""
        SELECT * FROM vw_word_mastery_detail 
        WHERE user_id = %s AND word_text = %s
    """, (user_id, word_text))
    
    word_detail = cur.fetchone()
    if word_detail:
        print(f"📊 Word '{word_text}' Mastery:")
        print(f"   Total Questions: {word_detail['total_questions']}")
        print(f"   Mastered Questions: {word_detail['mastered_questions']}")
        print(f"   Mastery Percentage: {word_detail['mastery_percentage']}%")
        print(f"   Status: {word_detail['mastery_status']}")
    else:
        print(f"📊 Word '{word_text}': No mastery data yet")
    
    cur.close()
    conn.close()

def show_comprehensive_mastery_report(user_id):
    """Show comprehensive mastery report for user"""
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    print(f"\n📈 COMPREHENSIVE MASTERY REPORT")
    print("=" * 50)
    
    # Overall progress
    cur.execute("""
        SELECT * FROM vw_enhanced_word_progress WHERE user_id = %s
    """, (user_id,))
    
    overall = cur.fetchone()
    if overall:
        print(f"👤 User: {overall['username']}")
        print(f"📚 Total Words Encountered: {overall['total_words_encountered']}")
        print(f"❓ Total Questions Encountered: {overall['total_questions_encountered']}")
        print(f"✅ Total Questions Mastered: {overall['total_questions_mastered']}")
        print(f"📊 Average Word Mastery: {overall['average_word_mastery']}%")
        print(f"🎯 Fully Mastered Words: {overall['fully_mastered_words']}")
        print(f"📈 Partially Mastered Words: {overall['partially_mastered_words']}")
        print(f"🔴 Unmastered Words: {overall['unmastered_words']}")
        print(f"🏆 Fully Mastered Percentage: {overall['fully_mastered_percentage']}%")
    
    # Words needing practice
    cur.execute("""
        SELECT * FROM vw_words_needing_practice 
        WHERE user_id = %s 
        ORDER BY mastery_percentage ASC, questions_remaining DESC
        LIMIT 5
    """, (user_id,))
    
    words_needing_practice = cur.fetchall()
    if words_needing_practice:
        print(f"\n🎯 TOP 5 WORDS NEEDING PRACTICE:")
        for word in words_needing_practice:
            print(f"   '{word['word_text']}': {word['mastery_percentage']}% "
                  f"({word['mastered_questions']}/{word['total_questions']} questions)")
    
    # Question-level mastery for "happy"
    cur.execute("""
        SELECT * FROM vw_question_mastery_detail 
        WHERE user_id = %s AND word_text = 'happy'
        ORDER BY quiz_type
    """, (user_id,))
    
    question_details = cur.fetchall()
    if question_details:
        print(f"\n📝 QUESTION-LEVEL MASTERY FOR 'HAPPY':")
        for detail in question_details:
            print(f"   {detail['quiz_type']}: {detail['status']} "
                  f"({detail['first_try_correct_count']}/2 correct attempts)")
    
    cur.close()
    conn.close()

def test_question_addition_updates():
    """Test that adding new questions automatically updates mastery percentages"""
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    print(f"\n🔧 Testing automatic mastery updates when new questions are added...")
    
    # Get testuser ID
    cur.execute("SELECT user_id FROM users WHERE username = 'testuser'")
    user_id = cur.fetchone()['user_id']
    
    # Check current mastery for "happy"
    cur.execute("""
        SELECT mastery_percentage, total_questions, mastered_questions
        FROM enhanced_word_mastery ewm
        JOIN words w ON ewm.word_id = w.word_id
        WHERE ewm.user_id = %s AND w.word_text = 'happy'
    """, (user_id,))
    
    before = cur.fetchone()
    if before:
        print(f"📊 Before adding new question:")
        print(f"   Mastery: {before['mastery_percentage']}% "
              f"({before['mastered_questions']}/{before['total_questions']} questions)")
    
    # Add a new question containing "happy"
    cur.execute("""
        SELECT insert_question_with_words(%s, %s, %s, %s, %s)
    """, (
        "The child was _____ playing in the park.",
        'fill_in_blank',
        'happy',
        ['happy', 'sad', 'tired', 'bored'],
        1
    ))
    
    print(f"✅ Added new question containing 'happy'")
    
    # Check updated mastery
    cur.execute("""
        SELECT mastery_percentage, total_questions, mastered_questions
        FROM enhanced_word_mastery ewm
        JOIN words w ON ewm.word_id = w.word_id
        WHERE ewm.user_id = %s AND w.word_text = 'happy'
    """, (user_id,))
    
    after = cur.fetchone()
    if after:
        print(f"📊 After adding new question:")
        print(f"   Mastery: {after['mastery_percentage']}% "
              f"({after['mastered_questions']}/{after['total_questions']} questions)")
        
        if before and after['total_questions'] > before['total_questions']:
            print(f"✅ Mastery percentage automatically recalculated!")
            print(f"   Total questions increased from {before['total_questions']} to {after['total_questions']}")
            print(f"   Mastery percentage updated from {before['mastery_percentage']}% to {after['mastery_percentage']}%")
    
    cur.close()
    conn.close()

def main():
    """Main execution function"""
    print("🚀 ENHANCED WORD MASTERY TRACKING SYSTEM")
    print("=" * 60)
    print("This system tracks word mastery as percentage of questions mastered per word.")
    print("A question is mastered when answered correctly twice on first attempt.")
    print("Word mastery = (Mastered Questions / Total Questions) * 100%")
    print("=" * 60)
    
    # Setup enhanced system
    if not setup_enhanced_mastery_system():
        print("❌ Failed to setup enhanced mastery system")
        return
    
    # Create sample questions
    create_sample_questions_for_word()
    
    # Simulate progressive mastery
    simulate_progressive_mastery()
    
    # Test automatic updates when new questions are added
    test_question_addition_updates()
    
    print(f"\n🎉 ENHANCED MASTERY SYSTEM DEMONSTRATION COMPLETE!")
    print(f"Key Features Demonstrated:")
    print(f"✅ Question-level mastery tracking")
    print(f"✅ Word mastery as percentage of questions mastered") 
    print(f"✅ Automatic recalculation when new questions added")
    print(f"✅ Comprehensive mastery analytics and reporting")
    print(f"✅ Progressive mastery demonstration")

if __name__ == "__main__":
    main()
