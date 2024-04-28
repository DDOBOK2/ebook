from .script import db
from datetime import datetime
from models import User, ReviewSession


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)

    def __repr__(self):
        return f'<User {self.name}>'

class ReviewSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ebook_title = db.Column(db.String(150), nullable=False)
    review_text = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', backref=db.backref('reviews', lazy=True))

    def __repr__(self):
        return f'<ReviewSession {self.ebook_title}>'