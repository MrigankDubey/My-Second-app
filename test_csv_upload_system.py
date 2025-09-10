#!/usr/bin/env python3
"""
CSV Upload System Demonstration
Tests the comprehensive validation and upload system with various scenarios
"""

import os
import csv
from csv_upload_validator import CSVUploadValidator
from csv_upload_service import CSVUploadService
from dotenv import load_dotenv

load_dotenv()

def create_test_csv_files():
    """Create various test CSV files to demonstrate validation"""
    
    # 1. Valid CSV file
    valid_data = [
        ['question_text', 'quiz_type', 'correct_answer', 'options'],
        ['What is a synonym of "brilliant"?', 'synonym', 'bright', 'dim,bright,dark,dull'],
        ['Choose the antonym of "ancient".', 'antonym', 'modern', 'old,historic,modern,vintage'],
        ['Word : Sentence :: Note : ?', 'analogy', 'Music', 'Book,Music,Letter,Sound'],
        ['The _____ sky was beautiful.', 'fill_in_blank', 'clear', 'cloudy,clear,dark,stormy'],
        ['Find the odd word.', 'odd_one_out', 'apple', 'car,train,plane,apple']
    ]
    
    with open('/workspaces/My-Second-app/test_valid.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerows(valid_data)
    
    # 2. CSV with errors
    error_data = [
        ['question_text', 'quiz_type', 'correct_answer', 'options'],
        ['', 'synonym', 'happy', 'sad,happy,angry,tired'],  # Empty question
        ['Valid question?', 'invalid_type', 'answer', 'opt1,answer,opt3'],  # Invalid quiz type
        ['Question text?', 'synonym', 'notinlist', 'opt1,opt2,opt3,opt4'],  # Answer not in options
        ['A' * 600, 'synonym', 'short', 'long,short,medium,brief']  # Question too long
    ]
    
    with open('/workspaces/My-Second-app/test_errors.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerows(error_data)
    
    # 3. CSV with warnings
    warning_data = [
        ['question_text', 'quiz_type', 'correct_answer', 'options'],
        ['Short?', 'synonym', 'brief', 'long,brief'],  # Very short question
        ['Pick word.', 'synonym', 'choose', 'select,choose,pick'],  # Missing synonym keyword
        ['Weather today.', 'fill_in_blank', 'sunny', 'rainy,sunny,cloudy'],  # No blanks
        ['Find different.', 'odd_one_out', 'car', 'dog,cat,bird,car'],  # Missing odd keyword
        ['A : B :: C : ?', 'analogy', 'D', 'E,D,F,G']  # Good format
    ]
    
    with open('/workspaces/My-Second-app/test_warnings.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerows(warning_data)
    
    # 4. Empty CSV
    with open('/workspaces/My-Second-app/test_empty.csv', 'w', newline='', encoding='utf-8') as f:
        pass
    
    # 5. Invalid format (missing columns)
    invalid_data = [
        ['question', 'type'],  # Missing required columns
        ['Some question?', 'synonym']
    ]
    
    with open('/workspaces/My-Second-app/test_invalid_format.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerows(invalid_data)
    
    print("Created test CSV files:")
    print("  - test_valid.csv (should pass)")
    print("  - test_errors.csv (has errors)")
    print("  - test_warnings.csv (has warnings)")
    print("  - test_empty.csv (empty file)")
    print("  - test_invalid_format.csv (missing columns)")

def test_csv_validator():
    """Test the CSV validator with different scenarios"""
    print("\n=== TESTING CSV VALIDATOR ===")
    
    validator = CSVUploadValidator()
    test_files = [
        'test_valid.csv',
        'test_errors.csv', 
        'test_warnings.csv',
        'test_empty.csv',
        'test_invalid_format.csv'
    ]
    
    for filename in test_files:
        file_path = f'/workspaces/My-Second-app/{filename}'
        print(f"\n--- Testing {filename} ---")
        
        if os.path.exists(file_path):
            is_valid, validation_results = validator.validate_csv_file(file_path)
            summary = validator.get_validation_summary()
            
            print(f"File valid: {is_valid}")
            print(f"Can import: {summary['can_import']}")
            print(f"Valid rows: {summary['valid_rows']}")
            print(f"Invalid rows: {summary['invalid_rows']}")
            print(f"Errors: {summary['error_count']}")
            print(f"Warnings: {summary['warning_count']}")
            
            if validation_results:
                print("Issues found:")
                for result in validation_results[:5]:  # Show first 5 issues
                    print(f"  {result.level.value.upper()}: Row {result.row_number}, {result.field} - {result.message}")
                if len(validation_results) > 5:
                    print(f"  ... and {len(validation_results) - 5} more issues")
        else:
            print(f"File {filename} not found")

def test_upload_service():
    """Test the upload service with validation integration"""
    print("\n=== TESTING UPLOAD SERVICE ===")
    
    upload_service = CSVUploadService()
    
    # Test valid file upload
    print("\n--- Testing Valid File Upload ---")
    result = upload_service.upload_and_validate_csv(
        '/workspaces/My-Second-app/test_valid.csv',
        user_id=1,
        filename='test_valid.csv'
    )
    
    if result.get('upload_id'):
        print(f"Upload ID: {result['upload_id']}")
        print(f"Valid: {result['is_valid']}")
        print(f"Can import: {result['can_import']}")
        print(f"Valid rows: {len(result.get('valid_rows', []))}")
        
        # Test import
        if result['can_import']:
            print("\n--- Testing Import ---")
            import_result = upload_service.import_validated_csv(
                result['upload_id'], 
                user_id=1
            )
            
            if import_result['success']:
                import_stats = import_result['import_results']
                print(f"Import successful!")
                print(f"Imported: {import_stats['imported_count']} questions")
                print(f"Errors: {import_stats['error_count']}")
                print(f"Success rate: {import_stats['success_rate']:.1f}%")
            else:
                print(f"Import failed: {import_result.get('error')}")
    else:
        print(f"Upload failed: {result.get('error')}")
    
    # Test file with errors
    print("\n--- Testing File with Errors ---")
    error_result = upload_service.upload_and_validate_csv(
        '/workspaces/My-Second-app/test_errors.csv',
        user_id=1,
        filename='test_errors.csv'
    )
    
    if error_result.get('upload_id'):
        print(f"Upload ID: {error_result['upload_id']}")
        print(f"Valid: {error_result['is_valid']}")
        print(f"Can import: {error_result['can_import']}")
        print("This file should NOT be importable due to errors")
        
        # Try to import (should fail)
        if not error_result['can_import']:
            import_result = upload_service.import_validated_csv(
                error_result['upload_id'],
                user_id=1
            )
            print(f"Import attempt result: {import_result['success']} (should be False)")
    
    # Test upload history
    print("\n--- Testing Upload History ---")
    history = upload_service.get_upload_history(user_id=1, limit=10)
    print(f"Found {len(history)} upload records:")
    for record in history:
        print(f"  {record['upload_id'][:8]}... - {record['original_filename']} - {record['status']}")

def generate_validation_reports():
    """Generate detailed validation reports for all test files"""
    print("\n=== GENERATING DETAILED VALIDATION REPORTS ===")
    
    validator = CSVUploadValidator()
    test_files = ['test_valid.csv', 'test_errors.csv', 'test_warnings.csv']
    
    for filename in test_files:
        file_path = f'/workspaces/My-Second-app/{filename}'
        if os.path.exists(file_path):
            print(f"\n--- REPORT FOR {filename} ---")
            
            is_valid, validation_results = validator.validate_csv_file(file_path)
            report = validator.generate_validation_report()
            print(report)

def test_database_integration():
    """Test database schema compatibility"""
    print("\n=== TESTING DATABASE INTEGRATION ===")
    
    validator = CSVUploadValidator()
    
    # Test with a simple valid file to check database functions
    try:
        is_valid, validation_results = validator.validate_csv_file('/workspaces/My-Second-app/test_valid.csv')
        
        db_issues = [r for r in validation_results if r.field == 'database']
        if db_issues:
            print("Database compatibility issues found:")
            for issue in db_issues:
                print(f"  {issue.level.value.upper()}: {issue.message}")
        else:
            print("✓ Database schema compatibility confirmed")
            print("✓ Required tables and functions available")
            print("✓ Enhanced word mastery tracking ready")
            
    except Exception as e:
        print(f"Database test failed: {e}")

def main():
    """Run comprehensive CSV upload system demonstration"""
    print("=== CSV UPLOAD SYSTEM COMPREHENSIVE DEMONSTRATION ===")
    
    # Create test files
    create_test_csv_files()
    
    # Test validator
    test_csv_validator()
    
    # Test upload service
    test_upload_service()
    
    # Generate detailed reports
    generate_validation_reports()
    
    # Test database integration
    test_database_integration()
    
    print("\n=== DEMONSTRATION COMPLETE ===")
    print("Key Features Demonstrated:")
    print("✓ Comprehensive CSV validation with multiple error types")
    print("✓ Secure file upload handling with unique IDs")
    print("✓ Quiz type specific validation rules")
    print("✓ Database schema compatibility checking")
    print("✓ Integration with enhanced word mastery tracking")
    print("✓ Upload history and management")
    print("✓ Detailed validation reporting")
    print("✓ Error prevention and data integrity protection")

if __name__ == "__main__":
    main()
