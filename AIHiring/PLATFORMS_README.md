# Separate Platforms Setup

The application has been separated into two independent platforms:

## 1. Resume Analyzer Platform
**File:** `resume_analyzer_app.py`  
**Port:** 5001  
**URL:** http://localhost:5001

### Features:
- Upload and analyze resumes (PDF, DOCX, TXT)
- AI-powered skill extraction
- Experience and education analysis
- Score calculation and recommendations
- No navbar - standalone platform

### To Run:
```bash
python resume_analyzer_app.py
```

Then access at: http://localhost:5001

---

## 2. Interview Platform
**File:** `interview_app.py`  
**Port:** 5000 (HTTPS)  
**URL:** https://localhost:5000

### Features:
- AI-powered video interviews
- Real-time question generation
- Voice and video analysis
- Physical/behavioral analysis
- Interview results and feedback
- No navbar - standalone platform

### To Run:
```bash
python interview_app.py
```

Then access at: https://localhost:5000 (HTTPS required for camera/microphone)

---

## Key Changes:

1. **Separated Applications**: Two independent Flask apps instead of one combined app
2. **No Navbar**: Both platforms run without navigation bars - they are completely separate
3. **Different Base Templates**: 
   - `base_resume.html` - for resume analyzer platform
   - `base_interview.html` - for interview platform
4. **Independent Sessions**: Each platform maintains its own session data
5. **Removed Cross-Platform Links**: No links between platforms in the UI

## Notes:

- The original `app.py` still exists but is deprecated
- The original `base.html` has been updated to remove navbar
- Both platforms can run simultaneously on different ports
- Each platform is completely independent and can be deployed separately
