# -*- coding: utf-8 -*-
"""
Лабораторная работа: «Разработка графического приложения с помощью Tkinter».
Приложение «Запись на приём к врачу».

Запуск:  python appointment_app.py
Данные хранятся в файле appointments.csv рядом со скриптом
(создаётся автоматически и загружается при запуске).
"""

import csv
import os
import re
import tkinter as tk
from datetime import date, datetime
from tkinter import messagebox, ttk

# ----------------------------------------------------------------------------
# Константы
# ----------------------------------------------------------------------------
APP_TITLE = "Запись на приём к врачу"
CSV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "appointments.csv")
CSV_FIELDS = [
    "id", "fio", "iin", "birth", "phone", "email", "specialty", "doctor",
    "date", "time", "type", "format", "complaints", "status",
]

DATE_FORMAT = "%d.%m.%Y"
MAX_COMPLAINT_LEN = 300
MAX_AGE = 120
ALL = "Все"

DOCTORS = {
    "Терапевт": ["Алиев Серик Маратович", "Нурпеисова Айгерим Булатовна", "Ким Елена Викторовна"],
    "Кардиолог": ["Жумабаев Данияр Асхатович", "Сидорова Ольга Петровна"],
    "Невролог": ["Касымов Ерлан Тимурович", "Ахметова Гульнара Салиховна"],
    "Офтальмолог": ["Бекова Меруерт Сериковна", "Иванов Андрей Николаевич"],
    "Дерматолог": ["Оспанова Жанар Кайратовна", "Петров Игорь Сергеевич"],
}

TIMES = [f"{h:02d}:{m:02d}" for h in range(9, 18) for m in (0, 30) if not (h == 17 and m == 30)]
VISIT_TYPES = ["Первичный", "Повторный"]
VISIT_FORMATS = ["Очный", "Онлайн"]

STATUS_PLANNED = "Запланирован"
STATUS_DONE = "Пациент принят"
STATUS_CANCELLED = "Отменён"
STATUS_NO_SHOW = "Пациент не явился"
# (название, имя тега, цвет строки)
STATUSES = [
    (STATUS_PLANNED, "planned", "#DCEBFF"),
    (STATUS_DONE, "done", "#D4F1D4"),
    (STATUS_CANCELLED, "cancelled", "#E2E2E2"),
    (STATUS_NO_SHOW, "noshow", "#F8D2D2"),
]
STATUS_NAMES = [s[0] for s in STATUSES]
STATUS_TAG = {s[0]: s[1] for s in STATUSES}


# ----------------------------------------------------------------------------
# Вспомогательные функции (без интерфейса)
# ----------------------------------------------------------------------------
def parse_date(text):
    """Строку ДД.ММ.ГГГГ -> date, при ошибке None."""
    text = text.strip()
    if not re.fullmatch(r"[0-9]{2}\.[0-9]{2}\.[0-9]{4}", text):
        return None
    try:
        return datetime.strptime(text, DATE_FORMAT).date()
    except ValueError:
        return None


def calc_age(birth, today):
    """Полное количество лет на дату today."""
    return today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))


def sort_key(rec):
    """Ключ сортировки записей: дата, затем время."""
    d = parse_date(rec["date"]) or date.max
    return (d, rec["time"])


# ----------------------------------------------------------------------------
# Основной класс приложения
# ----------------------------------------------------------------------------
class AppointmentApp:
    def __init__(self, root):
        self.root = root
        self.records = []        # все записи (список словарей)
        self.editing_id = None   # id записи, которая сейчас редактируется

        root.title(APP_TITLE)
        root.geometry("1240x740")
        root.minsize(900, 650)

        self.setup_styles()
        self.create_variables()
        self.build_ui()
        self.load_from_csv()
        self.refresh_table()

    # ------------------------------------------------------------------ стили
    def setup_styles(self):
        style = ttk.Style()

        # Исправление известной ошибки Tk: цвета тегов Treeview не работают
        def fixed_map(option):
            return [e for e in style.map("Treeview", query_opt=option)
                    if e[:2] != ("!disabled", "!selected")]

        style.map("Treeview", foreground=fixed_map("foreground"),
                  background=fixed_map("background"))
        style.configure("Treeview", rowheight=24)

    # ------------------------------------------------------------ переменные
    def create_variables(self):
        # форма пациента
        self.var_fio = tk.StringVar()
        self.var_iin = tk.StringVar()
        self.var_birth = tk.StringVar()
        self.var_phone = tk.StringVar()
        self.var_email = tk.StringVar()
        # приём
        self.var_specialty = tk.StringVar()
        self.var_doctor = tk.StringVar()
        self.var_date = tk.StringVar()
        self.var_time = tk.StringVar()
        self.var_type = tk.StringVar(value=VISIT_TYPES[0])
        self.var_format = tk.StringVar(value=VISIT_FORMATS[0])
        self.var_counter = tk.StringVar(value=f"0 / {MAX_COMPLAINT_LEN}")
        # поиск и фильтры
        self.var_f_name = tk.StringVar()
        self.var_f_iin = tk.StringVar()
        self.var_f_doctor = tk.StringVar(value=ALL)
        self.var_f_date = tk.StringVar()
        self.var_f_status = tk.StringVar(value=ALL)
        # управление статусом и информационная строка
        self.var_new_status = tk.StringVar(value=STATUS_PLANNED)
        self.var_info = tk.StringVar(value="Выберите запись в таблице, чтобы увидеть подробности.")
        self.var_count = tk.StringVar()

    # -------------------------------------------------------------- интерфейс
    def build_ui(self):
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(0, weight=1)

        left = ttk.Frame(self.root, padding=8)
        left.grid(row=0, column=0, sticky="ns")
        right = ttk.Frame(self.root, padding=8)
        right.grid(row=0, column=1, sticky="nsew")

        self.build_form(left)
        self.build_right_panel(right)

    def build_form(self, parent):
        # ---- Данные пациента (Задание 2)
        patient = ttk.LabelFrame(parent, text=" Данные пациента ", padding=8)
        patient.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        rows = [
            ("Ф. И. О.:", self.var_fio),
            ("ИИН (12 цифр):", self.var_iin),
            ("Дата рождения\n(ДД.ММ.ГГГГ):", self.var_birth),
            ("Телефон:", self.var_phone),
            ("E-mail:", self.var_email),
        ]
        for i, (caption, var) in enumerate(rows):
            ttk.Label(patient, text=caption).grid(row=i, column=0, sticky="w", pady=2)
            entry = ttk.Entry(patient, textvariable=var, width=32)
            entry.grid(row=i, column=1, sticky="ew", pady=2, padx=(8, 0))
            if i == 0:
                self.entry_fio = entry
        patient.columnconfigure(1, weight=1)

        # ---- Выбор врача (Задание 3)
        doctor = ttk.LabelFrame(parent, text=" Врач ", padding=8)
        doctor.grid(row=1, column=0, sticky="ew", pady=6)
        ttk.Label(doctor, text="Специальность:").grid(row=0, column=0, sticky="w", pady=2)
        self.cb_specialty = ttk.Combobox(doctor, textvariable=self.var_specialty,
                                         values=list(DOCTORS.keys()), state="readonly", width=30)
        self.cb_specialty.grid(row=0, column=1, sticky="ew", pady=2, padx=(8, 0))
        self.cb_specialty.bind("<<ComboboxSelected>>", self.on_specialty_change)

        ttk.Label(doctor, text="Врач:").grid(row=1, column=0, sticky="w", pady=2)
        self.cb_doctor = ttk.Combobox(doctor, textvariable=self.var_doctor,
                                      values=[], state="readonly", width=30)
        self.cb_doctor.grid(row=1, column=1, sticky="ew", pady=2, padx=(8, 0))
        doctor.columnconfigure(1, weight=1)

        # ---- Параметры приёма (Задание 4)
        visit = ttk.LabelFrame(parent, text=" Параметры приёма ", padding=8)
        visit.grid(row=2, column=0, sticky="ew", pady=6)
        ttk.Label(visit, text="Дата (ДД.ММ.ГГГГ):").grid(row=0, column=0, sticky="w", pady=2)
        ttk.Entry(visit, textvariable=self.var_date, width=32).grid(
            row=0, column=1, sticky="ew", pady=2, padx=(8, 0))

        ttk.Label(visit, text="Время:").grid(row=1, column=0, sticky="w", pady=2)
        self.cb_time = ttk.Combobox(visit, textvariable=self.var_time, values=TIMES,
                                    state="readonly", width=30)
        self.cb_time.grid(row=1, column=1, sticky="ew", pady=2, padx=(8, 0))

        ttk.Label(visit, text="Тип приёма:").grid(row=2, column=0, sticky="w", pady=2)
        type_frame = ttk.Frame(visit)
        type_frame.grid(row=2, column=1, sticky="w", padx=(8, 0))
        for text in VISIT_TYPES:
            ttk.Radiobutton(type_frame, text=text, value=text,
                            variable=self.var_type).pack(side="left", padx=(0, 12))

        ttk.Label(visit, text="Формат:").grid(row=3, column=0, sticky="w", pady=2)
        fmt_frame = ttk.Frame(visit)
        fmt_frame.grid(row=3, column=1, sticky="w", padx=(8, 0))
        for text in VISIT_FORMATS:
            ttk.Radiobutton(fmt_frame, text=text, value=text,
                            variable=self.var_format).pack(side="left", padx=(0, 12))
        visit.columnconfigure(1, weight=1)

        # ---- Жалобы (Задание 5)
        complaints = ttk.LabelFrame(parent, text=" Краткое описание жалоб ", padding=8)
        complaints.grid(row=3, column=0, sticky="ew", pady=6)
        self.txt_complaints = tk.Text(complaints, height=5, width=38, wrap="word",
                                      font=("TkDefaultFont", 10))
        self.txt_complaints.grid(row=0, column=0, sticky="ew")
        ttk.Label(complaints, textvariable=self.var_counter).grid(row=1, column=0, sticky="e")
        complaints.columnconfigure(0, weight=1)
        self.txt_complaints.bind("<KeyPress>", self.on_complaint_keypress)
        self.txt_complaints.bind("<KeyRelease>", self.on_complaint_change)
        self.txt_complaints.bind("<<Paste>>", self.on_complaint_paste)

        # ---- Кнопки формы (Задание 7)
        buttons = ttk.Frame(parent)
        buttons.grid(row=4, column=0, sticky="ew", pady=(6, 0))
        self.btn_submit = ttk.Button(buttons, text="Записаться на приём", command=self.submit_form)
        self.btn_submit.pack(fill="x", pady=2)
        row = ttk.Frame(buttons)
        row.pack(fill="x", pady=2)
        ttk.Button(row, text="Очистить форму", command=self.clear_form).pack(
            side="left", expand=True, fill="x", padx=(0, 3))
        self.btn_cancel_edit = ttk.Button(row, text="Отменить редактирование",
                                          command=self.clear_form, state="disabled")
        self.btn_cancel_edit.pack(side="left", expand=True, fill="x", padx=(3, 0))

    def build_right_panel(self, parent):
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        # ---- Поиск и фильтры (Задание 11)
        search = ttk.LabelFrame(parent, text=" Поиск и фильтры ", padding=8)
        search.grid(row=0, column=0, sticky="ew")

        ttk.Label(search, text="Ф. И. О.:").grid(row=0, column=0, sticky="w")
        e_name = ttk.Entry(search, textvariable=self.var_f_name, width=22)
        e_name.grid(row=0, column=1, padx=(4, 12), pady=2, sticky="w")
        ttk.Label(search, text="ИИН:").grid(row=0, column=2, sticky="w")
        e_iin = ttk.Entry(search, textvariable=self.var_f_iin, width=16)
        e_iin.grid(row=0, column=3, padx=(4, 12), pady=2, sticky="w")
        ttk.Label(search, text="Дата:").grid(row=0, column=4, sticky="w")
        e_date = ttk.Entry(search, textvariable=self.var_f_date, width=12)
        e_date.grid(row=0, column=5, padx=(4, 0), pady=2, sticky="w")

        all_doctors = [d for docs in DOCTORS.values() for d in docs]
        ttk.Label(search, text="Врач:").grid(row=1, column=0, sticky="w")
        cb_doc = ttk.Combobox(search, textvariable=self.var_f_doctor, state="readonly",
                              values=[ALL] + sorted(all_doctors), width=30)
        cb_doc.grid(row=1, column=1, columnspan=3, padx=(4, 12), pady=2, sticky="w")
        ttk.Label(search, text="Статус:").grid(row=1, column=4, sticky="w")
        cb_status = ttk.Combobox(search, textvariable=self.var_f_status, state="readonly",
                                 values=[ALL] + STATUS_NAMES, width=18)
        cb_status.grid(row=1, column=5, padx=(4, 0), pady=2, sticky="w")

        btns = ttk.Frame(search)
        btns.grid(row=0, column=6, rowspan=2, padx=(14, 0))
        ttk.Button(btns, text="Найти", command=self.refresh_table).pack(fill="x", pady=1)
        ttk.Button(btns, text="Показать все", command=self.reset_filters).pack(fill="x", pady=1)

        # поиск «на лету» и по Enter
        for widget in (e_name, e_iin, e_date):
            widget.bind("<KeyRelease>", lambda e: self.refresh_table())
            widget.bind("<Return>", lambda e: self.refresh_table())
        for widget in (cb_doc, cb_status):
            widget.bind("<<ComboboxSelected>>", lambda e: self.refresh_table())

        # ---- Таблица записей (Задание 8)
        table_frame = ttk.Frame(parent)
        table_frame.grid(row=1, column=0, sticky="nsew", pady=6)
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)

        columns = ("patient", "doctor", "specialty", "date", "time", "format", "status")
        headings = {
            "patient": ("Пациент", 190), "doctor": ("Врач", 190),
            "specialty": ("Специальность", 105), "date": ("Дата", 85),
            "time": ("Время", 55), "format": ("Формат", 65), "status": ("Статус", 125),
        }
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings",
                                 selectmode="browse")
        for col in columns:
            title, width = headings[col]
            self.tree.heading(col, text=title)
            self.tree.column(col, width=width, minwidth=50, anchor="w")
        for _name, tag, color in STATUSES:
            self.tree.tag_configure(tag, background=color)

        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        self.tree.bind("<<TreeviewSelect>>", self.on_row_select)
        self.tree.bind("<Double-1>", self.on_row_double_click)

        ttk.Label(parent, textvariable=self.var_count).grid(row=2, column=0, sticky="w")

        # ---- Подробные данные выбранной строки
        info = ttk.LabelFrame(parent, text=" Подробные данные ", padding=6)
        info.grid(row=3, column=0, sticky="ew", pady=6)
        ttk.Label(info, textvariable=self.var_info, wraplength=760, justify="left",
                  anchor="nw").pack(fill="x")
        info.configure(height=80)

        # ---- Управление записями (Задание 10 + доп. задание)
        actions = ttk.LabelFrame(parent, text=" Управление записями ", padding=6)
        actions.grid(row=4, column=0, sticky="ew")
        ttk.Button(actions, text="Изменить", command=self.start_edit).pack(side="left", padx=2)
        ttk.Button(actions, text="Отменить запись", command=self.cancel_appointment).pack(
            side="left", padx=2)
        ttk.Button(actions, text="Удалить", command=self.delete_appointment).pack(
            side="left", padx=2)
        ttk.Button(actions, text="Подробности", command=self.show_details).pack(
            side="left", padx=2)

        ttk.Separator(actions, orient="vertical").pack(side="left", fill="y", padx=8)
        ttk.Label(actions, text="Статус:").pack(side="left")
        ttk.Combobox(actions, textvariable=self.var_new_status, values=STATUS_NAMES,
                     state="readonly", width=18).pack(side="left", padx=4)
        ttk.Button(actions, text="Изменить статус", command=self.change_status).pack(
            side="left", padx=2)

    # ------------------------------------------------- обработчики событий формы
    def on_specialty_change(self, event=None):
        """Задание 3: обновить список врачей при смене специальности."""
        doctors = DOCTORS.get(self.var_specialty.get(), [])
        self.cb_doctor["values"] = doctors
        self.var_doctor.set("")

    def complaints_length(self):
        return len(self.txt_complaints.get("1.0", "end-1c"))

    def update_counter(self):
        self.var_counter.set(f"{self.complaints_length()} / {MAX_COMPLAINT_LEN}")

    def on_complaint_keypress(self, event):
        """Задание 5: не допускаем ввод символов сверх лимита."""
        if event.state & 0x4:          # Ctrl+... (копирование и т.п.) пропускаем
            return None
        if not event.char or event.keysym in ("BackSpace", "Delete"):
            return None
        if self.txt_complaints.tag_ranges("sel"):   # выделенный текст будет заменён
            return None
        if self.complaints_length() >= MAX_COMPLAINT_LEN:
            return "break"
        return None

    def on_complaint_paste(self, event):
        """Вставка из буфера обмена с обрезкой по лимиту."""
        try:
            clip = self.root.clipboard_get()
        except tk.TclError:
            return "break"
        if self.txt_complaints.tag_ranges("sel"):
            self.txt_complaints.delete("sel.first", "sel.last")
        free = MAX_COMPLAINT_LEN - self.complaints_length()
        if free > 0:
            self.txt_complaints.insert("insert", clip[:free])
        self.update_counter()
        return "break"

    def on_complaint_change(self, event=None):
        """Страховка: если текст всё же превысил лимит, обрезаем его."""
        excess = self.complaints_length() - MAX_COMPLAINT_LEN
        if excess > 0:
            self.txt_complaints.delete(f"end-1c-{excess}c", "end-1c")
        self.update_counter()

    # ------------------------------------------------------ проверка (Задание 6)
    def validate_form(self):
        """Проверяет форму. Возвращает словарь данных или None (ошибки показаны)."""
        errors = []
        today = date.today()

        fio = " ".join(self.var_fio.get().split())
        iin = self.var_iin.get().strip()
        birth_s = self.var_birth.get().strip()
        phone = self.var_phone.get().strip()
        email = self.var_email.get().strip()
        specialty = self.var_specialty.get()
        doctor = self.var_doctor.get()
        date_s = self.var_date.get().strip()
        time_s = self.var_time.get()

        # Ф. И. О.
        if not fio:
            errors.append("Ф. И. О. не должно быть пустым.")
        elif (not all(ch.isalpha() or ch in " -'." for ch in fio)) or len(fio.split()) < 2:
            errors.append("Ф. И. О. должно состоять из букв и содержать минимум фамилию и имя.")

        # ИИН
        if not re.fullmatch(r"[0-9]{12}", iin):
            errors.append("ИИН должен содержать ровно 12 цифр.")

        # Дата рождения / возраст
        birth = parse_date(birth_s)
        if birth is None:
            errors.append("Дата рождения должна быть реальной датой в формате ДД.ММ.ГГГГ.")
        elif birth > today:
            errors.append("Дата рождения не может быть в будущем.")
        elif calc_age(birth, today) > MAX_AGE:
            errors.append(f"Возраст пациента не может превышать {MAX_AGE} лет — проверьте дату рождения.")

        # Телефон
        digits = re.sub(r"[^0-9]", "", phone)
        if not re.fullmatch(r"\+?[0-9\s\-()]+", phone) or not 10 <= len(digits) <= 15:
            errors.append("Телефон должен содержать 10–15 цифр и только допустимые символы "
                          "(цифры, пробел, «+», «-», скобки).")

        # E-mail
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            errors.append("Электронная почта должна содержать символ @ и точку в домене "
                          "(например, name@mail.kz).")

        # Врач, дата, время
        if not specialty or not doctor:
            errors.append("Выберите специальность и врача.")
        visit_date = None
        if not date_s:
            errors.append("Укажите дату приёма.")
        else:
            visit_date = parse_date(date_s)
            if visit_date is None:
                errors.append("Дата приёма должна быть реальной датой в формате ДД.ММ.ГГГГ.")
            elif visit_date < today:
                errors.append("Нельзя записаться на прошедшую дату.")
        if not time_s:
            errors.append("Выберите время приёма.")
        elif visit_date is not None and visit_date == today:
            hh, mm = map(int, time_s.split(":"))
            if datetime.combine(today, datetime.min.time()).replace(hour=hh, minute=mm) <= datetime.now():
                errors.append("Выбранное время сегодня уже прошло.")

        if errors:
            messagebox.showerror("Ошибка ввода данных",
                                 "\n".join("• " + e for e in errors), parent=self.root)
            return None

        return {
            "fio": fio, "iin": iin, "birth": birth_s, "phone": phone, "email": email,
            "specialty": specialty, "doctor": doctor, "date": date_s, "time": time_s,
            "type": self.var_type.get(), "format": self.var_format.get(),
            "complaints": self.txt_complaints.get("1.0", "end-1c").strip(),
        }

    # ------------------------------------------- занятость врача (Задание 9)
    def is_busy(self, doctor, date_s, time_s, exclude_id=None):
        """Занято ли время у врача. Отменённые записи время не занимают."""
        for r in self.records:
            if (r["doctor"] == doctor and r["date"] == date_s and r["time"] == time_s
                    and r["status"] != STATUS_CANCELLED and r["id"] != exclude_id):
                return True
        return False

    def free_times(self, doctor, date_s, exclude_id=None):
        """Список свободных времён врача на дату."""
        d = parse_date(date_s)
        result = []
        for t in TIMES:
            if self.is_busy(doctor, date_s, t, exclude_id):
                continue
            if d == date.today():
                hh, mm = map(int, t.split(":"))
                if datetime.now().replace(hour=hh, minute=mm, second=0) <= datetime.now():
                    continue
            result.append(t)
        return result

    def handle_conflict(self, data):
        """Предупреждение о занятом времени и предложение другого."""
        free = self.free_times(data["doctor"], data["date"], self.editing_id)
        head = (f"Врач «{data['doctor']}» уже занят {data['date']} в {data['time']}.\n\n")
        if not free:
            messagebox.showwarning(
                "Время занято",
                head + "На эту дату свободного времени у врача нет.\nВыберите другую дату.",
                parent=self.root)
            return
        later = [t for t in free if t > data["time"]]
        nearest = later[0] if later else free[0]
        answer = messagebox.askyesno(
            "Время занято",
            head + "Свободное время в этот день:\n" + ", ".join(free) +
            f"\n\nВыбрать ближайшее свободное время ({nearest})?",
            icon="warning", parent=self.root)
        if answer:
            self.var_time.set(nearest)

    # ---------------------------------------------------- добавление (Задание 7)
    def submit_form(self):
        data = self.validate_form()
        if data is None:
            return
        if self.is_busy(data["doctor"], data["date"], data["time"], self.editing_id):
            self.handle_conflict(data)
            return
        if self.editing_id is None:
            self.add_appointment(data)
        else:
            self.update_appointment(self.editing_id, data)

    def add_appointment(self, data):
        new_id = str(max((int(r["id"]) for r in self.records), default=0) + 1)
        record = dict(data, id=new_id, status=STATUS_PLANNED)
        self.records.append(record)
        saved = self.save_to_csv()
        self.refresh_table()
        self.select_row(new_id)
        if saved:
            messagebox.showinfo(
                "Запись оформлена",
                f"Пациент {record['fio']} записан к врачу {record['doctor']}\n"
                f"на {record['date']} в {record['time']}.", parent=self.root)
        self.clear_form()

    # --------------------------------------------------- изменение (Задание 10)
    def start_edit(self):
        rec = self.get_selected()
        if rec is None:
            return
        self.clear_form()
        self.editing_id = rec["id"]
        self.var_fio.set(rec["fio"])
        self.var_iin.set(rec["iin"])
        self.var_birth.set(rec["birth"])
        self.var_phone.set(rec["phone"])
        self.var_email.set(rec["email"])
        self.var_specialty.set(rec["specialty"])
        self.on_specialty_change()
        self.var_doctor.set(rec["doctor"])
        self.var_date.set(rec["date"])
        self.var_time.set(rec["time"])
        self.var_type.set(rec["type"] or VISIT_TYPES[0])
        self.var_format.set(rec["format"] or VISIT_FORMATS[0])
        self.txt_complaints.insert("1.0", rec["complaints"][:MAX_COMPLAINT_LEN])
        self.update_counter()
        self.btn_submit.configure(text="Сохранить изменения")
        self.btn_cancel_edit.configure(state="normal")
        self.entry_fio.focus_set()

    def update_appointment(self, rec_id, data):
        rec = self.find_record(rec_id)
        if rec is None:
            messagebox.showerror("Ошибка", "Редактируемая запись не найдена.", parent=self.root)
            self.clear_form()
            return
        rec.update(data)
        saved = self.save_to_csv()
        self.refresh_table()
        self.select_row(rec_id)
        if saved:
            messagebox.showinfo("Запись изменена", "Изменения сохранены.", parent=self.root)
        self.clear_form()

    # ---------------------------------------------- отмена / статус / удаление
    def cancel_appointment(self):
        rec = self.get_selected()
        if rec is None:
            return
        if rec["status"] == STATUS_CANCELLED:
            messagebox.showinfo("Отмена записи", "Запись уже отменена.", parent=self.root)
            return
        if messagebox.askyesno("Отмена записи",
                               f"Отменить запись пациента {rec['fio']}\n"
                               f"на {rec['date']} в {rec['time']}?", parent=self.root):
            self.set_status(rec, STATUS_CANCELLED)

    def change_status(self):
        rec = self.get_selected()
        if rec is None:
            return
        self.set_status(rec, self.var_new_status.get())

    def set_status(self, rec, new_status):
        # возвращая запись из «Отменён», проверяем, что время не заняли за это время
        if (rec["status"] == STATUS_CANCELLED and new_status != STATUS_CANCELLED
                and self.is_busy(rec["doctor"], rec["date"], rec["time"], rec["id"])):
            messagebox.showwarning(
                "Время занято",
                "Это время у врача уже занято другой записью.\n"
                "Восстановить запись нельзя — измените дату или время.", parent=self.root)
            return
        rec["status"] = new_status
        self.save_to_csv()
        self.refresh_table()
        self.select_row(rec["id"])

    def delete_appointment(self):
        rec = self.get_selected()
        if rec is None:
            return
        if not messagebox.askyesno("Удаление записи",
                                   f"Удалить запись пациента {rec['fio']}\n"
                                   f"на {rec['date']} в {rec['time']}?\n\n"
                                   "Это действие нельзя отменить.", icon="warning",
                                   parent=self.root):
            return
        self.records = [r for r in self.records if r["id"] != rec["id"]]
        if self.editing_id == rec["id"]:
            self.clear_form()
        self.save_to_csv()
        self.refresh_table()
        self.var_info.set("Запись удалена. Выберите другую запись, чтобы увидеть подробности.")

    # ---------------------------------------------------- таблица и поиск
    def find_record(self, rec_id):
        for r in self.records:
            if r["id"] == rec_id:
                return r
        return None

    def get_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Запись не выбрана",
                                   "Сначала выберите запись в таблице.", parent=self.root)
            return None
        return self.find_record(sel[0])

    def select_row(self, rec_id):
        if self.tree.exists(rec_id):
            self.tree.selection_set(rec_id)
            self.tree.focus(rec_id)
            self.tree.see(rec_id)

    def search_records(self):
        """Задание 11: отбор записей по условиям поиска и фильтрам."""
        name_q = self.var_f_name.get().strip().lower()
        iin_q = self.var_f_iin.get().strip()
        doctor_q = self.var_f_doctor.get()
        date_q = self.var_f_date.get().strip()
        status_q = self.var_f_status.get()
        result = []
        for r in self.records:
            if name_q and name_q not in r["fio"].lower():
                continue
            if iin_q and iin_q not in r["iin"]:
                continue
            if doctor_q not in ("", ALL) and r["doctor"] != doctor_q:
                continue
            if date_q and not r["date"].startswith(date_q):
                continue
            if status_q not in ("", ALL) and r["status"] != status_q:
                continue
            result.append(r)
        return sorted(result, key=sort_key)

    def refresh_table(self):
        selected = self.tree.selection()
        self.tree.delete(*self.tree.get_children())
        found = self.search_records()
        for r in found:
            self.tree.insert(
                "", "end", iid=r["id"],
                values=(r["fio"], r["doctor"], r["specialty"], r["date"], r["time"],
                        r["format"], r["status"]),
                tags=(STATUS_TAG.get(r["status"], "planned"),))
        self.var_count.set(f"Показано записей: {len(found)} из {len(self.records)}")
        if selected and self.tree.exists(selected[0]):
            self.tree.selection_set(selected[0])

    def reset_filters(self):
        self.var_f_name.set("")
        self.var_f_iin.set("")
        self.var_f_doctor.set(ALL)
        self.var_f_date.set("")
        self.var_f_status.set(ALL)
        self.refresh_table()

    def on_row_select(self, event=None):
        sel = self.tree.selection()
        rec = self.find_record(sel[0]) if sel else None
        if rec is None:
            return
        self.var_new_status.set(rec["status"])
        birth = parse_date(rec["birth"])
        age = f" ({calc_age(birth, date.today())} лет)" if birth else ""
        complaints = rec["complaints"].replace("\n", " ") or "—"
        self.var_info.set(
            f"Пациент: {rec['fio']}   ИИН: {rec['iin']}   Дата рождения: {rec['birth']}{age}\n"
            f"Телефон: {rec['phone']}   E-mail: {rec['email']}\n"
            f"Приём: {rec['type']}, {rec['format']}   Жалобы: {complaints}")

    def on_row_double_click(self, event):
        if self.tree.identify_region(event.x, event.y) == "cell":
            self.show_details()

    def show_details(self):
        """Подробности записи в отдельном окне Toplevel."""
        rec = self.get_selected()
        if rec is None:
            return
        win = tk.Toplevel(self.root)
        win.title("Подробности записи")
        win.transient(self.root)
        win.resizable(False, False)

        birth = parse_date(rec["birth"])
        age = f" ({calc_age(birth, date.today())} лет)" if birth else ""
        rows = [
            ("Пациент", rec["fio"]), ("ИИН", rec["iin"]),
            ("Дата рождения", rec["birth"] + age), ("Телефон", rec["phone"]),
            ("E-mail", rec["email"]), ("Специальность", rec["specialty"]),
            ("Врач", rec["doctor"]), ("Дата приёма", rec["date"]),
            ("Время", rec["time"]), ("Тип приёма", rec["type"]),
            ("Формат", rec["format"]), ("Статус", rec["status"]),
        ]
        body = ttk.Frame(win, padding=12)
        body.grid(row=0, column=0)
        for i, (caption, value) in enumerate(rows):
            ttk.Label(body, text=caption + ":", font=("TkDefaultFont", 10, "bold")).grid(
                row=i, column=0, sticky="nw", pady=2)
            ttk.Label(body, text=value or "—", wraplength=320, justify="left").grid(
                row=i, column=1, sticky="w", padx=(10, 0), pady=2)
        ttk.Label(body, text="Жалобы:", font=("TkDefaultFont", 10, "bold")).grid(
            row=len(rows), column=0, sticky="nw", pady=2)
        txt = tk.Text(body, width=40, height=5, wrap="word")
        txt.grid(row=len(rows), column=1, padx=(10, 0), pady=2)
        txt.insert("1.0", rec["complaints"] or "—")
        txt.configure(state="disabled")
        ttk.Button(body, text="Закрыть", command=win.destroy).grid(
            row=len(rows) + 1, column=0, columnspan=2, pady=(10, 0))
        win.grab_set()

    # ------------------------------------------------------------ очистка формы
    def clear_form(self):
        for var in (self.var_fio, self.var_iin, self.var_birth, self.var_phone,
                    self.var_email, self.var_specialty, self.var_doctor,
                    self.var_date, self.var_time):
            var.set("")
        self.cb_doctor["values"] = []
        self.var_type.set(VISIT_TYPES[0])
        self.var_format.set(VISIT_FORMATS[0])
        self.txt_complaints.delete("1.0", "end")
        self.update_counter()
        self.editing_id = None
        self.btn_submit.configure(text="Записаться на приём")
        self.btn_cancel_edit.configure(state="disabled")

    # ---------------------------------------------- сохранение и загрузка CSV
    def save_to_csv(self):
        """Запись всех записей в CSV через временный файл (данные не теряются при сбое)."""
        tmp = CSV_FILE + ".tmp"
        try:
            with open(tmp, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, delimiter=";")
                writer.writeheader()
                writer.writerows(self.records)
            os.replace(tmp, CSV_FILE)
            return True
        except (OSError, csv.Error) as err:
            messagebox.showerror("Ошибка сохранения",
                                 f"Не удалось сохранить данные в файл:\n{CSV_FILE}\n\n{err}",
                                 parent=self.root)
            return False

    def load_from_csv(self):
        """Загрузка записей при запуске программы."""
        if not os.path.exists(CSV_FILE):
            return
        try:
            loaded = []
            with open(CSV_FILE, newline="", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f, delimiter=";")
                for row in reader:
                    rec = {k: (row.get(k) or "") for k in CSV_FIELDS}
                    if rec["status"] not in STATUS_NAMES:
                        rec["status"] = STATUS_PLANNED
                    loaded.append(rec)
            for i, rec in enumerate(loaded, start=1):   # гарантируем уникальные id
                rec["id"] = str(i)
            self.records = loaded
        except (OSError, csv.Error, UnicodeDecodeError) as err:
            backup = CSV_FILE + ".bak"
            note = ""
            try:
                with open(CSV_FILE, "rb") as src, open(backup, "wb") as dst:
                    dst.write(src.read())
                note = f"\n\nКопия повреждённого файла сохранена:\n{backup}"
            except OSError:
                pass
            messagebox.showerror("Ошибка загрузки",
                                 f"Не удалось прочитать файл данных:\n{CSV_FILE}\n\n{err}{note}",
                                 parent=self.root)


def main():
    root = tk.Tk()
    AppointmentApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
