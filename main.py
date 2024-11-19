from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.popup import Popup
from hashlib import sha256
from db import Database
from kivy.lang import Builder


class LoginScreen(Screen):
    def login(self):
        username = self.ids.username.text
        password = self.ids.password.text

        if not username or not password:
            self.show_popup("Ошибка", "Введите имя пользователя и пароль!")
            return

        hashed_password = sha256(password.encode()).hexdigest()

        query = "SELECT * FROM users WHERE username = %s AND password_hash = %s"
        user = self.manager.db.fetch_one(query, (username, hashed_password))

        if user:
            self.manager.current_user = user
            self.manager.current = 'home'
            self.manager.db.log_action(App.get_running_app().root.current_user['id'], 'Вход')

        else:
            self.show_popup("Ошибка", "Неверное имя пользователя или пароль!")

    def registration(self):
        username = self.ids.username.text
        password = self.ids.password.text

        if not username or not password:
            self.show_popup("Ошибка", "Введите имя пользователя и пароль!")
            return

        hashed_password = sha256(password.encode()).hexdigest()

        existing_user = self.manager.db.fetch_one("SELECT * FROM users WHERE username = %s", (username,))

        if existing_user:
            self.show_popup("Внимание!", "Пользователь с таким именем уже существует.")
            return

        self.manager.db.execute("INSERT INTO users (username, password_hash, role) VALUES (%s, %s, 'user')",
                                (username, hashed_password))

        self.show_popup("Внимание!", "Пользователь зарегистрирован!")

        self.manager.db.log_action(self.manager.db.cursor.lastrowid, 'Регистрация')

    def show_popup(self, title, message):
        popup = Popup(
            title=title,
            content=Label(text=message),
            size_hint=(0.6, 0.4)
        )
        popup.open()


class NotesScreen(Screen):
    def on_enter(self):
        self.load_notes()

    def load_notes(self):
        user = self.manager.current_user
        user_id = user['id']
        role = user['role']

        query = """
            SELECT id, title, content, is_public, is_visible 
            FROM notes 
            WHERE (is_public = 1 AND is_visible = 1) OR user_id = %s
        """
        params = (user_id,)

        if role == 'admin':
            query = "SELECT id, title, content, is_public, is_visible FROM notes"
            params = ()

        notes = self.manager.db.fetch_all(query, params)

        notes_list = self.ids.notes_list
        notes_list.clear_widgets()

        for note in notes:
            note_button = Button(
                text=note['title'],
                size_hint_y=None,
                height=50,
                on_release=lambda btn, note_id=note['id']: self.open_note_for_edit(note_id)
            )
            notes_list.add_widget(note_button)

    def open_note_for_edit(self, note_id):
        # Сохраняем ID заметки в manager и открываем экран редактирования
        self.manager.current_note_id = note_id
        note_id = self.manager.current_note_id
        query = "SELECT id, title, content, is_public, password FROM notes WHERE id = %s"
        note = self.manager.db.fetch_one(query, (note_id,))

        if note['password']:
            self.manager.current_note_id = note['id']
            self.manager.current_note_password_hash = note['password']  # Сохраняем хеш пароля
            self.manager.current = 'note_password'
        else:
            self.manager.current = 'edit_note'

    def create_note(self):
        self.manager.current = 'create_note'

    def change_note_password(self, note):
        self.manager.current_note = note
        self.manager.current = 'change_note_password'


class CreateNoteScreen(Screen):
    def save_note(self):
        title = self.ids.note_title.text
        content = self.ids.note_content.text
        is_public = 1 if self.ids.is_public.active else 0
        user_id = self.manager.current_user['id']

        if is_public:
            self.ids.note_password.text = ''
            self.ids.note_password_confirm.text = ''

        password = self.ids.note_password.text
        password_confirm = self.ids.note_password_confirm.text

        if not title or not content:
            self.show_popup("Ошибка", "Введите заголовок и содержание заметки!")
            return

        # Если пароль введен, проверяем его подтверждение
        password_hash = None
        if password or password_confirm:
            if password != password_confirm:
                self.show_popup("Ошибка", "Пароли не совпадают!")
                return
            password_hash = Database.hash_password(password)

        query = """
            INSERT INTO notes (title, content, user_id, is_public, password)
            VALUES (%s, %s, %s, %s, %s)
        """
        self.manager.db.execute(query, (title, content, user_id, is_public, password_hash))

        note_id = self.manager.db.cursor.lastrowid

        # Логируем действие
        self.manager.db.log_action(user_id, 'Создание заметки', note_id)

        self.show_popup("Успех", "Заметка успешно создана!")
        self.manager.current = 'notes'

    def show_popup(self, title, message):
        popup = Popup(
            title=title,
            content=Label(text=message),
            size_hint=(0.6, 0.4)
        )
        popup.open()


class EditNoteScreen(Screen):
    def on_enter(self):
        # Получаем заметку по ID
        note_id = self.manager.current_note_id
        query = "SELECT id, title, content, is_public FROM notes WHERE id = %s"
        note = self.manager.db.fetch_one(query, (note_id,))

        if note:
            # Заполняем поля для редактирования
            self.ids.note_title.text = note['title']
            self.ids.note_content.text = note['content']
            self.ids.is_public.active = note['is_public'] == 1

    def save_note(self):
        user_id = App.get_running_app().root.current_user['id']
        title = self.ids.note_title.text
        content = self.ids.note_content.text
        is_public = 1 if self.ids.is_public.active else 0
        note_id = self.manager.current_note_id

        if is_public:
            query = """
                UPDATE notes
                SET title = %s, content = %s, is_public = %s, password = NULL 
                WHERE id = %s
            """
        else:
            # Обновляем заметку в базе данных
            query = """
                    UPDATE notes
                    SET title = %s, content = %s, is_public = %s
                    WHERE id = %s
                """
        self.manager.db.execute(query, (title, content, is_public, note_id))

        # Логируем действие
        self.manager.db.log_action(user_id, 'Изменение заметки', note_id)

        # Переходим на экран со списком заметок
        self.manager.current = 'notes'
        self.show_popup("Успех", "Заметка успешно обновлена!")

    def show_popup(self, title, message):
        popup = Popup(
            title=title,
            content=Label(text=message),
            size_hint=(0.6, 0.4)
        )
        popup.open()

    def cancel_edit(self):
        # Возвращаемся на экран с заметками без изменений
        self.manager.current = 'notes'

    def del_note(self):
        user_id = App.get_running_app().root.current_user['id']
        note_id = self.manager.current_note_id

        # Удаление заметки
        self.manager.db.execute("DELETE FROM notes WHERE id = %s", (note_id,))
        self.manager.db.log_action(user_id, 'Удаление заметки', note_id)
        self.manager.current = 'notes'
        self.show_popup("Успех", "Заметка успешно удалена!")

    def change_password(self):
        self.manager.current = 'change_password'


class HomeScreen(Screen):
    pass


class NotePasswordScreen(Screen):
    def on_enter(self):
        # Сбрасываем текстовое поле пароля
        self.ids.password_input.text = ''

    def check_password(self):
        entered_password = self.ids.password_input.text
        hashed_entered_password = sha256(entered_password.encode('utf-8')).hexdigest()

        if hashed_entered_password == self.manager.current_note_password_hash:
            # Если пароль правильный, открываем заметку
            note_id = self.manager.current_note_id
            query = "SELECT id, title, content, is_public FROM notes WHERE id = %s"
            note = self.manager.db.fetch_one(query, (note_id,))

            self.manager.current = 'edit_note'

        else:
            # Если пароль неверный, показываем ошибку
            self.show_popup("Ошибка", "Неверный пароль!")

    def show_popup(self, title, message):
        popup = Popup(
            title=title,
            content=Label(text=message),
            size_hint=(0.6, 0.4)
        )
        popup.open()


class EditPasswordScreen(Screen):
    def change_password(self):
        # Получаем заметку по ID
        note_id = self.manager.current_note_id
        user_id = App.get_running_app().root.current_user['id']
        password = self.ids.new_password.text
        password_confirm = self.ids.confirm_password.text

        password_hash = None
        if password or password_confirm:
            if password != password_confirm:
                self.show_popup("Ошибка", "Пароли не совпадают!")
                return
            password_hash = Database.hash_password(password)

        query = """
                UPDATE notes
                SET password = %s 
                WHERE id = %s
            """
        self.manager.db.execute(query, (password_hash, note_id))

        # Логируем действие
        self.manager.db.log_action(user_id, 'Изменение пароля', note_id)
        self.manager.current = 'edit_note'

    def show_popup(self, title, message):
        popup = Popup(
            title=title,
            content=Label(text=message),
            size_hint=(0.6, 0.4)
        )
        popup.open()


class UserPasswordScreen(Screen):
    def save_new_password(self):
        # Получаем заметку по ID
        user_id = App.get_running_app().root.current_user['id']
        password = self.ids.new_password.text
        password_confirm = self.ids.confirm_password.text

        password_hash = None
        if password or password_confirm:
            if password != password_confirm:
                self.show_popup("Ошибка", "Пароли не совпадают!")
                return
            password_hash = Database.hash_password(password)

        query = """
                        UPDATE users
                        SET password_hash = %s 
                        WHERE id = %s
                    """
        self.manager.db.execute(query, (password_hash, user_id))

        self.show_popup("Внимание!", "Пароль изменен!")

        # Логируем действие
        self.manager.db.log_action(user_id, 'Изменение пароля')
        self.manager.current = 'login'

    def show_popup(self, title, message):
        popup = Popup(
            title=title,
            content=Label(text=message),
            size_hint=(0.6, 0.4)
        )
        popup.open()


class NotesApp(ScreenManager):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.db = Database()
        self.current_user = None
        self.add_widget(LoginScreen(name='login'))
        self.add_widget(HomeScreen(name='home'))
        self.add_widget(NotesScreen(name='notes'))
        self.add_widget(CreateNoteScreen(name='create_note'))
        self.add_widget(EditNoteScreen(name='edit_note'))
        self.add_widget(NotePasswordScreen(name='note_password'))
        self.add_widget(EditPasswordScreen(name='change_password'))
        self.add_widget(UserPasswordScreen(name='user_password'))


class MainApp(App):
    def build(self):
        Builder.load_file('login.kv')
        Builder.load_file('home.kv')
        Builder.load_file('notes.kv')
        Builder.load_file('create_note.kv')
        Builder.load_file('change_note_password.kv')
        Builder.load_file('edit_note.kv')
        Builder.load_file('note_password.kv')
        Builder.load_file('change_user_password.kv')
        return NotesApp()


if __name__ == '__main__':
    MainApp().run()
