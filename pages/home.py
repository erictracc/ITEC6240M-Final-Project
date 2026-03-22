from flask import render_template, request, redirect
from db.mongo import get_db
from services.moderation import classify_text
from utils.logger import setup_logger
from datetime import datetime
from bson.objectid import ObjectId
import pandas as pd

logger = setup_logger()


# =========================
# HOME
# =========================
def home():
    db = get_db()
    posts_collection = db["posts"]

    # -------- CREATE POST --------
    if request.method == "POST":
        content = request.form.get("content")

        posts_collection.insert_one({
            "content": content,
            "true_label": None,
            "source": "user",
            "model_results": None,
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


# =========================
# DELETE SINGLE POST
# =========================
def delete_post(post_id):
    db = get_db()
    db["posts"].delete_one({"_id": ObjectId(post_id)})
    logger.info(f"Deleted post {post_id}")
    return redirect("/")


# =========================
# DELETE ALL POSTS
# =========================
def delete_all_posts():
    db = get_db()
    result = db["posts"].delete_many({})
    logger.info(f"🔥 Deleted {result.deleted_count} posts")
    return redirect("/")


# =========================
# CSV UPLOAD
# =========================
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
            "model_results": None,
            "source": "dataset",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M")
        })

        inserted += 1

    logger.info(f"📦 Inserted {inserted} posts from CSV")

    return redirect("/")


# =========================
# SINGLE RE-EVALUATE
# =========================
def reevaluate_post(post_id):
    db = get_db()
    posts_collection = db["posts"]

    post = posts_collection.find_one({"_id": ObjectId(post_id)})

    if not post:
        logger.warning("Post not found")
        return redirect("/")

    if not post.get("true_label"):
        logger.warning("Skipping evaluation - no ground truth")
        return redirect("/")

    result = classify_text(post["content"])

    posts_collection.update_one(
        {"_id": ObjectId(post_id)},
        {"$set": {"model_results": result}}
    )

    logger.info(f"🔄 Re-evaluated post {post_id}")

    return redirect("/")


# =========================
# BATCH EVALUATE
# =========================
def evaluate_batch_posts(batch_size):
    db = get_db()
    posts = db["posts"]

    # Only evaluate posts that:
    # - have label
    # - not evaluated yet
    unevaluated = list(
        posts.find({
            "$and": [
                {"true_label": {"$ne": None}},
                {
                    "$or": [
                        {"model_results": None},
                        {"model_results": {"$exists": False}}
                    ]
                }
            ]
        }).limit(batch_size)
    )

    if not unevaluated:
        logger.info("No more posts to evaluate")
        return redirect("/analysis")

    processed = 0

    for post in unevaluated:
        result = classify_text(post["content"])

        posts.update_one(
            {"_id": post["_id"]},
            {"$set": {"model_results": result}}
        )

        processed += 1

    logger.info(f"Processed {processed} posts (batch size {batch_size})")

    return redirect("/analysis")


# =========================
# NORMALIZE LABELS
# =========================
def normalize(label):
    if not label:
        return "unknown"

    label = str(label).lower().strip()

    if "hate" in label:
        return "hate speech"

    if "offensive" in label:
        return "offensive language"

    if "neither" in label or "not" in label:
        return "neither"

    return "unknown"


# =========================
# UPDATE LABEL
# =========================
def update_label(post_id):
    db = get_db()
    posts = db["posts"]

    new_label = request.form.get("label")

    if not new_label:
        logger.warning("No label provided")
        return redirect("/")

    posts.update_one(
        {"_id": ObjectId(post_id)},
        {"$set": {"true_label": new_label}}
    )

    logger.info(f"Updated label for {post_id} = {new_label}")

    return redirect("/")


# =========================
# METRICS
# =========================
def compute_metrics():
    db = get_db()
    posts_collection = db["posts"]

    # Get all evaluated posts (dataset + user)
    posts = list(posts_collection.find({
        "true_label": {"$ne": None},
        "model_results": {"$ne": None}
    }))

    labels = ["hate speech", "offensive language", "neither"]

    total_posts = len(posts)

    if total_posts == 0:
        return {
            "total": 0,
            "models": [],
            "accuracy": {},
            "matrices": {}
        }

    # Get model names dynamically
    sample = next(
        (p["model_results"] for p in posts if p.get("model_results")),
        None
    )

    if not sample:
        return {
            "total": 0,
            "models": [],
            "accuracy": {},
            "matrices": {}
        }

    models = [m.replace(":latest", "") for m in sample.keys()]

    # Initialize structures
    matrices = {}
    correct_counts = {}
    model_totals = {}

    for model in models:
        matrices[model] = {
            true: {pred: 0 for pred in labels}
            for true in labels
        }
        correct_counts[model] = 0
        model_totals[model] = 0

    # Compute metrics
    for post in posts:
        true = normalize(post.get("true_label"))
        results = post.get("model_results")

        if not results or true not in labels:
            continue

        for raw_model, result in results.items():
            model = raw_model.replace(":latest", "")

            pred = normalize(result.get("label"))

            if pred not in labels:
                pred = "neither"

            model_totals[model] += 1

            if pred == true:
                correct_counts[model] += 1

            matrices[model][true][pred] += 1

    # Accuracy per model
    accuracy = {}
    for model in models:
        if model_totals[model] > 0:
            accuracy[model] = round(
                correct_counts[model] / model_totals[model],
                3
            )
        else:
            accuracy[model] = 0

    return {
        "total": total_posts,
        "models": models,
        "accuracy": accuracy,
        "matrices": matrices
    }