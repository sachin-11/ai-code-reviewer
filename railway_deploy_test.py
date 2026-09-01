def get_user(user_id):
    query = "SELECT * FROM users WHERE id=" + user_id
    return query
