from .common import *  # noqa: F401,F403


class PagedTable:
    """Таблица (ttk.Treeview) с поиском, сортировкой по клику и пагинацией.

    Работает с DataFrame: хранит полный набор, применяет фильтр и сортировку,
    а на экран выводит только текущую страницу.
    """

    def __init__(self, parent, page_size=50, min_col_width=80, max_col_width=300,
                 formatter=format_value):
        self.parent = parent
        self.page_size = page_size
        self.min_col_width = min_col_width
        self.max_col_width = max_col_width
        self.formatter = formatter

        self.base_df = None
        self.view_df = None
        self.page = 0
        self.sort_col = None
        self.sort_asc = True
        self.search_term = ""
        self.search_column = None
        self._search_blob = None
        self._search_job = None
        self._suppress_search = False

        self._build_ui()
        self._render_page()

    # --- построение интерфейса -------------------------------------------------
    def _build_ui(self):
        controls = ctk.CTkFrame(self.parent)
        controls.pack(fill="x", pady=(0, 5))

        ctk.CTkLabel(controls, text="Поиск:").pack(side="left", padx=(0, 4))
        self.search_var = ctk.StringVar()
        self.search_entry = ctk.CTkEntry(
            controls, textvariable=self.search_var, width=190,
            placeholder_text="фильтр по всем колонкам"
        )
        self.search_entry.pack(side="left")
        self.search_var.trace_add("write", self._on_search_changed)

        self.search_col_var = ctk.StringVar(value="Все колонки")
        self.search_col_combo = ctk.CTkComboBox(
            controls, variable=self.search_col_var, values=["Все колонки"],
            width=130, command=self._on_search_column_changed
        )
        self.search_col_combo.pack(side="left", padx=(6, 0))

        ctk.CTkButton(controls, text="Сброс", width=70, command=self.clear_filter).pack(
            side="left", padx=6
        )

        self.next_btn = ctk.CTkButton(controls, text="Вперёд ▶", width=90, command=self.next_page)
        self.next_btn.pack(side="right")
        self.page_label = ctk.CTkLabel(controls, text="")
        self.page_label.pack(side="right", padx=8)
        self.prev_btn = ctk.CTkButton(controls, text="◀ Назад", width=90, command=self.prev_page)
        self.prev_btn.pack(side="right")
        self.count_label = ctk.CTkLabel(controls, text="")
        self.count_label.pack(side="right", padx=(0, 12))

        ctk.CTkLabel(controls, text="На странице:").pack(side="left", padx=(14, 4))
        self.page_size_var = ctk.StringVar(value=str(self.page_size))
        self.page_size_combo = ctk.CTkComboBox(
            controls, values=["25", "50", "100", "200", "500", "1000"],
            variable=self.page_size_var, width=80, command=self._on_page_size_changed
        )
        self.page_size_combo.pack(side="left")

        tree_frame = ctk.CTkFrame(self.parent)
        tree_frame.pack(fill="both", expand=True)

        self.tree = ttk.Treeview(tree_frame, show="headings")
        v_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        h_scroll = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        v_scroll.grid(row=0, column=1, sticky="ns")
        h_scroll.grid(row=1, column=0, sticky="ew")
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

    # --- данные ----------------------------------------------------------------
    def set_data(self, df):
        """Заменяет данные таблицы и сбрасывает фильтр/сортировку/страницу."""
        self.base_df = None if df is None else df.reset_index(drop=True)
        self.page = 0
        self.sort_col = None
        self.sort_asc = True
        self.search_term = ""
        self.search_column = None

        # Предрасчёт строки поиска (по всем колонкам) для быстрого фильтра
        self._search_blob = None
        columns = ["Все колонки"]
        if self.base_df is not None:
            columns += [str(c) for c in self.base_df.columns]
            try:
                self._search_blob = self.base_df.astype(str).agg(" ".join, axis=1).str.lower()
            except Exception:
                logger.debug("Не удалось построить индекс поиска", exc_info=True)
        self.search_col_combo.configure(values=columns)
        self.search_col_var.set("Все колонки")

        self._suppress_search = True
        if self.search_var.get():
            self.search_var.set("")
        self._suppress_search = False

        self.render()

    def clear(self):
        self.set_data(None)

    def render(self):
        self._apply_filter_and_sort()
        self._render_page()

    def _apply_filter_and_sort(self):
        df = self.base_df
        if df is None:
            self.view_df = None
            return

        term = (self.search_term or "").strip().lower()
        if term:
            column = self.search_column
            actual_col = None
            if column is not None:
                if column in df.columns:
                    actual_col = column
                else:
                    matches = [c for c in df.columns if str(c) == column]
                    actual_col = matches[0] if matches else None

            if actual_col is not None:
                mask = df[actual_col].astype(str).str.lower().str.contains(term, regex=False)
            elif self._search_blob is not None and len(self._search_blob) == len(df):
                mask = self._search_blob.str.contains(term, regex=False)
            else:
                mask = df.astype(str).apply(
                    lambda col: col.str.lower().str.contains(term, regex=False)
                ).any(axis=1)
            df = df[mask]

        if self.sort_col is not None and self.sort_col in df.columns and len(df) > 0:
            series = df[self.sort_col]
            try:
                order = series.sort_values(
                    ascending=self.sort_asc, kind="stable", na_position="last"
                ).index
            except TypeError:
                order = series.astype(str).sort_values(
                    ascending=self.sort_asc, kind="stable", na_position="last"
                ).index
            df = df.loc[order]

        self.view_df = df

    def total_pages(self):
        if self.view_df is None or len(self.view_df) == 0:
            return 1
        return max(1, -(-len(self.view_df) // self.page_size))

    def _render_page(self):
        self._clear_tree()

        if self.view_df is None:
            if list(self.tree["columns"]):
                self.tree["columns"] = ()
            self.count_label.configure(text="")
            self.page_label.configure(text="")
            self.prev_btn.configure(state="disabled")
            self.next_btn.configure(state="disabled")
            return

        pages = self.total_pages()
        if self.page >= pages:
            self.page = pages - 1
        start = self.page * self.page_size
        page_df = self.view_df.iloc[start:start + self.page_size]

        self._set_columns(self.view_df.columns)
        for _, row in page_df.iterrows():
            values = [self.formatter(col, val) for col, val in row.items()]
            self.tree.insert("", "end", values=values)

        self._autosize(page_df.columns)

        self.count_label.configure(text=f"Записей: {len(self.view_df)}")
        self.page_label.configure(text=f"Стр. {self.page + 1} / {pages}")
        self.prev_btn.configure(state="normal" if self.page > 0 else "disabled")
        self.next_btn.configure(state="normal" if self.page < pages - 1 else "disabled")

    def _set_columns(self, columns):
        columns = [str(c) for c in columns]
        if list(self.tree["columns"]) != columns:
            self.tree["columns"] = columns

        for col in columns:
            arrow = ""
            if col == self.sort_col:
                arrow = " ▲" if self.sort_asc else " ▼"
            self.tree.heading(
                col, text=wrap_text(col, 15) + arrow,
                command=lambda c=col: self.sort_by(c)
            )
            self.tree.column(
                col, width=max(self.min_col_width, len(col) * 8), stretch=True, anchor="w"
            )

    def _autosize(self, columns):
        self.tree.update_idletasks()
        for col in columns:
            col = str(col)
            heading = self.tree.heading(col)["text"].replace("\n", "")
            width = len(heading) * 8
            for item in self.tree.get_children():
                width = max(width, len(str(self.tree.set(item, col))) * 7)
            width = min(max(self.min_col_width, width), self.max_col_width)
            self.tree.column(col, width=width, stretch=True)

    def _clear_tree(self):
        children = self.tree.get_children()
        if children:
            self.tree.delete(*children)

    # --- фильтр / сортировка / страницы ---------------------------------------
    def _on_search_changed(self, *_):
        if self._suppress_search:
            return
        if self._search_job is not None:
            try:
                self.tree.after_cancel(self._search_job)
            except Exception:
                pass
        # Небольшая задержка, чтобы не фильтровать на каждое нажатие клавиши
        self._search_job = self.tree.after(350, self._apply_search)

    def _apply_search(self):
        self._search_job = None
        self.search_term = self.search_var.get()
        self.page = 0
        self.render()

    def _on_search_column_changed(self, value):
        self.search_column = None if value == "Все колонки" else value
        self.page = 0
        self.render()

    def clear_filter(self):
        self._suppress_search = True
        self.search_var.set("")
        self._suppress_search = False
        self.search_term = ""
        self.page = 0
        self.render()

    def sort_by(self, column):
        if self.sort_col == column:
            self.sort_asc = not self.sort_asc
        else:
            self.sort_col = column
            self.sort_asc = True
        self.page = 0
        self.render()

    def prev_page(self):
        if self.page > 0:
            self.page -= 1
            self._render_page()

    def next_page(self):
        if self.page < self.total_pages() - 1:
            self.page += 1
            self._render_page()

    def _on_page_size_changed(self, value):
        try:
            size = int(value)
        except (TypeError, ValueError):
            return
        if size > 0:
            self.page_size = size
            self.page = 0
            self.render()
