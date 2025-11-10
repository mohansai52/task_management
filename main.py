from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt
from datetime import datetime
import sqlalchemy
from sqlalchemy import text
import sqlite3

app = Flask(__name__)
from flask import send_file
import os

@app.route('/download-real-db')
def download_real_db():
    # THIS IS WHERE RENDER ACTUALLY STORES YOUR DB ON FREE TIER
    REAL_PATH = "/opt/render/project/src/instance/tasks.db"
    
    if os.path.exists(REAL_PATH):
        return send_file(
            REAL_PATH,
            as_attachment=True,
            download_name="TASK_MANAGER_FULL_DATA_WITH_USERS.db",
            mimetype="application/x-sqlite3"
        )
    
    # If not there, show proof
    instance_files = os.listdir("/opt/render/project/src/instance") if os.path.exists("/opt/render/project/src/instance") else []
    root_files = os.listdir("/opt/render/project/src")
    
    return f"""
    <h1>Database Location Found!</h1>
    <p>Root files: {root_files}</p>
    <p>Instance folder files: {instance_files}</p>
    <p>Expected path: /opt/render/project/src/instance/tasks.db</p>
    <p>If you see 'tasks.db' above → refresh this page</p>
    <hr>
    <h2>TRY THESE LINKS:</h2>
    <ul>
        <li><a href="/download-real-db">CLICK HERE TO DOWNLOAD REAL DB</a></li>
        <li><a href="https://dashboard.render.com" target="_blank">Open Render Dashboard → Files tab → Download manually</a></li>
    </ul>
    """

# Optional: Add this to see exactly what's there
@app.route('/debug')
def debug():
    return f"""
    <pre>
CWD: {os.getcwd()}
Root: {os.listdir('/opt/render/project/src')}
Instance: {os.listdir('/opt/render/project/src/instance') if os.path.exists('/opt/render/project/src/instance') else 'NOT FOUND'}
    </pre>
    """
    
app.config['SECRET_KEY'] = 'your-super-secret-key-2025'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///tasks.db'
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    name = db.Column(db.String(150), nullable=False)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    deadline = db.Column(db.String(50))
    status = db.Column(db.String(20), default='Pending')
    completed = db.Column(db.Boolean, default=False)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))
def force_upgrade_db():
    conn = sqlite3.connect("tasks.db")  # not Task_data.db
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user';")
    if cursor.fetchone() is None:
        print("User table not found, skipping ALTER TABLE.")
        conn.close()
        return

    try:
        cursor.execute("ALTER TABLE user ADD COLUMN email TEXT")
        conn.commit()
    except sqlite3.OperationalError as e:
        print("Skipping column addition:", e)
    finally:
        conn.close()
from flask import send_file, abort
import os


@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        name = request.form['name']
        password = bcrypt.generate_password_hash(request.form['password']).decode('utf-8')
        if User.query.filter_by(username=username).first() or User.query.filter_by(email=email).first():
            flash('Username or email already exists!', 'danger')
            return redirect('/register')
        new_user = User(username=username, email=email, name=name, password=password)
        db.session.add(new_user)
        db.session.commit()
        flash('Account created! Please login.', 'success')
        return redirect('/login')
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and bcrypt.check_password_hash(user.password, password):
            login_user(user)
            return redirect('/')
        flash('Invalid credentials.', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out.', 'info')
    return redirect('/login')

@app.route('/profile')
@login_required
def profile():
    return render_template('profile.html', user=current_user)

@app.route('/', methods=['GET', 'POST'])
@login_required
def index():
    if request.method == 'POST':
        content = request.form['content']
        description = request.form.get('description', '')
        deadline = request.form.get('deadline', '')
        new_task = Task(content=content, description=description, deadline=deadline, user_id=current_user.id)
        db.session.add(new_task)
        db.session.commit()
        flash('Task added!', 'success')
    tasks = Task.query.filter_by(user_id=current_user.id).order_by(Task.date_created.desc()).all()
    return render_template('index.html', tasks=tasks)

@app.route('/delete/<int:id>')
@login_required
def delete(id):
    task = Task.query.get_or_404(id)
    if task.user_id != current_user.id:
        flash('Unauthorized!', 'danger')
        return redirect('/')
    db.session.delete(task)
    db.session.commit()
    flash('Task deleted.', 'info')
    return redirect('/')

@app.route('/update/<int:id>', methods=['GET', 'POST'])
@login_required
def update(id):
    task = Task.query.get_or_404(id)
    if task.user_id != current_user.id:
        flash('Unauthorized!', 'danger')
        return redirect('/')
    if request.method == 'POST':
        task.content = request.form['content']
        task.description = request.form.get('description', '')
        task.deadline = request.form.get('deadline', '')
        db.session.commit()
        flash('Task updated!', 'success')
        return redirect('/')
    return render_template('update.html', task=task)

@app.route('/complete/<int:id>')
@login_required
def complete(id):
    task = Task.query.get_or_404(id)
    if task.user_id != current_user.id:
        return redirect('/')
    task.completed = not task.completed
    task.status = 'Completed' if task.completed else 'Pending'
    db.session.commit()
    return redirect('/')
with app.app_context():
    db.create_all()
force_upgrade_db()
if __name__ == "__main__":
    with app.app_context():
        import sqlalchemy
        engine = sqlalchemy.create_engine('sqlite:///tasks.db')
        if not sqlalchemy.inspect(engine).has_table('user'):
            db.create_all()
        else:
            # Force add missing columns (email, name)
            with engine.connect() as conn:
                try:
                    conn.execute(sqlalchemy.text("ALTER TABLE user ADD COLUMN email TEXT"))
                except:
                    pass
                try:
                    conn.execute(sqlalchemy.text("ALTER TABLE user ADD COLUMN name TEXT"))
                except:
                    pass
                conn.commit()
        db.create_all()  # Safe to run again
    app.run(debug=True)
