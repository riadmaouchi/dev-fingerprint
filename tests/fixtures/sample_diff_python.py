"""Sample Python diff content for tests — simulates a post-LLM style commit."""

HUMAN_STYLE_PATCH = """\
+def calc(x, y):
+    return x + y
+
+def proc(lst):
+    res = []
+    for i in lst:
+        if i > 0:
+            res.append(i * 2)
+    return res
+
+# TODO: fix edge case
+def get_user(id):
+    try:
+        return db.find(id)
+    except:
+        return None
"""

LLM_STYLE_PATCH = """\
+def calculate_sum(first_value: int, second_value: int) -> int:
+    \"\"\"
+    Calculate the sum of two integers.
+
+    Args:
+        first_value: The first integer to add.
+        second_value: The second integer to add.
+
+    Returns:
+        The sum of first_value and second_value.
+    \"\"\"
+    return first_value + second_value
+
+def process_positive_items(items: list[int]) -> list[int]:
+    \"\"\"
+    Filter and double all positive items in the list.
+
+    Args:
+        items: A list of integers to process.
+
+    Returns:
+        A new list containing doubled values of all positive integers.
+    \"\"\"
+    result = []
+    for item in items:
+        if item > 0:
+            result.append(item * 2)
+    return result
+
+def get_user_by_id(user_id: int) -> Optional[User]:
+    \"\"\"
+    Retrieve a user from the database by their ID.
+
+    Args:
+        user_id: The unique identifier of the user.
+
+    Returns:
+        The User object if found, None otherwise.
+    \"\"\"
+    try:
+        return database.find_by_id(user_id)
+    except DatabaseError as error:
+        logger.error(f"Failed to fetch user {user_id}: {error}")
+        return None
+    except Exception as unexpected_error:
+        logger.critical(f"Unexpected error retrieving user: {unexpected_error}")
+        raise
"""
