"""Small script to initialize the database with demo users and import sample questions.
Run after creating the DB and applying schema.sql.
"""
import os
import csv
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv
import bcrypt

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost/vocab_app')

SAMPLE_CSV = 'sample_questions.csv'

# Demo users
DEMO_USERS = [
    ('testuser', 'user123', 'learner'),
    ('admin', 'admin123', 'admin')
]


def get_conn():
    return psycopg2.connect(DATABASE_URL)


def create_demo_users():
    conn = get_conn()
    cur = conn.cursor()
    for username, password, role in DEMO_USERS:
        pw_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        try:
            cur.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s) ON CONFLICT (username) DO NOTHING",
                (username, pw_hash, role)
            )
        except Exception as e:
            print('user insert error', e)
    conn.commit()
    cur.close()
    conn.close()
    print('Demo users created (if not existed)')


def import_sample_questions(csv_path=SAMPLE_CSV, admin_username='admin'):
    conn = get_conn()
    cur = conn.cursor()

    # get admin user id
    cur.execute('SELECT user_id FROM users WHERE username = %s', (admin_username,))
    row = cur.fetchone()
    if not row:
        print('Admin user not found; aborting import')
        cur.close()
        conn.close()
        return
    admin_id = row[0]

    # Read CSV and call insert_question_with_words
    with open(csv_path, newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        count = 0
        for r in reader:
            options = [o.strip() for o in r['options'].split(',')] if r.get('options') else []
            try:
                cur.execute("SELECT insert_question_with_words(%s, %s, %s, %s, %s)", (
                    r['question_text'], r['quiz_type'], r['correct_answer'], options, admin_id
                ))
                count += 1
            except Exception as e:
                print('error inserting question', e)
        conn.commit()
        print(f'Imported {count} questions')
    cur.close()
    conn.close()


if __name__ == '__main__':
    create_demo_users()
    if os.path.exists(SAMPLE_CSV):
        import_sample_questions()
    else:
        print(f'{SAMPLE_CSV} not found. To import sample questions, place the CSV at project root and run this script.')
