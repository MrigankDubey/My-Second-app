#!/usr/bin/env python3
"""
CSV Upload Validation System
Comprehensive validation for CSV files containing vocabulary questions
Prevents incompatible entries and ensures data integrity
"""

import os
import csv
import re
import pandas as pd
import psycopg2
import psycopg2.extras
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from enum import Enum
from dotenv import load_dotenv

load_dotenv()

class ValidationLevel(Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"

@dataclass
class ValidationResult:
    level: ValidationLevel
    field: str
    row_number: int
    message: str
    value: Any = None

class CSVUploadValidator:
    """Comprehensive CSV validation system for vocabulary questions"""
    
    # Supported quiz types
    VALID_QUIZ_TYPES = {
        'synonym', 'antonym', 'analogy', 'fill_in_blank', 
        'word_meaning', 'odd_one_out', 'multiple_choice'
    }
    
    # Required CSV columns
    REQUIRED_COLUMNS = ['question_text', 'quiz_type', 'correct_answer']
    OPTIONAL_COLUMNS = ['options', 'difficulty', 'category', 'explanation']
    
    # Validation constraints
    MAX_QUESTION_LENGTH = 500
    MAX_ANSWER_LENGTH = 200
    MAX_OPTION_LENGTH = 100
    MIN_OPTIONS_COUNT = 2
    MAX_OPTIONS_COUNT = 6
    
    def __init__(self, database_url: str = None):
        self.database_url = database_url or os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost/vocab_app')
        self.validation_results: List[ValidationResult] = []
        self.valid_rows: List[Dict] = []
        self.invalid_rows: List[Dict] = []
        
    def validate_csv_file(self, file_path: str) -> Tuple[bool, List[ValidationResult]]:
        """
        Validate entire CSV file for upload compatibility
        
        Args:
            file_path: Path to CSV file
            
        Returns:
            Tuple of (is_valid, validation_results)
        """
        self.validation_results.clear()
        self.valid_rows.clear()
        self.invalid_rows.clear()
        
        # File existence and format check
        if not self._validate_file_format(file_path):
            return False, self.validation_results
        
        # Load and validate CSV structure
        try:
            df = pd.read_csv(file_path, encoding='utf-8')
        except Exception as e:
            self.validation_results.append(ValidationResult(
                ValidationLevel.ERROR, "file", 0, f"Failed to read CSV: {str(e)}"
            ))
            return False, self.validation_results
        
        # Validate CSV structure
        if not self._validate_csv_structure(df):
            return False, self.validation_results
        
        # Validate each row
        for index, row in df.iterrows():
            row_number = index + 2  # +2 because pandas is 0-indexed and CSV has header
            row_valid = self._validate_row(row, row_number)
            
            if row_valid:
                self.valid_rows.append(row.to_dict())
            else:
                self.invalid_rows.append(row.to_dict())
        
        # Database compatibility check
        self._validate_database_compatibility()
        
        # Overall validation result
        has_errors = any(result.level == ValidationLevel.ERROR for result in self.validation_results)
        return not has_errors, self.validation_results
    
    def _validate_file_format(self, file_path: str) -> bool:
        """Validate file existence and format"""
        if not os.path.exists(file_path):
            self.validation_results.append(ValidationResult(
                ValidationLevel.ERROR, "file", 0, "File does not exist"
            ))
            return False
        
        if not file_path.lower().endswith('.csv'):
            self.validation_results.append(ValidationResult(
                ValidationLevel.ERROR, "file", 0, "File must be a CSV file"
            ))
            return False
        
        # Check file size (max 10MB)
        file_size = os.path.getsize(file_path)
        if file_size > 10 * 1024 * 1024:
            self.validation_results.append(ValidationResult(
                ValidationLevel.ERROR, "file", 0, f"File too large: {file_size / (1024*1024):.1f}MB (max 10MB)"
            ))
            return False
        
        # Check if file is empty
        if file_size == 0:
            self.validation_results.append(ValidationResult(
                ValidationLevel.ERROR, "file", 0, "File is empty"
            ))
            return False
        
        return True
    
    def _validate_csv_structure(self, df: pd.DataFrame) -> bool:
        """Validate CSV column structure"""
        columns = [col.strip().lower() for col in df.columns]
        
        # Check for required columns
        missing_columns = [col for col in self.REQUIRED_COLUMNS if col not in columns]
        if missing_columns:
            self.validation_results.append(ValidationResult(
                ValidationLevel.ERROR, "structure", 0, 
                f"Missing required columns: {', '.join(missing_columns)}"
            ))
            return False
        
        # Check for unknown columns
        all_valid_columns = self.REQUIRED_COLUMNS + self.OPTIONAL_COLUMNS
        unknown_columns = [col for col in columns if col not in all_valid_columns]
        if unknown_columns:
            self.validation_results.append(ValidationResult(
                ValidationLevel.WARNING, "structure", 0,
                f"Unknown columns will be ignored: {', '.join(unknown_columns)}"
            ))
        
        # Check if CSV has data rows
        if len(df) == 0:
            self.validation_results.append(ValidationResult(
                ValidationLevel.ERROR, "structure", 0, "CSV has no data rows"
            ))
            return False
        
        # Check for reasonable number of rows
        if len(df) > 1000:
            self.validation_results.append(ValidationResult(
                ValidationLevel.WARNING, "structure", 0,
                f"Large file with {len(df)} rows - consider splitting for better performance"
            ))
        
        return True
    
    def _validate_row(self, row: pd.Series, row_number: int) -> bool:
        """Validate individual row data"""
        row_valid = True
        
        # Check for required fields
        for field in self.REQUIRED_COLUMNS:
            if pd.isna(row.get(field)) or str(row.get(field, '')).strip() == '':
                self.validation_results.append(ValidationResult(
                    ValidationLevel.ERROR, field, row_number,
                    f"Required field '{field}' is empty"
                ))
                row_valid = False
        
        # Validate quiz type
        quiz_type = str(row.get('quiz_type', '')).strip().lower()
        if quiz_type not in self.VALID_QUIZ_TYPES:
            self.validation_results.append(ValidationResult(
                ValidationLevel.ERROR, "quiz_type", row_number,
                f"Invalid quiz type '{quiz_type}'. Valid types: {', '.join(self.VALID_QUIZ_TYPES)}"
            ))
            row_valid = False
        
        # Validate question text
        question_text = str(row.get('question_text', '')).strip()
        if len(question_text) > self.MAX_QUESTION_LENGTH:
            self.validation_results.append(ValidationResult(
                ValidationLevel.ERROR, "question_text", row_number,
                f"Question text too long: {len(question_text)} chars (max {self.MAX_QUESTION_LENGTH})"
            ))
            row_valid = False
        
        if len(question_text) < 10:
            self.validation_results.append(ValidationResult(
                ValidationLevel.WARNING, "question_text", row_number,
                f"Question text very short: {len(question_text)} chars"
            ))
        
        # Validate correct answer
        correct_answer = str(row.get('correct_answer', '')).strip()
        if len(correct_answer) > self.MAX_ANSWER_LENGTH:
            self.validation_results.append(ValidationResult(
                ValidationLevel.ERROR, "correct_answer", row_number,
                f"Correct answer too long: {len(correct_answer)} chars (max {self.MAX_ANSWER_LENGTH})"
            ))
            row_valid = False
        
        # Validate options if present
        options_str = str(row.get('options', '')).strip()
        if options_str and options_str.lower() != 'nan':
            options = [opt.strip() for opt in options_str.split(',')]
            options = [opt for opt in options if opt]  # Remove empty options
            
            if len(options) < self.MIN_OPTIONS_COUNT:
                self.validation_results.append(ValidationResult(
                    ValidationLevel.WARNING, "options", row_number,
                    f"Few options provided: {len(options)} (recommended: {self.MIN_OPTIONS_COUNT}-{self.MAX_OPTIONS_COUNT})"
                ))
            
            if len(options) > self.MAX_OPTIONS_COUNT:
                self.validation_results.append(ValidationResult(
                    ValidationLevel.WARNING, "options", row_number,
                    f"Many options provided: {len(options)} (recommended: {self.MIN_OPTIONS_COUNT}-{self.MAX_OPTIONS_COUNT})"
                ))
            
            # Check if correct answer is in options
            if correct_answer not in options:
                self.validation_results.append(ValidationResult(
                    ValidationLevel.ERROR, "options", row_number,
                    f"Correct answer '{correct_answer}' not found in options: {', '.join(options)}"
                ))
                row_valid = False
            
            # Check option lengths
            for i, option in enumerate(options):
                if len(option) > self.MAX_OPTION_LENGTH:
                    self.validation_results.append(ValidationResult(
                        ValidationLevel.ERROR, "options", row_number,
                        f"Option {i+1} too long: {len(option)} chars (max {self.MAX_OPTION_LENGTH})"
                    ))
                    row_valid = False
        
        # Quiz type specific validations
        row_valid = self._validate_quiz_type_specific(row, row_number, quiz_type) and row_valid
        
        return row_valid
    
    def _validate_quiz_type_specific(self, row: pd.Series, row_number: int, quiz_type: str) -> bool:
        """Validate quiz type specific requirements"""
        row_valid = True
        question_text = str(row.get('question_text', '')).strip()
        correct_answer = str(row.get('correct_answer', '')).strip()
        
        if quiz_type == 'analogy':
            # Analogy questions should have ":" and "::" patterns
            if '::' not in question_text or question_text.count(':') < 3:
                self.validation_results.append(ValidationResult(
                    ValidationLevel.WARNING, "question_text", row_number,
                    "Analogy questions typically use format 'A : B :: C : ?'"
                ))
        
        elif quiz_type == 'fill_in_blank':
            # Fill in blank should have blanks indicated
            blank_patterns = ['_____', '____', '___', '__', '_']
            has_blank = any(pattern in question_text for pattern in blank_patterns)
            if not has_blank:
                self.validation_results.append(ValidationResult(
                    ValidationLevel.WARNING, "question_text", row_number,
                    "Fill in blank questions should contain blanks (e.g., _____)"
                ))
        
        elif quiz_type == 'synonym':
            # Synonym questions should ask for similar words
            synonym_keywords = ['synonym', 'similar', 'same meaning', 'equivalent']
            has_synonym_keyword = any(keyword in question_text.lower() for keyword in synonym_keywords)
            if not has_synonym_keyword:
                self.validation_results.append(ValidationResult(
                    ValidationLevel.WARNING, "question_text", row_number,
                    "Synonym questions should mention 'synonym', 'similar', or 'same meaning'"
                ))
        
        elif quiz_type == 'antonym':
            # Antonym questions should ask for opposite words
            antonym_keywords = ['antonym', 'opposite', 'contrary', 'reverse']
            has_antonym_keyword = any(keyword in question_text.lower() for keyword in antonym_keywords)
            if not has_antonym_keyword:
                self.validation_results.append(ValidationResult(
                    ValidationLevel.WARNING, "question_text", row_number,
                    "Antonym questions should mention 'antonym', 'opposite', or 'contrary'"
                ))
        
        elif quiz_type == 'odd_one_out':
            # Odd one out should mention finding the different item
            odd_keywords = ['odd', 'different', 'does not belong', 'exception']
            has_odd_keyword = any(keyword in question_text.lower() for keyword in odd_keywords)
            if not has_odd_keyword:
                self.validation_results.append(ValidationResult(
                    ValidationLevel.WARNING, "question_text", row_number,
                    "Odd one out questions should mention 'odd', 'different', or 'does not belong'"
                ))
        
        return row_valid
    
    def _validate_database_compatibility(self):
        """Check compatibility with existing database schema"""
        try:
            conn = psycopg2.connect(self.database_url)
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            # Check if database schema exists
            cur.execute("""
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_name IN ('questions', 'words', 'users')
            """)
            tables = [row['table_name'] for row in cur.fetchall()]
            
            missing_tables = ['questions', 'words', 'users']
            missing_tables = [table for table in missing_tables if table not in tables]
            
            if missing_tables:
                self.validation_results.append(ValidationResult(
                    ValidationLevel.ERROR, "database", 0,
                    f"Missing database tables: {', '.join(missing_tables)}. Run schema setup first."
                ))
            
            # Check for required functions
            cur.execute("""
                SELECT routine_name FROM information_schema.routines 
                WHERE routine_schema = 'public' AND routine_name = 'add_question_with_mastery_tracking'
            """)
            
            if not cur.fetchone():
                self.validation_results.append(ValidationResult(
                    ValidationLevel.ERROR, "database", 0,
                    "Enhanced word mastery functions not found. Update database schema."
                ))
            
            cur.close()
            conn.close()
            
        except Exception as e:
            self.validation_results.append(ValidationResult(
                ValidationLevel.ERROR, "database", 0,
                f"Database connection failed: {str(e)}"
            ))
    
    def get_validation_summary(self) -> Dict[str, Any]:
        """Get summary of validation results"""
        error_count = sum(1 for r in self.validation_results if r.level == ValidationLevel.ERROR)
        warning_count = sum(1 for r in self.validation_results if r.level == ValidationLevel.WARNING)
        info_count = sum(1 for r in self.validation_results if r.level == ValidationLevel.INFO)
        
        return {
            'total_rows': len(self.valid_rows) + len(self.invalid_rows),
            'valid_rows': len(self.valid_rows),
            'invalid_rows': len(self.invalid_rows),
            'error_count': error_count,
            'warning_count': warning_count,
            'info_count': info_count,
            'can_import': error_count == 0,
            'validation_results': self.validation_results
        }
    
    def generate_validation_report(self) -> str:
        """Generate human-readable validation report"""
        summary = self.get_validation_summary()
        
        report = []
        report.append("=== CSV VALIDATION REPORT ===")
        report.append(f"Total rows: {summary['total_rows']}")
        report.append(f"Valid rows: {summary['valid_rows']}")
        report.append(f"Invalid rows: {summary['invalid_rows']}")
        report.append(f"Errors: {summary['error_count']}")
        report.append(f"Warnings: {summary['warning_count']}")
        report.append(f"Can import: {'✓ YES' if summary['can_import'] else '✗ NO'}")
        report.append("")
        
        if self.validation_results:
            report.append("=== VALIDATION DETAILS ===")
            
            # Group by level
            errors = [r for r in self.validation_results if r.level == ValidationLevel.ERROR]
            warnings = [r for r in self.validation_results if r.level == ValidationLevel.WARNING]
            infos = [r for r in self.validation_results if r.level == ValidationLevel.INFO]
            
            if errors:
                report.append("ERRORS (must fix before import):")
                for result in errors:
                    report.append(f"  Row {result.row_number}: [{result.field}] {result.message}")
                report.append("")
            
            if warnings:
                report.append("WARNINGS (recommended to fix):")
                for result in warnings:
                    report.append(f"  Row {result.row_number}: [{result.field}] {result.message}")
                report.append("")
            
            if infos:
                report.append("INFO:")
                for result in infos:
                    report.append(f"  Row {result.row_number}: [{result.field}] {result.message}")
                report.append("")
        
        return "\n".join(report)
