def get_user(user_id):
    query = "SELECT * FROM users WHERE id=%s"
    return query, (user_id,)
