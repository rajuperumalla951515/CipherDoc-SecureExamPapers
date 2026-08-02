import os
import logging
from flask import Flask, request
from werkzeug.middleware.proxy_fix import ProxyFix
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.secret_key = os.environ.get('SESSION_SECRET', 'secure-system-key-2024')
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

app_root = os.path.dirname(os.path.abspath(__file__))
uploads_path = os.path.join(app_root, 'uploads')
keys_path = os.path.join(app_root, 'keys')

try:
    os.makedirs(uploads_path, exist_ok=True)
    os.makedirs(keys_path, exist_ok=True)
except OSError:
    # Read-only filesystem fallback (e.g. Vercel deployment)
    uploads_path = '/tmp/uploads'
    keys_path = '/tmp/keys'
    os.makedirs(uploads_path, exist_ok=True)
    os.makedirs(keys_path, exist_ok=True)

# Supabase client initialization
supabase_url = os.environ.get('SUPABASE_URL')
supabase_key = os.environ.get('SUPABASE_KEY')

if not supabase_url or not supabase_key:
    # Set to None to prevent fatal startup crash on initial build/deploy
    supabase = None
else:
    try:
        supabase: Client = create_client(supabase_url, supabase_key)
    except Exception as e:
        logging.error(f"Failed to initialize Supabase client: {e}")
        supabase = None

app.config['UPLOAD_FOLDER'] = uploads_path
app.config['KEYS_FOLDER'] = keys_path
app.config['SUPABASE'] = supabase

from routes import auth, ea, aef
app.register_blueprint(auth.bp)
app.register_blueprint(ea.bp)
app.register_blueprint(aef.bp)

from flask import session, render_template

@app.before_request
def check_config():
    if supabase is None:
        if request.endpoint == 'static' or request.path.startswith('/static/'):
            return
        return render_template('config_error.html'), 503

@app.context_processor
def inject_user():
    user_id = session.get('user_id')
    if user_id and supabase:
        res = supabase.table('users').select('*').eq('id', user_id).execute()
        if res.data:
            return dict(current_user=res.data[0])
    return dict(current_user=None)

@app.route('/update-profile', methods=['POST'])
def update_profile():
    if 'user_id' not in session:
        return {"success": False, "message": "Unauthorized"}, 401
    
    user_id = session['user_id']
    user_type = session['user_type']
    
    update_data = {
        'full_name': request.form.get('full_name'),
        'email': request.form.get('email'),
        'department': request.form.get('department'),
        'contact_number': request.form.get('contact_number')
    }
    
    if user_type == 'EA':
        update_data.update({
            'designation': request.form.get('designation'),
            'office_location': request.form.get('office_location')
        })
    else:
        update_data.update({
            'subject_expertise': request.form.get('subject_expertise'),
            'qualification': request.form.get('qualification'),
            'experience_years': request.form.get('experience_years')
        })
    
    supabase.table('users').update(update_data).eq('id', user_id).execute()
    
    # Sync session
    session['user_name'] = update_data['full_name']
    session['user_email'] = update_data['email']
    
    return {"success": True, "message": "Profile updated successfully"}

from flask import redirect, url_for

@app.route('/')
def index():
    return redirect(url_for('auth.home'))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

