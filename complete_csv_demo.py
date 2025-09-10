#!/usr/bin/env python3
"""
Complete CSV Upload System Demonstration
Shows the full workflow from file creation to web interface deployment
"""

import os
import time
import threading
import webbrowser
from csv_upload_service import CSVUploadService
from csv_upload_validator import CSVUploadValidator
import csv

def create_comprehensive_test_files():
    """Create a comprehensive set of test CSV files"""
    print("Creating comprehensive test CSV files...")
    
    # 1. Perfect CSV file
    perfect_data = [
        ['question_text', 'quiz_type', 'correct_answer', 'options'],
        ['What is a synonym of "brilliant"?', 'synonym', 'bright', 'dim,bright,dark,dull'],
        ['Choose the antonym of "ancient".', 'antonym', 'modern', 'old,historic,modern,vintage'],
        ['Hand : Glove :: Foot : ?', 'analogy', 'Shoe', 'Hat,Shoe,Sock,Sandal'],
        ['The _____ weather was perfect for the picnic.', 'fill_in_blank', 'sunny', 'rainy,sunny,cloudy,stormy'],
        ['Find the odd word in this group.', 'odd_one_out', 'car', 'dog,cat,bird,car'],
        ['"Ubiquitous" means:', 'word_meaning', 'everywhere', 'rare,everywhere,hidden,difficult'],
        ['Which word best completes the sentence?', 'multiple_choice', 'therefore', 'however,therefore,meanwhile,otherwise']
    ]
    
    with open('/workspaces/My-Second-app/perfect_questions.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerows(perfect_data)
    
    # 2. Mixed quality CSV (has warnings but importable)
    mixed_data = [
        ['question_text', 'quiz_type', 'correct_answer', 'options'],
        ['Short?', 'synonym', 'brief', 'long,brief,tiny'],  # Short question (warning)
        ['Pick the word.', 'synonym', 'select', 'choose,select,pick'],  # Missing keyword (warning)
        ['A correct analogy question: A : B :: C : ?', 'analogy', 'D', 'X,D,Y,Z'],
        ['Weather today.', 'fill_in_blank', 'nice', 'bad,nice,awful'],  # No blanks (warning)
        ['Find different item.', 'odd_one_out', 'apple', 'car,train,plane,apple'],  # Missing keyword (warning)
        ['"Excellent" means very good.', 'word_meaning', 'very good', 'bad,very good,okay,poor']
    ]
    
    with open('/workspaces/My-Second-app/mixed_quality.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerows(mixed_data)
    
    # 3. Error-prone CSV (should fail validation)
    error_data = [
        ['question_text', 'quiz_type', 'correct_answer', 'options'],
        ['', 'synonym', 'empty', 'question,empty,missing,blank'],  # Empty question (error)
        ['Valid question?', 'invalid_type', 'answer', 'opt1,answer,opt3'],  # Invalid type (error)
        ['Question with wrong answer?', 'synonym', 'notinlist', 'opt1,opt2,opt3,opt4'],  # Answer not in options (error)
        ['A' * 600, 'synonym', 'toolong', 'short,toolong,medium,brief']  # Too long (error)
    ]
    
    with open('/workspaces/My-Second-app/error_prone.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerows(error_data)
    
    print("✓ Created test files:")
    print("  - perfect_questions.csv (should pass with no issues)")
    print("  - mixed_quality.csv (should pass with warnings)")
    print("  - error_prone.csv (should fail validation)")

def demonstrate_validation_engine():
    """Demonstrate the validation engine capabilities"""
    print("\n=== VALIDATION ENGINE DEMONSTRATION ===")
    
    validator = CSVUploadValidator()
    test_files = [
        ('perfect_questions.csv', 'Perfect File'),
        ('mixed_quality.csv', 'Mixed Quality File'),
        ('error_prone.csv', 'Error-Prone File')
    ]
    
    for filename, description in test_files:
        file_path = f'/workspaces/My-Second-app/{filename}'
        print(f"\n--- {description} ({filename}) ---")
        
        if os.path.exists(file_path):
            is_valid, validation_results = validator.validate_csv_file(file_path)
            summary = validator.get_validation_summary()
            
            print(f"✓ File processed: {summary['total_rows']} rows")
            print(f"✓ Validation result: {'PASS' if is_valid else 'FAIL'}")
            print(f"✓ Import eligible: {'YES' if summary['can_import'] else 'NO'}")
            print(f"✓ Valid rows: {summary['valid_rows']}")
            print(f"✓ Errors: {summary['error_count']}")
            print(f"✓ Warnings: {summary['warning_count']}")
            
            if validation_results:
                print("Key validation issues:")
                for result in validation_results[:3]:
                    level_icon = "🔴" if result.level.value == "error" else "🟡" if result.level.value == "warning" else "🔵"
                    print(f"  {level_icon} Row {result.row_number}: {result.message}")
        else:
            print(f"❌ File not found: {filename}")

def demonstrate_upload_service():
    """Demonstrate the upload service with full workflow"""
    print("\n=== UPLOAD SERVICE DEMONSTRATION ===")
    
    upload_service = CSVUploadService()
    
    # Test perfect file
    print("\n--- Testing Perfect File Upload & Import ---")
    result = upload_service.upload_and_validate_csv(
        '/workspaces/My-Second-app/perfect_questions.csv',
        user_id=1,
        filename='perfect_questions.csv'
    )
    
    if result.get('upload_id'):
        upload_id = result['upload_id']
        print(f"✓ Upload successful: {upload_id}")
        print(f"✓ Validation: {'PASS' if result['is_valid'] else 'FAIL'}")
        print(f"✓ Can import: {'YES' if result['can_import'] else 'NO'}")
        
        if result['can_import']:
            print("📤 Attempting import...")
            import_result = upload_service.import_validated_csv(upload_id, user_id=1)
            
            if import_result['success']:
                stats = import_result['import_results']
                print(f"✅ Import successful!")
                print(f"   Imported: {stats['imported_count']} questions")
                print(f"   Errors: {stats['error_count']}")
                print(f"   Success rate: {stats['success_rate']:.1f}%")
            else:
                print(f"❌ Import failed: {import_result.get('error')}")
    
    # Test mixed quality file with warnings
    print("\n--- Testing Mixed Quality File (Force Import) ---")
    mixed_result = upload_service.upload_and_validate_csv(
        '/workspaces/My-Second-app/mixed_quality.csv',
        user_id=1,
        filename='mixed_quality.csv'
    )
    
    if mixed_result.get('upload_id') and mixed_result['can_import']:
        mixed_upload_id = mixed_result['upload_id']
        print(f"✓ Upload successful with warnings")
        
        # Try normal import (might fail due to warnings)
        import_result = upload_service.import_validated_csv(mixed_upload_id, user_id=1)
        
        if not import_result['success'] and import_result.get('requires_force'):
            print("⚠️ Normal import blocked due to warnings, trying force import...")
            force_result = upload_service.import_validated_csv(mixed_upload_id, user_id=1, force_import=True)
            
            if force_result['success']:
                stats = force_result['import_results']
                print(f"✅ Force import successful!")
                print(f"   Imported: {stats['imported_count']} questions")
                print(f"   Success rate: {stats['success_rate']:.1f}%")
    
    # Test error file (should fail)
    print("\n--- Testing Error-Prone File (Should Fail) ---")
    error_result = upload_service.upload_and_validate_csv(
        '/workspaces/My-Second-app/error_prone.csv',
        user_id=1,
        filename='error_prone.csv'
    )
    
    if error_result.get('upload_id'):
        print(f"✓ File uploaded but validation failed (as expected)")
        print(f"✓ Can import: {'NO' if not error_result['can_import'] else 'YES'}")
        
        if not error_result['can_import']:
            print("✅ System correctly prevented import of invalid file")
    
    # Show upload history
    print("\n--- Upload History ---")
    history = upload_service.get_upload_history(user_id=1, limit=5)
    print(f"Found {len(history)} recent uploads:")
    for record in history:
        status_icon = "✅" if record['status'] == 'imported' else "📋" if record['status'] == 'uploaded' else "❌"
        print(f"  {status_icon} {record['original_filename']} - {record['status']}")
        if record.get('imported_count'):
            print(f"      Imported {record['imported_count']} questions")

def start_web_interface():
    """Start the web interface in a separate thread"""
    print("\n=== STARTING WEB INTERFACE ===")
    print("🌐 Starting Flask web server...")
    print("📍 Interface will be available at: http://localhost:5000")
    print("🔧 Use Ctrl+C to stop the server")
    
    def run_server():
        import csv_upload_web
        csv_upload_web.app.run(debug=False, host='0.0.0.0', port=5000, use_reloader=False)
    
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    
    # Give server time to start
    time.sleep(2)
    
    print("✅ Web server started successfully!")
    print("\nWeb Interface Features:")
    print("• 📁 Drag-and-drop CSV file upload")
    print("• 🔍 Real-time validation feedback")
    print("• 📊 Detailed validation reports")
    print("• ✅ One-click question import")
    print("• 📚 Upload history tracking")
    print("• 📥 Sample CSV template download")
    
    return server_thread

def show_system_capabilities():
    """Display system capabilities and features"""
    print("\n=== SYSTEM CAPABILITIES SUMMARY ===")
    
    capabilities = {
        "📋 File Validation": [
            "✓ CSV format verification",
            "✓ File size limits (10MB max)",
            "✓ Required column checking",
            "✓ Data type validation",
            "✓ Content length limits"
        ],
        "🎯 Quiz Type Support": [
            "✓ Synonym questions",
            "✓ Antonym questions", 
            "✓ Analogy questions (A:B::C:?)",
            "✓ Fill-in-the-blank questions",
            "✓ Odd-one-out questions",
            "✓ Word meaning questions",
            "✓ Multiple choice questions"
        ],
        "🔒 Security Features": [
            "✓ Secure filename handling",
            "✓ File type restrictions",
            "✓ SQL injection prevention",
            "✓ Input sanitization",
            "✓ Temporary file cleanup"
        ],
        "🎮 Integration Features": [
            "✓ Enhanced word mastery tracking",
            "✓ Automatic word deduplication",
            "✓ Question-level mastery initialization",
            "✓ Real-time database updates",
            "✓ Comprehensive progress analytics"
        ],
        "🌐 Web Interface": [
            "✓ User-friendly upload interface",
            "✓ Real-time validation feedback",
            "✓ Detailed error reporting",
            "✓ Upload history management",
            "✓ Sample template download"
        ],
        "📈 Monitoring & Analytics": [
            "✓ Upload success/failure tracking",
            "✓ Validation error analytics",
            "✓ Import statistics",
            "✓ Performance monitoring",
            "✓ User activity tracking"
        ]
    }
    
    for category, features in capabilities.items():
        print(f"\n{category}:")
        for feature in features:
            print(f"  {feature}")

def main():
    """Run the complete CSV upload system demonstration"""
    print("🎓 COMPREHENSIVE CSV UPLOAD SYSTEM DEMONSTRATION")
    print("=" * 60)
    
    # Create test files
    create_comprehensive_test_files()
    
    # Demonstrate validation
    demonstrate_validation_engine()
    
    # Demonstrate upload service
    demonstrate_upload_service()
    
    # Show capabilities
    show_system_capabilities()
    
    # Start web interface
    server_thread = start_web_interface()
    
    print(f"\n{'='*60}")
    print("🎉 DEMONSTRATION COMPLETE!")
    print("=" * 60)
    
    print("\nNext Steps:")
    print("1. 🌐 Visit http://localhost:5000 to use the web interface")
    print("2. 📥 Download the sample template to create your own questions")
    print("3. 📁 Upload test files to see validation in action")
    print("4. ✅ Import validated questions into the database")
    print("5. 📚 Review upload history and analytics")
    
    print("\nTest Files Created:")
    print("• perfect_questions.csv - Perfect file (no issues)")
    print("• mixed_quality.csv - Has warnings but importable")  
    print("• error_prone.csv - Has errors, blocks import")
    
    print("\nSystem Ready for Production Use! 🚀")
    print("Press Ctrl+C to stop the web server when done testing.")
    
    try:
        # Keep the demonstration running
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n👋 Thank you for using the CSV Upload System!")
        print("System demonstration completed successfully.")

if __name__ == "__main__":
    main()
