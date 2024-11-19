import pymysql
import hashlib


class Database:
    def __init__(self):
        self.connection = pymysql.connect(
            host='localhost',
            user='root',
            password='',
            db='notes_app',
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
        self.cursor = self.connection.cursor()

    def fetch_all(self, query, params=None):
        self.cursor.execute(query, params or ())
        return self.cursor.fetchall()

    def fetch_one(self, query, params=None):
        self.cursor.execute(query, params or ())
        return self.cursor.fetchone()

    def execute(self, query, params=None):
        try:
            self.cursor.execute(query, params or ())
            self.connection.commit()
        except Exception as e:
            print(f"Ошибка выполнения запроса: {e}")
            self.connection.rollback()

    def log_action(self, user_id, action_type, note_id=None):
        query = """
            INSERT INTO logs (user_id, action_type, note_id)
            VALUES (%s, %s, %s)
        """
        self.execute(query, (user_id, action_type, note_id))

    @staticmethod
    def hash_password(password):
        # Хешируем пароль с помощью sha256
        return hashlib.sha256(password.encode('utf-8')).hexdigest()
