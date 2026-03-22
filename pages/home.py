from cProfile import label
from unittest import result

from flask import render_template, request, redirect
from requests import post
from db.mongo import get_db
from services.moderation import classify_text
from utils.logger import setup_logger
from datetime import datetime
from bson.objectid import ObjectId
import pandas as pd

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
            "true_label": None,
            "source": "user",
            "llama_label": "not_evaluated",
            "phi_label": "not_evaluated",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M")
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

def upload_csv(file):
    db = get_db()
    posts_collection = db["posts"]

    df = pd.read_csv(file)

    inserted = 0

    for _, row in df.iterrows():
        content = row.get("tweet_cleaned") or row.get("tweet")

        if not content:
            continue

        posts_collection.insert_one({
            "content": content,
            "true_label": row.get("class_label", "unknown"),
            "llama_label": "not_evaluated",
            "phi_label": "not_evaluated",
            "source": "dataset",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M")
        })

        inserted += 1

    logger.info(f"📦 Inserted {inserted} posts from CSV")

    return redirect("/")

def reevaluate_post(post_id):
    db = get_db()
    posts_collection = db["posts"]

    post = posts_collection.find_one({"_id": ObjectId(post_id)})

    if not post:
        return redirect("/")

    result = classify_text(post["content"])

    posts_collection.update_one(
        {"_id": ObjectId(post_id)},
        {
            "$set": {
                "llama_label": result["llama"],
                "phi_label": result["phi"]
            }
        }
    )

    logger.info(f"🔄 Re-evaluated post {post_id}")

    return redirect("/")

def evaluate_batch_posts(batch_size):
    db = get_db()
    posts = db["posts"]

    unevaluated = list(
        posts.find({"llama_label": "not_evaluated"}).limit(batch_size)
    )

    if not unevaluated:
        logger.info("No more posts to evaluate")
        return redirect("/analysis")

    processed = 0

    for post in unevaluated:
        result = classify_text(post["content"])

        posts.update_one(
            {"_id": post["_id"]},
            {
                "$set": {
                    "llama_label": result["llama"],
                    "phi_label": result["phi"]
                }
            }
        )

        processed += 1

    logger.info(f"Processed {processed} posts (batch size {batch_size})")

    return redirect("/analysis")

def normalize(label):
    if not label:
        return "unknown"

    label = str(label).lower().strip()

    if label in ["hate speech", "hate_speech"]:
        return "hate_speech"

    if label in ["offensive language", "offensive_language"]:
        return "offensive"

    if label in ["neither", "not"]:
        return "not"

    return label

def update_label(post_id):
    db = get_db()
    posts = db["posts"]

    new_label = request.form.get("label")

    if not new_label:
        return redirect("/")

    posts.update_one(
        {"_id": ObjectId(post_id)},
        {"$set": {"true_label": new_label}}
    )

    logger.info(f"Updated label for {post_id} → {new_label}")

    return redirect("/")

def compute_metrics():
    db = get_db()
    posts_collection = db["posts"]

    posts = list(posts_collection.find({
        "source": "dataset",              # 🔥 ONLY dataset
        "true_label": {"$ne": None},      # 🔥 must have ground truth
        "llama_label": {"$ne": "not_evaluated"}
    }))

    total = len(posts)

    if total == 0:
        return {
            "total": 0,
            "llama_acc": 0,
            "phi_acc": 0,
            "llama_matrix": {},
            "phi_matrix": {}
        }
    

    # 🔥 Define classes
    labels = ["hate_speech", "offensive", "not"]

    # 🔥 Initialize 3x3 matrices
    llama_matrix = {true: {pred: 0 for pred in labels} for true in labels}
    phi_matrix = {true: {pred: 0 for pred in labels} for true in labels}

    llama_correct = 0
    phi_correct = 0

    for post in posts:
        true = normalize(post.get("true_label"))
        llama = normalize(post.get("llama_label"))
        phi = normalize(post.get("phi_label"))

        # Skip bad labels
        if true not in labels:
            continue
        if llama not in labels:
            llama = "not"
        if phi not in labels:
            phi = "not"

        # ✅ Accuracy
        if llama == true:
            llama_correct += 1
        if phi == true:
            phi_correct += 1

        # ✅ Confusion matrix (multiclass)
        llama_matrix[true][llama] += 1
        phi_matrix[true][phi] += 1

    return {
        "total": total,
        "llama_acc": round(llama_correct / total, 3),
        "phi_acc": round(phi_correct / total, 3),
        "llama_matrix": llama_matrix,
        "phi_matrix": phi_matrix
    }