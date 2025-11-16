from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import timedelta
import os
import csv
import json
import firebase_admin
from firebase_admin import credentials, firestore
from itsdangerous import URLSafeTimedSerializer
from flask_mail import Mail, Message
import random

app = Flask(__name__, static_folder='static')
app.secret_key = 'Varya-Riddle1043'
app.permanent_session_lifetime = timedelta(hours=2)

# ─── Mail Configuration ───
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ['MAIL_USERNAME']
app.config['MAIL_PASSWORD'] = os.environ['MAIL_PASSWORD']
app.config['MAIL_DEFAULT_SENDER'] = ('Ravens & Quill', os.environ['MAIL_USERNAME'])

# ─── Firebase Admin Configuration ───
cred_dict = json.loads(os.environ['FIREBASE_CREDENTIALS'])
cred = credentials.Certificate(cred_dict)

if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)

db = firestore.client()

# Token generator setup
s = URLSafeTimedSerializer(app.config['SECRET_KEY'])



@app.route('/forgot', methods=['GET', 'POST'])
def forgot():
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        doc = db.collection('users').document(email).get()

        if doc.exists:
            try:
                token = s.dumps(email, salt='password-reset-salt')
                reset_url = url_for('reset_password', token=token, _external=True)

                msg = Message("Ravens & Quill – Reset Your Archive Key",
                              recipients=[email])
                msg.body = f"Use this link to reset: {reset_url}"
                mail.send(msg)

                flash("A parchment scroll has been dispatched to your inbox.")
            except Exception as e:
                flash(f"Error sending email: {e}")
        else:
            flash("No archive key found for that email.")

        # Use url_for here to redirect back to the forgot page
        return redirect(url_for('forgot'))

    # Render the forgot.html template
    return render_template('forgot.html')





@app.route('/reset/<token>', methods=['GET', 'POST'])
def reset_password(token):
    try:
        email = s.loads(token, salt='password-reset-salt', max_age=3600)
    except Exception:
        flash("This parchment scroll has expired or is invalid.")
        return redirect(url_for('forgot'))

    if request.method == 'POST':
        new_password = request.form['password']
        confirm_password = request.form['confirm_password']

        if new_password != confirm_password:
            flash("The archive keys do not match. Please try again.")
            return redirect(url_for('reset_password', token=token))

        hashed_pw = generate_password_hash(new_password)
        db.collection('users').document(email).update({"password_hash": hashed_pw})

        flash("Your archive key has been reforged.")
        return redirect(url_for('login'))

    return render_template('reset.html', token=token)




# ─── Signup ───
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        password = request.form['password']
        confirm = request.form['confirm']

        if password != confirm:
            flash("Passwords do not match.")
            return redirect(url_for('signup'))

        doc_ref = db.collection('users').document(email)
        if doc_ref.get().exists:
            flash("An account with this email already exists.")
            return redirect(url_for('signup'))

        # Generate verification token and hash password
        token = secrets.token_urlsafe(32)
        hashed = generate_password_hash(password)

        # ─── Store user in Firestore ───
        doc_ref.set({
            'email': email,
            'password_hash': hashed,
            'joined': datetime.now().strftime('%B %d, %Y'),  # ← here
            'verified': False,
            'verify_token': token
        })

        # ─── Send verification email ───
        verify_link = url_for('verify', token=token, _external=True)
        msg = Message("Verify Your Account – Ravens & Quill",
                      recipients=[email])
        msg.body = f"""
Welcome to Ravens & Quill!

Please verify your account by clicking the link below:
{verify_link}

If you did not sign up, you can safely ignore this message.
"""
        mail.send(msg)

        flash("Account created. Please check your email to verify.")
        return redirect(url_for('login'))

    return render_template('signup.html')



# ─── Verify Email ───
@app.route('/verify')
def verify():
    token = request.args.get('token')
    users = db.collection('users').stream()

    for user in users:
        data = user.to_dict()
        if data.get('verify_token') == token:
            db.collection('users').document(data['email']).update({
                'verified': True,
                'verify_token': firestore.DELETE_FIELD
            })
            return render_template('verify.html')

    flash("Invalid or expired verification link.")
    return redirect(url_for('signup'))


# ─── Login ───
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        password = request.form['password']
        doc = db.collection('users').document(email).get()

        if doc.exists:
            data = doc.to_dict()
            if check_password_hash(data.get('password_hash'), password):
                session.permanent = True
                session['email'] = email
                flash("Welcome back, scribe.")
                return redirect(url_for('profile'))
            else:
                flash("Incorrect password.")
        else:
            flash("No account found.")
    return render_template('login.html')

# ─── Logout ───
@app.route('/logout')
def logout():
    session.clear()
    flash("You have been signed out.")
    return redirect(url_for('home'))

@app.route("/loading")
def loading():
    # Dark academia loading page
    return render_template("loading.html")

# ─── Home ───
@app.route('/')
def home():
    return render_template('home.html')

@app.route('/author')
def author():
    return render_template('author.html')

@app.route('/silence')
def silence():
    return render_template('silence.html')


# ─── Profile ───
@app.route('/profile')
def profile():
    email = session.get('email')
    if not email:
        flash("Please log in.")
        return redirect(url_for('login'))

    doc = db.collection('profiles').document(email).get()
    if doc.exists:
        return render_template('profile.html', profile=doc.to_dict())
    else:
        flash("No profile found. Please inscribe your details.")
        return redirect(url_for('create_profile'))

# ─── Create Profile ───
@app.route('/create-profile', methods=['GET', 'POST'])
def create_profile():
    email = session.get('email')
    if not email:
        flash("Please log in.")
        return redirect(url_for('login'))

    if request.method == 'POST':
        name = request.form['name']
        title = request.form['title']
        quote = request.form['quote']
        bio = request.form['bio']
        joined = request.form['joined']
        image = request.files['image']

        profile_data = {
            'email': email,
            'name': name,
            'title': title,
            'quote': quote,
            'bio': bio,
            'joined': joined
        }

        optional_fields = ['thinkers', 'allegiances', 'relics', 'annotations', 'visions']
        for field in optional_fields:
            value = request.form.get(field)
            if value:
                profile_data[field] = value

        if image and image.filename:
            image_path = os.path.join('static/uploads', secure_filename(image.filename))
            image.save(image_path)
            profile_data['image_url'] = image_path
        else:
            profile_data['image_url'] = url_for('static', filename='profile_icon.png')

        db.collection('profiles').document(email).set(profile_data)
        flash("Profile inscribed.")
        return redirect(url_for('profile'))

    return render_template('create_profile.html')


# ─── Quotes ───
def load_all_quotes():
    quotes = []
    data_folder = os.path.join(os.path.dirname(__file__), 'data')
    for filename in os.listdir(data_folder):
        if filename.endswith('.csv'):
            with open(os.path.join(data_folder, filename), newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    quotes.append({
                        'quote': row.get('Quote', '').strip(),
                        'author': row.get('Author', '').strip(),
                        'genre': row.get('Tag', '').strip().lower()
                    })
    return quotes

@app.route('/quotes', methods=['GET', 'POST'])
def quotes():
    all_quotes = load_all_quotes()
    page = request.args.get('page', default=1, type=int)
    per_page = 20

    # Default slice
    start = (page - 1) * per_page
    end = start + per_page
    filtered = all_quotes[start:end]

    if request.method == 'POST':
        author = request.form.get('author', '').lower()
        genre = request.form.get('genre', '').lower()
        filtered = [
            q for q in all_quotes
            if (author in q['author'].lower()) and (genre in q['genre'].lower())
        ]
        # When searching, you may want to show all results or paginate separately
        has_more = False
    else:
        # Instead of slicing by page, pick 20 random quotes
        filtered = random.sample(all_quotes, min(per_page, len(all_quotes)))
        has_more = False  # no pagination when randomizing

    return render_template(
        'quotes.html',
        quotes=filtered,
        page=page,
        has_more=has_more
    )

# ─── Aesthetics ───
def load_blogs():
    with open('data/blogs.json', encoding='utf-8') as f:
        return json.load(f)

@app.route('/aesthetics')
def aesthetics():
    blogs = load_blogs()
    return render_template('aesthetics.html', blogs=blogs)

@app.route('/aesthetic/<int:blog_id>')
def blog_post(blog_id):
    blogs = load_blogs()
    blog = blogs.get(str(blog_id))
    if blog:
        return render_template('blog_post.html', blog=blog, blog_id=blog_id)
    return "Blog not found", 404

# ─── Create Journal ───
@app.route('/reading-journal/create', methods=['GET', 'POST'])
def create_reading_journal():
    email = session.get('email')
    if not email:
        flash("Please log in.")
        return redirect(url_for('login'))

    if request.method == 'POST':
        journal_data = {
            'title': request.form['title'],
            'author': request.form['author'],
            'cover_image_url': request.form['cover_image_url'],
            'tags': request.form['tags'],
            'theme': request.form['theme'],
            'date_started': request.form['date_started'],
            'date_finished': request.form['date_finished'],
            'status': request.form['status'],
            'is_hidden': request.form['is_hidden'] == 'True',
            'rating_crowns': int(request.form['rating_crowns']),
            'quotes': request.form['quotes'],
            'reflection': request.form['reflection'],
            'thoughts_characters': request.form['thoughts_characters'],
            'thoughts_plot': request.form['thoughts_plot'],
            'user_email': email
        }
        doc_ref = db.collection('journals').document()
        doc_ref.set(journal_data)
        
        # ✅ Redirect after POST
        return redirect(url_for('view_reading_journal', journal_id=doc_ref.id))

    return render_template('create_journal.html')

# ─── View Journal ───
@app.route('/reading-journal/view/<journal_id>')
def view_reading_journal(journal_id):
    email = session.get('email')
    if not email:
        flash("Please log in.")
        return redirect(url_for('login'))

    doc = db.collection('journals').document(journal_id).get()
    if doc.exists and doc.to_dict().get('user_email') == email:
        journal = doc.to_dict()
        journal['id'] = doc.id  # ✅ Needed here

        # Fallback for missing cover image
        if not journal.get('cover_image_url'):
            journal['cover_image_url'] = url_for('static', filename='default-book.png')

        return render_template('journal.html', journal=journal)
    else:
        flash("Journal not found or access denied.")
        return redirect(url_for('all_journals'))


# ─── All Journals Grid ───
@app.route('/reading-journal/all')
def all_journals():
    email = session.get('email')
    if not email:
        flash("Please log in.")
        return redirect(url_for('login'))

    journals_ref = db.collection('journals').where('user_email', '==', email).stream()
    journals = []
    for doc in journals_ref:
        journal = doc.to_dict()
        journal['id'] = doc.id  # Include Firestore document ID
        journals.append(journal)

    return render_template('journals.html', journals=journals)


@app.route('/reading-journal')
def reading_journal_redirect():
    email = session.get('email')
    if not email:
        flash("Please log in.")
        return redirect(url_for('login'))

    journals_ref = db.collection('journals').where('user_email', '==', email).stream()
    first_journal = next(journals_ref, None)

    if first_journal:
        return redirect(url_for('view_reading_journal', journal_id=first_journal.id))
    else:
        return redirect(url_for('create_reading_journal'))
    

@app.route('/reading-journal/delete/<journal_id>', methods=['POST'])
def delete_journal(journal_id):
    email = session.get('email')  # ✅ This must come first

    if not email:
        flash("Please log in.")
        return redirect(url_for('login'))

    doc_ref = db.collection('journals').document(journal_id)
    doc = doc_ref.get()

    if doc.exists and doc.to_dict().get('user_email') == email:
        doc_ref.delete()
        flash("Journal has been sealed and archived.")
    else:
        flash("Access denied or journal not found.")

    return redirect(url_for('all_journals'))

@app.route('/reading-journal/edit/<journal_id>', methods=['GET', 'POST'])
def edit_journal(journal_id):
    email = session.get('email')
    if not email:
        flash("Please log in.")
        return redirect(url_for('login'))

    doc_ref = db.collection('journals').document(journal_id)
    doc = doc_ref.get()

    if not doc.exists or doc.to_dict().get('user_email') != email:
        flash("Access denied or journal not found.")
        return redirect(url_for('all_journals'))

    if request.method == 'POST':
        updated_data = {
            'title': request.form.get('title'),
            'author': request.form.get('author'),
            'cover_image_url': request.form.get('cover_image_url'),
            'tags': request.form.get('tags'),
            'theme': request.form.get('theme'),
            'date_started': request.form.get('date_started'),
            'date_finished': request.form.get('date_finished'),
            'status': request.form.get('status'),
            'is_hidden': request.form.get('is_hidden') == 'True',
            'quotes': request.form.get('quotes'),
            'rating_crowns': int(request.form.get('rating_crowns')),
            'reflection': request.form.get('reflection'),
            'thoughts_characters': request.form.get('thoughts_characters'),
            'thoughts_plot': request.form.get('thoughts_plot'),
        }
        doc_ref.update(updated_data)
        flash("Journal has been revised.")
        return redirect(url_for('view_reading_journal', journal_id=journal_id))

    journal = doc.to_dict()
    journal['id'] = doc.id
    return render_template('edit_journal.html', journal=journal)


@app.route('/profile/edit', methods=['GET', 'POST'])
def edit_profile():
    email = session.get('email')
    if not email:
        flash("Please log in.")
        return redirect(url_for('login'))

    user_ref = db.collection('profiles').document(email)
    user_doc = user_ref.get()
    user_data = user_doc.to_dict() if user_doc.exists else {}

    if request.method == 'POST':
        updated_data = {
            'name': request.form.get('name'),
            'title': request.form.get('title'),
            'quote': request.form.get('quote'),
            'bio': request.form.get('bio'),
            'thinkers': request.form.get('thinkers'),
            'allegiances': request.form.get('allegiances'),
            'relics': request.form.get('relics'),
            'annotations': request.form.get('annotations'),
            'visions': request.form.get('visions'),
            'joined': request.form.get('joined'),
            # Handle image upload separately if needed
        }
        user_ref.update(updated_data)
        flash("Profile updated.")
        return redirect(url_for('profile'))

    return render_template('edit_profile.html', user=user_data)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)

