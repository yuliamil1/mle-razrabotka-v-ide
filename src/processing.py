
import os

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from statsmodels.stats.proportion import proportions_ztest


class DataProcessor:
    def __init__(self):
        self.orders_df = None
        self.currency_df = None
        self.user_profile_df = None

    # ---------------------------------------------------------
    # 1. ПОДКЛЮЧЕНИЕ К БАЗЕ ДАННЫХ
    # ---------------------------------------------------------

    def create_connection(self):
        """Создаёт подключение к базе данных через переменные .env."""

        load_dotenv(override=True)

        required_vars = [
            'DB_USER',
            'DB_PASSWORD',
            'DB_HOST',
            'DB_PORT',
            'DB_NAME'
        ]

        missing_vars = [
            var for var in required_vars
            if not os.getenv(var)
        ]

        if missing_vars:
            raise ValueError(
                f'Не найдены переменные окружения: {missing_vars}'
            )

        connection_url = URL.create(
            drivername='postgresql+psycopg2',
            username=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            host=os.getenv('DB_HOST'),
            port=int(os.getenv('DB_PORT')),
            database=os.getenv('DB_NAME')
        )

        engine = create_engine(
            connection_url,
            connect_args={'connect_timeout': 10}
        )

        return engine

    # ---------------------------------------------------------
    # 2. ЗАГРУЗКА ДАННЫХ
    # ---------------------------------------------------------

    def load_orders(self, path='data/orders.csv'):
        """Загружает данные о заказах."""

        self.orders_df = pd.read_csv(path)

        self.orders_df['order_dt'] = pd.to_datetime(
            self.orders_df['order_dt'],
            errors='coerce'
        )

        self.orders_df['order_ts'] = pd.to_datetime(
            self.orders_df['order_ts'],
            errors='coerce'
        )

        print('Данные о заказах загружены.')
        print(f'Количество строк: {len(self.orders_df)}')
        print(f'Количество столбцов: {len(self.orders_df.columns)}')

        return self.orders_df

    def load_currency(self, path='data/final_tickets_tenge_df.csv'):
        """Загружает данные о курсах валют."""

        self.currency_df = pd.read_csv(path)

        self.currency_df['data'] = pd.to_datetime(
            self.currency_df['data'],
            errors='coerce'
        )

        print('\nДанные о курсах валют загружены.')
        print(f'Количество строк: {len(self.currency_df)}')

        return self.currency_df

    # ---------------------------------------------------------
    # 3. КОНВЕРТАЦИЯ ВАЛЮТ
    # ---------------------------------------------------------

    def convert_currency(self):
        """Переводит выручку в тенге в рубли."""

        if self.orders_df is None or self.currency_df is None:
            raise ValueError(
                'Сначала необходимо загрузить заказы и курсы валют.'
            )

        orders = self.orders_df.copy()
        currency = self.currency_df.copy()

        # Приводим коды валют к единому регистру.
        orders['currency_code'] = (
            orders['currency_code']
            .astype(str)
            .str.strip()
            .str.upper()
        )

        currency['cdx'] = (
            currency['cdx']
            .astype(str)
            .str.strip()
            .str.upper()
        )

        orders['order_dt'] = pd.to_datetime(
            orders['order_dt'],
            errors='coerce'
        ).dt.normalize()

        currency['data'] = pd.to_datetime(
            currency['data'],
            errors='coerce'
        ).dt.normalize()

        orders['revenue'] = pd.to_numeric(
            orders['revenue'],
            errors='coerce'
        )

        # Проверяем распределение заказов по валютам.
        print('\nРаспределение заказов по валютам:')
        print(orders['currency_code'].value_counts(dropna=False))

        # Выбираем курс тенге.
        kzt_rates = currency[
            currency['cdx'] == 'KZT'
        ].copy()

        if kzt_rates.empty:
            raise ValueError(
                'В файле курсов не найдены данные для валюты KZT. '
                'Проверьте значения в столбце cdx.'
            )

        # Рассчитываем курс за одну единицу валюты.
        kzt_rates['rate'] = (
            pd.to_numeric(kzt_rates['curs'], errors='coerce')
            / pd.to_numeric(kzt_rates['nominal'], errors='coerce')
        )

        kzt_rates = (
            kzt_rates[['data', 'rate']]
            .dropna()
            .drop_duplicates(subset='data', keep='last')
            .sort_values('data')
        )

        # Заполняем отсутствующие даты последним доступным курсом.
        rates_series = (
            kzt_rates
            .set_index('data')['rate']
            .sort_index()
        )

        all_dates = pd.DatetimeIndex(
            orders['order_dt'].dropna().unique()
        ).union(rates_series.index)

        rates_series = (
            rates_series
            .reindex(all_dates)
            .sort_index()
            .ffill()
        )

        orders['kzt_rate'] = orders['order_dt'].map(
            rates_series
        )

        # Проверяем, что для каждого заказа в тенге найден курс.
        missing_kzt_rates = (
            (orders['currency_code'] == 'KZT')
            & orders['kzt_rate'].isna()
        )

        if missing_kzt_rates.any():
            missing_dates = (
                orders.loc[missing_kzt_rates, 'order_dt']
                .drop_duplicates()
                .head(10)
                .tolist()
            )

            raise ValueError(
                'Не удалось найти курс KZT для некоторых заказов. '
                f'Примеры дат: {missing_dates}'
            )

        # По умолчанию оставляем выручку без изменений.
        orders['revenue_rub'] = orders['revenue']

        # Конвертируем только заказы в тенге.
        kzt_mask = orders['currency_code'] == 'KZT'

        orders.loc[kzt_mask, 'revenue_rub'] = (
            orders.loc[kzt_mask, 'revenue']
            * orders.loc[kzt_mask, 'kzt_rate']
        )

        # Проверяем, что нет неизвестных валют.
        unknown_currency = ~orders['currency_code'].isin(
            ['RUB', 'KZT']
        )

        if unknown_currency.any():
            unknown_values = (
                orders.loc[unknown_currency, 'currency_code']
                .unique()
                .tolist()
            )

            raise ValueError(
                f'Обнаружены неизвестные валюты: {unknown_values}'
            )

        self.orders_df = orders

        print('\nКонвертация валют завершена.')
        print(
            'Заказов в KZT:',
            int(kzt_mask.sum())
        )
        print(
            'Заказов в RUB:',
            int((orders['currency_code'] == 'RUB').sum())
        )
        print(
            'Общая выручка в рублях:',
            round(orders['revenue_rub'].sum(), 2)
        )

        return self.orders_df

    # ---------------------------------------------------------
    # 4. ПРЕДОБРАБОТКА ДАННЫХ
    # ---------------------------------------------------------

    def preprocess_data(self):
        """Подготавливает данные к дальнейшему анализу."""

        if self.orders_df is None:
            raise ValueError('Сначала необходимо загрузить заказы.')

        self.orders_df['days_since_prev'] = pd.to_numeric(
            self.orders_df['days_since_prev'],
            errors='coerce'
        ).astype('Int64')

        self.orders_df['revenue_rub'] = pd.to_numeric(
            self.orders_df['revenue_rub'],
            errors='coerce'
        )

        print('\nПредобработка данных завершена.')
        print('\nТипы данных:')
        print(self.orders_df.dtypes)

        print('\nКоличество пропусков:')
        print(self.orders_df.isna().sum())

        return self.orders_df

    # ---------------------------------------------------------
    # 5. ФОРМИРОВАНИЕ ПРОФИЛЕЙ ПОЛЬЗОВАТЕЛЕЙ
    # ---------------------------------------------------------

    def build_user_profiles(self):
        """Формирует агрегированные профили пользователей."""

        if self.orders_df is None:
            raise ValueError('Сначала необходимо загрузить заказы.')

        orders = self.orders_df.copy()

        orders = orders.sort_values(
            ['user_id', 'order_ts']
        )

        # Рассчитываем интервалы между заказами.
        orders['days_between_orders'] = (
            orders.groupby('user_id')['order_dt']
            .diff()
            .dt.days
        )

        # Данные о первом заказе пользователя.
        first_orders = (
            orders
            .groupby('user_id', as_index=False)
            .first()[
                [
                    'user_id',
                    'order_dt',
                    'event_type_main',
                    'device_type_canonical',
                    'region_name'
                ]
            ]
            .rename(
                columns={
                    'order_dt': 'first_order_dt',
                    'event_type_main': 'first_event_type',
                    'device_type_canonical': 'first_device',
                    'region_name': 'first_region'
                }
            )
        )

        # Агрегированные показатели по каждому пользователю.
        user_agg = (
            orders
            .groupby('user_id')
            .agg(
                last_order_dt=('order_dt', 'max'),
                total_orders=('order_id', 'count'),
                avg_revenue_rub=('revenue_rub', 'mean'),
                avg_days_between=('days_between_orders', 'mean')
            )
            .reset_index()
        )

        # Объединяем таблицы.
        profiles = first_orders.merge(
            user_agg,
            on='user_id',
            how='left'
        )

        # Признак повторной покупки.
        profiles['is_two'] = (
            profiles['total_orders'] >= 2
        ).astype(int)

        self.user_profile_df = profiles

        print('\nПрофили пользователей сформированы.')
        print(f'Количество пользователей: {len(profiles)}')

        return self.user_profile_df

    # ---------------------------------------------------------
    # 6. ПРОВЕРКА ПРОФИЛЕЙ
    # ---------------------------------------------------------

    def validate_user_profiles(self):
        """Проверяет корректность сформированных профилей."""

        if self.user_profile_df is None:
            raise ValueError(
                'Сначала необходимо сформировать профили пользователей.'
            )

        profiles = self.user_profile_df

        print('\nПроверка профилей пользователей:')
        print(f'Количество строк: {len(profiles)}')

        print(
            'Количество уникальных пользователей:',
            profiles['user_id'].nunique()
        )

        print(
            'Количество дубликатов user_id:',
            profiles['user_id'].duplicated().sum()
        )

        print('\nПропуски:')
        print(profiles.isna().sum())

        print('\nОсновные статистики:')
        print(
            profiles[
                [
                    'total_orders',
                    'avg_revenue_rub',
                    'avg_days_between'
                ]
            ].describe()
        )

        return profiles

    # ---------------------------------------------------------
    # 7. РАСЧЁТ МЕТРИК И ФИЛЬТРАЦИЯ ВЫБРОСОВ
    # ---------------------------------------------------------

    def calculate_user_metrics(self):
        """Рассчитывает метрики и фильтрует выбросы по заказам."""

        if self.user_profile_df is None:
            raise ValueError(
                'Сначала необходимо сформировать профили пользователей.'
            )

        profiles = self.user_profile_df.copy()

        print('\nМетрики до фильтрации:')

        print(
            'Доля пользователей с повторными покупками:',
            round(profiles['is_two'].mean() * 100, 2),
            '%'
        )

        print('\nРаспределение количества заказов:')
        print(
            profiles['total_orders'].describe(
                percentiles=[0.25, 0.5, 0.75, 0.9, 0.95, 0.99]
            )
        )

        # Граница 99-го перцентиля.
        p99 = profiles['total_orders'].quantile(0.99)

        print(f'\n99-й перцентиль заказов: {p99}')

        before = len(profiles)

        # Исключаем пользователей с количеством заказов выше p99.
        profiles = profiles[
            profiles['total_orders'] <= p99
        ].copy()

        after = len(profiles)

        print('\nРезультаты фильтрации:')
        print(f'Пользователей до фильтрации: {before}')
        print(f'Пользователей после фильтрации: {after}')
        print(f'Удалено пользователей: {before - after}')

        print(
            'Доля повторных покупателей после фильтрации:',
            round(profiles['is_two'].mean() * 100, 2),
            '%'
        )

        self.user_profile_df = profiles

        return profiles

    # ---------------------------------------------------------
    # 8. АНАЛИЗ СЕГМЕНТОВ
    # ---------------------------------------------------------

    def analyze_segments(self):
        """Анализирует распределение пользователей по сегментам."""

        if self.user_profile_df is None:
            raise ValueError(
                'Сначала необходимо сформировать профили пользователей.'
            )

        profiles = self.user_profile_df.copy()

        def make_segment_table(column):
            result = (
                profiles
                .groupby(column, dropna=False)
                .agg(
                    users=('user_id', 'nunique'),
                    repeat_users=('is_two', 'sum'),
                    repeat_share=('is_two', 'mean')
                )
                .reset_index()
            )

            result['users_share'] = (
                result['users'] / result['users'].sum()
            )

            result = result.sort_values(
                'users',
                ascending=False
            )

            result['cum_share'] = (
                result['users_share'].cumsum()
            )

            return result

        event_stats = make_segment_table('first_event_type')
        device_stats = make_segment_table('first_device')
        region_stats = make_segment_table('first_region')

        print('\nРаспределение по типам мероприятий:')
        print(event_stats.to_string(index=False))

        print('\nРаспределение по устройствам:')
        print(device_stats.to_string(index=False))

        print('\nРаспределение по регионам:')
        print(region_stats.head(15).to_string(index=False))

        return {
            'event': event_stats,
            'device': device_stats,
            'region': region_stats
        }

    # ---------------------------------------------------------
    # 9. АНАЛИЗ ПОВТОРНЫХ ПОКУПОК ПО СЕГМЕНТАМ
    # ---------------------------------------------------------

    def analyze_returns(self, min_users=100):
        """Анализирует долю повторных покупок в разных сегментах."""

        if self.user_profile_df is None:
            raise ValueError(
                'Сначала необходимо сформировать профили пользователей.'
            )

        profiles = self.user_profile_df.copy()

        def calculate_return_share(column):
            result = (
                profiles
                .groupby(column, dropna=False)
                .agg(
                    users=('user_id', 'nunique'),
                    repeat_users=('is_two', 'sum'),
                    repeat_share=('is_two', 'mean')
                )
                .reset_index()
            )

            overall_share = profiles['is_two'].mean()

            result['diff_vs_avg_pp'] = (
                result['repeat_share'] - overall_share
            ) * 100

            result['small_sample'] = (
                result['users'] < min_users
            )

            return result.sort_values(
                'repeat_share',
                ascending=False
            )

        event_returns = calculate_return_share(
            'first_event_type'
        )

        device_returns = calculate_return_share(
            'first_device'
        )

        region_returns = calculate_return_share(
            'first_region'
        )

        print('\nПовторные покупки по типам мероприятий:')
        print(event_returns.to_string(index=False))

        print('\nПовторные покупки по устройствам:')
        print(device_returns.to_string(index=False))

        print('\nПовторные покупки по регионам:')
        print(region_returns.head(15).to_string(index=False))

        print(
            f'\nРегионов с количеством пользователей меньше {min_users}:',
            int(region_returns['small_sample'].sum())
        )

        return {
            'event': event_returns,
            'device': device_returns,
            'region': region_returns
        }

    # ---------------------------------------------------------
    # 10. ПРОВЕРКА СТАТИСТИЧЕСКИХ ГИПОТЕЗ
    # ---------------------------------------------------------

    def analyze_hypotheses(self):
        """Проверяет гипотезы о различиях в повторных покупках."""

        if self.user_profile_df is None:
            raise ValueError(
                'Сначала необходимо сформировать профили пользователей.'
            )

        profiles = self.user_profile_df.copy()

        results = {}

        # Гипотеза 1.
        # Доля повторных покупателей среди любителей спорта
        # выше, чем среди любителей концертов.

        sport = profiles[
            profiles['first_event_type'] == 'спорт'
        ]

        concerts = profiles[
            profiles['first_event_type'] == 'концерты'
        ]

        if len(sport) > 0 and len(concerts) > 0:
            counts = [
                sport['is_two'].sum(),
                concerts['is_two'].sum()
            ]

            sample_sizes = [
                len(sport),
                len(concerts)
            ]

            z_stat, p_value = proportions_ztest(
                count=counts,
                nobs=sample_sizes,
                alternative='larger'
            )

            sport_share = sport['is_two'].mean()
            concerts_share = concerts['is_two'].mean()

            results['sport_vs_concerts'] = {
                'sport_users': len(sport),
                'concert_users': len(concerts),
                'sport_repeat_share': sport_share,
                'concert_repeat_share': concerts_share,
                'difference_pp': (
                    sport_share - concerts_share
                ) * 100,
                'z_stat': z_stat,
                'p_value': p_value
            }

            print('\nГипотеза 1: спорт против концертов')
            print(
                f'Повторные покупки (спорт): {sport_share:.2%}'
            )
            print(
                f'Повторные покупки (концерты): {concerts_share:.2%}'
            )
            print(
                'Разница:',
                f'{(sport_share - concerts_share) * 100:.2f} п.п.'
            )
            print(f'p-value: {p_value:.6f}')

            if p_value < 0.05:
                print(
                    'Есть статистические основания считать, '
                    'что доля повторных покупок в спорте выше.'
                )
            else:
                print(
                    'Нет статистических оснований считать, '
                    'что доля повторных покупок в спорте выше.'
                )

        # Гипотеза 2.
        # Доля повторных покупателей в топ-10 регионов
        # выше, чем в остальных регионах.

        region_counts = (
            profiles['first_region']
            .value_counts()
        )

        top_10_regions = region_counts.head(10).index

        top_regions = profiles[
            profiles['first_region'].isin(top_10_regions)
        ]

        other_regions = profiles[
            ~profiles['first_region'].isin(top_10_regions)
        ]

        if len(top_regions) > 0 and len(other_regions) > 0:
            counts = [
                top_regions['is_two'].sum(),
                other_regions['is_two'].sum()
            ]

            sample_sizes = [
                len(top_regions),
                len(other_regions)
            ]

            z_stat, p_value = proportions_ztest(
                count=counts,
                nobs=sample_sizes,
                alternative='larger'
            )

            top_share = top_regions['is_two'].mean()
            other_share = other_regions['is_two'].mean()

            results['top_regions_vs_rest'] = {
                'top_regions_users': len(top_regions),
                'other_regions_users': len(other_regions),
                'top_regions_repeat_share': top_share,
                'other_regions_repeat_share': other_share,
                'difference_pp': (
                    top_share - other_share
                ) * 100,
                'z_stat': z_stat,
                'p_value': p_value
            }

            print('\nГипотеза 2: топ-10 регионов против остальных')
            print(
                f'Повторные покупки (топ-10): {top_share:.2%}'
            )
            print(
                f'Повторные покупки (остальные): {other_share:.2%}'
            )
            print(
                'Разница:',
                f'{(top_share - other_share) * 100:.2f} п.п.'
            )
            print(f'p-value: {p_value:.10f}')

            if p_value < 0.05:
                print(
                    'Есть статистические основания считать, '
                    'что доля повторных покупок в топ-10 регионах выше.'
                )
            else:
                print(
                    'Нет статистических оснований считать, '
                    'что доля повторных покупок в топ-10 регионах выше.'
                )

        return results

    # ---------------------------------------------------------
    # 11. АНАЛИЗ ВЫРУЧКИ ПО СТАТУСУ ПОВТОРНОЙ ПОКУПКИ
    # ---------------------------------------------------------

    def analyze_revenue_by_return_status(self):
        """Сравнивает выручку пользователей с повторными покупками
        и без них."""

        if self.user_profile_df is None:
            raise ValueError(
                'Сначала необходимо сформировать профили пользователей.'
            )

        profiles = self.user_profile_df.copy()

        result = (
            profiles
            .groupby('is_two')['avg_revenue_rub']
            .describe(
                percentiles=[0.25, 0.5, 0.75, 0.95]
            )
        )

        print('\nСредняя выручка по статусу повторной покупки:')
        print(result)

        # Рассчитываем межквартильный размах.
        for group_value in [0, 1]:
            group = profiles.loc[
                profiles['is_two'] == group_value,
                'avg_revenue_rub'
            ].dropna()

            q1 = group.quantile(0.25)
            q3 = group.quantile(0.75)
            iqr = q3 - q1

            group_name = (
                'Одна покупка'
                if group_value == 0
                else 'Две и более покупок'
            )

            print(f'\n{group_name}:')
            print(f'Количество пользователей: {len(group)}')
            print(f'Медиана выручки: {group.median():.2f}')
            print(f'Q1: {q1:.2f}')
            print(f'Q3: {q3:.2f}')
            print(f'IQR: {iqr:.2f}')

        return result

    # ---------------------------------------------------------
    # 12. АНАЛИЗ ПОВТОРНЫХ ПОКУПОК ПО ДНЮ НЕДЕЛИ
    # ---------------------------------------------------------

    def analyze_returns_by_weekday(self):
        """Анализирует повторные покупки в зависимости от дня
        недели первой покупки."""

        if self.user_profile_df is None:
            raise ValueError(
                'Сначала необходимо сформировать профили пользователей.'
            )

        profiles = self.user_profile_df.copy()

        weekday_names = {
            0: 'Понедельник',
            1: 'Вторник',
            2: 'Среда',
            3: 'Четверг',
            4: 'Пятница',
            5: 'Суббота',
            6: 'Воскресенье'
        }

        profiles['weekday_num'] = (
            profiles['first_order_dt'].dt.dayofweek
        )

        result = (
            profiles
            .groupby('weekday_num')
            .agg(
                users=('user_id', 'nunique'),
                repeat_users=('is_two', 'sum'),
                repeat_share=('is_two', 'mean')
            )
            .reset_index()
        )

        result['weekday'] = (
            result['weekday_num'].map(weekday_names)
        )

        result['users_share'] = (
            result['users'] / result['users'].sum()
        )

        overall_share = profiles['is_two'].mean()

        result['diff_vs_avg_pp'] = (
            result['repeat_share'] - overall_share
        ) * 100

        result = result.sort_values('weekday_num')

        print('\nПовторные покупки по дням недели первой покупки:')
        print(
            result[
                [
                    'weekday',
                    'users',
                    'users_share',
                    'repeat_share',
                    'diff_vs_avg_pp'
                ]
            ].to_string(index=False)
        )

        return result

    # ---------------------------------------------------------
    # 13. КОРРЕЛЯЦИОННЫЙ АНАЛИЗ
    # ---------------------------------------------------------

    def analyze_correlations(self):
        """Рассчитывает корреляции между числовыми метриками
        профилей пользователей."""

        if self.user_profile_df is None:
            raise ValueError(
                'Сначала необходимо сформировать профили пользователей.'
            )

        numeric_columns = [
            'total_orders',
            'avg_revenue_rub',
            'avg_days_between'
        ]

        available_columns = [
            column
            for column in numeric_columns
            if column in self.user_profile_df.columns
        ]

        correlation_data = (
            self.user_profile_df[available_columns]
            .corr(method='pearson')
        )

        print('\nКорреляционная матрица:')
        print(correlation_data)

        return correlation_data
