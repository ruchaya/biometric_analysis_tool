from .common import *  # noqa: F401,F403


class BiometricAnalysis:
    # Внутренние имена признаков в clean_data
    INTERNAL_VARS = (
        'Weight', 'TotalLength', 'FishingLength', 'HeadLength',
        'Girth', 'BodyHeight', 'DorsalRays', 'AnalRays',
    )

    def __init__(self):
        self.data = None
        self.clean_data = None
        self.regression_coefficients = None
        self.current_plot = None
        self.filter_info = None
        # Кэш степенных регрессий: ключ -> результат
        self._regression_cache = {}
        # Настройки формул/регрессии
        self.fulton_length_basis = FULTON_LENGTH_DEFAULT
        self.regression_x_var = REGRESSION_X_DEFAULT
        self.regression_y_var = REGRESSION_Y_DEFAULT
        # Отброшенные при очистке строки (DataFrame) и причины
        self.rejected_data = None
        # Callback для отмены длительных операций (ставит GUI)
        self.cancel_check = None

    def _resolve_internal(self, name, column_mapping):
        """Переводит имя колонки из данных во внутреннее имя признака.

        В интерфейсе регрессия выбирается по исходным названиям колонок
        ("Длина", "Вес"), а clean_data использует внутренние имена
        ("TotalLength", "Weight"). Без этого перевода регрессия не считалась.
        """
        if not name:
            return None
        if name in self.INTERNAL_VARS:
            return name
        source_map = {
            column_mapping.get('weight_col'): 'Weight',
            column_mapping.get('total_length_col'): 'TotalLength',
            column_mapping.get('fishing_length_col'): 'FishingLength',
            column_mapping.get('head_length_col'): 'HeadLength',
            column_mapping.get('girth_col'): 'Girth',
            column_mapping.get('body_height_col'): 'BodyHeight',
            column_mapping.get('dorsal_rays_col'): 'DorsalRays',
            column_mapping.get('anal_rays_col'): 'AnalRays',
        }
        return source_map.get(name)

    def find_column(self, pattern, data, exclude=None):
        """Поиск колонки по шаблону.

        Раньше возвращалась первая колонка, содержащая подстроку, из-за чего
        "длина" могла указать на "Промыс.длина", а "пол" - на "половина".
        Теперь используется оценка совпадения (точное > с начала > вхождение)
        и учитываются исключающие слова.
        """
        patterns = [pattern] if isinstance(pattern, str) else list(pattern)
        patterns = [p.lower() for p in patterns if p]
        exclude = [e.lower() for e in (exclude or [])]

        candidates = []
        for idx, col in enumerate(data.columns):
            name = str(col).lower()
            if any(bad in name for bad in exclude):
                continue
            best_score = None
            for candidate_pattern in patterns:
                if candidate_pattern not in name:
                    continue
                if name == candidate_pattern:
                    score = 0
                elif name.startswith(candidate_pattern):
                    score = 1
                else:
                    score = 2
                if best_score is None or score < best_score:
                    best_score = score
            if best_score is None:
                continue
            candidates.append((best_score, len(name), idx, col))

        if not candidates:
            return None
        candidates.sort(key=lambda item: (item[0], item[1], item[2]))
        return candidates[0][3]
    
    @staticmethod
    def list_excel_sheets(file_path):
        """Список листов Excel-файла ([] при ошибке)."""
        try:
            with pd.ExcelFile(file_path) as book:
                return list(book.sheet_names)
        except Exception:
            logger.debug("Не удалось получить список листов %s", file_path, exc_info=True)
            return []

    @staticmethod
    def _read_csv(source, sep=None, encoding=None):
        """Чтение CSV с автоопределением разделителя и подбором кодировки."""
        encodings = [encoding] if encoding else ["utf-8-sig", "cp1251"]
        last_error = None
        for enc in encodings:
            try:
                return pd.read_csv(source, sep=sep, engine="python", encoding=enc)
            except UnicodeDecodeError as exc:
                last_error = exc
        raise last_error if last_error else ValueError("Не удалось прочитать CSV")

    def load_data(self, file_path=None, uploaded_file=None, sheet_name=None,
                  csv_sep=None, csv_encoding=None):
        """Загрузка данных из Excel (с выбором листа) или CSV.

        Ошибки пробрасываются наверх (их обрабатывает GUI).
        """
        try:
            source = uploaded_file if uploaded_file is not None else file_path
            if source is None or (isinstance(source, str) and not os.path.exists(source)):
                raise FileNotFoundError("Файл не найден или не загружен")

            name = str(source)
            ext = os.path.splitext(name)[1].lower()
            if ext == ".csv":
                self.data = self._read_csv(source, csv_sep, csv_encoding)
                source_label = name
            else:
                sheet = sheet_name if sheet_name else 0
                self.data = pd.read_excel(source, sheet_name=sheet)
                source_label = f"{name} (лист: {sheet})"

            logger.info(
                "Данные загружены: %s строк, %s колонок (%s)",
                self.data.shape[0], self.data.shape[1], source_label,
            )
            return True
        except Exception:
            logger.exception("Не удалось загрузить данные (%s)", file_path)
            raise
    
    @staticmethod
    def _to_numeric(series):
        """Приводит колонку к числам: понимает строки, пробелы и запятую как разделитель."""
        # В pandas 3.0 текстовые колонки имеют dtype "str", а не "object",
        # поэтому проверяем именно "не числовой" тип.
        if not pd.api.types.is_numeric_dtype(series):
            series = (
                series.astype(str)
                .str.strip()
                .str.replace(',', '.', regex=False)
                .replace({'': None, 'nan': None, 'None': None, '-': None})
            )
        return pd.to_numeric(series, errors='coerce')

    def calculate_indices(self, column_mapping, options=None):
        """Расчет биометрических индексов.

        options:
          fulton_length: 'fishing' | 'total' - длина для индекса Фультона;
          regression_x / regression_y - переменные регрессии.
        """
        options = options or {}
        self.fulton_length_basis = options.get('fulton_length', FULTON_LENGTH_DEFAULT)

        requested_x = options.get('regression_x')
        requested_y = options.get('regression_y')
        resolved_x = self._resolve_internal(requested_x, column_mapping)
        resolved_y = self._resolve_internal(requested_y, column_mapping)
        if requested_x and not resolved_x:
            logger.warning("Переменная регрессии X '%s' не сопоставлена, берётся %s",
                           requested_x, REGRESSION_X_DEFAULT)
        if requested_y and not resolved_y:
            logger.warning("Переменная регрессии Y '%s' не сопоставлена, берётся %s",
                           requested_y, REGRESSION_Y_DEFAULT)
        self.regression_x_var = resolved_x or REGRESSION_X_DEFAULT
        self.regression_y_var = resolved_y or REGRESSION_Y_DEFAULT

        try:
            clean_data = pd.DataFrame()
            total_rows = len(self.data)

            # Базовые колонки
            if column_mapping['number_col']:
                clean_data['Number'] = self.data[column_mapping['number_col']]
            if column_mapping['chip_col']:
                clean_data['ChipNumber'] = self.data[column_mapping['chip_col']]
            if column_mapping['tube_col']:
                clean_data['TubeNumber'] = self.data[column_mapping['tube_col']]

            clean_data['Weight'] = self._to_numeric(self.data[column_mapping['weight_col']])
            clean_data['FishingLength'] = self._to_numeric(self.data[column_mapping['fishing_length_col']])
            # Длина, см не обязательна: если не указана, используем промысловую длину.
            if column_mapping['total_length_col']:
                clean_data['TotalLength'] = self._to_numeric(self.data[column_mapping['total_length_col']])
            else:
                clean_data['TotalLength'] = clean_data['FishingLength']

            # Дополнительные колонки
            if column_mapping['head_length_col']:
                clean_data['HeadLength'] = self._to_numeric(self.data[column_mapping['head_length_col']])
            if column_mapping['girth_col']:
                clean_data['Girth'] = self._to_numeric(self.data[column_mapping['girth_col']])
            if column_mapping['body_height_col']:
                clean_data['BodyHeight'] = self._to_numeric(self.data[column_mapping['body_height_col']])
            if column_mapping['dorsal_rays_col']:
                clean_data['DorsalRays'] = self._to_numeric(self.data[column_mapping['dorsal_rays_col']])
            if column_mapping['anal_rays_col']:
                clean_data['AnalRays'] = self._to_numeric(self.data[column_mapping['anal_rays_col']])
            # Пол и примечание - необязательные признаки: пропуски сохраняются,
            # а не приводят к удалению строки.
            if column_mapping['sex_col']:
                clean_data['Sex'] = (
                    self.data[column_mapping['sex_col']]
                    .fillna('Не указано').astype(str).str.strip().replace('', 'Не указано')
                )
            if column_mapping['notes_col']:
                clean_data['Notes'] = (
                    self.data[column_mapping['notes_col']]
                    .fillna('Не указано').astype(str).str.strip().replace('', 'Не указано')
                )

            if self.cancel_check:
                self.cancel_check()

            # Очистка данных: обязательны только вес и промысловая длина.
            # Дополнительно помечаем причину отбраковки каждой строки.
            weight = clean_data['Weight']
            fishing = clean_data['FishingLength']
            head = clean_data.get('HeadLength')
            height = clean_data.get('BodyHeight')

            reasons = pd.Series('', index=clean_data.index, dtype=object)

            def add_reason(hit, text):
                hit = hit.fillna(False)
                empty = (reasons == '')
                reasons.loc[hit & empty] = text
                reasons.loc[hit & ~empty] = reasons.loc[hit & ~empty] + '; ' + text

            add_reason(weight.isna(), 'вес отсутствует или не число')
            add_reason(fishing.isna(), 'промысловая длина отсутствует или не число')
            add_reason(weight.notna() & (weight <= 0), 'вес ≤ 0')
            add_reason(fishing.notna() & (fishing <= 0), 'промысловая длина ≤ 0')
            if head is not None:
                add_reason(head.notna() & (head <= 0), 'длина головы ≤ 0')
            if height is not None:
                add_reason(height.notna() & (height <= 0), 'наибольшая высота ≤ 0')

            mask = (reasons == '')
            rejected = clean_data[~mask].copy()
            if not rejected.empty:
                rejected['Причина'] = reasons[~mask]
                self.rejected_data = rejected
                logger.info("Отброшено строк: %d", len(rejected))
            else:
                self.rejected_data = None

            clean_data = clean_data[mask].copy()

            self.filter_info = {
                'total': total_rows,
                'kept': len(clean_data),
                'removed': total_rows - len(clean_data),
            }

            # Расчет индексов
            fulton_length = (
                clean_data['TotalLength'] if self.fulton_length_basis == 'total'
                else clean_data['FishingLength']
            )
            clean_data['FultonIndex'] = (clean_data['Weight'] / (fulton_length ** 3)) * 100
            clean_data['PhysicalDevelopmentIndex'] = (clean_data['Weight'] * clean_data['FishingLength']) / 100
            clean_data['Относит_вес'] = (clean_data['Weight'] / clean_data['FishingLength']) * 1000

            if 'HeadLength' in clean_data.columns:
                clean_data['CephalicIndex'] = (clean_data['HeadLength'] / clean_data['FishingLength']) * 100

            if 'BodyHeight' in clean_data.columns:
                clean_data['BodyShapeIndex'] = (clean_data['FishingLength'] / clean_data['BodyHeight']) * 100

            self.clean_data = clean_data
            self.calculate_regression_coefficients()

            logger.info(
                "Индексы рассчитаны: всего %s, отфильтровано %s, осталось %s",
                self.filter_info['total'], self.filter_info['removed'], self.filter_info['kept'],
            )
            return True

        except Exception:
            logger.exception("Ошибка расчета индексов")
            raise
    
    def _regression_cache_key(self, x_values, y_values, x_var, y_var):
        """Стабильный ключ кэша по значениям выборки (без учёта порядка)."""
        x_arr = np.ascontiguousarray(x_values, dtype=np.float64)
        y_arr = np.ascontiguousarray(y_values, dtype=np.float64)
        # Ключ не должен зависеть от порядка строк: сортируем пары (x, y)
        order = np.lexsort((y_arr, x_arr))
        x_arr = np.ascontiguousarray(x_arr[order])
        y_arr = np.ascontiguousarray(y_arr[order])
        digest = hashlib.md5()
        digest.update(f"{x_var}|{y_var}|{len(x_arr)}".encode("utf-8"))
        digest.update(x_arr.tobytes())
        digest.update(y_arr.tobytes())
        return digest.hexdigest()

    def calculate_power_regression(self, data, x_var, y_var):
        """Степенная регрессия y = a * x^b на лог-лог данных.

        Возвращает коэффициенты, R², стандартные ошибки, 95% доверительные
        интервалы, p-value наклона и данные для доверительной полосы.
        Результат кэшируется по значениям выборки.
        """
        if len(data) < 2:
            return None

        try:
            data = data[(data[x_var] > 0) & (data[y_var] > 0)]
            x_values = np.asarray(data[x_var], dtype=np.float64)
            y_values = np.asarray(data[y_var], dtype=np.float64)

            if len(x_values) < 2:
                return None

            cache_key = self._regression_cache_key(x_values, y_values, x_var, y_var)
            cached = self._regression_cache.get(cache_key)
            if cached is not None:
                return cached

            log_x = np.log(x_values)
            log_y = np.log(y_values)
            n = len(log_x)

            slope, intercept = np.polyfit(log_x, log_y, 1)
            b = float(slope)
            log_a = float(intercept)
            a = float(np.exp(log_a))

            predicted = log_a + b * log_x
            ss_res = float(np.sum((log_y - predicted) ** 2))
            ss_tot = float(np.sum((log_y - np.mean(log_y)) ** 2))
            r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0.0

            result = {
                'a': a,
                'b': b,
                'r_squared': r_squared,
                'n': n,
                'equation': f"y = {a:.4f} * x^{b:.4f}",
                'r2_label': f"R² = {r_squared:.4f}",
                # для доверительной полосы и проверки модели
                'log_a': log_a,
                'residual_se': None,
                'log_x_mean': float(np.mean(log_x)),
                'sxx': None,
                'df': max(n - 2, 1),
                'se_b': None,
                'se_log_a': None,
                'b_ci_low': None,
                'b_ci_high': None,
                'a_ci_low': None,
                'a_ci_high': None,
                'p_value': None,
                'p_value_b3': None,
            }

            if n > 2:
                df = n - 2
                sxx = float(np.sum((log_x - np.mean(log_x)) ** 2))
                residual_se = np.sqrt(ss_res / df) if df > 0 else 0.0
                result['df'] = df
                result['sxx'] = sxx
                result['residual_se'] = float(residual_se)

                if sxx > 0:
                    se_b = residual_se / np.sqrt(sxx)
                    se_log_a = residual_se * np.sqrt(1.0 / n + np.mean(log_x) ** 2 / sxx)
                    result['se_b'] = float(se_b)
                    result['se_log_a'] = float(se_log_a)

                    if scipy_stats is not None:
                        t_crit = float(scipy_stats.t.ppf(0.975, df))
                        result['b_ci_low'] = float(b - t_crit * se_b)
                        result['b_ci_high'] = float(b + t_crit * se_b)
                        result['a_ci_low'] = float(np.exp(log_a - t_crit * se_log_a))
                        result['a_ci_high'] = float(np.exp(log_a + t_crit * se_log_a))
                        if se_b > 0:
                            result['p_value'] = float(2 * scipy_stats.t.sf(abs(b / se_b), df))
                            # проверка изометрии: наклон против b=3 (для длина-масса)
                            result['p_value_b3'] = float(2 * scipy_stats.t.sf(abs((b - 3.0) / se_b), df))

            # Ограничиваем рост кэша
            if len(self._regression_cache) > 500:
                self._regression_cache.clear()
            self._regression_cache[cache_key] = result
            return result
        except Exception:
            logger.debug("Не удалось рассчитать регрессию %s~%s", y_var, x_var, exc_info=True)
            return None

    def power_regression_band(self, x_grid, regression):
        """95% доверительная полоса для среднего значения степенной модели."""
        if (regression is None or regression.get('residual_se') is None
                or not regression.get('sxx')):
            return None

        x_grid = np.asarray(x_grid, dtype=np.float64)
        x_grid = x_grid[x_grid > 0]
        if x_grid.size == 0:
            return None

        df = regression['df']
        s = regression['residual_se']
        xbar = regression['log_x_mean']
        sxx = regression['sxx']
        log_a = regression['log_a']
        b = regression['b']

        t_crit = float(scipy_stats.t.ppf(0.975, df)) if scipy_stats is not None else 1.96
        se_mean = s * np.sqrt(1.0 / regression['n'] + (np.log(x_grid) - xbar) ** 2 / sxx)
        fitted = log_a + b * np.log(x_grid)
        lower = np.exp(fitted - t_crit * se_mean)
        upper = np.exp(fitted + t_crit * se_mean)
        return x_grid, lower, upper

    def _draw_trendline(self, ax, x, y, plot_type, color='black', alpha=0.5, show_ci=False):
        """Рисует линию тренда той же моделью, что и подпись на графике.

        Для "Длина-Живая масса" - степенная кривая a*x^b (как в подписи),
        для остальных - линейный тренд. Раньше всегда строился квадратичный
        полином, который не соответствовал показываемой регрессии.
        При show_ci добавляется 95% доверительная полоса.
        """
        frame = pd.DataFrame({
            'x': pd.to_numeric(pd.Series(np.asarray(x)), errors='coerce'),
            'y': pd.to_numeric(pd.Series(np.asarray(y)), errors='coerce'),
        }).dropna()

        if len(frame) < 2 or frame['x'].nunique() < 2:
            return

        x_line = np.linspace(frame['x'].min(), frame['x'].max(), 100)
        if plot_type == 'length_weight':
            regression = self.calculate_power_regression(frame, 'x', 'y')
            if not regression:
                return
            ax.plot(x_line, regression['a'] * x_line ** regression['b'], color=color, alpha=alpha)
            if show_ci:
                band = self.power_regression_band(x_line, regression)
                if band is not None:
                    bx, lower, upper = band
                    ax.fill_between(bx, lower, upper, color=color, alpha=0.12, linewidth=0)
        else:
            slope, intercept = np.polyfit(frame['x'], frame['y'], 1)
            ax.plot(x_line, slope * x_line + intercept, color=color, alpha=alpha)

    @staticmethod
    def _regression_row(group, sex, regression, n):
        """Строка таблицы коэффициентов регрессии."""
        return {
            'Группа': group,
            'Пол': sex,
            'n': n,
            'Коэффициент_a': round(regression['a'], 6),
            'Коэффициент_b': round(regression['b'], 6),
            'Ст.ошибка_b': None if regression['se_b'] is None else round(regression['se_b'], 6),
            'CI_b_нижн': None if regression['b_ci_low'] is None else round(regression['b_ci_low'], 6),
            'CI_b_верх': None if regression['b_ci_high'] is None else round(regression['b_ci_high'], 6),
            'R_квадрат': round(regression['r_squared'], 6),
            'p_value': regression['p_value'],
            'p_value_b3': regression.get('p_value_b3'),
            'Уравнение': regression['equation'],
        }

    def calculate_regression_coefficients(self):
        """Расчет коэффициентов регрессии для всех комбинаций (группа/пол)."""
        coefficients_list = []

        if self.clean_data is None:
            return

        x_var = self.regression_x_var
        y_var = self.regression_y_var
        if x_var not in self.clean_data.columns or y_var not in self.clean_data.columns:
            logger.warning("Переменные регрессии %s~%s отсутствуют в данных", y_var, x_var)
            self.regression_coefficients = None
            return

        if self.cancel_check:
            self.cancel_check()

        if 'Notes' in self.clean_data.columns and 'Sex' in self.clean_data.columns:
            groups = self.clean_data['Notes'].unique()
            sexes = self.clean_data['Sex'].unique()

            for group in groups:
                group_data = self.clean_data[self.clean_data['Notes'] == group]
                for sex in sexes:
                    sex_group_data = group_data[group_data['Sex'] == sex]
                    if len(sex_group_data) >= 2:
                        regression = self.calculate_power_regression(sex_group_data, x_var, y_var)
                        if regression:
                            coefficients_list.append(
                                self._regression_row(group, sex, regression, len(sex_group_data))
                            )

        if 'Notes' in self.clean_data.columns:
            groups = self.clean_data['Notes'].unique()
            for group in groups:
                if self.cancel_check:
                    self.cancel_check()
                group_data = self.clean_data[self.clean_data['Notes'] == group]
                if len(group_data) >= 2:
                    regression = self.calculate_power_regression(group_data, x_var, y_var)
                    if regression:
                        coefficients_list.append(
                            self._regression_row(group, 'Все', regression, len(group_data))
                        )

        if 'Sex' in self.clean_data.columns:
            sexes = self.clean_data['Sex'].unique()
            for sex in sexes:
                if self.cancel_check:
                    self.cancel_check()
                sex_data = self.clean_data[self.clean_data['Sex'] == sex]
                if len(sex_data) >= 2:
                    regression = self.calculate_power_regression(sex_data, x_var, y_var)
                    if regression:
                        coefficients_list.append(
                            self._regression_row('Все', sex, regression, len(sex_data))
                        )

        if len(self.clean_data) >= 2:
            regression = self.calculate_power_regression(self.clean_data, x_var, y_var)
            if regression:
                coefficients_list.append(
                    self._regression_row('Все', 'Все', regression, len(self.clean_data))
                )

        if coefficients_list:
            self.regression_coefficients = pd.DataFrame(coefficients_list)
        else:
            self.regression_coefficients = None

    # --- корреляционный анализ -------------------------------------------------
    _ID_COLUMNS = {'Number', 'ChipNumber', 'TubeNumber'}

    def get_correlation_columns(self):
        """Числовые признаки, пригодные для корреляционного анализа."""
        if self.clean_data is None:
            return []
        numeric = self.clean_data.select_dtypes(include=[np.number])
        columns = []
        for col in numeric.columns:
            if col in self._ID_COLUMNS:
                continue
            series = numeric[col]
            if series.notna().sum() >= 2 and series.std(skipna=True) not in (0, None):
                columns.append(col)
        return columns

    def get_correlation_matrix(self, method='pearson'):
        """Матрица корреляций (r) для числовых признаков."""
        columns = self.get_correlation_columns()
        if len(columns) < 2:
            return None
        return self.clean_data[columns].corr(method=method, min_periods=3)

    def get_correlation_display(self, method='pearson'):
        """Матрица r со звёздочками значимости: * p<0.05, ** p<0.01, *** p<0.001."""
        columns = self.get_correlation_columns()
        if len(columns) < 2:
            return None

        data = self.clean_data[columns]
        corr = data.corr(method=method, min_periods=3)
        display = pd.DataFrame(index=corr.index, columns=corr.columns, dtype=object)

        for i, row_name in enumerate(columns):
            for j, col_name in enumerate(columns):
                value = corr.iloc[i, j]
                if pd.isna(value):
                    display.iloc[i, j] = "—"
                    continue
                if i == j:
                    display.iloc[i, j] = "1.00"
                    continue
                stars = ""
                if scipy_stats is not None:
                    pair = data[[row_name, col_name]].dropna()
                    if len(pair) >= 3:
                        if method == 'spearman':
                            _, p_value = scipy_stats.spearmanr(pair.iloc[:, 0], pair.iloc[:, 1])
                        else:
                            _, p_value = scipy_stats.pearsonr(pair.iloc[:, 0], pair.iloc[:, 1])
                        if p_value < 0.001:
                            stars = "***"
                        elif p_value < 0.01:
                            stars = "**"
                        elif p_value < 0.05:
                            stars = "*"
                display.iloc[i, j] = f"{value:.2f}{stars}"

        display.index = [feature_label(c) for c in display.index]
        display.columns = [feature_label(c) for c in display.columns]
        return display

    @staticmethod
    def _rename_corr(corr):
        """Русифицирует подписи строк/столбцов корреляционной матрицы."""
        renamed = corr.copy()
        renamed.index = [feature_label(c) for c in corr.index]
        renamed.columns = [feature_label(c) for c in corr.columns]
        return renamed

    @staticmethod
    def _make_figure(figsize):
        """Создаёт фигуру без pyplot.

        pyplot нельзя использовать в фоновом потоке: он обращается к Tk и
        падает с "main thread is not in main loop". Поэтому фигуры создаются
        напрямую через Figure + не-GUI canvas (Agg), а Tk-canvas подключается
        позже, уже в главном потоке.
        """
        fig = Figure(figsize=figsize)
        FigureCanvasAgg(fig)
        return fig

    def _create_correlation_plot(self):
        """Тепловая карта корреляционной матрицы."""
        corr = self.get_correlation_matrix()
        if corr is None:
            return None
        corr = self._rename_corr(corr)

        columns = list(corr.columns)
        n = len(columns)
        matrix = corr.to_numpy(dtype=float)
        size = max(6.0, 0.7 * n + 3.0)

        fig = self._make_figure((size, size))
        ax = fig.add_subplot(111)
        im = ax.imshow(matrix, cmap='coolwarm', vmin=-1, vmax=1)

        ax.set_xticks(range(n))
        ax.set_yticks(range(n))
        ax.set_xticklabels(columns, rotation=45, ha='right', fontsize=8)
        ax.set_yticklabels(columns, fontsize=8)
        ax.set_title("Корреляционная матрица (Пирсон)", fontsize=13, fontweight='bold')

        for i in range(n):
            for j in range(n):
                value = matrix[i, j]
                if np.isnan(value):
                    text, color = "—", "black"
                else:
                    text = f"{value:.2f}"
                    color = "white" if abs(value) > 0.6 else "black"
                ax.text(j, i, text, ha="center", va="center", fontsize=7, color=color)

        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="r")
        fig.tight_layout()
        return fig

    def _create_custom_plot(self, x_var, y_var, point_size, show_trendline, show_ci):
        """Произвольный график выбранных X и Y по исходным данным (степенная модель)."""
        if self.data is None:
            return None
        if (not x_var or not y_var or x_var not in self.data.columns
                or y_var not in self.data.columns):
            logger.warning("Произвольный график: не выбраны X/Y (%s, %s)", x_var, y_var)
            return None

        # X/Y выбираются по исходным колонкам, поэтому строим по self.data
        frame = pd.DataFrame({
            'x': self._to_numeric(self.data[x_var]),
            'y': self._to_numeric(self.data[y_var]),
        }).dropna()
        if frame.empty:
            logger.warning("Произвольный график: нет числовых данных для %s/%s", y_var, x_var)
            return None

        fig = self._make_figure((12, 8))
        ax = fig.add_subplot(111)
        ax.scatter(
            frame['x'], frame['y'],
            alpha=0.7, s=point_size * 20, color='blue',
        )
        if show_trendline:
            self._draw_trendline(ax, frame['x'], frame['y'], 'custom', show_ci=show_ci)

        regression = self.calculate_power_regression(frame, 'x', 'y')
        if regression:
            text = f"{regression['equation']}\nR²={regression['r_squared']:.4f}"
            if regression.get('p_value') is not None:
                text += f"\np={regression['p_value']:.3g}"
            ax.text(
                0.02, 0.98, text, transform=ax.transAxes, va='top',
                bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.8),
                fontsize=9,
            )

        ax.set_xlabel(feature_label(x_var))
        ax.set_ylabel(feature_label(y_var))
        ax.grid(True, alpha=0.3)
        ax.set_title(f"{feature_label(y_var)} от {feature_label(x_var)}", fontweight='bold')
        fig.tight_layout()
        return fig

    def create_plot(self, plot_type, by_sex=False, by_groups=False, point_size=2,
                    show_trendline=True, show_ci=True, x_var=None, y_var=None):
        """Создание графиков"""
        if self.clean_data is None:
            return None
        
        try:
            # Отпускаем предыдущую фигуру (её Tk-canvas уже уничтожен в GUI).
            # pyplot здесь не используется - только обычная сборка мусора.
            self.current_plot = None

            if plot_type == "correlation":
                fig = self._create_correlation_plot()
                self.current_plot = fig
                logger.info("Построена корреляционная матрица")
                return fig

            if plot_type == "custom":
                fig = self._create_custom_plot(x_var, y_var, point_size, show_trendline, show_ci)
                self.current_plot = fig
                logger.info("Построен произвольный график %s~%s", y_var, x_var)
                return fig

            x_label = "Длина, см"
            y_label = "Значение"
            show_power_regression = True
            
            if plot_type == "length_weight":
                x_data = self.clean_data['TotalLength']
                y_data = self.clean_data['Weight']
                y_label = "Живая масса, г"
                show_power_regression = True
                main_title = "График зависимости Длина-Живая масса"
            elif plot_type == "fulton":
                x_data = self.clean_data['FishingLength']
                y_data = self.clean_data['FultonIndex']
                y_label = "Индекс Фультона"
                show_power_regression = True
                main_title = "График индекса Фультона"
            elif plot_type == "physical":
                x_data = self.clean_data['FishingLength']
                y_data = self.clean_data['PhysicalDevelopmentIndex']
                y_label = "Индекс физ. развития"
                show_power_regression = True
                main_title = "График индекса физического развития"
            elif plot_type == "relative":
                x_data = self.clean_data['FishingLength']
                y_data = self.clean_data['Относит_вес']
                y_label = "Относит.вес"
                show_power_regression = True
                main_title = "График относительного веса"
            elif plot_type == "cephalic" and 'CephalicIndex' in self.clean_data.columns:
                x_data = self.clean_data['FishingLength']
                y_data = self.clean_data['CephalicIndex']
                y_label = "Индекс длиноголовости, %"
                show_power_regression = True
                main_title = "График индекса длиноголовости"
            elif plot_type == "shape" and 'BodyShapeIndex' in self.clean_data.columns:
                x_data = self.clean_data['FishingLength']
                y_data = self.clean_data['BodyShapeIndex']
                y_label = "Индекс прогонистости, %"
                show_power_regression = True
                main_title = "График индекса прогонистости"
            else:
                return None
            
            if by_sex and 'Sex' in self.clean_data.columns and by_groups and 'Notes' in self.clean_data.columns:
                unique_groups = self.clean_data['Notes'].unique()
                n_groups = len(unique_groups)
                
                fig = self._make_figure((5 * n_groups, 6))
                axes = fig.subplots(1, n_groups)
                if n_groups == 1:
                    axes = [axes]
                
                fig.suptitle(main_title, fontsize=16, fontweight='bold', y=0.98)
                
                for idx, group in enumerate(unique_groups):
                    group_data = self.clean_data[self.clean_data['Notes'] == group]
                    ax = axes[idx]
                    
                    sexes = group_data['Sex'].unique()
                    for sex in sexes:
                        sex_data = group_data[group_data['Sex'] == sex]
                        if plot_type == "length_weight":
                            x_plot = sex_data['TotalLength']
                            y_plot = sex_data['Weight']
                        else:
                            x_plot = sex_data['FishingLength']
                            y_plot = sex_data[y_data.name] if hasattr(y_data, 'name') else y_data
                        
                        ax.scatter(x_plot, y_plot, alpha=0.7, s=point_size*20, label=sex)
                    
                    if show_trendline:
                        x_smooth = group_data['TotalLength'] if plot_type == "length_weight" else group_data['FishingLength']
                        y_smooth = group_data['Weight'] if plot_type == "length_weight" else group_data[y_data.name] if hasattr(y_data, 'name') else y_data
                        self._draw_trendline(ax, x_smooth, y_smooth, plot_type, show_ci=show_ci)
                    
                    if plot_type == "length_weight" and show_power_regression:
                        equation_text = ""
                        for sex in sexes:
                            sex_data = group_data[group_data['Sex'] == sex]
                            if len(sex_data) >= 2:
                                regression = self.calculate_power_regression(sex_data, 'TotalLength', 'Weight')
                                if regression:
                                    equation_text += f"{sex}: {regression['equation']}\nR²={regression['r_squared']:.4f}\n\n"
                        
                        if equation_text:
                            x_range = group_data['TotalLength'].max() - group_data['TotalLength'].min()
                            y_range = group_data['Weight'].max() - group_data['Weight'].min()
                            x_pos = group_data['TotalLength'].min() + x_range * 0.02
                            y_pos = group_data['Weight'].max() - y_range * 0.1
                            
                            ax.text(x_pos, y_pos, equation_text.strip(), 
                                   bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.8),
                                   fontsize=7, verticalalignment='top')
                    
                    group_name = group
                    if len(group_name) > 20:
                        words = group_name.split()
                        lines = []
                        current_line = ""
                        for word in words:
                            if len(current_line + word) <= 20:
                                current_line += word + " "
                            else:
                                lines.append(current_line.strip())
                                current_line = word + " "
                        lines.append(current_line.strip())
                        group_name = "\n".join(lines)
                    
                    ax.set_title(group_name, fontsize=10, pad=10)
                    ax.set_xlabel(x_label, fontsize=8)
                    if idx == 0:
                        ax.set_ylabel(y_label, fontsize=8)
                    ax.legend(fontsize=7)
                    ax.grid(True, alpha=0.3)
                    ax.tick_params(axis='both', which='major', labelsize=7)
                
            elif by_groups and 'Notes' in self.clean_data.columns:
                unique_groups = self.clean_data['Notes'].unique()
                n_groups = len(unique_groups)
                
                fig = self._make_figure((5 * n_groups, 6))
                axes = fig.subplots(1, n_groups)
                if n_groups == 1:
                    axes = [axes]
                
                fig.suptitle(main_title, fontsize=16, fontweight='bold', y=0.98)
                
                for idx, group in enumerate(unique_groups):
                    group_data = self.clean_data[self.clean_data['Notes'] == group]
                    ax = axes[idx]
                    
                    x_plot = group_data['TotalLength'] if plot_type == "length_weight" else group_data['FishingLength']
                    y_plot = group_data['Weight'] if plot_type == "length_weight" else group_data[y_data.name] if hasattr(y_data, 'name') else y_data
                    
                    ax.scatter(x_plot, y_plot, alpha=0.7, s=point_size*20, color='blue')
                    
                    if show_trendline:
                        self._draw_trendline(ax, x_plot, y_plot, plot_type, show_ci=show_ci)
                    
                    if plot_type == "length_weight" and show_power_regression and len(group_data) >= 2:
                        regression = self.calculate_power_regression(group_data, 'TotalLength', 'Weight')
                        if regression:
                            x_range = x_plot.max() - x_plot.min()
                            y_range = y_plot.max() - y_plot.min()
                            x_pos = x_plot.min() + x_range * 0.02
                            y_pos = y_plot.max() - y_range * 0.15
                            
                            equation_text = f"{regression['equation']}\nR²={regression['r_squared']:.4f}"
                            ax.text(x_pos, y_pos, equation_text, 
                                   bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.8),
                                   fontsize=8, verticalalignment='top')
                    
                    group_name = group
                    if len(group_name) > 20:
                        words = group_name.split()
                        lines = []
                        current_line = ""
                        for word in words:
                            if len(current_line + word) <= 20:
                                current_line += word + " "
                            else:
                                lines.append(current_line.strip())
                                current_line = word + " "
                        lines.append(current_line.strip())
                        group_name = "\n".join(lines)
                    
                    ax.set_title(group_name, fontsize=10, pad=10)
                    ax.set_xlabel(x_label, fontsize=8)
                    if idx == 0:
                        ax.set_ylabel(y_label, fontsize=8)
                    ax.grid(True, alpha=0.3)
                    ax.tick_params(axis='both', which='major', labelsize=7)
                
            elif by_sex and 'Sex' in self.clean_data.columns:
                fig = self._make_figure((12, 8))
                ax = fig.add_subplot(111)
                sexes = self.clean_data['Sex'].unique()
                colors = ['blue', 'red', 'green', 'orange']
                
                for i, sex in enumerate(sexes):
                    sex_data = self.clean_data[self.clean_data['Sex'] == sex]
                    x_plot = sex_data['TotalLength'] if plot_type == "length_weight" else sex_data['FishingLength']
                    y_plot = sex_data['Weight'] if plot_type == "length_weight" else sex_data[y_data.name] if hasattr(y_data, 'name') else y_data
                    
                    color = colors[i % len(colors)]
                    ax.scatter(x_plot, y_plot, alpha=0.7, s=point_size*20, label=sex, color=color)
                    
                    if show_trendline:
                        x_smooth = sex_data['TotalLength'] if plot_type == "length_weight" else sex_data['FishingLength']
                        y_smooth = sex_data['Weight'] if plot_type == "length_weight" else sex_data[y_data.name] if hasattr(y_data, 'name') else y_data
                        self._draw_trendline(ax, x_smooth, y_smooth, plot_type, color=color, show_ci=show_ci)
                
                if plot_type == "length_weight" and show_power_regression:
                    equation_text = ""
                    for i, sex in enumerate(sexes):
                        sex_data = self.clean_data[self.clean_data['Sex'] == sex]
                        if len(sex_data) >= 2:
                            regression = self.calculate_power_regression(sex_data, 'TotalLength', 'Weight')
                            if regression:
                                color = colors[i % len(colors)]
                                equation_text += f"{sex}: {regression['equation']}\nR²={regression['r_squared']:.4f}\n\n"
                    
                    if equation_text:
                        x_range = x_data.max() - x_data.min()
                        y_range = y_data.max() - y_data.min()
                        x_pos = x_data.min() + x_range * 0.02
                        y_pos = y_data.max() - y_range * 0.1
                        
                        ax.text(x_pos, y_pos, equation_text.strip(), 
                               bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.8),
                               fontsize=9, verticalalignment='top')
                
                ax.legend()
                ax.set_xlabel(x_label)
                ax.set_ylabel(y_label)
                ax.grid(True, alpha=0.3)
                ax.set_title(main_title)
                
            else:
                fig = self._make_figure((12, 8))
                ax = fig.add_subplot(111)
                ax.scatter(x_data, y_data, alpha=0.7, s=point_size*20, color='blue')
                
                if show_trendline:
                    self._draw_trendline(ax, x_data, y_data, plot_type, show_ci=show_ci)
                
                if plot_type == "length_weight" and show_power_regression and len(self.clean_data) >= 2:
                    regression = self.calculate_power_regression(self.clean_data, 'TotalLength', 'Weight')
                    if regression:
                        x_range = x_data.max() - x_data.min()
                        y_range = y_data.max() - y_data.min()
                        x_pos = x_data.min() + x_range * 0.02
                        y_pos = y_data.max() - y_range * 0.1
                        
                        equation_text = f"Общая регрессия:\n{regression['equation']}\nR²={regression['r_squared']:.4f}"
                        ax.text(x_pos, y_pos, equation_text, 
                               bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.8),
                               fontsize=10, verticalalignment='top')
                
                ax.set_xlabel(x_label)
                ax.set_ylabel(y_label)
                ax.grid(True, alpha=0.3)
                ax.set_title(main_title)
            
            if by_groups or (by_sex and by_groups):
                fig.tight_layout(rect=[0, 0, 1, 0.95], h_pad=3, w_pad=3)
            else:
                fig.tight_layout()
                
            self.current_plot = fig
            logger.info("График построен: %s", plot_type)
            return fig

        except Exception:
            logger.exception("Ошибка создания графика (%s)", plot_type)
            raise
    
    # (колонка, подпись, категория)
    SUMMARY_FEATURES = [
        ('Weight', 'Вес, г', 'Входные данные'),
        ('TotalLength', 'Длина, см', 'Входные данные'),
        ('FishingLength', 'Промыс.длина, см', 'Входные данные'),
        ('HeadLength', 'Длина головы, см', 'Входные данные'),
        ('Girth', 'Обхват, см', 'Входные данные'),
        ('BodyHeight', 'Наиб. высота, см', 'Входные данные'),
        ('FultonIndex', 'Индекс Фультона', 'Биометрические индексы'),
        ('PhysicalDevelopmentIndex', 'Индекс физ.развития', 'Биометрические индексы'),
        ('Относит_вес', 'Относит.вес', 'Биометрические индексы'),
        ('CephalicIndex', 'Длинноголовость, %', 'Биометрические индексы'),
        ('BodyShapeIndex', 'Прогонистость, %', 'Биометрические индексы'),
    ]

    @staticmethod
    def _ci95(series):
        """95% доверительный интервал среднего."""
        values = pd.Series(series).dropna()
        if len(values) < 2:
            return None, None
        se = values.std(ddof=1) / np.sqrt(len(values))
        t_crit = float(scipy_stats.t.ppf(0.975, len(values) - 1)) if scipy_stats is not None else 1.96
        mean = values.mean()
        return mean - t_crit * se, mean + t_crit * se

    def get_summary_statistics(self):
        """Сводная статистика: размах, среднее, медиана, ст.откл, CV, ДИ, квартили."""
        if self.clean_data is None:
            return None

        rows = [{
            'Категория': 'Общая информация',
            'Показатель': 'Количество образцов',
            'Значение': len(self.clean_data),
        }]
        if self.rejected_data is not None:
            rows.append({
                'Категория': 'Общая информация',
                'Показатель': 'Отброшено строк',
                'Значение': len(self.rejected_data),
            })

        for col, label, category in self.SUMMARY_FEATURES:
            if col not in self.clean_data.columns:
                continue
            values = self.clean_data[col].dropna()
            if values.empty:
                continue
            ci_low, ci_high = self._ci95(values)
            mean = values.mean()
            std = values.std(ddof=1) if len(values) > 1 else None
            cv = (std / mean * 100) if (std is not None and mean) else None
            metrics = [
                ('мин', values.min()),
                ('макс', values.max()),
                ('средн', mean),
                ('медиана', values.median()),
                ('ст.откл', std),
                ('Q1', values.quantile(0.25)),
                ('Q3', values.quantile(0.75)),
                ('CV, %', cv),
                ('95% ДИ низ', ci_low),
                ('95% ДИ верх', ci_high),
            ]
            for name, value in metrics:
                rows.append({
                    'Категория': category,
                    'Показатель': f'{label} ({name})',
                    'Значение': value,
                })
        return pd.DataFrame(rows)

    def get_group_statistics(self, group_cols=('Sex', 'Notes')):
        """Описательная статистика по группам (пол / примечание)."""
        if self.clean_data is None:
            return None

        features = [col for col, _l, _c in self.SUMMARY_FEATURES if col in self.clean_data.columns]
        rows = []
        for group_col in group_cols:
            if group_col not in self.clean_data.columns:
                continue
            if self.cancel_check:
                self.cancel_check()
            for col in features:
                for group_name, subset in self.clean_data.groupby(group_col, dropna=False):
                    values = subset[col].dropna()
                    if values.empty:
                        continue
                    ci_low, ci_high = self._ci95(values)
                    rows.append({
                        'Группировка': GROUP_LABELS.get(group_col, group_col),
                        'Группа': str(group_name),
                        'Признак': feature_label(col),
                        'n': len(values),
                        'средн': values.mean(),
                        'ст.откл': values.std(ddof=1) if len(values) > 1 else None,
                        'медиана': values.median(),
                        'Q1': values.quantile(0.25),
                        'Q3': values.quantile(0.75),
                        'CI_низ': ci_low,
                        'CI_верх': ci_high,
                    })
        return pd.DataFrame(rows) if rows else None

    @staticmethod
    def _benjamini_hochberg(pvalues):
        """Поправка на множественные сравнения (Benjamini–Hochberg, FDR)."""
        pvalues = np.asarray(pvalues, dtype=float)
        n = len(pvalues)
        if n == 0:
            return pvalues
        order = np.argsort(pvalues)
        ranked = pvalues[order] * n / (np.arange(n) + 1)
        ranked = np.minimum.accumulate(ranked[::-1])[::-1]
        adjusted = np.empty(n)
        adjusted[order] = np.clip(ranked, 0, 1)
        return adjusted

    def compare_groups(self, group_cols=('Sex', 'Notes')):
        """Сравнение групп: t-тест/Манн–Уитни (2 группы) или ANOVA/Краскел (больше)."""
        if self.clean_data is None or scipy_stats is None:
            return None

        features = [col for col, _l, _c in self.SUMMARY_FEATURES if col in self.clean_data.columns]
        rows = []
        for group_col in group_cols:
            if group_col not in self.clean_data.columns:
                continue
            for col in features:
                groups = []
                for _name, subset in self.clean_data.groupby(group_col, dropna=False):
                    values = subset[col].dropna().to_numpy(dtype=float)
                    if len(values) >= 2:
                        groups.append(values)
                if len(groups) < 2:
                    continue
                tests = []
                if len(groups) == 2:
                    tests = [
                        ('t-тест Уэлча', scipy_stats.ttest_ind, {'equal_var': False}),
                        ('Манн–Уитни', scipy_stats.mannwhitneyu, {'alternative': 'two-sided'}),
                    ]
                else:
                    tests = [
                        ('ANOVA', scipy_stats.f_oneway, {}),
                        ('Краскела–Уоллиса', scipy_stats.kruskal, {}),
                    ]
                for test_name, func, kwargs in tests:
                    try:
                        stat, p_value = func(*groups, **kwargs)
                    except Exception:
                        logger.debug("Тест %s не удался для %s", test_name, col, exc_info=True)
                        continue
                    rows.append({
                        'Группировка': GROUP_LABELS.get(group_col, group_col),
                        'Признак': feature_label(col),
                        'Тест': test_name,
                        'Статистика': float(stat),
                        'p-value': float(p_value),
                    })
            if self.cancel_check:
                self.cancel_check()

        if not rows:
            return None
        result = pd.DataFrame(rows)
        result['p_adj (BH)'] = self._benjamini_hochberg(result['p-value'].to_numpy())
        result['значимо'] = np.where(result['p_adj (BH)'] < 0.05, 'да', 'нет')
        return result
