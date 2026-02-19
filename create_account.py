from cooperative import app, db
from models import User


with app.app_context():
    db.create_all()

    # Create admin if not exists
    admin = User.query.filter_by(email="abel2micro@gmail.com").first()
    if not admin:
        admin = User(
            full_name="System Admin",
            email="abel2micro@gmail.com",
            role="admin",
            is_member=True,
           
        )
        admin.set_password("abel")
        db.session.add(admin)
        db.session.commit()
        print("Admin created successfully!")

app.run(debug=True)

