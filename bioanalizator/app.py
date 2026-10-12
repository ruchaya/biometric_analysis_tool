from PIL import Image

from .common import *  # noqa: F401,F403
from .core import BiometricAnalysis
from .tables import PagedTable


class BiometricApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.analyzer = BiometricAnalysis()
        self.column_combos = {}
        self.current_fig = None
        self.current_canvas = None

        # Инфраструктура фоновых задач
        self._task_queue = queue.Queue()
        self._busy = False
        self._cancel_event = threading.Event()
        self.analyzer.cancel_check = self._raise_if_cancelled

        self.setup_ui()

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(80, self._poll_tasks)
        logger.info("Приложение запущено")

    # --- фоновые задачи --------------------------------------------------------
    def run_task(self, func, on_success=None, on_error=None, description="Выполняется…"):
        """Запускает func в отдельном потоке, не блокируя интерфейс.

        Результат и ошибка возвращаются в главный поток через очередь и
        вызываются как on_success(result) / on_error(exception).
        """
        if self._busy:
            messagebox.showwarning(
                "Подождите", "Дождитесь завершения текущей операции."
            )
            return

        self._busy = True
        self._cancel_event.clear()
        self._set_busy(True, description)
        logger.info("Начало операции: %s", description)

        def worker():
            try:
                self._raise_if_cancelled()
                result = func()
                self._raise_if_cancelled()
            except TaskCancelled:
                logger.info("Операция отменена: %s", description)
                self._task_queue.put(("cancelled", None, None, description))
            except Exception as exc:  # noqa: BLE001 - пробрасываем в GUI
                logger.exception("Операция завершилась ошибкой: %s", description)
                self._task_queue.put(("error", exc, on_error, description))
            else:
                logger.info("Операция завершена: %s", description)
                self._task_queue.put(("ok", result, on_success, description))

        threading.Thread(target=worker, daemon=True).start()

    def _raise_if_cancelled(self):
        if self._cancel_event.is_set():
            raise TaskCancelled()

    def cancel_task(self):
        """Запрашивает отмену текущей фоновой операции (кооперативно)."""
        if self._busy:
            logger.info("Запрошена отмена операции")
            self._cancel_event.set()
            self.busy_label.configure(text="⏳ Отмена…")

    def _poll_tasks(self):
        try:
            while True:
                kind, payload, callback, description = self._task_queue.get_nowait()
                self._busy = False
                self._set_busy(False)

                if kind == "ok":
                    if callback is not None:
                        callback(payload)
                elif kind == "cancelled":
                    messagebox.showinfo("Отменено", f"Операция отменена: {description}")
                elif callback is not None:
                    callback(payload)
                else:
                    messagebox.showerror("Ошибка", f"{description}\n\n{payload}")
        except queue.Empty:
            pass
        except Exception:
            logger.exception("Ошибка обработки результата фоновой задачи")

        try:
            if self.winfo_exists():
                self.after(80, self._poll_tasks)
        except Exception:
            # Окно уже закрыто — останавливаем опрос очереди
            pass

    def _set_busy(self, busy, description=""):
        if busy:
            self.busy_label.configure(text=f"⏳ {description}")
            if not self.busy_frame.winfo_manager():
                self.busy_frame.pack(side="right", padx=10)
            self.progress.start()
        else:
            self.progress.stop()
            self.busy_frame.pack_forget()

    def _on_close(self):
        logger.info("Приложение закрыто")
        for handler in logger.handlers:
            try:
                handler.flush()
            except Exception:
                pass
        self.destroy()

    def export_log(self):
        """Сохраняет файл журнала в выбранное пользователем место."""
        for handler in logger.handlers:
            try:
                handler.flush()
            except Exception:
                pass

        if not LOG_FILE_PATH or not os.path.exists(LOG_FILE_PATH):
            messagebox.showwarning("Журнал", "Файл журнала не найден.")
            return

        dest = filedialog.asksaveasfilename(
            defaultextension=".log",
            filetypes=[("Log files", "*.log"), ("Text files", "*.txt"), ("All files", "*.*")],
            initialfile=f"bioanalizator_{pd.Timestamp.now().strftime('%Y-%m-%d_%H-%M')}.log",
        )
        if not dest:
            return

        try:
            shutil.copyfile(LOG_FILE_PATH, dest)
            logger.info("Журнал экспортирован: %s", dest)
            messagebox.showinfo("Успех", f"Журнал сохранён в {dest}")
        except Exception as exc:
            logger.exception("Не удалось экспортировать журнал")
            messagebox.showerror("Ошибка", f"Не удалось сохранить журнал:\n{exc}")

    
    def setup_ui(self):
        self.title(f"📊 {APP_NAME} v{APP_VERSION}")
        self.geometry("1400x900")

        # Иконка окна/панели задач (в собранном exe берётся из ресурсов)
        try:
            icon = resource_path(ICON_RELATIVE)
            if os.path.exists(icon):
                self.iconbitmap(icon)
        except Exception:
            logger.debug("Не удалось установить иконку окна", exc_info=True)

        self.create_menu()
        
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=20, pady=20)
        
        self.tab1 = self.tabview.add("Загрузка данных")
        self.tab2 = self.tabview.add("Обзор данных")
        self.tab3 = self.tabview.add("Биометрические индексы")
        self.tab4 = self.tabview.add("Графики")
        self.tab5 = self.tabview.add("Результаты")
        
        self.setup_tab1()
        self.setup_tab2()
        self.setup_tab3()
        self.setup_tab4()
        self.setup_tab5()
    
    def create_menu(self):
        menu_frame = ctk.CTkFrame(self, height=40)
        menu_frame.pack(fill="x", padx=20, pady=(10, 0))
        menu_frame.pack_propagate(False)

        # Логотип
        try:
            logo_path = resource_path(LOGO_RELATIVE)
            if os.path.exists(logo_path):
                logo_img = Image.open(logo_path)
                self.logo_image = ctk.CTkImage(
                    light_image=logo_img, dark_image=logo_img, size=(30, 30)
                )
                ctk.CTkLabel(menu_frame, image=self.logo_image, text="").pack(
                    side="left", padx=(10, 4), pady=2
                )
        except Exception:
            logger.debug("Не удалось загрузить логотип", exc_info=True)

        instruction_btn = ctk.CTkButton(
            menu_frame, 
            text="📖 Инструкция", 
            command=self.show_instructions,
            width=120,
            height=30
        )
        instruction_btn.pack(side="left", padx=10, pady=5)

        export_log_btn = ctk.CTkButton(
            menu_frame,
            text="📄 Сохранить журнал",
            command=self.export_log,
            width=150,
            height=30,
        )
        export_log_btn.pack(side="left", padx=10, pady=5)

        theme_btn = ctk.CTkButton(
            menu_frame,
            text="🌓 Тема",
            command=self.toggle_theme,
            width=90,
            height=30,
        )
        theme_btn.pack(side="left", padx=10, pady=5)

        # Индикатор выполнения фоновой задачи (скрыт по умолчанию)
        self.busy_frame = ctk.CTkFrame(menu_frame, fg_color="transparent")
        self.busy_label = ctk.CTkLabel(self.busy_frame, text="")
        self.busy_label.pack(side="left", padx=(0, 8))
        self.progress = ctk.CTkProgressBar(self.busy_frame, mode="indeterminate", width=140)
        self.progress.pack(side="left")
        self.cancel_btn = ctk.CTkButton(
            self.busy_frame, text="Отмена", width=70, command=self.cancel_task,
            fg_color="#d9534f", hover_color="#c9302c",
        )
        self.cancel_btn.pack(side="left", padx=(8, 0))

    def toggle_theme(self):
        """Переключает светлую/тёмную тему."""
        current = ctk.get_appearance_mode()
        ctk.set_appearance_mode("Light" if current == "Dark" else "Dark")
        logger.info("Тема переключена на %s", ctk.get_appearance_mode())
    
    def show_instructions(self):
        instructions = f"""
{APP_NAME} — версия {APP_VERSION}
Автор: {APP_AUTHOR}

ИНСТРУКЦИЯ ПО ИСПОЛЬЗОВАНИЮ ПРОГРАММЫ

1. ЗАГРУЗКА ДАННЫХ
   - Нет данных? Нажмите "Скачать шаблон Excel" и заполните таблицу
   - На вкладке "Загрузка данных" выберите Excel или CSV файл с данными
   - Программа автоматически определит названия колонок

2. НАСТРОЙКА КОЛОНОК И РАСЧЕТ
   - Перейдите на вкладку "Биометрические индексы"
   - Укажите соответствие колонок
   - Выберите длину для индекса Фультона: промысловую или общую
   - Для регрессии выберите переменные X и Y (по умолчанию Длина -> Вес)
   - Нажмите "Рассчитать индексы"

3. ОБЗОР И АНАЛИЗ
   - Просматривайте данные на вкладках "Обзор данных" и "Результаты"
   - В таблицах доступны: поиск (по всем колонкам или по выбранной),
     сортировка (клик по заголовку) и постраничный вывод
   - Строите графики на вкладке "Графики"; для типа
     "Произвольный график (X–Y)" выберите свои X и Y

4. РАССЧИТЫВАЕМЫЕ ИНДЕКСЫ:
   - Индекс Фультона: (Вес / Длина³) × 100, где длина - выбранная
     (по умолчанию промысловая; можно переключить на общую)
   - Индекс физического развития: (Вес × Промысловая длина) / 100
   - Относительный вес: (Вес / Промысловая длина) × 1000
   - Длинноголовость: (Длина головы / Промысловая длина) × 100 (если есть данные)
   - Прогонистость: (Промысловая длина / Наибольшая высота) × 100 (если есть данные)

5. СТАТИСТИКА:
   - Сводная статистика: размах, среднее, медиана, ст.отклонение, CV,
     95% доверительный интервал и квартили
   - "По группам" - та же статистика отдельно по полу и примечанию
   - "Сравнение групп" - t-тест Уэлча / Манн–Уитни (2 группы) или
     ANOVA / Краскела–Уоллиса (больше), с поправкой на множественные
     сравнения (Benjamini–Hochberg)
   - "Отброшенные строки" - какие строки исключены и почему

6. РЕГРЕССИИ И КОРРЕЛЯЦИИ:
   - Степенная регрессия y = a·x^b считается в лог-лог координатах
   - Для наклона b приводятся стандартная ошибка, 95% доверительный интервал
     и p-value; для длина-масса дополнительно p-value наклона против b=3
   - Результат кэшируется и не пересчитывается повторно
   - На графике линия тренда строится по той же степенной модели;
     можно включить 95% доверительную область
   - Вкладка "Результаты" содержит коэффициенты регрессии и корреляционную
     матрицу со значимостью: * p<0.05, ** p<0.01, *** p<0.001
   - Тип графика "Корреляционная матрица" строит тепловую карту

ПРИМЕЧАНИЯ:
• Для расчета необходимы колонки с весом и промысловой длиной
• Результаты можно сохранить в Excel файл (много листов)
• Длительные операции выполняются в фоне; их можно отменить кнопкой "Отмена"
• Кнопка "Тема" переключает светлую/тёмную тему интерфейса
• Все действия пишутся в журнал (log-файл). Кнопка "Сохранить журнал"
  позволяет экспортировать его в выбранное место
        """
        
        instruction_window = ctk.CTkToplevel(self)
        instruction_window.title("Инструкция по использованию программы")
        instruction_window.geometry("800x600")
        instruction_window.transient(self)
        instruction_window.grab_set()
        
        text_widget = ctk.CTkTextbox(instruction_window, wrap="word")
        text_widget.pack(fill="both", expand=True, padx=20, pady=20)
        text_widget.insert("1.0", instructions)
        text_widget.configure(state="disabled")
        
        close_btn = ctk.CTkButton(
            instruction_window, 
            text="Закрыть", 
            command=instruction_window.destroy
        )
        close_btn.pack(pady=10)
    
    def setup_tab1(self):
        left_frame = ctk.CTkFrame(self.tab1)
        left_frame.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        
        ctk.CTkLabel(left_frame, text="📁 Загрузка данных", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)

        ctk.CTkLabel(left_frame, text="Файл данных (Excel или CSV)").pack(anchor="w", pady=(10,5))
        self.load_btn = ctk.CTkButton(left_frame, text="Выбрать файл…", command=self.load_file)
        self.load_btn.pack(fill="x", pady=5)

        ctk.CTkLabel(left_frame, text="Или укажите путь к файлу:").pack(anchor="w", pady=(10,5))
        self.file_path_entry = ctk.CTkEntry(left_frame, placeholder_text="C:/путь/к/файлу.xlsx")
        self.file_path_entry.pack(fill="x", pady=5)
        self.file_path_entry.bind(
            "<FocusOut>", lambda _e: self.update_sheet_list(self.file_path_entry.get().strip())
        )

        ctk.CTkLabel(left_frame, text="Лист Excel (для .xlsx/.xls):").pack(anchor="w", pady=(10,5))
        self.sheet_var = ctk.StringVar(value="")
        self.sheet_combo = ctk.CTkComboBox(left_frame, variable=self.sheet_var, values=[""])
        self.sheet_combo.pack(fill="x", pady=5)

        self.load_data_btn = ctk.CTkButton(left_frame, text="Загрузить данные", command=self.process_load_data)
        self.load_data_btn.pack(fill="x", pady=20)

        self.template_btn = ctk.CTkButton(
            left_frame, text="📥 Скачать шаблон Excel",
            command=self.download_excel_template,
        )
        self.template_btn.pack(fill="x", pady=(0, 5))

        ctk.CTkLabel(
            left_frame, text="Профиль сопоставления колонок:",
            font=ctk.CTkFont(weight="bold"),
        ).pack(anchor="w", pady=(10,5))
        profile_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
        profile_frame.pack(fill="x")
        ctk.CTkButton(
            profile_frame, text="💾 Сохранить", command=self.save_mapping_profile
        ).pack(side="left", fill="x", expand=True, padx=(0,4))
        ctk.CTkButton(
            profile_frame, text="📂 Загрузить", command=self.load_mapping_profile
        ).pack(side="left", fill="x", expand=True, padx=(4,0))
        
        right_frame = ctk.CTkFrame(self.tab1)
        right_frame.pack(side="right", fill="both", expand=True, padx=10, pady=10)
        
        ctk.CTkLabel(right_frame, text="Статус загрузки", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)
        
        self.status_text = ctk.CTkTextbox(right_frame, height=300)
        self.status_text.pack(fill="both", expand=True, pady=10)
        
        ctk.CTkLabel(right_frame, text="Автоматически найденные колонки:", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(10,5))
        
        self.columns_text = ctk.CTkTextbox(right_frame, height=200)
        self.columns_text.pack(fill="both", expand=True, pady=10)
    
    def setup_tab2(self):
        self.tab2_frame = ctk.CTkFrame(self.tab2)
        self.tab2_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        ctk.CTkLabel(self.tab2_frame, text="📋 Обзор данных", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)
        
        info_frame = ctk.CTkFrame(self.tab2_frame)
        info_frame.pack(fill="x", pady=10)
        
        self.data_info_label = ctk.CTkLabel(info_frame, text="Данные не загружены", font=ctk.CTkFont(weight="bold"))
        self.data_info_label.pack(pady=10)
        
        self.create_data_table()
    
    def create_data_table(self):
        frame = ctk.CTkFrame(self.tab2_frame)
        frame.pack(fill="both", expand=True, pady=10)

        self.data_table = PagedTable(frame, page_size=100, min_col_width=80, formatter=format_raw)
        self.data_tree = self.data_table.tree

        refresh_btn = ctk.CTkButton(frame, text="Обновить данные", command=self.update_data_table)
        refresh_btn.pack(pady=5)
    
    def setup_tab3(self):
        main_frame = ctk.CTkFrame(self.tab3)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        left_frame = ctk.CTkFrame(main_frame, width=400)
        left_frame.pack(side="left", fill="both", padx=(0,10), pady=10)
        
        canvas = ctk.CTkCanvas(left_frame, highlightthickness=0)
        scrollbar = ctk.CTkScrollbar(left_frame, orientation="vertical", command=canvas.yview)
        scrollable_frame = ctk.CTkFrame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        ctk.CTkLabel(scrollable_frame, text="Настройки анализа", font=ctk.CTkFont(size=14, weight="bold")).pack(pady=10)
        
        column_options = [""]
        
        self.column_vars = {}
        columns_config = [
            ('number_col', 'Колонка №:'),
            ('chip_col', 'Колонка № чипа:'),
            ('tube_col', 'Колонка № пробирки:'),
            ('weight_col', 'Колонка Вес, г:'),
            ('total_length_col', 'Колонка Длина, см:'),
            ('fishing_length_col', 'Колонка Промыс.длина, см:'),
            ('head_length_col', 'Колонка Длина гол., см:'),
            ('girth_col', 'Колонка Обхват, см:'),
            ('body_height_col', 'Колонка Наиб. Высота, см:'),
            ('dorsal_rays_col', 'Колонка Кол-во лучей в СП:'),
            ('anal_rays_col', 'Колонка Кол-во лучей в АП:'),
            ('notes_col', 'Колонка Примечание:'),
            ('sex_col', 'Колонка Пол:'),
        ]
        
        for key, label in columns_config:
            ctk.CTkLabel(scrollable_frame, text=label).pack(anchor="w", pady=(5,0))
            var = ctk.StringVar(value="")
            combo = ctk.CTkComboBox(scrollable_frame, variable=var, values=column_options)
            combo.pack(fill="x", pady=(0,10))
            self.column_vars[key] = var
            self.column_combos[key] = combo

        ctk.CTkLabel(
            scrollable_frame, text="Длина для индекса Фультона:",
            font=ctk.CTkFont(weight="bold"),
        ).pack(anchor="w", pady=(10, 0))
        self.fulton_basis_var = ctk.StringVar(value="Промысловая")
        self.fulton_basis_combo = ctk.CTkOptionMenu(
            scrollable_frame, variable=self.fulton_basis_var, values=["Промысловая", "Общая"]
        )
        self.fulton_basis_combo.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(
            scrollable_frame, text="Регрессия X → Y:",
            font=ctk.CTkFont(weight="bold"),
        ).pack(anchor="w", pady=(5, 0))
        self.regression_x_var = ctk.StringVar(value="")
        self.regression_y_var = ctk.StringVar(value="")
        self.regression_x_combo = ctk.CTkComboBox(
            scrollable_frame, variable=self.regression_x_var, values=[""]
        )
        self.regression_x_combo.pack(fill="x", pady=(2, 4))
        self.regression_y_combo = ctk.CTkComboBox(
            scrollable_frame, variable=self.regression_y_var, values=[""]
        )
        self.regression_y_combo.pack(fill="x", pady=(0, 10))

        self.calculate_btn = ctk.CTkButton(scrollable_frame, text="Рассчитать индексы", command=self.calculate_indices)
        self.calculate_btn.pack(fill="x", pady=10)
        
        self.reset_btn = ctk.CTkButton(scrollable_frame, text="Сбросить данные", command=self.reset_data, fg_color="#d9534f", hover_color="#c9302c")
        self.reset_btn.pack(fill="x", pady=10)
        
        right_frame = ctk.CTkFrame(main_frame)
        right_frame.pack(side="right", fill="both", expand=True, pady=10)
        
        ctk.CTkLabel(right_frame, text="Результаты расчета", font=ctk.CTkFont(size=14, weight="bold")).pack(pady=10)
        
        self.results_info = ctk.CTkTextbox(right_frame, height=100)
        self.results_info.pack(fill="x", pady=10)
        
        self.create_results_table(right_frame)
    
    def create_results_table(self, parent):
        self.results_table = PagedTable(parent, page_size=50, min_col_width=100)
        self.results_tree = self.results_table.tree
    
    def setup_tab4(self):
        main_frame = ctk.CTkFrame(self.tab4)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        left_frame = ctk.CTkFrame(main_frame, width=300)
        left_frame.pack(side="left", fill="y", padx=(0,10), pady=10)
        left_frame.pack_propagate(False)
        
        ctk.CTkLabel(left_frame, text="Настройки графиков", font=ctk.CTkFont(size=14, weight="bold")).pack(pady=10)
        
        ctk.CTkLabel(left_frame, text="Тип графика:").pack(anchor="w", pady=(10,5))
        self.plot_type_var = ctk.StringVar(value="Длина-Живая масса")
        plot_types = [
            "Длина-Живая масса",
            "Индекс Фультона", 
            "Индекс физического развития",
            "Относительный вес",
            "Длинноголовость",
            "Прогонистость",
            "Корреляционная матрица",
            "Произвольный график (X–Y)",
        ]
        self.plot_type_combo = ctk.CTkComboBox(left_frame, variable=self.plot_type_var, values=plot_types)
        self.plot_type_combo.pack(fill="x", pady=5)
        
        self.by_sex_var = ctk.BooleanVar(value=False)
        self.by_sex_cb = ctk.CTkCheckBox(left_frame, text="По полу", variable=self.by_sex_var)
        self.by_sex_cb.pack(anchor="w", pady=5)
        
        self.by_groups_var = ctk.BooleanVar(value=False)
        self.by_groups_cb = ctk.CTkCheckBox(left_frame, text="По группам", variable=self.by_groups_var)
        self.by_groups_cb.pack(anchor="w", pady=5)
        
        self.trendline_var = ctk.BooleanVar(value=True)
        self.trendline_cb = ctk.CTkCheckBox(left_frame, text="Показать линию тренда", variable=self.trendline_var)
        self.trendline_cb.pack(anchor="w", pady=5)

        self.ci_var = ctk.BooleanVar(value=True)
        self.ci_cb = ctk.CTkCheckBox(left_frame, text="95% доверительная область", variable=self.ci_var)
        self.ci_cb.pack(anchor="w", pady=5)

        ctk.CTkLabel(left_frame, text="X и Y (для произвольного):").pack(anchor="w", pady=(10, 0))
        self.custom_x_var = ctk.StringVar(value="")
        self.custom_y_var = ctk.StringVar(value="")
        self.custom_x_combo = ctk.CTkComboBox(left_frame, variable=self.custom_x_var, values=[""])
        self.custom_x_combo.pack(fill="x", pady=(2, 4))
        self.custom_y_combo = ctk.CTkComboBox(left_frame, variable=self.custom_y_var, values=[""])
        self.custom_y_combo.pack(fill="x", pady=(0, 6))
        
        ctk.CTkLabel(left_frame, text="Размер точек:").pack(anchor="w", pady=(10,5))
        self.point_size_var = ctk.IntVar(value=2)
        self.point_size_slider = ctk.CTkSlider(left_frame, from_=1, to=5, variable=self.point_size_var)
        self.point_size_slider.pack(fill="x", pady=5)
        
        self.create_plot_btn = ctk.CTkButton(left_frame, text="Создать график", command=self.create_plot)
        self.create_plot_btn.pack(fill="x", pady=20)
        
        self.download_plot_btn = ctk.CTkButton(left_frame, text="Скачать график", command=self.download_plot, state="disabled")
        self.download_plot_btn.pack(fill="x", pady=5)
        
        right_frame = ctk.CTkFrame(main_frame)
        right_frame.pack(side="right", fill="both", expand=True, pady=10)
        
        ctk.CTkLabel(right_frame, text="График", font=ctk.CTkFont(size=14, weight="bold")).pack(pady=10)
        
        self.plot_frame = ctk.CTkFrame(right_frame)
        self.plot_frame.pack(fill="both", expand=True, pady=10)
    
    def setup_tab5(self):
        main_frame = ctk.CTkFrame(self.tab5)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        ctk.CTkLabel(main_frame, text="📊 Результаты", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)
        
        button_frame = ctk.CTkFrame(main_frame)
        button_frame.pack(fill="x", pady=10)
        
        self.save_results_btn = ctk.CTkButton(button_frame, text="Сохранить все результаты", command=self.save_all_results)
        self.save_results_btn.pack(side="left", padx=5)
        
        self.download_excel_btn = ctk.CTkButton(button_frame, text="Скачать Excel файл", command=self.download_excel)
        self.download_excel_btn.pack(side="left", padx=5)
        
        self.reset_results_btn = ctk.CTkButton(button_frame, text="Сбросить данные", command=self.reset_data, fg_color="#d9534f", hover_color="#c9302c")
        self.reset_results_btn.pack(side="left", padx=5)
        
        results_tabview = ctk.CTkTabview(main_frame)
        results_tabview.pack(fill="both", expand=True, pady=10)
        
        self.stats_tab = results_tabview.add("Сводная статистика")
        self.group_tab = results_tabview.add("По группам")
        self.compare_tab = results_tabview.add("Сравнение групп")
        self.regression_tab = results_tabview.add("Коэффициенты регрессии")
        self.corr_tab = results_tabview.add("Корреляционная матрица")
        self.rejected_tab = results_tabview.add("Отброшенные строки")
        
        self.create_stats_table()
        self.create_group_table()
        self.create_compare_table()
        self.create_regression_table()
        self.create_corr_table()
        self.create_rejected_table()
    
    def create_stats_table(self):
        self.stats_table = PagedTable(self.stats_tab, page_size=50, min_col_width=120)
        self.stats_tree = self.stats_table.tree

    def create_group_table(self):
        self.group_table = PagedTable(self.group_tab, page_size=50, min_col_width=90)
        self.group_tree = self.group_table.tree

    def create_compare_table(self):
        self.compare_table = PagedTable(
            self.compare_tab, page_size=50, min_col_width=90, formatter=format_regression
        )
        self.compare_tree = self.compare_table.tree

    def create_regression_table(self):
        self.regression_table = PagedTable(
            self.regression_tab, page_size=50, min_col_width=80, formatter=format_regression
        )
        self.regression_tree = self.regression_table.tree

    def create_corr_table(self):
        self.corr_table = PagedTable(self.corr_tab, page_size=50, min_col_width=90)
        self.corr_tree = self.corr_table.tree

    def create_rejected_table(self):
        self.rejected_table = PagedTable(
            self.rejected_tab, page_size=50, min_col_width=90, formatter=format_raw
        )
        self.rejected_tree = self.rejected_table.tree
    
    def reset_data(self):
        if messagebox.askyesno("Подтверждение", "Вы уверены, что хотите сбросить все данные? Все текущие расчеты будут потеряны."):
            self.analyzer = BiometricAnalysis()
            self.analyzer.cancel_check = self._raise_if_cancelled

            self.status_text.delete("1.0", "end")
            self.columns_text.delete("1.0", "end")
            self.results_info.delete("1.0", "end")
            
            self.data_table.set_data(None)
            self.results_table.set_data(None)
            self.stats_table.set_data(None)
            self.group_table.set_data(None)
            self.compare_table.set_data(None)
            self.regression_table.set_data(None)
            self.corr_table.set_data(None)
            self.rejected_table.set_data(None)

            for var in self.column_vars.values():
                var.set("")

            self._discard_current_plot()

            self.data_info_label.configure(text="Данные не загружены")

            messagebox.showinfo("Успех", "Все данные сброшены. Вы можете начать новый анализ.")
    
    def load_file(self):
        file_path = filedialog.askopenfilename(
            title="Выберите файл данных",
            filetypes=[
                ("Данные", "*.xlsx *.xls *.csv"),
                ("Excel", "*.xlsx *.xls"),
                ("CSV", "*.csv"),
                ("Все файлы", "*.*"),
            ],
        )
        if file_path:
            self.file_path_entry.delete(0, "end")
            self.file_path_entry.insert(0, file_path)
            self.update_sheet_list(file_path)

    def update_sheet_list(self, file_path):
        """Заполняет список листов, если выбран Excel-файл."""
        if not file_path or not os.path.exists(file_path):
            return
        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".csv":
            self.sheet_combo.configure(values=["—"])
            self.sheet_var.set("—")
            return
        sheets = self.analyzer.list_excel_sheets(file_path)
        self.sheet_combo.configure(values=sheets or [""])
        if sheets:
            self.sheet_var.set(sheets[0])
        else:
            self.sheet_var.set("")

    def process_load_data(self):
        file_path = self.file_path_entry.get().strip()

        if not file_path:
            messagebox.showwarning("Предупреждение", "Пожалуйста, укажите путь к файлу")
            return

        ext = os.path.splitext(file_path)[1].lower()
        sheet_name = None
        if ext != ".csv":
            sheet_name = self.sheet_var.get()
            if not sheet_name or sheet_name == "—":
                sheets = self.analyzer.list_excel_sheets(file_path)
                sheet_name = sheets[0] if sheets else None

        logger.info("Запрошена загрузка данных: %s (лист: %s)", file_path, sheet_name)
        self.run_task(
            lambda: self.analyzer.load_data(file_path=file_path, sheet_name=sheet_name),
            on_success=self._on_data_loaded,
            description="Загрузка данных",
        )

    def _profile_options(self):
        return {
            'fulton_length': 'total' if self.fulton_basis_var.get() == "Общая" else 'fishing',
            'regression_x': self.regression_x_var.get() or None,
            'regression_y': self.regression_y_var.get() or None,
        }

    def save_mapping_profile(self):
        if self.analyzer.data is None:
            messagebox.showwarning("Профиль", "Сначала загрузите данные.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("Профиль (JSON)", "*.json"), ("Все файлы", "*.*")],
            initialfile="профиль_колонок.json",
        )
        if not path:
            return
        try:
            mapping = {key: var.get() for key, var in self.column_vars.items()}
            save_profile(path, mapping, self._profile_options())
            logger.info("Профиль сохранён: %s", path)
            messagebox.showinfo("Профиль", f"Профиль сохранён в {path}")
        except Exception as exc:
            logger.exception("Не удалось сохранить профиль")
            messagebox.showerror("Ошибка", f"Не удалось сохранить профиль:\n{exc}")

    def load_mapping_profile(self):
        path = filedialog.askopenfilename(
            filetypes=[("Профиль (JSON)", "*.json"), ("Все файлы", "*.*")]
        )
        if not path:
            return
        try:
            mapping, options = load_profile(path)
        except Exception as exc:
            logger.exception("Не удалось прочитать профиль")
            messagebox.showerror("Ошибка", f"Не удалось прочитать профиль:\n{exc}")
            return

        available = set()
        if self.analyzer.data is not None:
            available = {str(c) for c in self.analyzer.data.columns}

        applied = 0
        for key, value in mapping.items():
            if key not in self.column_vars or not value:
                continue
            if available and str(value) not in available:
                logger.info("Профиль: колонка '%s' отсутствует в данных, пропущена", value)
                continue
            self.column_vars[key].set(str(value))
            applied += 1

        fulton = options.get('fulton_length')
        if fulton == 'total':
            self.fulton_basis_var.set("Общая")
        elif fulton == 'fishing':
            self.fulton_basis_var.set("Промысловая")

        numeric = set()
        if self.analyzer.data is not None:
            numeric = {
                str(c) for c in self.analyzer.data.columns
                if pd.api.types.is_numeric_dtype(self.analyzer.data[c])
            }
        for opt_key, var in (('regression_x', self.regression_x_var),
                             ('regression_y', self.regression_y_var)):
            value = options.get(opt_key)
            if value and (not numeric or str(value) in numeric):
                var.set(str(value))

        logger.info("Профиль загружен: %s (применено полей: %d)", path, applied)
        messagebox.showinfo("Профиль", f"Профиль загружен. Применено полей: {applied}")

    def _on_data_loaded(self, _result):
        self.status_text.delete("1.0", "end")
        self.status_text.insert(
            "1.0",
            f"Данные успешно загружены!\n\nРазмер: "
            f"{self.analyzer.data.shape[0]} строк × {self.analyzer.data.shape[1]} колонок",
        )

        self.update_columns_info()
        self.update_column_comboboxes()
        self.update_data_table()

        messagebox.showinfo("Успех", "Данные успешно загружены!")
    
    def detect_columns(self):
        """Автоопределение колонок: возвращает {внутреннее_поле: колонка|None}."""
        if self.analyzer.data is None:
            return {key: None for key, _ in COLUMN_FIELD_LABELS}

        detected = {}
        for key, _label in COLUMN_FIELD_LABELS:
            pattern, exclude = COLUMN_DETECTION[key]
            detected[key] = self.analyzer.find_column(pattern, self.analyzer.data, exclude=exclude)
        return detected

    def update_columns_info(self):
        self.columns_text.delete("1.0", "end")

        detected = self.detect_columns()
        self.detected_columns = detected

        for key, label in COLUMN_FIELD_LABELS:
            found_col = detected.get(key)
            if found_col:
                self.columns_text.insert("end", f"✓ {label}: {found_col}\n")
            else:
                self.columns_text.insert("end", f"✗ {label}: не найдена\n")

    def update_column_comboboxes(self):
        if self.analyzer.data is None:
            return

        column_options = [""] + [str(c) for c in self.analyzer.data.columns]
        detected = getattr(self, 'detected_columns', None) or self.detect_columns()

        for key, combo in self.column_combos.items():
            combo.configure(values=column_options)
            var = self.column_vars[key]
            current = var.get()
            # Сохраняем уже выбранное/загруженное из профиля значение
            if current and current in column_options:
                continue
            found_col = detected.get(key)
            if found_col is not None and str(found_col) in column_options:
                var.set(str(found_col))
            elif current not in column_options:
                var.set("")

        # Числовые колонки для выбора осей регрессии и произвольного графика
        numeric_cols = [
            c for c in self.analyzer.data.columns
            if pd.api.types.is_numeric_dtype(self.analyzer.data[c])
        ]
        numeric_cols = [str(c) for c in numeric_cols]
        if not numeric_cols:
            numeric_cols = column_options[1:]

        for combo in (self.regression_x_combo, self.regression_y_combo,
                      self.custom_x_combo, self.custom_y_combo):
            combo.configure(values=numeric_cols)

        # Значения по умолчанию - по результатам автоопределения колонок
        detected_x = detected.get('total_length_col') or detected.get('fishing_length_col')
        detected_y = detected.get('weight_col')
        default_x = str(detected_x) if detected_x is not None and str(detected_x) in numeric_cols \
            else self._default_numeric(numeric_cols, ["длина", "length"])
        default_y = str(detected_y) if detected_y is not None and str(detected_y) in numeric_cols \
            else self._default_numeric(numeric_cols, ["вес", "weight"])

        if default_x and self.regression_x_var.get() not in numeric_cols:
            self.regression_x_var.set(default_x)
        if default_y and self.regression_y_var.get() not in numeric_cols:
            self.regression_y_var.set(default_y)
        if numeric_cols:
            if self.custom_x_var.get() not in numeric_cols:
                self.custom_x_var.set(default_x or numeric_cols[0])
            if self.custom_y_var.get() not in numeric_cols:
                self.custom_y_var.set(default_y or numeric_cols[-1])

    @staticmethod
    def _default_numeric(numeric_cols, hints):
        """Первый числовой столбец, в названии которого встречается подсказка."""
        for col in numeric_cols:
            low = col.lower()
            if any(h in low for h in hints):
                return col
        return numeric_cols[0] if numeric_cols else ""

    def update_data_table(self):
        if self.analyzer.data is None:
            self.data_info_label.configure(text="Данные не загружены")
            self.data_table.set_data(None)
            return

        self.data_info_label.configure(
            text=f"Загружено данных: {self.analyzer.data.shape[0]} строк, {self.analyzer.data.shape[1]} колонок"
        )
        self.data_table.set_data(self.analyzer.data)
    
    def calculate_indices(self):
        if self.analyzer.data is None:
            messagebox.showwarning("Предупреждение", "Пожалуйста, сначала загрузите данные")
            return
        
        column_mapping = {key: var.get() for key, var in self.column_vars.items()}
        
        if not column_mapping['weight_col'] or not column_mapping['fishing_length_col']:
            messagebox.showerror("Ошибка", "Необходимо выбрать колонки 'Вес, г' и 'Промыс.длина, см'")
            return
        
        data_columns = [str(c) for c in self.analyzer.data.columns]
        missing_columns = [
            col_name for col_name in column_mapping.values()
            if col_name and col_name not in data_columns
        ]

        if missing_columns:
            messagebox.showerror("Ошибка", f"Следующие колонки не найдены в данных: {', '.join(missing_columns)}")
            return

        options = {
            'fulton_length': 'total' if self.fulton_basis_var.get() == "Общая" else 'fishing',
            'regression_x': self.regression_x_var.get() or None,
            'regression_y': self.regression_y_var.get() or None,
        }
        logger.info("Запрошен расчет индексов: Фультон=%s, регрессия=%s~%s",
                    options['fulton_length'], options['regression_y'], options['regression_x'])
        self.run_task(
            lambda: self.analyzer.calculate_indices(column_mapping, options),
            on_success=self._on_indices_calculated,
            description="Расчёт биометрических индексов",
        )

    def _on_indices_calculated(self, success):
        if not success:
            return

        total_count = len(self.analyzer.clean_data)
        filter_info = self.analyzer.filter_info or {'total': total_count, 'removed': 0}

        self.results_info.delete("1.0", "end")
        self.results_info.insert("1.0", 
            f"РАСЧЕТ БИОМЕТРИЧЕСКИХ ИНДЕКСОВ ЗАВЕРШЕН\n"
            f"Строк в исходных данных: {filter_info['total']}\n"
            f"Отфильтровано некорректных строк: {filter_info['removed']}\n"
            f"Количество образцов после очистки: {len(self.analyzer.clean_data)}\n"
            f"Промысловая длина: {self.analyzer.clean_data['FishingLength'].min():.2f} - {self.analyzer.clean_data['FishingLength'].max():.2f} см\n"
            f"Вес: {self.analyzer.clean_data['Weight'].min():.2f} - {self.analyzer.clean_data['Weight'].max():.2f} г\n"
            f"Индекс Фультона: {self.analyzer.clean_data['FultonIndex'].min():.4f} - {self.analyzer.clean_data['FultonIndex'].max():.4f}\n"
            f"Относит.вес: {self.analyzer.clean_data['Относит_вес'].min():.2f} - {self.analyzer.clean_data['Относит_вес'].max():.2f}"
        )
        
        self.update_results_table()
        self.update_stats_table()
        self.update_group_table()
        self.update_compare_table()
        self.update_regression_table()
        self.update_corr_table()
        self.update_rejected_table()
        
        messagebox.showinfo("Успех", "Индексы успешно рассчитаны!")
    
    def update_results_table(self):
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)
        
        if self.analyzer.clean_data is None:
            return
        
        display_data = self.analyzer.clean_data.copy()
        
        columns_to_show = []
        
        if 'Number' in display_data.columns:
            columns_to_show.append(('Number', '№'))
        if 'ChipNumber' in display_data.columns:
            columns_to_show.append(('ChipNumber', '№ чипа'))
        if 'TubeNumber' in display_data.columns:
            columns_to_show.append(('TubeNumber', '№ пробирки'))
        
        if 'Sex' in display_data.columns:
            columns_to_show.append(('Sex', 'Пол'))
        
        if 'Notes' in display_data.columns:
            columns_to_show.append(('Notes', 'Примечание'))
        
        index_columns = {
            'FultonIndex': 'Индекс Фультона',
            'PhysicalDevelopmentIndex': 'Индекс физ.развития',
            'Относит_вес': 'Относит.вес',
            'CephalicIndex': 'Длинноголовость, %',
            'BodyShapeIndex': 'Прогонистость, %'
        }
        
        for col, ru_name in index_columns.items():
            if col in display_data.columns:
                columns_to_show.append((col, ru_name))
        
        if not columns_to_show:
            column_rename_map = {
                'Number': '№', 'ChipNumber': '№ чипа', 'TubeNumber': '№ пробирки',
                'Weight': 'Вес, г', 'TotalLength': 'Длина, см', 
                'FishingLength': 'Промыс.длина, см', 'HeadLength': 'Длина гол., см',
                'Girth': 'Обхват, см', 'BodyHeight': 'Наиб. Высота, см',
                'DorsalRays': 'Кол-во лучей в СП', 'AnalRays': 'Кол-во лучей в АП',
                'FultonIndex': 'Индекс Фультона', 
                'PhysicalDevelopmentIndex': 'Индекс физ.развития',
                'Относит_вес': 'Относит.вес', 'CephalicIndex': 'Длинноголовость, %',
                'BodyShapeIndex': 'Прогонистость, %', 'Sex': 'Пол', 'Notes': 'Примечание'
            }
            existing_columns = {k: v for k, v in column_rename_map.items() if k in display_data.columns}
            display_data = display_data.rename(columns=existing_columns)
            columns_to_show = [(col, col) for col in display_data.columns]
        else:
            selected_data = {}
            for col, ru_name in columns_to_show:
                selected_data[ru_name] = display_data[col]
            display_data = pd.DataFrame(selected_data)
        
        self.results_table.set_data(display_data)

    def update_stats_table(self):
        if self.analyzer.clean_data is None:
            self.stats_table.set_data(None)
            return

        stats_df = self.analyzer.get_summary_statistics()
        self.stats_table.set_data(stats_df)

    def update_regression_table(self):
        if self.analyzer.regression_coefficients is None:
            self.regression_table.set_data(None)
            return

        self.regression_table.set_data(self.analyzer.regression_coefficients)

    def update_corr_table(self):
        if self.analyzer.clean_data is None:
            self.corr_table.set_data(None)
            return

        display = self.analyzer.get_correlation_display()
        if display is None:
            self.corr_table.set_data(None)
            return

        display = display.copy()
        display.insert(0, "Признак", display.index)
        self.corr_table.set_data(display)

    def update_group_table(self):
        if self.analyzer.clean_data is None:
            self.group_table.set_data(None)
            return
        self.group_table.set_data(self.analyzer.get_group_statistics())

    def update_compare_table(self):
        if self.analyzer.clean_data is None:
            self.compare_table.set_data(None)
            return
        self.compare_table.set_data(self.analyzer.compare_groups())

    def update_rejected_table(self):
        rejected = self.analyzer.rejected_data
        if rejected is None or rejected.empty:
            self.rejected_table.set_data(None)
            return
        self.rejected_table.set_data(rejected)

    def create_plot(self):
        if self.analyzer.clean_data is None:
            messagebox.showwarning("Предупреждение", "Пожалуйста, сначала рассчитайте индексы")
            return

        plot_type_map = {
            "Длина-Живая масса": "length_weight",
            "Индекс Фультона": "fulton",
            "Индекс физического развития": "physical",
            "Относительный вес": "relative",
            "Длинноголовость": "cephalic",
            "Прогонистость": "shape",
            "Корреляционная матрица": "correlation",
            "Произвольный график (X–Y)": "custom",
        }

        plot_type = plot_type_map[self.plot_type_var.get()]
        params = dict(
            by_sex=self.by_sex_var.get(),
            by_groups=self.by_groups_var.get(),
            point_size=self.point_size_var.get(),
            show_trendline=self.trendline_var.get(),
            show_ci=self.ci_var.get(),
            x_var=self.custom_x_var.get() or None,
            y_var=self.custom_y_var.get() or None,
        )

        # Освобождаем старый график строго в главном потоке: у FigureCanvasTkAgg
        # внутри есть tkinter.PhotoImage, и его __del__ вызывает Tk. Если сборка
        # мусора произойдёт в фоновом потоке, Tk выдаст
        # "main thread is not in main loop".
        self._discard_current_plot()

        logger.info("Запрошено построение графика: %s %s", self.plot_type_var.get(), params)
        self.run_task(
            lambda: self.analyzer.create_plot(plot_type, **params),
            on_success=self._on_plot_created,
            description="Построение графика",
        )

    def _discard_current_plot(self):
        """Уничтожает текущий график и его Tk-ресурсы в главном потоке."""
        for widget in self.plot_frame.winfo_children():
            widget.destroy()
        self.current_fig = None
        self.current_canvas = None
        self.analyzer.current_plot = None
        self.download_plot_btn.configure(state="disabled")
        # __del__ у tkinter.PhotoImage должен выполниться в главном потоке
        gc.collect()

    def _on_plot_created(self, fig):
        if not fig:
            return

        for widget in self.plot_frame.winfo_children():
            widget.destroy()

        canvas = FigureCanvasTkAgg(fig, master=self.plot_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

        self.download_plot_btn.configure(state="normal")
        self.current_fig = fig
        self.current_canvas = canvas

    def download_plot(self):
        if getattr(self, 'current_fig', None) is None:
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG files", "*.png"), ("All files", "*.*")],
            initialfile=f"график_{self.plot_type_var.get()}_{pd.Timestamp.now().strftime('%Y-%m-%d')}.png"
        )
        if not file_path:
            return

        logger.info("Сохранение графика: %s", file_path)
        self.run_task(
            lambda: self.current_fig.savefig(file_path, dpi=300, bbox_inches='tight'),
            on_success=lambda _r: messagebox.showinfo("Успех", f"График сохранен в {file_path}"),
            description="Сохранение графика",
        )

    def _export_dataframe(self):
        export_data = self.analyzer.clean_data.copy()
        existing_columns = {k: v for k, v in COLUMN_RENAME_MAP.items() if k in export_data.columns}
        return export_data.rename(columns=existing_columns)

    def _write_all_results(self, file_path):
        with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
            self._export_dataframe().to_excel(
                writer, sheet_name='Данные_с_индексами', index=False
            )

            summary_stats = self.analyzer.get_summary_statistics()
            if summary_stats is not None:
                summary_stats.to_excel(writer, sheet_name='Сводная_статистика', index=False)

            if self.analyzer.regression_coefficients is not None:
                self.analyzer.regression_coefficients.to_excel(
                    writer, sheet_name='Коэффициенты_регрессии', index=False
                )

            corr = self.analyzer.get_correlation_matrix()
            if corr is not None:
                self.analyzer._rename_corr(corr).to_excel(
                    writer, sheet_name='Корреляционная_матрица'
                )

            group_stats = self.analyzer.get_group_statistics()
            if group_stats is not None:
                group_stats.to_excel(writer, sheet_name='Статистика_по_группам', index=False)

            comparison = self.analyzer.compare_groups()
            if comparison is not None:
                comparison.to_excel(writer, sheet_name='Сравнение_групп', index=False)

            rejected = self.analyzer.rejected_data
            if rejected is not None and not rejected.empty:
                rejected.to_excel(writer, sheet_name='Отброшенные_строки', index=False)
        return file_path

    def _write_excel(self, file_path):
        with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
            self._export_dataframe().to_excel(
                writer, sheet_name='Данные_с_индексами', index=False
            )
        return file_path

    def save_all_results(self):
        if self.analyzer.clean_data is None:
            messagebox.showwarning("Предупреждение", "Нет данных для сохранения")
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
            initialfile="биометрические_индексы_результаты.xlsx"
        )
        if not file_path:
            return

        logger.info("Запрошено сохранение всех результатов: %s", file_path)
        self.run_task(
            lambda: self._write_all_results(file_path),
            on_success=lambda _r: messagebox.showinfo("Успех", f"Результаты сохранены в {file_path}"),
            description="Сохранение результатов в Excel",
        )

    def download_excel(self):
        if self.analyzer.clean_data is None:
            messagebox.showwarning("Предупреждение", "Нет данных для экспорта")
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
            initialfile="биометрические_индексы_результаты.xlsx"
        )
        if not file_path:
            return

        logger.info("Запрошен экспорт данных: %s", file_path)
        self.run_task(
            lambda: self._write_excel(file_path),
            on_success=lambda _r: messagebox.showinfo("Успех", f"Файл сохранен в {file_path}"),
            description="Сохранение Excel файла",
        )

    def download_excel_template(self):
        """Сохраняет пустой шаблон таблицы со всеми необходимыми колонками."""
        file_path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
            initialfile="шаблон_биометрических_данных.xlsx",
        )
        if not file_path:
            return

        logger.info("Запрошено сохранение шаблона: %s", file_path)
        self.run_task(
            lambda: self._write_template(file_path),
            on_success=lambda _r: messagebox.showinfo(
                "Шаблон", f"Шаблон сохранён в {file_path}"
            ),
            description="Сохранение шаблона Excel",
        )

    @staticmethod
    def _write_template(file_path):
        """Формирует шаблон: лист «Данные» с колонками и лист «Инструкция»."""
        with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
            data = pd.DataFrame(TEMPLATE_EXAMPLES, columns=TEMPLATE_COLUMNS)
            data.to_excel(writer, sheet_name="Данные", index=False)
            help_df = pd.DataFrame(
                TEMPLATE_HELP,
                columns=["Колонка", "Обязательность", "Единицы", "Описание"],
            )
            help_df.to_excel(writer, sheet_name="Инструкция", index=False)
        logger.info("Шаблон сохранён: %s", file_path)
        return file_path
