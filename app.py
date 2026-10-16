import os
import json
from decimal import Decimal

import boto3
from botocore.config import Config
from flask import Flask, jsonify, request, send_from_directory

REGION = os.environ.get("AWS_REGION", "us-east-1")
dynamodb = boto3.resource(
    "dynamodb",
    region_name=REGION,
    config=Config(retries={"max_attempts": 10, "mode": "standard"}),
)
TABLES = {
    "candidates": dynamodb.Table(os.environ.get("CANDIDATES_TABLE", "Candidates")),
    "jobs": dynamodb.Table(os.environ.get("JOBS_TABLE", "Jobs")),
    "interviews": dynamodb.Table(os.environ.get("INTERVIEWS_TABLE", "Interviews")),
}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_FILES = {"index.html", "style.css", "script.js", "1.png"}

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 1_000_000


def to_json(v):
    if isinstance(v, Decimal):
        return int(v) if v == v.to_integral_value() else float(v)
    if isinstance(v, list):
        return [to_json(i) for i in v]
    if isinstance(v, dict):
        return {k: to_json(x) for k, x in v.items()}
    return v


def scan_all(table):
    resp = table.scan()
    items = resp["Items"]
    while "LastEvaluatedKey" in resp:
        resp = table.scan(ExclusiveStartKey=resp["LastEvaluatedKey"])
        items += resp["Items"]
    return items


def sort_key(item):
    i = item["id"]
    return (0, i, "") if isinstance(i, int) else (1, 0, str(i))


def sync_table(table, items):
    new = {}
    for it in items:
        if not isinstance(it, dict) or it.get("id") is None:
            continue
        it = dict(it)
        if isinstance(it["id"], int) and not isinstance(it["id"], bool):
            it["_n"] = True
        it["id"] = str(it["id"])
        new[it["id"]] = it
    existing = {i["id"]: i for i in scan_all(table)}
    with table.batch_writer() as batch:
        for item_id, it in new.items():
            if existing.get(item_id) != it:
                batch.put_item(Item=it)
        for old_id in set(existing) - set(new):
            batch.delete_item(Key={"id": old_id})


@app.get("/health")
def health():
    return jsonify(status="ok")


@app.get("/api/data")
def get_data():
    out = {}
    for name, table in TABLES.items():
        items = []
        for it in scan_all(table):
            it = to_json(it)
            if it.pop("_n", False):
                it["id"] = int(it["id"])
            items.append(it)
        items.sort(key=sort_key)
        out[name] = items
    return jsonify(out)


@app.put("/api/data")
def put_data():
    try:
        payload = json.loads(request.get_data(as_text=True), parse_float=Decimal)
    except ValueError:
        return jsonify(error="invalid json"), 400
    if not isinstance(payload, dict):
        return jsonify(error="invalid payload"), 400
    for name, table in TABLES.items():
        items = payload.get(name)
        if isinstance(items, list):
            sync_table(table, items)
    return jsonify(status="saved")


@app.get("/")
def home():
    return send_from_directory(BASE_DIR, "index.html")


@app.get("/<path:name>")
def static_files(name):
    if name in STATIC_FILES:
        return send_from_directory(BASE_DIR, name)
    return jsonify(error="not found"), 404


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
