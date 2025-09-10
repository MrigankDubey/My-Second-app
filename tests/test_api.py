#!/usr/bin/env python3
"""
Basic API Tests for the Vocabulary Quiz System
Tests authentication, quiz creation, and submission workflows
"""

import pytest
import json
from fastapi.testclient import TestClient
from app import app

client = TestClient(app)

# Test data
TEST_USER = {
    "username": "testuser",
    "password": "testpass123",
    "email": "test@example.com"
}

TEST_QUIZ_CONFIG = {
    "target_question_count": 10,
    "exclude_recent_attempts": 3
}

class TestAuthentication:
    """Test authentication endpoints"""
    
    def test_register_user(self):
        """Test user registration"""
        response = client.post("/api/auth/register", json=TEST_USER)
        assert response.status_code == 200
        
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert "expires_in" in data
    
    def test_register_duplicate_user(self):
        """Test duplicate user registration fails"""
        # First registration should succeed
        client.post("/api/auth/register", json=TEST_USER)
        
        # Second registration should fail
        response = client.post("/api/auth/register", json=TEST_USER)
        assert response.status_code == 400
        assert "already registered" in response.json()["error"].lower()
    
    def test_login_valid_user(self):
        """Test login with valid credentials"""
        # Register user first
        client.post("/api/auth/register", json=TEST_USER)
        
        # Login
        login_data = {
            "username": TEST_USER["username"],
            "password": TEST_USER["password"]
        }
        response = client.post("/api/auth/login", json=login_data)
        assert response.status_code == 200
        
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
    
    def test_login_invalid_user(self):
        """Test login with invalid credentials"""
        login_data = {
            "username": "nonexistent",
            "password": "wrongpass"
        }
        response = client.post("/api/auth/login", json=login_data)
        assert response.status_code == 401
        assert "incorrect" in response.json()["error"].lower()

class TestQuizAPI:
    """Test quiz-related endpoints"""
    
    @pytest.fixture
    def auth_headers(self):
        """Get authentication headers for requests"""
        # Register and login user
        client.post("/api/auth/register", json=TEST_USER)
        
        login_data = {
            "username": TEST_USER["username"],
            "password": TEST_USER["password"]
        }
        response = client.post("/api/auth/login", json=login_data)
        token = response.json()["access_token"]
        
        return {"Authorization": f"Bearer {token}"}
    
    def test_get_quiz_types(self):
        """Test getting available quiz types"""
        response = client.get("/api/quiz/types")
        assert response.status_code == 200
        
        quiz_types = response.json()
        assert isinstance(quiz_types, list)
        assert len(quiz_types) > 0
        
        # Check structure of quiz type
        quiz_type = quiz_types[0]
        assert "name" in quiz_type
        assert "display_name" in quiz_type
        assert "description" in quiz_type
    
    def test_create_quiz_authenticated(self, auth_headers):
        """Test creating a quiz with authentication"""
        response = client.post(
            "/api/quiz/create",
            json=TEST_QUIZ_CONFIG,
            headers=auth_headers
        )
        assert response.status_code == 200
        
        quiz_data = response.json()
        assert "attempt_id" in quiz_data
        assert "questions" in quiz_data
        assert len(quiz_data["questions"]) == TEST_QUIZ_CONFIG["target_question_count"]
        
        # Check question structure
        question = quiz_data["questions"][0]
        assert "question_id" in question
        assert "question_text" in question
        assert "options" in question
        assert "quiz_type" in question
        # Should NOT contain correct_answer in question list
        assert "correct_answer" not in question
    
    def test_create_quiz_unauthenticated(self):
        """Test creating a quiz without authentication fails"""
        response = client.post("/api/quiz/create", json=TEST_QUIZ_CONFIG)
        assert response.status_code == 403  # HTTPBearer requires auth
    
    def test_submit_quiz(self, auth_headers):
        """Test submitting quiz responses"""
        # First create a quiz
        response = client.post(
            "/api/quiz/create",
            json=TEST_QUIZ_CONFIG,
            headers=auth_headers
        )
        quiz_data = response.json()
        attempt_id = quiz_data["attempt_id"]
        
        # Prepare responses (just select first option for each question)
        responses = []
        for question in quiz_data["questions"]:
            responses.append({
                "question_id": question["question_id"],
                "answer": question["options"][0]  # Select first option
            })
        
        # Submit quiz
        submission = {"responses": responses}
        response = client.post(
            f"/api/quiz/{attempt_id}/submit",
            json=submission,
            headers=auth_headers
        )
        assert response.status_code == 200
        
        result = response.json()
        assert "attempt_id" in result
        assert "total_questions" in result
        assert "correct_answers" in result
        assert "score_percentage" in result
        assert "individual_results" in result
        assert "mastery_updates" in result
        assert "performance_by_type" in result
    
    def test_get_user_progress(self, auth_headers):
        """Test getting user progress"""
        # Create and submit a quiz first to have some progress
        # Create quiz
        response = client.post(
            "/api/quiz/create",
            json=TEST_QUIZ_CONFIG,
            headers=auth_headers
        )
        quiz_data = response.json()
        attempt_id = quiz_data["attempt_id"]
        
        # Submit quiz
        responses = []
        for question in quiz_data["questions"]:
            responses.append({
                "question_id": question["question_id"],
                "answer": question["options"][0]
            })
        
        submission = {"responses": responses}
        client.post(
            f"/api/quiz/{attempt_id}/submit",
            json=submission,
            headers=auth_headers
        )
        
        # Get progress
        response = client.get("/api/progress", headers=auth_headers)
        assert response.status_code == 200
        
        progress = response.json()
        assert "username" in progress
        assert "recent_quizzes" in progress
        assert "total_attempts" in progress
        assert len(progress["recent_quizzes"]) >= 1

class TestHealthCheck:
    """Test system health endpoints"""
    
    def test_health_check(self):
        """Test health check endpoint"""
        response = client.get("/api/health")
        # Should return 200 if database is accessible, 503 if not
        assert response.status_code in [200, 503]
        
        data = response.json()
        assert "status" in data
        assert "timestamp" in data

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
