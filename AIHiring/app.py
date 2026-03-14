from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import os
import json
from datetime import datetime, timedelta
from config import Config
from models.ai_interviewer import AIInterviewer
from models.resume_analyzer import ResumeAnalyzer
from models.speech_processor import SpeechProcessor
from models.question_generator import QuestionGenerator
from models.physical_analyzer import PhysicalAnalyzer
from models.interview_db import InterviewDatabase
from utils.helpers import allowed_file, calculate_score, clean_text
import secrets
import ssl
import random

app = Flask(__name__)
app.config.from_object(Config)

# Create upload directory
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize AI components and database
ai_interviewer = AIInterviewer()
resume_analyzer = ResumeAnalyzer()
speech_processor = SpeechProcessor()
question_generator = QuestionGenerator()
physical_analyzer = PhysicalAnalyzer()
interview_db = InterviewDatabase()

# Add CORS headers for microphone access
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

# Debug small probe logger for .well-known requests (quiet unless matched)
@app.before_request
def log_well_known_requests():
    try:
        if '.well-known' in request.path:
            print(f"DEBUG: Well-known probe request: {request.method} {request.path}")
    except Exception:
        pass

@app.route('/')
def index():
    return render_template('index.html')

# Serve devtools probe file to avoid 404 spam
@app.route('/.well-known/appspecific/com.chrome.devtools.json')
def serve_chrome_devtools_probe_root():
    try:
        file_path = os.path.join(app.root_path, '.well-known', 'appspecific', 'com.chrome.devtools.json')
        print(f"DEBUG: serve_chrome_devtools_probe_root called, checking {file_path}")
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return (content, 200, {'Content-Type': 'application/json'})
        return ('{}', 200, {'Content-Type': 'application/json'})
    except Exception as e:
        print(f"Error serving devtools probe (root): {e}")
        return ('', 204)

# Generic catch for other .well-known/appspecific probes (return 204 No Content)
@app.route('/.well-known/appspecific/<path:filename>', methods=['GET','HEAD','OPTIONS'])
def appspecific_probe_root(filename):
    print(f"DEBUG: appspecific probe for {filename}")
    return ('', 204)

# Catch-all for any /.well-known/* probe to avoid 404 spam from browsers or extensions
@app.route('/.well-known/<path:subpath>', methods=['GET','HEAD','OPTIONS'])
def well_known_catch_all(subpath):
    print(f"DEBUG: Well-known catch-all probe: {request.method} {request.path}")
    # Try to serve matching file if exists under .well-known
    file_path = os.path.join(app.root_path, '.well-known', subpath)
    try:
        if os.path.exists(file_path) and os.path.isfile(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return (content, 200, {'Content-Type': 'application/json'})
    except Exception as e:
        print(f"Error serving well-known {subpath}: {e}")
    # Otherwise return empty JSON to silence clients
    return ('{}', 200, {'Content-Type': 'application/json'})

# Helpful 404 logger to capture missing resource patterns (quiet)
@app.errorhandler(404)
def log_404(e):
    try:
        print(f"DEBUG 404: {request.method} {request.path} Host: {request.host} Referer: {request.headers.get('Referer')}")
    except Exception:
        pass
    return e, 404

# JSON endpoints for question bank
@app.route('/api/questions/<role>')
def api_get_questions_root(role):
    try:
        role_q = question_generator.base_questions.get(role)
        if not role_q:
            return jsonify({'error': 'Role not found', 'available_roles': list(question_generator.base_questions.keys())}), 404
        return jsonify({'role': role, 'questions': role_q, 'count': len(role_q)})
    except Exception as e:
        print(f"Error in api_get_questions_root: {e}")
        return jsonify({'error': 'internal error'}), 500

@app.route('/data/questions/<role>.json')
def data_role_questions_root(role):
    try:
        role_q = question_generator.base_questions.get(role)
        if not role_q:
            return jsonify({'error': 'Role not found', 'available_roles': list(question_generator.base_questions.keys())}), 404
        return (json.dumps({role: role_q}, indent=2), 200, {'Content-Type': 'application/json'})
    except Exception as e:
        print(f"Error in data_role_questions_root: {e}")
        return jsonify({'error': 'internal error'}), 500

@app.route('/data/questions/interview_questions.json')
def data_all_questions():
    try:
        file_path = os.path.join(app.root_path, 'data', 'questions', 'interview_questions.json')
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return (content, 200, {'Content-Type': 'application/json'})
        return (json.dumps({}), 200, {'Content-Type': 'application/json'})
    except Exception as e:
        print(f"Error serving interview_questions.json: {e}")
        return jsonify({'error': 'internal error'}), 500

@app.route('/api/session/questions')
def api_session_questions_root():
    if 'interview_id' not in session or 'questions' not in session:
        return jsonify({'error': 'No active interview or questions not generated yet'}), 404
    return jsonify({
        'interview_id': session.get('interview_id'),
        'role': session.get('job_role'),
        'questions_source': session.get('questions_source'),
        'questions': session.get('questions')
    })

@app.route('/api/questions_source')
def api_questions_source_root():
    source = session.get('questions_source') if 'interview_id' in session else None
    return jsonify({'questions_source': source})


@app.route('/api/verify_otp', methods=['POST'])
def api_verify_otp():
    """Verify OTP submitted from the client. If correct, mark session otp_verified True."""
    try:
        # Accept JSON or form payloads
        data = request.get_json(silent=True) or request.form
        otp = data.get('otp') if isinstance(data, dict) else None
        if not otp:
            return jsonify({'success': False, 'error': 'Missing OTP'}), 400

        expected = session.get('interview_otp')
        if not expected:
            return jsonify({'success': False, 'error': 'No OTP for this session'}), 400

        if str(otp).strip() == str(expected).strip():
            session['otp_verified'] = True
            # Mirror client-side sessionStorage state for convenience
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'OTP does not match'}), 400
    except Exception as e:
        print(f"Error verifying OTP: {e}")
        return jsonify({'success': False, 'error': 'internal error'}), 500


@app.route('/api/session/load_local_questions', methods=['POST'])
def api_load_local_questions():
    """Load local base questions into the session as a fallback when external APIs fail.
    Request JSON: { "role": "software_engineer", "num": 12 }
    """
    try:
        data = request.get_json(silent=True) or request.form
        role = data.get('role') if isinstance(data, dict) else None
        role = role or session.get('job_role', 'software_engineer')
        try:
            num = int(data.get('num')) if isinstance(data, dict) and data.get('num') else None
        except Exception:
            num = None

        base = question_generator.base_questions.get(role)
        if not base:
            return jsonify({'success': False, 'error': 'Role not found', 'available_roles': list(question_generator.base_questions.keys())}), 404

        # Build questions list - repeat if needed to reach num
        questions = list(base)
        if num:
            while len(questions) < num:
                questions.extend(base)
            questions = questions[:num]

        # Initialize session with questions
        session['questions'] = questions
        session['current_question'] = 0
        session['questions_source'] = 'local'

        print(f"✅ Loaded {len(questions)} local questions for role {role} into session")
        return jsonify({'success': True, 'count': len(questions)})
    except Exception as e:
        print(f"Error loading local questions: {e}")
        return jsonify({'success': False, 'error': 'internal error'}), 500

@app.route('/interview_setup')
def interview_setup():
    return render_template('interview_setup.html')

@app.route('/start_interview_with_name', methods=['GET', 'POST'])
def start_interview_with_name():
    # Handle both POST (from form) and GET (fallback) requests
    if request.method == 'POST':
        candidate_name = request.form.get('candidate_name', '').strip()
    else:  # GET request
        candidate_name = request.args.get('candidate_name', '').strip()

    print(f"DEBUG: Method={request.method}, Received candidate_name: '{candidate_name}'")
    print(f"DEBUG: Form data: {dict(request.form)}")
    print(f"DEBUG: Args data: {dict(request.args)}")

    if not candidate_name:
        print("DEBUG: Candidate name is empty, returning 400")
        return jsonify({'error': 'Candidate name is required'}), 400

    # Clear any existing session
    session.clear()

    # Store candidate name
    session['candidate_name'] = candidate_name
    session['job_role'] = 'software_engineer'

    # Create database entry for this interview
    interview_id = interview_db.create_interview(candidate_name, 'software_engineer')
    session['interview_id'] = interview_id

    print(f"✅ Interview session initialized for {candidate_name} (ID: {interview_id})")

    # Initialize interview session
    session['current_question'] = 0
    session['score'] = 0
    session['responses'] = []
    session['start_time'] = datetime.now().isoformat()
    session['enable_voice'] = True
    # Mark session as OTP verified for simpler start flow (dev-friendly)
    session['otp_verified'] = True

    # Generate questions
    from config import Config
    target_total = max(Config.MIN_QUESTIONS, min(Config.MAX_QUESTIONS, Config.DEFAULT_QUESTIONS))
    session['total_questions_target'] = target_total

    resume_analysis = session.get('resume_analysis', {})
    questions = question_generator.generate_questions_raw('software_engineer', resume_analysis, target_total)

    # Record where questions came from
    try:
        session['questions_source'] = question_generator.last_generation_source
        print(f"🧭 Questions source (root): {session['questions_source']}")
    except Exception:
        session['questions_source'] = None

    if not questions:
        questions = [{
            "question": "Tell me about yourself and your most relevant experience for this role.",
            "type": "behavioral",
            "difficulty": "easy"
        }]

    session['questions'] = questions
    print(f"✅ Generated {len(questions)} questions successfully")

    # Return JSON response for frontend to handle redirect
    print(f"✅ Interview session initialized for {candidate_name}")
    # If this is a normal form submission (non-AJAX), return an HTTP redirect to the interview room page so users without JS still continue.
    accept_header = request.headers.get('Accept', '')
    xreq = request.headers.get('X-Requested-With', '')
    if xreq != 'XMLHttpRequest' and 'application/json' not in accept_header:
        print("DEBUG: Non-AJAX form submit detected, issuing HTTP redirect to interview_room")
        return redirect(url_for('interview_room'))

    return jsonify({
        'success': True,
        'redirect': url_for('interview_room')
    })
def debug_models():
    """Test if all models are working"""
    results = {}
    
    try:
        # Test AI Interviewer
        questions = ai_interviewer.get_questions('software_engineer')
        results['ai_interviewer'] = f"Working - {len(questions)} questions"
    except Exception as e:
        results['ai_interviewer'] = f"Error: {e}"
    
    try:
        # Test Question Generator
        questions = question_generator.generate_questions('software_engineer', {})
        results['question_generator'] = f"Working - {len(questions)} questions"
    except Exception as e:
        results['question_generator'] = f"Error: {e}"
    
    try:
        # Test Resume Analyzer
        analysis = resume_analyzer.analyze_resume_text("Sample resume text with Python and Java skills")
        results['resume_analyzer'] = f"Working - Skills: {len(analysis['skills'])}"
    except Exception as e:
        results['resume_analyzer'] = f"Error: {e}"
    
    try:
        # Test Speech Processor
        speech_processor.speech_to_text(None)
        results['speech_processor'] = "Working"
    except Exception as e:
        results['speech_processor'] = f"Error: {e}"
    
    return jsonify(results)

@app.route('/debug/start_interview_direct')
def debug_start_interview_direct():
    """Direct test of interview start"""
    session.clear()
    
    # Use AI Interviewer directly (bypass question generator)
    questions = ai_interviewer.get_questions('software_engineer')
    
    # Initialize interview session
    session['interview_id'] = secrets.token_hex(16)
    session['current_question'] = 0
    session['score'] = 0
    session['responses'] = []
    session['questions'] = questions
    session['job_role'] = 'software_engineer'
    session['start_time'] = datetime.now().isoformat()
    session['enable_voice'] = False
    
    return redirect(url_for('interview_room'))


@app.route('/debug_interview_state')
def debug_interview_state():
    """Debug current interview state"""
    if 'interview_id' not in session:
        return jsonify({'error': 'No active interview'})
    
    return jsonify({
        'current_question': session['current_question'],
        'total_questions': len(session['questions']),
        'questions': session['questions'],
        'completed': session['current_question'] >= len(session['questions'])
    })


@app.route('/check_permissions')
def check_permissions():
    """Check if browser supports media devices"""
    return jsonify({
        'https': request.is_secure,
        'host': request.host,
        'scheme': request.scheme
    })

@app.route('/auto_next_question')
def auto_next_question():
    """Automatically redirect to next question or results"""
    if 'interview_id' not in session:
        return redirect(url_for('index'))
    
    current_q = session['current_question']
    target_total = session.get('total_questions_target', len(session.get('questions', [])))
    
    if current_q >= target_total:
        return redirect(url_for('results'))
    else:
        return redirect(url_for('interview_room'))

@app.route('/analyze_resume', methods=['GET', 'POST'])
def analyze_resume():
    if request.method == 'POST':
        if 'resume' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['resume']
        if file and allowed_file(file.filename):
            try:
                # Save file
                filename = secrets.token_hex(8) + '_' + file.filename
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                
                # Analyze resume
                analysis = resume_analyzer.analyze_resume_file(filepath)
                
                # Store analysis in session
                session['resume_analysis'] = analysis
                session['resume_file'] = filename
                
                return render_template('resume_analysis.html', analysis=analysis)
                
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        return jsonify({'error': 'Invalid file type'}), 400
    
    return render_template('resume_analysis.html')

@app.route('/chatbot')
def chatbot_page():
    return render_template('chatbot.html')

@app.route('/test_camera')
def test_camera():
    return render_template('test_camera.html')

@app.route('/test_questions')
def test_questions():
    """Test question flow"""
    session.clear()
    questions = [
        {'question': 'Question 1: Tell me about yourself', 'type': 'behavioral'},
        {'question': 'Question 2: What are your strengths?', 'type': 'behavioral'},
        {'question': 'Question 3: Where do you see yourself in 5 years?', 'type': 'behavioral'}
    ]
    
    session['interview_id'] = 'test'
    session['current_question'] = 0
    session['questions'] = questions
    session['responses'] = []
    
    return redirect('/interview_room')

@app.route('/start_video_interview', methods=['POST'])
def start_video_interview():
    session.clear()
    
    # Get candidate name, job role and use resume analysis if available
    candidate_name = request.form.get('candidate_name', 'Anonymous')
    job_role = request.form.get('job_role', 'software_engineer')
    resume_analysis = session.get('resume_analysis', {})
    
    # Initialize interview session first
    # Create database entry for this interview
    interview_id = interview_db.create_interview(candidate_name, job_role)
    session['interview_id'] = interview_id
    
    session['candidate_name'] = candidate_name  # Store candidate name
    session['current_question'] = 0
    session['score'] = 0
    session['responses'] = []
    session['job_role'] = job_role
    session['start_time'] = datetime.now().isoformat()
    session['enable_voice'] = True
    
    # Generate OTP for interview verification (6-digit code)
    # For user convenience, we will auto-verify this session since they just clicked start
    otp_code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
    session['interview_otp'] = otp_code
    session['otp_expires'] = (datetime.now() + timedelta(minutes=10)).isoformat()
    session['otp_verified'] = True  # Auto-verify to enable camera immediately
    
    # Interview length target (10-15 by config)
    from config import Config
    target_total = max(Config.MIN_QUESTIONS, min(Config.MAX_QUESTIONS, Config.DEFAULT_QUESTIONS))
    session['total_questions_target'] = target_total

    # Generate only the first question now; generate subsequent questions sequentially (interviewer-style)
    print(f"🔄 Generating first question for {job_role} interview using Hugging Face API...")
    
    # Use question generator with fallback logic
    first_batch = question_generator.generate_questions_raw(job_role, resume_analysis, 1)
    
    session['questions'] = first_batch if first_batch else [{
        "question": "Tell me about yourself and your most relevant experience for this role.",
        "type": "behavioral",
        "difficulty": "easy"
    }]
    print(f"✅ Interview initialized with ID {interview_id} and {len(session['questions'])} questions")
    print(f"🔐 OTP generated: {otp_code} (Auto-verified)")
    
    return redirect(url_for('interview_room'))

@app.route('/video_interview')
def video_interview():
    if 'interview_id' not in session:
        return redirect(url_for('index'))
    
    # Ensure at least the first question exists
    if 'questions' not in session or not session['questions']:
        print("⚠️ No questions in session - generating first question...")
        job_role = session.get('job_role', 'software_engineer')
        resume_analysis = session.get('resume_analysis', {})
        from config import Config
        session['total_questions_target'] = max(Config.MIN_QUESTIONS, min(Config.MAX_QUESTIONS, Config.DEFAULT_QUESTIONS))
        first_batch = question_generator.generate_questions_raw(job_role, resume_analysis, 1)
        session['questions'] = first_batch if first_batch else [{
            "question": "Tell me about yourself and your most relevant experience for this role.",
            "type": "behavioral",
            "difficulty": "easy"
        }]
        session['current_question'] = 0
    
    return render_template('video_interview.html',
                         enable_voice=session.get('enable_voice', True))

@app.route('/interview_room')
def interview_room():
    print(f"DEBUG: interview_room called, session keys: {list(session.keys())}")
    print(f"DEBUG: interview_id in session: {'interview_id' in session}")
    if 'interview_id' in session:
        print(f"DEBUG: interview_id value: {session.get('interview_id')}")
    
    if 'interview_id' not in session:
        print("DEBUG: No interview_id in session, redirecting to index")
        return redirect(url_for('index'))
    
    print("DEBUG: interview_id found, proceeding with interview setup")
    
    # Ensure interview target is set and at least the first question exists
    from config import Config
    if 'total_questions_target' not in session:
        session['total_questions_target'] = max(Config.MIN_QUESTIONS, min(Config.MAX_QUESTIONS, Config.DEFAULT_QUESTIONS))
        print(f"DEBUG: Set total_questions_target to {session['total_questions_target']}")

    if 'questions' not in session or not session['questions']:
        print("DEBUG: No questions found in session - generating first question...")
        job_role = session.get('job_role', 'software_engineer')
        resume_analysis = session.get('resume_analysis', {})
        first_batch = question_generator.generate_questions_raw(job_role, resume_analysis, 1)
        session['questions'] = first_batch if first_batch else [{
            "question": "Tell me about yourself and your most relevant experience for this role.",
            "type": "behavioral",
            "difficulty": "easy"
        }]
        session['current_question'] = 0
        print(f"DEBUG: Generated questions: {len(session['questions'])}")
    
    current_q = session['current_question']
    questions = session['questions']
    target_total = session.get('total_questions_target', len(questions))
    
    print(f"DEBUG: current_q={current_q}, len(questions)={len(questions)}, target_total={target_total}")
    
    # Check if interview is completed - auto redirect to results
    if current_q >= target_total:
        print("DEBUG: Interview completed, redirecting to results")
        # Stop any ongoing analysis and redirect to results
        return redirect(url_for('results'))

    # Ensure the current question exists (sequential generation)
    if current_q >= len(questions):
        print(f"DEBUG: Need to generate question {current_q}, generating...")
        job_role = session.get('job_role', 'software_engineer')
        resume_analysis = session.get('resume_analysis', {})
        prev_answer = None
        if session.get('responses'):
            prev_answer = session['responses'][-1].get('answer')
        next_q = question_generator.generate_next_question(job_role, resume_analysis, questions, prev_answer)
        questions.append(next_q)
        session['questions'] = questions
        print(f"DEBUG: Generated next question: {next_q}")
    
    question = questions[current_q]
    print(f"DEBUG: Current question: {question}")
    
    try:
        result = render_template('interview_room.html',
                         question=question,
                         question_num=current_q + 1,
                         total_questions=target_total,
                         enable_voice=session.get('enable_voice', True))
        print("DEBUG: Template rendered successfully")
        return result
    except Exception as e:
        print(f"DEBUG: Template rendering error: {e}")
        import traceback
        traceback.print_exc()
        return f"Template error: {e}", 500
    
    
@app.route('/submit_answer', methods=['POST'])
def submit_answer():
    print(f"DEBUG: submit_answer called, session keys: {list(session.keys())}")
    print(f"DEBUG: interview_id in session: {'interview_id' in session}")
    if 'interview_id' in session:
        print(f"DEBUG: interview_id value: {session.get('interview_id')}")
    
    if 'interview_id' not in session:
        print("DEBUG: No interview_id in session, returning 400")
        return jsonify({'error': 'No active interview'}), 400
    
    current_q = session['current_question']
    questions = session['questions']
    
    # Check if we've exceeded the question count
    if current_q >= len(questions):
        return jsonify({
            'completed': True,
            'next_question': current_q,
            'score': 0,
            'feedback': 'Interview completed!',
            'detailed_analysis': {}
        })
    
    answer = request.form.get('answer', '')
    job_role = session['job_role']
    resume_analysis = session.get('resume_analysis', {})
    
    # Get physical analysis data if available
    physical_data = session.get('physical_analysis', {}).get(f'question_{current_q}', {})
    
    # Analyze the answer
    score, feedback, detailed_analysis = ai_interviewer.analyze_answer(
        job_role, current_q, answer, resume_analysis
    )
    
    # Integrate physical analysis into score if available
    if physical_data and Config.ENABLE_PHYSICAL_ANALYSIS:
        physical_score = physical_data.get('overall_physical_score', 0)
        # Combine answer score (70%) with physical score (30%)
        combined_score = (score * 0.7) + (physical_score * 0.3)
        score = round(combined_score, 1)
        
        # Add physical analysis to detailed analysis
        detailed_analysis['physical_analysis'] = physical_data
        detailed_analysis['confidence_score'] = physical_data.get('confidence', 0)
        detailed_analysis['voice_quality'] = physical_data.get('voice_quality', 0)
        detailed_analysis['body_language'] = physical_data.get('body_language', 0)
    
    # Add AI personality to feedback
    if score >= 8:
        ai_feedback = f"Excellent! {feedback} That was a well-structured response."
    elif score >= 6:
        ai_feedback = f"Good job. {feedback} You're on the right track."
    elif score >= 4:
        ai_feedback = f"Okay. {feedback} Let's work on improving this."
    else:
        ai_feedback = f"I see. {feedback} We'll practice more on this area."
    
    # Store response with physical analysis
    response_data = {
        'question_index': current_q,
        'question': questions[current_q]['question'],
        'answer': answer,
        'score': score,
        'feedback': ai_feedback,
        'detailed_analysis': detailed_analysis
    }
    
    # Add physical analysis if available
    if physical_data:
        response_data['physical_analysis'] = physical_data
    
    session['responses'].append(response_data)
    
    # Save responses to database
    interview_id = session.get('interview_id')
    if interview_id:
        interview_db.save_responses(interview_id, session['responses'])
    
    # Clear physical analysis for next question
    if f'question_{current_q}' in session.get('physical_analysis', {}):
        session['physical_analysis'].pop(f'question_{current_q}', None)
    
    session['score'] += score
    session['current_question'] += 1
    
    # Check if interview is completed
    target_total = session.get('total_questions_target', len(questions))
    completed = session['current_question'] >= target_total

    # If completed, save final results to database
    if completed and interview_id:
        avg_score = session['score'] / len(session['responses']) if session['responses'] else 0
        interview_db.update_interview_score(interview_id, round(avg_score, 1),
                                          len(session['responses']), target_total)

    # Pre-generate the next question (so the next page load has it)
    if not completed:
        next_index = session['current_question']
        if next_index >= len(session.get('questions', [])):
            job_role = session['job_role']
            next_q = question_generator.generate_next_question(
                job_role,
                resume_analysis,
                session.get('questions', []),
                last_answer=answer
            )
            session['questions'].append(next_q)
    
    return jsonify({
        'next_question': session['current_question'],
        'score': score,
        'feedback': ai_feedback,
        'detailed_analysis': detailed_analysis,
        'completed': completed
    })

@app.route('/admin')
def admin():
    """Admin panel to view all interviews"""
    interviews = interview_db.get_all_interviews()
    stats = interview_db.get_interview_stats()
    score_distribution = interview_db.get_score_distribution()
    job_role_stats = interview_db.get_job_role_stats()
    return render_template('admin.html',
                         interviews=interviews,
                         stats=stats,
                         score_distribution=score_distribution,
                         job_role_stats=job_role_stats)

@app.route('/admin/interview/<int:interview_id>')
def admin_interview_detail(interview_id):
    """View detailed interview results"""
    interview = interview_db.get_interview(interview_id)
    if not interview:
        return "Interview not found", 404

    # Parse JSON data - handle None values
    responses_data = interview.get('responses') or '[]'
    resume_analysis_data = interview.get('resume_analysis') or '{}'

    try:
        responses = json.loads(responses_data)
    except (json.JSONDecodeError, TypeError):
        responses = []

    try:
        resume_analysis = json.loads(resume_analysis_data)
    except (json.JSONDecodeError, TypeError):
        resume_analysis = {}

    return render_template('admin_interview_detail.html',
                         interview=interview,
                         responses=responses,
                         resume_analysis=resume_analysis)

@app.route('/admin/delete/<int:interview_id>', methods=['POST'])
def admin_delete_interview(interview_id):
    """Delete an interview"""
    interview_db.delete_interview(interview_id)
    return redirect(url_for('admin'))
    if 'interview_id' not in session:
        return jsonify({'error': 'No active interview'}), 400
    
    if 'audio' not in request.files:
        return jsonify({'error': 'No audio file'}), 400
    
    audio_file = request.files['audio']
    
    try:
        # Convert speech to text
        text = speech_processor.speech_to_text(audio_file)
        
        if text:
            return jsonify({
                'success': True,
                'text': text
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Could not understand audio'
            })
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/analyze_physical', methods=['POST'])
def analyze_physical():
    """Analyze physical actions: confidence, voice, body language"""
    if 'interview_id' not in session:
        return jsonify({'error': 'No active interview'}), 400
    
    try:
        current_q = session['current_question']
        
        # Get video frames and audio segments from request
        video_frames = request.form.getlist('video_frames[]')  # Base64 encoded frames
        audio_segments = request.form.getlist('audio_segments[]')  # Base64 encoded audio
        
        if not video_frames and not audio_segments:
            return jsonify({'error': 'No data provided'}), 400
        
        # Analyze physical actions using Hugging Face
        physical_analysis = physical_analyzer.analyze_realtime_data(
            video_frames if video_frames else [],
            audio_segments if audio_segments else []
        )
        
        # Store analysis in session for this question
        if 'physical_analysis' not in session:
            session['physical_analysis'] = {}
        
        session['physical_analysis'][f'question_{current_q}'] = physical_analysis
        
        return jsonify({
            'success': True,
            'analysis': physical_analysis,
            'summary': physical_analyzer.get_analysis_summary()
        })
        
    except Exception as e:
        print(f"Error in physical analysis: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/update_physical_analysis', methods=['POST'])
def update_physical_analysis():
    """Update physical analysis with single frame/audio segment"""
    if 'interview_id' not in session:
        return jsonify({'error': 'No active interview'}), 400
    
    try:
        current_q = session['current_question']
        
        # Get single frame or audio segment
        video_frame = request.form.get('video_frame')  # Base64 encoded
        audio_segment = request.form.get('audio_segment')  # Base64 encoded
        
        if not video_frame and not audio_segment:
            return jsonify({'success': False, 'error': 'No data provided'})
        
        # Initialize storage if needed
        if 'physical_analysis' not in session:
            session['physical_analysis'] = {}
        
        if f'question_{current_q}' not in session['physical_analysis']:
            session['physical_analysis'][f'question_{current_q}'] = {
                'confidence': 0.0,
                'voice_quality': 0.0,
                'body_language': 0.0,
                'overall_physical_score': 0.0,
                'details': {
                    'confidence_scores': [],
                    'voice_scores': [],
                    'posture_scores': [],
                    'frame_count': 0,
                    'audio_segment_count': 0
                }
            }
        
        current_data = session['physical_analysis'][f'question_{current_q}']
        details = current_data['details']
        
        # Analyze video frame if provided
        if video_frame:
            frame_analysis = physical_analyzer.analyze_video_frame(video_frame)
            if frame_analysis:
                details['confidence_scores'].append(frame_analysis.get('confidence', 5.0))
                details['posture_scores'].append(frame_analysis.get('posture_score', 5.0))
                details['frame_count'] += 1
                
                # Recalculate averages
                if details['confidence_scores']:
                    current_data['confidence'] = round(
                        sum(details['confidence_scores']) / len(details['confidence_scores']), 2
                    )
                if details['posture_scores']:
                    current_data['body_language'] = round(
                        sum(details['posture_scores']) / len(details['posture_scores']), 2
                    )
        
        # Analyze audio segment if provided
        if audio_segment:
            audio_analysis = physical_analyzer.analyze_audio(audio_segment)
            if audio_analysis:
                details['voice_scores'].append(audio_analysis.get('voice_score', 5.0))
                details['audio_segment_count'] += 1
                
                # Recalculate average
                if details['voice_scores']:
                    current_data['voice_quality'] = round(
                        sum(details['voice_scores']) / len(details['voice_scores']), 2
                    )
        
        # Recalculate overall physical score
        current_data['overall_physical_score'] = round(
            (current_data['confidence'] * Config.CONFIDENCE_WEIGHT +
             current_data['voice_quality'] * Config.VOICE_WEIGHT +
             current_data['body_language'] * Config.BODY_LANGUAGE_WEIGHT), 2
        )
        
        return jsonify({
            'success': True,
            'current_analysis': current_data,
            'summary': {
                'confidence': current_data['confidence'],
                'voice_quality': current_data['voice_quality'],
                'body_language': current_data['body_language'],
                'overall_physical_score': current_data['overall_physical_score']
            }
        })
        
    except Exception as e:
        print(f"Error updating physical analysis: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/results')
def results():
    if 'interview_id' not in session:
        return redirect(url_for('index'))
    
    total_score = session['score']
    max_possible = len(session['responses']) * 10
    percentage = (total_score / max_possible * 100) if max_possible > 0 else 0
    candidate_name = session.get('candidate_name', 'Anonymous')
    
    # Generate overall feedback
    overall_feedback = ai_interviewer.generate_overall_feedback(
        session['responses'], session.get('resume_analysis', {})
    )
    
    # Store prediction scores with candidate name
    prediction_data = {
        'candidate_name': candidate_name,
        'otp': session.get('interview_otp', 'N/A'),
        'interview_id': session['interview_id'],
        'job_role': session.get('job_role', 'software_engineer'),
        'total_score': total_score,
        'percentage': percentage,
        'max_possible': max_possible,
        'total_questions': len(session['responses']),
        'responses': session['responses'],
        'overall_feedback': overall_feedback,
        'start_time': session.get('start_time'),
        'end_time': datetime.now().isoformat(),
        'physical_analysis': session.get('physical_analysis', {})
    }
    
    # Save prediction scores to file (JSON format)
    try:
        os.makedirs('data/predictions', exist_ok=True)
        prediction_file = f"data/predictions/{session['interview_id']}_{candidate_name.replace(' ', '_')}.json"
        with open(prediction_file, 'w') as f:
            json.dump(prediction_data, f, indent=2)
        print(f"✅ Prediction scores saved for {candidate_name}: {prediction_file}")
    except Exception as e:
        print(f"⚠️ Error saving prediction scores: {e}")
    
    return render_template('results.html',
                         candidate_name=candidate_name,
                         score=total_score,
                         percentage=percentage,
                         responses=session['responses'],
                         overall_feedback=overall_feedback,
                         resume_analysis=session.get('resume_analysis'))

@app.route('/admin')
def admin_panel():
    """Admin panel to view all interview predictions"""
    try:
        predictions_dir = 'data/predictions'
        if not os.path.exists(predictions_dir):
            return render_template('admin.html', predictions=[])
        
        predictions = []
        for filename in os.listdir(predictions_dir):
            if filename.endswith('.json'):
                try:
                    with open(os.path.join(predictions_dir, filename), 'r') as f:
                        data = json.load(f)
                        predictions.append(data)
                except Exception as e:
                    print(f"Error loading prediction file {filename}: {e}")
        
        # Sort by end time (most recent first)
        predictions.sort(key=lambda x: x.get('end_time', ''), reverse=True)
        
        return render_template('admin.html', predictions=predictions)
    except Exception as e:
        print(f"Error loading admin panel: {e}")
        return render_template('admin.html', predictions=[])

@app.route('/get_next_question')
def get_next_question():
    if 'interview_id' not in session:
        return jsonify({'error': 'No active interview'}), 400
    
    current_q = session['current_question']
    questions = session['questions']
    target_total = session.get('total_questions_target', len(questions))
    
    if current_q >= target_total:
        return jsonify({'completed': True})
    
    # Ensure question exists
    if current_q >= len(questions):
        job_role = session.get('job_role', 'software_engineer')
        resume_analysis = session.get('resume_analysis', {})
        prev_answer = None
        if session.get('responses'):
            prev_answer = session['responses'][-1].get('answer')
        questions.append(question_generator.generate_next_question(job_role, resume_analysis, questions, prev_answer))
        session['questions'] = questions

    question = questions[current_q]
    return jsonify({
        'question': question['question'],
        'question_num': current_q + 1,
        'total_questions': target_total,
        'type': question.get('type', 'technical')
    })

def create_ssl_context():
    """Create SSL context with fallback"""
    try:
        # Method 1: Use existing certificate files
        if os.path.exists('cert.pem') and os.path.exists('key.pem'):
            context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
            context.load_cert_chain('cert.pem', 'key.pem')
            return context
        else:
            # Method 2: Create self-signed certificate programmatically
            from OpenSSL import crypto
            import tempfile
            
            # Create a key pair
            k = crypto.PKey()
            k.generate_key(crypto.TYPE_RSA, 4096)
            
            # Create a self-signed cert
            cert = crypto.X509()
            cert.get_subject().C = "US"
            cert.get_subject().ST = "State"
            cert.get_subject().L = "City"
            cert.get_subject().O = "Organization"
            cert.get_subject().OU = "Organization Unit"
            cert.get_subject().CN = "localhost"
            cert.set_serial_number(1000)
            cert.gmtime_adj_notBefore(0)
            cert.gmtime_adj_notAfter(365*24*60*60)
            cert.set_issuer(cert.get_subject())
            cert.set_pubkey(k)
            cert.sign(k, 'sha512')
            
            # Save certificate and key to temporary files
            with open('cert.pem', 'wt') as f:
                f.write(crypto.dump_certificate(crypto.FILETYPE_PEM, cert).decode('utf-8'))
            with open('key.pem', 'wt') as f:
                f.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, k).decode('utf-8'))
            
            context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
            context.load_cert_chain('cert.pem', 'key.pem')
            return context
            
    except Exception as e:
        print(f"SSL context creation failed: {e}")
        return None

if __name__ == '__main__':
    # Try to run with HTTPS first
    ssl_context = create_ssl_context()
    
    if ssl_context:
        print("🚀 Running with HTTPS on https://localhost:5000")
        print("📹 Camera and microphone should work now!")
        print("🔐 Make sure to access via: https://localhost:5000")
        app.run(debug=True, ssl_context=ssl_context, host='0.0.0.0', port=5000)
    else:
        print("⚠️  Running without HTTPS - camera/microphone won't work")
        print("💡 To fix this, run: openssl req -x509 -newkey rsa:4096 -nodes -out cert.pem -keyout key.pem -days 365 -subj '/C=US/ST=State/L=City/O=Organization/CN=localhost'")
        app.run(debug=True, host='0.0.0.0', port=5000)