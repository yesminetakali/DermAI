import os
from flask import Flask, render_template, request, redirect, session, flash
import numpy as np
from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing import image
import mysql.connector
 
app = Flask(__name__)
app.secret_key = "secret"
 
UPLOAD_FOLDER = "static/uploads/"
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
 
model = load_model("model/vgg16_skin_cancer.h5", compile=False)
 
db_config = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "skin_cancer_db"
}
 
def get_db():
    return mysql.connector.connect(**db_config)
 
 
# LOGIN
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = request.form["username"]
        pwd  = request.form["password"]
        conn = get_db()
        cur  = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM users WHERE username=%s AND password=%s", (user, pwd))
        result = cur.fetchone()
        cur.close(); conn.close()
        if result:
            session["user"] = user
            flash("Login réussi ✓", "success")
            return redirect("/dashboard")
        else:
            flash("Nom d'utilisateur ou mot de passe incorrect ✗", "danger")
    return render_template("login.html")
 
 
# INSCRIPTION
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        firstname        = request.form["firstname"]
        lastname         = request.form["lastname"]
        username         = request.form["username"]
        specialty        = request.form["specialty"]
        password         = request.form["password"]
        confirm_password = request.form["confirm_password"]
 
        if password != confirm_password:
            flash("Les mots de passe ne correspondent pas ✗", "danger")
            return redirect("/register")
 
        conn = get_db()
        cur  = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM users WHERE username=%s", (username,))
        existing = cur.fetchone()
 
        if existing:
            flash("Ce nom d'utilisateur est déjà pris ✗", "danger")
            cur.close(); conn.close()
            return redirect("/register")
 
        cur.execute(
            "INSERT INTO users (firstname, lastname, username, specialty, password) VALUES (%s, %s, %s, %s, %s)",
            (firstname, lastname, username, specialty, password)
        )
        conn.commit()
        cur.close(); conn.close()
 
        flash("Compte créé avec succès ! Vous pouvez vous connecter ✓", "success")
        return redirect("/")
 
    return render_template("register.html")
 
 
# DASHBOARD
@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/")
    conn = get_db()
    cur  = conn.cursor(dictionary=True)
 
    cur.execute("SELECT COUNT(*) AS total FROM patients WHERE username=%s", (session["user"],))
    total = cur.fetchone()["total"]
 
    cur.execute("SELECT COUNT(*) AS benign FROM patients WHERE username=%s AND result='Benign'", (session["user"],))
    benign = cur.fetchone()["benign"]
 
    cur.execute("SELECT COUNT(*) AS malignant FROM patients WHERE username=%s AND result='Malignant'", (session["user"],))
    malignant = cur.fetchone()["malignant"]
 
    cur.close(); conn.close()
    stats = {"total": total, "benign": benign, "malignant": malignant}
    return render_template("dashboard.html", stats=stats)
 
 
# PREDICT
@app.route("/predict", methods=["GET", "POST"])
def predict():
    if "user" not in session:
        return redirect("/")
    if request.method == "POST":
        try:
            name = request.form["name"]
            age  = request.form["age"]
            file = request.files["image"]
            if file.filename == "":
                flash("Veuillez choisir une image", "warning")
                return redirect("/predict")
            path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(path)
            img = image.load_img(path, target_size=(224, 224))
            img = image.img_to_array(img) / 255.0
            img = np.expand_dims(img, axis=0)
            pred   = model.predict(img)[0][0]
            result = "Malignant" if pred > 0.5 else "Benign"
            conn = get_db()
            cur  = conn.cursor()
            cur.execute(
                "INSERT INTO patients (name, age, result, probability, image_path, username) VALUES (%s, %s, %s, %s, %s, %s)",
                (name, age, result, float(pred), path, session["user"])
            )
            conn.commit()
            cur.close(); conn.close()
            flash("Analyse réussie ✓", "success")
            return render_template("result.html", result=result,
                                   prob=round(pred * 100, 2), img=path)
        except Exception as e:
            flash(f"Erreur système : {e}", "danger")
            return redirect("/predict")
    return render_template("predict.html")
 
 
# PATIENTS
@app.route("/patients")
def patients():
    if "user" not in session:
        return redirect("/")
    conn = get_db()
    cur  = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM patients WHERE username=%s ORDER BY created_at DESC", (session["user"],))
    data = cur.fetchall()
    cur.close(); conn.close()
    return render_template("patients.html", patients=data)
 
 
# SUPPRIMER PATIENT
@app.route("/delete/<int:id>")
def delete(id):
    if "user" not in session:
        return redirect("/")
    conn = get_db()
    cur  = conn.cursor()
    cur.execute("DELETE FROM patients WHERE id=%s AND username=%s", (id, session["user"]))
    conn.commit()
    cur.close(); conn.close()
    flash("Patient supprimé ✓", "success")
    return redirect("/patients")
 
 
# LOGOUT
@app.route("/logout")
def logout():
    session.clear()
    flash("Déconnecté", "info")
    return redirect("/")
 
 
if __name__ == "__main__":
    app.run(debug=True)