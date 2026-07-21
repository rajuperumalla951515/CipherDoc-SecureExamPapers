from flask import Blueprint, render_template, request, redirect, url_for, session, flash, make_response
from functools import wraps
from datetime import datetime
import uuid
from encryption import decrypt_text

bp = Blueprint('aef', __name__, url_prefix='/aef')

def get_db():
    from app import supabase
    return supabase


def aef_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('user_type') != 'AEF':
            flash('Please login as Authorized Examination Faculty to access this page.', 'error')
            return redirect(url_for('auth.aef_login'))
        return f(*args, **kwargs)
    return decorated_function


def log_activity(supabase, user_id, action, details=""):
    supabase.table('access_logs').insert({
        'id': str(uuid.uuid4()),
        'user_id': user_id,
        'user_type': 'AEF',
        'action': action,
        'details': details,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }).execute()


@bp.route('/dashboard')
@aef_required
def dashboard():
    supabase = get_db()
    
    user_res = supabase.table('users').select('*').eq('id', session['user_id']).execute()
    is_authorized = user_res.data[0]['is_authorized'] if user_res.data else False
    
    authorized_papers = []
    if is_authorized:
        auth_res = supabase.table('authorizations').select('paper_id').eq('faculty_id', session['user_id']).execute()
        paper_ids = [a['paper_id'] for a in auth_res.data]
        
        for paper_id in paper_ids:
            paper_res = supabase.table('papers').select('*').eq('id', paper_id).execute()
            if paper_res.data:
                authorized_papers.append(paper_res.data[0])
    
    stats = {
        'is_authorized': is_authorized,
        'total_authorized': len(authorized_papers),
        'papers': authorized_papers
    }
    
    return render_template('aef/dashboard.html', stats=stats)


@bp.route('/view-exams')
@aef_required
def view_exams():
    supabase = get_db()
    
    user_res = supabase.table('users').select('is_authorized').eq('id', session['user_id']).execute()
    if not user_res.data or not user_res.data[0]['is_authorized']:
        flash('You are not authorized to view exam papers. Please contact an administrator.', 'error')
        return redirect(url_for('aef.dashboard'))
    
    auth_res = supabase.table('authorizations').select('paper_id').eq('faculty_id', session['user_id']).execute()
    paper_ids = [a['paper_id'] for a in auth_res.data]
    
    authorized_papers = []
    for paper_id in paper_ids:
        paper_res = supabase.table('papers').select('*').eq('id', paper_id).execute()
        if paper_res.data:
            authorized_papers.append(paper_res.data[0])
    
    log_activity(supabase, session['user_id'], 'VIEW_EXAMS', f"Viewed {len(authorized_papers)} authorized exams")
    return render_template('aef/view_exams.html', papers=authorized_papers)


@bp.route('/decrypt-paper/<paper_id>', methods=['GET', 'POST'])
@aef_required
def decrypt_paper(paper_id):
    supabase = get_db()
    
    user_res = supabase.table('users').select('is_authorized').eq('id', session['user_id']).execute()
    if not user_res.data or not user_res.data[0]['is_authorized']:
        flash('You are not authorized to decrypt exam papers.', 'error')
        return redirect(url_for('aef.dashboard'))
    
    auth_res = supabase.table('authorizations').select('id').eq('faculty_id', session['user_id']).eq('paper_id', paper_id).execute()
    if not auth_res.data:
        flash('You are not authorized to access this exam paper.', 'error')
        return redirect(url_for('aef.view_exams'))
    
    paper_res = supabase.table('papers').select('*').eq('id', paper_id).execute()
    if not paper_res.data:
        flash('Exam paper not found!', 'error')
        return redirect(url_for('aef.view_exams'))
    
    paper = paper_res.data[0]
    decrypted_data = None
    
    if request.method == 'POST':
        key_res = supabase.table('keys').select('private_key').eq('id', paper['key_id']).execute()
        if not key_res.data:
            flash('Encryption key not found! Contact administrator.', 'error')
            return redirect(url_for('aef.view_exams'))
        
        private_key = key_res.data[0]['private_key']
        
        try:
            decrypted_questions = decrypt_text(
                paper['encrypted_questions'],
                paper['encrypted_key'],
                private_key
            )
            decrypted_instructions = decrypt_text(
                paper['encrypted_instructions'],
                paper['instructions_key'],
                private_key
            )
            
            decrypted_data = {
                'questions': decrypted_questions,
                'instructions': decrypted_instructions
            }
            
            session[f'decrypted_{paper_id}'] = decrypted_data
            
            log_activity(supabase, session['user_id'], 'DECRYPT_PAPER',
                        f"Decrypted paper: {paper['exam_name']}")
            flash('Paper decrypted successfully!', 'success')
            
        except Exception as e:
            flash(f'Decryption failed: {str(e)}', 'error')
            log_activity(supabase, session['user_id'], 'DECRYPT_FAILED',
                        f"Failed to decrypt: {paper['exam_name']} - {str(e)}")
    
    else:
        decrypted_data = session.get(f'decrypted_{paper_id}')
    
    return render_template('aef/decrypt_paper.html', paper=paper, decrypted_data=decrypted_data)


@bp.route('/download-paper/<paper_id>')
@aef_required
def download_paper(paper_id):
    supabase = get_db()
    
    user_res = supabase.table('users').select('is_authorized').eq('id', session['user_id']).execute()
    if not user_res.data or not user_res.data[0]['is_authorized']:
        flash('You are not authorized to download exam papers.', 'error')
        return redirect(url_for('aef.dashboard'))
    
    auth_res = supabase.table('authorizations').select('id').eq('faculty_id', session['user_id']).eq('paper_id', paper_id).execute()
    if not auth_res.data:
        flash('You are not authorized to access this exam paper.', 'error')
        return redirect(url_for('aef.view_exams'))
    
    paper_res = supabase.table('papers').select('*').eq('id', paper_id).execute()
    if not paper_res.data:
        flash('Exam paper not found!', 'error')
        return redirect(url_for('aef.view_exams'))
    
    paper = paper_res.data[0]
    
    decrypted_data = session.get(f'decrypted_{paper_id}')
    if not decrypted_data:
        key_res = supabase.table('keys').select('private_key').eq('id', paper['key_id']).execute()
        if not key_res.data:
            flash('Encryption key not found!', 'error')
            return redirect(url_for('aef.view_exams'))
        
        private_key = key_res.data[0]['private_key']
        
        try:
            decrypted_questions = decrypt_text(
                paper['encrypted_questions'],
                paper['encrypted_key'],
                private_key
            )
            decrypted_instructions = decrypt_text(
                paper['encrypted_instructions'],
                paper['instructions_key'],
                private_key
            )
            decrypted_data = {
                'questions': decrypted_questions,
                'instructions': decrypted_instructions
            }
        except Exception as e:
            flash(f'Decryption failed: {str(e)}', 'error')
            return redirect(url_for('aef.view_exams'))
    
    content = f"""
================================================================================
                        EXAMINATION QUESTION PAPER
================================================================================

Exam Name: {paper['exam_name']}
Subject: {paper['subject']}
Date: {paper['exam_date']}
Duration: {paper['exam_duration']} minutes
Total Marks: {paper['total_marks']}

================================================================================
                              INSTRUCTIONS
================================================================================

{decrypted_data['instructions']}

================================================================================
                               QUESTIONS
================================================================================

{decrypted_data['questions']}

================================================================================
                           END OF QUESTION PAPER
================================================================================

Downloaded by: {session['user_name']}
Downloaded at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
    
    log_activity(supabase, session['user_id'], 'DOWNLOAD_PAPER', f"Downloaded paper: {paper['exam_name']}")
    
    response = make_response(content)
    response.headers['Content-Type'] = 'text/plain'
    response.headers['Content-Disposition'] = f'attachment; filename={paper["exam_name"].replace(" ", "_")}_question_paper.txt'
    
    return response
