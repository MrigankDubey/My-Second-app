#!/usr/bin/env python3
"""
Quiz Logic System - Core quiz generation, execution, and scoring logic
Implements the quiz flow described in the design document with smart question selection
"""

import os
import random
import psycopg2
import psycopg2.extras
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost/vocab_app')

class QuizType(Enum):
    SYNONYM = "synonym"
    ANTONYM = "antonym" 
    FILL_IN_BLANK = "fill_in_blank"
    WORD_MEANING = "word_meaning"
    ANALOGY = "analogy"
    ODD_ONE_OUT = "odd_one_out"

@dataclass
class QuestionData:
    question_id: int
    question_text: str
    correct_answer: str
    options: List[str]
    quiz_type: str
    difficulty: Optional[int] = None

@dataclass
class QuizConfig:
    target_question_count: int = 20
    format_distribution: Dict[str, int] = None
    difficulty_distribution: Dict[str, float] = None
    exclude_recent_attempts: int = 5
    
    def __post_init__(self):
        if self.format_distribution is None:
            # Default: balanced distribution across all types
            self.format_distribution = {
                "synonym": 4,
                "antonym": 4,
                "word_meaning": 4,
                "fill_in_blank": 3,
                "analogy": 3,
                "odd_one_out": 2
            }
        
        if self.difficulty_distribution is None:
            # Default: 40% easy, 40% medium, 20% hard
            self.difficulty_distribution = {
                "easy": 0.4,
                "medium": 0.4,
                "hard": 0.2
            }

@dataclass
class QuizAttempt:
    attempt_id: int
    user_id: int
    quiz_type_id: Optional[int]
    questions: List[QuestionData]
    started_at: datetime
    completed_at: Optional[datetime] = None

@dataclass
class QuizResponse:
    question_id: int
    question_text: str
    user_answer: str
    correct_answer: str
    selected_answer: str
    is_correct: bool
    quiz_type: str
    time_taken_ms: Optional[int] = None

@dataclass
class QuizResult:
    attempt_id: int
    total_questions: int
    correct_answers: int
    score_percentage: float
    responses: List[QuizResponse]
    mastery_updates: Dict[str, Any]  # word -> mastery info
    is_perfect_score: bool = False
    incorrect_questions: Optional[List[QuestionData]] = None  # For next round if needed

@dataclass
class QuizSession:
    """Tracks the complete quiz session across multiple rounds"""
    session_id: str
    user_id: int
    original_questions: List[QuestionData]
    current_round: int = 1
    first_attempt_id: Optional[int] = None
    current_attempt_id: Optional[int] = None
    completed_rounds: Optional[List[QuizResult]] = None
    is_completed: bool = False
    
    def __post_init__(self):
        if self.completed_rounds is None:
            self.completed_rounds = []

class QuizEngine:
    def __init__(self, db_url: str = DATABASE_URL):
        self.db_url = db_url
        self.conn: Any = None
    
    def connect(self):
        """Establish database connection"""
        self.conn = psycopg2.connect(self.db_url)
        self.conn.autocommit = True
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
    
    def get_excluded_questions(self, user_id: int, recent_attempts: int = 5) -> set:
        """Get question IDs that should be excluded (seen in last N attempts)"""
        cur = self.conn.cursor()
        
        # Get last N quiz attempts for user
        cur.execute("""
            SELECT attempt_id FROM quiz_attempts 
            WHERE user_id = %s 
            ORDER BY started_at DESC 
            LIMIT %s
        """, (user_id, recent_attempts))
        
        recent_attempt_ids = [row[0] for row in cur.fetchall()]
        
        if not recent_attempt_ids:
            return set()
        
        # Get question IDs from recent attempts
        format_str = ','.join(['%s'] * len(recent_attempt_ids))
        cur.execute(f"""
            SELECT DISTINCT question_id 
            FROM responses 
            WHERE attempt_id IN ({format_str})
        """, recent_attempt_ids)
        
        excluded_questions = {row[0] for row in cur.fetchall()}
        cur.close()
        
        return excluded_questions
    
    def get_globally_mastered_words(self, user_id: int) -> set:
        """Get words that are globally mastered for the user"""
        cur = self.conn.cursor()
        
        cur.execute("""
            SELECT w.word_id
            FROM word_mastery wm
            JOIN words w ON wm.word_id = w.word_id
            WHERE wm.user_id = %s AND wm.mastered = TRUE
        """, (user_id,))
        
        mastered_word_ids = {row[0] for row in cur.fetchall()}
        cur.close()
        
        return mastered_word_ids
    
    def get_questions_by_criteria(self, 
                                quiz_type: str, 
                                count: int, 
                                excluded_questions: set,
                                excluded_words: set) -> List[QuestionData]:
        """Get questions matching criteria, avoiding excluded questions and mastered words"""
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Build exclusion clauses
        excluded_q_clause = ""
        excluded_w_clause = ""
        params = [quiz_type]
        
        if excluded_questions:
            placeholders = ','.join(['%s'] * len(excluded_questions))
            excluded_q_clause = f"AND q.question_id NOT IN ({placeholders})"
            params.extend(excluded_questions)
        
        if excluded_words:
            placeholders = ','.join(['%s'] * len(excluded_words))
            excluded_w_clause = f"""
                AND q.question_id NOT IN (
                    SELECT wqm.question_id 
                    FROM word_question_map wqm 
                    WHERE wqm.word_id IN ({placeholders})
                )
            """
            params.extend(excluded_words)
        
        query = f"""
            SELECT 
                q.question_id,
                q.question_text,
                q.correct_answer,
                qt.name as quiz_type,
                array_agg(o.option_text ORDER BY o.option_id) as options
            FROM questions q
            JOIN quiz_types qt ON q.quiz_type_id = qt.quiz_type_id
            LEFT JOIN options o ON q.question_id = o.question_id
            WHERE qt.name = %s
            {excluded_q_clause}
            {excluded_w_clause}
            GROUP BY q.question_id, q.question_text, q.correct_answer, qt.name
            ORDER BY RANDOM()
            LIMIT %s
        """
        
        params.append(count * 2)  # Get extra questions in case some need to be filtered
        
        cur.execute(query, params)
        results = cur.fetchall()
        
        questions = []
        for row in results:
            if len(questions) >= count:
                break
                
            options = [opt for opt in row['options'] if opt is not None]
            questions.append(QuestionData(
                question_id=row['question_id'],
                question_text=row['question_text'],
                correct_answer=row['correct_answer'],
                options=options,
                quiz_type=row['quiz_type']
            ))
        
        cur.close()
        return questions
    
    def generate_quiz(self, user_id: int, config: Optional[QuizConfig] = None) -> QuizAttempt:
        """Generate a new quiz for the user following smart selection rules"""
        if config is None:
            config = QuizConfig()
        
        # Get exclusions
        excluded_questions = self.get_excluded_questions(user_id, config.exclude_recent_attempts)
        excluded_words = self.get_globally_mastered_words(user_id)
        
        print(f"Excluded {len(excluded_questions)} recent questions and {len(excluded_words)} mastered words")
        
        # Collect questions by type
        all_questions = []
        
        for quiz_type, target_count in config.format_distribution.items():
            questions = self.get_questions_by_criteria(
                quiz_type, target_count, excluded_questions, excluded_words
            )
            all_questions.extend(questions)
            print(f"Found {len(questions)}/{target_count} {quiz_type} questions")
        
        # If we don't have enough questions, backfill with any available
        if len(all_questions) < config.target_question_count:
            needed = config.target_question_count - len(all_questions)
            print(f"Backfilling {needed} questions from any type...")
            
            cur = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            used_question_ids = {q.question_id for q in all_questions}
            excluded_questions.update(used_question_ids)
            
            # Get any remaining questions
            backfill_questions = self.get_questions_by_criteria(
                quiz_type="synonym",  # Default type for backfill
                count=needed,
                excluded_questions=excluded_questions,
                excluded_words=excluded_words
            )
            all_questions.extend(backfill_questions)
        
        # Shuffle final question order
        random.shuffle(all_questions)
        final_questions = all_questions[:config.target_question_count]
        
        # Create quiz attempt record
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO quiz_attempts (user_id, started_at)
            VALUES (%s, %s)
            RETURNING attempt_id
        """, (user_id, datetime.now()))
        
        attempt_id = cur.fetchone()[0]
        
        # Record quiz attempt items
        for question in final_questions:
            cur.execute("""
                INSERT INTO quiz_attempt_items (attempt_id, question_id)
                VALUES (%s, %s)
            """, (attempt_id, question.question_id))
        
        cur.close()
        
        quiz_attempt = QuizAttempt(
            attempt_id=attempt_id,
            user_id=user_id,
            quiz_type_id=None,
            questions=final_questions,
            started_at=datetime.now()
        )
        
        print(f"Generated quiz {attempt_id} with {len(final_questions)} questions")
        return quiz_attempt
    
    def submit_response(self, attempt_id: int, question_id: int, selected_answer: str) -> QuizResponse:
        """Submit a single response and check if it's correct"""
        cur = self.conn.cursor()
        
        # Get correct answer and question details
        cur.execute("""
            SELECT q.correct_answer, q.question_text, qt.name as quiz_type
            FROM questions q
            LEFT JOIN quiz_types qt ON q.quiz_type_id = qt.quiz_type_id
            WHERE q.question_id = %s
        """, (question_id,))
        
        result = cur.fetchone()
        if not result:
            raise ValueError(f"Question {question_id} not found")
        
        correct_answer, question_text, quiz_type = result
        is_correct = selected_answer.strip().lower() == correct_answer.strip().lower()
        
        # Record response (this will trigger mastery update via database trigger)
        cur.execute("""
            INSERT INTO responses (attempt_id, question_id, selected_answer, is_correct)
            VALUES (%s, %s, %s, %s)
        """, (attempt_id, question_id, selected_answer, is_correct))
        
        cur.close()
        
        return QuizResponse(
            question_id=question_id,
            question_text=question_text,
            user_answer=selected_answer,
            correct_answer=correct_answer,
            selected_answer=selected_answer,
            is_correct=is_correct,
            quiz_type=quiz_type or "unknown"
        )
    
    def submit_quiz(self, attempt_id: int, responses: List[Dict[str, Any]]) -> QuizResult:
        """Submit all responses for a quiz and calculate final score"""
        quiz_responses = []
        
        # Submit each response
        for response_data in responses:
            response = self.submit_response(
                attempt_id=attempt_id,
                question_id=response_data['question_id'],
                selected_answer=response_data['answer']
            )
            quiz_responses.append(response)
        
        # Calculate score
        correct_count = sum(1 for r in quiz_responses if r.is_correct)
        total_count = len(quiz_responses)
        score_percentage = (correct_count / total_count * 100) if total_count > 0 else 0
        is_perfect_score = correct_count == total_count
        
        # Get incorrect questions for potential next round
        incorrect_questions = []
        if not is_perfect_score:
            cur = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            # Get full question data for incorrect responses
            incorrect_question_ids = [r.question_id for r in quiz_responses if not r.is_correct]
            
            if incorrect_question_ids:
                format_str = ','.join(['%s'] * len(incorrect_question_ids))
                cur.execute(f"""
                    SELECT 
                        q.question_id,
                        q.question_text,
                        q.correct_answer,
                        qt.name as quiz_type,
                        array_agg(o.option_text ORDER BY o.option_id) as options
                    FROM questions q
                    LEFT JOIN quiz_types qt ON q.quiz_type_id = qt.quiz_type_id
                    LEFT JOIN options o ON q.question_id = o.question_id
                    WHERE q.question_id IN ({format_str})
                    GROUP BY q.question_id, q.question_text, q.correct_answer, qt.name
                """, incorrect_question_ids)
                
                for row in cur.fetchall():
                    options = [opt for opt in row['options'] if opt is not None] if row['options'] else []
                    incorrect_questions.append(QuestionData(
                        question_id=row['question_id'],
                        question_text=row['question_text'],
                        correct_answer=row['correct_answer'],
                        options=options,
                        quiz_type=row['quiz_type'] or "unknown"
                    ))
            
            cur.close()
        
        # Mark quiz as completed
        cur = self.conn.cursor()
        cur.execute("""
            UPDATE quiz_attempts 
            SET completed_at = %s 
            WHERE attempt_id = %s
        """, (datetime.now(), attempt_id))
        
        # Get mastery updates for affected words (only for first attempts)
        cur.execute("""
            SELECT DISTINCT
                w.word_text, 
                wm.first_try_correct_count,
                wm.mastered,
                CASE WHEN r.is_correct THEN 'increased' ELSE 'no_change' END as status
            FROM responses r
            JOIN questions q ON r.question_id = q.question_id
            JOIN word_question_map wqm ON q.question_id = wqm.question_id
            JOIN words w ON wqm.word_id = w.word_id
            LEFT JOIN word_mastery wm ON w.word_id = wm.word_id
            JOIN quiz_attempts qa ON r.attempt_id = qa.attempt_id
            WHERE r.attempt_id = %s 
            AND (wm.user_id = qa.user_id OR wm.user_id IS NULL)
        """, (attempt_id,))
        
        mastery_updates = {}
        for row in cur.fetchall():
            mastery_updates[row[0]] = {
                'word': row[0],
                'previous_count': max(0, row[1] - 1) if row[1] else 0,
                'new_count': row[1] if row[1] else 0,
                'mastered': row[2] if row[2] else False,
                'status': row[3]
            }
        
        cur.close()
        
        return QuizResult(
            attempt_id=attempt_id,
            total_questions=total_count,
            correct_answers=correct_count,
            score_percentage=score_percentage,
            responses=quiz_responses,
            mastery_updates=mastery_updates,
            is_perfect_score=is_perfect_score,
            incorrect_questions=incorrect_questions if incorrect_questions else None
        )
    
    def get_quiz_attempt(self, attempt_id: int) -> Optional[QuizAttempt]:
        """Get quiz attempt details"""
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        cur.execute("""
            SELECT qa.*, u.username
            FROM quiz_attempts qa
            JOIN users u ON qa.user_id = u.user_id
            WHERE qa.attempt_id = %s
        """, (attempt_id,))
        
        attempt_data = cur.fetchone()
        if not attempt_data:
            return None
        
        # Get questions for this attempt
        cur.execute("""
            SELECT 
                q.question_id,
                q.question_text,
                q.correct_answer,
                qt.name as quiz_type,
                array_agg(o.option_text ORDER BY o.option_id) as options
            FROM quiz_attempt_items qai
            JOIN questions q ON qai.question_id = q.question_id
            JOIN quiz_types qt ON q.quiz_type_id = qt.quiz_type_id
            LEFT JOIN options o ON q.question_id = o.question_id
            WHERE qai.attempt_id = %s
            GROUP BY q.question_id, q.question_text, q.correct_answer, qt.name
            ORDER BY qai.attempt_item_id
        """, (attempt_id,))
        
        questions = []
        for row in cur.fetchall():
            options = [opt for opt in row['options'] if opt is not None]
            questions.append(QuestionData(
                question_id=row['question_id'],
                question_text=row['question_text'],
                correct_answer=row['correct_answer'],
                options=options,
                quiz_type=row['quiz_type']
            ))
        
        cur.close()
        
        return QuizAttempt(
            attempt_id=attempt_data['attempt_id'],
            user_id=attempt_data['user_id'],
            quiz_type_id=attempt_data['quiz_type_id'],
            questions=questions,
            started_at=attempt_data['started_at'],
            completed_at=attempt_data['completed_at']
        )
    
    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Get user by username"""
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        cur.execute("""
            SELECT user_id, username, password_hash, email, created_at
            FROM users
            WHERE username = %s
        """, (username,))
        
        user = cur.fetchone()
        cur.close()
        
        return dict(user) if user else None
    
    def create_user(self, username: str, hashed_password: str, email: Optional[str] = None) -> int:
        """Create a new user and return user_id"""
        cur = self.conn.cursor()
        
        cur.execute("""
            INSERT INTO users (username, password_hash, email)
            VALUES (%s, %s, %s)
            RETURNING user_id
        """, (username, hashed_password, email))
        
        user_id = cur.fetchone()[0]
        cur.close()
        
        return user_id
    
    def get_quiz_types(self) -> List[Dict[str, Any]]:
        """Get all available quiz types"""
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        cur.execute("""
            SELECT quiz_type_id, name
            FROM quiz_types
            ORDER BY name
        """)
        
        quiz_types = [dict(row) for row in cur.fetchall()]
        cur.close()
        
        return quiz_types
    
    def get_quiz_attempt_details(self, attempt_id: int) -> Optional[Dict[str, Any]]:
        """Get quiz attempt with detailed information for API responses"""
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Get attempt details
        cur.execute("""
            SELECT qa.*, u.username
            FROM quiz_attempts qa
            JOIN users u ON qa.user_id = u.user_id
            WHERE qa.attempt_id = %s
        """, (attempt_id,))
        
        attempt_data = cur.fetchone()
        if not attempt_data:
            return None
        
        # Get questions and their details
        cur.execute("""
            SELECT 
                q.question_id,
                q.question_text,
                q.correct_answer,
                qt.name as quiz_type,
                array_agg(o.option_text ORDER BY o.option_id) as options
            FROM quiz_attempt_items qai
            JOIN questions q ON qai.question_id = q.question_id
            JOIN quiz_types qt ON q.quiz_type_id = qt.quiz_type_id
            LEFT JOIN options o ON q.question_id = o.question_id
            WHERE qai.attempt_id = %s
            GROUP BY q.question_id, q.question_text, q.correct_answer, qt.name
            ORDER BY qai.attempt_item_id
        """, (attempt_id,))
        
        questions = []
        for row in cur.fetchall():
            options = [opt for opt in row['options'] if opt is not None]
            questions.append({
                'question_id': row['question_id'],
                'question_text': row['question_text'],
                'correct_answer': row['correct_answer'],
                'quiz_type': row['quiz_type'],
                'options': options
            })
        
        # Get score if completed
        if attempt_data['completed_at']:
            cur.execute("""
                SELECT 
                    COUNT(*) as total_questions,
                    COUNT(*) FILTER (WHERE is_correct = TRUE) as correct_answers
                FROM responses
                WHERE attempt_id = %s
            """, (attempt_id,))
            
            score_data = cur.fetchone()
            if score_data and score_data['total_questions'] > 0:
                attempt_data['correct_answers'] = score_data['correct_answers']
                attempt_data['score_percentage'] = (score_data['correct_answers'] / score_data['total_questions']) * 100
        
        cur.close()
        
        result = dict(attempt_data)
        result['questions'] = questions
        return result
    
    def create_quiz_session(self, user_id: int, config: Optional[QuizConfig] = None) -> QuizSession:
        """Create a new quiz session that can handle multiple rounds"""
        import uuid
        
        session_id = str(uuid.uuid4())
        
        # Generate initial quiz with all questions
        quiz_attempt = self.generate_quiz(user_id, config)
        
        return QuizSession(
            session_id=session_id,
            user_id=user_id,
            original_questions=quiz_attempt.questions,
            current_round=1,
            first_attempt_id=quiz_attempt.attempt_id,
            current_attempt_id=quiz_attempt.attempt_id
        )
    
    def create_retry_quiz(self, user_id: int, incorrect_questions: List[QuestionData]) -> QuizAttempt:
        """Create a new quiz attempt with only the incorrect questions"""
        # Create quiz attempt record
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO quiz_attempts (user_id, started_at)
            VALUES (%s, %s)
            RETURNING attempt_id
        """, (user_id, datetime.now()))
        
        attempt_id = cur.fetchone()[0]
        
        # Record quiz attempt items for incorrect questions
        for question in incorrect_questions:
            cur.execute("""
                INSERT INTO quiz_attempt_items (attempt_id, question_id)
                VALUES (%s, %s)
            """, (attempt_id, question.question_id))
        
        cur.close()
        
        return QuizAttempt(
            attempt_id=attempt_id,
            user_id=user_id,
            quiz_type_id=None,
            questions=incorrect_questions,
            started_at=datetime.now()
        )
    
    def submit_quiz_session_round(self, session: QuizSession, responses: List[Dict[str, Any]]) -> Tuple[QuizResult, QuizSession]:
        """Submit a round of the quiz session and return updated session"""
        if session.current_attempt_id is None:
            raise ValueError("No active attempt in session")
        
        # Submit the current round
        result = self.submit_quiz(session.current_attempt_id, responses)
        
        # Update session with completed round
        if session.completed_rounds is None:
            session.completed_rounds = []
        session.completed_rounds.append(result)
        
        if result.is_perfect_score:
            # Session completed successfully
            session.is_completed = True
        else:
            # Need another round with incorrect questions
            if result.incorrect_questions:
                session.current_round += 1
                retry_attempt = self.create_retry_quiz(session.user_id, result.incorrect_questions)
                session.current_attempt_id = retry_attempt.attempt_id
            else:
                # No incorrect questions but not perfect score - shouldn't happen
                session.is_completed = True
        
        return result, session

class QuizService:
    """High-level service for quiz operations"""
    
    def __init__(self, db_url: str = DATABASE_URL):
        self.engine = QuizEngine(db_url)
    
    def __enter__(self):
        self.engine.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.engine.close()
    
    def create_quiz_for_user(self, username: str, config: Optional[QuizConfig] = None) -> QuizAttempt:
        """Create a new quiz for a user by username"""
        cur = self.engine.conn.cursor()
        cur.execute("SELECT user_id FROM users WHERE username = %s", (username,))
        result = cur.fetchone()
        cur.close()
        
        if not result:
            raise ValueError(f"User '{username}' not found")
        
        user_id = result[0]
        return self.engine.generate_quiz(user_id, config)
    
    def take_quiz(self, attempt_id: int, user_responses: List[Dict[str, Any]]) -> QuizResult:
        """Complete a quiz with user responses"""
        return self.engine.submit_quiz(attempt_id, user_responses)
    
    def create_quiz_session_for_user(self, username: str, config: Optional[QuizConfig] = None) -> QuizSession:
        """Create a new repetitive quiz session for a user"""
        cur = self.engine.conn.cursor()
        cur.execute("SELECT user_id FROM users WHERE username = %s", (username,))
        result = cur.fetchone()
        cur.close()
        
        if not result:
            raise ValueError(f"User '{username}' not found")
        
        user_id = result[0]
        return self.engine.create_quiz_session(user_id, config)
    
    def submit_quiz_session_round(self, session: QuizSession, user_responses: List[Dict[str, Any]]) -> Tuple[QuizResult, QuizSession]:
        """Submit a round of responses in a quiz session"""
        return self.engine.submit_quiz_session_round(session, user_responses)
    
    def get_session_summary(self, session: QuizSession) -> Dict[str, Any]:
        """Get a summary of the entire quiz session"""
        if not session.completed_rounds:
            return {
                'session_id': session.session_id,
                'current_round': session.current_round,
                'is_completed': session.is_completed,
                'total_rounds': 0,
                'original_question_count': len(session.original_questions),
                'first_attempt_score': None,
                'rounds_summary': []
            }
        
        # Calculate first round statistics
        first_round = session.completed_rounds[0]
        first_attempt_score = first_round.score_percentage
        
        # Calculate words that were mastered in first attempt
        words_mastered_first_try = sum(1 for update in first_round.mastery_updates.values() 
                                     if update.get('status') == 'increased')
        
        rounds_summary = []
        for i, round_result in enumerate(session.completed_rounds):
            rounds_summary.append({
                'round': i + 1,
                'attempt_id': round_result.attempt_id,
                'questions_count': round_result.total_questions,
                'correct_answers': round_result.correct_answers,
                'score_percentage': round_result.score_percentage,
                'is_perfect': round_result.is_perfect_score
            })
        
        return {
            'session_id': session.session_id,
            'current_round': session.current_round,
            'is_completed': session.is_completed,
            'total_rounds': len(session.completed_rounds),
            'original_question_count': len(session.original_questions),
            'first_attempt_score': first_attempt_score,
            'words_mastered_first_try': words_mastered_first_try,
            'rounds_summary': rounds_summary,
            'mastery_updates': first_round.mastery_updates if session.completed_rounds else {}
        }
    
    def get_user_progress(self, username: str) -> Dict[str, Any]:
        """Get comprehensive progress data for a user"""
        cur = self.engine.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Get user ID
        cur.execute("SELECT user_id FROM users WHERE username = %s", (username,))
        result = cur.fetchone()
        if not result:
            raise ValueError(f"User '{username}' not found")
        
        user_id = result['user_id']
        
        # Get global progress
        cur.execute("SELECT * FROM vw_global_word_progress WHERE user_id = %s", (user_id,))
        global_progress = cur.fetchone()
        
        # Get progress by type
        cur.execute("SELECT * FROM vw_word_progress_by_type WHERE user_id = %s", (user_id,))
        type_progress = cur.fetchall()
        
        # Get recent quiz attempts
        cur.execute("""
            SELECT attempt_id, started_at, completed_at
            FROM quiz_attempts
            WHERE user_id = %s
            ORDER BY started_at DESC
            LIMIT 10
        """, (user_id,))
        recent_quizzes = cur.fetchall()
        
        cur.close()
        
        return {
            'username': username,
            'global_progress': dict(global_progress) if global_progress else None,
            'progress_by_type': [dict(row) for row in type_progress],
            'recent_quizzes': [dict(row) for row in recent_quizzes]
        }

if __name__ == "__main__":
    # Example usage and testing
    print("=== QUIZ LOGIC SYSTEM DEMO ===")
    
    with QuizService() as quiz_service:
        try:
            # Create a quiz for testuser
            print("\n1. Creating quiz for testuser...")
            quiz = quiz_service.create_quiz_for_user("testuser")
            print(f"Created quiz {quiz.attempt_id} with {len(quiz.questions)} questions")
            
            # Show first few questions
            print(f"\nFirst 3 questions:")
            for i, q in enumerate(quiz.questions[:3], 1):
                print(f"{i}. {q.question_text}")
                print(f"   Options: {', '.join(q.options)}")
                print(f"   Correct: {q.correct_answer}")
                print(f"   Type: {q.quiz_type}")
            
            # Simulate taking the quiz
            print(f"\n2. Simulating quiz responses...")
            sample_responses = []
            for q in quiz.questions[:3]:  # Just first 3 for demo
                # Randomly choose correct or incorrect answer
                is_correct_attempt = random.choice([True, True, False])  # 66% correct
                answer = q.correct_answer if is_correct_attempt else "wrong_answer"
                
                sample_responses.append({
                    'question_id': q.question_id,
                    'answer': answer
                })
            
            # Submit quiz
            result = quiz_service.take_quiz(quiz.attempt_id, sample_responses)
            
            print(f"\n3. Quiz Results:")
            print(f"Score: {result.correct_answers}/{result.total_questions} ({result.score_percentage:.1f}%)")
            print(f"Mastery updates: {len(result.mastery_updates)} words affected")
            
            # Show progress
            print(f"\n4. User Progress:")
            progress = quiz_service.get_user_progress("testuser")
            if progress['global_progress']:
                gp = progress['global_progress']
                print(f"Global: {gp['words_mastered']}/{gp['total_words_encountered']} words mastered ({gp['mastery_percentage']}%)")
        
        except Exception as e:
            print(f"Error: {e}")
            print("Make sure the database is running and initialized!")
