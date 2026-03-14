from flask import Flask, render_template, request, jsonify, session
import os
import secrets
from config import Config
from models.resume_analyzer import ResumeAnalyzer
from utils.helpers import allowed_file

app = Flask(__name__)
app.config.from_object(Config)

# Create upload directory
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize Resume Analyzer
resume_analyzer = ResumeAnalyzer()

# Add CORS headers
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

@app.route('/')
def index():
    return render_template('resume_analysis.html')

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

if __name__ == '__main__':
    print("🚀 Resume Analyzer Platform running on http://localhost:5001")
    print("📄 Access at: http://localhost:5001")
    app.run(debug=True, host='0.0.0.0', port=5001)
