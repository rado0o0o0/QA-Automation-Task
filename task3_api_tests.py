"""
Task 3 - API Tests against JSONPlaceholder
===========================================
Senior Manual QA perspective | Python + requests (no Java/Rest Assured)
Target: https://jsonplaceholder.typicode.com/

Scenarios covered:
  1. Posts per user - happy path    : GET /posts?userId=<id> returns exactly 10 posts
                                      Data-driven: user IDs 1, 5, 10
  2. Posts per user - negative case : GET /posts?userId=999 → HTTP 200, empty array
  3. Unique post IDs                : GET /posts → every post has a unique id
  4. Schema sanity                  : GET /posts/1 → id, userId (int), title, body (non-empty str)
  5. Create a post                  : POST /posts → HTTP 201, echoed payload, id present

Design notes (Sr QA perspective):
  - Base URL in one place (BASE_URL constant) — never scattered across tests
  - Every assertion has a clear failure message so you know what broke without
    reading the test body
  - No time-based or order-dependent assertions — all tests are independent
  - A lightweight ApiClient wraps requests so HTTP details stay out of tests
  - Results are printed in a structured pass/fail format; final exit code is
    non-zero if any test failed (CI-friendly)
"""

import sys
import json
import requests
from typing import Any

# ---------------------------------------------------------------------------
# Config — one place to change the base URL
# ---------------------------------------------------------------------------

BASE_URL = "https://jsonplaceholder.typicode.com"
TIMEOUT  = 10   # seconds per request — never hang indefinitely


# ---------------------------------------------------------------------------
# Lightweight API Client  (keeps HTTP plumbing out of test functions)
# ---------------------------------------------------------------------------

class ApiClient:
    """Thin wrapper around requests. Raises on network errors, not on HTTP status."""

    def __init__(self, base_url: str, timeout: int = TIMEOUT):
        self.base_url = base_url.rstrip("/")
        self.timeout  = timeout
        self.session  = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

    def get(self, path: str, params: dict = None) -> requests.Response:
        url = f"{self.base_url}{path}"
        return self.session.get(url, params=params, timeout=self.timeout)

    def post(self, path: str, body: dict) -> requests.Response:
        url = f"{self.base_url}{path}"
        return self.session.post(url, data=json.dumps(body), timeout=self.timeout)


# ---------------------------------------------------------------------------
# Test runner helpers
# ---------------------------------------------------------------------------

_results: list[dict] = []

def _record(name: str, passed: bool, message: str = ""):
    status = "PASS" if passed else "FAIL"
    _results.append({"name": name, "status": status, "message": message})
    suffix = f" → {message}" if message else ""
    print(f"  [{status}] {name}{suffix}")

def _assert(condition: bool, failure_msg: str, test_name: str):
    """Single assertion helper — records result and raises on failure."""
    if not condition:
        _record(test_name, passed=False, message=failure_msg)
        raise AssertionError(failure_msg)

def _run(test_fn, *args):
    """Runs a test function, catches exceptions, records outcome."""
    # Build a display name: function name + args if any
    arg_str   = ", ".join(str(a) for a in args) if args else ""
    test_name = f"{test_fn.__name__}({arg_str})" if arg_str else test_fn.__name__
    try:
        test_fn(*args)
        _record(test_name, passed=True)
    except AssertionError:
        pass                          # already recorded inside _assert
    except Exception as e:
        _record(test_name, passed=False, message=f"Unexpected error: {type(e).__name__}: {e}")


# ---------------------------------------------------------------------------
# Test functions
# ---------------------------------------------------------------------------

client = ApiClient(BASE_URL)


# -- Scenario 1: Posts per user — happy path (data-driven: users 1, 5, 10) --

def test_posts_per_user_happy_path(user_id: int):
    """GET /posts?userId=<id> must return exactly 10 posts for a valid user."""
    test_name = f"test_posts_per_user_happy_path(userId={user_id})"

    response = client.get("/posts", params={"userId": user_id})

    _assert(
        response.status_code == 200,
        f"Expected HTTP 200 for userId={user_id}, got {response.status_code}",
        test_name
    )

    posts = response.json()

    _assert(
        isinstance(posts, list),
        f"Response body for userId={user_id} should be a list, got {type(posts).__name__}",
        test_name
    )

    _assert(
        len(posts) == 10,
        f"Expected exactly 10 posts for userId={user_id}, got {len(posts)}",
        test_name
    )

    # Every returned post should actually belong to the requested user
    wrong_owner = [p for p in posts if p.get("userId") != user_id]
    _assert(
        len(wrong_owner) == 0,
        f"Posts with wrong userId found for userId={user_id}: {wrong_owner}",
        test_name
    )

    _record(test_name, passed=True)


# -- Scenario 2: Posts per user — negative case (userId=999) --

def test_posts_per_user_negative_case():
    """GET /posts?userId=999 must return HTTP 200 with an empty array."""
    test_name = "test_posts_per_user_negative_case(userId=999)"

    response = client.get("/posts", params={"userId": 999})

    _assert(
        response.status_code == 200,
        f"Expected HTTP 200 for non-existent userId=999, got {response.status_code}",
        test_name
    )

    posts = response.json()

    _assert(
        isinstance(posts, list),
        f"Expected a list for userId=999, got {type(posts).__name__}",
        test_name
    )

    _assert(
        len(posts) == 0,
        f"Expected empty array for userId=999, got {len(posts)} posts",
        test_name
    )

    _record(test_name, passed=True)


# -- Scenario 3: Unique post IDs across all posts --

def test_all_post_ids_are_unique():
    """GET /posts — every post in the response must have a unique id."""
    test_name = "test_all_post_ids_are_unique"

    response = client.get("/posts")

    _assert(
        response.status_code == 200,
        f"Expected HTTP 200 for GET /posts, got {response.status_code}",
        test_name
    )

    posts = response.json()

    _assert(
        isinstance(posts, list) and len(posts) > 0,
        "GET /posts returned an empty or non-list response — cannot check uniqueness",
        test_name
    )

    all_ids      = [p.get("id") for p in posts]
    unique_ids   = set(all_ids)
    duplicate_ids = [pid for pid in unique_ids if all_ids.count(pid) > 1]

    _assert(
        len(duplicate_ids) == 0,
        f"Duplicate post IDs found: {duplicate_ids}",
        test_name
    )

    _record(test_name, passed=True)


# -- Scenario 4: Schema sanity on /posts/1 --

def test_post_schema_sanity():
    """
    GET /posts/1 — response must contain:
      - id    : non-null integer
      - userId: non-null integer
      - title : non-null, non-empty string
      - body  : non-null, non-empty string
    """
    test_name = "test_post_schema_sanity(postId=1)"

    response = client.get("/posts/1")

    _assert(
        response.status_code == 200,
        f"Expected HTTP 200 for GET /posts/1, got {response.status_code}",
        test_name
    )

    post = response.json()

    # --- id ---
    _assert(
        "id" in post and post["id"] is not None,
        "Field 'id' is missing or null in /posts/1 response",
        test_name
    )
    _assert(
        isinstance(post["id"], int),
        f"Field 'id' must be an integer, got {type(post['id']).__name__} (value: {post['id']})",
        test_name
    )

    # --- userId ---
    _assert(
        "userId" in post and post["userId"] is not None,
        "Field 'userId' is missing or null in /posts/1 response",
        test_name
    )
    _assert(
        isinstance(post["userId"], int),
        f"Field 'userId' must be an integer, got {type(post['userId']).__name__} (value: {post['userId']})",
        test_name
    )

    # --- title ---
    _assert(
        "title" in post and post["title"] is not None,
        "Field 'title' is missing or null in /posts/1 response",
        test_name
    )
    _assert(
        isinstance(post["title"], str) and len(post["title"].strip()) > 0,
        f"Field 'title' must be a non-empty string, got: '{post.get('title')}'",
        test_name
    )

    # --- body ---
    _assert(
        "body" in post and post["body"] is not None,
        "Field 'body' is missing or null in /posts/1 response",
        test_name
    )
    _assert(
        isinstance(post["body"], str) and len(post["body"].strip()) > 0,
        f"Field 'body' must be a non-empty string, got: '{post.get('body')}'",
        test_name
    )

    _record(test_name, passed=True)


# -- Scenario 5: Create a post --

def test_create_post():
    """
    POST /posts with a valid JSON body must:
      - Return HTTP 201
      - Echo back the sent payload fields (title, body, userId)
      - Include a non-null id in the response
    """
    test_name = "test_create_post"

    payload = {
        "title":  "Test Post Title",
        "body":   "This is the test post body.",
        "userId": 1
    }

    response = client.post("/posts", body=payload)

    _assert(
        response.status_code == 201,
        f"Expected HTTP 201 for POST /posts, got {response.status_code}",
        test_name
    )

    created = response.json()

    # id must be present and non-null
    _assert(
        "id" in created and created["id"] is not None,
        "Response for POST /posts is missing a non-null 'id' field",
        test_name
    )

    # Echoed fields must match what was sent
    for field in ("title", "body", "userId"):
        _assert(
            field in created,
            f"Field '{field}' is missing from the POST /posts response",
            test_name
        )
        _assert(
            created[field] == payload[field],
            (f"Field '{field}' mismatch: sent '{payload[field]}', "
             f"received '{created.get(field)}'"),
            test_name
        )

    _record(test_name, passed=True)


# ---------------------------------------------------------------------------
# Entry point — runs all scenarios, prints summary, exits non-zero on failure
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("Task 3 — API Tests | JSONPlaceholder")
    print(f"Base URL : {BASE_URL}")
    print("=" * 60)

    # Scenario 1: data-driven — run for each user ID
    print("\n[Scenario 1] Posts per user — happy path")
    for user_id in (1, 5, 10):
        _run(test_posts_per_user_happy_path, user_id)

    # Scenario 2: negative case
    print("\n[Scenario 2] Posts per user — negative case")
    _run(test_posts_per_user_negative_case)

    # Scenario 3: unique IDs
    print("\n[Scenario 3] Unique post IDs")
    _run(test_all_post_ids_are_unique)

    # Scenario 4: schema sanity
    print("\n[Scenario 4] Schema sanity")
    _run(test_post_schema_sanity)

    # Scenario 5: create a post
    print("\n[Scenario 5] Create a post")
    _run(test_create_post)

    # Summary
    total  = len(_results)
    passed = sum(1 for r in _results if r["status"] == "PASS")
    failed = total - passed

    print("\n" + "=" * 60)
    print(f"Results: {passed}/{total} passed  |  {failed} failed")
    print("=" * 60)

    if failed:
        print("\nFailed tests:")
        for r in _results:
            if r["status"] == "FAIL":
                print(f"  ✗ {r['name']}")
                print(f"    Reason: {r['message']}")
        sys.exit(1)   # non-zero exit for CI pipelines
    else:
        print("\nAll tests passed.")
        sys.exit(0)


if __name__ == "__main__":
    main()
