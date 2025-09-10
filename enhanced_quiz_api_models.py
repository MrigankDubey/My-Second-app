#!/usr/bin/env python3
"""
Enhanced Quiz API Models - Pydantic models supporting question-level word mastery tracking
"""

from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime

# Enhanced Word Mastery Models
class QuestionMasteryDetail(BaseModel):
    question_id: int
    question_text: str
    quiz_type: str
    first_try_correct_count: int
    total_attempts: int
    is_mastered: bool
    last_attempted: Optional[datetime]
    status: str  # "Mastered", "Progress", "Not Attempted"

class WordMasteryDetail(BaseModel):
    word_text: str
    total_questions: int
    mastered_questions: int
    mastery_percentage: float
    mastery_status: str  # "Fully Mastered", "Well Practiced", "Learning", "Not Started"
    last_updated: Optional[datetime]
    question_details: List[QuestionMasteryDetail] = []

class EnhancedProgressResponse(BaseModel):
    user_id: int
    username: str
    
    # Overall statistics
    total_words_encountered: int
    total_questions_encountered: int
    total_questions_mastered: int
    average_word_mastery: float
    
    # Word mastery breakdown
    fully_mastered_words: int
    partially_mastered_words: int
    unmastered_words: int
    fully_mastered_percentage: float
    
    # Detailed word mastery
    word_mastery_details: List[WordMasteryDetail] = []
    words_needing_practice: List[WordMasteryDetail] = []

class QuizSessionCreationRequest(BaseModel):
    quiz_type: Optional[str] = None
    question_count: int = Field(default=20, ge=1, le=50)
    difficulty_preference: Optional[str] = None  # "easy", "medium", "hard"

class QuizSessionResponse(BaseModel):
    session_id: str
    questions: List['QuestionResponse']
    total_questions: int
    is_first_attempt: bool
    session_type: str = "repetitive"  # "repetitive" or "single"

class QuizRoundSubmission(BaseModel):
    responses: List['ResponseSubmission']

class QuizRoundResult(BaseModel):
    session_id: str
    round_number: int
    total_questions: int
    correct_answers: int
    incorrect_questions: List['QuestionResponse'] = []
    is_session_complete: bool
    next_questions: List['QuestionResponse'] = []
    mastery_updates: List[WordMasteryDetail] = []

class QuizSessionSummary(BaseModel):
    session_id: str
    total_rounds: int
    total_questions_attempted: int
    unique_questions_mastered: int
    session_completion_time: Optional[datetime]
    final_mastery_updates: List[WordMasteryDetail] = []

# Legacy models for backward compatibility
class QuestionResponse(BaseModel):
    question_id: int
    question_text: str
    options: List[str]
    quiz_type: str

class ResponseSubmission(BaseModel):
    question_id: int
    selected_answer: str

class QuizCreationRequest(BaseModel):
    quiz_type: Optional[str] = None
    exclude_mastered: bool = True
    difficulty_level: Optional[str] = None

class QuizCreationResponse(BaseModel):
    attempt_id: int
    questions: List[QuestionResponse]
    total_questions: int

class QuizSubmissionRequest(BaseModel):
    responses: List[ResponseSubmission]

class QuizResult(BaseModel):
    attempt_id: int
    score: int
    total_questions: int
    percentage: float
    correct_answers: List[int]
    incorrect_answers: List[int]
    mastery_updates: Dict[str, Any]

class ProgressResponse(BaseModel):
    global_stats: Dict[str, Any]
    by_quiz_type: List[Dict[str, Any]]
    recent_activity: List[Dict[str, Any]]
    words_to_review: List[Dict[str, Any]]

# Update forward references
QuizSessionResponse.model_rebuild()
QuizRoundResult.model_rebuild()
