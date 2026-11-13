from src.processing import DataProcessor
from src.reporter import DataFrameReporter


def main():
    print('=' * 60)
    print('АНАЛИЗ ДАННЫХ ЯНДЕКС АФИША')
    print('=' * 60)

    processor = DataProcessor()
    reporter = DataFrameReporter()

    # 1. Загрузка данных
    print('\n1. ЗАГРУЗКА ДАННЫХ')
    processor.load_orders()
    processor.load_currency()

    # 2. Первичный отчёт по исходным данным
    print('\n2. ОТЧЁТ ПО ИСХОДНЫМ ДАННЫМ')
    reporter.show_report(
        processor.orders_df,
        title='Исходные данные о заказах'
    )

    reporter.show_report(
        processor.currency_df,
        title='Данные о курсах валют'
    )

    # 3. Предобработка и конвертация валют
    print('\n3. ПРЕДОБРАБОТКА И КОНВЕРТАЦИЯ ВАЛЮТ')
    processor.convert_currency()
    processor.preprocess_data()

    # 4. Отчёт после предобработки
    print('\n4. ОТЧЁТ ПО ОБРАБОТАННЫМ ДАННЫМ')
    reporter.show_report(
        processor.orders_df,
        title='Заказы после предобработки'
    )

    # 5. Формирование профилей пользователей
    print('\n5. ФОРМИРОВАНИЕ ПРОФИЛЕЙ ПОЛЬЗОВАТЕЛЕЙ')
    processor.build_user_profiles()
    processor.validate_user_profiles()

    reporter.show_report(
        processor.user_profile_df,
        title='Профили пользователей'
    )

    # 6. Расчёт метрик и фильтрация выбросов
    print('\n6. РАСЧЁТ МЕТРИК И ФИЛЬТРАЦИЯ ВЫБРОСОВ')
    processor.calculate_user_metrics()

    # 7. Анализ сегментов пользователей
    print('\n7. АНАЛИЗ СЕГМЕНТОВ ПОЛЬЗОВАТЕЛЕЙ')
    segment_results = processor.analyze_segments()

    # 8. Анализ повторных покупок по сегментам
    print('\n8. АНАЛИЗ ПОВТОРНЫХ ПОКУПОК ПО СЕГМЕНТАМ')
    return_results = processor.analyze_returns()

    # 9. Проверка статистических гипотез
    print('\n9. ПРОВЕРКА СТАТИСТИЧЕСКИХ ГИПОТЕЗ')
    hypothesis_results = processor.analyze_hypotheses()

    # 10. Анализ средней выручки
    print('\n10. АНАЛИЗ СРЕДНЕЙ ВЫРУЧКИ')
    revenue_results = processor.analyze_revenue_by_return_status()

    # 11. Анализ повторных покупок по дням недели
    print('\n11. АНАЛИЗ ПО ДНЮ НЕДЕЛИ ПЕРВОЙ ПОКУПКИ')
    weekday_stats = processor.analyze_returns_by_weekday()

    # 12. Корреляционный анализ
    print('\n12. КОРРЕЛЯЦИОННЫЙ АНАЛИЗ')
    correlation_results = processor.analyze_correlations()

    # 13. Итоговый отчёт
    print('\n' + '=' * 60)
    print('ИТОГОВЫЙ ОТЧЁТ')
    print('=' * 60)

    print('\nКоличество пользователей после фильтрации:')
    print(len(processor.user_profile_df))

    print('\nДоля пользователей с повторными покупками:')
    print(f"{processor.user_profile_df['is_two'].mean():.2%}")

    print('\nОбщая выручка в рублях:')
    print(f"{processor.orders_df['revenue_rub'].sum():,.2f} ₽")

    print('\nАнализ по дням недели:')
    print(
        weekday_stats[
            [
                'weekday',
                'users',
                'users_share',
                'repeat_share',
                'diff_vs_avg_pp'
            ]
        ].to_string(index=False)
    )

    print('\nКорреляционная матрица:')
    print(correlation_results.to_string())

    print('\n' + '=' * 60)
    print('ОБРАБОТКА И АНАЛИЗ ДАННЫХ ЗАВЕРШЕНЫ')
    print('=' * 60)


if __name__ == '__main__':
    main()