from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
from config import Config
import MySQLdb.cursors
import re

app = Flask(__name__)
app.config.from_object(Config)
mysql = MySQL(app)

# ALL ROUTES IN PROPER ORDER
@app.route('/')
def index():
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        email = request.form['email'].strip().lower()
        password = generate_password_hash(request.form['password'])
        
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cursor.fetchone():
            cursor.close()
            flash('Email already registered!', 'danger')
            return render_template('register.html')
        
        cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
        if cursor.fetchone():
            cursor.close()
            flash('Username already taken!', 'danger')
            return render_template('register.html')
        
        try:
            cursor.execute("INSERT INTO users (username, email, password, role, has_voted) VALUES (%s, %s, %s, 'voter', FALSE)", 
                          (username, email, password))
            mysql.connection.commit()
            cursor.close()
            flash('✅ Registration successful!', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            mysql.connection.rollback()
            cursor.close()
            flash('Registration failed!', 'danger')
            return render_template('register.html')
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        password = request.form['password']
        
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        cursor.close()
        
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        flash('Invalid credentials!', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully!', 'success')
    return redirect(url_for('login'))

@app.route('/home')
def home():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("SELECT COUNT(*) as total FROM users WHERE role='voter'")
        total_voters = cursor.fetchone()['total']
        cursor.execute("SELECT COUNT(*) as voted FROM users WHERE has_voted=TRUE")
        voted_count = cursor.fetchone()['voted']
        cursor.execute("SELECT COUNT(*) as total FROM candidates")
        total_candidates = cursor.fetchone()['total']
        cursor.execute("SELECT SUM(votes) as total_votes FROM candidates")
        total_votes = cursor.fetchone()['total_votes'] or 0
        cursor.close()
        return render_template('home.html', stats={
            'total_voters': total_voters, 'voted_count': voted_count,
            'total_candidates': total_candidates, 'total_votes': total_votes
        })
    except Exception as e:
        print(f"Home page error: {e}")
        return render_template('home.html', stats={'total_voters': 0, 'voted_count': 0, 'total_candidates': 0, 'total_votes': 0})

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("SELECT has_voted, username FROM users WHERE id = %s", (session['user_id'],))
        user = cursor.fetchone()
        cursor.execute("SELECT DISTINCT position FROM candidates ORDER BY position")
        positions = cursor.fetchall()
        cursor.close()
        return render_template('dashboard.html', user=user or {'has_voted': False}, positions=positions or [])
    except Exception as e:
        print(f"Dashboard error: {e}")
        return render_template('dashboard.html', user={'has_voted': False}, positions=[])

@app.route('/vote/<position>')
def vote_page(position):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("SELECT * FROM candidates WHERE position = %s ORDER BY name", (position,))
        candidates = cursor.fetchall()
        cursor.close()
        if not candidates:
            flash('No candidates available!', 'warning')
            return redirect(url_for('dashboard'))
        return render_template('vote.html', candidates=candidates, position=position)
    except Exception as e:
        print(f"Vote page error: {e}")
        flash('Position not found!', 'danger')
        return redirect(url_for('dashboard'))

@app.route('/cast_vote', methods=['POST'])
def cast_vote():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Please login first'})
    
    try:
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT id FROM votes WHERE user_id = %s AND position = %s", 
                      (session['user_id'], request.form['position']))
        if cursor.fetchone():
            cursor.close()
            return jsonify({'success': False, 'message': 'Already voted for this position!'})
        
        cursor.execute("INSERT INTO votes (user_id, candidate_id, position) VALUES (%s, %s, %s)",
                      (session['user_id'], request.form['candidate_id'], request.form['position']))
        cursor.execute("UPDATE users SET has_voted = TRUE WHERE id = %s", (session['user_id'],))
        cursor.execute("UPDATE candidates SET votes = votes + 1 WHERE id = %s", (request.form['candidate_id'],))
        
        mysql.connection.commit()
        cursor.close()
        return jsonify({'success': True, 'message': 'Vote cast successfully!'})
    except Exception as e:
        mysql.connection.rollback()
        print(f"Vote cast error: {e}")
        return jsonify({'success': False, 'message': 'Vote failed!'})

@app.route('/results')
def results():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("""
            SELECT c.*, COALESCE(SUM(v.id), 0) as total_votes 
            FROM candidates c 
            LEFT JOIN votes v ON c.id = v.candidate_id 
            GROUP BY c.id 
            ORDER BY c.position, total_votes DESC
        """)
        results = cursor.fetchall()
        cursor.close()
        return render_template('results.html', results=results)
    except Exception as e:
        print(f"Results error: {e}")
        return render_template('results.html', results=[])

@app.route('/contact')
def contact():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('contact.html')

#  ADMIN ROUTEs
@app.route('/admin')
def admin():
    if session.get('role') != 'admin':
        flash('❌ Admin access only!', 'danger')
        return redirect(url_for('login'))
    
    try:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("""
            SELECT c.*, COALESCE(SUM(v.id), 0) as votes 
            FROM candidates c 
            LEFT JOIN votes v ON c.id = v.candidate_id 
            GROUP BY c.id 
            ORDER BY c.created_at DESC
        """)
        candidates = cursor.fetchall()
        cursor.close()
        return render_template('admin.html', candidates=candidates)
    except Exception as e:
        print(f"Admin error: {e}")
        return render_template('admin.html', candidates=[])

@app.route('/admin/add_candidate', methods=['POST'])
def add_candidate():
    if session.get('role') != 'admin':
        return jsonify({'success': False, 'message': 'Admin only!'})
    
    name = request.form['name'].strip()
    position = request.form['position'].strip()
    party = request.form['party'].strip() or 'Independent'
    image = request.form['image'].strip() or None
    
    if not name or not position:
        return jsonify({'success': False, 'message': 'Name and position required!'})
    
    try:
        cursor = mysql.connection.cursor()
        cursor.execute("""
            INSERT INTO candidates (name, position, party, image, votes, created_at) 
            VALUES (%s, %s, %s, %s, 0, NOW())
        """, (name, position, party, image))
        mysql.connection.commit()
        cursor.close()
        return jsonify({'success': True, 'message': 'Candidate added successfully!'})
    except Exception as e:
        mysql.connection.rollback()
        print(f"Add candidate error: {e}")
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

@app.route('/admin/delete_candidate/<int:candidate_id>', methods=['DELETE'])
def delete_candidate(candidate_id):
    if session.get('role') != 'admin':
        return jsonify({'success': False, 'message': 'Admin only!'})
    
    try:
        cursor = mysql.connection.cursor()
        cursor.execute("DELETE FROM candidates WHERE id = %s", (candidate_id,))
        mysql.connection.commit()
        cursor.close()
        return jsonify({'success': True, 'message': 'Candidate deleted!'})
    except Exception as e:
        mysql.connection.rollback()
        print(f"Delete candidate error: {e}")
        return jsonify({'success': False, 'message': f'Error: {str(e)}'})

@app.route('/admin/edit_candidate', methods=['POST'])
def edit_candidate():
    if session.get('role') != 'admin':
        return jsonify({'success': False, 'message': 'Admin only!'})
    
    try:
        candidate_id = request.form['candidate_id']
        name = request.form['name'].strip()
        position = request.form['position'].strip()
        party = request.form['party'].strip() or 'Independent'
        image = request.form['image'].strip() or None
        
        # Validate required fields
        if not candidate_id or not name:
            return jsonify({'success': False, 'message': 'Candidate ID and name are required!'})
        
        # Validate candidate_id is numeric
        if not re.match(r'^\d+$', candidate_id):
            return jsonify({'success': False, 'message': 'Invalid candidate ID!'})
        
        cursor = mysql.connection.cursor()
        result = cursor.execute("""
            UPDATE candidates 
            SET name = %s, position = %s, party = %s, image = %s 
            WHERE id = %s
        """, (name, position, party, image, candidate_id))
        
        mysql.connection.commit()
        
        if cursor.rowcount == 0:
            cursor.close()
            return jsonify({'success': False, 'message': 'No candidate found with that ID!'})
        
        cursor.close()
        return jsonify({'success': True, 'message': '✅ Candidate updated successfully!'})
        
    except Exception as e:
        mysql.connection.rollback()
        print(f"Edit candidate error: {e}")
        return jsonify({'success': False, 'message': f'Database error: {str(e)}'})

#  END ADMIN ROUTES 

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)