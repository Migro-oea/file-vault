import os
import sqlite3
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory, render_template, abort

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
DB_PATH = 'files.db'
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE


# ── Database ──────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS files (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            original_name TEXT NOT NULL,
            stored_name   TEXT NOT NULL,
            mimetype      TEXT,
            size          INTEGER,
            upload_date   TEXT
        )''')

init_db()


# ── Routes ────────────────────────────────────────────────
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    # Generate unique filename
    ext = os.path.splitext(file.filename)[1]
    import uuid
    stored_name = f"{uuid.uuid4().hex}{ext}"
    save_path = os.path.join(UPLOAD_FOLDER, stored_name)
    file.save(save_path)

    size = os.path.getsize(save_path)
    mimetype = file.content_type or 'application/octet-stream'

    with get_db() as conn:
        cursor = conn.execute(
            'INSERT INTO files (original_name, stored_name, mimetype, size, upload_date) VALUES (?, ?, ?, ?, ?)',
            [file.filename, stored_name, mimetype, size, datetime.now().isoformat()]
        )
        file_id = cursor.lastrowid

    return jsonify({'id': file_id, 'original_name': file.filename})


@app.route('/files')
def list_files():
    with get_db() as conn:
        rows = conn.execute('SELECT * FROM files ORDER BY id DESC').fetchall()
    return jsonify([dict(r) for r in rows])


@app.route('/download/<int:file_id>')
def download(file_id):
    with get_db() as conn:
        row = conn.execute('SELECT * FROM files WHERE id = ?', [file_id]).fetchone()
    if not row:
        abort(404)
    return send_from_directory(UPLOAD_FOLDER, row['stored_name'],
                               as_attachment=True,
                               download_name=row['original_name'])


@app.route('/preview/<int:file_id>')
def preview(file_id):
    with get_db() as conn:
        row = conn.execute('SELECT * FROM files WHERE id = ?', [file_id]).fetchone()
    if not row:
        abort(404)
    return send_from_directory(UPLOAD_FOLDER, row['stored_name'])


@app.route('/files/<int:file_id>', methods=['DELETE'])
def delete_file(file_id):
    with get_db() as conn:
        row = conn.execute('SELECT * FROM files WHERE id = ?', [file_id]).fetchone()
        if not row:
            abort(404)
        path = os.path.join(UPLOAD_FOLDER, row['stored_name'])
        if os.path.exists(path):
            os.remove(path)
        conn.execute('DELETE FROM files WHERE id = ?', [file_id])
    return jsonify({'success': True})


if __name__ == '__main__':
    app.run(debug=True, port=5000)
