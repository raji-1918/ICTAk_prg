from flask import Flask, render_template, request, redirect, session, url_for, flash
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import date
import sqlite3
conn = sqlite3.connect("library_management.db")

app = Flask(__name__)
app.secret_key = "change_this_to_a_random_secret"  # change this in production

# ====== Configure DB connection ======
db_config = {
    "host": "localhost",
    "user": "root",
    "password": "yourpassword",   # change this
    "database": "library_management"
}

def get_db_connection():
    conn = mysql.connector.connect(**db_config)
    return conn

# ====== Helpers ======
def get_user_by_username(username):
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM users WHERE username = %s", (username,))
    user = cur.fetchone()
    cur.close()
    conn.close()
    return user

def login_required(fn):
    from functools import wraps
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return fn(*args, **kwargs)
    return wrapper

def librarian_required(fn):
    from functools import wraps
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if session.get('role') != 'librarian':
            flash("Access denied: Librarian only area.", "warning")
            return redirect(url_for('index'))
        return fn(*args, **kwargs)
    return wrapper

# ====== Routes ======
@app.route('/')
def index():
    stats = {}
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM books")
    stats['total_books'] = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM issue_records WHERE return_date IS NULL")
    stats['issued_books'] = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM students")
    stats['students'] = cur.fetchone()[0]
    cur.close()
    conn.close()
    return render_template('index.html', stats=stats)

# -------- Authentication --------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name'].strip()
        email = request.form['email'].strip()
        username = request.form['username'].strip()
        password = request.form['password']
        role = request.form.get('role', 'student')

        if not (name and email and username and password):
            flash("Please fill all required fields.", "danger")
            return redirect(url_for('register'))

        if get_user_by_username(username):
            flash("Username already taken.", "danger")
            return redirect(url_for('register'))

        pw_hash = generate_password_hash(password)

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO users (name, email, username, password_hash, role) VALUES (%s,%s,%s,%s,%s)",
                    (name, email, username, pw_hash, role))
        conn.commit()
        cur.close()
        conn.close()
        flash("Registration successful. Please login.", "success")
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        user = get_user_by_username(username)
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['user_id']
            session['username'] = user['username']
            session['role'] = user['role']
            flash(f"Welcome {user['name']}!", "success")
            return redirect(url_for('index'))
        else:
            flash("Invalid credentials.", "danger")
            return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully.", "info")
    return redirect(url_for('index'))

# -------- Students --------
@app.route('/students')
@login_required
def students():
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM students ORDER BY student_id DESC")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('students.html', students=rows)

@app.route('/add_student', methods=['POST'])
@login_required
@librarian_required
def add_student():
    name = request.form['name']
    roll_no = request.form.get('roll_no')
    course = request.form.get('course')
    contact = request.form.get('contact')
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO students (name, roll_no, course, contact) VALUES (%s,%s,%s,%s)",
                (name, roll_no, course, contact))
    conn.commit()
    cur.close()
    conn.close()
    flash("Student added.", "success")
    return redirect(url_for('students'))

# -------- Books --------
@app.route('/books')
@login_required
def books():
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM books ORDER BY book_id DESC")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('books.html', books=rows)

@app.route('/add_book', methods=['POST'])
@login_required
@librarian_required
def add_book():
    title = request.form['title']
    author = request.form.get('author')
    publication = request.form.get('publication')
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO books (title, author, publication) VALUES (%s,%s,%s)",
                (title, author, publication))
    conn.commit()
    cur.close()
    conn.close()
    flash("Book added.", "success")
    return redirect(url_for('books'))

# -------- Issue / Return --------
@app.route('/issue')
@login_required
def issue():
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM students")
    students = cur.fetchall()
    cur.execute("SELECT * FROM books WHERE available = TRUE")
    books = cur.fetchall()
    cur.execute("""
        SELECT ir.*, s.name AS student_name, b.title AS book_title
        FROM issue_records ir
        LEFT JOIN students s ON ir.student_id = s.student_id
        LEFT JOIN books b ON ir.book_id = b.book_id
        ORDER BY ir.issue_id DESC
    """)
    records = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('issue.html', students=students, books=books, records=records)

@app.route('/issue_book', methods=['POST'])
@login_required
@librarian_required
def issue_book():
    student_id = request.form['student_id']
    book_id = request.form['book_id']
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO issue_records (student_id, book_id, issue_date) VALUES (%s,%s,%s)",
                (student_id, book_id, date.today()))
    cur.execute("UPDATE books SET available = FALSE WHERE book_id = %s", (book_id,))
    conn.commit()
    cur.close()
    conn.close()
    flash("Book issued.", "success")
    return redirect(url_for('issue'))

@app.route('/return_book/<int:issue_id>', methods=['GET'])
@login_required
@librarian_required
def return_book(issue_id):
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT book_id, issue_date FROM issue_records WHERE issue_id = %s", (issue_id,))
    rec = cur.fetchone()
    if rec:
        book_id = rec['book_id']
        cur.execute("UPDATE books SET available = TRUE WHERE book_id = %s", (book_id,))
        cur.execute("UPDATE issue_records SET return_date = %s WHERE issue_id = %s", (date.today(), issue_id))
        conn.commit()
        flash("Book returned.", "success")
    else:
        flash("Record not found.", "danger")
    cur.close()
    conn.close()
    return redirect(url_for('issue'))

# -------- Simple protected route example --------
@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

# ===== Run =====
if __name__ == "__main__":
    app.run(debug=True)
