from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash, session
import os
import re
import shutil

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev_secret_key')

# Répertoires
PDF_DIR = os.path.join(app.static_folder, "pdf")
PENDING_DIR = os.path.join(os.getcwd(), "uploads_pending")

# Création des dossiers au démarrage
os.makedirs(PDF_DIR, exist_ok=True)
os.makedirs(PENDING_DIR, exist_ok=True)

# Tri naturel
def trier_naturellement(nom):
    return [int(s) if s.isdigit() else s.lower() for s in re.split(r'(\d+)', nom)]

# Tri par date
def trier_par_date(fichiers, base_dir):
    return sorted(fichiers, key=lambda f: os.path.getmtime(os.path.join(base_dir, f)), reverse=True)

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
            if mdp == os.environ.get("MODERATION_PASSWORD", "sardaukar"):
                session["moderateur"] = True
                return redirect(url_for("moderation"))
            else:
                flash("Mot de passe incorrect.")
        return render_template("login.html")

    # Fichiers en attente
    fichiers_pending = []
    for root, _, files in os.walk(PENDING_DIR):
        for f in files:
            if f.endswith(".pdf"):
                chemin_relatif = os.path.relpath(os.path.join(root, f), PENDING_DIR)
                fichiers_pending.append(chemin_relatif)

    fichiers_pending.sort(key=lambda x: os.path.getmtime(os.path.join(PENDING_DIR, x)), reverse=True)

    # Fichiers validés
    fichiers_valides = []
    for root, _, files in os.walk(PDF_DIR):
        for f in files:
            if f.endswith(".pdf"):
                chemin_relatif = os.path.relpath(os.path.join(root, f), PDF_DIR)
                fichiers_valides.append(chemin_relatif)

    fichiers_valides.sort(key=lambda x: os.path.getmtime(os.path.join(PDF_DIR, x)), reverse=True)

    # Tous les dossiers existants pour menu déroulant
    dossiers_existants = set()
    for root, dirs, _ in os.walk(PENDING_DIR):
        for d in dirs:
            rel = os.path.relpath(os.path.join(root, d), PENDING_DIR)
            dossiers_existants.add(rel)

    return render_template("moderation.html", fichiers_pending=fichiers_pending, fichiers_valides=fichiers_valides, dossiers=dossiers_existants)

@app.route("/valider/<path:filename>")
def valider(filename):
    if not session.get("moderateur"):
        return redirect(url_for("moderation"))

    src = os.path.join(PENDING_DIR, filename)
    dst = os.path.join(PDF_DIR, filename)
    os.makedirs(os.path.dirname(dst), exist_ok=True)

    try:
        shutil.move(src, dst)
        flash(f"Fichier {filename} validé.")
    except Exception as e:
        flash(f"Erreur lors du déplacement : {e}")

    return redirect(url_for("moderation"))

@app.route("/supprimer/<path:filename>")
def supprimer(filename):
    if not session.get("moderateur"):
        return redirect(url_for("moderation"))

    chemin = os.path.join(PENDING_DIR, filename)
    if os.path.exists(chemin):
        os.remove(chemin)
        flash(f"Fichier {filename} supprimé.")
    else:
        flash("Fichier introuvable.")
    return redirect(url_for("moderation"))

@app.route("/modifier_fichier", methods=["POST"])
def modifier_fichier():
    if not session.get("moderateur"):
        return redirect(url_for("moderation"))

    old_filename = request.form.get("old_filename")
    new_name = request.form.get("new_name", "").strip()
    new_folder = request.form.get("new_folder", "").strip()
    new_folder_custom = request.form.get("new_folder_custom", "").strip()
    valid_file = request.form.get("valid_file") == "1"

    base_dir = PDF_DIR if valid_file else PENDING_DIR

    if not old_filename or not new_name:
        flash("Nom de fichier invalide.")
        return redirect(url_for("moderation"))

    # Dossier final prioritaire : personnalisé > sélection
    final_folder = new_folder_custom if new_folder_custom else new_folder

    # Sécurité sur le nom
    if not re.match(r'^[\w\-\s]+$', new_name):
        flash("Le nom contient des caractères invalides.")
        return redirect(url_for("moderation"))

    src = os.path.join(base_dir, old_filename)
    new_rel_path = os.path.join(final_folder, new_name + ".pdf") if final_folder else new_name + ".pdf"
    dst = os.path.join(base_dir, new_rel_path)

    if os.path.exists(dst):
        flash("Un fichier avec ce nom existe déjà.")
        return redirect(url_for("moderation"))

    os.makedirs(os.path.dirname(dst), exist_ok=True)

    try:
        shutil.move(src, dst)
        flash(f"Fichier modifié : {old_filename} → {new_rel_path}")
    except Exception as e:
        flash(f"Erreur lors du renommage : {e}")

    return redirect(url_for("moderation"))

@app.route("/logout")
def logout():
    session.pop("moderateur", None)
    flash("Déconnecté.")
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(debug=True)