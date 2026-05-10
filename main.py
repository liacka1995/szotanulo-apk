import os, csv, json, random, time, unicodedata, difflib

from kivy.app import App
from kivy.core.window import Window
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.togglebutton import ToggleButton

# ---- ALAP STÍLUS ----
Window.clearcolor = (0.07, 0.07, 0.07, 1)

BG = (0.07, 0.07, 0.07, 1)
CARD = (0.12, 0.12, 0.12, 1)
ACCENT = (0.3, 0.7, 0.3, 1)
TEXT = (1, 1, 1, 1)

# ---- NORMALIZÁLÁS ----
def normalize(text):
    text = text.lower().strip()
    text = ''.join(
        c for c in unicodedata.normalize('NFD', text)
        if unicodedata.category(c) != 'Mn'
    )
    return text

def similar(a, b):
    return difflib.SequenceMatcher(None, normalize(a), normalize(b)).ratio()

def hu_match(user, correct_list):
    user_n = normalize(user)
    for c in correct_list:
        c_n = normalize(c)
        if user_n == c_n:
            return True
        if len(user_n) >= 3 and user_n in c_n:
            return True
        if len(c_n) >= 3 and c_n in user_n:
            return True
        if similar(user_n, c_n) > 0.75:
            return True
    return False

# ---- FÁJLOK ----
BASE = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE, "szavak_2000.csv")
TUDAS_PATH = os.path.join(BASE, "tudas.json")

# ---- SZÓTÁR ----
szotar = []
with open(CSV_PATH, encoding="utf-8-sig") as f:
    sample = f.read(1024)
    f.seek(0)
    delimiter = ',' if sample.count(',') >= sample.count(';') else ';'
    reader = csv.reader(f, delimiter=delimiter)
    for row in reader:
        if len(row) < 2:
            continue
        en = row[0].strip()
        hu = [x.strip() for x in row[1].split("|") if x.strip()]
        if en and hu:
            szotar.append({"en": en, "hu": hu})

daily_goal = len(szotar)

# ---- TUDÁS ----
if os.path.exists(TUDAS_PATH):
    try:
        with open(TUDAS_PATH, "r", encoding="utf-8") as f:
            tudas = json.load(f)
    except:
        tudas = {}
else:
    tudas = {}

def get_data(word):
    if word not in tudas:
        tudas[word] = {"score": 0, "wrong": 0, "last_correct": 0, "streak": 0}
    if isinstance(tudas[word], int):
        tudas[word] = {"score": tudas[word], "wrong": 0, "last_correct": 0, "streak": 0}
    return tudas[word]

def save():
    with open(TUDAS_PATH, "w", encoding="utf-8") as f:
        json.dump(tudas, f, ensure_ascii=False, indent=2)

def format_time(seconds):
    seconds = int(seconds)
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h} óra {m} perc {s} mp"
    elif m > 0:
        return f"{m} perc {s} mp"
    else:
        return f"{s} mp"

# ---- KÉRDÉSVÁLASZTÓ ----
def get_question(master_mode, master_list, master_index):
    now = time.time()

    if master_mode:
        if not master_list:
            master_list.extend([s for s in szotar if get_data(s["en"])["wrong"] > 0])
            random.shuffle(master_list)
            master_index[0] = 0
        if master_list:
            szo = master_list[master_index[0]]
            master_index[0] = (master_index[0] + 1) % len(master_list)
            return szo

    while True:
        szo = random.choice(szotar)
        d = get_data(szo["en"])
        wait = min(600, d["score"] * 30)
        if now - d["last_correct"] < wait:
            continue
        if d["wrong"] > 2:
            return szo
        if d["score"] >= 4:
            if random.random() < 0.3:
                return szo
        else:
            return szo

# ---- FŐ FELÜLET ----
class MainWidget(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", padding=15, spacing=10, **kwargs)
        self.session_start = time.time()
        self.daily_wrong = set()
        self.daily_fixed = set()
        self.stats_visible = False

        self.master_mode = False
        self.quiz_mode = False
        self.mix_mode = False

        self.master_list = []
        self.master_index = [0]
        self.waiting_for_next = False

        self.current_word = None
        self.mode = None
        self.options = []

        self.pont = 0
        self.ossz = 0

        self.mix_pair_count = 5
        self.mix_pairs = {}
        self.mix_selected_left = None
        self.mix_selected_right = None
        self.mix_left_buttons = []
        self.mix_right_buttons = []

        # --- FELSŐ KÁRTYA ---
        top = BoxLayout(orientation="vertical", padding=10, spacing=10)
        self.label = Label(
            text="Szótanuló ULTRA 😄",
            font_size=28,
            color=TEXT
        )
        top.add_widget(self.label)

        self.entry = TextInput(
            multiline=False,
            font_size=24,
            size_hint=(1, 0.2),
            halign="center",
            foreground_color=TEXT,
            background_color=(0.15, 0.15, 0.15, 1)
        )
        top.add_widget(self.entry)

        self.result_label = Label(
            text="",
            font_size=20,
            color=TEXT
        )
        top.add_widget(self.result_label)

        self.score_label = Label(
            text="0 / {}".format(daily_goal),
            font_size=18,
            color=TEXT
        )
        top.add_widget(self.score_label)

        self.add_widget(top)

        # --- KVÍZ GOMBOK ---
        self.quiz_buttons_layout = BoxLayout(orientation="vertical", spacing=5, size_hint=(1, 0.5))
        self.option_buttons = []
        for i in range(4):
            b = Button(
                text="",
                font_size=18,
                size_hint=(1, None),
                height=40,
                background_color=(0.16, 0.16, 0.16, 1),
                color=TEXT
            )
            b.bind(on_press=lambda btn, idx=i: self.check_answer(idx))
            self.quiz_buttons_layout.add_widget(b)
            self.option_buttons.append(b)
        self.add_widget(self.quiz_buttons_layout)

        # --- MIX UI ---
        self.mix_layout = GridLayout(cols=2, spacing=10, size_hint=(1, 0.7))
        self.mix_left_layout = BoxLayout(orientation="vertical", spacing=5)
        self.mix_right_layout = BoxLayout(orientation="vertical", spacing=5)
        self.mix_layout.add_widget(self.mix_left_layout)
        self.mix_layout.add_widget(self.mix_right_layout)
        # alapból rejtve, csak mix módban használjuk

        # --- STATISZTIKA LABEL ---
        self.stats_layout = BoxLayout(orientation="vertical", size_hint=(1, 0.2))
        self.stats_label1 = Label(text="", font_size=16, color=(1, 0.6, 1, 1))
        self.stats_label2 = Label(text="", font_size=16, color=(1, 0.6, 1, 1))
        self.stats_layout.add_widget(self.stats_label1)
        self.stats_layout.add_widget(self.stats_label2)
        # alapból rejtve

        # --- ALSÓ GOMBOK ---
        btn_row1 = BoxLayout(orientation="horizontal", size_hint=(1, 0.15), spacing=5)
        btn_row2 = BoxLayout(orientation="horizontal", size_hint=(1, 0.15), spacing=5)

        self.btn_check = Button(
            text="Ellenőrzés",
            font_size=18,
            background_color=ACCENT,
            color=TEXT
        )
        self.btn_check.bind(on_press=lambda *_: self.check_answer())
        btn_row1.add_widget(self.btn_check)

        self.btn_show = Button(
            text="Mutasd",
            font_size=18,
            background_color=ACCENT,
            color=TEXT
        )
        self.btn_show.bind(on_press=lambda *_: self.show_answer())
        btn_row1.add_widget(self.btn_show)

        self.btn_stats = Button(
            text="Statisztika",
            font_size=18,
            background_color=ACCENT,
            color=TEXT
        )
        self.btn_stats.bind(on_press=lambda *_: self.toggle_stats())
        btn_row1.add_widget(self.btn_stats)

        self.btn_master = ToggleButton(
            text="Master OFF",
            font_size=18,
            background_color=ACCENT,
            color=TEXT
        )
        self.btn_master.bind(on_press=lambda *_: self.toggle_master())
        btn_row2.add_widget(self.btn_master)

        self.btn_quiz = ToggleButton(
            text="Kvíz OFF",
            font_size=18,
            background_color=ACCENT,
            color=TEXT
        )
        self.btn_quiz.bind(on_press=lambda *_: self.toggle_quiz())
        btn_row2.add_widget(self.btn_quiz)

        self.btn_mix = ToggleButton(
            text="MIX OFF",
            font_size=18,
            background_color=ACCENT,
            color=TEXT
        )
        self.btn_mix.bind(on_press=lambda *_: self.toggle_mix())
        btn_row2.add_widget(self.btn_mix)

        self.btn_reset = Button(
            text="Reset",
            font_size=18,
            background_color=(0.8, 0.4, 0.1, 1),
            color=TEXT
        )
        self.btn_reset.bind(on_press=lambda *_: self.reset_all())
        btn_row2.add_widget(self.btn_reset)

        self.add_widget(btn_row1)
        self.add_widget(btn_row2)

        # ENTER kezelés
        Window.bind(on_key_down=self.on_key_down)

        self.update_progress()
        self.new_question()

    # ---- ENTER ----
    def on_key_down(self, window, key, scancode, codepoint, modifiers):
        if key == 13:  # Enter
            if self.mix_mode:
                return
            if self.quiz_mode:
                self.next_question()
            else:
                self.check_answer()
        return False

    # ---- PROGRESS ----
    def update_progress(self):
        if daily_goal > 0:
            self.score_label.text = f"{self.ossz}/{daily_goal}"

    def reset_quiz_buttons(self):
        for b in self.option_buttons:
            b.text = ""
            b.background_color = (0.16, 0.16, 0.16, 1)
            b.disabled = False

    # ---- KÉRDÉS ----
    def new_question(self):
        if self.mix_mode:
            return
        self.waiting_for_next = False
        self.entry.text = ""
        self.result_label.text = ""
        self.reset_quiz_buttons()

        self.current_word = get_question(self.master_mode, self.master_list, self.master_index)

        if random.random() < 0.5:
            self.mode = "hu"
            self.label.text = f"Mit jelent: [b]{self.current_word['en']}[/b]"
            self.label.markup = True
        else:
            self.mode = "en"
            hu = random.choice(self.current_word["hu"])
            self.label.text = f"Mi angolul: [b]{hu}[/b]"
            self.label.markup = True

        if self.quiz_mode:
            self.generate_options()

    def generate_options(self):
        self.options = []
        if self.mode == "hu":
            correct = random.choice(self.current_word["hu"])
            self.options.append(correct)
            while len(self.options) < 4:
                cand = random.choice(random.choice(szotar)["hu"])
                if cand not in self.options:
                    self.options.append(cand)
        else:
            correct = self.current_word["en"]
            self.options.append(correct)
            while len(self.options) < 4:
                cand = random.choice(szotar)["en"]
                if cand not in self.options:
                    self.options.append(cand)

        random.shuffle(self.options)
        for i, b in enumerate(self.option_buttons):
            b.text = self.options[i]
            b.disabled = False
            b.background_color = (0.16, 0.16, 0.16, 1)

    # ---- ELLENŐRZÉS ----
    def check_answer(self, idx=None):
        if self.mix_mode:
            return
        if self.waiting_for_next:
            return
        self.waiting_for_next = True

        if self.quiz_mode and idx is not None:
            valasz = self.options[idx]
        else:
            valasz = self.entry.text.strip()

        if not valasz:
            self.waiting_for_next = False
            return

        self.ossz += 1
        d = get_data(self.current_word["en"])
        word_key = self.current_word["en"]

        if self.mode == "hu":
            helyes = hu_match(valasz, self.current_word["hu"])
            helyes_valasz = ", ".join(self.current_word["hu"])
        else:
            if self.quiz_mode:
                helyes = normalize(valasz) == normalize(self.current_word["en"])
            else:
                if normalize(valasz) == normalize(self.current_word["en"]):
                    helyes = True
                elif len(valasz) < 3:
                    helyes = False
                else:
                    helyes = similar(valasz, self.current_word["en"]) > 0.92
            helyes_valasz = self.current_word["en"]

        if helyes:
            self.pont += 1
            d["score"] += 1
            d["streak"] += 1
            d["last_correct"] = time.time()
            self.result_label.text = "[color=00ff00]✅ Helyes![/color]"
            self.result_label.markup = True
            if word_key in self.daily_wrong:
                self.daily_fixed.add(word_key)
        else:
            d["score"] = 0
            d["streak"] = 0
            d["wrong"] += 1
            self.daily_wrong.add(word_key)
            self.result_label.text = f"[color=ff4444]❌ {helyes_valasz}[/color]"
            self.result_label.markup = True

        self.update_progress()
        save()

        if self.quiz_mode and idx is not None:
            for i, b in enumerate(self.option_buttons):
                b.disabled = True
                if self.mode == "hu":
                    if self.options[i] in self.current_word["hu"]:
                        b.background_color = (0.2, 0.7, 0.2, 1)
                else:
                    if normalize(self.options[i]) == normalize(self.current_word["en"]):
                        b.background_color = (0.2, 0.7, 0.2, 1)
            if not helyes:
                self.option_buttons[idx].background_color = (0.9, 0.3, 0.3, 1)

        if self.quiz_mode:
            if helyes:
                # gyorsan új kérdés
                self.waiting_for_next = False
                self.new_question()
            else:
                self.result_label.text = f"[color=ff4444]❌ {helyes_valasz}  (Nyomj Entert)[/color]"
                self.result_label.markup = True
        else:
            # normál mód
            self.waiting_for_next = False
            self.new_question()

    def next_question(self):
        if self.mix_mode:
            return
        if self.waiting_for_next:
            self.waiting_for_next = False
            self.new_question()

    # ---- MÓDOK ----
    def toggle_master(self):
        self.master_mode = not self.master_mode
        self.master_list.clear()
        self.btn_master.text = f"Master {'ON' if self.master_mode else 'OFF'}"
        self.new_question()

    def toggle_quiz(self):
        self.quiz_mode = not self.quiz_mode
        self.btn_quiz.text = f"Kvíz {'ON' if self.quiz_mode else 'OFF'}"
        self.reset_quiz_buttons()
        if self.quiz_mode:
            self.generate_options()
        else:
            self.reset_quiz_buttons()

    def show_answer(self):
        if not self.current_word or self.mix_mode:
            return
        if self.mode == "hu":
            self.result_label.text = ", ".join(self.current_word["hu"])
        else:
            self.result_label.text = self.current_word["en"]

    # ---- STATISZTIKA ----
    def toggle_stats(self):
        if self.stats_visible:
            if self.stats_layout.parent:
                self.remove_widget(self.stats_layout)
            self.stats_visible = False
        else:
            elapsed = time.time() - self.session_start
            ido = format_time(elapsed)
            javitott = len(self.daily_fixed)
            self.stats_label1.text = f"Idő: {ido}"
            self.stats_label2.text = f"Javított szavak: {javitott}"
            if not self.stats_layout.parent:
                self.add_widget(self.stats_layout)
            self.stats_visible = True

    # ---- RESET ----
    def reset_all(self):
        global tudas
        tudas = {}
        self.pont = 0
        self.ossz = 0
        self.daily_wrong = set()
        self.daily_fixed = set()
        self.session_start = time.time()
        save()
        self.update_progress()
        self.result_label.text = "[color=ffbb33]Resetelve[/color]"
        self.result_label.markup = True

    # ---- MIX MÓD ----
    def toggle_mix(self):
        self.mix_mode = not self.mix_mode
        if self.mix_mode:
            self.btn_mix.text = "MIX ON"
            # elrejtjük a bevitelt + kvíz gombokat
            self.entry.opacity = 0
            self.entry.disabled = True
            self.quiz_buttons_layout.opacity = 0
            self.quiz_buttons_layout.disabled = True
            if self.stats_layout.parent:
                self.remove_widget(self.stats_layout)
                self.stats_visible = False
            if not self.mix_layout.parent:
                self.add_widget(self.mix_layout, index=1)
            self.new_mix_round()
        else:
            self.btn_mix.text = "MIX OFF"
            if self.mix_layout.parent:
                self.remove_widget(self.mix_layout)
            self.entry.opacity = 1
            self.entry.disabled = False
            self.quiz_buttons_layout.opacity = 1
            self.quiz_buttons_layout.disabled = False
            self.new_question()

    def clear_mix_buttons(self):
        for b in self.mix_left_buttons + self.mix_right_buttons:
            if b.parent:
                b.parent.remove_widget(b)
        self.mix_left_buttons = []
        self.mix_right_buttons = []

    def new_mix_round(self):
        self.clear_mix_buttons()
        self.mix_pairs = {}
        self.mix_selected_left = None
        self.mix_selected_right = None

        words = random.sample(szotar, min(self.mix_pair_count, len(szotar)))
        left_words = [w["en"] for w in words]
        right_words = [random.choice(w["hu"]) for w in words]

        self.mix_pairs = dict(zip(left_words, right_words))

        random.shuffle(left_words)
        random.shuffle(right_words)

        for w in left_words:
            b = Button(
                text=w,
                font_size=16,
                size_hint=(1, None),
                height=40,
                background_color=(0.16, 0.16, 0.16, 1),
                color=TEXT
            )
            b.bind(on_press=lambda btn, word=w: self.select_left(word))
            self.mix_left_layout.add_widget(b)
            self.mix_left_buttons.append(b)

        for w in right_words:
            b = Button(
                text=w,
                font_size=16,
                size_hint=(1, None),
                height=40,
                background_color=(0.16, 0.16, 0.16, 1),
                color=TEXT
            )
            b.bind(on_press=lambda btn, word=w: self.select_right(word))
            self.mix_right_layout.add_widget(b)
            self.mix_right_buttons.append(b)

        self.label.text = "Párosítsd az angol és magyar szavakat!"
        self.result_label.text = ""

    def highlight_selection(self):
        for b in self.mix_left_buttons:
            if b.text == self.mix_selected_left and not b.disabled:
                b.background_color = (0.27, 0.27, 0.27, 1)
            elif not b.disabled:
                b.background_color = (0.16, 0.16, 0.16, 1)
        for b in self.mix_right_buttons:
            if b.text == self.mix_selected_right and not b.disabled:
                b.background_color = (0.27, 0.27, 0.27, 1)
            elif not b.disabled:
                b.background_color = (0.16, 0.16, 0.16, 1)

    def select_left(self, word):
        self.mix_selected_left = word
        self.highlight_selection()

    def select_right(self, word):
        self.mix_selected_right = word
        self.highlight_selection()
        self.check_mix_pair()

    def reset_wrong(self, b1, b2):
        if not b1.disabled:
            b1.background_color = (0.16, 0.16, 0.16, 1)
        if not b2.disabled:
            b2.background_color = (0.16, 0.16, 0.16, 1)

    def check_mix_complete(self):
        for b in self.mix_left_buttons + self.mix_right_buttons:
            if not b.disabled:
                return
        # ha minden kész, új kör
        self.new_mix_round()

    def check_mix_pair(self):
        if not self.mix_selected_left or not self.mix_selected_right:
            return

        left = self.mix_selected_left
        right = self.mix_selected_right

        left_btn = next(b for b in self.mix_left_buttons if b.text == left)
        right_btn = next(b for b in self.mix_right_buttons if b.text == right)

        if self.mix_pairs[left] == right:
            left_btn.background_color = (0.2, 0.7, 0.2, 1)
            right_btn.background_color = (0.2, 0.7, 0.2, 1)
            left_btn.disabled = True
            right_btn.disabled = True
        else:
            left_btn.background_color = (0.9, 0.3, 0.3, 1)
            right_btn.background_color = (0.9, 0.3, 0.3, 1)
            # kis késleltetés helyett egyszerű visszaállítás
            self.reset_wrong(left_btn, right_btn)

        self.mix_selected_left = None
        self.mix_selected_right = None
        self.highlight_selection()
        self.check_mix_complete()

class SzotanuloUltraApp(App):
    def build(self):
        self.title = "Szótanuló ULTRA – Kivy"
        return MainWidget()

if __name__ == "__main__":
    SzotanuloUltraApp().run()
