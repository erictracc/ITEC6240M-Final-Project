from flask import Flask
from pages.home import home
from db.mongo import get_db
from utils.logger import setup_logger
from pages.home import home, delete_post, delete_all_posts
from flask import render_template
import pandas as pd
from flask import request, redirect
from datetime import datetime

logger = setup_logger()

app = Flask(__name__, template_folder="pages/templates")

# Initialize DB
db = get_db()

@app.route("/", methods=["GET", "POST"])
def index():
    logger.info("GET / - Home page accessed")
    return home()

@app.route("/delete/<post_id>")
def delete(post_id):
    logger.info("GET /delete/<post_id> - Delete post accessed")
    return delete_post(post_id)

@app.route("/settings")
def settings():
    logger.info("GET /settings - Settings page accessed")
    return render_template("settings.html")

@app.route("/delete_all", methods=["POST"])
def delete_all():
    logger.info("POST /delete_all - Delete all posts accessed")
    return delete_all_posts()

@app.route("/upload_csv", methods=["POST"])
def upload_csv():
    logger.info("POST /upload_csv - CSV upload started")

    file = request.files.get("file")

    if not file:
        logger.warning("No file uploaded")
        return redirect("/settings")

    try:
        df = pd.read_csv(file)
        db = get_db()
        posts_collection = db["posts"]

        inserted_count = 0
        skipped_count = 0

        for _, row in df.iterrows():
            content = row.get("tweet_cleaned", "")

            if not content or str(content).strip() == "":
                skipped_count += 1
                continue

            post = {
                "content": content,
                "label": row.get("class_label", "unknown"),
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M")
            }

            posts_collection.insert_one(post)
            inserted_count += 1

        logger.info(f"Inserted: {inserted_count}, Skipped: {skipped_count}")

        # 👇 PASS RESULT TO SETTINGS PAGE
        return redirect(f"/settings?inserted={inserted_count}&skipped={skipped_count}")

    except Exception as e:
        logger.error(f"CSV upload failed: {str(e)}")
        return redirect("/settings?error=1")

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True,
        use_reloader=False  # prevents duplicate logs / weird thread error
    )