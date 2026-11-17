# CipherDoc

CipherDoc is a Flask web application for creating, encrypting, authorizing, and
accessing examination papers. It provides separate workflows for:

- **Exam Authority (EA):** create and edit papers, manage RSA key pairs,
  authorize faculty, and review access logs.
- **Authorized Exam Faculty (AEF):** log in after authorization and decrypt
  papers they are allowed to access.

The application stores users, encrypted paper data, keys, authorizations, and
audit logs in Supabase. AES-GCM encrypts paper content and RSA-OAEP protects
the AES keys.

> **Project status:** This is an educational/project application. Before using
> it with real examination content, review the security notes below and add
> production controls such as email OTP delivery, rate limiting, CSRF
> protection, strict Supabase Row Level Security policies, secure secret
> management, and durable file/object storage.

## Features

- EA and AEF role-based access
- EA and AEF registration with generated employee/faculty IDs
- Password hashing using Werkzeug
- Flask session-based login and logout
- Exam-paper creation and editing
- AES-GCM content encryption
- RSA-2048 key-pair management and RSA-OAEP key wrapping
- Faculty authorization for individual papers
- Access/activity logging
- Supabase PostgreSQL data storage
- Local development and Vercel deployment entry points

## Technology

- Python 3.10+ recommended
- Flask 3.1
- Supabase Python client
- `cryptography`
- Jinja2 templates
- HTML/CSS/JavaScript
- Optional Node.js code in `backend/` (not the primary application entry
  point)

## Repository layout

```text
.
├── app.py                 # Flask application and configuration
├── api/index.py           # Vercel serverless entry point
├── encryption.py          # AES-GCM and RSA-OAEP helpers
├── routes/
│   ├── auth.py            # Home, registration, login, reset, logout
│   ├── ea.py              # Exam Authority workflows
│   └── aef.py             # Authorized Exam Faculty workflows
├── templates/             # Jinja2 pages and dashboards
├── static/                # Images, fonts, and frontend assets
├── supabase_schema.sql    # Database schema and indexes
├── data/                  # Local sample JSON data
├── requirements.txt       # Python dependencies
├── backend/               # Separate/incomplete Node.js scaffold
├── vercel.json             # Vercel routing configuration
└── run3120.bat            # Existing local environment helper
```

The application creates `keys/` and `uploads/` at runtime. They are ignored by
Git. On read-only deployments, the Flask app falls back to `/tmp/keys` and
`/tmp/uploads`; those files are temporary and should not be treated as
permanent storage.

## Prerequisites

Install the following before starting:

1. Python 3.10 or newer
2. Git
3. A Supabase project
4. Optional: Node.js 18+ and npm if you are working on `backend/`

Check the installed tools in PowerShell:

```powershell
python --version
git --version
```

## First-time setup on Windows

Open PowerShell in the repository directory:

```powershell
cd "C:\Users\<your-user>\path\to\CipherDoc-SecureExamPapers"
```

Create and activate a virtual environment:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, either allow it for the current user or use
the activation script from Command Prompt:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
.\.venv\Scripts\Activate.ps1
```

Install Python dependencies:

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Supabase database setup

1. Create a project at [supabase.com](https://supabase.com/).
2. Open **SQL Editor** in the Supabase dashboard.
3. Copy and run the complete contents of [`supabase_schema.sql`](./supabase_schema.sql).
4. In **Project Settings → API**, copy the project URL and the API key used
   by this application.

The schema creates these tables:

| Table | Purpose |
| --- | --- |
| `users` | EA and AEF accounts and profile data |
| `papers` | Exam metadata and encrypted paper content |
| `keys` | RSA key pairs managed by the application |
| `authorizations` | Faculty-to-paper authorization records |
| `access_logs` | Authentication and paper-access audit events |

The current schema grants broad access to the Supabase `anon` and
`authenticated` roles because authorization is implemented in the Flask
application. Do not copy this policy unchanged into a production system
without reviewing and tightening it.

## Environment variables

Create a file named `.env` in the repository root. Do not commit it:

```dotenv
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_KEY=your-supabase-api-key
SESSION_SECRET=replace-with-a-long-random-secret
```

Generate a strong session secret with PowerShell:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Use the generated value as `SESSION_SECRET`. Keep `.env` private; it is
excluded by [`.gitignore`](./.gitignore).

When `SUPABASE_URL` or `SUPABASE_KEY` is missing, the app intentionally shows
the configuration page instead of starting normal authenticated workflows.

## Run locally

With the virtual environment activated and `.env` configured:

```powershell
python app.py
```

Open <http://127.0.0.1:5000> in a browser.

The Flask development server listens on all interfaces and runs in debug mode
because that is how `app.py` is currently configured. Use it only for local
development.

For a production-style local process using Gunicorn (Linux/macOS, or WSL):

```bash
gunicorn --bind 0.0.0.0:5000 app:app
```

On Windows, use the Flask command above for development, or run the app behind
a production-capable WSGI server supported by your deployment environment.

### Optional Windows batch helper

[`run3120.bat`](./run3120.bat) is a machine-specific helper that attempts to
activate `C:\Envs\py3120env`. It is not required. If that path does not exist,
use the `.venv` commands above instead.

## Quick functional flow

After starting the app:

1. Visit `/ea/signup` and create an Exam Authority account.
2. Visit `/ea/login` and sign in as the EA.
3. Create an RSA key pair from the EA key-management page.
4. Create an encrypted exam paper.
5. Register an account at `/aef/signup`.
6. As the EA, authorize the AEF for a paper.
7. Log in at `/aef/login` and view/decrypt the authorized paper.

The login and registration pages are available from the home page at
<http://127.0.0.1:5000/home>.

## Security and production notes

- Set a unique, high-entropy `SESSION_SECRET`; the fallback value in
  `app.py` is for development only.
- The current OTP endpoint returns the generated OTP to the client and does
  not send email. Treat this as a demo flow and integrate a trusted email/SMS
  provider before production use.
- Do not store production private keys in application-managed database rows
  without a reviewed key-management design.
- Supabase policies in `supabase_schema.sql` are intentionally permissive for
  this project and must be replaced with least-privilege policies.
- Add CSRF protection, input validation, login/OTP rate limiting, secure
  cookies, HTTPS, and centralized error monitoring before deployment.
- Do not commit `.env`, `keys/`, `uploads/`, credentials, or real exam papers.
- Local filesystem writes and `/tmp` writes are not durable on serverless
  platforms. Use Supabase Storage or another encrypted object store for
  production files.

## Deploy to Vercel

The repository includes [`vercel.json`](./vercel.json), which routes requests
to [`api/index.py`](./api/index.py). From the repository root:

```powershell
npm install -g vercel
vercel login
vercel
```

When prompted, choose the current directory as the project directory. Add the
following environment variables in the Vercel project settings, or with the
Vercel CLI:

```powershell
vercel env add SUPABASE_URL
vercel env add SUPABASE_KEY
vercel env add SESSION_SECRET
```

Deploy to production:

```powershell
vercel --prod
```

After deployment, verify the home page and then test EA login, AEF login,
paper creation, authorization, and decryption using non-sensitive test data.

## Optional Node.js directory

`backend/` contains an Express/Supabase scaffold with its own
`package.json`. It is separate from the Flask app and is not used by
`python app.py` or the Vercel Python entry point.

To install its dependencies:

```powershell
cd backend
npm install
```

The current Node server is only a minimal scaffold and does not provide the
Flask application’s complete route set. Use the Python application as the
supported runtime unless you are explicitly continuing the Node migration.

## Troubleshooting

**The configuration error page appears**

- Confirm `.env` is in the repository root.
- Confirm the variable names are exactly `SUPABASE_URL` and `SUPABASE_KEY`.
- Restart the Flask process after changing `.env`.
- Confirm the Supabase URL and key belong to the same project.

**Database requests fail**

- Run [`supabase_schema.sql`](./supabase_schema.sql) in the Supabase SQL
  Editor.
- Check that the required tables and policies exist.
- Review the terminal output for the failing Supabase request.

**PowerShell will not activate the virtual environment**

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
.\.venv\Scripts\Activate.ps1
```

**Port 5000 is already in use**

Stop the process using port 5000, or run the app with a small local-only
change to the port in `app.py`.

## License

No license file is currently included. Add a license before distributing this
project or accepting external contributions.
