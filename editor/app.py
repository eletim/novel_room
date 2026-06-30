from flask import Flask, render_template, request, jsonify, redirect, url_for, session, g, flash
from functools import wraps
from datetime import datetime
import os
import sqlite3
from db import get_db, init_db

app = Flask(__name__)
app.secret_key = 'your_secret_key'

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login', next=request.url))
        if g.user is None:
            session.pop('user_id', None)
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

@app.before_request
def load_logged_in_user():
    user_id = session.get('user_id')
    if user_id is None:
        g.user = None
    else:
        with get_db() as conn:
            g.user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()

@app.route('/')
@login_required
def index():
    user_id = session['user_id']
    with get_db() as conn:
        user = conn.execute('SELECT username FROM users WHERE id = ?', (user_id,)).fetchone()
        folders = conn.execute('SELECT * FROM folders WHERE user_id = ? AND parent_id IS NULL', (user_id,)).fetchall()
        documents = conn.execute('SELECT * FROM documents WHERE user_id = ? AND folder_id IS NULL', (user_id,)).fetchall()
        documents = [dict(doc) for doc in documents]
        for doc in documents:
            doc['last_modified'] = datetime.strptime(doc['last_modified'].split('.')[0], '%Y-%m-%d %H:%M:%S')
    return render_template('index.html', folders=folders, documents=documents, username=user['username'], current_folder=None)

@app.route('/folder/<int:folder_id>')
@login_required
def view_folder(folder_id):
    user_id = session['user_id']
    user_id = int(user_id)  # user_idを整数に変換
    with get_db() as conn:
        user = conn.execute('SELECT username FROM users WHERE id = ?', (user_id,)).fetchone()
        current_folder = conn.execute('SELECT * FROM folders WHERE id = ? AND user_id = ?', (folder_id, user_id)).fetchone()
        folders = conn.execute('SELECT * FROM folders WHERE parent_id = ? AND user_id = ?', (folder_id, user_id)).fetchall()
        documents = conn.execute('SELECT * FROM documents WHERE folder_id = ? AND user_id = ?', (folder_id, user_id)).fetchall()
        documents = [dict(doc) for doc in documents]
        for doc in documents:
            doc['last_modified'] = datetime.strptime(doc['last_modified'].split('.')[0], '%Y-%m-%d %H:%M:%S')
    return render_template('index.html', current_folder=current_folder, folders=folders, documents=documents, username=user['username'])

@app.route('/create_folder', methods=['POST'])
@login_required
def create_folder():
    name = request.form['name'].strip()
    parent_id = request.form.get('parent_id')
    user_id = session['user_id']

    if not name:
        return "Folder name cannot be empty", 400

    parent_id = int(parent_id) if parent_id else None

    with get_db() as conn:
        existing_folder = conn.execute('SELECT id FROM folders WHERE user_id = ? AND name = ? AND parent_id IS ?', (user_id, name, parent_id)).fetchone()
        if existing_folder:
            return "Folder with the same name already exists", 400

        conn.execute('INSERT INTO folders (user_id, name, parent_id) VALUES (?, ?, ?)', (user_id, name, parent_id))
    
    return redirect(url_for('index') if parent_id is None else url_for('view_folder', folder_id=parent_id))

@app.route('/create', methods=['POST'])
@login_required
def create():
    title = request.form['title'].strip()
    folder_id = request.form.get('folder_id')
    user_id = session['user_id']
    last_modified = datetime.now()

    if not title:
        return "Document title cannot be empty", 400

    folder_id = int(folder_id) if folder_id else None

    with get_db() as conn:
        existing_document = conn.execute('SELECT id FROM documents WHERE user_id = ? AND title = ? AND folder_id IS ?', (user_id, title, folder_id)).fetchone()
        if existing_document:
            return "Document with the same title already exists", 400

        conn.execute('INSERT INTO documents (user_id, folder_id, title, content, length, last_modified) VALUES (?, ?, ?, ?, ?, ?)', 
                     (user_id, folder_id, title, '', 0, last_modified))
    return redirect(url_for('index') if folder_id is None else url_for('view_folder', folder_id=folder_id))

@app.route('/delete_document/<int:doc_id>', methods=['POST'])
@login_required
def delete_document(doc_id):
    user_id = session['user_id']
    with get_db() as conn:
        conn.execute('DELETE FROM documents WHERE id = ? AND user_id = ?', (doc_id, user_id))
    return redirect(request.referrer or url_for('index'))

@app.route('/delete_folder/<int:folder_id>', methods=['POST'])
@login_required
def delete_folder(folder_id):
    user_id = session['user_id']
    with get_db() as conn:
        # フォルダが空であるかを確認
        subfolders = conn.execute('SELECT id FROM folders WHERE parent_id = ? AND user_id = ?', (folder_id, user_id)).fetchall()
        documents = conn.execute('SELECT id FROM documents WHERE folder_id = ? AND user_id = ?', (folder_id, user_id)).fetchall()
        
        if subfolders or documents:
            flash('フォルダ内にアイテムが存在するため、削除できません。', 'warn')
            return redirect(request.referrer or url_for('index'))
        
        conn.execute('DELETE FROM folders WHERE id = ? AND user_id = ?', (folder_id, user_id))
    
    return redirect(request.referrer or url_for('index'))

@app.route('/move_document', methods=['POST'])
@login_required
def move_document():
    doc_id = request.form['doc_id']
    new_folder_id = request.form['new_folder_id']
    user_id = session['user_id']

    with get_db() as conn:
        # ドキュメントが存在するか確認
        document = conn.execute('SELECT * FROM documents WHERE id = ? AND user_id = ?', (doc_id, user_id)).fetchone()
        if not document:
            return "Document not found", 404

        # フォルダが存在するか確認
        if new_folder_id:
            folder = conn.execute('SELECT * FROM folders WHERE id = ? AND user_id = ?', (new_folder_id, user_id)).fetchone()
            if not folder:
                return "Target folder not found", 404
        else:
            new_folder_id = None  # ルートフォルダへ移動

        # ドキュメントのフォルダを更新
        conn.execute('UPDATE documents SET folder_id = ? WHERE id = ? AND user_id = ?', (new_folder_id, doc_id, user_id))
    
    return redirect(request.referrer or url_for('index'))

@app.route('/rename_document', methods=['POST'])
@login_required
def rename_document():
    doc_id = request.form['doc_id']
    new_title = request.form['new_title'].strip()
    user_id = session['user_id']

    if not new_title:
        return "Document title cannot be empty", 400

    with get_db() as conn:
        # ドキュメントが存在するか確認
        document = conn.execute('SELECT * FROM documents WHERE id = ? AND user_id = ?', (doc_id, user_id)).fetchone()
        if not document:
            return "Document not found", 404

        # 同じ名前のドキュメントが存在しないか確認
        existing_document = conn.execute('SELECT id FROM documents WHERE user_id = ? AND title = ? AND folder_id = ?', 
                                         (user_id, new_title, document['folder_id'])).fetchone()
        if existing_document:
            return "A document with this title already exists in the folder", 400

        # ドキュメントの名前を更新
        conn.execute('UPDATE documents SET title = ? WHERE id = ? AND user_id = ?', (new_title, doc_id, user_id))
    
    return redirect(request.referrer or url_for('index'))

@app.route('/check_folder_empty/<int:folder_id>', methods=['GET'])
@login_required
def check_folder_empty(folder_id):
    user_id = session['user_id']
    with get_db() as conn:
        subfolders = conn.execute('SELECT id FROM folders WHERE parent_id = ? AND user_id = ?', (folder_id, user_id)).fetchall()
        documents = conn.execute('SELECT id FROM documents WHERE folder_id = ? AND user_id = ?', (folder_id, user_id)).fetchall()
        is_empty = not subfolders and not documents
    return jsonify({"isEmpty": is_empty})

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        with get_db() as conn:
            user = conn.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, password)).fetchone()
            if user:
                session['user_id'] = user['id']
                return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        with get_db() as conn:
            try:
                conn.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, password))
                conn.commit()
                return redirect(url_for('login'))
            except sqlite3.IntegrityError:
                return "Username already exists"
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))

@app.route('/editor', methods=['POST'])
@login_required
def editor():
    doc_id = request.form.get('doc_id')
    user_id = session['user_id']
    with get_db() as conn:
        document = conn.execute('SELECT * FROM documents WHERE id = ? AND user_id = ?', (doc_id, user_id)).fetchone()
        if document:
            document = dict(document)
            document['last_modified'] = datetime.strptime(document['last_modified'].split('.')[0], '%Y-%m-%d %H:%M:%S')
            return render_template('editor.html', document=document)
    return "File not found", 404

@app.route('/save', methods=['POST'])
@login_required
def save():
    content = request.json.get('content')
    length = request.json.get('length')
    doc_id = request.json.get('doc_id')
    last_modified = datetime.now()
    with get_db() as conn:
        conn.execute('UPDATE documents SET content = ?, length = ?, last_modified = ? WHERE id = ?', (content, length, last_modified, doc_id))
    return jsonify({"message": "File saved successfully"}), 200

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
