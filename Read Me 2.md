Design Document: CAT Vocabulary Learning Web Application
Version 1.0 • Prepared for Engineering & Product Teams

1. Overview
This document specifies a web-based vocabulary learning application tailored for CAT exam preparation. It provides user authentication, a personalized dashboard with vocabulary and word-mastery scores, quizzes built from a centralized question bank, and per-user word mastery tracking from 0–100%. The design targets a production-ready MVP with room for future scaling.
1.1 Goals
•	Teach and assess English vocabulary for CAT aspirants via multiple question formats.
•	Provide individualized mastery for each word (0–100%) and aggregate vocabulary metrics.
•	Support secure user accounts and dashboards with real-time progress and insights.
•	Generate 20-question quizzes with recent non-repetition (no repeats from the last 5 quiz attempts per user).
•	Ensure modular, scalable architecture with clear boundaries between shared content and per-user data.
1.2 Non-Goals (v1)
•	Mobile-native apps (responsive web UI will support mobile browsers).
•	Tutor chat or LLM-based hinting (future extension point).
•	Offline mode.
2. Personas & Use Cases
2.1 Personas
Student (Primary)	CAT aspirant who practices vocabulary daily, attempts quizzes, and tracks progress.
Content Curator (Secondary)	Internal role managing question bank and word metadata.
Admin (Secondary)	Operational role for user management, monitoring, and metrics.

2.2 Core Use Cases
1.	Sign up / log in and land on a personal dashboard.
2.	Attempt a 20-question quiz composed from multiple formats (antonym, synonym, fill in the blank, meaning, usage).
3.	View results instantly; update per-word mastery in the user database.
4.	Track overall vocabulary score and word-mastery distribution over time.
5.	Resume practice sessions and avoid question repetition across the last 5 quizzes.
3. High-Level Requirements
3.1 Functional Requirements
•	User authentication (email/password; optional OAuth v2 in future).
•	User dashboard showing: Overall Vocabulary Score (aggregate) and Word Mastery (per-word, 0–100%).
•	Question bank stored in a common database shared by all users.
•	Per-user database tracking per-word mastery, quiz history, and preferences.
•	Quiz generation logic: 20 questions; avoid repeating exact questions seen in the last 5 quizzes for that user.
•	Question formats supported: antonym, synonym, fill in the blank, word meaning, usage in sentence.
•	Result evaluation, scoring, and mastery update after each quiz.
•	Basic admin capabilities to ingest/update question bank (v1 can be SQL or CSV import).
3.2 Non-Functional Requirements
Availability	99.5%+ quarterly target.
Latency	P95 < 300ms for API reads; < 600ms for quiz generation.
Scale	10k DAU with burst to 100 RPS (read-heavy).
Security	JWT auth, hashed passwords (bcrypt/argon2), RBAC.
Observability	Structured logs, metrics, request tracing, error tracking.
Accessibility	WCAG 2.1 AA where feasible for web UI.

4. System Architecture
A modular web architecture separates concerns across client, API, and databases. The common database hosts the global question bank; the per-user database stores user-specific mastery and quiz history.
4.1 Proposed Stack (Opinionated; replace as needed)
Frontend	React + TypeScript (Next.js optional), TailwindCSS for styling.
Backend	Node.js (NestJS/Express) or Python (FastAPI) with REST APIs.
Databases	PostgreSQL (two logical schemas or two DBs: common & user).
Auth	JWT, refresh tokens, secure cookie storage for refresh.
Hosting	Cloud PaaS (e.g., Render/Heroku/AWS Elastic Beanstalk) + managed Postgres.
Cache (opt.)	Redis for session blacklists and quiz generation caching.

4.2 Component Responsibilities
•	Web Client: login/logout, dashboard, quiz player UI, results, analytics.
•	API Gateway/Service: authentication, quiz generation, scoring, mastery updates, dashboards, admin ingest.
•	Common DB: words, definitions, metadata, question bank.
•	User DB: users, per-word mastery, quiz attempts, attempt items, recent history index.
5. Data Model
Two database contexts are defined: Common (global) and Per-User. PostgreSQL shown below; adapt as needed.
5.1 Common Database (Question Bank) — Tables
words
word_id (PK, UUID)
lemma (text, unique)
part_of_speech (text)
frequency_rank (int, nullable)
definitions (jsonb)
examples (jsonb)
created_at (timestamptz)
updated_at (timestamptz)
questions
question_id (PK, UUID)
word_id (FK -> words.word_id)
format (enum: ANTONYM,SYNONYM,FITB,MEANING,USAGE)
prompt (text)
choices (jsonb)
answer_key (text or jsonb)
explanation (text, nullable)
difficulty (int 1–5)
source (text, nullable)
created_at (timestamptz)
updated_at (timestamptz)
question_tags
question_id (FK -> questions.question_id)
tag (text)
PRIMARY KEY (question_id, tag)
5.2 Per-User Database — Tables
users
user_id (PK, UUID)
email (citext unique)
password_hash (text)
name (text)
created_at (timestamptz)
updated_at (timestamptz)
role (enum: STUDENT,ADMIN)
user_word_mastery
user_id (FK -> users.user_id)
word_id (FK -> common.words.word_id)
mastery (numeric(5,2) % between 0 and 100)
evidence_counts (jsonb: {ANTONYM:int,SYNONYM:int,FITB:int,MEANING:int,USAGE:int})
last_seen_at (timestamptz)
PRIMARY KEY (user_id, word_id)
quiz_attempts
attempt_id (PK, UUID)
user_id (FK -> users.user_id)
created_at (timestamptz)
score_raw (int)
score_pct (numeric(5,2))
question_count (int default 20)
quiz_attempt_items
attempt_item_id (PK, UUID)
attempt_id (FK -> quiz_attempts.attempt_id)
question_id (FK -> common.questions.question_id)
word_id (FK -> common.words.word_id)
user_answer (text)
result (enum: CORRECT,INCORRECT)
time_taken_ms (int)
recent_question_window
user_id (FK -> users.user_id)
question_id (FK -> common.questions.question_id)
last_seen_attempt_id (FK -> quiz_attempts.attempt_id)
last_seen_at (timestamptz)
PRIMARY KEY (user_id, question_id)  -- supports non-repetition rule
6. Mastery Model
Mastery is defined per word on a 0–100% scale. It aggregates performance across formats; if a student answers all supported formats for a word correctly (within recent assessment), mastery reaches 100%. Mastery decays slowly over time to encourage spaced review.
6.1 Format Weights
ANTONYM	0.20
SYNONYM	0.20
FITB	0.25
MEANING	0.20
USAGE	0.15

Weights can be tuned. A format contributes fully when the last K (default 3) interactions for that format on the word are correct; partial credit is awarded otherwise.
6.2 Mastery Calculation (Pseudocode)
Inputs:
- For a given (user, word), the last N=10 interactions across formats and per-format streaks.
- Weights W_f per format f.
- Time since last correct per format.

Pseudocode:
let mastery = 0
for each format f in {ANTONYM,SYNONYM,FITB,MEANING,USAGE}:
    score_f = clamp( (correct_streak_f / K), 0, 1 )  # K=3 correct answers recent
    # Optional recency decay (half-life 45 days)
    decay = exp( - ln(2) * days_since_last_seen / 45 )
    contrib_f = W_f * score_f * decay
    mastery += contrib_f
mastery_pct = round(mastery * 100, 2)
if all formats fully mastered in last window -> mastery_pct = 100.00

6.3 Update Rules After a Quiz Item
•	On CORRECT: increment evidence_counts[format] and update streak; update last_seen_at; recompute mastery.
•	On INCORRECT: reset streak for format; optionally reduce mastery via negative evidence; recompute.
•	Clamp mastery to [0, 100].
7. Quiz Generation & Non-Repetition
7.1 Constraints
•	Exactly 20 questions per quiz.
•	Diverse mix of formats (configurable target distribution e.g., [5,5,4,3,3]).
•	No question appears if used in the last 5 quiz attempts by the same user.
•	Respect difficulty band distribution (e.g., 40% easy, 40% medium, 20% hard).
7.2 Algorithm (Pseudocode)
Inputs: user_id, target_count=20, format_mix, difficulty_mix.

1) Build exclusion set E = { question_id | (user_id, question_id) exists in recent_question_window AND count of distinct recent attempts ≤ 5 }.
2) Candidate pool C = SELECT * FROM questions WHERE question_id NOT IN E AND active=true.
3) Apply balancing: stratify C by format and difficulty; sample without replacement per bucket until 20 picked.
4) If insufficient in a bucket, backfill from nearest difficulty/any format.
5) Persist quiz_attempts row; persist quiz_attempt_items with selected question_ids.
6) Update recent_question_window with chosen questions (evict entries older than 5 attempts for that user).
7.3 SQL Sketches
-- Exclusion set (last 5 attempts for user)
WITH last5 AS (
  SELECT attempt_id
  FROM quiz_attempts
  WHERE user_id = :user_id
  ORDER BY created_at DESC
  LIMIT 5
), used AS (
  SELECT DISTINCT question_id
  FROM quiz_attempt_items
  WHERE attempt_id IN (SELECT attempt_id FROM last5)
)
SELECT q.* FROM questions q
LEFT JOIN used u ON u.question_id = q.question_id
WHERE u.question_id IS NULL;
8. API Design
8.1 Authentication
POST /auth/signup	Body: {email, password, name}. Returns: {user, tokens}. Email unique.

POST /auth/login	Body: {email, password}. Returns: {user, tokens}. Rate-limit brute force.

POST /auth/refresh	Body: {refresh_token}. Returns: {access_token}.

POST /auth/logout	Invalidate refresh token (server-side blacklist if used).

8.2 Quiz & Results
GET /quiz/new	Query: mix params (optional). Returns: {attempt_id, questions[...20]} without answers.

POST /quiz/{attempt_id}/submit	Body: {answers[]} -> Returns: {score_raw, score_pct, per_item_results}. Updates mastery.

GET /quiz/{attempt_id}	Return attempt summary and breakdown.

8.3 Dashboard & Mastery
GET /dashboard	Returns: {overall_vocab_score, mastery_distribution, recent_activity, streaks}

GET /words/{word_id}/mastery	Returns: {mastery_pct, evidence_counts, last_seen_at, history[]}

8.4 Admin (v1 minimal)
POST /admin/questions/import	CSV/JSON import. Admin only.

POST /admin/questions	Create question.

PUT /admin/questions/{id}	Update question.

DELETE /admin/questions/{id}	Soft-delete or archive.

9. Security & Privacy
•	Password hashing with argon2id or bcrypt (cost tuned).
•	JWT access tokens (short TTL, e.g., 15m); refresh tokens (httpOnly secure cookies, 7–30 days).
•	RBAC roles: STUDENT, ADMIN.
•	PII minimization (email, name). No sensitive data in logs.
•	Rate limiting on auth endpoints; captcha after repeated failures.
•	Database row-level ownership enforced on user data.
10. Dashboard Metrics & Scoring
Overall Vocabulary Score	Weighted aggregation over mastered words: mean of mastery_pct across active word set.
Mastery Distribution	Histogram buckets: [0–20, 20–40, 40–60, 60–80, 80–100].
Recent Activity	Quizzes taken, time on task, accuracy by format.
Weak Areas	Lowest average mastery by format and by POS.

11. UI/UX Wireframe Notes (Textual)
•	Login/Signup page with email/password fields and password rules inline validation.
•	Dashboard with two hero cards: Overall Vocabulary Score and Word Mastery, plus charts of progress.
•	Quiz Player: progress bar (1/20), timer (optional), single-question view, next/prev within attempt (locked after submit).
•	Results Page: overall score, per-format accuracy, word list with mastery deltas, explanations.
12. Telemetry & Observability
•	Structured logs with request IDs; audit trail for admin changes.
•	Metrics: request latency, error rates, quiz generation time, questions per format served.
•	Events: quiz_started, question_answered, quiz_submitted, mastery_updated.
13. Testing Strategy
•	Unit tests for mastery update logic and quiz generator sampling/constraints.
•	Integration tests for API endpoints and DB interactions.
•	Load tests for quiz generation and dashboard endpoints.
•	Security tests: auth, RLS, SQL injection, permission checks.
14. Deployment & Environments
Environments	dev, staging, prod
Migrations	Use Alembic (FastAPI/Python) or Prisma/TypeORM (Node)
CI/CD	Automated tests, lint, migrations, blue/green deploys

15. Risks & Mitigations
•	Data skew in question formats → enforce format quotas in sampling.
•	Question leakage/repetition → maintain recent_question_window and enforce last-5 constraint.
•	Mastery inflation → use decay and require per-format streaks.
16. Future Enhancements
•	Spaced repetition scheduling & notifications.
•	Adaptive difficulty based on mastery slope.
•	Hints/explanations powered by LLM (guardrails).
•	Gamification: streaks, badges, leaderboards (opt-in).
Appendix A: Example Question JSON Schemas
A.1 Question Object (Common DB)
{
  "question_id": "uuid",
  "word_id": "uuid",
  "format": "ANTONYM|SYNONYM|FITB|MEANING|USAGE",
  "prompt": "text",
  "choices": ["A","B","C","D"],
  "answer_key": "A",
  "explanation": "text",
  "difficulty": 3,
  "tags": ["CAT","vocabulary"]
}
A.2 Submission Payload
{
  "attempt_id": "uuid",
  "answers": [
     {"question_id": "uuid", "answer": "A"},
     ... (20)
  ]
}
