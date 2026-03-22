from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = "users"
    id         = db.Column(db.Integer, primary_key=True)
    google_sub = db.Column(db.String(128), unique=True, nullable=False, index=True)
    email      = db.Column(db.String(256), unique=True, nullable=False)
    name       = db.Column(db.String(256))
    picture    = db.Column(db.String(512))
    is_admin   = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    videos = db.relationship("Video", back_populates="author", lazy="dynamic", cascade="all, delete-orphan")
    likes  = db.relationship("Like",  back_populates="user",   lazy="dynamic", cascade="all, delete-orphan")


class Video(db.Model):
    __tablename__ = "videos"
    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    filename    = db.Column(db.String(256), nullable=False)
    title       = db.Column(db.String(256))
    description = db.Column(db.Text)
    # Gemini-generated vocabulary JSON string
    vocab_json  = db.Column(db.Text)
    vocab_ready = db.Column(db.Boolean, default=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

    author   = db.relationship("User",  back_populates="videos")
    likes    = db.relationship("Like",  back_populates="video", lazy="dynamic", cascade="all, delete-orphan")

    def like_count(self):
        return self.likes.count()

    def is_liked_by(self, user_id):
        return self.likes.filter_by(user_id=user_id).first() is not None


class Like(db.Model):
    __tablename__ = "likes"
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    video_id   = db.Column(db.Integer, db.ForeignKey("videos.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user  = db.relationship("User",  back_populates="likes")
    video = db.relationship("Video", back_populates="likes")

    __table_args__ = (db.UniqueConstraint("user_id", "video_id", name="uq_like"),)
