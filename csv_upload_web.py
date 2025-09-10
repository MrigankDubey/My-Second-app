#!/usr/bin/env python3
"""
Flask Web Interface for CSV Upload System
Provides a user-friendly web interface for uploading and validating CSV files
"""

import os
import json
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, send_file
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge
from csv_upload_service import CSVUploadService
from csv_upload_validator import ValidationLevel
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB max file size

# Initialize upload service
upload_service = CSVUploadService()

@app.route('/')
def index():
    """Main upload page"""
    return render_template('csv_upload.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle file upload and validation"""
    try:
        # Check if file was uploaded
        if 'csv_file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['csv_file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Validate file type
        if not file.filename.lower().endswith('.csv'):
            return jsonify({'error': 'File must be a CSV file'}), 400
        
        # Get user ID (in real app, get from session/auth)
        user_id = request.form.get('user_id', 1, type=int)
        
        # Save uploaded file temporarily
        filename = secure_filename(file.filename)
        temp_path = f'/tmp/{filename}'
        file.save(temp_path)
        
        # Upload and validate
        result = upload_service.upload_and_validate_csv(
            temp_path, user_id, filename
        )
        
        # Clean up temp file
        if os.path.exists(temp_path):
            os.remove(temp_path)
        
        if result.get('upload_id'):
            return jsonify({
                'success': True,
                'upload_id': result['upload_id'],
                'is_valid': result['is_valid'],
                'can_import': result['can_import'],
                'validation_summary': result['validation_summary'],
                'validation_report': result['validation_report']
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', 'Upload failed')
            }), 400
            
    except RequestEntityTooLarge:
        return jsonify({'error': 'File too large (max 10MB)'}), 413
    except Exception as e:
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500

@app.route('/import/<upload_id>', methods=['POST'])
def import_csv(upload_id):
    """Import a validated CSV file"""
    try:
        user_id = request.json.get('user_id', 1)
        force_import = request.json.get('force_import', False)
        
        result = upload_service.import_validated_csv(
            upload_id, user_id, force_import
        )
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/history/<int:user_id>')
def upload_history(user_id):
    """Get upload history for a user"""
    try:
        history = upload_service.get_upload_history(user_id, limit=50)
        return jsonify({'history': history})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/download/sample')
def download_sample():
    """Download a sample CSV template"""
    sample_content = '''question_text,quiz_type,correct_answer,options
"What is a synonym of 'happy'?",synonym,joyful,"sad,joyful,angry,tired"
"Choose the antonym of 'bright'.",antonym,dim,"brilliant,dim,shiny,clear"
"Hand : Glove :: Foot : ?",analogy,Shoe,"Hat,Shoe,Sock,Sandal"
"The _____ weather was perfect.",fill_in_blank,sunny,"rainy,sunny,cloudy,stormy"
"Find the odd word.",odd_one_out,car,"dog,cat,bird,car"
"'Ubiquitous' means:",word_meaning,everywhere,"rare,everywhere,hidden,difficult"'''
    
    # Save sample file
    sample_path = '/tmp/sample_questions_template.csv'
    with open(sample_path, 'w', encoding='utf-8') as f:
        f.write(sample_content)
    
    return send_file(sample_path, as_attachment=True, download_name='sample_questions_template.csv')

@app.errorhandler(413)
def too_large(e):
    return jsonify({'error': 'File too large (max 10MB)'}), 413

if __name__ == '__main__':
    # Create templates directory if it doesn't exist
    os.makedirs('templates', exist_ok=True)
    
    app.run(debug=True, host='0.0.0.0', port=5000)
