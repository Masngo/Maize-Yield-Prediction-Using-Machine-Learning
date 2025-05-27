from flask import Flask, request, jsonify, render_template, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import pandas as pd
import numpy as np
import pickle

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# User model
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    role = db.Column(db.String(50), nullable=False)

class Prediction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user_name = db.Column(db.String(150), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    average_rainfall = db.Column(db.Float, nullable=False)
    pesticides_tonnes = db.Column(db.Float, nullable=False)
    avg_temp = db.Column(db.Float, nullable=False)
    area = db.Column(db.String(100), nullable=False)
    predicted_value = db.Column(db.Float, nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            if user.role == 'Admin':
                return redirect(url_for('admin_dashboard'))
            elif user.role == 'Expert':
                return redirect(url_for('expert_dashboard'))
            elif user.role == 'User':
                return redirect(url_for('index'))
        else:
            flash('Login Unsuccessful. Please check username and password', 'danger')

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    if current_user.role != 'User':
        return redirect(url_for('login'))
    return render_template('user/index.html')

@app.route('/admin')
@login_required
def admin_dashboard():
    if current_user.role != 'Admin':
        return redirect(url_for('login'))
    users = User.query.all()
    return render_template('admin/dashboard.html', users=users)

@app.route('/expert')
@login_required
def expert_dashboard():
    if current_user.role != 'Expert':
        return redirect(url_for('login'))
    predictions = Prediction.query.all()
    return render_template('expert/dashboard.html', predictions=predictions)

@app.route('/predict', methods=['POST'])
@login_required
def predict():
    if current_user.role != 'User':
        return redirect(url_for('login'))

    data = request.get_json(force=True)
    required_features = ['Year', 'Average_Rainfall_mm_per_year', 'Pesticides_Tonnes', 'Avg_Temp', 'Area']
    if not all(feature in data for feature in required_features):
        return jsonify({'error': 'Missing data'}), 400

    input_data = pd.DataFrame([data])
    input_data = pd.get_dummies(input_data, columns=['Area'])
    missing_cols = set(columns) - set(input_data.columns)
    for col in missing_cols:
        input_data[col] = 0
    input_data = input_data[columns]
    input_data[['Average_Rainfall_mm_per_year', 'Pesticides_Tonnes', 'Avg_Temp']] = scaler.transform(input_data[['Average_Rainfall_mm_per_year', 'Pesticides_Tonnes', 'Avg_Temp']])
    prediction = model.predict(input_data)

    new_prediction = Prediction(user_id=current_user.id, user_name=current_user.username,
                                year=data['Year'], average_rainfall=data['Average_Rainfall_mm_per_year'],
                                pesticides_tonnes=data['Pesticides_Tonnes'], avg_temp=data['Avg_Temp'],
                                area=data['Area'], predicted_value=-1 * prediction[0])
    db.session.add(new_prediction)
    db.session.commit()

    return jsonify({'prediction': -1 * prediction[0]})

# CRUD Routes for Admin
@app.route('/admin/create_user', methods=['GET', 'POST'])
@login_required
def create_user():
    if current_user.role != 'Admin':
        return redirect(url_for('login'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']
        hashed_password = generate_password_hash(password, method='sha256')
        new_user = User(username=username, password=hashed_password, role=role)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('admin_dashboard'))
    return render_template('admin/create_user.html')

@app.route('/admin/update_user/<int:user_id>', methods=['GET', 'POST'])
@login_required
def update_user(user_id):
    if current_user.role != 'Admin':
        return redirect(url_for('login'))
    user = User.query.get_or_404(user_id)
    if request.method == 'POST':
        user.username = request.form['username']
        user.password = generate_password_hash(request.form['password'], method='sha256')
        user.role = request.form['role']
        db.session.commit()
        return redirect(url_for('admin_dashboard'))
    return render_template('admin/update_user.html', user=user)

@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    if current_user.role != 'Admin':
        return redirect(url_for('login'))
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    return redirect(url_for('admin_dashboard'))

# Load the model, scaler, and columns
with open('model.pkl', 'rb') as f:
    model_data = pickle.load(f)
    model = model_data['model']
    scaler = model_data['scaler']
    columns = model_data['columns']

@app.before_first_request
def create_admin_user():
    admin_user = User.query.filter_by(username='admin').first()
    if not admin_user:
        hashed_password = generate_password_hash('admin', method='sha256')
        new_admin = User(username='admin', password=hashed_password, role='Admin')
        db.session.add(new_admin)
        db.session.commit()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Creates the database and tables
        create_admin_user()  # Create admin user if it doesn't exist
    app.run(debug=True)