from flask import Flask, render_template_string, request, redirect, url_for, flash, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import sqlite3
import os
import base64
from datetime import datetime
import uuid

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this'

# Configuration
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Database initialization
def init_db():
    try:
        conn = sqlite3.connect('instagram_clone.db')
        c = conn.cursor()
        
        # Drop existing tables if they exist (for clean start)
        c.execute('DROP TABLE IF EXISTS comments')
        c.execute('DROP TABLE IF EXISTS likes') 
        c.execute('DROP TABLE IF EXISTS posts')
        c.execute('DROP TABLE IF EXISTS users')
        
        # Users table
        c.execute('''CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            bio TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        # Posts table
        c.execute('''CREATE TABLE posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            image_data TEXT NOT NULL,
            caption TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )''')
        
        # Likes table
        c.execute('''CREATE TABLE likes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            post_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (post_id) REFERENCES posts (id),
            UNIQUE(user_id, post_id)
        )''')
        
        # Comments table
        c.execute('''CREATE TABLE comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            post_id INTEGER NOT NULL,
            comment TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (post_id) REFERENCES posts (id)
        )''')
        
        # Create demo users
        demo_password = generate_password_hash('demo123')
        c.execute('INSERT INTO users (username, email, password, bio) VALUES (?, ?, ?, ?)',
                  ('demo_user', 'demo@example.com', demo_password, 'Welcome to my Instagram clone! 📸'))
        c.execute('INSERT INTO users (username, email, password, bio) VALUES (?, ?, ?, ?)',
                  ('photographer', 'photo@example.com', demo_password, 'Professional photographer 📷 ✨'))
        
        conn.commit()
        conn.close()
        print("✅ Database initialized successfully!")
        
    except Exception as e:
        print(f"❌ Database initialization error: {e}")
        # Create a simple fallback database
        try:
            conn = sqlite3.connect('instagram_clone.db')
            c = conn.cursor()
            c.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT, email TEXT, password TEXT)')
            c.execute('CREATE TABLE IF NOT EXISTS posts (id INTEGER PRIMARY KEY, user_id INTEGER, image_data TEXT, caption TEXT)')
            c.execute('CREATE TABLE IF NOT EXISTS likes (id INTEGER PRIMARY KEY, user_id INTEGER, post_id INTEGER)')
            c.execute('CREATE TABLE IF NOT EXISTS comments (id INTEGER PRIMARY KEY, user_id INTEGER, post_id INTEGER, comment TEXT)')
            conn.commit()
            conn.close()
            print("✅ Fallback database created!")
        except Exception as fallback_error:
            print(f"❌ Fallback database error: {fallback_error}")

# Database helper functions with error handling
def get_user_by_username(username):
    try:
        conn = sqlite3.connect('instagram_clone.db')
        c = conn.cursor()
        c.execute('SELECT * FROM users WHERE username = ?', (username,))
        user = c.fetchone()
        conn.close()
        return user
    except Exception as e:
        print(f"Error getting user: {e}")
        return None

def create_user(username, email, password):
    try:
        conn = sqlite3.connect('instagram_clone.db')
        c = conn.cursor()
        hashed_password = generate_password_hash(password)
        c.execute('INSERT INTO users (username, email, password) VALUES (?, ?, ?)',
                  (username, email, hashed_password))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error creating user: {e}")
        return False

def get_posts_for_feed(limit=20):
    conn = sqlite3.connect('instagram_clone.db')
    c = conn.cursor()
    c.execute('''SELECT p.id, p.image_data, p.caption, p.created_at, u.username,
                        (SELECT COUNT(*) FROM likes WHERE post_id = p.id) as like_count,
                        (SELECT COUNT(*) FROM comments WHERE post_id = p.id) as comment_count
                 FROM posts p
                 JOIN users u ON p.user_id = u.id
                 ORDER BY p.created_at DESC
                 LIMIT ?''', (limit,))
    posts = c.fetchall()
    conn.close()
    return posts

def create_post(user_id, image_data, caption):
    try:
        conn = sqlite3.connect('instagram_clone.db')
        c = conn.cursor()
        c.execute('INSERT INTO posts (user_id, image_data, caption) VALUES (?, ?, ?)',
                  (user_id, image_data, caption))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error creating post: {e}")
        return False

def toggle_like(user_id, post_id):
    try:
        conn = sqlite3.connect('instagram_clone.db')
        c = conn.cursor()
        
        # Check if already liked
        c.execute('SELECT id FROM likes WHERE user_id = ? AND post_id = ?', (user_id, post_id))
        existing_like = c.fetchone()
        
        if existing_like:
            c.execute('DELETE FROM likes WHERE user_id = ? AND post_id = ?', (user_id, post_id))
            liked = False
        else:
            c.execute('INSERT INTO likes (user_id, post_id) VALUES (?, ?)', (user_id, post_id))
            liked = True
        
        conn.commit()
        conn.close()
        return liked
    except Exception as e:
        print(f"Error toggling like: {e}")
        return False

def add_comment(user_id, post_id, comment):
    try:
        conn = sqlite3.connect('instagram_clone.db')
        c = conn.cursor()
        c.execute('INSERT INTO comments (user_id, post_id, comment) VALUES (?, ?, ?)',
                  (user_id, post_id, comment))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error adding comment: {e}")
        return False

def get_comments(post_id):
    try:
        conn = sqlite3.connect('instagram_clone.db')
        c = conn.cursor()
        c.execute('''SELECT c.comment, c.created_at, u.username 
                     FROM comments c
                     JOIN users u ON c.user_id = u.id
                     WHERE c.post_id = ?
                     ORDER BY c.created_at ASC''', (post_id,))
        comments = c.fetchall()
        conn.close()
        return comments
    except Exception as e:
        print(f"Error getting comments: {e}")
        return []

def is_liked_by_user(user_id, post_id):
    try:
        conn = sqlite3.connect('instagram_clone.db')
        c = conn.cursor()
        c.execute('SELECT id FROM likes WHERE user_id = ? AND post_id = ?', (user_id, post_id))
        result = c.fetchone()
        conn.close()
        return result is not None
    except Exception as e:
        print(f"Error checking like status: {e}")
        return False

# Main Template
MAIN_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>InstaClone - Social Media App</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background-color: #fafafa;
            color: #262626;
        }
        
        .header {
            background: white;
            border-bottom: 1px solid #dbdbdb;
            padding: 0;
            position: fixed;
            top: 0;
            width: 100%;
            z-index: 1000;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        .nav-container {
            max-width: 975px;
            margin: 0 auto;
            padding: 0 20px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            height: 60px;
        }
        
        .logo {
            font-size: 28px;
            font-weight: bold;
            color: #262626;
            text-decoration: none;
            background: linear-gradient(45deg, #f09433 0%,#e6683c 25%,#dc2743 50%,#cc2366 75%,#bc1888 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        
        .nav-links {
            display: flex;
            align-items: center;
            gap: 20px;
        }
        
        .nav-links a {
            color: #262626;
            text-decoration: none;
            font-weight: 500;
            padding: 8px 12px;
            border-radius: 6px;
            transition: all 0.3s ease;
        }
        
        .nav-links a:hover {
            background: #f5f5f5;
            transform: translateY(-1px);
        }
        
        .main-content {
            margin-top: 60px;
            min-height: calc(100vh - 60px);
            padding: 20px;
        }
        
        .container {
            max-width: 600px;
            margin: 0 auto;
        }
        
        .post {
            background: white;
            border: 1px solid #dbdbdb;
            border-radius: 12px;
            margin-bottom: 24px;
            overflow: hidden;
            box-shadow: 0 2px 10px rgba(0,0,0,0.05);
            transition: transform 0.2s ease;
        }
        
        .post:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 20px rgba(0,0,0,0.1);
        }
        
        .post-header {
            padding: 14px 16px;
            display: flex;
            align-items: center;
            gap: 12px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        
        .post-header .avatar {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            background: white;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            color: #667eea;
        }
        
        .post-header .username {
            font-weight: 600;
            font-size: 16px;
        }
        
        .post-image {
            width: 100%;
            max-height: 600px;
            object-fit: cover;
            display: block;
        }
        
        .post-actions {
            padding: 12px 16px;
            display: flex;
            gap: 16px;
            align-items: center;
            border-bottom: 1px solid #efefef;
        }
        
        .btn-like, .btn-comment {
            background: none;
            border: none;
            cursor: pointer;
            font-size: 24px;
            padding: 8px;
            border-radius: 50%;
            transition: all 0.2s ease;
        }
        
        .btn-like:hover, .btn-comment:hover {
            background: #f5f5f5;
            transform: scale(1.1);
        }
        
        .btn-like.liked {
            animation: likeAnimation 0.4s ease;
        }
        
        @keyframes likeAnimation {
            0% { transform: scale(1); }
            50% { transform: scale(1.3); }
            100% { transform: scale(1); }
        }
        
        .post-info {
            padding: 12px 16px;
        }
        
        .like-count {
            font-weight: 600;
            margin-bottom: 8px;
            color: #262626;
        }
        
        .post-caption {
            margin-bottom: 8px;
            line-height: 1.4;
        }
        
        .post-caption .username {
            font-weight: 600;
            margin-right: 8px;
            color: #262626;
        }
        
        .post-time {
            color: #8e8e8e;
            font-size: 12px;
            margin-bottom: 12px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .comments-section {
            border-top: 1px solid #efefef;
            padding: 12px 16px;
            background: #fafafa;
        }
        
        .comment {
            margin-bottom: 6px;
            font-size: 14px;
        }
        
        .comment .username {
            font-weight: 600;
            margin-right: 8px;
            color: #262626;
        }
        
        .comment-form {
            display: flex;
            gap: 8px;
            margin-top: 12px;
            padding-top: 12px;
            border-top: 1px solid #efefef;
        }
        
        .comment-input {
            flex: 1;
            border: 1px solid #dbdbdb;
            border-radius: 20px;
            padding: 8px 12px;
            outline: none;
            font-size: 14px;
            transition: border-color 0.3s ease;
        }
        
        .comment-input:focus {
            border-color: #0095f6;
        }
        
        .comment-submit {
            background: linear-gradient(45deg, #f09433 0%,#e6683c 25%,#dc2743 50%,#cc2366 75%,#bc1888 100%);
            color: white;
            border: none;
            border-radius: 20px;
            padding: 8px 16px;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s ease;
        }
        
        .comment-submit:hover {
            transform: translateY(-1px);
        }
        
        .comment-submit:disabled {
            background: #ccc;
            cursor: default;
            transform: none;
        }
        
        .upload-form {
            background: white;
            border: 1px solid #dbdbdb;
            border-radius: 12px;
            padding: 30px;
            margin-bottom: 24px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.05);
        }
        
        .upload-form h2 {
            text-align: center;
            margin-bottom: 24px;
            background: linear-gradient(45deg, #f09433 0%,#e6683c 25%,#dc2743 50%,#cc2366 75%,#bc1888 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        
        .file-input-wrapper {
            position: relative;
            display: inline-block;
            cursor: pointer;
            background: linear-gradient(45deg, #f09433 0%,#e6683c 25%,#dc2743 50%,#cc2366 75%,#bc1888 100%);
            color: white;
            padding: 15px 30px;
            border-radius: 25px;
            font-weight: 600;
            transition: all 0.3s ease;
            box-shadow: 0 4px 15px rgba(0,0,0,0.2);
        }
        
        .file-input-wrapper:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(0,0,0,0.3);
        }
        
        .file-input-wrapper input {
            position: absolute;
            left: -9999px;
        }
        
        .form-group {
            margin: 20px 0;
        }
        
        .form-group label {
            display: block;
            margin-bottom: 8px;
            font-weight: 600;
            color: #262626;
        }
        
        .form-group input, .form-group textarea {
            width: 100%;
            padding: 12px;
            border: 1px solid #dbdbdb;
            border-radius: 8px;
            font-size: 14px;
            transition: border-color 0.3s ease;
        }
        
        .form-group input:focus, .form-group textarea:focus {
            border-color: #0095f6;
            outline: none;
        }
        
        .form-group textarea {
            resize: vertical;
            min-height: 100px;
            font-family: inherit;
        }
        
        .btn-primary {
            background: linear-gradient(45deg, #f09433 0%,#e6683c 25%,#dc2743 50%,#cc2366 75%,#bc1888 100%);
            color: white;
            border: none;
            padding: 15px 30px;
            border-radius: 25px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            box-shadow: 0 4px 15px rgba(0,0,0,0.2);
        }
        
        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(0,0,0,0.3);
        }
        
        .alert {
            padding: 12px 20px;
            border-radius: 8px;
            margin-bottom: 16px;
            font-weight: 500;
        }
        
        .alert-error {
            background: linear-gradient(135deg, #ff6b6b, #ee5a5a);
            color: white;
        }
        
        .alert-success {
            background: linear-gradient(135deg, #51cf66, #40c057);
            color: white;
        }
        
        .login-container {
            max-width: 400px;
            margin: 80px auto;
            background: white;
            border: 1px solid #dbdbdb;
            border-radius: 12px;
            padding: 40px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        }
        
        .login-logo {
            text-align: center;
            margin-bottom: 30px;
        }
        
        .login-logo h1 {
            font-size: 36px;
            background: linear-gradient(45deg, #f09433 0%,#e6683c 25%,#dc2743 50%,#cc2366 75%,#bc1888 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        
        .login-logo p {
            color: #8e8e8e;
            margin-top: 8px;
        }
        
        .switch-form {
            text-align: center;
            margin-top: 20px;
        }
        
        .switch-form a {
            color: #0095f6;
            text-decoration: none;
            font-weight: 600;
        }
        
        .switch-form a:hover {
            text-decoration: underline;
        }
        
        .empty-state {
            text-align: center;
            padding: 60px 20px;
            background: white;
            border-radius: 12px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.05);
        }
        
        .empty-state h3 {
            font-size: 24px;
            margin-bottom: 16px;
            color: #262626;
        }
        
        .empty-state p {
            color: #8e8e8e;
            margin-bottom: 24px;
        }
        
        .empty-state a {
            color: #0095f6;
            text-decoration: none;
            font-weight: 600;
        }
        
        @media (max-width: 768px) {
            .container {
                max-width: 100%;
                padding: 0 8px;
            }
            
            .post {
                border-left: none;
                border-right: none;
                border-radius: 0;
                margin-bottom: 0;
            }
            
            .nav-container {
                padding: 0 15px;
            }
            
            .nav-links {
                gap: 10px;
            }
            
            .nav-links a {
                padding: 6px 8px;
                font-size: 14px;
            }
        }
    </style>
</head>
<body>
    {% if session.username %}
    <header class="header">
        <div class="nav-container">
            <a href="{{ url_for('home') }}" class="logo">InstaClone</a>
            <nav class="nav-links">
                <a href="{{ url_for('home') }}">🏠 Home</a>
                <a href="{{ url_for('upload') }}">📸 Upload</a>
                <a href="{{ url_for('logout') }}">🚪 Logout</a>
            </nav>
        </div>
    </header>
    {% endif %}
    
    <main class="main-content">
        {{ content|safe }}
    </main>
    
    <script>
        // Like button functionality
        function toggleLike(postId) {
            fetch('/like/' + postId, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            })
            .then(response => response.json())
            .then(data => {
                const likeBtn = document.querySelector(`[data-post-id="${postId}"] .btn-like`);
                const likeCount = document.querySelector(`[data-post-id="${postId}"] .like-count`);
                
                if (data.liked) {
                    likeBtn.innerHTML = '❤️';
                    likeBtn.classList.add('liked');
                } else {
                    likeBtn.innerHTML = '🤍';
                    likeBtn.classList.remove('liked');
                }
                
                likeCount.textContent = data.like_count + ' likes';
            })
            .catch(error => console.error('Error:', error));
        }
        
        // Comment functionality
        function submitComment(postId) {
            const commentInput = document.querySelector(`[data-post-id="${postId}"] .comment-input`);
            const comment = commentInput.value.trim();
            
            if (!comment) return;
            
            fetch('/comment/' + postId, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({comment: comment})
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Add comment to UI
                    const commentsContainer = document.querySelector(`[data-post-id="${postId}"] .comments`);
                    const newComment = document.createElement('div');
                    newComment.className = 'comment';
                    newComment.innerHTML = `<span class="username">${data.username}</span>${comment}`;
                    commentsContainer.appendChild(newComment);
                    
                    // Clear input
                    commentInput.value = '';
                }
            })
            .catch(error => console.error('Error:', error));
        }
        
        // Enter key for comments
        document.addEventListener('keypress', function(e) {
            if (e.target.classList.contains('comment-input') && e.key === 'Enter') {
                const postId = e.target.closest('[data-post-id]').dataset.postId;
                submitComment(postId);
            }
        });
    </script>
</body>
</html>
'''

# Routes
@app.route('/')
def home():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    posts = get_posts_for_feed()
    
    # Process posts and add like status
    processed_posts = []
    for post in posts:
        post_data = {
            'id': post[0],
            'image_data': post[1],
            'caption': post[2],
            'created_at': post[3],
            'username': post[4],
            'like_count': post[5],
            'comment_count': post[6],
            'is_liked': is_liked_by_user(session['user_id'], post[0]),
            'comments': get_comments(post[0])[:3]  # Show first 3 comments
        }
        processed_posts.append(post_data)
    
    # Flash messages
    messages_html = ""
    messages = session.pop('_flashes', []) if '_flashes' in session else []
    for category, message in messages:
        alert_class = 'alert-success' if category == 'message' else 'alert-error'
        messages_html += f'<div class="alert {alert_class}">{message}</div>'
    
    if not processed_posts:
        content = f'''
        {messages_html}
        <div class="container">
            <div class="empty-state">
                <h3>Welcome to InstaClone! 🎉</h3>
                <p>No posts yet. Be the first to share something amazing!</p>
                <a href="{url_for('upload')}">📸 Upload your first photo</a>
            </div>
        </div>
        '''
    else:
        posts_html = ""
        for post in processed_posts:
            like_icon = "❤️" if post['is_liked'] else "🤍"
            like_class = "liked" if post['is_liked'] else ""
            
            comments_html = ""
            for comment in post['comments']:
                comments_html += f'<div class="comment"><span class="username">{comment[2]}</span>{comment[0]}</div>'
            
            posts_html += f'''
            <article class="post" data-post-id="{post['id']}">
                <header class="post-header">
                    <div class="avatar">{post['username'][0].upper()}</div>
                    <span class="username">{post['username']}</span>
                </header>
                
                <img src="data:image/jpeg;base64,{post['image_data']}" alt="Post image" class="post-image">
                
                <div class="post-actions">
                    <button class="btn-like {like_class}" onclick="toggleLike({post['id']})">{like_icon}</button>
                    <button class="btn-comment" onclick="document.querySelector('[data-post-id=\\'{post['id']}\\'] .comment-input').focus()">💬</button>
                </div>
                
                <div class="post-info">
                    <div class="like-count">{post['like_count']} likes</div>
                    {f'<div class="post-caption"><span class="username">{post["username"]}</span>{post["caption"]}</div>' if post['caption'] else ''}
                    <div class="post-time">{post['created_at']}</div>
                </div>
                
                <div class="comments-section">
                    <div class="comments">{comments_html}</div>
                    <form class="comment-form" onsubmit="event.preventDefault(); submitComment({post['id']})">
                        <input type="text" class="comment-input" placeholder="Add a comment...">
                        <button type="submit" class="comment-submit">Post</button>
                    </form>
                </div>
            </article>
            '''
        
        content = f'''
        {messages_html}
        <div class="container">
            {posts_html}
        </div>
        '''
    
    return MAIN_TEMPLATE.replace('{{ content|safe }}', content).replace('{{ url_for(\'home\') }}', '/').replace('{{ url_for(\'upload\') }}', '/upload').replace('{{ url_for(\'logout\') }}', '/logout')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = get_user_by_username(username)
        if user and check_password_hash(user[3], password):
            session['user_id'] = user[0]
            session['username'] = user[1]
            flash('Welcome back!', 'message')
            return redirect(url_for('home'))
        else:
            flash('Invalid username or password')
    
    # Flash messages
    messages_html = ""
    messages = session.pop('_flashes', []) if '_flashes' in session else []
    for category, message in messages:
        alert_class = 'alert-success' if category == 'message' else 'alert-error'
        messages_html += f'<div class="alert {alert_class}">{message}</div>'
    
    content = f'''
    <div class="login-container">
        <div class="login-logo">
            <h1>InstaClone</h1>
            <p>Share your world 🌟</p>
        </div>
        
        {messages_html}
        
        <form method="POST">
            <div class="form-group">
                <input type="text" name="username" placeholder="Username" required>
            </div>
            <div class="form-group">
                <input type="password" name="password" placeholder="Password" required>
            </div>
            <div class="form-group">
                <button type="submit" class="btn-primary" style="width: 100%;">Log In</button>
            </div>
        </form>
        
        <div class="switch-form">
            Don't have an account? <a href="/register">Sign up</a>
        </div>
        
        <div class="switch-form" style="margin-top: 20px; font-size: 12px; color: #8e8e8e;">
            <strong>Demo Accounts:</strong><br>
            Username: demo_user | Password: demo123<br>
            Username: photographer | Password: demo123
        </div>
    </div>
    '''
    
    return MAIN_TEMPLATE.replace('{{ content|safe }}', content)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        
        if len(password) < 6:
            flash('Password must be at least 6 characters long')
        elif create_user(username, email, password):
            flash('Account created successfully! Please log in.', 'message')
            return redirect(url_for('login'))
        else:
            flash('Username or email already exists')
    
    # Flash messages
    messages_html = ""
    messages = session.pop('_flashes', []) if '_flashes' in session else []
    for category, message in messages:
        alert_class = 'alert-success' if category == 'message' else 'alert-error'
        messages_html += f'<div class="alert {alert_class}">{message}</div>'
    
    content = f'''
    <div class="login-container">
        <div class="login-logo">
            <h1>InstaClone</h1>
            <p>Join the community 🚀</p>
        </div>
        
        {messages_html}
        
        <form method="POST">
            <div class="form-group">
                <input type="text" name="username" placeholder="Username" required>
            </div>
            <div class="form-group">
                <input type="email" name="email" placeholder="Email" required>
            </div>
            <div class="form-group">
                <input type="password" name="password" placeholder="Password (min 6 characters)" required>
            </div>
            <div class="form-group">
                <button type="submit" class="btn-primary" style="width: 100%;">Sign Up</button>
            </div>
        </form>
        
        <div class="switch-form">
            Already have an account? <a href="/login">Log in</a>
        </div>
    </div>
    '''
    
    return MAIN_TEMPLATE.replace('{{ content|safe }}', content)

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file selected')
            return redirect(request.url)
        
        file = request.files['file']
        if file.filename == '':
            flash('No file selected')
            return redirect(request.url)
        
        if file and allowed_file(file.filename):
            # Convert image to base64
            image_data = base64.b64encode(file.read()).decode('utf-8')
            caption = request.form.get('caption', '')
            
            create_post(session['user_id'], image_data, caption)
            flash('Photo uploaded successfully! 📸', 'message')
            return redirect(url_for('home'))
        else:
            flash('Invalid file type. Please upload an image (PNG, JPG, JPEG, GIF)')
    
    # Flash messages
    messages_html = ""
    messages = session.pop('_flashes', []) if '_flashes' in session else []
    for category, message in messages:
        alert_class = 'alert-success' if category == 'message' else 'alert-error'
        messages_html += f'<div class="alert {alert_class}">{message}</div>'
    
    content = f'''
    <div class="container">
        <div class="upload-form">
            <h2>📸 Share a new photo</h2>
            
            {messages_html}
            
            <form method="POST" enctype="multipart/form-data">
                <div class="form-group" style="text-align: center;">
                    <label class="file-input-wrapper">
                        <input type="file" name="file" accept="image/*" required>
                        📷 Choose Photo
                    </label>
                </div>
                
                <div class="form-group">
                    <label for="caption">Caption</label>
                    <textarea name="caption" id="caption" placeholder="Write a caption... ✨"></textarea>
                </div>
                
                <div class="form-group" style="text-align: center;">
                    <button type="submit" class="btn-primary">🚀 Share Photo</button>
                </div>
            </form>
        </div>
    </div>
    '''
    
    return MAIN_TEMPLATE.replace('{{ content|safe }}', content).replace('{{ url_for(\'home\') }}', '/').replace('{{ url_for(\'upload\') }}', '/upload').replace('{{ url_for(\'logout\') }}', '/logout')

@app.route('/like/<int:post_id>', methods=['POST'])
def like_post(post_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    try:
        liked = toggle_like(session['user_id'], post_id)
        
        # Get updated like count
        conn = sqlite3.connect('instagram_clone.db')
        c = conn.cursor()
        c.execute('SELECT COUNT(*) FROM likes WHERE post_id = ?', (post_id,))
        like_count = c.fetchone()[0]
        conn.close()
        
        return jsonify({'liked': liked, 'like_count': like_count})
    except Exception as e:
        print(f"Error in like_post: {e}")
        return jsonify({'error': 'Database error'}), 500

@app.route('/comment/<int:post_id>', methods=['POST'])
def comment_post(post_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    try:
        data = request.get_json()
        comment = data.get('comment', '').strip()
        
        if comment and add_comment(session['user_id'], post_id, comment):
            return jsonify({'success': True, 'username': session['username']})
        
        return jsonify({'error': 'Invalid comment'}), 400
    except Exception as e:
        print(f"Error in comment_post: {e}")
        return jsonify({'error': 'Database error'}), 500

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out successfully! 👋', 'message')
    return redirect(url_for('login'))

if __name__ == '__main__':
    init_db()
    
    print("🚀 Starting InstaClone - Instagram-like Social Media App")
    print("=" * 50)
    print("✨ Features:")
    print("   📸 Photo Upload & Sharing")
    print("   ❤️  Like Posts") 
    print("   💬 Comment System")
    print("   👤 User Authentication")
    print("   📱 Mobile Responsive Design")
    print("   🎨 Instagram-like UI")
    print()
    print("🔑 Demo Accounts:")
    print("   Username: demo_user     | Password: demo123")
    print("   Username: photographer  | Password: demo123")
    print()
    print("🌐 Server starting at: http://127.0.0.1:5000")
    print("=" * 50)
    
    app.run(debug=True, host='127.0.0.1', port=5000)