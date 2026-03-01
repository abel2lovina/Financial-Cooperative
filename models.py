from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
from itsdangerous import URLSafeTimedSerializer
from flask import current_app
db = SQLAlchemy()

from werkzeug.security import generate_password_hash, check_password_hash

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='member')  # admin or member
    date_joined = db.Column(db.DateTime, default=datetime.utcnow)

    repayment = db.relationship('LoanRepayment', backref='member', lazy=True)
    contributions = db.relationship('Contribution', backref='member', lazy=True)
    loans = db.relationship('Loan', backref='member', lazy=True)
    membership_applications = db.relationship(
        'MembershipApplication',
        backref='user',
        lazy=True
    )
    is_member = db.Column(db.Boolean, default=False)
    membership_evidence = db.Column(db.String(500))
    membership_date_applied = db.Column(db.DateTime)
    membership_date_approved = db.Column(db.DateTime)

    membership_fee = db.Column(db.Float, default=0)
   
    
    # helper methods
    def set_password(self, password):
        self.password = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password, password)

    def generate_reset_token(self, expires_sec=3600):
        s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        return s.dumps({'user_id': self.id})

    @staticmethod
    def verify_reset_token(token):
        from itsdangerous import BadSignature
        s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        try:
            data = s.loads(token)
            user_id = data.get('user_id')
        except BadSignature:
            return None
        return User.query.get(user_id)

class Contribution(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    evidence = db.Column(db.String(500))  # filename or text
    status = db.Column(db.String(20), default='pending')  
    # pending | approved | rejected

    date_submitted = db.Column(db.DateTime, default=datetime.utcnow)
    date_approved = db.Column(db.DateTime)

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)


class Loan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    amount = db.Column(db.Float, nullable=False)
    balance = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected, paid
    account_number = db.Column(db.String(50))
    address = db.Column(db.String(200))
    selfie = db.Column(db.String(500))
    guarantor1_name = db.Column(db.String(100))
    guarantor1_phone = db.Column(db.String(20))
    guarantor2_name = db.Column(db.String(100))
    guarantor2_phone = db.Column(db.String(20))
    loan_repayment = db.relationship('LoanRepayment', backref='members', lazy=True)
    # New fields for repayment logic
    duration_months = db.Column(db.Integer)
    monthly_interest_rate = db.Column(db.Float, default=0.05)  # 5% interest
    repayment_amount = db.Column(db.Float)
    due_date = db.Column(db.DateTime)
    overdue = db.Column(db.Boolean, default=False)


    date_requested = db.Column(db.DateTime, default=datetime.utcnow)

class LoanRepayment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    loan_id = db.Column(db.Integer, db.ForeignKey('loan.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

    amount_paid = db.Column(db.Float, nullable=False)
    evidence = db.Column(db.String(500))
    status = db.Column(db.String(20), default='pending')  # pending, confirmed

    date_submitted = db.Column(db.DateTime, default=datetime.utcnow)


class MembershipApplication(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    full_name = db.Column(db.String(150), nullable=False)
    phone_number = db.Column(db.String(20), nullable=False)
    residential_address = db.Column(db.String(300), nullable=False)
    psn_number = db.Column(db.String(50))
    email = db.Column(db.String(120), nullable=False)
    grade_level = db.Column(db.String(50))
    next_of_kin = db.Column(db.String(150))
    next_of_kin_phone = db.Column(db.String(20))
    monthly_saving = db.Column(db.Float)
  
    payment_evidence = db.Column(db.String(200))
    passport = db.Column(db.String(500))

    status = db.Column(db.String(20), default='pending')  # pending / approved / rejected

    date_applied = db.Column(db.DateTime, default=datetime.utcnow)

class Feedback(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    message = db.Column(db.Text)
    rating = db.Column(db.Integer)
    date_submitted = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='feedbacks')



