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
        else:
            self.show_popup("Ошибка", "Неверное имя пользователя или пароль!")

    def show_popup(self, title, message):
        popup = Popup(
            title=title,
            content=Label(text=message),
            size_hint=(0.6, 0.4)
        )
        popup.open()


class HomeScreen(Screen):
    pass


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
                on_release=lambda btn: self.open_note(note)
            )
            notes_list.add_widget(note_button)

    def open_note(self, note):
        print("Открыта заметка:", note['title'])

    def create_note(self):
        self.manager.current = 'create_note'


class CreateNoteScreen(Screen):
    def save_note(self):
        title = self.ids.note_title.text
        content = self.ids.note_content.text
        is_public = 1 if self.ids.is_public.active else 0
        user_id = self.manager.current_user['id']

        if not title or not content:
            self.show_popup("Ошибка", "Введите заголовок и содержание заметки!")
            return

        query = """
            INSERT INTO notes (title, content, user_id, is_public)
            VALUES (%s, %s, %s, %s)
        """
        self.manager.db.execute_query(query, (title, content, user_id, is_public))
        self.show_popup("Успех", "Заметка успешно создана!")
        self.manager.current = 'notes'

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


class MainApp(App):
    def build(self):
        Builder.load_file('login.kv')
        Builder.load_file('home.kv')
        Builder.load_file('notes.kv')
        Builder.load_file('create_note.kv')
        return NotesApp()


if __name__ == '__main__':
    MainApp().run()
