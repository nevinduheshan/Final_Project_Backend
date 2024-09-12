from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_mysqldb import MySQL
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import pickle
import pandas as pd
from flask_cors import CORS


app = Flask(__name__)

CORS(app)

# Configure MySQL
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'root'
app.config['MYSQL_DB'] = 'final_pro'
app.config['SECRET_KEY'] = 'a24bb47c18e3b40414e155404c50bfda'

mysql = MySQL(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Load the model and encoder
model = pickle.load(open(r'C:\\Users\\nevin\\OneDrive\\Desktop\\react_flask\\Final_Project_React\\backend_new\\trained_model.pickle', 'rb'))
encoder = pickle.load(open(r'C:\\Users\\nevin\\OneDrive\\Desktop\\react_flask\\Final_Project_React\\backend_new\\encoder.pickle', 'rb'))

# User class for login
class User(UserMixin):
    def __init__(self, id, username):
        self.id = id
        self.username = username

@login_manager.user_loader
def load_user(user_id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT id, username FROM users WHERE id = %s", (user_id,))
    user_data = cur.fetchone()
    if user_data:
        return User(user_data[0], user_data[1])
    return None


@app.route("/")
def index():
    return render_template('index.html')

@app.route('/login', methods=['POST'])
def login():
    username = request.json.get('username')
    password = request.json.get('password')

    cur = mysql.connection.cursor()
    cur.execute("SELECT id, password FROM users WHERE username = %s", (username,))
    user_data = cur.fetchone()

    if user_data and bcrypt.check_password_hash(user_data[1], password):
        user = User(user_data[0], username)
        login_user(user)
        return jsonify({"message": "Login successful", "username": username}), 200
    else:
        return jsonify({"message": "Invalid credentials"}), 401

@app.route('/adminLogin', methods=['POST'])
def admin_login():
    username = request.json.get('username')
    password = request.json.get('password')

    # Check if username and password are correct
    if username == 'admin' and password == '123':
        login_user(User(id=0, username='admin'))  # Admin user with ID 0
        return jsonify({"message": "Admin login successful", "username": "admin"}), 200
    else:
        return jsonify({"message": "Invalid admin credentials"}), 401

@app.route('/admin/users', methods=['GET'])
def get_users():
    cur = mysql.connection.cursor()
    cur.execute("SELECT id, username, phone, name FROM users")
    users = cur.fetchall()
    cur.close()

    user_list = []
    for user in users:
        user_list.append({
            'id': user[0],
            'username': user[1],
            'phone': user[2],
            'name': user[3]
        })

    return jsonify(user_list), 200

@app.route('/admin/users/<int:id>', methods=['DELETE'])
def delete_user(id):
    try:
        cur = mysql.connection.cursor()
        cur.execute("DELETE FROM users WHERE id = %s", (id,))
        mysql.connection.commit()
        cur.close()

        return jsonify({"message": "User deleted successfully!"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500



@app.route('/dashboard')
@login_required
def dashboard():
    return f"Welcome {current_user.username}"

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route('/register', methods=['POST'])
def register():
    if request.method == 'POST':
        data = request.get_json()  # Retrieve JSON data
        username = data['username']
        password = data['password']
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        phone = data['phone']
        name = data['name']

        # Check if user already exists
        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE username = %s", (username,))
        existing_user = cur.fetchone()
        
        if existing_user:
            return jsonify({"message": "User already exists!"}), 400
        
        # Insert new user
        cur.execute("INSERT INTO users (username, password, phone, name) VALUES (%s, %s, %s, %s)", (username, hashed_password, phone, name))
        mysql.connection.commit()
        cur.close()

        return jsonify({"message": "User registered successfully!"}), 201


@app.route('/submit_contact', methods=['POST'])
def submit_contact():
    data = request.json

    first_name = data.get('first_name')
    last_name = data.get('last_name')
    email = data.get('email')
    phone_number = data.get('phone_number')
    message = data.get('message')

    # Validate the input (optional)
    if not first_name or not email or not message:
        return jsonify({"error": "Please fill in all required fields"}), 400

    # Insert data into MySQL
    try:
        cur = mysql.connection.cursor()
        cur.execute(
            "INSERT INTO contacts (first_name, last_name, email, phone_number, message) VALUES (%s, %s, %s, %s, %s)",
            (first_name, last_name, email, phone_number, message)
        )
        mysql.connection.commit()
        cur.close()

        return jsonify({"success": "Contact form submitted successfully"}), 200

    except Exception as e:
        print(e)
        return jsonify({"error": "An error occurred while saving your message"}), 500


@app.route('/predict', methods=['POST'])
def predict():
    data = request.json
    df = pd.DataFrame(data, index=[0])
    
    # Preprocessing similar to your FastAPI implementation
    df.rename(columns={
        'date': 'Date',
        "selling_mark": "Selling Mark",
        "grade": "Grade",
        "invoice_no": 'Invoice No',
        "lot_no": 'Lot No',
        "bag_weight": 'Bag Weight',
        "no_of_bags": 'No of Bags'
    }, inplace=True)
    
    df[["day", "month", "year"]] = df["Date"].str.split("/", expand=True)
    df.drop(columns=["Date"], inplace=True)
    df = df.astype({"day": int, "month": int, "year": int})
    
    df_objects = df.loc[:, ["Selling Mark", "Grade"]]
    df_objects_t = encoder.transform(df_objects).toarray()
    
    df.drop(columns=["Selling Mark", "Grade"], inplace=True)
    enc_list = encoder.categories_[0].tolist() + encoder.categories_[1].tolist()
    df_t = pd.DataFrame(df_objects_t, columns=enc_list)
    
    dff = pd.concat([df, df_t], axis=1)
    
    # Convert 'no_of_bags' and 'bag_weight' to numeric types
    no_of_bags = int(data['no_of_bags'])
    bag_weight = float(data['bag_weight'])
    
    # Prediction
    result = model.predict(dff.values)
    
    # Calculate nett_qty and prepare the response
    nett_qty = no_of_bags * bag_weight
    response = {"price": round(result[0], 2), "amount": round(result[0] * nett_qty, 2)}
    
    return jsonify(response)

if __name__ == "__main__":
    app.run(debug=True, port=8000)
