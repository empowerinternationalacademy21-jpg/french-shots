"""
FrenchShots — app.py
TikTok-style French video feed with Gemini vocabulary breakdown.
"""

import io, json, os, uuid, textwrap

from google import genai
from authlib.integrations.flask_client import OAuth
from flask import (
    Flask, abort, flash, jsonify, redirect,
    render_template, request, send_file, session, url_for,
)
from flask_session import Session
from flask_wtf.csrf import CSRFProtect
from werkzeug.utils import secure_filename

from models import Like, User, Video, db


# ─────────────────────────────────────────────────────────────
#  FACTORY
# ─────────────────────────────────────────────────────────────

def create_app():
    app = Flask(__name__)

    # ── Config ──────────────────────────────────────────────
    app.config["SECRET_KEY"]              = os.environ.get("SECRET_KEY", "frenchshots-dev-secret")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///frenchshots.db")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["UPLOAD_FOLDER"]           = os.path.join("static", "uploads", "videos")
    app.config["MAX_CONTENT_LENGTH"]      = 200 * 1024 * 1024   # 200 MB

    # ── Session ──────────────────────────────────────────────
    app.config["SESSION_TYPE"]     = "filesystem"
    app.config["SESSION_FILE_DIR"] = ".flask_session"
    app.config["SESSION_PERMANENT"] = False
    os.makedirs(".flask_session", exist_ok=True)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    # ── OAuth / Google ───────────────────────────────────────
    app.config["GOOGLE_CLIENT_ID"]     = os.environ.get("GOOGLE_CLIENT_ID",     "YOUR_GOOGLE_CLIENT_ID")
    app.config["GOOGLE_CLIENT_SECRET"] = os.environ.get("GOOGLE_CLIENT_SECRET", "YOUR_GOOGLE_CLIENT_SECRET")

    # ── Gemini ───────────────────────────────────────────────
    gemini_key  = os.environ.get("GEMINI_API_KEY", "")
    genai_client = genai.Client(api_key=gemini_key) if gemini_key else None

    # ── Extensions ───────────────────────────────────────────
    db.init_app(app)
    Session(app)
    CSRFProtect(app)

    oauth = OAuth(app)
    google = oauth.register(
        name="google",
        client_id=app.config["GOOGLE_CLIENT_ID"],
        client_secret=app.config["GOOGLE_CLIENT_SECRET"],
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )

    # ─────────────────────────────────────────────────────────
    #  HELPERS
    # ─────────────────────────────────────────────────────────

    def current_user():
        uid = session.get("user_id")
        return User.query.get(uid) if uid else None

    def login_required(f):
        from functools import wraps
        @wraps(f)
        def decorated(*args, **kwargs):
            if not current_user():
                return jsonify({"error": "login_required"}), 401
            return f(*args, **kwargs)
        return decorated

    ALLOWED_VIDEO = {"mp4", "mov", "webm", "mkv"}

    def allowed_video(filename):
        return "." in filename and filename.rsplit(".", 1)[-1].lower() in ALLOWED_VIDEO

    # ─────────────────────────────────────────────────────────
    #  GEMINI VOCAB PROMPT
    # ─────────────────────────────────────────────────────────

    VOCAB_SYSTEM = textwrap.dedent("""
        You are an expert French language teacher.
        The user will give you a short description or title of a French video clip.
        Your job is to extract or invent a realistic vocabulary list that a learner
        watching that video would encounter.

        Respond with ONLY a valid JSON array — no markdown, no explanation — like this:
        [
          {
            "word": "le boulanger",
            "type": "noun",
            "translation": "the baker",
            "example_fr": "Le boulanger prépare le pain.",
            "example_en": "The baker prepares the bread.",
            "pronunciation": "luh boo-lahn-ZHAY"
          }
        ]

        Include 8–14 words. Cover nouns, verbs, adjectives, and useful phrases.
        Keep it relevant to the video topic.
    """).strip()

    def generate_vocab(video_title: str, video_description: str) -> list:
        """Call Gemini and return a list of vocab dicts."""
        if not genai_client:
            return []
        try:
            full_prompt = (
                VOCAB_SYSTEM
                + f"\n\nVideo title: {video_title}\nDescription: {video_description or 'French video clip'}"
            )
            response = genai_client.models.generate_content(
                model="gemini-2.0-flash",
                contents=full_prompt,
            )
            raw = response.text.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            return json.loads(raw)
        except Exception as e:
            print(f"[Gemini error] {e}")
            return []

    # ─────────────────────────────────────────────────────────
    #  AUTH
    # ─────────────────────────────────────────────────────────

    @app.route("/auth/login")
    def auth_login():
        redirect_uri = url_for("auth_callback", _external=True)
        return google.authorize_redirect(redirect_uri)

    @app.route("/auth/callback")
    def auth_callback():
        token    = google.authorize_access_token()
        userinfo = token.get("userinfo") or google.userinfo()

        sub     = userinfo["sub"]
        email   = userinfo.get("email", "")
        name    = userinfo.get("name", "")
        picture = userinfo.get("picture", "")

        user = User.query.filter_by(google_sub=sub).first()
        if not user:
            user = User(google_sub=sub, email=email, name=name, picture=picture)
            if User.query.count() == 0:
                user.is_admin = True
            db.session.add(user)
            db.session.commit()
        else:
            user.name    = name
            user.picture = picture
            db.session.commit()

        session["user_id"] = user.id
        flash(f"Welcome back, {name}.", "success")
        return redirect(url_for("index"))

    @app.route("/auth/logout")
    def auth_logout():
        session.clear()
        return redirect(url_for("index"))

    # ─────────────────────────────────────────────────────────
    #  MAIN FEED
    # ─────────────────────────────────────────────────────────

    @app.route("/")
    def index():
        user   = current_user()
        videos = Video.query.order_by(Video.uploaded_at.desc()).all()
        return render_template("index.html", user=user, videos=videos)

    # ─────────────────────────────────────────────────────────
    #  VIDEO UPLOAD
    # ─────────────────────────────────────────────────────────

    @app.route("/upload", methods=["POST"])
    def upload_video():
        user = current_user()
        if not user:
            flash("Sign in with Google to upload.", "warning")
            return redirect(url_for("index"))

        file        = request.files.get("video")
        title       = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()

        if not file or not allowed_video(file.filename):
            flash("Please upload a valid video file (.mp4, .mov, .webm).", "danger")
            return redirect(url_for("index"))

        ext      = file.filename.rsplit(".", 1)[-1].lower()
        filename = f"{uuid.uuid4().hex}.{ext}"
        path     = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(path)

        # Pre-generate vocabulary synchronously
        vocab = generate_vocab(title or "French video", description)

        video = Video(
            user_id     = user.id,
            filename    = filename,
            title       = title or "Untitled",
            description = description,
            vocab_json  = json.dumps(vocab),
            vocab_ready = bool(vocab),
        )
        db.session.add(video)
        db.session.commit()

        flash("Video uploaded successfully.", "success")
        return redirect(url_for("index"))

    # ─────────────────────────────────────────────────────────
    #  API — VOCAB BREAKDOWN
    # ─────────────────────────────────────────────────────────

    @app.route("/api/vocab/<int:video_id>")
    def api_vocab(video_id):
        video = Video.query.get_or_404(video_id)

        if video.vocab_ready and video.vocab_json:
            try:
                return jsonify({"vocab": json.loads(video.vocab_json)})
            except Exception:
                pass

        # Generate on demand if not cached
        vocab = generate_vocab(video.title or "French video", video.description or "")
        video.vocab_json  = json.dumps(vocab)
        video.vocab_ready = bool(vocab)
        db.session.commit()
        return jsonify({"vocab": vocab})

    # ─────────────────────────────────────────────────────────
    #  API — LIKE TOGGLE
    # ─────────────────────────────────────────────────────────

    @app.route("/api/like/<int:video_id>", methods=["POST"])
    def api_like(video_id):
        user = current_user()
        if not user:
            return jsonify({"error": "login_required"}), 401

        video    = Video.query.get_or_404(video_id)
        existing = Like.query.filter_by(user_id=user.id, video_id=video_id).first()

        if existing:
            db.session.delete(existing)
            liked = False
        else:
            db.session.add(Like(user_id=user.id, video_id=video_id))
            liked = True

        db.session.commit()
        return jsonify({"liked": liked, "count": video.like_count()})

    # ─────────────────────────────────────────────────────────
    #  ERROR HANDLERS
    # ─────────────────────────────────────────────────────────

    @app.errorhandler(404)
    def not_found(e):
        return render_template("404.html", user=current_user()), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template("500.html", user=current_user()), 500

    # ── DB init ──────────────────────────────────────────────
    with app.app_context():
        db.create_all()

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
