import customtkinter as ctk

from tkinter import ttk, filedialog, messagebox

import pandas as pd

import numpy as np

import matplotlib.pyplot as plt

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

import os

import warnings

warnings.filterwarnings('ignore')





ctk.set_appearance_mode("Light")

ctk.set_default_color_theme("blue")



class BiometricAnalysis:

    def __init__(self):

        self.data = None

        self.clean_data = None

        self.regression_coefficients = None

        self.current_plot = None



    def find_column(self, pattern, data):

        pattern_lower = pattern.lower()

        for col in data.columns:

            if pattern_lower in col.lower():

                return col

        return None



    def load_data(self, file_path=None, uploaded_file=None):

        try:

            if uploaded_file is not None:

                self.data = pd.read_excel(uploaded_file)

            elif file_path and os.path.exists(file_path):

                self.data = pd.read_excel(file_path)

            else:

                messagebox.showerror("Ошибка", "Файл не найден")

                return False

            return True

        except Exception as e:

            messagebox.showerror("Ошибка", f"Ошибка загрузки: {e}")

            return False



    def calculate_indices(self, column_mapping):

        try:

            clean_data = pd.DataFrame()

            clean_data['Weight'] = self.data[column_mapping['weight_col']]

            clean_data['FishingLength'] = self.data[column_mapping['fishing_length_col']]



            if column_mapping['total_length_col']:

                clean_data['TotalLength'] = self.data[column_mapping['total_length_col']]

            if column_mapping['number_col']:

                clean_data['Number'] = self.data[column_mapping['number_col']]

            if column_mapping['chip_col']:

                clean_data['ChipNumber'] = self.data[column_mapping['chip_col']]

            if column_mapping['tube_col']:

                clean_data['TubeNumber'] = self.data[column_mapping['tube_col']]

            if column_mapping['head_length_col']:

                clean_data['HeadLength'] = self.data[column_mapping['head_length_col']]

            if column_mapping['girth_col']:

                clean_data['Girth'] = self.data[column_mapping['girth_col']]

            if column_mapping['body_height_col']:

                clean_data['BodyHeight'] = self.data[column_mapping['body_height_col']]

            if column_mapping['dorsal_rays_col']:

                clean_data['DorsalRays'] = self.data[column_mapping['dorsal_rays_col']]

            if column_mapping['anal_rays_col']:

                clean_data['AnalRays'] = self.data[column_mapping['anal_rays_col']]

            if column_mapping['sex_col']:

                clean_data['Sex'] = self.data[column_mapping['sex_col']]

            if column_mapping['notes_col']:

                clean_data['Notes'] = self.data[column_mapping['notes_col']]

            if column_mapping['age_col']:

                clean_data['Age'] = self.data[column_mapping['age_col']]



            mask = (clean_data['FishingLength'].notna() & clean_data['Weight'].notna() &

                    (clean_data['FishingLength'] > 0) & (clean_data['Weight'] > 0))



            if 'HeadLength' in clean_data.columns:

                mask = mask & ((clean_data['HeadLength'] > 0) | clean_data['HeadLength'].isna())

            if 'BodyHeight' in clean_data.columns:

                mask = mask & ((clean_data['BodyHeight'] > 0) | clean_data['BodyHeight'].isna())

            if 'Sex' in clean_data.columns:

                mask = mask & (clean_data['Sex'].notna() & (clean_data['Sex'] != ""))

            if 'Notes' in clean_data.columns:

                mask = mask & (clean_data['Notes'].notna() & (clean_data['Notes'] != ""))



            clean_data = clean_data[mask].copy()



            clean_data['FultonIndex'] = (clean_data['Weight'] / (clean_data['FishingLength']**3)) * 100

            clean_data['PhysicalDevelopmentIndex'] = (clean_data['Weight'] * clean_data['FishingLength']) / 100

            clean_data['Относит_вес'] = (clean_data['Weight'] / clean_data['FishingLength']) * 1000



            if 'HeadLength' in clean_data.columns and clean_data['HeadLength'].notna().any():

                clean_data['CephalicIndex'] = (clean_data['HeadLength'] / clean_data['FishingLength']) * 100

            if 'BodyHeight' in clean_data.columns and clean_data['BodyHeight'].notna().any():

                clean_data['BodyShapeIndex'] = (clean_data['FishingLength'] / clean_data['BodyHeight']) * 100



            self.clean_data = clean_data

            if 'TotalLength' in clean_data.columns:

                self.calculate_regression_coefficients()

            else:

                self.regression_coefficients = None

            return True

        except Exception as e:

            messagebox.showerror("Ошибка", f"Ошибка расчета: {e}")

            return False



    # Regression

    def calculate_power_regression(self, data, x_var, y_var):

        if len(data) < 2:

            return None

        try:

            data = data[(data[x_var] > 0) & (data[y_var] > 0)].copy()

            if len(data) < 2:

                return None

            log_x = np.log(data[x_var])

            log_y = np.log(data[y_var])

            coef = np.polyfit(log_x, log_y, 1)

            b = coef[0]

            a = np.exp(coef[1])

            pred_log_y = coef[1] + b * log_x

            ss_res = np.sum((log_y - pred_log_y)**2)

            ss_tot = np.sum((log_y - np.mean(log_y))**2)

            r2 = 1 - (ss_res/ss_tot) if ss_tot != 0 else 0

            return {'a': a, 'b': b, 'r_squared': r2,

                    'equation': f"y = {a:.4f} * x^{b:.4f}",

                    'r2_label': f"R² = {r2:.4f}"}

        except Exception:

            return None



    def calculate_regression_coefficients(self):

        if self.clean_data is None or 'TotalLength' not in self.clean_data.columns:

            self.regression_coefficients = None

            return

        coeff_list = []

        data = self.clean_data

        if 'Notes' in data.columns and 'Sex' in data.columns:

            for group in data['Notes'].unique():

                for sex in data['Sex'].unique():

                    sub = data[(data['Notes']==group) & (data['Sex']==sex)]

                    if len(sub) >= 2:

                        reg = self.calculate_power_regression(sub, 'TotalLength', 'Weight')

                        if reg:

                            coeff_list.append({'Группа': group, 'Пол': sex,

                                'Коэффициент_a': round(reg['a'],6), 'Коэффициент_b': round(reg['b'],6),

                                'R_квадрат': round(reg['r_squared'],6), 'Уравнение': reg['equation'], 'n': len(sub)})

        if 'Notes' in data.columns:

            for group in data['Notes'].unique():

                sub = data[data['Notes']==group]

                if len(sub) >= 2:

                    reg = self.calculate_power_regression(sub, 'TotalLength', 'Weight')

                    if reg:

                        coeff_list.append({'Группа': group, 'Пол': 'Все',

                            'Коэффициент_a': round(reg['a'],6), 'Коэффициент_b': round(reg['b'],6),

                            'R_квадрат': round(reg['r_squared'],6), 'Уравнение': reg['equation'], 'n': len(sub)})

        if 'Sex' in data.columns:

            for sex in data['Sex'].unique():

                sub = data[data['Sex']==sex]

                if len(sub) >= 2:

                    reg = self.calculate_power_regression(sub, 'TotalLength', 'Weight')

                    if reg:

                        coeff_list.append({'Группа': 'Все', 'Пол': sex,

                            'Коэффициент_a': round(reg['a'],6), 'Коэффициент_b': round(reg['b'],6),

                            'R_квадрат': round(reg['r_squared'],6), 'Уравнение': reg['equation'], 'n': len(sub)})

        if len(data) >= 2:

            reg = self.calculate_power_regression(data, 'TotalLength', 'Weight')

            if reg:

                coeff_list.append({'Группа': 'Все', 'Пол': 'Все',

                    'Коэффициент_a': round(reg['a'],6), 'Коэффициент_b': round(reg['b'],6),

                    'R_квадрат': round(reg['r_squared'],6), 'Уравнение': reg['equation'], 'n': len(data)})

        self.regression_coefficients = pd.DataFrame(coeff_list) if coeff_list else None



    # Charts

    def create_plot(self, plot_type, by_sex=False, by_groups=False, point_size=2, show_trendline=True):

        if self.clean_data is None:

            return None

        try:

            if plot_type == "length_weight":

                if 'TotalLength' not in self.clean_data.columns:

                    messagebox.showwarning("Предупреждение", "Нет данных общей длины")

                    return None

                x_label, y_label = "Общая длина, см", "Масса, г"

                x_data, y_data = self.clean_data['TotalLength'], self.clean_data['Weight']

                title = "Длина-Масса"

                power = True

            elif plot_type == "fulton":

                x_label, y_label = "Пром.длина, см", "Индекс Фультона"

                x_data, y_data = self.clean_data['FishingLength'], self.clean_data['FultonIndex']

                title = "Индекс Фультона"; power = False

            elif plot_type == "physical":

                x_label, y_label = "Пром.длина, см", "Индекс физ.развития"

                x_data, y_data = self.clean_data['FishingLength'], self.clean_data['PhysicalDevelopmentIndex']

                title = "Индекс физ.развития"; power = False

            elif plot_type == "relative":

                x_label, y_label = "Пром.длина, см", "Относительный вес"

                x_data, y_data = self.clean_data['FishingLength'], self.clean_data['Относит_вес']

                title = "Относительный вес"; power = False

            elif plot_type == "cephalic":

                if 'CephalicIndex' not in self.clean_data.columns:

                    messagebox.showwarning("Предупреждение", "Нет данных длиноголовости")

                    return None

                x_label, y_label = "Пром.длина, см", "Длинноголовость, %"

                x_data, y_data = self.clean_data['FishingLength'], self.clean_data['CephalicIndex']

                title = "Индекс длиноголовости"; power = False

            elif plot_type == "shape":

                if 'BodyShapeIndex' not in self.clean_data.columns:

                    messagebox.showwarning("Предупреждение", "Нет данных прогонистости")

                    return None

                x_label, y_label = "Пром.длина, см", "Прогонистость, %"

                x_data, y_data = self.clean_data['FishingLength'], self.clean_data['BodyShapeIndex']

                title = "Индекс прогонистости"; power = False

            else:

                return None



            

            if by_sex and by_groups and 'Sex' in self.clean_data.columns and 'Notes' in self.clean_data.columns:

                groups = self.clean_data['Notes'].unique()

                fig, axes = plt.subplots(1, len(groups), figsize=(5*len(groups), 6))

                if len(groups)==1: axes = [axes]

                fig.suptitle(title, fontsize=16, weight='bold')

                for idx, gr in enumerate(groups):

                    ax = axes[idx]

                    gr_data = self.clean_data[self.clean_data['Notes']==gr]

                    for sex in gr_data['Sex'].unique():

                        sub = gr_data[gr_data['Sex']==sex]

                        ax.scatter(x_data[sub.index], y_data[sub.index], alpha=0.7, s=point_size*20, label=sex)

                    if show_trendline and len(gr_data)>1:

                        z = np.polyfit(x_data[gr_data.index], y_data[gr_data.index], 2)

                        p = np.poly1d(z)

                        xl = np.linspace(x_data[gr_data.index].min(), x_data[gr_data.index].max(), 100)

                        ax.plot(xl, p(xl), 'k-', alpha=0.5)

                    ax.set_title(gr); ax.set_xlabel(x_label)

                    if idx==0: ax.set_ylabel(y_label)

                    ax.legend(); ax.grid(True, alpha=0.3)

            elif by_groups and 'Notes' in self.clean_data.columns:

                groups = self.clean_data['Notes'].unique()

                fig, axes = plt.subplots(1, len(groups), figsize=(5*len(groups), 6))

                if len(groups)==1: axes = [axes]

                fig.suptitle(title, fontsize=16, weight='bold')

                for idx, gr in enumerate(groups):

                    ax = axes[idx]

                    idxs = self.clean_data[self.clean_data['Notes']==gr].index

                    ax.scatter(x_data[idxs], y_data[idxs], alpha=0.7, s=point_size*20, color='blue')

                    if show_trendline and len(idxs)>1:

                        z = np.polyfit(x_data[idxs], y_data[idxs], 2)

                        p = np.poly1d(z)

                        xl = np.linspace(x_data[idxs].min(), x_data[idxs].max(), 100)

                        ax.plot(xl, p(xl), 'k-', alpha=0.5)

                    ax.set_title(gr); ax.set_xlabel(x_label)

                    if idx==0: ax.set_ylabel(y_label)

                    ax.grid(True, alpha=0.3)

            elif by_sex and 'Sex' in self.clean_data.columns:

                fig, ax = plt.subplots(figsize=(12,8))

                sexes = self.clean_data['Sex'].unique()

                colors = ['blue','red','green','orange']

                for i, sex in enumerate(sexes):

                    idxs = self.clean_data[self.clean_data['Sex']==sex].index

                    ax.scatter(x_data[idxs], y_data[idxs], alpha=0.7, s=point_size*20, label=sex, color=colors[i%len(colors)])

                    if show_trendline and len(idxs)>1:

                        z = np.polyfit(x_data[idxs], y_data[idxs], 2)

                        p = np.poly1d(z)

                        xl = np.linspace(x_data[idxs].min(), x_data[idxs].max(), 100)

                        ax.plot(xl, p(xl), '-', alpha=0.5, color=colors[i%len(colors)])

                ax.set_xlabel(x_label); ax.set_ylabel(y_label); ax.set_title(title)

                ax.legend(); ax.grid(True, alpha=0.3)

            else:

                fig, ax = plt.subplots(figsize=(12,8))

                ax.scatter(x_data, y_data, alpha=0.7, s=point_size*20, color='blue')

                if show_trendline and len(x_data)>1:

                    z = np.polyfit(x_data, y_data, 2)

                    p = np.poly1d(z)

                    xl = np.linspace(x_data.min(), x_data.max(), 100)

                    ax.plot(xl, p(xl), 'k-', alpha=0.5)

                ax.set_xlabel(x_label); ax.set_ylabel(y_label); ax.set_title(title)

                ax.grid(True, alpha=0.3)

            plt.tight_layout()

            self.current_plot = fig

            return fig

        except Exception as e:

            messagebox.showerror("Ошибка", f"Ошибка графика: {e}")

            return None



    def get_summary_statistics(self):

        if self.clean_data is None:

            return None

        stats = [{'Категория': 'Общая информация', 'Показатель': 'Количество образцов', 'Значение': len(self.clean_data)}]

        stats.extend([

            {'Категория': 'Входные данные', 'Показатель': 'Вес, г (мин)', 'Значение': self.clean_data['Weight'].min()},

            {'Категория': 'Входные данные', 'Показатель': 'Вес, г (макс)', 'Значение': self.clean_data['Weight'].max()},

            {'Категория': 'Входные данные', 'Показатель': 'Вес, г (средн)', 'Значение': self.clean_data['Weight'].mean()},

            {'Категория': 'Входные данные', 'Показатель': 'Промыс.длина, см (мин)', 'Значение': self.clean_data['FishingLength'].min()},

            {'Категория': 'Входные данные', 'Показатель': 'Промыс.длина, см (макс)', 'Значение': self.clean_data['FishingLength'].max()},

            {'Категория': 'Входные данные', 'Показатель': 'Промыс.длина, см (средн)', 'Значение': self.clean_data['FishingLength'].mean()}

        ])

        if 'TotalLength' in self.clean_data.columns:

            stats.extend([

                {'Категория': 'Входные данные', 'Показатель': 'Длина, см (мин)', 'Значение': self.clean_data['TotalLength'].min()},

                {'Категория': 'Входные данные', 'Показатель': 'Длина, см (макс)', 'Значение': self.clean_data['TotalLength'].max()},

                {'Категория': 'Входные данные', 'Показатель': 'Длина, см (средн)', 'Значение': self.clean_data['TotalLength'].mean()}

            ])

        if 'Age' in self.clean_data.columns:

            stats.extend([

                {'Категория': 'Входные данные', 'Показатель': 'Возраст (мин)', 'Значение': self.clean_data['Age'].min()},

                {'Категория': 'Входные данные', 'Показатель': 'Возраст (макс)', 'Значение': self.clean_data['Age'].max()},

                {'Категория': 'Входные данные', 'Показатель': 'Возраст (средн)', 'Значение': self.clean_data['Age'].mean()}

            ])

        stats.extend([

            {'Категория': 'Индексы', 'Показатель': 'Фультона (мин)', 'Значение': self.clean_data['FultonIndex'].min()},

            {'Категория': 'Индексы', 'Показатель': 'Фультона (макс)', 'Значение': self.clean_data['FultonIndex'].max()},

            {'Категория': 'Индексы', 'Показатель': 'Фультона (средн)', 'Значение': self.clean_data['FultonIndex'].mean()},

            {'Категория': 'Индексы', 'Показатель': 'физ.развития (мин)', 'Значение': self.clean_data['PhysicalDevelopmentIndex'].min()},

            {'Категория': 'Индексы', 'Показатель': 'физ.развития (макс)', 'Значение': self.clean_data['PhysicalDevelopmentIndex'].max()},

            {'Категория': 'Индексы', 'Показатель': 'физ.развития (средн)', 'Значение': self.clean_data['PhysicalDevelopmentIndex'].mean()},

            {'Категория': 'Индексы', 'Показатель': 'Относит.вес (мин)', 'Значение': self.clean_data['Относит_вес'].min()},

            {'Категория': 'Индексы', 'Показатель': 'Относит.вес (макс)', 'Значение': self.clean_data['Относит_вес'].max()},

            {'Категория': 'Индексы', 'Показатель': 'Относит.вес (средн)', 'Значение': self.clean_data['Относит_вес'].mean()}

        ])

        if 'CephalicIndex' in self.clean_data.columns:

            stats.extend([

                {'Категория': 'Индексы', 'Показатель': 'Длинноголовость (мин)', 'Значение': self.clean_data['CephalicIndex'].min()},

                {'Категория': 'Индексы', 'Показатель': 'Длинноголовость (макс)', 'Значение': self.clean_data['CephalicIndex'].max()},

                {'Категория': 'Индексы', 'Показатель': 'Длинноголовость (средн)', 'Значение': self.clean_data['CephalicIndex'].mean()}

            ])

        if 'BodyShapeIndex' in self.clean_data.columns:

            stats.extend([

                {'Категория': 'Индексы', 'Показатель': 'Прогонистость (мин)', 'Значение': self.clean_data['BodyShapeIndex'].min()},

                {'Категория': 'Индексы', 'Показатель': 'Прогонистость (макс)', 'Значение': self.clean_data['BodyShapeIndex'].max()},

                {'Категория': 'Индексы', 'Показатель': 'Прогонистость (средн)', 'Значение': self.clean_data['BodyShapeIndex'].mean()}

            ])

        return pd.DataFrame(stats)





class BiometricApp(ctk.CTk):

    def __init__(self):

        super().__init__()

        self.analyzer = BiometricAnalysis()

        self.column_combos = {}

        self.setup_ui()



    def setup_ui(self):

        self.title("📊 Анализ биометрических индексов")

        self.geometry("1400x900")

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

        menu = ctk.CTkFrame(self, height=40)

        menu.pack(fill="x", padx=20, pady=(10,0))

        menu.pack_propagate(False)

        ctk.CTkButton(menu, text="📖 Инструкция", command=self.show_instructions, width=120, height=30).pack(side="left", padx=10, pady=5)

        ctk.CTkButton(
            menu, text="📥 Скачать шаблон", command=self.download_template,
            width=120, height=30, fg_color="#28a745", hover_color="#218838"
        ).pack(side="left", padx=10, pady=5)



    def download_template(self):

        try:

            path = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Excel", "*.xlsx")],
                initialfile="шаблон_данных.xlsx"
            )

            if path:

                df = pd.DataFrame({

                    '№': [1,2], '№ чипа': ['ABC123','DEF456'], '№ пробирки': ['A1','B2'],

                    'Вес, г': [150.5,200.3], 'Длина, см': [25.0,30.5], 'Промыс.длина, см': [22.0,27.0],

                    'Длина гол., см': [5.2,6.1], 'Обхват, см': [12.0,14.5], 'Наиб. Высота, см': [8.0,9.5],

                    'Кол-во лучей в СП': [12,13], 'Кол-во лучей в АП': [10,11], 'Примечание': ['Рыба 1','Рыба 2'],

                    'Пол': ['М','Ж'], 'Возраст': [3,4]

                })

                with pd.ExcelWriter(path, engine='openpyxl') as writer:

                    df.to_excel(writer, sheet_name='Шаблон', index=False)

                    instr = pd.DataFrame({'Описание': ['Обязательные: Вес, г и Промыс.длина, см', 'Остальные колонки опциональны.']})

                    instr.to_excel(writer, sheet_name='Инструкция', index=False)

                messagebox.showinfo("Успех", f"Шаблон сохранён: {path}")

        except Exception as e:

            messagebox.showerror("Ошибка", f"Ошибка сохранения: {e}")



    def show_instructions(self):

        txt = """ИНСТРУКЦИЯ

1. Загрузите Excel с колонками (обязательны Вес, г и Промыс.длина, см)

2. На вкладке "Биометрические индексы" сопоставьте колонки и нажмите
"Рассчитать"

3. Результаты – индексы, статистика, регрессии (если есть общая длина), графики

4. Можно скачать шаблон для заполнения"""

        win = ctk.CTkToplevel(self)

        win.title("Инструкция")

        win.geometry("600x400")

        text = ctk.CTkTextbox(win, wrap="word")

        text.pack(fill="both", expand=True, padx=20, pady=20)

        text.insert("1.0", txt)

        text.configure(state="disabled")

        ctk.CTkButton(win, text="Закрыть", command=win.destroy).pack(pady=10)



    # -- Upload

    def setup_tab1(self):

        left = ctk.CTkFrame(self.tab1)

        left.pack(side="left", fill="both", expand=True, padx=10, pady=10)

        ctk.CTkLabel(left, text="📁 Загрузка данных", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)

        ctk.CTkLabel(left, text="Выберите Excel файл:").pack(anchor="w", pady=(10,5))

        self.load_btn = ctk.CTkButton(left, text="Обзор...", command=self.load_file)

        self.load_btn.pack(fill="x", pady=5)

        ctk.CTkLabel(left, text="Путь к файлу:").pack(anchor="w", pady=(10,5))

        self.file_path_entry = ctk.CTkEntry(left, placeholder_text="C:/путь/файл.xlsx")

        self.file_path_entry.pack(fill="x", pady=5)

        ctk.CTkLabel(left, text="Папка для результатов:").pack(anchor="w", pady=(10,5))

        self.results_dir_entry = ctk.CTkEntry(left, placeholder_text="C:/результаты")

        self.results_dir_entry.pack(fill="x", pady=5)

        self.load_data_btn = ctk.CTkButton(left, text="Загрузить", command=self.process_load_data)

        self.load_data_btn.pack(fill="x", pady=20)



        right = ctk.CTkFrame(self.tab1)

        right.pack(side="right", fill="both", expand=True, padx=10, pady=10)

        ctk.CTkLabel(right, text="Статус", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)

        self.status_text = ctk.CTkTextbox(right, height=300)

        self.status_text.pack(fill="both", expand=True, pady=10)

        ctk.CTkLabel(right, text="Найденные колонки:", font=ctk.CTkFont(weight="bold")).pack(anchor="w")

        self.columns_text = ctk.CTkTextbox(right, height=200)

        self.columns_text.pack(fill="both", expand=True, pady=10)



    # -- Data overview

    def setup_tab2(self):

        frame = ctk.CTkFrame(self.tab2)

        frame.pack(fill="both", expand=True, padx=10, pady=10)

        ctk.CTkLabel(frame, text="📋 Обзор загруженных данных", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)

        info_frame = ctk.CTkFrame(frame)

        info_frame.pack(fill="x", pady=10)

        self.data_info_label = ctk.CTkLabel(info_frame, text="Данные не загружены", font=ctk.CTkFont(weight="bold"))

        self.data_info_label.pack(pady=10)

        self.create_data_table(frame)



    def create_data_table(self, parent):

        frame = ctk.CTkFrame(parent)

        frame.pack(fill="both", expand=True, pady=5)

        tree_frame = ctk.CTkFrame(frame)

        tree_frame.pack(fill="both", expand=True, pady=5)

        v_scroll = ttk.Scrollbar(tree_frame, orient="vertical")

        h_scroll = ttk.Scrollbar(tree_frame, orient="horizontal")

        self.data_tree = ttk.Treeview(tree_frame, yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set, height=20)

        v_scroll.configure(command=self.data_tree.yview)

        h_scroll.configure(command=self.data_tree.xview)

        v_scroll.pack(side="right", fill="y")

        h_scroll.pack(side="bottom", fill="x")

        self.data_tree.pack(side="left", fill="both", expand=True)

        ctk.CTkButton(frame, text="Обновить таблицу", command=self.update_data_table).pack(pady=5)



    # -- Biometric indexes

    def setup_tab3(self):

        main = ctk.CTkFrame(self.tab3)

        main.pack(fill="both", expand=True, padx=10, pady=10)

        left = ctk.CTkFrame(main, width=400)

        left.pack(side="left", fill="both", padx=(0,10), pady=10)

        canvas = ctk.CTkCanvas(left, highlightthickness=0)

        scrollbar = ctk.CTkScrollbar(left, orientation="vertical", command=canvas.yview)

        scrollable = ctk.CTkFrame(canvas)

        scrollable.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        canvas.create_window((0,0), window=scrollable, anchor="nw")

        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)

        scrollbar.pack(side="right", fill="y")

        ctk.CTkLabel(scrollable, text="Настройки анализа", font=ctk.CTkFont(size=14, weight="bold")).pack(pady=10)



        col_opts = [""]

        self.column_vars = {}

        cols_cfg = [

            ('number_col', 'Колонка №:'), ('chip_col', '№ чипа:'), ('tube_col', '№ пробирки:'),

            ('weight_col', 'Вес, г: *'), ('total_length_col', 'Длина, см:'),

            ('fishing_length_col', 'Промыс.длина, см: *'), ('head_length_col', 'Длина гол., см:'),

            ('girth_col', 'Обхват, см:'), ('body_height_col', 'Наиб. Высота, см:'),

            ('dorsal_rays_col', 'Лучи СП:'), ('anal_rays_col', 'Лучи АП:'),

            ('notes_col', 'Примечание:'), ('sex_col', 'Пол:'), ('age_col', 'Возраст:')

        ]

        for key, label in cols_cfg:

            ctk.CTkLabel(scrollable, text=label).pack(anchor="w", pady=(5,0))

            var = ctk.StringVar(value="")

            combo = ctk.CTkComboBox(scrollable, variable=var, values=col_opts)

            combo.pack(fill="x", pady=(0,10))

            self.column_vars[key] = var

            self.column_combos[key] = combo

        ctk.CTkLabel(scrollable, text='* обязательные колонки', font=ctk.CTkFont(size=10, slant="italic")).pack(pady=(0,10))

        self.calculate_btn = ctk.CTkButton(scrollable, text="Рассчитать индексы", command=self.calculate_indices)

        self.calculate_btn.pack(fill="x", pady=10)

        self.reset_btn = ctk.CTkButton(scrollable, text="Сбросить все данные", command=self.reset_data, fg_color="#d9534f")

        self.reset_btn.pack(fill="x", pady=10)



        right = ctk.CTkFrame(main)

        right.pack(side="right", fill="both", expand=True, pady=10)

        ctk.CTkLabel(right, text="Результаты расчета", font=ctk.CTkFont(size=14, weight="bold")).pack(pady=10)

        self.results_info = ctk.CTkTextbox(right, height=100)

        self.results_info.pack(fill="x", pady=10)

        self.create_results_table(right)



    def create_results_table(self, parent):

        frame = ctk.CTkFrame(parent)

        frame.pack(fill="both", expand=True, pady=10)

        tree_frame = ctk.CTkFrame(frame)

        tree_frame.pack(fill="both", expand=True, pady=5)

        v_scroll = ttk.Scrollbar(tree_frame, orient="vertical")

        h_scroll = ttk.Scrollbar(tree_frame, orient="horizontal")

        self.results_tree = ttk.Treeview(tree_frame, yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set, height=20)

        v_scroll.configure(command=self.results_tree.yview)

        h_scroll.configure(command=self.results_tree.xview)

        v_scroll.pack(side="right", fill="y")

        h_scroll.pack(side="bottom", fill="x")

        self.results_tree.pack(side="left", fill="both", expand=True)



    # -- Charts

    def setup_tab4(self):

        main = ctk.CTkFrame(self.tab4)

        main.pack(fill="both", expand=True, padx=10, pady=10)

        left = ctk.CTkFrame(main, width=300)

        left.pack(side="left", fill="y", padx=(0,10), pady=10)

        left.pack_propagate(False)

        ctk.CTkLabel(left, text="Настройки", font=ctk.CTkFont(size=14, weight="bold")).pack(pady=10)

        ctk.CTkLabel(left, text="Тип графика:").pack(anchor="w", pady=(10,5))

        self.plot_type_var = ctk.StringVar(value="Длина-Живая масса")

        types = ["Длина-Живая масса","Индекс Фультона","Индекс физического развития","Относительный вес","Длинноголовость","Прогонистость"]

        self.plot_combo = ctk.CTkComboBox(left, variable=self.plot_type_var, values=types)

        self.plot_combo.pack(fill="x", pady=5)

        self.by_sex_var = ctk.BooleanVar(value=False)

        ctk.CTkCheckBox(left, text="По полу", variable=self.by_sex_var).pack(anchor="w", pady=5)

        self.by_groups_var = ctk.BooleanVar(value=False)

        ctk.CTkCheckBox(left, text="По группам (Примечание)", variable=self.by_groups_var).pack(anchor="w", pady=5)

        self.trend_var = ctk.BooleanVar(value=True)

        ctk.CTkCheckBox(left, text="Линия тренда", variable=self.trend_var).pack(anchor="w", pady=5)

        ctk.CTkLabel(left, text="Размер точек:").pack(anchor="w", pady=(10,5))

        self.point_size = ctk.IntVar(value=2)

        ctk.CTkSlider(left, from_=1, to=5, variable=self.point_size).pack(fill="x", pady=5)

        self.plot_btn = ctk.CTkButton(left, text="Построить", command=self.create_plot)

        self.plot_btn.pack(fill="x", pady=20)

        self.download_plot_btn = ctk.CTkButton(left, text="Скачать график", command=self.download_plot, state="disabled")

        self.download_plot_btn.pack(fill="x", pady=5)



        right = ctk.CTkFrame(main)

        right.pack(side="right", fill="both", expand=True, pady=10)

        ctk.CTkLabel(right, text="График", font=ctk.CTkFont(size=14, weight="bold")).pack(pady=10)

        self.plot_frame = ctk.CTkFrame(right)

        self.plot_frame.pack(fill="both", expand=True, pady=10)



    # -- Result

    def setup_tab5(self):

        main = ctk.CTkFrame(self.tab5)

        main.pack(fill="both", expand=True, padx=10, pady=10)

        ctk.CTkLabel(main, text="📊 Итоговые результаты", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)

        btn_frame = ctk.CTkFrame(main)

        btn_frame.pack(fill="x", pady=10)

        self.save_all_btn = ctk.CTkButton(btn_frame, text="Сохранить всё", command=self.save_all_results)

        self.save_all_btn.pack(side="left", padx=5)

        self.export_excel_btn = ctk.CTkButton(btn_frame, text="Экспорт Excel", command=self.download_excel)

        self.export_excel_btn.pack(side="left", padx=5)

        self.reset_data_btn = ctk.CTkButton(btn_frame, text="Сбросить", command=self.reset_data, fg_color="#d9534f")

        self.reset_data_btn.pack(side="left", padx=5)



        tabview = ctk.CTkTabview(main)

        tabview.pack(fill="both", expand=True, pady=10)

        self.stats_tab = tabview.add("Сводная статистика")

        self.reg_tab = tabview.add("Коэффициенты регрессии")

        self.create_stats_table()

        self.create_regression_table()



    def create_stats_table(self):

        frame = ctk.CTkFrame(self.stats_tab)

        frame.pack(fill="both", expand=True, pady=5)

        tree_f = ctk.CTkFrame(frame)

        tree_f.pack(fill="both", expand=True, pady=5)

        v_scroll = ttk.Scrollbar(tree_f, orient="vertical")

        h_scroll = ttk.Scrollbar(tree_f, orient="horizontal")

        self.stats_tree = ttk.Treeview(tree_f, columns=('Категория','Показатель','Значение'),

                                       yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set, height=15)

        v_scroll.configure(command=self.stats_tree.yview)

        h_scroll.configure(command=self.stats_tree.xview)

        self.stats_tree.heading('#0', text='#')

        self.stats_tree.heading('Категория', text='Категория')

        self.stats_tree.heading('Показатель', text='Показатель')

        self.stats_tree.heading('Значение', text='Значение')

        self.stats_tree.column('#0', width=40, stretch=False)

        self.stats_tree.column('Категория', width=180, stretch=True)

        self.stats_tree.column('Показатель', width=200, stretch=True)

        self.stats_tree.column('Значение', width=120, stretch=True)

        v_scroll.pack(side="right", fill="y")

        h_scroll.pack(side="bottom", fill="x")

        self.stats_tree.pack(side="left", fill="both", expand=True)



    def create_regression_table(self):

        frame = ctk.CTkFrame(self.reg_tab)

        frame.pack(fill="both", expand=True, pady=5)

        tree_f = ctk.CTkFrame(frame)

        tree_f.pack(fill="both", expand=True, pady=5)

        v_scroll = ttk.Scrollbar(tree_f, orient="vertical")

        h_scroll = ttk.Scrollbar(tree_f, orient="horizontal")

        self.reg_tree = ttk.Treeview(tree_f, yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set, height=15)

        v_scroll.configure(command=self.reg_tree.yview)

        h_scroll.configure(command=self.reg_tree.xview)

        v_scroll.pack(side="right", fill="y")

        h_scroll.pack(side="bottom", fill="x")

        self.reg_tree.pack(side="left", fill="both", expand=True)



    # -- Auxiliary methods

    def auto_adjust_columns(self, tree, columns, data_df=None, max_rows=100):

        

        tree.update_idletasks()

        for col in columns:

            max_width = 140

            header = tree.heading(col)['text']

            header_width = len(header.replace('\n', '')) * 9

            max_width = max(max_width, header_width)

            if data_df is not None and col in data_df.columns:

                sample = data_df[col].dropna().astype(str).head(max_rows)

                if len(sample) > 0:

                    data_width = max(len(val) for val in sample) * 8

                    max_width = max(max_width, data_width)

            tree.column(col, width=min(max_width, 450), stretch=True)



    def update_data_table(self):

        for item in self.data_tree.get_children():

            self.data_tree.delete(item)

        if self.analyzer.data is None:

            self.data_info_label.configure(text="Данные не загружены")

            return

        df = self.analyzer.data

        self.data_info_label.configure(text=f"Загружено: {df.shape[0]} строк × {df.shape[1]} колонок")

        cols = list(df.columns)

        self.data_tree["columns"] = cols

        for col in cols:

            self.data_tree.heading(col, text=self.wrap_text(col, 20))

        for _, row in df.head(100).iterrows():

            self.data_tree.insert("", "end", values=list(row))

        self.auto_adjust_columns(self.data_tree, cols, df)



    def update_results_table(self):

        for item in self.results_tree.get_children():

            self.results_tree.delete(item)

        if self.analyzer.clean_data is None:

            return

        data = self.analyzer.clean_data.copy()

        selected = {}

        for eng, rus in [('Number','№'), ('ChipNumber','№ чипа'), ('TubeNumber','№ пробирки'), ('Sex','Пол'), ('Notes','Примечание')]:

            if eng in data.columns:

                selected[rus] = data[eng]

        idx_map = {'FultonIndex':'Индекс Фультона','PhysicalDevelopmentIndex':'Индекс физ.развития','Относит_вес':'Относит.вес',

                   'CephalicIndex':'Длинноголовость, %','BodyShapeIndex':'Прогонистость, %'}

        for eng, rus in idx_map.items():

            if eng in data.columns:

                selected[rus] = data[eng]

        if not selected:

            rename = {'Number':'№','ChipNumber':'№ чипа','TubeNumber':'№ пробирки','Weight':'Вес, г','TotalLength':'Длина, см',

                      'FishingLength':'Промыс.длина, см','HeadLength':'Длина гол., см','Girth':'Обхват, см','BodyHeight':'Наиб. Высота, см',

                      'DorsalRays':'Лучи СП','AnalRays':'Лучи АП','FultonIndex':'Индекс Фультона','PhysicalDevelopmentIndex':'Индекс физ.развития',

                      'Относит_вес':'Относит.вес','CephalicIndex':'Длинноголовость, %','BodyShapeIndex':'Прогонистость, %','Sex':'Пол','Notes':'Примечание','Age':'Возраст'}

            data = data.rename(columns={k:v for k,v in rename.items() if k in data.columns})

            selected = {c: data[c] for c in data.columns}

        display_df = pd.DataFrame(selected)

        self.results_tree["columns"] = list(display_df.columns)

        for col in display_df.columns:

            self.results_tree.heading(col, text=self.wrap_text(col, 18))

        for _, row in display_df.iterrows():

            vals = []

            for val in row:

                if isinstance(val, float):

                    col_name = row.index[list(row).index(val)]

                    if '%' in col_name or 'индекс' in col_name.lower():

                        vals.append(round(val, 4))

                    else:

                        vals.append(round(val, 2))

                else:

                    vals.append(val)

            self.results_tree.insert("", "end", values=vals)

        self.auto_adjust_columns(self.results_tree, display_df.columns, display_df)



    def update_stats_table(self):

        for item in self.stats_tree.get_children():

            self.stats_tree.delete(item)

        if self.analyzer.clean_data is None:

            return

        stats = self.analyzer.get_summary_statistics()

        if stats is not None:

            for _, row in stats.iterrows():

                self.stats_tree.insert("", "end", values=(row['Категория'], row['Показатель'], row['Значение']))



    def update_regression_table(self):

        for item in self.reg_tree.get_children():

            self.reg_tree.delete(item)

        if self.analyzer.regression_coefficients is None:

            self.reg_tree.insert("", "end", values=("Нет данных","Требуется общая длина",""))

            return

        df = self.analyzer.regression_coefficients

        self.reg_tree["columns"] = list(df.columns)

        for col in df.columns:

            self.reg_tree.heading(col, text=self.wrap_text(col, 12))

        for _, row in df.iterrows():

            self.reg_tree.insert("", "end", values=list(row))

        self.auto_adjust_columns(self.reg_tree, df.columns, df)



    def wrap_text(self, text, max_len=15):

        words = text.split()

        lines = []

        cur = ""

        for w in words:

            if len(cur)+len(w) <= max_len:

                cur += (" " if cur else "") + w

            else:

                if cur: lines.append(cur)

                cur = w

        if cur: lines.append(cur)

        return "\n".join(lines)



    def load_file(self):

        path = filedialog.askopenfilename(filetypes=[("Excel", "*.xlsx *.xls")])

        if path:

            self.file_path_entry.delete(0, "end")

            self.file_path_entry.insert(0, path)



    def process_load_data(self):

        path = self.file_path_entry.get()

        if not path:

            messagebox.showwarning("Ошибка", "Укажите путь к файлу")

            return

        if self.analyzer.load_data(file_path=path):

            self.status_text.delete("1.0", "end")

            self.status_text.insert("1.0", f"Загружено: {self.analyzer.data.shape[0]} строк, {self.analyzer.data.shape[1]} колонок")

            self.update_columns_info()

            self.update_column_comboboxes()

            self.update_data_table()

            messagebox.showinfo("Успех", "Данные загружены")



    def update_columns_info(self):

        self.columns_text.delete("1.0", "end")

        names = ['№','№ чипа','№ пробирки','Вес, г','Длина, см','Промыс.длина, см',

                 'Длина гол., см','Обхват, см','Наиб. Высота, см','Кол-во лучей в СП',

                 'Кол-во лучей в АП','Примечание','Пол','Возраст']

        for name in names:

            col = self.analyzer.find_column(name, self.analyzer.data)

            self.columns_text.insert("end", f"{'✓' if col else '✗'} {name}: {col if col else 'не найдена'}\n")



    def update_column_comboboxes(self):

        if self.analyzer.data is not None:

            opts = [""] + list(self.analyzer.data.columns)

            for combo in self.column_combos.values():

                combo.configure(values=opts)



    def calculate_indices(self):

        if self.analyzer.data is None:

            messagebox.showwarning("Ошибка", "Сначала загрузите данные")

            return

        mapping = {k: v.get() for k, v in self.column_vars.items()}

        if not mapping['weight_col'] or not mapping['fishing_length_col']:

            messagebox.showerror("Ошибка", "Выберите колонки Вес и Промыс.длина (отмечены *)")

            return

        miss = [c for c in mapping.values() if c and c not in self.analyzer.data.columns]

        if miss:

            messagebox.showerror("Ошибка", f"Колонки не найдены: {', '.join(miss)}")

            return

        if self.analyzer.calculate_indices(mapping):

            self.results_info.delete("1.0","end")

            idx_list = ["Фультона","физ.развития","Относит.вес"]

            if 'CephalicIndex' in self.analyzer.clean_data.columns: idx_list.append("Длинноголовость")

            if 'BodyShapeIndex' in self.analyzer.clean_data.columns: idx_list.append("Прогонистость")

            self.results_info.insert("1.0", f"Расчёт завершён. Образцов: {len(self.analyzer.clean_data)}\n" +

                                     f"Пром.длина: {self.analyzer.clean_data['FishingLength'].min():.2f}-{self.analyzer.clean_data['FishingLength'].max():.2f} см\n" +

                                     f"Вес: {self.analyzer.clean_data['Weight'].min():.2f}-{self.analyzer.clean_data['Weight'].max():.2f} г\n" +

                                     f"Рассчитаны: {', '.join(idx_list)}")

            if 'TotalLength' not in self.analyzer.clean_data.columns:

                self.results_info.insert("end", "\n\nВНИМАНИЕ: нет общей длины → регрессия и график Длина-Масса недоступны")

            self.update_results_table()

            self.update_stats_table()

            self.update_regression_table()

            messagebox.showinfo("Успех", "Индексы рассчитаны")



    def create_plot(self):

        if self.analyzer.clean_data is None:

            messagebox.showwarning("Ошибка", "Сначала рассчитайте индексы")

            return

        ptype_map = {"Длина-Живая масса":"length_weight","Индекс Фультона":"fulton",

                     "Индекс физического развития":"physical","Относительный вес":"relative",

                     "Длинноголовость":"cephalic","Прогонистость":"shape"}

        ptype = ptype_map[self.plot_type_var.get()]

        fig = self.analyzer.create_plot(ptype, self.by_sex_var.get(), self.by_groups_var.get(),

                                        self.point_size.get(), self.trend_var.get())

        if fig:

            for w in self.plot_frame.winfo_children(): w.destroy()

            canvas = FigureCanvasTkAgg(fig, master=self.plot_frame)

            canvas.draw()

            canvas.get_tk_widget().pack(fill="both", expand=True)

            self.download_plot_btn.configure(state="normal")

            self.current_fig = fig



    def download_plot(self):

        if hasattr(self, 'current_fig'):

            path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG","*.png")],

                                               
initialfile=f"plot_{self.plot_type_var.get()}.png")

            if path:

                self.current_fig.savefig(path, dpi=300, bbox_inches='tight')

                messagebox.showinfo("Успех", f"График сохранён: {path}")



    def save_all_results(self):

        if self.analyzer.clean_data is None:

            messagebox.showwarning("Ошибка", "Нет данных для сохранения")

            return

        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx")],
            initialfile="биометрические_результаты.xlsx"
        )

        if not path: return

        try:

            with pd.ExcelWriter(path, engine='openpyxl') as writer:

                export = self.analyzer.clean_data.copy()

                rename = {'Number':'№','ChipNumber':'№ чипа','TubeNumber':'№ пробирки','Weight':'Вес, г','TotalLength':'Длина, см',

                          'FishingLength':'Промыс.длина, см','HeadLength':'Длина гол., см','Girth':'Обхват, см','BodyHeight':'Наиб. Высота, см',

                          'DorsalRays':'Лучи СП','AnalRays':'Лучи АП','FultonIndex':'Индекс Фультона','PhysicalDevelopmentIndex':'Индекс физ.развития',

                          'Относит_вес':'Относит.вес','CephalicIndex':'Длинноголовость, %','BodyShapeIndex':'Прогонистость, %','Sex':'Пол','Notes':'Примечание','Age':'Возраст'}

                export = export.rename(columns={k:v for k,v in rename.items() if k in export.columns})

                export.to_excel(writer, sheet_name='Данные с индексами', index=False)

                stats = self.analyzer.get_summary_statistics()

                if stats is not None:

                    stats.to_excel(writer, sheet_name='Статистика', index=False)

                if self.analyzer.regression_coefficients is not None:

                    self.analyzer.regression_coefficients.to_excel(writer, sheet_name='Регрессия', index=False)

            messagebox.showinfo("Успех", f"Результаты сохранены: {path}")

        except Exception as e:

            messagebox.showerror("Ошибка", f"Ошибка сохранения: {e}")



    def download_excel(self):

        self.save_all_results()



    def reset_data(self):

        if messagebox.askyesno("Сброс", "Удалить все данные и расчёты?"):

            self.analyzer = BiometricAnalysis()

            self.status_text.delete("1.0","end")

            self.columns_text.delete("1.0","end")

            self.results_info.delete("1.0","end")

            for tree in [self.data_tree, self.results_tree, self.stats_tree, self.reg_tree]:

                for item in tree.get_children(): tree.delete(item)

            for var in self.column_vars.values(): var.set("")

            for w in self.plot_frame.winfo_children(): w.destroy()

            self.download_plot_btn.configure(state="disabled")

            self.data_info_label.configure(text="Данные не загружены")

            messagebox.showinfo("Успех", "Данные сброшены")



if __name__ == "__main__":

    app = BiometricApp()

    app.mainloop()