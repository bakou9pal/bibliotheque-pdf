from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash, session
import os
import re
import shutil
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'change_ceci_par_un_secret_vraiment_securise'

# Répertoires
PDF_DIR = os.path.join(app.static_folder, "pdf")
PENDING_DIR = os.path.join(os.getcwd(), "uploads_pending")

# Création des dossiers s'ils n'existent pas
os.makedirs(PDF_DIR, exist_ok=True)
os.makedirs(PENDING_DIR, exist_ok=True)

# Tri naturel
def trier_naturellement(nom):
    return [int(s) if s.isdigit() else s.lower() for s in re.split(r'(\d+)', nom)]

# Tri par date de modification
def trier_par_date(liste_fichiers, base_dir):
    return sorted(liste_fichiers, key=lambda f: os.path.getmtime(os.path.join(base_dir, f)), reverse=True)

@app.route("/")
def index():
    fichiers_par_dossier = {}

    for root, _, files in os.walk(PDF_DIR):
        rel_path = os.path.relpath(root, PDF_DIR)
        rel_path = "" if rel_path == "." else rel_path

        fichiers_pdf = [f for f in files if f.endswith(".pdf")]
        if fichiers_pdf:
            fichiers_pdf = trier_par_date(fichiers_pdf, root)
            fichiers_par_dossier[rel_path] = fichiers_pdf

    dossiers_tries = sorted(fichiers_par_dossier.keys(), key=trier_naturellement)

    return render_template("index.html", dossiers=dossiers_tries, fichiers_par_dossier=fichiers_par_dossier)

@app.route("/pdf/<path:filename>")
def pdf(filename):
    return send_from_directory(PDF_DIR, filename)

@app.route("/pending/<path:filename>")
def pending_file(filename):
    return send_from_directory(PENDING_DIR, filename)

@app.route("/upload", methods=["GET", "POST"])
def upload():
    if request.method == "POST":
        fichier = request.files.get("file")
        dossier = request.form.get("folder", "").strip()

        if fichier and fichier.filename.endswith(".pdf"):
            dossier_path = os.path.join(PENDING_DIR, dossier) if dossier else PENDING_DIR
            os.makedirs(dossier_path, exist_ok=True)

            chemin_fichier = os.path.join(dossier_path, fichier.filename)
            fichier.save(chemin_fichier)
            flash("Fichier uploadé, en attente de validation.")
            return redirect(url_for("upload"))
        else:
            flash("Merci d’uploader un fichier PDF valide.")
            return redirect(url_for("upload"))

    return render_template("upload.html")

@app.route("/moderation", methods=["GET", "POST"])
def moderation():
    if not session.get("moderateur"):
        if request.method == "POST":
            mdp = request.form.get("password")
            if mdp == "sardaukar":  # 🔐 À personnaliser
                session["moderateur"] = True
                return redirect(url_for("moderation"))
            else:
                flash("Mot de passe incorrect.")
        return render_template("login.html")

    fichiers_en_attente = []
    for root, _, files in os.walk(PENDING_DIR):
        for f in files:
            if f.endswith(".pdf"):
                chemin_relatif = os.path.relpath(os.path.join(root, f), PENDING_DIR)
                fichiers_en_attente.append(chemin_relatif)

    fichiers_en_attente.sort(key=lambda x: os.path.getmtime(os.path.join(PENDING_DIR, x)), reverse=True)

    return render_template("moderation.html", fichiers=fichiers_en_attente)

@app.route("/valider/<path:filename>")
def valider(filename):
    if not session.get("moderateur"):
        return redirect(url_for("moderation"))

    src = os.path.join(PENDING_DIR, filename)
    dst = os.path.join(PDF_DIR, filename)
    os.makedirs(os.path.dirname(dst), exist_ok=True)

    shutil.move(src, dst)
    flash(f"Fichier {filename} validé.")
    return redirect(url_for("moderation"))

@app.route("/supprimer/<path:filename>")
def supprimer(filename):
    if not session.get("moderateur"):
        return redirect(url_for("moderation"))

    chemin = os.path.join(PENDING_DIR, filename)
    if os.path.exists(chemin):
        os.remove(chemin)
        flash(f"Fichier {filename} supprimé.")
    return redirect(url_for("moderation"))

@app.route("/logout")
def logout():
    session.pop("moderateur", None)
    flash("Déconnecté.")
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(debug=True)

