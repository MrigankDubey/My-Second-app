#!/usr/bin/env python3
"""
Quiz API Models and Endpoints - FastAPI integration for the quiz system
Defines the REST API structure for quiz operations
"""

from __future__ import annotations
from typing import List, Dict, Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum

# === API Models ===

class QuizTypeEnum(str, Enum):
    """Quiz type enumeration for API"""
    SYNONYM = "synonym"
    ANTONYM = "antonym"
    FILL_IN_BLANK = "fill_in_blank"
    WORD_MEANING = "word_meaning"
    ANALOGY = "analogy"
    ODD_ONE_OUT = "odd_one_out"

class QuestionResponse(BaseModel):
    """Individual question response from user"""
    question_id: int
    answer: str = Field(..., description="User's selected answer")
    time_taken_ms: Optional[int] = Field(None, description="Time taken to answer in milliseconds")

class QuizConfigRequest(BaseModel):
    """Configuration for quiz generation"""
    target_question_count: int = Field(20, ge=5, le=50, description="Number of questions in quiz")
    format_distribution: Optional[Dict[str, int]] = Field(None, description="Questions per quiz type")
    exclude_recent_attempts: int = Field(5, ge=0, le=10, description="Exclude questions from last N attempts")

class QuestionData(BaseModel):
    """Question data returned to client (without correct answer)"""
    question_id: int
    question_text: str
    options: List[str]
    quiz_type: str

class QuestionWithAnswer(QuestionData):
    """Question data with correct answer (for results)"""
    correct_answer: str

class QuizSessionResponse(BaseModel):
    """Response when creating a new quiz session"""
    session_id: str
    user_id: int
    current_round: int
    questions: List[QuestionData]
    started_at: datetime
    total_questions: int
    is_first_attempt: bool = True

class QuizAttemptResponse(BaseModel):
    """Response when creating a new quiz (legacy single-attempt format)"""
    attempt_id: int
    user_id: int
    questions: List[QuestionData]
    started_at: datetime
    total_questions: int

class QuizSubmissionRequest(BaseModel):
    """Request payload for submitting quiz responses"""
    responses: List[QuestionResponse] = Field(..., description="List of user responses")

class IndividualResult(BaseModel):
    """Result for a single question"""
    question_id: int
    question_text: str
    user_answer: str
    correct_answer: str
    is_correct: bool
    quiz_type: str

class MasteryUpdate(BaseModel):
    """Word mastery update information"""
    word: str
    previous_count: int
    new_count: int
    mastered: bool

class RoundSummary(BaseModel):
    """Summary of a single quiz round"""
    round: int
    attempt_id: int
    questions_count: int
    correct_answers: int
    score_percentage: float
    is_perfect: bool

class QuizSessionResult(BaseModel):
    """Response after submitting a quiz session round"""
    session_id: str
    current_round: int
    round_result: "QuizRoundResult"
    is_session_completed: bool
    next_questions: Optional[List[QuestionData]] = None
    session_summary: Optional["QuizSessionSummary"] = None

class QuizRoundResult(BaseModel):
    """Result of a single quiz round"""
    attempt_id: int
    round_number: int
    total_questions: int
    correct_answers: int
    score_percentage: float
    is_perfect_score: bool
    individual_results: List[IndividualResult]
    time_taken_seconds: Optional[int] = None

class QuizSessionSummary(BaseModel):
    """Complete summary of a quiz session"""
    session_id: str
    total_rounds: int
    original_question_count: int
    first_attempt_score: float
    words_mastered_first_try: int
    rounds_summary: List[RoundSummary]
    mastery_updates: List[MasteryUpdate]
    is_completed: bool

class QuizResultResponse(BaseModel):
    """Response after submitting a quiz (legacy single-attempt format)"""
    attempt_id: int
    total_questions: int
    correct_answers: int
    score_percentage: float
    time_taken_seconds: Optional[int] = None
    individual_results: List[IndividualResult]
    mastery_updates: List[MasteryUpdate]
    performance_by_type: Dict[str, Dict[str, Any]]

class GlobalProgress(BaseModel):
    """User's global word mastery progress"""
    total_words_encountered: int
    words_mastered: int
    words_pending: int
    mastery_percentage: float

class TypeProgress(BaseModel):
    """Progress for a specific quiz type"""
    quiz_type: str
    total_words: int
    words_mastered: int
    mastery_percentage: float

class RecentQuiz(BaseModel):
    """Recent quiz attempt summary"""
    attempt_id: int
    started_at: datetime
    completed_at: Optional[datetime]
    score_percentage: Optional[float] = None

class UserProgressResponse(BaseModel):
    """Comprehensive user progress data"""
    username: str
    global_progress: Optional[GlobalProgress]
    progress_by_type: List[TypeProgress]
    recent_quizzes: List[RecentQuiz]
    total_attempts: int
    average_score: Optional[float] = None

class QuizAttemptSummary(BaseModel):
    """Summary of a quiz attempt"""
    attempt_id: int
    user_id: int
    username: str
    started_at: datetime
    completed_at: Optional[datetime]
    total_questions: int
    correct_answers: Optional[int] = None
    score_percentage: Optional[float] = None
    questions: List[QuestionWithAnswer]

# === Error Models ===

class ErrorResponse(BaseModel):
    """Standard error response"""
    error: str
    message: str
    details: Optional[Dict[str, Any]] = None

# === API Endpoint Schemas ===

class QuizEndpoints:
    """
    FastAPI endpoint definitions for quiz system
    This class serves as documentation for the API structure
    """
    
    @staticmethod
    def get_quiz_types() -> List[Dict[str, str]]:
        """
        GET /api/quiz/types
        Returns available quiz types
        """
        return [
            {"name": "synonym", "display_name": "Synonyms", "description": "Find words with similar meanings"},
            {"name": "antonym", "display_name": "Antonyms", "description": "Find words with opposite meanings"},
            {"name": "word_meaning", "display_name": "Word Meanings", "description": "Identify word definitions"},
            {"name": "fill_in_blank", "display_name": "Fill in the Blanks", "description": "Complete sentences with appropriate words"},
            {"name": "analogy", "display_name": "Analogies", "description": "Complete word relationships"},
            {"name": "odd_one_out", "display_name": "Odd One Out", "description": "Identify the different word"}
        ]
    
    @staticmethod
    def create_quiz(username: str, config: QuizConfigRequest) -> QuizAttemptResponse:
        """
        POST /api/quiz/create
        Body: QuizConfigRequest
        Headers: Authorization: Bearer {token}
        
        Creates a new quiz attempt for the authenticated user
        Returns: QuizAttemptResponse with questions (no correct answers)
        
        Implementation:
        1. Validate user authentication
        2. Get user ID from token/session
        3. Generate quiz using QuizEngine with config
        4. Return questions without revealing correct answers
        """
        pass
    
    @staticmethod
    def submit_quiz(attempt_id: int, submission: QuizSubmissionRequest) -> QuizResultResponse:
        """
        POST /api/quiz/{attempt_id}/submit
        Body: QuizSubmissionRequest
        Headers: Authorization: Bearer {token}
        
        Submits responses for a quiz attempt
        Returns: QuizResultResponse with detailed results and mastery updates
        
        Implementation:
        1. Validate user owns this quiz attempt
        2. Process each response through QuizEngine
        3. Calculate final score and performance metrics
        4. Return detailed results including mastery updates
        """
        pass
    
    @staticmethod
    def get_quiz_attempt(attempt_id: int) -> QuizAttemptSummary:
        """
        GET /api/quiz/{attempt_id}
        Headers: Authorization: Bearer {token}
        
        Gets details of a quiz attempt (completed or in progress)
        Returns: QuizAttemptSummary
        
        Implementation:
        1. Validate user has access to this attempt
        2. Return quiz details, questions, and results if completed
        """
        pass
    
    @staticmethod
    def get_user_progress(username: str) -> UserProgressResponse:
        """
        GET /api/progress
        Headers: Authorization: Bearer {token}
        
        Gets comprehensive progress data for authenticated user
        Returns: UserProgressResponse
        
        Implementation:
        1. Get user from authentication
        2. Query global and per-type mastery progress
        3. Calculate aggregated statistics
        4. Return comprehensive progress data
        """
        pass
    
    @staticmethod
    def get_leaderboard(quiz_type: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """
        GET /api/quiz/leaderboard?type={quiz_type}&limit={limit}
        
        Gets top performers leaderboard
        Returns: List of user performance data
        
        Implementation:
        1. Query top users by average score or mastery percentage
        2. Filter by quiz type if specified
        3. Return anonymized leaderboard data
        """
        pass
    
    @staticmethod
    def get_word_details(word: str, username: str) -> Dict[str, Any]:
        """
        GET /api/words/{word}/mastery
        Headers: Authorization: Bearer {token}
        
        Gets detailed mastery information for a specific word
        Returns: Word mastery details, history, and related questions
        
        Implementation:
        1. Query word mastery data for user
        2. Get mastery history and performance by quiz type
        3. Return detailed word progress information
        """
        pass
        pass

# === FastAPI Application Structure Example ===

FASTAPI_EXAMPLE = '''
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBearer
from quiz_logic import QuizService, QuizConfig
from quiz_api_models import *

app = FastAPI(title="Vocabulary Learning API", version="1.0.0")
security = HTTPBearer()

@app.post("/api/quiz/create", response_model=QuizAttemptResponse)
async def create_quiz(
    config: QuizConfigRequest,
    token: str = Depends(security)
):
    """Create a new quiz for the authenticated user"""
    username = get_username_from_token(token)  # Implement auth
    
    with QuizService() as quiz_service:
        quiz_config = QuizConfig(
            target_question_count=config.target_question_count,
            format_distribution=config.format_distribution,
            exclude_recent_attempts=config.exclude_recent_attempts
        )
        
        quiz = quiz_service.create_quiz_for_user(username, quiz_config)
        
        # Remove correct answers from response
        questions = [
            QuestionData(
                question_id=q.question_id,
                question_text=q.question_text,
                options=q.options,
                quiz_type=q.quiz_type
            )
            for q in quiz.questions
        ]
        
        return QuizAttemptResponse(
            attempt_id=quiz.attempt_id,
            user_id=quiz.user_id,
            questions=questions,
            started_at=quiz.started_at,
            total_questions=len(questions)
        )

@app.post("/api/quiz/{attempt_id}/submit", response_model=QuizResultResponse)
async def submit_quiz(
    attempt_id: int,
    submission: QuizSubmissionRequest,
    token: str = Depends(security)
):
    """Submit quiz responses and get results"""
    username = get_username_from_token(token)
    
    with QuizService() as quiz_service:
        # Validate user owns this attempt
        attempt = quiz_service.engine.get_quiz_attempt(attempt_id)
        if not attempt or get_user_id_from_token(token) != attempt.user_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Convert responses to expected format
        responses = [
            {
                'question_id': r.question_id,
                'answer': r.answer
            }
            for r in submission.responses
        ]
        
        result = quiz_service.take_quiz(attempt_id, responses)
        
        # Build detailed response
        return QuizResultResponse(
            attempt_id=result.attempt_id,
            total_questions=result.total_questions,
            correct_answers=result.correct_answers,
            score_percentage=result.score_percentage,
            individual_results=[...],  # Build from result.responses
            mastery_updates=[...],     # Build from result.mastery_updates
            performance_by_type={...}  # Calculate by quiz type
        )

@app.get("/api/progress", response_model=UserProgressResponse)
async def get_progress(token: str = Depends(security)):
    """Get user progress data"""
    username = get_username_from_token(token)
    
    with QuizService() as quiz_service:
        progress = quiz_service.get_user_progress(username)
        
        return UserProgressResponse(
            username=progress['username'],
            global_progress=GlobalProgress(**progress['global_progress']) if progress['global_progress'] else None,
            progress_by_type=[TypeProgress(**p) for p in progress['progress_by_type']],
            recent_quizzes=[RecentQuiz(**q) for q in progress['recent_quizzes']],
            total_attempts=len(progress['recent_quizzes']),
            average_score=calculate_average_score(progress['recent_quizzes'])
        )
'''

if __name__ == "__main__":
    print("Quiz API Models and Structure")
    print("============================")
    print("This module defines the API models and endpoint structure for the quiz system.")
    print("Use these models with FastAPI to create a complete REST API.")
    print(f"\\nExample FastAPI implementation:\\n{FASTAPI_EXAMPLE}")

# Update forward references
QuizSessionResult.model_rebuild()
QuizSessionSummary.model_rebuild()
