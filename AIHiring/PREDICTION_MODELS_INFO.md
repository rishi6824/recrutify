# AI Hiring - Prediction Models Complete Information

## 📋 Project Overview
**AI-Powered Interview & Hiring System** - A Flask-based web application that uses multiple prediction models to evaluate candidates through interviews, resume analysis, and skill assessments.

---

## 🤖 Prediction Models

### 1. **AIInterviewer Model** 
**File:** `models/ai_interviewer.py`

#### Purpose
- Evaluates candidate answers to interview questions
- Generates dynamic feedback
- Calculates interview performance scores

#### Input Data
- Job role (e.g., 'software_engineer', 'data_scientist')
- Question index
- Candidate answer (text)
- Resume analysis (optional)

#### Prediction Outputs
1. **Score** (0-10 scale): Overall answer quality
2. **Feedback** (string): Personalized guidance
3. **Analysis** (dict): Word count, sentence count

#### Scoring Algorithm

**Step 1: Keyword Matching Score**
```
keyword_score = (keywords_found / total_keywords) × 6
Max: 6 points
```
- Checks if answer contains expected keywords
- Case-insensitive matching

**Step 2: Answer Length Score**
```
length_score = min(4, word_count / 25)
Max: 4 points
```
- Encourages detailed, comprehensive answers
- 25 words = 1 point

**Step 3: Total Score**
```
total_score = min(10, keyword_score + length_score)
Range: 0.0 - 10.0 (rounded to 0.1)
```

#### Feedback Tiers
| Score Range | Feedback |
|-------------|----------|
| ≥ 8.0 | "Excellent answer! You covered the key points clearly and thoroughly." |
| 6.0 - 7.9 | "Good answer. You mentioned some relevant points but could add more detail." |
| 4.0 - 5.9 | "Average answer. Consider providing more specific examples and details." |
| < 4.0 | "Try to include concepts like: [missing keywords]" |

#### Question Database
**Default Questions Format:**
```python
{
    "job_role": [
        {
            "question": "Question text",
            "type": "technical|behavioral",
            "keywords": ["keyword1", "keyword2", ...]
        }
    ]
}
```

**Built-in Questions:**
- **Software Engineer** (3 questions)
  - OOP principles
  - Problem-solving approach
  - Code quality & testing
- **Data Scientist** (2 questions)
  - Supervised vs unsupervised learning
  - Handling missing data

#### Methods
- `get_questions(job_role)` - Retrieve questions for a role
- `analyze_answer(job_role, question_index, answer)` - Score an answer
- `_calculate_score()` - Internal scoring logic
- `_generate_feedback()` - Create personalized feedback
- `generate_overall_feedback()` - Aggregate performance

---

### 2. **ResumeAnalyzer Model**
**File:** `models/resume_analyzer.py`

#### Purpose
- Parse resumes in multiple formats
- Extract skills, experience, and education
- Calculate resume quality scores
- Generate improvement recommendations

#### Input Data
- Resume file (PDF, DOCX, or TXT)
- Resume text content

#### Supported File Formats
- **.pdf** - PyPDF2 based extraction
- **.docx** - python-docx based extraction
- **.txt** - Plain text reading

#### Prediction Outputs

**1. Skills Analysis**
```python
{
    "programming": ["Python", "Java", "JavaScript", ...],
    "web_tech": ["React", "Django", "Flask", ...],
    "databases": ["MySQL", "PostgreSQL", "MongoDB", ...],
    "cloud": ["AWS", "Azure", "Docker", "Kubernetes", ...],
    "data_science": ["Pandas", "TensorFlow", "Scikit-learn", ...],
    "soft_skills": ["Communication", "Leadership", "Teamwork", ...]
}
```

**2. Experience Extraction**
```python
{
    "years": "5"  # Extracted from resume or "Not specified"
}
```

**3. Education Extraction**
```python
{
    "degrees": ["Bachelor", "Master", "MBA", ...]
}
```

**4. Scoring System**

| Component | Calculation | Max Points |
|-----------|-------------|-----------|
| **Skills Score** | (total_skills / 2) | 10 |
| **Experience Score** | Based on years mentioned | 10 |
| **Education Score** | (degrees_count × 3) | 10 |
| **Overall Score** | (Skills + Experience + Education) / 3 | 10 |

**Formulas:**
```
skills_score = min(10, total_skills_found / 2)
experience_score = min(10, 5) if years found
education_score = min(10, degrees_count × 3)
overall_score = (skills + experience + education) / 3
```

#### Skill Categories (6 Categories, 34 Skills)

| Category | Skills |
|----------|--------|
| **Programming** (9) | Python, Java, JavaScript, C++, C#, Ruby, PHP, Swift, Kotlin |
| **Web Technologies** (9) | HTML, CSS, React, Angular, Vue, Django, Flask, Node.js, Express |
| **Databases** (6) | MySQL, PostgreSQL, MongoDB, Redis, SQLite, Oracle |
| **Cloud & DevOps** (6) | AWS, Azure, GCP, Docker, Kubernetes, Terraform, Jenkins |
| **Data Science** (6) | Pandas, NumPy, TensorFlow, PyTorch, Scikit-learn, R, Matplotlib |
| **Soft Skills** (6) | Communication, Leadership, Teamwork, Problem-solving, Creativity, Adaptability |

#### Recommendations Engine
Generated based on analysis results:

| Condition | Recommendation |
|-----------|-----------------|
| Skills Score < 6 | "Consider adding more technical skills to your resume" |
| Experience Score < 5 | "Highlight your work experience with specific achievements" |
| Word Count < 200 | "Your resume seems brief. Consider adding more details" |
| All scores good | "Your resume looks strong! Focus on behavioral questions" |

#### Methods
- `parse_resume(file_path)` - Parse resume file
- `analyze_resume_file(file_path)` - Full file analysis
- `analyze_resume_text(text)` - Text-based analysis
- `_extract_skills()` - Skill extraction
- `_extract_experience()` - Experience parsing
- `_extract_education()` - Education detection
- `_calculate_scores()` - Score computation
- `_generate_recommendations()` - Improvement suggestions

---

### 3. **QuestionGenerator Model**
**File:** `models/question_generator.py`

#### Purpose
- Generate interview questions based on job role
- Categorize questions by type and difficulty
- Personalize questions based on resume analysis

#### Input Data
- Job role (e.g., 'software_engineer', 'data_scientist')
- Resume analysis (dict)
- Number of questions (default: 3)

#### Question Database Structure
```python
{
    "job_role": [
        {
            "question": "Question text",
            "type": "technical|behavioral",
            "difficulty": "easy|medium|hard"
        }
    ]
}
```

#### Built-in Questions

**Software Engineer (3 questions)**
| # | Question | Type | Difficulty |
|---|----------|------|-----------|
| 1 | "Explain your experience with OOP" | Technical | Medium |
| 2 | "Describe time you debugged a complex issue" | Behavioral | Medium |
| 3 | "How do you handle code reviews?" | Behavioral | Easy |

**Data Scientist (2 questions)**
| # | Question | Type | Difficulty |
|---|----------|------|-----------|
| 1 | "Explain supervised vs unsupervised learning" | Technical | Medium |
| 2 | "How do you validate ML models?" | Technical | Hard |

#### Output
- Question list filtered by role
- Max 3 questions per default
- Customizable count

#### Methods
- `generate_questions(job_role, resume_analysis, num_questions=3)` - Main prediction method

---

### 4. **InterviewChatbot Model**
**File:** `models/chatbot.py`

#### Purpose
- Provide interview coaching and guidance
- Answer user queries about interview preparation
- Pattern-based conversational AI

#### Prediction Type
**Pattern Matching Classification** - Categorizes user input and returns relevant advice

#### Input Data
- User query (text)

#### Response Categories (6 Categories)

| Category | Triggers | Sample Response Count |
|----------|----------|----------------------|
| **Greeting** | hello, hi, hey, greetings | 3 responses |
| **Interview Tips** | tip, advice, suggest, how to | 5 responses |
| **Technical Interview** | technical, code, programming, algorithm | 5 responses |
| **Salary Negotiation** | salary, pay, compensation, money | 5 responses |
| **Behavioral Questions** | behavioral, experience, story, situation | 5 responses |
| **Fallback** | Unknown queries | 4 responses |

#### Sample Responses
```
Technical Interview Examples:
- "Practice coding on LeetCode or HackerRank"
- "Explain your thought process out loud"
- "Focus on clean, efficient code"
- "Review data structures and algorithms"
- "Discuss projects in detail"

Behavioral Examples:
- "Prepare 3-5 stories from your experience"
- "Use STAR method: Situation, Task, Action, Result"
- "Be specific about your role and contributions"
```

#### Methods
- `get_response(user_input)` - Main prediction method
- Returns random response from matched category

---

### 5. **SpeechProcessor Model**
**File:** `models/speech_processor.py`

#### Purpose
- Convert speech to text (framework)
- Audio processing capabilities

#### Status
⚠️ **Currently Placeholder** - Ready for implementation

#### Planned Features
- Speech-to-text conversion
- Audio file processing
- Real-time transcription

---

## 🎯 Overall Prediction Pipeline

```
Resume Upload
    ↓
ResumeAnalyzer
(Skills, Experience, Education Analysis)
    ↓
Select Job Role
    ↓
QuestionGenerator
(Generate role-specific questions)
    ↓
Interview Session
(Candidate answers questions)
    ↓
AIInterviewer
(Score each answer 0-10)
    ↓
Results Aggregation
(Average score, overall feedback)
    ↓
Generate Report
(Detailed analysis & recommendations)
```

---

## 📊 Scoring Summary

### Answer Scoring (AIInterviewer)
- **Range:** 0.0 - 10.0
- **Components:**
  - Keyword coverage: 0-6 points
  - Answer length: 0-4 points
- **Feedback Levels:** 4 tiers based on score

### Resume Scoring (ResumeAnalyzer)
- **Skills Score:** 0-10 (based on skills found)
- **Experience Score:** 0-10 (based on years)
- **Education Score:** 0-10 (based on degrees)
- **Overall Score:** Average of three components

### Overall Interview Score (App)
```
Interview Score = (Sum of all answer scores) / (Number of questions × 10) × 100
Range: 0% - 100%
```

---

## 💾 Configuration

**File:** `config.py`

```python
SECRET_KEY = 'your-secret-key-here'
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
MAX_QUESTIONS = 10
QUESTION_TIME_LIMIT = 180  # 3 minutes
CHATBOT_NAME = "InterviewBot"
MAX_CHAT_HISTORY = 20
```

---

## 📦 Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| Flask | 2.3.3 | Web framework |
| NLTK | 3.8.1 | Text tokenization |
| TextBlob | 0.17.1 | Text analysis |
| python-docx | 0.8.11 | DOCX parsing |
| PyPDF2 | 3.0.1 | PDF parsing |
| werkzeug | 2.3.7 | WSGI utilities |
| SpeechRecognition | 3.10.0 | Audio input |
| PyAudio | 0.2.11 | Audio processing |
| textstat | 0.7.3 | Text readability |
| scikit-learn | 1.3.0 | ML utilities |
| pandas | 2.0.3 | Data analysis |
| numpy | 1.24.3 | Numerical computing |

---

## 🔧 How Models Are Used

### In Main Application (`app.py`)

1. **Resume Analysis Route**
   ```python
   resume_analyzer.analyze_resume_file(filepath)
   → Returns: skills, experience, education, scores, recommendations
   ```

2. **Start Interview Route**
   ```python
   question_generator.generate_questions(job_role, resume_analysis)
   → Returns: list of questions
   ```

3. **Submit Answer Route**
   ```python
   ai_interviewer.analyze_answer(job_role, question_index, answer)
   → Returns: score, feedback, analysis
   ```

4. **Results Route**
   ```python
   ai_interviewer.generate_overall_feedback(responses, resume_analysis)
   → Returns: aggregated performance feedback
   ```

---

## 🎓 Key Insights

### Strengths
✅ Multi-dimensional evaluation (skills + answers + experience)
✅ Flexible scoring system (keyword + length based)
✅ Resume parsing from multiple formats
✅ Personalized feedback generation
✅ Role-specific question generation

### Current Limitations
⚠️ Keyword matching is case-insensitive but exact phrase matching
⚠️ No semantic analysis of answer meaning
⚠️ Chatbot uses pattern matching (not NLP/ML based)
⚠️ SpeechProcessor is not implemented
⚠️ No comparison with industry benchmarks

### Potential Improvements
💡 Add NLP-based semantic analysis
💡 Implement BERT/GPT for answer evaluation
💡 Add speaker diarization for group interviews
💡 Create industry benchmark comparisons
💡 Add ML-based pattern matching for chatbot
💡 Implement emotion/sentiment analysis

---

## 📈 Model Performance Metrics

Currently, no formal metrics are implemented. Suggestions:

- **Accuracy:** Compare AI scores with human evaluator scores
- **Precision:** Skill detection accuracy
- **Recall:** Comprehensive skill coverage
- **F1-Score:** Balanced assessment
- **Feedback Quality:** User satisfaction survey

---

## 🔒 Local Question Bank & Management

- The project now includes a local question bank at `data/questions/interview_questions.json` that contains curated questions for multiple engineering branches (software, frontend, backend, devops, data science, QA, embedded, electrical, mechanical, civil, etc.).
- This file is used as a resilient fallback when external APIs (Router/DeepSeek/Hugging Face) are unavailable or API keys are not set.
- A simple management script `scripts/manage_questions.py` is provided to list roles and add questions from the command line:
  - `python3 scripts/manage_questions.py list-roles`
  - `python3 scripts/manage_questions.py list --role software_engineer`
  - `python3 scripts/manage_questions.py add --role software_engineer --question "Why X?" --type technical --difficulty medium`

**Last Updated:** December 2025 (updated with local question bank details)
