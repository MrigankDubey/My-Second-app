#!/usr/bin/env python3
"""
FastAPI Application for Vocabulary Learning Quiz System
Complete REST API implementation integrating quiz logic and database
"""

import os
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from contextlib import asynccontextmanager
import tempfile
import shutil

from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import jwt
from passlib.context import CryptContext

# Local imports
from quiz_logic import QuizService, QuizConfig, QuizSession
from quiz_api_models import *
from csv_upload_service import CSVUploadService
from csv_upload_validator import CSVUploadValidator

# === Configuration ===

# Environment variables with defaults
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://quiz_user:quiz_password@localhost:5432/vocabulary_quiz")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# In-memory storage for quiz sessions (in production, use Redis or database)
active_quiz_sessions: Dict[str, QuizSession] = {}

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT Security
security = HTTPBearer()

# CSV Upload Service
csv_upload_service = CSVUploadService(database_url=DATABASE_URL)

# === Application Lifecycle ===

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle manager"""
    logger.info("Starting Vocabulary Quiz API...")
    
    # Startup: Test database connection
    try:
        with QuizService(DATABASE_URL) as quiz_service:
            # Test connection
            quiz_service.engine.get_quiz_types()
            logger.info("Database connection successful")
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        raise
    
    yield
    
    logger.info("Shutting down Vocabulary Quiz API...")

# === FastAPI Application ===

app = FastAPI(
    title="Vocabulary Learning Quiz API",
    description="Complete API for CAT vocabulary preparation with adaptive learning",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8080"],  # Add your frontend URLs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === Authentication Utilities ===

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hash a password"""
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=JWT_EXPIRY_HOURS)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Verify JWT token and return payload"""
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return payload
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

# === Authentication Models ===

class UserLogin(BaseModel):
    username: str
    password: str

class UserRegister(BaseModel):
    username: str
    password: str
    email: Optional[str] = None

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int

# === Authentication Endpoints ===

@app.post("/api/auth/register", response_model=TokenResponse)
async def register(user_data: UserRegister):
    """Register a new user"""
    try:
        with QuizService(DATABASE_URL) as quiz_service:
            # Check if user exists
            existing_user = quiz_service.engine.get_user_by_username(user_data.username)
            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Username already registered"
                )
            
            # Hash password and create user
            hashed_password = get_password_hash(user_data.password)
            user_id = quiz_service.engine.create_user(
                username=user_data.username,
                hashed_password=hashed_password,
                email=user_data.email
            )
            
            # Create access token
            access_token = create_access_token(
                data={"sub": user_data.username, "user_id": user_id}
            )
            
            return TokenResponse(
                access_token=access_token,
                token_type="bearer",
                expires_in=JWT_EXPIRY_HOURS * 3600
            )
    except Exception as e:
        logger.error(f"Registration error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )

@app.post("/api/auth/login", response_model=TokenResponse)
async def login(user_data: UserLogin):
    """Authenticate user and return token"""
    try:
        with QuizService(DATABASE_URL) as quiz_service:
            # Get user by username
            user = quiz_service.engine.get_user_by_username(user_data.username)
            if not user or not verify_password(user_data.password, user['password_hash']):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Incorrect username or password",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            # Create access token
            access_token = create_access_token(
                data={"sub": user['username'], "user_id": user['user_id']}
            )
            
            return TokenResponse(
                access_token=access_token,
                token_type="bearer",
                expires_in=JWT_EXPIRY_HOURS * 3600
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )

# === Quiz Endpoints ===

@app.get("/api/quiz/types")
async def get_quiz_types():
    """Get available quiz types"""
    return [
        {"name": "synonym", "display_name": "Synonyms", "description": "Find words with similar meanings"},
        {"name": "antonym", "display_name": "Antonyms", "description": "Find words with opposite meanings"},
        {"name": "word_meaning", "display_name": "Word Meanings", "description": "Identify word definitions"},
        {"name": "fill_in_blank", "display_name": "Fill in the Blanks", "description": "Complete sentences with appropriate words"},
        {"name": "analogy", "display_name": "Analogies", "description": "Complete word relationships"},
        {"name": "odd_one_out", "display_name": "Odd One Out", "description": "Identify the different word"}
    ]

@app.post("/api/quiz/session/create", response_model=QuizSessionResponse)
async def create_quiz_session(
    config: QuizConfigRequest,
    token_data: dict = Depends(verify_token)
):
    """Create a new repetitive quiz session for the authenticated user"""
    try:
        with QuizService(DATABASE_URL) as quiz_service:
            quiz_config = QuizConfig(
                target_question_count=config.target_question_count,
                format_distribution=config.format_distribution or {},
                exclude_recent_attempts=config.exclude_recent_attempts
            )
            
            session = quiz_service.create_quiz_session_for_user(token_data["sub"], quiz_config)
            
            # Store session in memory (use Redis in production)
            active_quiz_sessions[session.session_id] = session
            
            # Remove correct answers from response
            questions = [
                QuestionData(
                    question_id=q.question_id,
                    question_text=q.question_text,
                    options=q.options,
                    quiz_type=q.quiz_type
                )
                for q in session.original_questions
            ]
            
            return QuizSessionResponse(
                session_id=session.session_id,
                user_id=session.user_id,
                current_round=session.current_round,
                questions=questions,
                started_at=datetime.utcnow(),
                total_questions=len(questions),
                is_first_attempt=True
            )
    except Exception as e:
        logger.error(f"Quiz session creation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Quiz session creation failed"
        )

@app.post("/api/quiz/session/{session_id}/submit", response_model=QuizSessionResult)
async def submit_quiz_session_round(
    session_id: str,
    submission: QuizSubmissionRequest,
    token_data: dict = Depends(verify_token)
):
    """Submit responses for a quiz session round"""
    try:
        # Get session from memory
        session = active_quiz_sessions.get(session_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Quiz session not found"
            )
        
        # Validate user owns this session
        if token_data["user_id"] != session.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        with QuizService(DATABASE_URL) as quiz_service:
            # Convert responses to expected format
            responses = [
                {
                    'question_id': r.question_id,
                    'answer': r.answer
                }
                for r in submission.responses
            ]
            
            round_result, updated_session = quiz_service.submit_quiz_session_round(session, responses)
            
            # Update stored session
            active_quiz_sessions[session_id] = updated_session
            
            # Build round result
            individual_results = []
            for resp in round_result.responses:
                individual_results.append(IndividualResult(
                    question_id=resp.question_id,
                    question_text=resp.question_text,
                    user_answer=resp.user_answer,
                    correct_answer=resp.correct_answer,
                    is_correct=resp.is_correct,
                    quiz_type=resp.quiz_type
                ))
            
            round_result_response = QuizRoundResult(
                attempt_id=round_result.attempt_id,
                round_number=updated_session.current_round - 1,  # Previous round
                total_questions=round_result.total_questions,
                correct_answers=round_result.correct_answers,
                score_percentage=round_result.score_percentage,
                is_perfect_score=round_result.is_perfect_score,
                individual_results=individual_results
            )
            
            # Prepare next questions if not completed
            next_questions = None
            if not updated_session.is_completed and round_result.incorrect_questions:
                next_questions = [
                    QuestionData(
                        question_id=q.question_id,
                        question_text=q.question_text,
                        options=q.options,
                        quiz_type=q.quiz_type
                    )
                    for q in round_result.incorrect_questions
                ]
            
            # Prepare session summary if completed
            session_summary = None
            if updated_session.is_completed:
                summary = quiz_service.get_session_summary(updated_session)
                
                # Build mastery updates for completed session
                mastery_updates = []
                if summary.get('mastery_updates'):
                    for word, update_info in summary['mastery_updates'].items():
                        mastery_updates.append(MasteryUpdate(
                            word=word,
                            previous_count=update_info.get('previous_count', 0),
                            new_count=update_info.get('new_count', 0),
                            mastered=update_info.get('mastered', False)
                        ))
                
                rounds_summary = [
                    RoundSummary(**round_data) for round_data in summary.get('rounds_summary', [])
                ]
                
                session_summary = QuizSessionSummary(
                    session_id=summary['session_id'],
                    total_rounds=summary['total_rounds'],
                    original_question_count=summary['original_question_count'],
                    first_attempt_score=summary.get('first_attempt_score', 0.0),
                    words_mastered_first_try=summary.get('words_mastered_first_try', 0),
                    rounds_summary=rounds_summary,
                    mastery_updates=mastery_updates,
                    is_completed=summary['is_completed']
                )
                
                # Clean up completed session
                if updated_session.is_completed:
                    del active_quiz_sessions[session_id]
            
            return QuizSessionResult(
                session_id=session_id,
                current_round=updated_session.current_round,
                round_result=round_result_response,
                is_session_completed=updated_session.is_completed,
                next_questions=next_questions,
                session_summary=session_summary
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Quiz session submission error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Quiz session submission failed"
        )

@app.get("/api/quiz/session/{session_id}")
async def get_quiz_session_status(
    session_id: str,
    token_data: dict = Depends(verify_token)
):
    """Get current status of a quiz session"""
    session = active_quiz_sessions.get(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quiz session not found"
        )
    
    if token_data["user_id"] != session.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    return {
        "session_id": session.session_id,
        "current_round": session.current_round,
        "is_completed": session.is_completed,
        "total_rounds_completed": len(session.completed_rounds or []),
        "original_question_count": len(session.original_questions)
    }

@app.post("/api/quiz/create", response_model=QuizAttemptResponse)
async def create_quiz(
    config: QuizConfigRequest,
    token_data: dict = Depends(verify_token)
):
    """Create a new quiz for the authenticated user"""
    try:
        with QuizService(DATABASE_URL) as quiz_service:
            quiz_config = QuizConfig(
                target_question_count=config.target_question_count,
                format_distribution=config.format_distribution,
                exclude_recent_attempts=config.exclude_recent_attempts
            )
            
            quiz = quiz_service.create_quiz_for_user(token_data["sub"], quiz_config)
            
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
    except Exception as e:
        logger.error(f"Quiz creation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Quiz creation failed"
        )

@app.post("/api/quiz/{attempt_id}/submit", response_model=QuizResultResponse)
async def submit_quiz(
    attempt_id: int,
    submission: QuizSubmissionRequest,
    token_data: dict = Depends(verify_token)
):
    """Submit quiz responses and get results"""
    try:
        with QuizService(DATABASE_URL) as quiz_service:
            # Validate user owns this attempt
            attempt = quiz_service.engine.get_quiz_attempt(attempt_id)
            if not attempt or token_data["user_id"] != attempt.user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied"
                )
            
            # Convert responses to expected format
            responses = [
                {
                    'question_id': r.question_id,
                    'answer': r.answer
                }
                for r in submission.responses
            ]
            
            result = quiz_service.take_quiz(attempt_id, responses)
            
            # Build individual results
            individual_results = []
            for resp in result.responses:
                individual_results.append(IndividualResult(
                    question_id=resp.question_id,
                    question_text=resp.question_text,
                    user_answer=resp.user_answer,
                    correct_answer=resp.correct_answer,
                    is_correct=resp.is_correct,
                    quiz_type=resp.quiz_type
                ))
            
            # Build mastery updates
            mastery_updates = []
            for update in result.mastery_updates:
                mastery_updates.append(MasteryUpdate(
                    word=update['word'],
                    previous_count=update['previous_count'],
                    new_count=update['new_count'],
                    mastered=update['mastered']
                ))
            
            # Calculate performance by type
            performance_by_type = {}
            for quiz_type in set(resp.quiz_type for resp in result.responses):
                type_responses = [r for r in result.responses if r.quiz_type == quiz_type]
                correct_count = sum(1 for r in type_responses if r.is_correct)
                performance_by_type[quiz_type] = {
                    "total": len(type_responses),
                    "correct": correct_count,
                    "percentage": (correct_count / len(type_responses)) * 100 if type_responses else 0
                }
            
            return QuizResultResponse(
                attempt_id=result.attempt_id,
                total_questions=result.total_questions,
                correct_answers=result.correct_answers,
                score_percentage=result.score_percentage,
                individual_results=individual_results,
                mastery_updates=mastery_updates,
                performance_by_type=performance_by_type
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Quiz submission error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Quiz submission failed"
        )

@app.get("/api/quiz/{attempt_id}", response_model=QuizAttemptSummary)
async def get_quiz_attempt(
    attempt_id: int,
    token_data: dict = Depends(verify_token)
):
    """Get details of a quiz attempt"""
    try:
        with QuizService(DATABASE_URL) as quiz_service:
            attempt = quiz_service.engine.get_quiz_attempt_details(attempt_id)
            if not attempt or token_data["user_id"] != attempt['user_id']:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied"
                )
            
            questions = [
                QuestionWithAnswer(
                    question_id=q['question_id'],
                    question_text=q['question_text'],
                    options=q['options'],
                    quiz_type=q['quiz_type'],
                    correct_answer=q['correct_answer']
                )
                for q in attempt['questions']
            ]
            
            return QuizAttemptSummary(
                attempt_id=attempt['attempt_id'],
                user_id=attempt['user_id'],
                username=attempt['username'],
                started_at=attempt['started_at'],
                completed_at=attempt.get('completed_at'),
                total_questions=len(questions),
                correct_answers=attempt.get('correct_answers'),
                score_percentage=attempt.get('score_percentage'),
                questions=questions
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Quiz attempt retrieval error: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quiz attempt not found"
        )

@app.get("/api/progress", response_model=UserProgressResponse)
async def get_progress(token_data: dict = Depends(verify_token)):
    """Get user progress data"""
    try:
        with QuizService(DATABASE_URL) as quiz_service:
            progress = quiz_service.get_user_progress(token_data["sub"])
            
            # Build global progress
            global_progress = None
            if progress.get('global_progress'):
                global_progress = GlobalProgress(**progress['global_progress'])
            
            # Build progress by type
            progress_by_type = [
                TypeProgress(**p) for p in progress.get('progress_by_type', [])
            ]
            
            # Build recent quizzes
            recent_quizzes = [
                RecentQuiz(**q) for q in progress.get('recent_quizzes', [])
            ]
            
            # Calculate average score
            completed_quizzes = [q for q in recent_quizzes if q.score_percentage is not None]
            average_score = None
            if completed_quizzes:
                average_score = sum(q.score_percentage for q in completed_quizzes) / len(completed_quizzes)
            
            return UserProgressResponse(
                username=progress['username'],
                global_progress=global_progress,
                progress_by_type=progress_by_type,
                recent_quizzes=recent_quizzes,
                total_attempts=len(recent_quizzes),
                average_score=average_score
            )
    except Exception as e:
        logger.error(f"Progress retrieval error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Progress retrieval failed"
        )

# === CSV Upload Endpoints ===

class CSVUploadResponse(BaseModel):
    upload_id: str
    is_valid: bool
    can_import: bool
    validation_summary: Dict[str, Any]
    validation_report: str
    uploaded_file_path: str

class CSVImportResponse(BaseModel):
    success: bool
    upload_id: str
    import_results: Dict[str, Any]
    validation_summary: Dict[str, Any]
    error: Optional[str] = None

@app.post("/api/admin/csv/upload", response_model=CSVUploadResponse)
async def upload_csv_file(
    file: UploadFile = File(...),
    token_data: dict = Depends(verify_token)
):
    """Upload and validate CSV file for admin users"""
    try:
        # Check if user has admin privileges (you may want to add role checking)
        user_id = token_data["user_id"]
        
        # Validate file type
        if not file.filename.lower().endswith('.csv'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only CSV files are allowed"
            )
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as temp_file:
            # Copy uploaded file to temporary location
            shutil.copyfileobj(file.file, temp_file)
            temp_file_path = temp_file.name
        
        try:
            # Upload and validate using CSV service
            upload_result = csv_upload_service.upload_and_validate_csv(
                temp_file_path, user_id, file.filename
            )
            
            if upload_result.get('error'):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=upload_result['error']
                )
            
            return CSVUploadResponse(
                upload_id=upload_result['upload_id'],
                is_valid=upload_result['is_valid'],
                can_import=upload_result['can_import'],
                validation_summary=upload_result['validation_summary'],
                validation_report=upload_result['validation_report'],
                uploaded_file_path=upload_result['uploaded_file_path']
            )
        
        finally:
            # Clean up temporary file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"CSV upload error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="CSV upload failed"
        )

@app.post("/api/admin/csv/import", response_model=CSVImportResponse)
async def import_csv_file(
    upload_id: str = Form(...),
    force_import: bool = Form(False),
    token_data: dict = Depends(verify_token)
):
    """Import a previously validated CSV file"""
    try:
        user_id = token_data["user_id"]
        
        # Import the CSV using the upload service
        import_result = csv_upload_service.import_validated_csv(
            upload_id, user_id, force_import
        )
        
        if not import_result['success']:
            if import_result.get('requires_force'):
                return CSVImportResponse(
                    success=False,
                    upload_id=upload_id,
                    import_results={},
                    validation_summary={},
                    error=import_result['error']
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=import_result['error']
                )
        
        return CSVImportResponse(
            success=True,
            upload_id=upload_id,
            import_results=import_result['import_results'],
            validation_summary=import_result['validation_summary']
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"CSV import error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="CSV import failed"
        )

@app.get("/api/admin/csv/uploads")
async def get_upload_history(
    limit: int = 50,
    token_data: dict = Depends(verify_token)
):
    """Get upload history for the current user"""
    try:
        user_id = token_data["user_id"]
        upload_history = csv_upload_service.get_upload_history(user_id, limit)
        return {"uploads": upload_history}
    
    except Exception as e:
        logger.error(f"Upload history retrieval error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve upload history"
        )

# === Health Check ===

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    try:
        with QuizService(DATABASE_URL) as quiz_service:
            # Simple database check
            quiz_service.engine.get_quiz_types()
            return {"status": "healthy", "timestamp": datetime.utcnow()}
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unhealthy", "error": str(e)}
        )

# === Exception Handlers ===

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Custom HTTP exception handler"""
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error=exc.detail,
            message=f"HTTP {exc.status_code}: {exc.detail}"
        ).dict()
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """General exception handler"""
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            error="Internal Server Error",
            message="An unexpected error occurred"
        ).dict()
    )

# === Development Server ===

if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
