"""Synthetic test cases with known expected findings, used by the offline
eval to score the agent's actual issues against what a reviewer should
have caught -- and, for the clean cases, should NOT have invented."""

GOLDEN_CASES = [
    {
        "name": "sql_injection_fstring",
        "file": "db.py",
        "content": (
            "def get_user(conn, user_id):\n"
            '    query = f"SELECT * FROM users WHERE id={user_id}"\n'
            "    return conn.execute(query).fetchone()\n"
        ),
        "expected_issues": [
            {
                "category": "security",
                "description": "SQL injection: user_id is interpolated directly into the query string "
                "instead of using a parameterized query.",
            },
        ],
    },
    {
        "name": "hardcoded_secret",
        "file": "config.py",
        "content": (
            "import requests\n\n"
            'API_KEY = "sk-live-51Hd8x9J2eZvKYlo2C000000000000"\n\n'
            "def call_api():\n"
            '    return requests.get("https://api.example.com/data", headers={"Authorization": API_KEY})\n'
        ),
        "expected_issues": [
            {
                "category": "security",
                "description": "A live-looking API key is hardcoded directly in source instead of "
                "being read from an environment variable or secret store.",
            },
        ],
    },
    {
        "name": "off_by_one_loop",
        "file": "utils.py",
        "content": (
            "def get_last_n(items, n):\n"
            "    result = []\n"
            "    for i in range(1, n + 1):\n"
            "        result.append(items[len(items) - i])\n"
            "    return result\n"
        ),
        "expected_issues": [
            {
                "category": "bug",
                "description": "range(1, n + 1) combined with items[len(items) - i] skips the very "
                "last element (index len(items)-1 is never reached) and will raise an "
                "IndexError once i reaches len(items).",
            },
        ],
    },
    {
        "name": "n_plus_one_query",
        "file": "orders.py",
        "content": (
            "def get_order_totals(conn, order_ids):\n"
            "    totals = []\n"
            "    for order_id in order_ids:\n"
            "        row = conn.execute(\n"
            '            "SELECT SUM(price) FROM order_items WHERE order_id = ?", (order_id,)\n'
            "        ).fetchone()\n"
            "        totals.append(row[0])\n"
            "    return totals\n"
        ),
        "expected_issues": [
            {
                "category": "performance",
                "description": "N+1 query: issues one database query per order_id in a loop instead "
                "of a single batched query (e.g. GROUP BY order_id with an IN clause).",
            },
        ],
    },
    {
        "name": "xss_unescaped_render",
        "file": "views.py",
        "content": (
            "from flask import request\n\n"
            "def profile_page():\n"
            '    name = request.args.get("name", "")\n'
            '    return f"<h1>Welcome, {name}</h1>"\n'
        ),
        "expected_issues": [
            {
                "category": "security",
                "description": "Reflected XSS: the 'name' query parameter is interpolated directly "
                "into HTML output with no escaping, so a script tag in the URL executes in "
                "the victim's browser.",
            },
        ],
    },
    {
        "name": "missing_auth_check",
        "file": "admin.py",
        "content": (
            "from flask import Blueprint, jsonify\n\n"
            'admin_bp = Blueprint("admin", __name__)\n\n'
            '@admin_bp.route("/admin/users/<int:user_id>/delete", methods=["POST"])\n'
            "def delete_user(user_id):\n"
            "    db.session.query(User).filter_by(id=user_id).delete()\n"
            "    db.session.commit()\n"
            '    return jsonify({"status": "deleted"})\n'
        ),
        "expected_issues": [
            {
                "category": "security",
                "description": "The admin user-deletion endpoint has no authentication or "
                "authorization check, so any caller can delete arbitrary users.",
            },
        ],
    },
    {
        "name": "clean_parameterized_query",
        "file": "db_safe.py",
        "content": (
            "def get_user(conn, user_id: int):\n"
            '    query = "SELECT * FROM users WHERE id = ?"\n'
            "    return conn.execute(query, (user_id,)).fetchone()\n"
        ),
        "expected_issues": [],
    },
    {
        "name": "clean_simple_utility",
        "file": "math_utils.py",
        "content": (
            "def clamp(value: float, low: float, high: float) -> float:\n"
            "    if value < low:\n"
            "        return low\n"
            "    if value > high:\n"
            "        return high\n"
            "    return value\n"
        ),
        "expected_issues": [],
    },
]
