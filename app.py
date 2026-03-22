from flask import Flask, render_template, request, redirect, Response
from functools import wraps

from db.mongo import get_db
from utils.logger import setup_logger
from pages.home import compute_metrics

# Import ALL handlers from home.py
from pages.home import (
    home,
    delete_post,
    delete_all_posts,
    upload_csv,
    reevaluate_post,
    evaluate_batch_posts,
    update_label
)

# -------- AUTH (MUST BE ABOVE ROUTES) --------
USERNAME = "admin"
PASSWORD = "adminadmin"

def check_auth(username, password):
    return username == USERNAME and password == PASSWORD

def authenticate():
    return Response(
        "Login Required",
        401,
        {"WWW-Authenticate": 'Basic realm="Login Required"'}
    )

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        print("AUTH CHECK RUNNING")  # DEBUG

        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            print("AUTH FAILED")
            return authenticate()

        print("AUTH PASSED")
        return f(*args, **kwargs)
    return decorated

# -------- APP INIT --------
logger = setup_logger()

app = Flask(__name__, template_folder="pages/templates")

# Initialize DB
db = get_db()

# -------- ROUTES --------

# HOME
@app.route("/", methods=["GET", "POST"])
@requires_auth
def index():
    logger.info("GET / - Home page accessed")
    return home()

# DELETE SINGLE
@app.route("/delete/<post_id>")
@requires_auth
def delete(post_id):
    logger.info(f"DELETE post {post_id}")
    return delete_post(post_id)

# SETTINGS
@app.route("/settings")
@requires_auth
def settings():
    logger.info("GET /settings")
    return render_template("settings.html")

# DELETE ALL
@app.route("/delete_all", methods=["POST"])
@requires_auth
def delete_all():
    logger.info("POST /delete_all")
    return delete_all_posts()

# CSV UPLOAD
@app.route("/upload_csv", methods=["POST"])
@requires_auth
def upload():
    logger.info("POST /upload_csv")

    file = request.files.get("file")

    if not file:
        logger.warning("No file uploaded")
        return redirect("/settings")

    return upload_csv(file)

# RE-EVALUATE
@app.route("/reevaluate/<post_id>")
@requires_auth
def reevaluate(post_id):
    logger.info(f"Re-evaluating post {post_id}")
    return reevaluate_post(post_id)

# BATCH EVALUATE
@app.route("/evaluate_batch")
@requires_auth
def evaluate_batch():
    size = int(request.args.get("size", 10))
    return evaluate_batch_posts(size)

# ANALYSIS
@app.route("/analysis")
@requires_auth
def analysis():
    logger.info("GET /analysis - Analysis page accessed")

    stats = compute_metrics()

    return render_template("analysis.html", stats=stats)

@app.route("/set_label/<post_id>", methods=["POST"])
@requires_auth
def set_label(post_id):
    return update_label(post_id)

# -------- RUN --------
if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True,
        use_reloader=True
    )