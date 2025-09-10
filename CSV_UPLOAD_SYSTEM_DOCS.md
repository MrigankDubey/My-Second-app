# CSV Upload System Documentation

## Overview

The CSV Upload System provides a comprehensive solution for uploading, validating, and importing vocabulary questions from CSV files. It includes robust validation checks to prevent incompatible entries and ensures data integrity throughout the import process.

## System Components

### 1. CSV Upload Validator (`csv_upload_validator.py`)
- **Purpose**: Comprehensive validation engine for CSV files
- **Features**: 
  - File format validation
  - Structure validation
  - Content validation
  - Quiz type-specific validation
  - Database compatibility checking

### 2. CSV Upload Service (`csv_upload_service.py`)
- **Purpose**: Handles file uploads, validation orchestration, and database import
- **Features**:
  - Secure file handling
  - Upload tracking and history
  - Integration with enhanced word mastery system
  - Error handling and recovery

### 3. Web Interface (`csv_upload_web.py` + `templates/csv_upload.html`)
- **Purpose**: User-friendly web interface for file uploads
- **Features**:
  - Drag-and-drop file upload
  - Real-time validation feedback
  - Import progress tracking
  - Upload history management

## Validation Rules

### File-Level Validation
- **File Format**: Must be a valid CSV file (.csv extension)
- **File Size**: Maximum 10MB
- **Encoding**: UTF-8 encoding support
- **Structure**: Must contain required columns

### Column Validation
#### Required Columns
- `question_text`: The question content
- `quiz_type`: Type of question (see supported types below)
- `correct_answer`: The correct answer

#### Optional Columns
- `options`: Comma-separated list of answer choices
- `difficulty`: Question difficulty level
- `category`: Question category
- `explanation`: Answer explanation

### Content Validation
#### Question Text
- **Maximum Length**: 500 characters
- **Minimum Length**: 10 characters (warning if shorter)
- **Required**: Must not be empty

#### Quiz Type
- **Supported Types**: 
  - `synonym` - Find words with similar meaning
  - `antonym` - Find words with opposite meaning
  - `analogy` - Complete word relationships (A : B :: C : ?)
  - `fill_in_blank` - Complete sentences with missing words
  - `odd_one_out` - Find the word that doesn't belong
  - `word_meaning` - Define vocabulary words
  - `multiple_choice` - General multiple choice questions

#### Correct Answer
- **Maximum Length**: 200 characters
- **Must Be Present**: In options list (if options provided)
- **Required**: Must not be empty

#### Options
- **Format**: Comma-separated values
- **Count**: 2-6 options recommended
- **Length**: Each option max 100 characters
- **Validation**: Correct answer must be included

### Quiz Type-Specific Validation

#### Synonym Questions
- Should mention keywords: 'synonym', 'similar', 'same meaning'
- Warning if keywords not found

#### Antonym Questions
- Should mention keywords: 'antonym', 'opposite', 'contrary'
- Warning if keywords not found

#### Analogy Questions
- Should use format: 'A : B :: C : ?'
- Should contain '::' and appropriate colons
- Warning if format not detected

#### Fill in Blank Questions
- Should contain blanks: '_____', '____', '___', '__', '_'
- Warning if no blanks detected

#### Odd One Out Questions
- Should mention keywords: 'odd', 'different', 'does not belong'
- Warning if keywords not found

## Database Integration

### Schema Requirements
The system requires the enhanced word mastery schema with:
- `questions` table
- `words` table
- `word_question_map` table
- `word_question_mastery` table
- `add_question_with_mastery_tracking()` function

### Import Process
1. **Validation**: File passes all validation checks
2. **Word Extraction**: Extract words from questions and answers
3. **Deduplication**: Prevent duplicate words in database
4. **Question Import**: Use enhanced import function
5. **Mastery Initialization**: Automatic mastery tracking setup
6. **Relationship Mapping**: Link words to questions

## Usage Examples

### Basic CSV Format
```csv
question_text,quiz_type,correct_answer,options
"What is a synonym of 'happy'?",synonym,joyful,"sad,joyful,angry,tired"
"Choose the antonym of 'bright'.",antonym,dim,"brilliant,dim,shiny,clear"
"Hand : Glove :: Foot : ?",analogy,Shoe,"Hat,Shoe,Sock,Sandal"
```

### Python Usage
```python
from csv_upload_service import CSVUploadService

# Initialize service
upload_service = CSVUploadService()

# Upload and validate
result = upload_service.upload_and_validate_csv(
    file_path='/path/to/questions.csv',
    user_id=1,
    filename='questions.csv'
)

if result['can_import']:
    # Import the file
    import_result = upload_service.import_validated_csv(
        result['upload_id'],
        user_id=1
    )
    print(f"Imported {import_result['import_results']['imported_count']} questions")
```

### Web Interface Usage
1. **Access Interface**: Navigate to the web application
2. **Upload File**: Click "Choose File" and select CSV
3. **Review Validation**: Check validation results and errors/warnings
4. **Import**: Click "Import Questions" if validation passes
5. **Monitor Progress**: View import statistics and results

## Validation Error Types

### Error Level (Blocks Import)
- Empty required fields
- Invalid quiz types
- Correct answer not in options
- Text length exceeded
- Invalid file format
- Database schema issues

### Warning Level (Allows Import)
- Very short question text
- Missing quiz type keywords
- Unusual option counts
- Large file sizes
- Minor formatting issues

### Info Level (Informational)
- File statistics
- Processing notes
- Performance recommendations

## Error Handling

### File Upload Errors
- File too large (>10MB)
- Invalid file format
- File corruption
- Network issues

### Validation Errors
- Missing required columns
- Invalid data types
- Content validation failures
- Database connectivity issues

### Import Errors
- Database constraint violations
- Transaction failures
- Resource limitations
- Permission issues

## Security Features

### File Handling Security
- **Secure Filenames**: Uses Werkzeug's secure_filename()
- **File Type Validation**: Restricts to CSV files only
- **Size Limits**: Prevents large file attacks
- **Temporary Storage**: Uses secure temporary directories
- **Cleanup**: Automatic file cleanup after processing

### Input Validation
- **SQL Injection Prevention**: Uses parameterized queries
- **Content Sanitization**: Validates all input data
- **Type Checking**: Enforces data types
- **Length Limits**: Prevents buffer overflow attacks

## Performance Considerations

### File Processing
- **Streaming**: Large files processed in chunks
- **Memory Management**: Efficient memory usage
- **Indexing**: Database optimizations for import speed
- **Batch Processing**: Bulk insert operations

### Scalability
- **Async Processing**: Background import jobs (future enhancement)
- **Queue System**: Job queue for large imports (future enhancement)
- **Caching**: Validation result caching
- **Resource Limits**: Configurable processing limits

## Monitoring and Logging

### Upload Tracking
- Complete upload history
- Validation results storage
- Import statistics
- Error logging

### Analytics
- Success/failure rates
- Common validation errors
- Performance metrics
- Usage patterns

## Configuration

### Environment Variables
```bash
DATABASE_URL=postgresql://postgres:postgres@localhost/vocab_app
SECRET_KEY=your-secret-key-here
MAX_UPLOAD_SIZE=10485760  # 10MB in bytes
UPLOAD_FOLDER=/path/to/uploads
```

### Customization Options
- Validation rule modifications
- File size limits
- Supported quiz types
- Error message customization

## Maintenance

### Regular Tasks
- **Cleanup**: Remove old upload files (configurable retention)
- **Monitoring**: Check error rates and performance
- **Updates**: Keep validation rules current
- **Backups**: Regular database backups

### Troubleshooting
1. **Validation Failures**: Check validation report details
2. **Import Errors**: Review database logs and constraints
3. **Performance Issues**: Monitor file sizes and processing times
4. **Database Issues**: Verify schema and function availability

## Future Enhancements

### Planned Features
- **Async Processing**: Background job processing for large files
- **Advanced Analytics**: Detailed import statistics and trends
- **User Management**: Role-based access control
- **API Endpoints**: RESTful API for programmatic access
- **Bulk Operations**: Multiple file upload support
- **Template Management**: Custom question templates

### Integration Opportunities
- **LMS Integration**: Connect with learning management systems
- **External APIs**: Question bank integrations
- **Export Features**: Export questions to various formats
- **Collaboration**: Multi-user editing and review workflows

## Support and Documentation

### Getting Help
- Review validation reports for specific error details
- Check database schema requirements
- Verify file format compliance
- Contact system administrators for database issues

### Best Practices
- Use the provided CSV template
- Test with small files first
- Review validation warnings before import
- Keep regular backups of question databases
- Monitor upload history for patterns

---

**Note**: This documentation covers the comprehensive CSV upload system with validation, security, and integration features. For specific technical issues, refer to the validation reports and error messages provided by the system.
