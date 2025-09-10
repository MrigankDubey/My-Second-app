#!/usr/bin/env python3
"""
CSV Upload Service
Handles secure file uploads with comprehensive validation and database integration
"""

import os
import shutil
import uuid
import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
import psycopg2
import psycopg2.extras
from werkzeug.utils import secure_filename
from csv_upload_validator import CSVUploadValidator, ValidationLevel

class CSVUploadService:
    """Service for handling CSV file uploads with validation and import"""
    
    def __init__(self, upload_folder: str = "/tmp/csv_uploads", database_url: str = None):
        self.upload_folder = Path(upload_folder)
        self.upload_folder.mkdir(exist_ok=True)
        self.database_url = database_url or os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost/vocab_app')
        self.validator = CSVUploadValidator(self.database_url)
        
        # Allowed file extensions
        self.allowed_extensions = {'.csv'}
        
        # Max file size (10MB)
        self.max_file_size = 10 * 1024 * 1024
    
    def upload_and_validate_csv(self, file_path: str, user_id: int, filename: str = None) -> Dict[str, Any]:
        """
        Upload and validate CSV file
        
        Args:
            file_path: Path to the CSV file to upload
            user_id: ID of the user uploading the file
            filename: Original filename (optional)
            
        Returns:
            Dictionary with upload and validation results
        """
        try:
            # Generate secure filename and unique upload ID
            upload_id = str(uuid.uuid4())
            original_filename = filename or os.path.basename(file_path)
            secure_name = secure_filename(original_filename)
            
            # Create upload directory for this batch
            upload_dir = self.upload_folder / upload_id
            upload_dir.mkdir(exist_ok=True)
            
            # Copy file to upload directory
            uploaded_file_path = upload_dir / secure_name
            shutil.copy2(file_path, uploaded_file_path)
            
            # Validate the uploaded file
            is_valid, validation_results = self.validator.validate_csv_file(str(uploaded_file_path))
            
            # Create upload record
            upload_record = self._create_upload_record(
                upload_id, user_id, original_filename, secure_name, 
                str(uploaded_file_path), is_valid
            )
            
            # Generate detailed results
            summary = self.validator.get_validation_summary()
            report = self.validator.generate_validation_report()
            
            return {
                'upload_id': upload_id,
                'upload_record': upload_record,
                'is_valid': is_valid,
                'can_import': summary['can_import'],
                'validation_summary': summary,
                'validation_report': report,
                'uploaded_file_path': str(uploaded_file_path),
                'valid_rows': self.validator.valid_rows,
                'invalid_rows': self.validator.invalid_rows
            }
            
        except Exception as e:
            return {
                'upload_id': None,
                'error': f"Upload failed: {str(e)}",
                'is_valid': False,
                'can_import': False
            }
    
    def import_validated_csv(self, upload_id: str, user_id: int, force_import: bool = False) -> Dict[str, Any]:
        """
        Import a previously validated CSV file
        
        Args:
            upload_id: Upload ID from previous validation
            user_id: User ID for mastery tracking
            force_import: Import even with warnings (errors still block)
            
        Returns:
            Import results
        """
        try:
            # Get upload record
            upload_record = self._get_upload_record(upload_id)
            if not upload_record:
                return {'success': False, 'error': 'Upload record not found'}
            
            # Re-validate file
            file_path = upload_record['file_path']
            if not os.path.exists(file_path):
                return {'success': False, 'error': 'Upload file not found'}
            
            is_valid, validation_results = self.validator.validate_csv_file(file_path)
            
            # Check if import is allowed
            has_errors = any(r.level == ValidationLevel.ERROR for r in validation_results)
            has_warnings = any(r.level == ValidationLevel.WARNING for r in validation_results)
            
            if has_errors:
                return {
                    'success': False, 
                    'error': 'Cannot import: file has validation errors',
                    'validation_results': validation_results
                }
            
            if has_warnings and not force_import:
                return {
                    'success': False,
                    'error': 'File has warnings. Use force_import=True to proceed',
                    'validation_results': validation_results,
                    'requires_force': True
                }
            
            # Perform the import
            import_results = self._import_questions(self.validator.valid_rows, user_id)
            
            # Update upload record
            self._update_upload_record(upload_id, 'imported', import_results)
            
            return {
                'success': True,
                'upload_id': upload_id,
                'import_results': import_results,
                'validation_summary': self.validator.get_validation_summary()
            }
            
        except Exception as e:
            self._update_upload_record(upload_id, 'failed', {'error': str(e)})
            return {'success': False, 'error': f"Import failed: {str(e)}"}
    
    def _create_upload_record(self, upload_id: str, user_id: int, original_filename: str, 
                            secure_filename: str, file_path: str, is_valid: bool) -> Dict[str, Any]:
        """Create upload record in database"""
        try:
            conn = psycopg2.connect(self.database_url)
            conn.autocommit = True
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            # Create uploads table if it doesn't exist
            cur.execute("""
                CREATE TABLE IF NOT EXISTS csv_uploads (
                    upload_id VARCHAR PRIMARY KEY,
                    user_id INTEGER REFERENCES users(user_id),
                    original_filename VARCHAR NOT NULL,
                    secure_filename VARCHAR NOT NULL,
                    file_path VARCHAR NOT NULL,
                    file_size BIGINT,
                    is_valid BOOLEAN NOT NULL,
                    status VARCHAR DEFAULT 'uploaded',
                    upload_timestamp TIMESTAMP DEFAULT NOW(),
                    import_timestamp TIMESTAMP,
                    import_results JSONB,
                    validation_results JSONB
                )
            """)
            
            file_size = os.path.getsize(file_path)
            
            cur.execute("""
                INSERT INTO csv_uploads 
                (upload_id, user_id, original_filename, secure_filename, file_path, 
                 file_size, is_valid, validation_results)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING *
            """, (
                upload_id, user_id, original_filename, secure_filename, 
                file_path, file_size, is_valid, 
                [{'level': r.level.value, 'field': r.field, 'row_number': r.row_number, 
                  'message': r.message} for r in self.validator.validation_results]
            ))
            
            record = cur.fetchone()
            cur.close()
            conn.close()
            
            return dict(record)
            
        except Exception as e:
            return {'error': f"Failed to create upload record: {str(e)}"}
    
    def _get_upload_record(self, upload_id: str) -> Optional[Dict[str, Any]]:
        """Get upload record from database"""
        try:
            conn = psycopg2.connect(self.database_url)
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            cur.execute("SELECT * FROM csv_uploads WHERE upload_id = %s", (upload_id,))
            record = cur.fetchone()
            
            cur.close()
            conn.close()
            
            return dict(record) if record else None
            
        except Exception:
            return None
    
    def _update_upload_record(self, upload_id: str, status: str, import_results: Dict[str, Any]):
        """Update upload record with import results"""
        try:
            conn = psycopg2.connect(self.database_url)
            conn.autocommit = True
            cur = conn.cursor()
            
            cur.execute("""
                UPDATE csv_uploads 
                SET status = %s, import_timestamp = NOW(), import_results = %s
                WHERE upload_id = %s
            """, (status, import_results, upload_id))
            
            cur.close()
            conn.close()
            
        except Exception as e:
            print(f"Failed to update upload record: {e}")
    
    def _import_questions(self, valid_rows: List[Dict], user_id: int) -> Dict[str, Any]:
        """Import validated questions into database"""
        conn = psycopg2.connect(self.database_url)
        conn.autocommit = True
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        imported_questions = []
        import_errors = []
        
        try:
            for i, row in enumerate(valid_rows, 1):
                try:
                    # Clean and prepare data
                    quiz_type = row['quiz_type'].strip().lower()
                    question_text = row['question_text'].strip()
                    correct_answer = row['correct_answer'].strip()
                    
                    # Handle options
                    options_str = str(row.get('options', '')).strip()
                    if options_str and options_str.lower() != 'nan':
                        options = [opt.strip() for opt in options_str.split(',')]
                        options = [opt for opt in options if opt]  # Remove empty
                    else:
                        options = []
                    
                    # Import using enhanced function
                    cur.execute("""
                        SELECT add_question_with_mastery_tracking(%s, %s, %s, %s, %s) as question_id
                    """, (quiz_type, question_text, correct_answer, options, user_id))
                    
                    result = cur.fetchone()
                    question_id = result['question_id']
                    
                    imported_questions.append({
                        'row_number': i,
                        'question_id': question_id,
                        'quiz_type': quiz_type,
                        'question_text': question_text,
                        'correct_answer': correct_answer
                    })
                    
                except Exception as e:
                    import_errors.append({
                        'row_number': i,
                        'error': str(e),
                        'data': row
                    })
        
        finally:
            cur.close()
            conn.close()
        
        return {
            'imported_count': len(imported_questions),
            'error_count': len(import_errors),
            'imported_questions': imported_questions,
            'import_errors': import_errors,
            'success_rate': len(imported_questions) / len(valid_rows) * 100 if valid_rows else 0
        }
    
    def get_upload_history(self, user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """Get upload history for a user"""
        try:
            conn = psycopg2.connect(self.database_url)
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            cur.execute("""
                SELECT upload_id, original_filename, file_size, is_valid, status,
                       upload_timestamp, import_timestamp,
                       (import_results->>'imported_count')::integer as imported_count,
                       (import_results->>'error_count')::integer as error_count
                FROM csv_uploads 
                WHERE user_id = %s 
                ORDER BY upload_timestamp DESC 
                LIMIT %s
            """, (user_id, limit))
            
            records = cur.fetchall()
            cur.close()
            conn.close()
            
            return [dict(record) for record in records]
            
        except Exception as e:
            return []
    
    def cleanup_old_uploads(self, days_old: int = 7):
        """Clean up old upload files and records"""
        try:
            conn = psycopg2.connect(self.database_url)
            conn.autocommit = True
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            # Get old upload records
            cur.execute("""
                SELECT upload_id, file_path 
                FROM csv_uploads 
                WHERE upload_timestamp < NOW() - INTERVAL %s
            """, (f"{days_old} days",))
            
            old_uploads = cur.fetchall()
            
            # Delete files and records
            deleted_files = 0
            for upload in old_uploads:
                file_path = upload['file_path']
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                        # Also remove upload directory if empty
                        upload_dir = os.path.dirname(file_path)
                        if os.path.exists(upload_dir) and not os.listdir(upload_dir):
                            os.rmdir(upload_dir)
                        deleted_files += 1
                    except Exception:
                        pass
            
            # Delete database records
            cur.execute("""
                DELETE FROM csv_uploads 
                WHERE upload_timestamp < NOW() - INTERVAL %s
            """, (f"{days_old} days",))
            
            deleted_records = cur.rowcount
            
            cur.close()
            conn.close()
            
            return {
                'deleted_files': deleted_files,
                'deleted_records': deleted_records
            }
            
        except Exception as e:
            return {'error': f"Cleanup failed: {str(e)}"}


def create_sample_invalid_csv():
    """Create a sample CSV with various validation issues for testing"""
    import csv
    
    sample_data = [
        # Header row
        ['question_text', 'quiz_type', 'correct_answer', 'options'],
        
        # Valid row
        ['What is a synonym of "happy"?', 'synonym', 'joyful', 'sad,joyful,angry,tired'],
        
        # Missing required field
        ['', 'synonym', 'large', 'small,large,tiny,huge'],
        
        # Invalid quiz type
        ['Choose the best answer.', 'invalid_type', 'correct', 'wrong,correct,maybe,never'],
        
        # Question too long
        ['This is an extremely long question that exceeds the maximum allowed length for question text in our system. ' * 10, 'synonym', 'answer', 'option1,answer,option3,option4'],
        
        # Correct answer not in options
        ['Find the antonym of "hot".', 'antonym', 'freezing', 'warm,cool,mild,tepid'],
        
        # No blanks in fill_in_blank
        ['The weather is nice today.', 'fill_in_blank', 'sunny', 'rainy,sunny,cloudy,windy'],
        
        # Good analogy format
        ['Hand : Glove :: Foot : ?', 'analogy', 'Shoe', 'Hat,Shoe,Glove,Sock'],
        
        # Missing synonym keyword
        ['Pick the word.', 'synonym', 'select', 'choose,select,pick,take'],
        
        # Too many options
        ['Color?', 'multiple_choice', 'blue', 'red,blue,green,yellow,purple,orange,pink,black,white,brown']
    ]
    
    with open('/workspaces/My-Second-app/sample_invalid.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerows(sample_data)
    
    print("Created sample_invalid.csv with various validation issues")


if __name__ == "__main__":
    # Create sample files for testing
    create_sample_invalid_csv()
    print("CSV Upload Service and Validator created successfully!")
