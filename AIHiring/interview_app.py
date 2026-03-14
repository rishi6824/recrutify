from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import os
import json
from datetime import datetime
from config import Config
from models.ai_interviewer import AIInterviewer
from models.speech_processor import SpeechProcessor
from models.question_generator import QuestionGenerator
from models.physical_analyzer import PhysicalAnalyzer
from models.resume_analyzer import ResumeAnalyzer
from utils.helpers import allowed_file, calculate_score, clean_text
import secrets
import ssl
from functools import wraps

app = Flask(__name__)
app.config.from_object(Config)

# Admin credentials (simple for now as requested)
ADMIN_PASSWORD = "123456"

def require_admin(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

# Create upload directory
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize AI components
ai_interviewer = AIInterviewer()
speech_processor = SpeechProcessor()
question_generator = QuestionGenerator()
physical_analyzer = PhysicalAnalyzer()
resume_analyzer = ResumeAnalyzer()

# Add CORS headers for microphone access
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    """Admin login page"""
    error = None
    if request.method == 'POST':
        password = request.form.get('password')
        if password == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            next_url = request.args.get('next') or url_for('admin')
            return redirect(next_url)
        else:
            error = "Invalid password"
    
    return render_template('admin_login.html', error=error)

@app.route('/admin_logout')
def admin_logout():
    """Logout admin"""
    session.pop('admin_logged_in', None)
    return redirect(url_for('index'))

@app.route('/analyze_resume', methods=['GET', 'POST'])
def analyze_resume():
    """Handle resume upload and analysis"""
    analysis = None
    if request.method == 'POST':
        if 'resume' not in request.files:
            return redirect(request.url)
        
        file = request.files['resume']
        if file.filename == '' or not allowed_file(file.filename):
            return redirect(request.url)
        
        # Save file temporarily
        filename = secrets.token_hex(8) + "_" + file.filename
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        try:
            # Perform analysis
            print(f"📄 Analyzing resume: {file.filename}")
            analysis = resume_analyzer.analyze_resume_file(filepath)
            
            # Clean up file
            # os.remove(filepath)
        except Exception as e:
            print(f"Error analyzing resume: {e}")
            return render_template('error.html', 
                                 message="Analysis Failed", 
                                 details=f"An error occurred while analyzing your resume: {str(e)}")
            
    return render_template('resume_analysis.html', analysis=analysis)

@app.route('/interview_setup')
def interview_setup():
    """Render the interview setup/name entry page."""
    return render_template('interview_setup.html')

@app.route('/start_interview_with_name', methods=['POST'])
def start_interview_with_name():
    """Initialize interview session with candidate name and redirect to room."""
    candidate_name = request.form.get('candidate_name', 'Candidate')
    
    # Initialize fresh session
    session.clear()
    session['interview_id'] = secrets.token_hex(16)
    session['candidate_name'] = candidate_name
    session['current_question'] = 0
    session['score'] = 0
    session['responses'] = []
    session['start_time'] = datetime.now().isoformat()
    session['job_role'] = 'software_engineer' # Default
    session['enable_voice'] = True
    
    # Return JSON for AJAX handling in interview_setup.html
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'success': True,
            'redirect': url_for('interview_room')
        })
    
    return redirect(url_for('interview_room'))

# Silence noisy browser probe for devtools by returning 204 to avoid 404 logs
from flask import send_from_directory

# Serve specific devtools probe file to avoid 404 spam from browsers/devtools
@app.route('/.well-known/appspecific/com.chrome.devtools.json')
def serve_chrome_devtools_probe():
    try:
        # Use absolute path from app root to avoid issues with working directory
        file_path = os.path.join(app.root_path, '.well-known', 'appspecific', 'com.chrome.devtools.json')
        print(f"DEBUG: serve_chrome_devtools_probe called, checking {file_path}")
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            # Return file contents directly to avoid send_from_directory issues
            return (content, 200, {'Content-Type': 'application/json'})
        # If file doesn't exist, return an empty JSON body with 200 to silence clients
        return ('{}', 200, {'Content-Type': 'application/json'})
    except Exception as e:
        print(f"Error serving devtools probe: {e}")
        return ('', 204)

# Generic catch for other .well-known/appspecific probes (return 204 No Content)
@app.route('/.well-known/appspecific/<path:filename>', methods=['GET','HEAD','OPTIONS'])
def appspecific_probe(filename):
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


# --- API endpoints for questions (JSON) ---
@app.route('/api/questions/<role>')
def api_get_questions(role):
    """Return question bank for a role as JSON."""
    try:
        role_q = question_generator.base_questions.get(role)
        if not role_q:
            return jsonify({'error': 'Role not found', 'available_roles': list(question_generator.base_questions.keys())}), 404
        return jsonify({'role': role, 'questions': role_q, 'count': len(role_q)})
    except Exception as e:
        print(f"Error in api_get_questions: {e}")
        return jsonify({'error': 'internal error'}), 500

@app.route('/data/questions/interview_questions.json')
def data_all_questions_interview():
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

# Convenience static-like endpoint for front-end to fetch role questions as JSON
@app.route('/data/questions/<role>.json')
def data_role_questions(role):
    try:
        role_q = question_generator.base_questions.get(role)
        if not role_q:
            return jsonify({'error': 'Role not found', 'available_roles': list(question_generator.base_questions.keys())}), 404
        return (json.dumps({role: role_q}, indent=2), 200, {'Content-Type': 'application/json'})
    except Exception as e:
        print(f"Error in data_role_questions: {e}")
        return jsonify({'error': 'internal error'}), 500

@app.route('/api/session/questions')
def api_session_questions():
    """Return current interview session questions (if any)."""
    if 'interview_id' not in session or 'questions' not in session:
        return jsonify({'error': 'No active interview or questions not generated yet'}), 404
    return jsonify({
        'interview_id': session.get('interview_id'),
        'role': session.get('job_role'),
        'questions_source': session.get('questions_source'),
        'questions': session.get('questions')
    })

@app.route('/api/questions_source')
def api_questions_source():
    """Return where questions were sourced from for current session."""
    source = session.get('questions_source') if 'interview_id' in session else None
    return jsonify({'questions_source': source})

@app.route('/start_video_interview', methods=['POST'])
def start_video_interview():
    session.clear()
    
    # Get job role
    job_role = request.form.get('job_role', 'software_engineer')
    resume_analysis = session.get('resume_analysis', {})
    
    # Initialize interview session first
    session['interview_id'] = secrets.token_hex(16)
    session['current_question'] = 0
    session['score'] = 0
    session['responses'] = []
    session['job_role'] = job_role
    session['start_time'] = datetime.now().isoformat()
    session['enable_voice'] = True
    
    # Generate 10-15 personalized questions using Hugging Face API
    from config import Config
    num_questions = Config.DEFAULT_QUESTIONS
    
    print(f"🔄 Generating {num_questions} questions for {job_role} interview using Hugging Face API...")
    questions = question_generator.generate_questions(job_role, resume_analysis, num_questions)
    # Record where questions came from (api/local/mixed)
    try:
        session['questions_source'] = question_generator.last_generation_source
        print(f"🧭 Questions source: {session['questions_source']}")
    except Exception:
        session['questions_source'] = None
    
    # Ensure we have at least minimum questions
    if not questions or len(questions) < Config.MIN_QUESTIONS:
        print(f"⚠️ Only got {len(questions) if questions else 0} questions, generating more...")
        if not questions:
            questions = []
        
        # Generate more questions if needed
        remaining = Config.MIN_QUESTIONS - len(questions)
        additional = question_generator.generate_questions(job_role, resume_analysis, remaining)
        if additional:
            questions.extend(additional[:remaining])
    
    # Final fallback - use base questions if still not enough
    if not questions or len(questions) < Config.MIN_QUESTIONS:
        print("⚠️ Using fallback base questions...")
        base_questions = question_generator.base_questions.get(job_role, question_generator.base_questions["software_engineer"])
        # Repeat to reach minimum
        while len(base_questions) < Config.MIN_QUESTIONS:
            base_questions.extend(question_generator.base_questions.get(job_role, question_generator.base_questions["software_engineer"]))
        questions = base_questions[:Config.MIN_QUESTIONS]
    
    session['questions'] = questions
    print(f"✅ Successfully generated {len(questions)} questions for {job_role} interview")
    
    # Log first few questions for debugging
    if questions:
        print(f"📝 Sample questions:")
        for i, q in enumerate(questions[:3]):
            print(f"   {i+1}. {q.get('question', 'N/A')[:60]}...")
    
    return redirect(url_for('video_interview'))

@app.route('/video_interview')
def video_interview():
    if 'interview_id' not in session:
        return redirect(url_for('index'))
    
    # Ensure questions are generated before showing video interview page
    if 'questions' not in session or not session['questions']:
        print("⚠️ No questions in video_interview route - redirecting to generate questions...")
        job_role = session.get('job_role', 'software_engineer')
        resume_analysis = session.get('resume_analysis', {})
        
        from config import Config
        num_questions = Config.DEFAULT_QUESTIONS
        
        questions = question_generator.generate_questions(job_role, resume_analysis, num_questions)
        
        if not questions or len(questions) < Config.MIN_QUESTIONS:
            if not questions:
                questions = []
            remaining = Config.MIN_QUESTIONS - len(questions)
            additional = question_generator.generate_questions(job_role, resume_analysis, remaining)
            if additional:
                questions.extend(additional[:remaining])
        
        if not questions or len(questions) < Config.MIN_QUESTIONS:
            base_questions = question_generator.base_questions.get(job_role, question_generator.base_questions["software_engineer"])
            while len(base_questions) < Config.MIN_QUESTIONS:
                base_questions.extend(question_generator.base_questions.get(job_role, question_generator.base_questions["software_engineer"]))
            questions = base_questions[:Config.MIN_QUESTIONS]
        
        session['questions'] = questions
        session['current_question'] = 0
        print(f"✅ Generated {len(questions)} questions in video_interview route")
    
    return render_template('video_interview.html',
                         enable_voice=session.get('enable_voice', True))

@app.route('/interview_room')
def interview_room():
    if 'interview_id' not in session:
        return redirect(url_for('index'))
    
    # Auto-generate questions if they don't exist
    if 'questions' not in session or not session['questions']:
        print("⚠️ No questions found in session - auto-generating questions...")
        job_role = session.get('job_role', 'software_engineer')
        resume_analysis = session.get('resume_analysis', {})
        
        from config import Config
        num_questions = Config.DEFAULT_QUESTIONS
        
        # Generate questions using Hugging Face API
        questions = question_generator.generate_questions(job_role, resume_analysis, num_questions)
        
        # Ensure we have at least minimum questions
        if not questions or len(questions) < Config.MIN_QUESTIONS:
            print(f"⚠️ Only got {len(questions) if questions else 0} questions, generating more...")
            # Try generating more questions
            if not questions:
                questions = []
            
            remaining = Config.MIN_QUESTIONS - len(questions)
            additional = question_generator.generate_questions(job_role, resume_analysis, remaining)
            if additional:
                questions.extend(additional[:remaining])
        
        # Final check - if still no questions, use fallback
        if not questions or len(questions) < Config.MIN_QUESTIONS:
            print("⚠️ Using fallback questions...")
            # Get base questions as fallback
            base_questions = question_generator.base_questions.get(job_role, question_generator.base_questions["software_engineer"])
            # Repeat to reach minimum
            while len(base_questions) < Config.MIN_QUESTIONS:
                base_questions.extend(question_generator.base_questions.get(job_role, question_generator.base_questions["software_engineer"]))
            questions = base_questions[:Config.MIN_QUESTIONS]
        
        session['questions'] = questions
        session['current_question'] = 0
        print(f"✅ Auto-generated {len(questions)} questions for {job_role} interview")
    
    current_q = session['current_question']
    questions = session['questions']
    
    # Check if interview is completed - auto redirect to results
    if current_q >= len(questions):
        # Stop any ongoing analysis and redirect to results
        return redirect(url_for('results'))
    
    question = questions[current_q]
    return render_template('interview_room.html',
                         question=question,
                         question_num=current_q + 1,
                         total_questions=len(questions),
                         enable_voice=session.get('enable_voice', True))

@app.route('/submit_answer', methods=['POST'])
def submit_answer():
    if 'interview_id' not in session:
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
    
    # Clear physical analysis for next question
    if f'question_{current_q}' in session.get('physical_analysis', {}):
        session['physical_analysis'].pop(f'question_{current_q}', None)
    
    session['score'] += score
    session['current_question'] += 1
    
    # Check if interview is completed
    completed = session['current_question'] >= len(questions)
    
    return jsonify({
        'next_question': session['current_question'],
        'score': score,
        'feedback': ai_feedback,
        'detailed_analysis': detailed_analysis,
        'completed': completed
    })

@app.route('/process_voice', methods=['POST'])
def process_voice():
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
        # Gracefully handle missing session (e.g. after restart) -> return empty success to keep UI alive
        print("⚠️ analyze_physical called without active session - returning empty result")
        return jsonify({
            'success': True,
            'analysis': {},
            'summary': {
                'confidence': 5.0,
                'voice_quality': 5.0,
                'body_language': 5.0, 
                'overall_physical_score': 5.0
            }
        })
    
    try:
        current_q = session.get('current_question', 0)
        
        # Get video frames and audio segments from request
        video_frames = request.form.getlist('video_frames[]')  # Base64 encoded frames
        audio_segments = request.form.getlist('audio_segments[]')  # Base64 encoded audio
        
        if not video_frames and not audio_segments:
            # Return empty analysis instead of error if no data collected (e.g. robot mode)
            return jsonify({
                'success': True,
                'analysis': {},
                'summary': {
                    'confidence': 5.0,
                    'voice_quality': 5.0,
                    'body_language': 5.0, 
                    'overall_physical_score': 5.0
                }
            })
        
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
                'person_count': 1,
                'phone_detected': False,
                'violations': [],
                'details': {
                    'confidence_scores': [],
                    'voice_scores': [],
                    'posture_scores': [],
                    'person_counts': [],
                    'phone_detections': [],
                    'emotion_history': [],
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
                details['person_counts'].append(frame_analysis.get('person_count', 1))
                details['phone_detections'].append(frame_analysis.get('phone_detected', False))
                
                # Track raw emotions breakdown
                if frame_analysis.get('emotions'):
                    details['emotion_history'].append(frame_analysis['emotions'])
                
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
                
                # Update person count and phone detection
                current_data['person_count'] = max(details['person_counts']) if details['person_counts'] else 1
                current_data['phone_detected'] = any(details['phone_detections']) if details['phone_detections'] else False
                
                # Update violations
                violations = []
                if current_data['phone_detected']:
                    violations.append("Mobile phone detected")
                
                if current_data['person_count'] == 0:
                    violations.append("No face detected")
                elif current_data['person_count'] > 1:
                    violations.append(f"Multiple people detected ({current_data['person_count']})")
                
                current_data['violations'] = violations
        
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
        
        # Get latest emotion for real-time display
        latest_emotion = "Neutral"
        if details['emotion_history']:
            last_emotions = details['emotion_history'][-1]
            if last_emotions:
                latest_emotion = max(last_emotions.items(), key=lambda x: x[1])[0].capitalize()

        return jsonify({
            'success': True,
            'current_analysis': current_data,
            'latest_emotion': latest_emotion,
            'person_count': current_data['person_count'],
            'phone_detected': current_data['phone_detected'],
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

@app.route('/cancel_interview')
def cancel_interview():
    """Cancel the interview due to security violation"""
    if 'interview_id' in session:
        print(f"🚫 Interview {session['interview_id']} cancelled due to security violation (tab switch)")
        session.clear()
    return render_template('error.html', 
                         message="Interview Terminated", 
                         details="This interview session has been cancelled because you switched tabs or minimized the window. Security protocol requires you to stay on the page during the entire interview.")

@app.route('/results')
def results():
    if 'interview_id' not in session:
        return redirect(url_for('index'))
    
    total_score = session['score']
    max_possible = len(session['responses']) * 10
    percentage = (total_score / max_possible * 100) if max_possible > 0 else 0
    candidate_name = session.get('candidate_name', 'Candidate')
    
    # Aggregate physical analysis data from responses
    responses_history = session.get('responses', [])
    avg_confidence = 0
    avg_voice = 0
    avg_posture = 0
    total_violations = []
    all_emotions = []
    
    physical_count = 0
    for resp in responses_history:
        pa = resp.get('physical_analysis')
        if pa:
            conf = pa.get('confidence', 0)
            voice = pa.get('voice_quality', 0)
            posture = pa.get('body_language', 0)
            
            avg_confidence += conf
            avg_voice += voice
            avg_posture += posture
            physical_count += 1
            
            if pa.get('violations'):
                total_violations.extend(pa['violations'])
            if pa.get('details', {}).get('emotion_history'):
                all_emotions.extend(pa['details']['emotion_history'])
    
    if physical_count > 0:
        avg_confidence = round(avg_confidence / physical_count, 1)
        avg_voice = round(avg_voice / physical_count, 1)
        avg_posture = round(avg_posture / physical_count, 1)
    
    # Calculate average emotion profile
    emotion_profile = {}
    if all_emotions:
        # Get list of all emotion labels
        possible_emotions = []
        for frame_emotions in all_emotions:
            possible_emotions.extend(frame_emotions.keys())
        possible_emotions = list(set(possible_emotions))
        
        for emotion in possible_emotions:
            scores = [f.get(emotion, 0) for f in all_emotions]
            avg_score = sum(scores) / len(scores)
            if avg_score > 0.05: # Only include significant emotions
                emotion_profile[emotion.capitalize()] = round(float(avg_score * 100), 1)
        
        # Sort by impact
        emotion_profile = dict(sorted(emotion_profile.items(), key=lambda x: x[1], reverse=True))

    # Generate overall feedback
    overall_feedback = ai_interviewer.generate_overall_feedback(
        session['responses'], session.get('resume_analysis', {})
    )
    
    # Store prediction scores with candidate name
    prediction_data = {
        'candidate_name': candidate_name,
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
        'physical_summary': {
            'avg_confidence': avg_confidence,
            'avg_voice': avg_voice,
            'avg_posture': avg_posture,
            'violations_count': len(total_violations),
            'unique_violations': list(set(total_violations)),
            'emotion_profile': emotion_profile
        }
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
                         responses=session.get('responses', []))

@app.route('/admin')
@require_admin
def admin():
    """Admin panel to view all interview predictions with full statistics"""
    try:
        predictions_dir = 'data/predictions'
        if not os.path.exists(predictions_dir):
            return render_template('admin.html', predictions=[], interviews=[], stats={}, score_distribution={}, job_role_stats=[])
        
        predictions = []
        for filename in os.listdir(predictions_dir):
            if filename.endswith('.json'):
                try:
                    with open(os.path.join(predictions_dir, filename), 'r') as f:
                        data = json.load(f)
                        # Map internal keys to template expected keys if necessary
                        data['id'] = data.get('interview_id')
                        data['status'] = 'completed'
                        data['completed_questions'] = data.get('total_questions', 0)
                        data['overall_score'] = data.get('total_score', 0) / data.get('total_questions', 1) if data.get('total_questions', 0) > 0 else 0
                        data['created_at'] = data.get('end_time', data.get('start_time', ''))
                        predictions.append(data)
                except Exception as e:
                    print(f"Error loading prediction file {filename}: {e}")
        
        # Sort by end time (most recent first)
        predictions.sort(key=lambda x: x.get('end_time', ''), reverse=True)
        
        # Calculate Stats
        total_interviews = len(predictions)
        completed = len(predictions)
        avg_score = sum(p.get('overall_score', 0) for p in predictions) / total_interviews if total_interviews > 0 else 0
        
        stats = {
            'total_interviews': total_interviews,
            'completed_interviews': completed,
            'in_progress_interviews': 0,
            'avg_score': avg_score,
            'failed_interviews': 0
        }
        
        # Calculate Score Distribution
        score_dist = {'0-2': 0, '2-4': 0, '4-6': 0, '6-8': 0, '8-10': 0}
        for p in predictions:
            s = p.get('overall_score', 0)
            if s < 2: score_dist['0-2'] += 1
            elif s < 4: score_dist['2-4'] += 1
            elif s < 6: score_dist['4-6'] += 1
            elif s < 8: score_dist['6-8'] += 1
            else: score_dist['8-10'] += 1
            
        # Calculate Job Role Stats
        role_map = {}
        for p in predictions:
            role = p.get('job_role', 'software_engineer')
            if role not in role_map:
                role_map[role] = {'job_role': role, 'total': 0, 'sum_score': 0, 'completed': 0}
            role_map[role]['total'] += 1
            role_map[role]['completed'] += 1
            role_map[role]['sum_score'] += p.get('overall_score', 0)
            
        job_role_stats = []
        for role, data in role_map.items():
            data['avg_score'] = data['sum_score'] / data['total'] if data['total'] > 0 else 0
            job_role_stats.append(data)
            
        return render_template('admin.html', 
                             predictions=predictions, 
                             interviews=predictions, 
                             stats=stats, 
                             score_distribution=score_dist, 
                             job_role_stats=job_role_stats)
    except Exception as e:
        print(f"Error loading admin panel: {e}")
        import traceback
        traceback.print_exc()
        return f"Admin Panel Error: {e}", 500

@app.route('/admin/interview/<interview_id>')
@require_admin
def admin_interview_detail(interview_id):
    """View detailed interview results from JSON files"""
    try:
        predictions_dir = 'data/predictions'
        for filename in os.listdir(predictions_dir):
            if filename.startswith(interview_id) and filename.endswith('.json'):
                with open(os.path.join(predictions_dir, filename), 'r') as f:
                    data = json.load(f)
                    # Mapping for template
                    interview = {
                        'id': data.get('interview_id'),
                        'candidate_name': data.get('candidate_name'),
                        'job_role': data.get('job_role', 'software_engineer').replace('_', ' ').title(),
                        'status': 'completed',
                        'start_time': data.get('start_time'),
                        'end_time': data.get('end_time'),
                        'overall_score': data.get('total_score', 0) / data.get('total_questions', 1) if data.get('total_questions', 0) > 0 else 0,
                        'physical_summary': data.get('physical_summary', {})
                    }
                    return render_template('admin_interview_detail.html',
                                         interview=interview,
                                         responses=data.get('responses', []),
                                         resume_analysis=data.get('resume_analysis', {}))
        return "Interview not found", 404
    except Exception as e:
        print(f"Error loading interview detail: {e}")
        return str(e), 500

@app.route('/admin/delete/<interview_id>', methods=['POST'])
@require_admin
def admin_delete_interview(interview_id):
    """Delete an interview JSON record"""
    try:
        predictions_dir = 'data/predictions'
        for filename in os.listdir(predictions_dir):
            if filename.startswith(interview_id) and filename.endswith('.json'):
                os.remove(os.path.join(predictions_dir, filename))
                print(f"🗑️ Deleted interview record: {filename}")
                break
        return redirect(url_for('admin'))
    except Exception as e:
        print(f"Error deleting interview: {e}")
        return str(e), 500

@app.route('/auto_next_question')
def auto_next_question():
    """Automatically redirect to next question or results"""
    if 'interview_id' not in session:
        return redirect(url_for('index'))
    
    current_q = session['current_question']
    questions = session['questions']
    
    if current_q >= len(questions):
        return redirect(url_for('results'))
    else:
        return redirect(url_for('interview_room'))

@app.route('/get_next_question')
def get_next_question():
    if 'interview_id' not in session:
        return jsonify({'error': 'No active interview'}), 400
    
    current_q = session['current_question']
    questions = session['questions']
    
    if current_q >= len(questions):
        return jsonify({'completed': True})
    
    question = questions[current_q]
    return jsonify({
        'question': question['question'],
        'question_num': current_q + 1,
        'total_questions': len(questions),
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
        print("🚀 Interview Platform running with HTTPS on https://localhost:5000")
        print("📹 Camera and microphone should work now!")
        print("🔐 Make sure to access via: https://localhost:5000")
        app.run(debug=True, ssl_context=ssl_context, host='0.0.0.0', port=5000)
    else:
        print("⚠️  Running without HTTPS - camera/microphone won't work")
        print("💡 To fix this, run: openssl req -x509 -newkey rsa:4096 -nodes -out cert.pem -keyout key.pem -days 365 -subj '/C=US/ST=State/L=City/O=Organization/CN=localhost'")
        print("🚀 Interview Platform running on http://localhost:5000")
        app.run(debug=True, host='0.0.0.0', port=5000)
