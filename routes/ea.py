from flask import Blueprint, render_template, request, redirect, url_for, session, flash, send_file
from functools import wraps
from tinydb import Query
from datetime import datetime
import uuid
import os
import tempfile
import re
from encryption import generate_rsa_key_pair, encrypt_file, encrypt_text, decrypt_text

bp = Blueprint('ea', __name__, url_prefix='/ea')

def get_db():
    from app import users_table, papers_table, keys_table, authorizations_table, logs_table
    return users_table, papers_table, keys_table, authorizations_table, logs_table


def ea_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('user_type') != 'EA':
            flash('Please login as Examination Administrator to access this page.', 'error')
            return redirect(url_for('auth.ea_login'))
        return f(*args, **kwargs)
    return decorated_function


def log_activity(user_id, action, details=""):
    _, _, _, _, logs_table = get_db()
    logs_table.insert({
        'id': str(uuid.uuid4()),
        'user_id': user_id,
        'user_type': 'EA',
        'action': action,
        'details': details,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })


def has_visible_content(value):
    if not value:
        return False
    text = re.sub(r'<[^>]+>', '', value)
    text = text.replace('&nbsp;', ' ').strip()
    return bool(text)


@bp.route('/dashboard')
@ea_required
def dashboard():
    users_table, papers_table, keys_table, authorizations_table, logs_table = get_db()
    User = Query()
    
    stats = {
        'total_papers': len(papers_table.all()),
        'total_faculty': len(users_table.search(User.user_type == 'AEF')),
        'authorized_faculty': len(users_table.search((User.user_type == 'AEF') & (User.is_authorized == True))),
        'total_keys': len(keys_table.all()),
        'recent_logs': logs_table.all()[-5:][::-1] if logs_table.all() else []
    }
    
    return render_template('ea/dashboard.html', stats=stats)


@bp.route('/create-paper', methods=['GET', 'POST'])
@ea_required
def create_paper():
    _, papers_table, keys_table, _, _ = get_db()
    Key = Query()
    
    keys = keys_table.all()
    
    if request.method == 'POST':
        if not keys:
            flash('Please generate RSA keys first before creating encrypted papers!', 'error')
            return redirect(url_for('ea.manage_keys'))
        
        selected_key_id = request.form.get('key_id')
        selected_key = keys_table.search(Key.id == selected_key_id)
        
        if not selected_key:
            flash('Selected RSA key not found. Please choose a valid key.', 'error')
            return redirect(url_for('ea.create_paper'))
        
        public_key = selected_key[0]['public_key']
        
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
            'key_id': selected_key[0]['id'],
            'created_by': session['user_id'],
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'status': 'encrypted',
            'is_active': True
        }
        
        papers_table.insert(paper_data)
        log_activity(session['user_id'], 'CREATE_PAPER', f"Created encrypted paper: {exam_name}")
        flash('Question paper created and encrypted successfully!', 'success')
        return redirect(url_for('ea.manage_papers'))
    
    return render_template('ea/create_paper.html', keys=keys)


@bp.route('/manage-papers')
@ea_required
def manage_papers():
    _, papers_table, _, _, _ = get_db()
    papers = papers_table.all()
    return render_template('ea/manage_papers.html', papers=papers)


@bp.route('/edit-paper/<paper_id>', methods=['GET', 'POST'])
@ea_required
def edit_paper(paper_id):
    _, papers_table, keys_table, _, _ = get_db()
    Paper = Query()
    Key = Query()
    
    paper = papers_table.search(Paper.id == paper_id)
    if not paper:
        flash('Paper not found!', 'error')
        return redirect(url_for('ea.manage_papers'))
    
    paper = paper[0]
    keys = keys_table.all()
    
    # Decrypt content for GET request
    if request.method == 'GET':
        paper_key = keys_table.search(Key.id == paper['key_id'])
        if paper_key:
            private_key = paper_key[0]['private_key']
            try:
                paper['decrypted_questions'] = decrypt_text(paper['encrypted_questions'], paper['encrypted_key'], private_key)
                paper['decrypted_instructions'] = decrypt_text(paper['encrypted_instructions'], paper['instructions_key'], private_key)
            except Exception as e:
                flash(f'Failed to decrypt paper content. Error: {e}', 'warning')

    if request.method == 'POST':
        selected_key_id = request.form.get('key_id')
        selected_key = keys_table.search(Key.id == selected_key_id)
        if not selected_key:
            flash('Selected RSA key not found.', 'error')
            return redirect(url_for('ea.edit_paper', paper_id=paper_id))
        
        public_key = selected_key[0]['public_key']
        questions = request.form.get('questions')
        instructions = request.form.get('instructions')

        if not has_visible_content(instructions) or not has_visible_content(questions):
            flash('Instructions and Questions are required to update a paper.', 'error')
            return redirect(url_for('ea.edit_paper', paper_id=paper_id))
        
        encrypted_questions, encrypted_key = encrypt_text(questions, public_key)
        encrypted_instructions, instr_key = encrypt_text(instructions, public_key)
        
        papers_table.update({
            'exam_name': request.form.get('exam_name'),
            'subject': request.form.get('subject'),
            'exam_date': request.form.get('exam_date'),
            'exam_duration': request.form.get('exam_duration'),
            'total_marks': request.form.get('total_marks'),
            'encrypted_questions': encrypted_questions,
            'encrypted_key': encrypted_key,
            'encrypted_instructions': encrypted_instructions,
            'instructions_key': instr_key,
            'key_id': selected_key[0]['id'],
            'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }, Paper.id == paper_id)
        
        log_activity(session['user_id'], 'EDIT_PAPER', f"Edited paper: {request.form.get('exam_name')}")
        flash('Paper updated successfully!', 'success')
        return redirect(url_for('ea.manage_papers'))
    
    return render_template('ea/edit_paper.html', paper=paper, keys=keys)


@bp.route('/delete-paper/<paper_id>')
@ea_required
def delete_paper(paper_id):
    _, papers_table, _, authorizations_table, _ = get_db()
    Paper = Query()
    Auth = Query()
    
    paper = papers_table.search(Paper.id == paper_id)
    if paper:
        papers_table.remove(Paper.id == paper_id)
        authorizations_table.remove(Auth.paper_id == paper_id)
        log_activity(session['user_id'], 'DELETE_PAPER', f"Deleted paper: {paper[0]['exam_name']}")
        flash('Paper deleted successfully!', 'success')
    
    return redirect(url_for('ea.manage_papers'))


@bp.route('/manage-keys', methods=['GET', 'POST'])
@ea_required
def manage_keys():
    _, _, keys_table, _, _ = get_db()
    Key = Query()
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'generate':
            key_name = request.form.get('key_name')
            private_key, public_key = generate_rsa_key_pair()
            
            keys_table.update({'is_active': False}, Key.is_active == True)
            
            key_data = {
                'id': str(uuid.uuid4()),
                'key_name': key_name,
                'private_key': private_key,
                'public_key': public_key,
                'created_by': session['user_id'],
                'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'is_active': True
            }
            
            keys_table.insert(key_data)
            log_activity(session['user_id'], 'GENERATE_KEY', f"Generated new RSA key pair: {key_name}")
            flash('New RSA key pair generated successfully!', 'success')
        
        elif action == 'activate':
            key_id = request.form.get('key_id')
            keys_table.update({'is_active': False}, Key.is_active == True)
            keys_table.update({'is_active': True}, Key.id == key_id)
            log_activity(session['user_id'], 'ACTIVATE_KEY', f"Activated key: {key_id}")
            flash('Key activated successfully!', 'success')
        
        elif action == 'delete':
            key_id = request.form.get('key_id')
            key = keys_table.search(Key.id == key_id)
            if key and not key[0]['is_active']:
                keys_table.remove(Key.id == key_id)
                log_activity(session['user_id'], 'DELETE_KEY', f"Deleted key: {key_id}")
                flash('Key deleted successfully!', 'success')
            else:
                flash('Cannot delete active key!', 'error')
        
        return redirect(url_for('ea.manage_keys'))
    
    keys = keys_table.all()
    return render_template('ea/manage_keys.html', keys=keys)


@bp.route('/download-key/<key_id>/<key_type>')
@ea_required
def download_key(key_id, key_type):
    _, _, keys_table, _, _ = get_db()
    Key = Query()
    
    key = keys_table.search(Key.id == key_id)
    if not key:
        flash('Key not found!', 'error')
        return redirect(url_for('ea.manage_keys'))
    
    key = key[0]
    
    if key_type == 'private':
        content = key['private_key']
        filename = f"{key['key_name']}_private.pem"
    else:
        content = key['public_key']
        filename = f"{key['key_name']}_public.pem"
    
    temp_path = os.path.join(tempfile.gettempdir(), filename)
    with open(temp_path, 'w') as f:
        f.write(content)
    
    log_activity(session['user_id'], 'DOWNLOAD_KEY', f"Downloaded {key_type} key: {key['key_name']}")
    return send_file(temp_path, as_attachment=True, download_name=filename)


@bp.route('/authorize-faculty', methods=['GET', 'POST'])
@ea_required
def authorize_faculty():
    users_table, papers_table, _, authorizations_table, _ = get_db()
    User = Query()
    Auth = Query()
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'authorize':
            faculty_id = request.form.get('faculty_id')
            paper_ids = request.form.getlist('paper_ids')
            
            faculty = users_table.search(User.id == faculty_id)
            if faculty:
                users_table.update({'is_authorized': True}, User.id == faculty_id)
                
                authorizations_table.remove((Auth.faculty_id == faculty_id))
                
                for paper_id in paper_ids:
                    auth_data = {
                        'id': str(uuid.uuid4()),
                        'faculty_id': faculty_id,
                        'paper_id': paper_id,
                        'authorized_by': session['user_id'],
                        'authorized_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'is_active': True
                    }
                    authorizations_table.insert(auth_data)
                
                log_activity(session['user_id'], 'AUTHORIZE_FACULTY', 
                           f"Authorized faculty {faculty[0]['full_name']} for {len(paper_ids)} papers")
                flash(f"Faculty {faculty[0]['full_name']} authorized successfully for {len(paper_ids)} exam papers!", 'success')
        
        elif action == 'revoke':
            faculty_id = request.form.get('faculty_id')
            faculty = users_table.search(User.id == faculty_id)
            if faculty:
                users_table.update({'is_authorized': False}, User.id == faculty_id)
                authorizations_table.remove(Auth.faculty_id == faculty_id)
                log_activity(session['user_id'], 'REVOKE_AUTHORIZATION', 
                           f"Revoked authorization for faculty {faculty[0]['full_name']}")
                flash(f"Authorization revoked for {faculty[0]['full_name']}!", 'success')
        
        return redirect(url_for('ea.authorize_faculty'))
    
    faculty_list = users_table.search(User.user_type == 'AEF')
    papers = papers_table.all()
    
    faculty_with_auth = []
    for faculty in faculty_list:
        auth = authorizations_table.search(Auth.faculty_id == faculty['id'])
        authorized_papers = [a['paper_id'] for a in auth]
        faculty['authorized_papers'] = authorized_papers
        faculty_with_auth.append(faculty)
    
    return render_template('ea/authorize_faculty.html', faculty_list=faculty_with_auth, papers=papers)


@bp.route('/access-logs')
@ea_required
def access_logs():
    users_table, _, _, _, logs_table = get_db()
    User = Query()
    
    logs = logs_table.all()
    logs = sorted(logs, key=lambda x: x['timestamp'], reverse=True)
    
    user_map = {}
    for user in users_table.all():
        user_map[user['id']] = user['full_name']
    
    for log in logs:
        log['user_name'] = user_map.get(log['user_id'], 'Unknown User')
    
    return render_template('ea/access_logs.html', logs=logs)


@bp.route('/view-paper/<paper_id>')
@ea_required
def view_paper(paper_id):
    _, papers_table, keys_table, _, _ = get_db()
    Paper = Query()
    Key = Query()

    paper = papers_table.search(Paper.id == paper_id)
    if not paper:
        flash('Paper not found!', 'error')
        return redirect(url_for('ea.manage_papers'))
    
    paper = paper[0]
    
    # Find the key used for this paper
    paper_key = keys_table.search(Key.id == paper['key_id'])
    if not paper_key:
        flash('Encryption key for this paper not found!', 'error')
        return redirect(url_for('ea.manage_papers'))
        
    private_key = paper_key[0]['private_key']
    
    try:
        decrypted_questions = decrypt_text(paper['encrypted_questions'], paper['encrypted_key'], private_key)
        decrypted_instructions = decrypt_text(paper['encrypted_instructions'], paper['instructions_key'], private_key)
    except Exception as e:
        flash(f'Failed to decrypt paper. The key may be incorrect or the data corrupted. Error: {e}', 'error')
        decrypted_questions = "Decryption Failed."
        decrypted_instructions = "Decryption Failed."

    paper['decrypted_questions'] = decrypted_questions
    paper['decrypted_instructions'] = decrypted_instructions
    
    log_activity(session['user_id'], 'VIEW_PAPER', f"Viewed paper: {paper['exam_name']}")
    
    return render_template('ea/view_paper.html', paper=paper)
