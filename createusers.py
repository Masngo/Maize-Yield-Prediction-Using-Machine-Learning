from ast import Module
from app import app, db, User

with app.app_context():
    # Create all the tables
    db.create_all()

    # Create initial users
    

    # Add users to the session and commit
   
    db.session.commit()

 Switchable Module # type: ignore