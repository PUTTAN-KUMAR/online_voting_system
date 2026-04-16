from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
from config import Config
import MySQLdb.cursors
import re
import random
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta
import os
import time

app = Flask(__name__)
app.secret_key = os.urandom(24).hex()  # ecure random key
app.config.from_object(Config)
mysql = MySQL(app)

# EMAIL CONFIG - UPDATE THESE
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587
EMAIL_USER = os.getenv('EMAIL_USER', 'puttankumar76@gmail.com')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD', 'your_16_digit_app_password_here')

def generate_otp():
    """Generate 6-digit OTP"""
    otp = str(random.randint(100000, 999999))
    print(f"TERMINAL OTP: {otp}")
    print("=" * 50)
    return otp

def send_otp_email(to_email, otp):
    """Send OTP via email"""
    try:
        msg = MIMEText(f"""
VoteSecure OTP: **{otp}**

Valid for 10 minutes.
Don't share your OTP with anyone!

Team VoteSecure
        """)
        msg['Subject'] = 'VoteSecure - Your OTP Code'
        msg['From'] = EMAIL_USER
        msg['To'] = to_email
        
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        print(f"EMAIL SENT TO: {to_email}")
        return True
    except Exception as e:
        print(f"EMAIL FAILED: {e} - Using Terminal OTP")
        return False

# SEND OTP ROUTE - Frontend register.html से call
@app.route('/send-otp', methods=['POST'])
def send_otp():
    """Send OTP via email - Supports JSON and FormData"""
    try:
        # Handle multiple content types
        if request.content_type == 'application/json':
            data = request.get_json(silent=True) or {}
        else:
            data = request.form.to_dict()
        
        #  Get email from any source
        email = (data.get('email') or 
                request.args.get('email') or 
                request.form.get('email') or 
                '').strip().lower()
        
        print(f"SEND-OTP REQUEST:")
        print(f"   Email: {email}")
        print(f"   Content-Type: {request.content_type}")
        print(f"   Data: {data}")
        
        if not email:
            return jsonify({'success': False, 'error': 'Email parameter missing!'}), 400
        
        if not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email):
            return jsonify({'success': False, 'error': 'Invalid email format!'}), 400
        
        # Check if user exists
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("SELECT id, username FROM users WHERE email = %s", (email,))
        existing_user = cursor.fetchone()
        cursor.close()
        
        if existing_user:
            return jsonify({
                'success': False, 
                'error': f'Email already registered as "{existing_user["username"]}"!',
                'login_url': url_for('login')
            }), 400
        
        # Generate OTP
        otp = generate_otp()
        email_sent = send_otp_email(email, otp)
        
        # Store in session
        session['otp_email'] = email
        session['otp'] = otp
        session['otp_time'] = time.time() + 600  # 10 minutes
        session['otp_attempts'] = 0
        
        print(f"ESSION STORED - Email: {email}, OTP: {otp}, Expires: {datetime.fromtimestamp(session['otp_time'])}")
        
        return jsonify({
            'success': True,
            'message': 'OTP sent successfully! Check terminal.',
            'email': email,
            'email_sent': email_sent,
            'terminal_otp': otp,
            'expires_in': 600
        }), 200
        
    except Exception as e:
        print(f"SEND-OTP ERROR: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False, 
            'error': 'Internal server error. Check terminal for OTP.'
        }), 500

# VERIFY OTP ROUTE - 
@app.route('/verify-otp', methods=['POST'])
def verify_otp():
    """Frontend verifyOtp() से call - OTP verification"""
    try:
        data = request.get_json()
        user_otp = data.get('otp', '').strip()
        
        print(f"VERIFY-OTP CALLED:")
        print(f"   User OTP: {user_otp}")
        print(f"   Session OTP: {session.get('otp', 'None')}")
        
        # Get session data
        email = session.get('otp_email')
        stored_otp = session.get('otp')
        otp_time = session.get('otp_time', 0)
        attempts = session.get('otp_attempts', 0)
        
        if not email or not stored_otp:
            print("No OTP session found!")
            return jsonify({'success': False, 'error': 'Session expired! Resend OTP.'})
        
        # Check attempts limit (3 tries)
        if attempts >= 3:
            session.clear()
            print("Too many attempts!")
            return jsonify({'success': False, 'error': 'Too many failed attempts! Resend OTP.'})
        
        # Check OTP expiry (10 minutes)
        if time.time() > otp_time:
            session.clear()
            print("OTP expired!")
            return jsonify({'success': False, 'error': 'OTP expired! Please request new one.'})
        
        # OTP MATCH CHECK
        if user_otp == stored_otp:
            print(f"OTP VERIFIED SUCCESSFULLY for {email}")
            session['otp_verified'] = True  # Mark as verified
            session['otp_attempts'] = 0     # Reset attempts
            return jsonify({
                'success': True, 
                'message': 'OTP verified! Proceeding to registration...'
            })
        else:
            # Wrong OTP
            session['otp_attempts'] = attempts + 1
            remaining = 3 - (attempts + 1)
            print(f"WRONG OTP! Remaining attempts: {remaining}")
            return jsonify({
                'success': False, 
                'error': f'Invalid OTP! {remaining} attempts remaining.'
            })
            
    except Exception as e:
        print(f"VERIFY-OTP ERROR: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': 'Verification failed!'}), 500

# REGISTER ROUTE (Updated for AJAX flow)
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        email = session.get('otp_email', '')
        return render_template('register.html', email=email)
    
    if request.method == 'POST':
        try:
            # Get form data (from hidden form submission)
            username = request.form.get('username', '').strip()
            email = request.form.get('email') or session.get('otp_email')
            password = request.form.get('password', '')
            aadhaar = request.form.get('aadhaar', '')
            mobile = request.form.get('mobile', '')
            
            print(f"REGISTER ATTEMPT:")
            print(f"   Username: {username}")
            print(f"   Email: {email}")
            print(f"   OTP Verified: {session.get('otp_verified', False)}")
            
            # MANDATORY: Check OTP verification
            if not session.get('otp_verified'):
                print("OTP not verified!")
                return '''
                <script>
                    alert("Please verify OTP first!");
                    window.history.back();
                </script>
                '''
            
            # Client-side validation (server-side too)
            if not all([username, email, password, aadhaar, mobile]):
                return 'All fields required!', 400
            
            if len(password) < 6:
                return 'Password must be 6+ characters!', 400
            
            if len(aadhaar) != 12 or not aadhaar.isdigit():
                return 'Aadhaar must be 12 digits!', 400
            
            if len(mobile) != 10 or not mobile.isdigit():
                return 'Mobile must be 10 digits!', 400
            
            # Check duplicates
            cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            
            # Username check
            cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
            if cursor.fetchone():
                cursor.close()
                return 'Username already taken!', 400
            
            # Email check (already done in send-otp, but double-check)
            cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
            if cursor.fetchone():
                cursor.close()
                return 'Email already registered!', 400
            
            # Insert new user
            cursor.execute("""
                INSERT INTO users (username, email, password, aadhaar, mobile, role, has_voted, created_at) 
                VALUES (%s, %s, %s, %s, %s, 'voter', FALSE, NOW())
            """, (username, email, generate_password_hash(password), aadhaar, mobile))
            
            mysql.connection.commit()
            new_user_id = mysql.connection.insert_id()
            cursor.close()
            
            print(f"NEW USER REGISTERED: ID={new_user_id}, {username}")
            
            # Clear session
            session.clear()
            
            return f'''
            <script>
                alert("Registration Successful!\\nWelcome {username}!");
                window.location.href = "/login";
            </script>
            '''
            
        except Exception as e:
            if mysql.connection:
                mysql.connection.rollback()
            print(f"REGISTER ERROR: {e}")
            import traceback
            traceback.print_exc()
            return f'Registration failed: {str(e)}', 500

# INDEX ROUTE
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        print(f"INDEX POST OTP: {email}")
        
        if not email or not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email):
            flash('Valid email required!', 'danger')
            return render_template('index.html')
        
        # Check duplicate
        try:
            cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
            if cursor.fetchone():
                cursor.close()
                flash('Email already registered! <a href="/login">Login here</a>', 'warning')
                return redirect(url_for('login'))
            cursor.close()
        except:
            pass
        
        # Generate & store OTP
        otp = generate_otp()
        send_otp_email(email, otp)
        
        session['otp_email'] = email
        session['otp'] = otp
        session['otp_time'] = time.time() + 600
        
        flash(f'OTP sent! Terminal: <strong>{otp}</strong><br>Click Register below!', 'success')
        return redirect(url_for('register'))
    
    return render_template('index.html')

# LOGIN ROUTE
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        print(f" LOGIN: {email}")
        
        if not email or not password:
            flash('Email & password required!', 'danger')
            return render_template('login.html')
        
        try:
            cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
            user = cursor.fetchone()
            cursor.close()
            
            if user and check_password_hash(user['password'], password):
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['role'] = user['role']
                print(f"LOGIN SUCCESS: {user['username']}")
                flash('Login successful!', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('Invalid credentials!', 'danger')
                print("LOGIN FAILED")
        except Exception as e:
            print(f" LOGIN ERROR: {e}")
            flash('Login error! Try again.', 'danger')
    
    return render_template('login.html')

#  RESULTS ROUTE
@app.route('/results')
def results():
    if 'user_id' not in session:
        flash('Login required!', 'warning')
        return redirect(url_for('login'))
    
    try:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

        # FIX: direct candidates table se votes lo
        cursor.execute("""
            SELECT * FROM candidates 
            ORDER BY position, votes DESC
        """)
        results = cursor.fetchall()
        
        # Stats
        cursor.execute("SELECT COUNT(*) as total_candidates FROM candidates")
        total_candidates = cursor.fetchone()['total_candidates']

        cursor.execute("SELECT COUNT(*) as total_votes FROM votes")
        total_votes = cursor.fetchone()['total_votes'] or 0
        
        cursor.close()

        return render_template(
            'results.html',
            results=results,
            stats={
                'total_candidates': total_candidates,
                'total_votes': total_votes
            }
        )

    except Exception as e:
        print("Results Error:", e)
        flash('Error loading results!', 'danger')
        return render_template('results.html', results=[], stats={})    
    # otp verify

@app.route('/verify_email_otp', methods=['GET', 'POST'])
def verify_email_otp():
    if request.method == 'POST':
        user_otp = request.form.get('otp', '').strip()
        stored_otp = session.get('otp')
        otp_time = session.get('otp_time', 0)
        
        print(f"OTP VERIFY: {user_otp} vs {stored_otp}")
        
        if not user_otp:
            flash('Enter OTP!', 'danger')
            return render_template('verify_otp.html')
        
        if time.time() > otp_time:
            flash('OTP expired! Request new one.', 'danger')
            session.clear()
            return redirect(url_for('index'))
        
        if user_otp == stored_otp:
            flash(' OTP Verified! Continue to register.', 'success')
            return redirect(url_for('register'))
        else:
            flash(' Wrong OTP! Try again.', 'danger')
    
    return render_template('verify_otp.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out!', 'success')
    return redirect(url_for('login'))

#  DASHBOARD ROUTES
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    try:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

        # User info
        cursor.execute("SELECT has_voted, username FROM users WHERE id = %s", (session['user_id'],))
        user = cursor.fetchone()

        #  Fetch positions from positions table (FIXED)
        cursor.execute("SELECT name FROM positions ORDER BY name")
        positions = cursor.fetchall()

        cursor.close()
        return render_template('dashboard.html', user=user or {}, positions=positions or [])
    except Exception as e:
        print(f"Dashboard Error: {e}")
        return render_template('dashboard.html', user={}, positions=[])    
    # condidate 
    
@app.route('/candidates/<position>')
def get_candidates(position):
    try:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("SELECT * FROM candidates WHERE position = %s", (position,))
        data = cursor.fetchall()
        cursor.close()
        return jsonify(data)
    except Exception as e:
        print(f"Candidate Fetch Error: {e}")
        return jsonify([])

# VOTE ROUTE
@app.route('/vote', defaults={'position': None}, methods=['GET', 'POST'])
@app.route('/vote/<position>', methods=['GET', 'POST'])
def vote(position):

    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        try:
            cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            user_id = session['user_id']
            candidate_id = request.form.get('candidate')

            #  Candidate select nahi kiya
            if not candidate_id:
                flash("Please select a candidate!", "warning")
                return redirect(request.url)

            #  Candidate se position nikaalo (IMPORTANT FIX)
            cursor.execute(
                "SELECT position FROM candidates WHERE id = %s",
                (candidate_id,)
            )
            result = cursor.fetchone()

            if not result:
                flash("Invalid candidate!", "danger")
                return redirect(url_for('dashboard'))

            position = result['position']   #  yahi main fix hai

            # Duplicate vote check (ab sahi kaam karega)
            cursor.execute(
                "SELECT id FROM votes WHERE user_id = %s AND position = %s",
                (user_id, position)
            )

            if cursor.fetchone():
                cursor.close()
                flash("You already voted for this position!", "warning")
                return redirect(url_for('dashboard'))

            # Insert vote
            cursor.execute(
                "INSERT INTO votes (user_id, candidate_id, position) VALUES (%s, %s, %s)",
                (user_id, candidate_id, position)
            )
            cursor.execute(
    "UPDATE candidates SET votes = votes + 1 WHERE id = %s",
    (candidate_id,)
)

            # Update user
            cursor.execute(
                "UPDATE users SET has_voted = TRUE WHERE id = %s",
                (user_id,)
            )

            mysql.connection.commit()
            cursor.close()

            flash(" Vote submitted successfully!", "success")
            return redirect(url_for('results'))

        except Exception as e:
            mysql.connection.rollback()
            print("Vote Error:", e)
            flash(" Vote failed!", "danger")
            return redirect(request.url)

    # GET PART
    try:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

        if position:
            cursor.execute("SELECT * FROM candidates WHERE position=%s", (position,))
        else:
            cursor.execute("SELECT * FROM candidates")

        candidates = cursor.fetchall()
        cursor.close()
    except:
        candidates = []

    return render_template('vote.html', candidates=candidates, position=position)

if __name__ == '__main__':
   
    app.run(debug=True, host='0.0.0.0', port=5000)