#!/usr/bin/env python3
"""
Word Mastery Tracker - Analyzes questions and tracks answer words for mastery system
This program extracts vocabulary words from quiz questions and builds the word mastery tracking list.
"""

import os
import re
import psycopg2
import psycopg2.extras
from collections import Counter
from typing import List, Dict, Set, Tuple, Optional, Any
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost/vocab_app')

class WordMasteryTracker:
    def __init__(self, db_url: str = DATABASE_URL):
        self.db_url = db_url
        self.conn: Any = None
        self.word_stats: Dict[str, Dict[str, Any]] = {}
    
    def connect(self):
        """Establish database connection"""
        self.conn = psycopg2.connect(self.db_url)
        self.conn.autocommit = True
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
    
    def extract_words(self, text: str) -> List[str]:
        """Extract meaningful words from text, filtering out common words"""
        if not text:
            return []
        
        # Convert to lowercase and extract alphabetic words
        words = re.findall(r'\b[a-zA-Z]+\b', text.lower())
        
        # Filter out common stop words and short words
        stop_words = {
            'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from',
            'has', 'he', 'in', 'is', 'it', 'its', 'of', 'on', 'that', 'the',
            'to', 'was', 'will', 'with', 'or', 'but', 'not', 'can', 'have',
            'had', 'what', 'when', 'where', 'who', 'why', 'how', 'this',
            'these', 'those', 'they', 'them', 'their', 'there', 'then',
            'than', 'would', 'could', 'should', 'all', 'any', 'some', 'no',
            'yes', 'do', 'does', 'did', 'i', 'you', 'we', 'my', 'your',
            'his', 'her', 'our', 'up', 'out', 'into', 'down', 'through'
        }
        
        # Filter meaningful words (length >= 3, not stop words)
        meaningful_words = [
            word for word in words 
            if len(word) >= 3 and word not in stop_words
        ]
        
        return meaningful_words
    
    def analyze_questions(self):
        """Analyze all questions and track word occurrences"""
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Get all questions with their quiz types and correct answers
        query = """
        SELECT 
            q.question_id,
            q.question_text,
            q.correct_answer,
            qt.name as quiz_type,
            array_agg(o.option_text) as all_options
        FROM questions q
        JOIN quiz_types qt ON q.quiz_type_id = qt.quiz_type_id
        LEFT JOIN options o ON q.question_id = o.question_id
        GROUP BY q.question_id, q.question_text, q.correct_answer, qt.name
        ORDER BY qt.name, q.question_id
        """
        
        cur.execute(query)
        questions = cur.fetchall()
        
        print(f"Analyzing {len(questions)} questions...")
        
        for question in questions:
            question_id = question['question_id']
            question_text = question['question_text']
            correct_answer = question['correct_answer']
            quiz_type = question['quiz_type']
            all_options = question['all_options'] or []
            
            # Extract words from correct answer (these are the target vocabulary)
            correct_words = self.extract_words(correct_answer)
            
            # Extract words from all options (for context)
            option_words = []
            for option in all_options:
                if option:
                    option_words.extend(self.extract_words(option))
            
            # Extract words from question text (for context words)
            question_words = self.extract_words(question_text)
            
            # Track correct answer words (primary vocabulary targets)
            for word in correct_words:
                if word not in self.word_stats:
                    self.word_stats[word] = {
                        'total_occurrences': 0,
                        'correct_answers': 0,
                        'question_types': set(),
                        'questions': []
                    }
                
                self.word_stats[word]['total_occurrences'] += 1
                self.word_stats[word]['correct_answers'] += 1
                self.word_stats[word]['question_types'].add(quiz_type)
                self.word_stats[word]['questions'].append({
                    'question_id': question_id,
                    'type': quiz_type,
                    'role': 'correct_answer',
                    'text': question_text[:100] + '...' if len(question_text) > 100 else question_text
                })
            
            # Track option words (secondary vocabulary)
            for word in option_words:
                if word not in correct_words:  # Avoid double counting
                    if word not in self.word_stats:
                        self.word_stats[word] = {
                            'total_occurrences': 0,
                            'correct_answers': 0,
                            'question_types': set(),
                            'questions': []
                        }
                    
                    self.word_stats[word]['total_occurrences'] += 1
                    self.word_stats[word]['question_types'].add(quiz_type)
                    self.word_stats[word]['questions'].append({
                        'question_id': question_id,
                        'type': quiz_type,
                        'role': 'option',
                        'text': question_text[:100] + '...' if len(question_text) > 100 else question_text
                    })
        
        cur.close()
        print(f"Analysis complete. Found {len(self.word_stats)} unique words.")
    
    def get_word_priority_list(self) -> List[Tuple[str, Dict[str, Any]]]:
        """Get words sorted by importance for mastery tracking"""
        word_list = []
        
        for word, stats in self.word_stats.items():
            # Calculate priority score
            priority_score = (
                stats['correct_answers'] * 10 +  # Correct answers are most important
                stats['total_occurrences'] * 2 +  # Overall frequency
                len(stats['question_types']) * 5   # Diversity across question types
            )
            
            word_data = {
                'word': word,
                'priority_score': priority_score,
                'total_occurrences': stats['total_occurrences'],
                'correct_answers': stats['correct_answers'],
                'question_types': sorted(list(stats['question_types'])),
                'type_count': len(stats['question_types']),
                'questions': stats['questions']
            }
            
            word_list.append((word, word_data))
        
        # Sort by priority score (descending)
        word_list.sort(key=lambda x: x[1]['priority_score'], reverse=True)
        
        return word_list
    
    def update_word_mastery_tracking(self, user_id: Optional[int] = None):
        """Initialize word mastery tracking for users"""
        cur = self.conn.cursor()
        
        # Get all users if no specific user provided
        if user_id is None:
            cur.execute("SELECT user_id FROM users WHERE role = 'learner'")
            user_ids = [row[0] for row in cur.fetchall()]
        else:
            user_ids = [user_id]
        
        # Get all words that should be tracked
        word_priority_list = self.get_word_priority_list()
        
        # Only track words that appear as correct answers or frequently in options
        words_to_track = [
            word for word, data in word_priority_list 
            if data['correct_answers'] > 0 or data['total_occurrences'] >= 2
        ]
        
        print(f"Initializing mastery tracking for {len(words_to_track)} words across {len(user_ids)} users...")
        
        for user_id in user_ids:
            for word in words_to_track:
                # Get word_id
                cur.execute("SELECT word_id FROM words WHERE word_text = %s", (word,))
                result = cur.fetchone()
                if result:
                    word_id = result[0]
                    
                    # Initialize global mastery tracking
                    cur.execute("""
                        INSERT INTO word_mastery (user_id, word_id, first_try_correct_count, mastered)
                        VALUES (%s, %s, 0, FALSE)
                        ON CONFLICT (user_id, word_id) DO NOTHING
                    """, (user_id, word_id))
                    
                    # Initialize per-type mastery tracking for each question type this word appears in
                    word_data = next(data for w, data in word_priority_list if w == word)
                    for quiz_type in word_data['question_types']:
                        cur.execute("""
                            INSERT INTO word_mastery_by_type (user_id, word_id, quiz_type, first_try_correct_count, mastered)
                            VALUES (%s, %s, %s, 0, FALSE)
                            ON CONFLICT (user_id, word_id, quiz_type) DO NOTHING
                        """, (user_id, word_id, quiz_type))
        
        cur.close()
        print("Mastery tracking initialization complete!")
    
    def generate_report(self):
        """Generate a comprehensive word tracking report"""
        word_priority_list = self.get_word_priority_list()
        
        print("\n" + "="*80)
        print("WORD MASTERY TRACKING REPORT")
        print("="*80)
        
        # Summary statistics
        total_words = len(word_priority_list)
        correct_answer_words = len([w for w, d in word_priority_list if d['correct_answers'] > 0])
        multi_type_words = len([w for w, d in word_priority_list if d['type_count'] > 1])
        
        print(f"\nSUMMARY:")
        print(f"  Total unique words found: {total_words}")
        print(f"  Words appearing as correct answers: {correct_answer_words}")
        print(f"  Words appearing in multiple question types: {multi_type_words}")
        
        # Question type distribution
        all_types = set()
        for _, data in word_priority_list:
            all_types.update(data['question_types'])
        
        print(f"\nQUESTION TYPES FOUND: {', '.join(sorted(all_types))}")
        
        # Top priority words
        print(f"\nTOP 20 PRIORITY WORDS FOR MASTERY TRACKING:")
        print(f"{'Rank':<4} {'Word':<15} {'Priority':<8} {'Correct':<7} {'Total':<5} {'Types':<5} {'Question Types'}")
        print("-" * 80)
        
        for i, (word, data) in enumerate(word_priority_list[:20], 1):
            types_str = ', '.join(data['question_types'])
            if len(types_str) > 18:
                types_str = types_str[:15] + "..."
            
            print(f"{i:<4} {word:<15} {data['priority_score']:<8} {data['correct_answers']:<7} {data['total_occurrences']:<5} {data['type_count']:<5} {types_str}")
        
        # Words by question type
        print(f"\nWORDS BY QUESTION TYPE:")
        type_word_count: Dict[str, int] = {}
        for _, data in word_priority_list:
            for qtype in data['question_types']:
                type_word_count[qtype] = type_word_count.get(qtype, 0) + 1
        
        for qtype in sorted(type_word_count.keys()):
            print(f"  {qtype}: {type_word_count[qtype]} words")
        
        return word_priority_list

def main():
    """Main execution function"""
    tracker = WordMasteryTracker()
    
    try:
        print("Connecting to database...")
        tracker.connect()
        
        print("Analyzing questions and extracting words...")
        tracker.analyze_questions()
        
        print("Generating word priority report...")
        word_list = tracker.generate_report()
        
        # Ask user if they want to initialize mastery tracking
        response = input("\nWould you like to initialize word mastery tracking for all learner users? (y/n): ")
        if response.lower() in ['y', 'yes']:
            tracker.update_word_mastery_tracking()
        
        # Export to CSV for further analysis
        print("\nExporting word list to CSV...")
        import csv
        with open('word_mastery_analysis.csv', 'w', newline='') as csvfile:
            fieldnames = ['word', 'priority_score', 'correct_answers', 'total_occurrences', 'question_types', 'type_count']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for word, data in word_list:
                writer.writerow({
                    'word': word,
                    'priority_score': data['priority_score'],
                    'correct_answers': data['correct_answers'],
                    'total_occurrences': data['total_occurrences'],
                    'question_types': ', '.join(data['question_types']),
                    'type_count': data['type_count']
                })
        
        print("Analysis complete! Results saved to word_mastery_analysis.csv")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        tracker.close()

if __name__ == "__main__":
    main()
