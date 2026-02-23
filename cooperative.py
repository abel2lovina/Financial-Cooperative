from flask import Flask, render_template, redirect, url_for, request, flash, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from datetime import datetime, timedelta
import os
import uuid
from werkzeug.utils import secure_filename
from itsdangerous import URLSafeTimedSerializer
from flask import current_app

from flask_mail import Mail, Message
from sqlalchemy import func




from flask import abort
from functools import wraps


from config import Config
from models import db, User, LoanRepayment, Loan, Contribution, MembershipApplication, Feedback





def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.role != 'admin':
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

app = Flask(__name__)
#app.config.from_object(Config)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')
app.config.from_object('config.Config')

MEMBERSHIP_FOLDER = os.path.join('static', 'uploads', 'membership')
SELFIE_FOLDER = os.path.join('static', 'uploads', 'selfies')
EVIDENCE_FOLDER = os.path.join('static', 'uploads', 'evidence')

app.config['SELFIE_FOLDER'] = SELFIE_FOLDER
app.config['EVIDENCE_FOLDER'] = EVIDENCE_FOLDER
app.config['MEMBERSHIP_FOLDER'] = MEMBERSHIP_FOLDER

os.makedirs(SELFIE_FOLDER, exist_ok=True)
os.makedirs(EVIDENCE_FOLDER, exist_ok=True)
os.makedirs(MEMBERSHIP_FOLDER, exist_ok=True)



app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'abel2micro@gmail.com'
#app.config['MAIL_PASSWORD'] = 'fuetixmcaqorygkg'
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')

mail = Mail(app)

app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=10)

db.init_app(app)

login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.before_request
def make_session_permanent():
    session.permanent = True

@app.route('/')
def home():
    if current_user.is_authenticated:
        
        return redirect(url_for('member_dashboard'))
    return render_template('home.html')


@app.route('/admin/loans')
@login_required
def admin_loans():
    if current_user.role != 'admin':
        abort(403)
    repayments = LoanRepayment.query.filter_by(status='confirmed').all()
    loans = Loan.query.order_by(Loan.date_requested.desc()).all()
    return render_template('admin_loans.html', loans=loans, repayments=repayments)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form['email']).first()
        if user and user.check_password(request.form['password']):
            login_user(user)
            
            # Redirect based on role
            if user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('member_dashboard'))

        else:
            flash('Invalid email or password', 'danger')

    return render_template('login.html')


@app.route('/member/dashboard')
@login_required
def member_dashboard():

    loans = current_user.loans
    member = MembershipApplication.query.filter_by(
        user_id=current_user.id).first()
    contributions = Contribution.query.filter_by( user_id=current_user.id, status='approved' ).all() 
    total_contribution = sum(c.amount for c in contributions) if contributions else 0 
    
    return render_template(
        'member_dashboard.html',
        loans=loans,
        member=member,        
        total_contribution=total_contribution
    )


@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    check_overdue_loans()
    # Ensure only admins can access
    if current_user.role != 'admin':
        abort(403)

    total_users = User.query.count()

    total_members = MembershipApplication.query.filter_by(status='approved').count()
    # Fetch all contributions (latest first)
    contributions = Contribution.query.order_by(Contribution.date_submitted.desc()).all()

    # Separate pending contributions for admin approval
    pending_contributions = [c for c in contributions if c.status == 'pending']

    # Fetch all loans (latest first)
    loans = Loan.query.order_by(Loan.date_requested.desc()).all()

    return render_template(
        'admin_dashboard.html',
        contributions=contributions,
        pending_contributions=pending_contributions,
        loans=loans,
        total_members=total_members,
        total_users=total_users
    )

@app.route('/admin/repayments')
@login_required
@admin_required
def admin_repayments():

    repayments = LoanRepayment.query.filter_by(status='pending').all()

    return render_template('admin_repayments.html', repayments=repayments)

@app.route('/admin/confirm-repayment/<int:repayment_id>')
@login_required
@admin_required
def confirm_repayment(repayment_id):

    repayment = LoanRepayment.query.get_or_404(repayment_id)
    loan = Loan.query.get_or_404(repayment.loan_id)

    if repayment.status == 'confirmed':
        flash("Repayment already confirmed.", "warning")
        return redirect(url_for('admin_repayments'))

    repayment.status = 'confirmed'

    # reduce loan balance directly
    loan.balance -= repayment.amount_paid

    if loan.balance <= 0:
        loan.balance = 0
        loan.status = 'paid'

    db.session.commit()

    flash("Repayment approved successfully.", "success")
    return redirect(url_for('admin_repayments'))


@app.route('/contributions', methods=['GET', 'POST'])
@login_required

def contributions():
    if request.method == 'POST':
        if not current_user.is_member:
            abort(403)

        amount = request.form['amount']
        file = request.files['evidence']

        filename = None
        if file and file.filename != '':
            filename = str(uuid.uuid4()) + "_" + secure_filename(file.filename)
            file.save(os.path.join(app.config['EVIDENCE_FOLDER'], filename))

        contribution = Contribution(
            user_id=current_user.id,
            amount=amount,
            evidence=filename
        )

        db.session.add(contribution)
        db.session.commit()

        flash('Contribution submitted and awaiting confirmation')
        return redirect(url_for('contributions'))  # redirect back here

    # 🔥 THIS WAS MISSING
    user_contributions = Contribution.query.filter_by(
        user_id=current_user.id
    ).order_by(Contribution.date_submitted.desc()).all()

    return render_template(
        'contributions.html',
        contributions=user_contributions,
        is_member = current_user.is_member
    )

@app.route('/admin/contributions')
@login_required
@admin_required
def admin_contributions():
    contributions = Contribution.query.order_by(
        Contribution.date_submitted.desc()
    ).all()
    return render_template(
        'admin_contributions.html',
        contributions=contributions
    )

@app.route('/admin/contribution/<int:id>/approve')
@login_required
@admin_required
def approve_contribution(id):
    contribution = Contribution.query.get_or_404(id)
    contribution.status = 'approved'
    contribution.date_approved = datetime.utcnow()
    db.session.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/reject_contribution/<int:id>')
@login_required
def reject_contribution(id):
    if current_user.role != 'admin':
        abort(403)
    contribution = Contribution.query.get_or_404(id)
    contribution.status = 'rejected'
    db.session.commit()
    flash('Contribution rejected!', 'warning')
    return redirect(url_for('admin_dashboard'))

@app.route('/loans', methods=['GET', 'POST'])
@login_required
def loans():
    if request.method == 'POST':
        amount = float(request.form['amount'])
        duration = int(request.form['duration_months'])
        account_number = request.form['acct_number']
        address = request.form['address']

        g1_name = request.form['g1_name']
        g1_phone = request.form['g1_phone']
        g2_name = request.form['g2_name']
        g2_phone = request.form['g2_phone']

        selfie_file = request.files['selfie']
        filename = secure_filename(selfie_file.filename)
        selfie_path = os.path.join(app.config['SELFIE_FOLDER'], filename)
        selfie_file.save(selfie_path)

        # calculate initial repayment including 5% interest
        if current_user.is_member == True:
            interest_rate = 0.05
        else:
            interest_rate = 0.10

        now = datetime.utcnow()

        repayment_amount = amount + (amount * interest_rate * duration)

        due_date = datetime.utcnow() + timedelta(days=30*duration)

        loans = Loan(
            amount=amount,
            balance=repayment_amount,
            account_number=account_number,
            repayment_amount=repayment_amount,
            duration_months=duration,
            due_date=due_date,
            address=address,
            selfie=filename,
            guarantor1_name=g1_name,
            guarantor1_phone=g1_phone,
            guarantor2_name=g2_name,
            guarantor2_phone=g2_phone,
            user_id=current_user.id,
            
        )

        db.session.add(loans)
        db.session.commit()
        flash('Loan application submitted!')
        return redirect(url_for('member_dashboard'))

    my_loans = Loan.query.filter_by(user_id=current_user.id).order_by(Loan.date_requested.desc()).all()
    return render_template('loans.html', loans=my_loans, now=datetime.utcnow())

def check_overdue_loans():
    loans = Loan.query.filter(Loan.status=='approved').all()
    for loan in loans:
        if loan.balance > 0 and datetime.utcnow() > loan.due_date:
            # mark overdue
            loan.overdue = True
            # add 5% penalty on balance
            loan.balance += loan.balance * 0.05
            db.session.commit()

@app.route('/admin/loan_action/<int:loan_id>/<action>')
@login_required
def loan_action(loan_id, action):
    if current_user.role != 'admin':
        abort(403)
    
    loan = Loan.query.get_or_404(loan_id)
    if action == 'approve':
        loan.status = 'approved'
    elif action == 'reject':
        loan.status = 'rejected'
    db.session.commit()
    flash(f'Loan {action}d successfully!', 'success')
    return redirect(url_for('admin_loans'))



@app.route('/submit_repayment/<int:loan_id>', methods=['POST'])
@login_required
def submit_repayment(loan_id):
    loan = Loan.query.get_or_404(loan_id)

    if loan.user_id != current_user.id:
        abort(403)

    amount = float(request.form['amount_paid'])
    file = request.files['evidence']

    filename = str(uuid.uuid4()) + "_" + secure_filename(file.filename)
    file.save(os.path.join(app.config['EVIDENCE_FOLDER'], filename))

    repayment = LoanRepayment(
        loan_id=loan.id,
        user_id=current_user.id,
        amount_paid=amount,
        evidence=filename
    )

    db.session.add(repayment)
    db.session.commit()

    flash("Repayment submitted for admin approval")
    return redirect(url_for('loans'))



@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        full_name = request.form['full_name']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        # Check password match
        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return redirect(url_for('register'))

        # Check if email exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash("Email already registered.", "danger")
            return redirect(url_for('register'))

        user = User(
            full_name=full_name,
            email=email
        )
        
        user.set_password(password)

        db.session.add(user)
        db.session.commit()

        flash("Account created successfully, login!", "success")
        return redirect(url_for('login'))

    return render_template('register.html')



@app.route('/apply-membership', methods=['GET', 'POST'])
@login_required
def apply_membership():

    existing_application = MembershipApplication.query.filter_by(
        user_id=current_user.id,
        status='pending'
    ).first()

    if existing_application:
        flash("You already have a pending application.", "warning")
        return redirect(url_for('member_dashboard'))

    if request.method == 'POST':

        payment_file = request.files.get('payment_evidence')
        passport_file = request.files.get('passport')

        payment_filename = None
        passport_filename = None

        if payment_file:
            payment_filename = str(uuid.uuid4()) + "_" + secure_filename(payment_file.filename)
            payment_file.save(os.path.join(app.config['EVIDENCE_FOLDER'], payment_filename))

        if passport_file:
            passport_filename = str(uuid.uuid4()) + "_" + secure_filename(passport_file.filename)
            passport_file.save(os.path.join(app.config['MEMBERSHIP_FOLDER'], passport_filename))

        application = MembershipApplication(
            user_id=current_user.id,
            phone_number=request.form.get('phone_number'),
            full_name=request.form.get('full_name'),
            email=request.form.get('email'),
            residential_address=request.form.get('residential_address'),
            psn_number=request.form.get('psn_number'),
            grade_level=request.form.get('grade_level'),
            next_of_kin=request.form.get('next_of_kin'),
            next_of_kin_phone=request.form.get('next_of_kin_phone'),
            monthly_saving=request.form.get('monthly_saving'),
            payment_evidence=payment_filename,
            passport=passport_filename,
            status='pending'
           
        )

        db.session.add(application)
        db.session.commit()

        flash("Application submitted successfully!", "success")
        return redirect(url_for('member_dashboard'))

    return render_template('apply_membership.html')



@app.route('/admin/membership/approve/<int:application_id>')
@login_required
@admin_required
def approve_membership(application_id):

    application = MembershipApplication.query.get_or_404(application_id)
    application.status = 'approved'
    user = User.query.get(application.user_id)
    user.is_member = True

    db.session.commit()

    flash("Membership approved successfully!", "success")
    return redirect(url_for('admin_membership'))



@app.route('/admin/memberships')
@login_required
@admin_required
def admin_membership():

    applications = MembershipApplication.query.order_by(
        MembershipApplication.date_applied.desc()
    ).all()

    return render_template(
        'admin_membership.html',
        applications=applications
    )



@app.route('/admin/membership/reject/<int:application_id>')
@login_required
@admin_required
def reject_membership(application_id):

    application = MembershipApplication.query.get_or_404(application_id)
    application.status = 'rejected'

    db.session.commit()

    flash("Membership rejected.", "warning")
    return redirect(url_for('admin_membership'))


@app.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        old_password = request.form['old_password']
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']

        if not current_user.check_password(old_password):
            flash("Old password incorrect", "danger")
            return redirect(request.url)

        if new_password != confirm_password:
            flash("New passwords do not match", "danger")
            return redirect(request.url)

        current_user.set_password(new_password)
        db.session.commit()
        flash("Password changed successfully!", "success")
        return redirect(url_for('logout'))

    return render_template('change_password.html')

def generate_reset_token(self):
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    return serializer.dumps(self.email, salt='password-reset-salt')

@staticmethod
def verify_reset_token(token, expiration=3600):
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        email = serializer.loads(
            token,
            salt='password-reset-salt',
            max_age=expiration
        )
    except:
        return None
    return User.query.filter_by(email=email).first()

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():

    if request.method == 'POST':
        email = request.form['email']
        user = User.query.filter_by(email=email).first()

        if user:
            token = user.generate_reset_token()
            reset_link = url_for('reset_password', token=token, _external=True)

            msg = Message(
                subject="Password Reset Request",
                sender=app.config['MAIL_USERNAME'],
                recipients=[email]
            )

            msg.body = f"""
            Click the link below to reset your password:

            {reset_link}

            If you did not request this, ignore this email.
            """

            mail.send(msg)

            flash("Password reset link sent to your email.", "success")
        else:
            flash("Email not found", "danger")

    return render_template('forgot_password.html')



@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    user = User.verify_reset_token(token)
    if not user:
        flash("Invalid or expired token", "danger")
        return redirect(url_for('login'))

    if request.method == 'POST':
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']

        if new_password != confirm_password:
            flash("Passwords do not match", "danger")
            return redirect(request.url)

        user.set_password(new_password)
        db.session.commit()
        flash("Password updated successfully!", "success")
        return redirect(url_for('login'))

    return render_template('reset_password.html')

@app.route('/feedback', methods=['GET', 'POST'])
@login_required
def feedback():

    if request.method == 'POST':
        fb = Feedback(
            user_id=current_user.id,
            message=request.form['message'],
            rating=int(request.form['rating'])
        )
        db.session.add(fb)
        db.session.commit()

        flash("Thank you for your feedback!", "success")
        return redirect(url_for('member_dashboard'))

    return render_template('feedback.html')


@app.route('/admin/feedback')
@login_required
def admin_feedback():
    if current_user.role != 'admin':
        abort(403)

    feedbacks = Feedback.query.order_by(Feedback.date_submitted.desc()).all()
    return render_template('admin_feedback.html', feedbacks=feedbacks)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route("/ping")
def ping():
    return "OK", 200


with app.app_context():
    db.create_all()

if __name__ == '__main__':
    with app.app_context():
    
        port = int(os.environ.get("PORT", 10000))  # fallback to 10000 if PORT not set
        app.run(host="0.0.0.0", port=port, debug=False)
