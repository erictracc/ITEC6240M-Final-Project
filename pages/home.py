from flask import render_template, request, redirect
from db.mongo import get_db
from services.moderation import classify_text
from utils.logger import setup_logger
from datetime import datetime
from bson.objectid import ObjectId

logger = setup_logger()

def home():
    db = get_db()
    posts_collection = db["posts"]

    # -------- CREATE POST --------
    if request.method == "POST":
        content = request.form.get("content")

        result = classify_text(content)

        posts_collection.insert_one({
            "content": content,
            "label": result["label"],
            "confidence": result["confidence"],
            "timestamp": datetime.now().strftime("%H:%M")
        })

        return redirect("/")

    # -------- PAGINATION --------
    page = int(request.args.get("page", 1))
    limit = 20
    skip = (page - 1) * limit

    total_posts = posts_collection.count_documents({})

    posts = list(
        posts_collection
        .find()
        .sort("_id", -1)
        .skip(skip)
        .limit(limit)
    )

    logger.info(f"Loaded page {page} | Showing {len(posts)} posts")

    return render_template(
        "home.html",
        posts=posts,
        total=total_posts,
        page=page,
        has_next=(skip + limit < total_posts)
    )


def delete_post(post_id):
    db = get_db()
    db["posts"].delete_one({"_id": ObjectId(post_id)})
    return redirect("/") 


def delete_all_posts():
    db = get_db()
    result = db["posts"].delete_many({})

    logger.info(f"🔥 Deleted {result.deleted_count} posts")

    return redirect("/")