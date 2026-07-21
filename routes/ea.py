from flask import Blueprint, render_template, request, redirect, url_for, session, flash, send_file
from functools import wraps
from datetime import datetime
import uuid
import os
import tempfile
import re
from encryption import generate_rsa_key_pair, encrypt_file, encrypt_text, decrypt_text

bp = Blueprint('ea', __name__, url_prefix='/ea')

def get_db():
    from app import supabase
    return supabase


def ea_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('user_type') != 'EA':
            flash('Please login as Examination Administrator to access this page.', 'error')
            return redirect(url_for('auth.ea_login'))
        return f(*args, **kwargs)
    return decorated_function


def log_activity(supabase, user_id, action, details=""):
    supabase.table('access_logs').insert({
        'id': str(uuid.uuid4()),
        'user_id': user_id,
        'user_type': 'EA',
        'action': action,
        'details': details,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }).execute()


def has_visible_content(value):
    if not value:
        return False
    text = re.sub(r'<[^>]+>', '', value)
    text = text.replace('&nbsp;', ' ').strip()
    return bool(text)


@bp.route('/dashboard')
@ea_required
def dashboard():
    supabase = get_db()
    
    papers_res = supabase.table('papers').select('id').execute()
    aef_res = supabase.table('users').select('id').eq('user_type', 'AEF').execute()
    auth_aef_res = supabase.table('users').select('id').eq('user_type', 'AEF').eq('is_authorized', True).execute()
    keys_res = supabase.table('keys').select('id').execute()
    logs_res = supabase.table('access_logs').select('*').order('timestamp', desc=True).limit(5).execute()
    
    stats = {
        'total_papers': len(papers_res.data),
        'total_faculty': len(aef_res.data),
        'authorized_faculty': len(auth_aef_res.data),
        'total_keys': len(keys_res.data),
        'recent_logs': logs_res.data
    }
    
    return render_template('ea/dashboard.html', stats=stats)


@bp.route('/create-paper', methods=['GET', 'POST'])
@ea_required
def create_paper():
    supabase = get_db()
    
    keys_res = supabase.table('keys').select('*').execute()
    keys = keys_res.data
    
    if request.method == 'POST':
        if not keys:
            flash('Please generate RSA keys first before creating encrypted papers!', 'error')
            return redirect(url_for('ea.manage_keys'))
        
        selected_key_id = request.form.get('key_id')
        key_res = supabase.table('keys').select('*').eq('id', selected_key_id).execute()
        
        if not key_res.data:
            flash('Selected RSA key not found. Please choose a valid key.', 'error')
            return redirect(url_for('ea.create_paper'))
        
        selected_key = key_res.data[0]
        public_key = selected_key['public_key']
        
        exam_name = request.form.get('exam_name')
        subject = request.form.get('subject')
        exam_date = request.form.get('exam_date')
        exam_duration = request.form.get('exam_duration')
        total_marks = request.form.get('total_marks')
        instructions = request.form.get('instructions')
        questions = request.form.get('questions')

        if not has_visible_content(instructions) or not has_visible_content(questions):
            flash('Instructions and Questions are required to create a paper.', 'error')
            return redirect(url_for('ea.create_paper'))
        
        encrypted_questions, encrypted_key = encrypt_text(questions, public_key)
        encrypted_instructions, instr_key = encrypt_text(instructions, public_key)
        
        paper_data = {
            'id': str(uuid.uuid4()),
            'exam_name': exam_name,
            'subject': subject,
            'exam_date': exam_date,
            'exam_duration': exam_duration,
            'total_marks': total_marks,
            'encrypted_questions': encrypted_questions,
            'encrypted_key': encrypted_key,
            'encrypted_instructions': encrypted_instructions,
            'instructions_key': instr_key,
            'key_id': selected_key['id'],
            'created_by': session['user_id'],
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'status': 'encrypted',
            'is_active': True
        }
        
        supabase.table('papers').insert(paper_data).execute()
        log_activity(supabase, session['user_id'], 'CREATE_PAPER', f"Created encrypted paper: {exam_name}")
        flash('Question paper created and encrypted successfully!', 'success')
        return redirect(url_for('ea.manage_papers'))
    
    return render_template('ea/create_paper.html', keys=keys)


@bp.route('/manage-papers')
@ea_required
def manage_papers():
    supabase = get_db()
    papers = supabase.table('papers').select('*').execute().data
    return render_template('ea/manage_papers.html', papers=papers)


@bp.route('/edit-paper/<paper_id>', methods=['GET', 'POST'])
@ea_required
def edit_paper(paper_id):
    supabase = get_db()
    
    paper_res = supabase.table('papers').select('*').eq('id', paper_id).execute()
    if not paper_res.data:
        flash('Paper not found!', 'error')
        return redirect(url_for('ea.manage_papers'))
    
    paper = paper_res.data[0]
    keys = supabase.table('keys').select('*').execute().data
    
    # Decrypt content for GET request
    if request.method == 'GET':
        key_res = supabase.table('keys').select('*').eq('id', paper['key_id']).execute()
        if key_res.data:
            private_key = key_res.data[0]['private_key']
            try:
                paper['decrypted_questions'] = decrypt_text(paper['encrypted_questions'], paper['encrypted_key'], private_key)
                paper['decrypted_instructions'] = decrypt_text(paper['encrypted_instructions'], paper['instructions_key'], private_key)
            except Exception as e:
                flash(f'Failed to decrypt paper content. Error: {e}', 'warning')

    if request.method == 'POST':
        selected_key_id = request.form.get('key_id')
        key_res = supabase.table('keys').select('*').eq('id', selected_key_id).execute()
        if not key_res.data:
            flash('Selected RSA key not found.', 'error')
            return redirect(url_for('ea.edit_paper', paper_id=paper_id))
        
        selected_key = key_res.data[0]
        public_key = selected_key['public_key']
        questions = request.form.get('questions')
        instructions = request.form.get('instructions')

        if not has_visible_content(instructions) or not has_visible_content(questions):
            flash('Instructions and Questions are required to update a paper.', 'error')
            return redirect(url_for('ea.edit_paper', paper_id=paper_id))
        
        encrypted_questions, encrypted_key = encrypt_text(questions, public_key)
        encrypted_instructions, instr_key = encrypt_text(instructions, public_key)
        
        supabase.table('papers').update({
            'exam_name': request.form.get('exam_name'),
            'subject': request.form.get('subject'),
            'exam_date': request.form.get('exam_date'),
            'exam_duration': request.form.get('exam_duration'),
            'total_marks': request.form.get('total_marks'),
            'encrypted_questions': encrypted_questions,
            'encrypted_key': encrypted_key,
            'encrypted_instructions': encrypted_instructions,
            'instructions_key': instr_key,
            'key_id': selected_key['id'],
            'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }).eq('id', paper_id).execute()
        
        log_activity(supabase, session['user_id'], 'EDIT_PAPER', f"Edited paper: {request.form.get('exam_name')}")
        flash('Paper updated successfully!', 'success')
        return redirect(url_for('ea.manage_papers'))
    
    return render_template('ea/edit_paper.html', paper=paper, keys=keys)


@bp.route('/delete-paper/<paper_id>')
@ea_required
def delete_paper(paper_id):
    supabase = get_db()
    
    paper_res = supabase.table('papers').select('exam_name').eq('id', paper_id).execute()
    if paper_res.data:
        exam_name = paper_res.data[0]['exam_name']
        supabase.table('papers').delete().eq('id', paper_id).execute()
        supabase.table('authorizations').delete().eq('paper_id', paper_id).execute()
        log_activity(supabase, session['user_id'], 'DELETE_PAPER', f"Deleted paper: {exam_name}")
        flash('Paper deleted successfully!', 'success')
    
    return redirect(url_for('ea.manage_papers'))


@bp.route('/manage-keys', methods=['GET', 'POST'])
@ea_required
def manage_keys():
    supabase = get_db()
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'generate':
            key_name = request.form.get('key_name')
            private_key, public_key = generate_rsa_key_pair()
            
            # Deactivate all existing keys
            supabase.table('keys').update({'is_active': False}).eq('is_active', True).execute()
            
            key_data = {
                'id': str(uuid.uuid4()),
                'key_name': key_name,
                'private_key': private_key,
                'public_key': public_key,
                'created_by': session['user_id'],
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'is_active': True
            }
            
            supabase.table('keys').insert(key_data).execute()
            log_activity(supabase, session['user_id'], 'GENERATE_KEY', f"Generated new RSA key pair: {key_name}")
            flash('New RSA key pair generated successfully!', 'success')
        
        elif action == 'activate':
            key_id = request.form.get('key_id')
            supabase.table('keys').update({'is_active': False}).eq('is_active', True).execute()
            supabase.table('keys').update({'is_active': True}).eq('id', key_id).execute()
            log_activity(supabase, session['user_id'], 'ACTIVATE_KEY', f"Activated key: {key_id}")
            flash('Key activated successfully!', 'success')
        
        elif action == 'delete':
            key_id = request.form.get('key_id')
            key_res = supabase.table('keys').select('*').eq('id', key_id).execute()
            if key_res.data and not key_res.data[0]['is_active']:
                supabase.table('keys').delete().eq('id', key_id).execute()
                log_activity(supabase, session['user_id'], 'DELETE_KEY', f"Deleted key: {key_id}")
                flash('Key deleted successfully!', 'success')
            else:
                flash('Cannot delete active key!', 'error')
        
        return redirect(url_for('ea.manage_keys'))
    
    keys = supabase.table('keys').select('*').execute().data
    return render_template('ea/manage_keys.html', keys=keys)


@bp.route('/download-key/<key_id>/<key_type>')
@ea_required
def download_key(key_id, key_type):
    supabase = get_db()
    
    key_res = supabase.table('keys').select('*').eq('id', key_id).execute()
    if not key_res.data:
        flash('Key not found!', 'error')
        return redirect(url_for('ea.manage_keys'))
    
    key = key_res.data[0]
    
    if key_type == 'private':
        content = key['private_key']
        filename = f"{key['key_name']}_private.pem"
    else:
        content = key['public_key']
        filename = f"{key['key_name']}_public.pem"
    
    temp_path = os.path.join(tempfile.gettempdir(), filename)
    with open(temp_path, 'w') as f:
        f.write(content)
    
    log_activity(supabase, session['user_id'], 'DOWNLOAD_KEY', f"Downloaded {key_type} key: {key['key_name']}")
    return send_file(temp_path, as_attachment=True, download_name=filename)


@bp.route('/authorize-faculty', methods=['GET', 'POST'])
@ea_required
def authorize_faculty():
    supabase = get_db()
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'authorize':
            faculty_id = request.form.get('faculty_id')
            paper_ids = request.form.getlist('paper_ids')
            
            faculty_res = supabase.table('users').select('*').eq('id', faculty_id).execute()
            if faculty_res.data:
                faculty = faculty_res.data[0]
                supabase.table('users').update({'is_authorized': True}).eq('id', faculty_id).execute()
                supabase.table('authorizations').delete().eq('faculty_id', faculty_id).execute()
                
                for paper_id in paper_ids:
                    auth_data = {
                        'id': str(uuid.uuid4()),
                        'faculty_id': faculty_id,
                        'paper_id': paper_id,
                        'authorized_by': session['user_id'],
                        'authorized_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'is_active': True
                    }
                    supabase.table('authorizations').insert(auth_data).execute()
                
                log_activity(supabase, session['user_id'], 'AUTHORIZE_FACULTY',
                           f"Authorized faculty {faculty['full_name']} for {len(paper_ids)} papers")
                flash(f"Faculty {faculty['full_name']} authorized successfully for {len(paper_ids)} exam papers!", 'success')
        
        elif action == 'revoke':
            faculty_id = request.form.get('faculty_id')
            faculty_res = supabase.table('users').select('*').eq('id', faculty_id).execute()
            if faculty_res.data:
                faculty = faculty_res.data[0]
                supabase.table('users').update({'is_authorized': False}).eq('id', faculty_id).execute()
                supabase.table('authorizations').delete().eq('faculty_id', faculty_id).execute()
                log_activity(supabase, session['user_id'], 'REVOKE_AUTHORIZATION',
                           f"Revoked authorization for faculty {faculty['full_name']}")
                flash(f"Authorization revoked for {faculty['full_name']}!", 'success')
        
        return redirect(url_for('ea.authorize_faculty'))
    
    faculty_list = supabase.table('users').select('*').eq('user_type', 'AEF').execute().data
    papers = supabase.table('papers').select('*').execute().data
    
    faculty_with_auth = []
    for faculty in faculty_list:
        auth_res = supabase.table('authorizations').select('paper_id').eq('faculty_id', faculty['id']).execute()
        faculty['authorized_papers'] = [a['paper_id'] for a in auth_res.data]
        faculty_with_auth.append(faculty)
    
    return render_template('ea/authorize_faculty.html', faculty_list=faculty_with_auth, papers=papers)


@bp.route('/access-logs')
@ea_required
def access_logs():
    supabase = get_db()
    
    logs = supabase.table('access_logs').select('*').order('timestamp', desc=True).execute().data
    users_res = supabase.table('users').select('id, full_name').execute()
    user_map = {u['id']: u['full_name'] for u in users_res.data}
    
    for log in logs:
        log['user_name'] = user_map.get(log['user_id'], 'Unknown User')
    
    return render_template('ea/access_logs.html', logs=logs)


@bp.route('/view-paper/<paper_id>')
@ea_required
def view_paper(paper_id):
    supabase = get_db()

    paper_res = supabase.table('papers').select('*').eq('id', paper_id).execute()
    if not paper_res.data:
        flash('Paper not found!', 'error')
        return redirect(url_for('ea.manage_papers'))
    
    paper = paper_res.data[0]
    
    key_res = supabase.table('keys').select('*').eq('id', paper['key_id']).execute()
    if not key_res.data:
        flash('Encryption key for this paper not found!', 'error')
        return redirect(url_for('ea.manage_papers'))
        
    private_key = key_res.data[0]['private_key']
    
    try:
        decrypted_questions = decrypt_text(paper['encrypted_questions'], paper['encrypted_key'], private_key)
        decrypted_instructions = decrypt_text(paper['encrypted_instructions'], paper['instructions_key'], private_key)
    except Exception as e:
        flash(f'Failed to decrypt paper. The key may be incorrect or the data corrupted. Error: {e}', 'error')
        decrypted_questions = "Decryption Failed."
        decrypted_instructions = "Decryption Failed."

    paper['decrypted_questions'] = decrypted_questions
    paper['decrypted_instructions'] = decrypted_instructions
    
    log_activity(supabase, session['user_id'], 'VIEW_PAPER', f"Viewed paper: {paper['exam_name']}")
    
    return render_template('ea/view_paper.html', paper=paper)
