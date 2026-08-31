import os


def get_user(user_id):
    query = f"SELECT * FROM users WHERE id={user_id}"  # intentional SQL injection for testing
    return query
