#!/usr/bin/env python3
"""
Enhanced FastAPI Application with Question-Level Word Mastery Tracking
Supports both legacy and enhanced mastery tracking systems
"""

import os
import uuid
import psycopg2
import psycopg2.extras
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import asdict

import jwt
import bcrypt
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from dotenv import load_dotenv

# Import enhanced models
from enhanced_quiz_api_models import (
    QuizSessionCreationRequest, QuizSessionResponse, QuizRoundSubmission, 
    QuizRoundResult, QuizSessionSummary, EnhancedProgressResponse,
    WordMasteryDetail, QuestionMasteryDetail,
    # Legacy models
    QuizCreationRequest, QuizCreationResponse, QuizSubmissionRequest, 
    QuizResult, ProgressResponse, QuestionResponse, ResponseSubmission
)

# Import existing logic
from quiz_logic import (
    QuizConfig, QuestionData, QuizResponse, QuizSession,
    generate_quiz, submit_quiz_responses, get_user_progress,
    create_quiz_session, submit_quiz_session_round
)

load_dotenv()

# Configuration
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost/vocab_app')
SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key-change-this')
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

app = FastAPI(
    title="Enhanced Vocabulary Learning API",
    description="Vocabulary learning system with question-level word mastery tracking",
    version="2.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer()

# In-memory session storage (use Redis in production)
active_sessions: Dict[str, Any] = {}

def get_db_connection():
    """Get database connection"""
    return psycopg2.connect(DATABASE_URL)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify JWT token and return user info"""
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = payload.get("user_id")
        username: str = payload.get("username")
        if user_id is None or username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return {"user_id": user_id, "username": username}
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

# Health check endpoint
@app.get("/api/health", tags=["System"])
async def health_check():
    """Check API and database health"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.close()
        conn.close()
        return {
            "status": "healthy",
            "database": "connected",
            "timestamp": datetime.utcnow().isoformat(),
            "version": "2.0.0",
            "features": ["question_level_mastery", "enhanced_tracking", "legacy_compatibility"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database connection failed: {e}")

# Authentication endpoints
@app.post("/api/auth/register", tags=["Authentication"])
async def register_user(username: str, password: str):
    """Register a new user"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Check if username exists
        cur.execute("SELECT user_id FROM users WHERE username = %s", (username,))
        if cur.fetchone():
            raise HTTPException(status_code=400, detail="Username already exists")
        
        # Hash password and create user
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        cur.execute(
            "INSERT INTO users (username, password_hash) VALUES (%s, %s) RETURNING user_id",
            (username, password_hash)
        )
        user_id = cur.fetchone()[0]
        
        conn.commit()
        cur.close()
        conn.close()
        
        # Create access token
        access_token = create_access_token(data={"user_id": user_id, "username": username})
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": ACCESS_TOKEN_EXPIRE_HOURS * 3600,
            "user_id": user_id,
            "username": username
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Registration failed: {e}")

@app.post("/api/auth/login", tags=["Authentication"])
async def login_user(username: str, password: str):
    """Login user and return access token"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get user and verify password
        cur.execute("SELECT user_id, password_hash FROM users WHERE username = %s", (username,))
        user = cur.fetchone()
        
        if not user or not bcrypt.checkpw(password.encode('utf-8'), user[1].encode('utf-8')):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        user_id = user[0]
        cur.close()
        conn.close()
        
        # Create access token
        access_token = create_access_token(data={"user_id": user_id, "username": username})
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": ACCESS_TOKEN_EXPIRE_HOURS * 3600,
            "user_id": user_id,
            "username": username
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Login failed: {e}")

# Enhanced quiz endpoints with question-level mastery tracking
@app.get("/api/quiz/types", tags=["Enhanced Quiz"])
async def get_quiz_types():
    """Get available quiz types with descriptions"""
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        cur.execute("""
            SELECT qt.name, COUNT(q.question_id) as question_count
            FROM quiz_types qt
            LEFT JOIN questions q ON qt.quiz_type_id = q.quiz_type_id
            GROUP BY qt.name
            ORDER BY qt.name
        """)
        
        quiz_types = cur.fetchall()
        cur.close()
        conn.close()
        
        descriptions = {
            "synonym": "Find words with similar meanings",
            "antonym": "Find words with opposite meanings", 
            "fill_in_blank": "Fill in the missing word",
            "word_meaning": "Choose the correct definition",
            "analogy": "Complete the analogy",
            "odd_one_out": "Find the word that doesn't belong"
        }
        
        return {
            "quiz_types": [
                {
                    "name": qt['name'],
                    "description": descriptions.get(qt['name'], "Vocabulary quiz"),
                    "question_count": qt['question_count']
                }
                for qt in quiz_types
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get quiz types: {e}")

@app.post("/api/quiz/session/create", response_model=QuizSessionResponse, tags=["Enhanced Quiz"])
async def create_quiz_session_endpoint(
    request: QuizSessionCreationRequest,
    current_user: dict = Depends(verify_token)
):
    """Create a new repetitive quiz session with enhanced mastery tracking"""
    try:
        session_id = str(uuid.uuid4())
        user_id = current_user["user_id"]
        
        # Create quiz session using existing logic
        session = create_quiz_session(
            user_id=user_id,
            quiz_type=request.quiz_type,
            question_count=request.question_count
        )
        
        # Store session in memory
        active_sessions[session_id] = {
            "session": session,
            "user_id": user_id,
            "created_at": datetime.utcnow(),
            "rounds": []
        }
        
        # Convert to API response format
        questions = [
            QuestionResponse(
                question_id=q.question_id,
                question_text=q.question_text,
                options=q.options,
                quiz_type=q.quiz_type
            )
            for q in session.questions
        ]
        
        return QuizSessionResponse(
            session_id=session_id,
            questions=questions,
            total_questions=len(questions),
            is_first_attempt=True
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create quiz session: {e}")

@app.post("/api/quiz/session/{session_id}/submit", response_model=QuizRoundResult, tags=["Enhanced Quiz"])
async def submit_quiz_session_round_endpoint(
    session_id: str,
    submission: QuizRoundSubmission,
    current_user: dict = Depends(verify_token)
):
    """Submit responses for a quiz session round with enhanced mastery tracking"""
    try:
        if session_id not in active_sessions:
            raise HTTPException(status_code=404, detail="Quiz session not found")
        
        session_data = active_sessions[session_id]
        user_id = current_user["user_id"]
        
        if session_data["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Access denied to this quiz session")
        
        # Convert API submission to internal format
        responses = [
            {"question_id": r.question_id, "selected_answer": r.selected_answer}
            for r in submission.responses
        ]
        
        # Submit round using existing logic
        round_result = submit_quiz_session_round(
            session=session_data["session"],
            responses=responses,
            user_id=user_id
        )
        
        # Store round data
        session_data["rounds"].append({
            "round_number": len(session_data["rounds"]) + 1,
            "responses": responses,
            "timestamp": datetime.utcnow()
        })
        
        # Get enhanced mastery updates
        mastery_updates = await get_enhanced_mastery_updates(user_id, [r.question_id for r in submission.responses])
        
        # Convert result to API format
        incorrect_questions = []
        next_questions = []
        
        if hasattr(round_result, 'incorrect_questions'):
            incorrect_questions = [
                QuestionResponse(
                    question_id=q.question_id,
                    question_text=q.question_text,
                    options=q.options,
                    quiz_type=q.quiz_type
                )
                for q in round_result.incorrect_questions
            ]
        
        if hasattr(round_result, 'next_questions'):
            next_questions = [
                QuestionResponse(
                    question_id=q.question_id,
                    question_text=q.question_text,
                    options=q.options,
                    quiz_type=q.quiz_type
                )
                for q in round_result.next_questions
            ]
        
        is_complete = not next_questions and not incorrect_questions
        
        # Clean up session if complete
        if is_complete:
            session_data["completed_at"] = datetime.utcnow()
        
        return QuizRoundResult(
            session_id=session_id,
            round_number=len(session_data["rounds"]),
            total_questions=len(submission.responses),
            correct_answers=getattr(round_result, 'correct_count', 0),
            incorrect_questions=incorrect_questions,
            is_session_complete=is_complete,
            next_questions=next_questions,
            mastery_updates=mastery_updates
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to submit quiz round: {e}")

@app.get("/api/quiz/session/{session_id}", response_model=QuizSessionSummary, tags=["Enhanced Quiz"])
async def get_quiz_session_status(
    session_id: str,
    current_user: dict = Depends(verify_token)
):
    """Get quiz session status and summary"""
    try:
        if session_id not in active_sessions:
            raise HTTPException(status_code=404, detail="Quiz session not found")
        
        session_data = active_sessions[session_id]
        user_id = current_user["user_id"]
        
        if session_data["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Access denied to this quiz session")
        
        # Get final mastery updates
        all_question_ids = []
        for round_data in session_data["rounds"]:
            all_question_ids.extend([r["question_id"] for r in round_data["responses"]])
        
        final_mastery_updates = await get_enhanced_mastery_updates(user_id, all_question_ids)
        
        return QuizSessionSummary(
            session_id=session_id,
            total_rounds=len(session_data["rounds"]),
            total_questions_attempted=len(all_question_ids),
            unique_questions_mastered=len([u for u in final_mastery_updates if u.mastery_percentage == 100.0]),
            session_completion_time=session_data.get("completed_at"),
            final_mastery_updates=final_mastery_updates
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get session status: {e}")

# Enhanced progress endpoint
@app.get("/api/progress/enhanced", response_model=EnhancedProgressResponse, tags=["Enhanced Progress"])
async def get_enhanced_progress(current_user: dict = Depends(verify_token)):
    """Get comprehensive progress with question-level mastery tracking"""
    try:
        user_id = current_user["user_id"]
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Get overall progress
        cur.execute("""
            SELECT * FROM vw_enhanced_word_progress WHERE user_id = %s
        """, (user_id,))
        overall = cur.fetchone()
        
        if not overall:
            # Return default response if no data
            return EnhancedProgressResponse(
                user_id=user_id,
                username=current_user["username"],
                total_words_encountered=0,
                total_questions_encountered=0,
                total_questions_mastered=0,
                average_word_mastery=0.0,
                fully_mastered_words=0,
                partially_mastered_words=0,
                unmastered_words=0,
                fully_mastered_percentage=0.0,
                word_mastery_details=[],
                words_needing_practice=[]
            )
        
        # Get detailed word mastery
        cur.execute("""
            SELECT * FROM vw_word_mastery_detail 
            WHERE user_id = %s 
            ORDER BY mastery_percentage DESC, word_text
        """, (user_id,))
        word_details = cur.fetchall()
        
        # Get words needing practice
        cur.execute("""
            SELECT * FROM vw_words_needing_practice 
            WHERE user_id = %s 
            ORDER BY mastery_percentage ASC, questions_remaining DESC
            LIMIT 10
        """, (user_id,))
        words_needing_practice = cur.fetchall()
        
        # Convert to API models
        word_mastery_details = []
        for word in word_details:
            # Get question details for this word
            cur.execute("""
                SELECT * FROM vw_question_mastery_detail 
                WHERE user_id = %s AND word_text = %s
                ORDER BY quiz_type
            """, (user_id, word['word_text']))
            question_details = cur.fetchall()
            
            question_mastery_list = [
                QuestionMasteryDetail(
                    question_id=0,  # We don't have question_id in the view
                    question_text=qd['question_text'],
                    quiz_type=qd['quiz_type'],
                    first_try_correct_count=qd['first_try_correct_count'],
                    total_attempts=qd['total_attempts'],
                    is_mastered=qd['is_mastered'],
                    last_attempted=qd['last_attempted'],
                    status=qd['status']
                )
                for qd in question_details
            ]
            
            word_mastery_details.append(
                WordMasteryDetail(
                    word_text=word['word_text'],
                    total_questions=word['total_questions'],
                    mastered_questions=word['mastered_questions'],
                    mastery_percentage=float(word['mastery_percentage']),
                    mastery_status=word['mastery_status'],
                    last_updated=word['last_updated'],
                    question_details=question_mastery_list
                )
            )
        
        words_needing_practice_list = [
            WordMasteryDetail(
                word_text=word['word_text'],
                total_questions=word['total_questions'],
                mastered_questions=word['mastered_questions'],
                mastery_percentage=float(word['mastery_percentage']),
                mastery_status="Needs Practice",
                last_updated=word['last_updated']
            )
            for word in words_needing_practice
        ]
        
        cur.close()
        conn.close()
        
        return EnhancedProgressResponse(
            user_id=user_id,
            username=current_user["username"],
            total_words_encountered=overall['total_words_encountered'],
            total_questions_encountered=overall['total_questions_encountered'],
            total_questions_mastered=overall['total_questions_mastered'],
            average_word_mastery=float(overall['average_word_mastery']),
            fully_mastered_words=overall['fully_mastered_words'],
            partially_mastered_words=overall['partially_mastered_words'],
            unmastered_words=overall['unmastered_words'],
            fully_mastered_percentage=float(overall['fully_mastered_percentage']),
            word_mastery_details=word_mastery_details,
            words_needing_practice=words_needing_practice_list
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get enhanced progress: {e}")

# Helper function for mastery updates
async def get_enhanced_mastery_updates(user_id: int, question_ids: List[int]) -> List[WordMasteryDetail]:
    """Get enhanced mastery updates for questions"""
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        if not question_ids:
            return []
        
        # Get words affected by these questions
        placeholders = ','.join(['%s'] * len(question_ids))
        cur.execute(f"""
            SELECT DISTINCT w.word_text
            FROM word_question_map wqm
            JOIN words w ON wqm.word_id = w.word_id
            WHERE wqm.question_id IN ({placeholders})
        """, question_ids)
        
        affected_words = [row['word_text'] for row in cur.fetchall()]
        
        # Get mastery details for affected words
        mastery_updates = []
        for word_text in affected_words:
            cur.execute("""
                SELECT * FROM vw_word_mastery_detail 
                WHERE user_id = %s AND word_text = %s
            """, (user_id, word_text))
            
            word_detail = cur.fetchone()
            if word_detail:
                mastery_updates.append(
                    WordMasteryDetail(
                        word_text=word_detail['word_text'],
                        total_questions=word_detail['total_questions'],
                        mastered_questions=word_detail['mastered_questions'],
                        mastery_percentage=float(word_detail['mastery_percentage']),
                        mastery_status=word_detail['mastery_status'],
                        last_updated=word_detail['last_updated']
                    )
                )
        
        cur.close()
        conn.close()
        return mastery_updates
        
    except Exception as e:
        print(f"Error getting mastery updates: {e}")
        return []

# Legacy endpoints for backward compatibility
@app.post("/api/quiz/create", response_model=QuizCreationResponse, tags=["Legacy Quiz"])
async def create_quiz_legacy(
    request: QuizCreationRequest,
    current_user: dict = Depends(verify_token)
):
    """Create a traditional single-attempt quiz (legacy endpoint)"""
    try:
        user_id = current_user["user_id"]
        
        # Use existing quiz generation logic
        config = QuizConfig(
            target_question_count=20,
            exclude_recent_attempts=5
        )
        
        quiz_response = generate_quiz(user_id, request.quiz_type, config)
        
        # Convert to API response format
        questions = [
            QuestionResponse(
                question_id=q.question_id,
                question_text=q.question_text,
                options=q.options,
                quiz_type=q.quiz_type
            )
            for q in quiz_response.questions
        ]
        
        return QuizCreationResponse(
            attempt_id=quiz_response.attempt_id,
            questions=questions,
            total_questions=len(questions)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create quiz: {e}")

@app.post("/api/quiz/{attempt_id}/submit", response_model=QuizResult, tags=["Legacy Quiz"])
async def submit_quiz_legacy(
    attempt_id: int,
    submission: QuizSubmissionRequest,
    current_user: dict = Depends(verify_token)
):
    """Submit quiz responses and get final results (legacy endpoint)"""
    try:
        user_id = current_user["user_id"]
        
        # Convert API submission to internal format
        responses = [
            {"question_id": r.question_id, "selected_answer": r.selected_answer}
            for r in submission.responses
        ]
        
        # Submit using existing logic
        result = submit_quiz_responses(attempt_id, responses, user_id)
        
        return QuizResult(
            attempt_id=attempt_id,
            score=result.score,
            total_questions=result.total_questions,
            percentage=result.percentage,
            correct_answers=result.correct_answers,
            incorrect_answers=result.incorrect_answers,
            mastery_updates=asdict(result) if hasattr(result, '__dict__') else {}
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to submit quiz: {e}")

@app.get("/api/progress", response_model=ProgressResponse, tags=["Legacy Progress"])
async def get_progress_legacy(current_user: dict = Depends(verify_token)):
    """Get user progress and statistics (legacy endpoint)"""
    try:
        user_id = current_user["user_id"]
        progress = get_user_progress(user_id)
        
        return ProgressResponse(
            global_stats=progress.get("global_stats", {}),
            by_quiz_type=progress.get("by_quiz_type", []),
            recent_activity=progress.get("recent_activity", []),
            words_to_review=progress.get("words_to_review", [])
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get progress: {e}")

# Demo/Testing endpoint
@app.get("/demo", response_class=HTMLResponse, tags=["Demo"])
async def get_demo_page():
    """Get demo page for testing the enhanced API"""
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Enhanced Vocabulary Learning Demo</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            .mastery-bar { height: 8px; border-radius: 4px; }
            .mastery-high { background: linear-gradient(90deg, #10b981, #059669); }
            .mastery-medium { background: linear-gradient(90deg, #f59e0b, #d97706); }
            .mastery-low { background: linear-gradient(90deg, #ef4444, #dc2626); }
            .question-card { transition: all 0.2s; }
            .question-card:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
        </style>
    </head>
    <body class="bg-light">
        <div class="container mt-4">
            <h1 class="text-center mb-4">🎓 Enhanced Vocabulary Learning System</h1>
            <p class="text-center text-muted">Question-Level Word Mastery Tracking</p>
            
            <div class="row">
                <div class="col-md-8 mx-auto">
                    <div id="app">
                        <div class="card mb-4">
                            <div class="card-header">
                                <h5>🔐 Authentication</h5>
                            </div>
                            <div class="card-body">
                                <div id="auth-section">
                                    <div class="row">
                                        <div class="col-md-6">
                                            <input type="text" id="username" class="form-control mb-2" placeholder="Username">
                                            <input type="password" id="password" class="form-control mb-2" placeholder="Password">
                                            <button onclick="login()" class="btn btn-primary me-2">Login</button>
                                            <button onclick="register()" class="btn btn-secondary">Register</button>
                                        </div>
                                        <div class="col-md-6">
                                            <p class="small text-muted">Demo Credentials:</p>
                                            <p class="small">Username: <code>testuser</code><br>Password: <code>user123</code></p>
                                        </div>
                                    </div>
                                </div>
                                <div id="user-info" style="display: none;"></div>
                            </div>
                        </div>
                        
                        <div id="quiz-section" style="display: none;">
                            <div class="card mb-4">
                                <div class="card-header">
                                    <h5>📊 Enhanced Progress Dashboard</h5>
                                </div>
                                <div class="card-body">
                                    <button onclick="getEnhancedProgress()" class="btn btn-info mb-3">Refresh Progress</button>
                                    <div id="progress-display"></div>
                                </div>
                            </div>
                            
                            <div class="card mb-4">
                                <div class="card-header">
                                    <h5>🎯 Start Enhanced Quiz Session</h5>
                                </div>
                                <div class="card-body">
                                    <button onclick="createQuizSession()" class="btn btn-success">Create Repetitive Quiz Session</button>
                                    <div id="quiz-display" class="mt-3"></div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <script>
            let authToken = '';
            let currentSession = null;
            let currentQuestions = [];

            async function apiCall(endpoint, method = 'GET', data = null) {
                const options = {
                    method,
                    headers: {
                        'Content-Type': 'application/json',
                        ...(authToken && { 'Authorization': `Bearer ${authToken}` })
                    }
                };
                
                if (data) options.body = JSON.stringify(data);
                
                const response = await fetch(endpoint, options);
                if (!response.ok) throw new Error(`HTTP ${response.status}: ${await response.text()}`);
                return response.json();
            }

            async function login() {
                try {
                    const username = document.getElementById('username').value;
                    const password = document.getElementById('password').value;
                    
                    const params = new URLSearchParams();
                    params.append('username', username);
                    params.append('password', password);
                    
                    const response = await fetch('/api/auth/login', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                        body: params
                    });
                    
                    if (!response.ok) throw new Error('Login failed');
                    
                    const result = await response.json();
                    authToken = result.access_token;
                    
                    document.getElementById('auth-section').style.display = 'none';
                    document.getElementById('user-info').style.display = 'block';
                    document.getElementById('user-info').innerHTML = `
                        <div class="alert alert-success">
                            ✅ Logged in as: <strong>${result.username}</strong>
                            <button onclick="logout()" class="btn btn-sm btn-outline-secondary ms-2">Logout</button>
                        </div>
                    `;
                    document.getElementById('quiz-section').style.display = 'block';
                    
                    await getEnhancedProgress();
                } catch (error) {
                    alert('Login failed: ' + error.message);
                }
            }

            async function register() {
                try {
                    const username = document.getElementById('username').value;
                    const password = document.getElementById('password').value;
                    
                    const params = new URLSearchParams();
                    params.append('username', username);
                    params.append('password', password);
                    
                    const response = await fetch('/api/auth/register', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                        body: params
                    });
                    
                    if (!response.ok) throw new Error('Registration failed');
                    
                    alert('Registration successful! You can now log in.');
                } catch (error) {
                    alert('Registration failed: ' + error.message);
                }
            }

            function logout() {
                authToken = '';
                currentSession = null;
                currentQuestions = [];
                
                document.getElementById('auth-section').style.display = 'block';
                document.getElementById('user-info').style.display = 'none';
                document.getElementById('quiz-section').style.display = 'none';
                document.getElementById('username').value = '';
                document.getElementById('password').value = '';
            }

            async function getEnhancedProgress() {
                try {
                    const progress = await apiCall('/api/progress/enhanced');
                    
                    let html = `
                        <div class="row mb-4">
                            <div class="col-md-3">
                                <div class="card text-center">
                                    <div class="card-body">
                                        <h5 class="card-title">${progress.total_words_encountered}</h5>
                                        <p class="card-text small">Words Encountered</p>
                                    </div>
                                </div>
                            </div>
                            <div class="col-md-3">
                                <div class="card text-center">
                                    <div class="card-body">
                                        <h5 class="card-title">${progress.total_questions_encountered}</h5>
                                        <p class="card-text small">Questions Encountered</p>
                                    </div>
                                </div>
                            </div>
                            <div class="col-md-3">
                                <div class="card text-center">
                                    <div class="card-body">
                                        <h5 class="card-title">${progress.total_questions_mastered}</h5>
                                        <p class="card-text small">Questions Mastered</p>
                                    </div>
                                </div>
                            </div>
                            <div class="col-md-3">
                                <div class="card text-center">
                                    <div class="card-body">
                                        <h5 class="card-title">${progress.average_word_mastery.toFixed(1)}%</h5>
                                        <p class="card-text small">Avg Word Mastery</p>
                                    </div>
                                </div>
                            </div>
                        </div>
                        
                        <div class="mb-4">
                            <h6>Word Mastery Breakdown</h6>
                            <div class="row">
                                <div class="col-md-4">
                                    <div class="text-success">✅ Fully Mastered: ${progress.fully_mastered_words}</div>
                                </div>
                                <div class="col-md-4">
                                    <div class="text-warning">📈 Partially Mastered: ${progress.partially_mastered_words}</div>
                                </div>
                                <div class="col-md-4">
                                    <div class="text-danger">🔴 Not Started: ${progress.unmastered_words}</div>
                                </div>
                            </div>
                        </div>
                    `;
                    
                    if (progress.words_needing_practice.length > 0) {
                        html += `
                            <div class="mb-4">
                                <h6>Words Needing Practice</h6>
                                ${progress.words_needing_practice.slice(0, 5).map(word => `
                                    <div class="d-flex justify-content-between align-items-center mb-2">
                                        <span><strong>${word.word_text}</strong></span>
                                        <div class="d-flex align-items-center">
                                            <span class="me-2 small">${word.mastery_percentage}%</span>
                                            <div class="mastery-bar ${word.mastery_percentage > 70 ? 'mastery-high' : word.mastery_percentage > 30 ? 'mastery-medium' : 'mastery-low'}" 
                                                 style="width: 100px; height: 8px; background: #e5e7eb; border-radius: 4px;">
                                                <div style="width: ${word.mastery_percentage}%; height: 100%; border-radius: 4px;" 
                                                     class="${word.mastery_percentage > 70 ? 'bg-success' : word.mastery_percentage > 30 ? 'bg-warning' : 'bg-danger'}"></div>
                                            </div>
                                        </div>
                                    </div>
                                `).join('')}
                            </div>
                        `;
                    }
                    
                    document.getElementById('progress-display').innerHTML = html;
                } catch (error) {
                    console.error('Progress fetch failed:', error);
                }
            }

            async function createQuizSession() {
                try {
                    const session = await apiCall('/api/quiz/session/create', 'POST', {
                        question_count: 5  // Smaller for demo
                    });
                    
                    currentSession = session;
                    currentQuestions = session.questions;
                    
                    displayQuestions();
                } catch (error) {
                    alert('Failed to create quiz session: ' + error.message);
                }
            }

            function displayQuestions() {
                if (!currentQuestions || currentQuestions.length === 0) {
                    document.getElementById('quiz-display').innerHTML = `
                        <div class="alert alert-success">
                            🎉 <strong>Quiz Session Complete!</strong> All questions mastered!
                        </div>
                    `;
                    return;
                }
                
                let html = `
                    <h6>📝 Quiz Questions (${currentQuestions.length} remaining)</h6>
                    <form id="quiz-form">
                `;
                
                currentQuestions.forEach((question, index) => {
                    html += `
                        <div class="card question-card mb-3">
                            <div class="card-body">
                                <h6 class="card-title">Question ${index + 1}: ${question.quiz_type}</h6>
                                <p class="card-text">${question.question_text}</p>
                                <div class="options">
                                    ${question.options.map(option => `
                                        <div class="form-check">
                                            <input class="form-check-input" type="radio" 
                                                   name="question_${question.question_id}" 
                                                   value="${option}" id="q${question.question_id}_${option}">
                                            <label class="form-check-label" for="q${question.question_id}_${option}">
                                                ${option}
                                            </label>
                                        </div>
                                    `).join('')}
                                </div>
                            </div>
                        </div>
                    `;
                });
                
                html += `
                        <button type="button" onclick="submitQuizRound()" class="btn btn-primary">Submit Round</button>
                    </form>
                `;
                
                document.getElementById('quiz-display').innerHTML = html;
            }

            async function submitQuizRound() {
                try {
                    const responses = [];
                    
                    currentQuestions.forEach(question => {
                        const selected = document.querySelector(`input[name="question_${question.question_id}"]:checked`);
                        if (selected) {
                            responses.push({
                                question_id: question.question_id,
                                selected_answer: selected.value
                            });
                        }
                    });
                    
                    if (responses.length !== currentQuestions.length) {
                        alert('Please answer all questions before submitting.');
                        return;
                    }
                    
                    const result = await apiCall(`/api/quiz/session/${currentSession.session_id}/submit`, 'POST', {
                        responses: responses
                    });
                    
                    // Show results
                    let resultHtml = `
                        <div class="alert alert-info mb-3">
                            <h6>Round ${result.round_number} Results</h6>
                            <p>Correct: ${result.correct_answers}/${result.total_questions}</p>
                        `;
                    
                    if (result.mastery_updates.length > 0) {
                        resultHtml += `
                            <div class="mt-2">
                                <strong>Mastery Updates:</strong>
                                ${result.mastery_updates.map(update => `
                                    <div class="small">
                                        <span class="badge bg-secondary">${update.word_text}</span>
                                        ${update.mastery_percentage}% mastered
                                    </div>
                                `).join('')}
                            </div>
                        `;
                    }
                    
                    resultHtml += `</div>`;
                    
                    // Update current questions for next round
                    currentQuestions = result.next_questions;
                    
                    if (result.is_session_complete) {
                        resultHtml += `
                            <div class="alert alert-success">
                                🎊 <strong>Session Complete!</strong> All questions mastered!
                                <button onclick="getEnhancedProgress()" class="btn btn-sm btn-success ms-2">Update Progress</button>
                            </div>
                        `;
                        currentSession = null;
                        currentQuestions = [];
                    } else {
                        resultHtml += `<button onclick="displayQuestions()" class="btn btn-info">Continue to Next Round</button>`;
                    }
                    
                    document.getElementById('quiz-display').innerHTML = resultHtml;
                    
                } catch (error) {
                    alert('Failed to submit quiz round: ' + error.message);
                }
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
