# mle-razrabotka-v-ide
# DataFrameReporter

Класс для быстрого отчёта по табличным данным (pandas DataFrame).

## Какую проблему решает

При знакомстве с новым датасетом нужно каждый раз вручную проверять одно и то же: размер таблицы, дубликаты, сводную статистику и пропуски. `DataFrameReporter` собирает всё это в один вызов `show_report` и выводит отчёт в консоль:

- количество столбцов и строк;
- количество и долю дубликатов;
- сводную статистику (`describe`, по всем столбцам при `include_all=True`);
- количество и долю пропусков во всём датафрейме.

Форматы вывода настраиваются при создании объекта: `float_format`, `percent_format`, `include_all`.

## Установка окружения

1. Клонируйте репозиторий и перейдите в его папку.
2. Создайте и активируйте виртуальное окружение:

```bash
   python -m venv venv
   # Windows (PowerShell)
   .\venv\Scripts\Activate.ps1
   # macOS / Linux
   source venv/bin/activate
```

3. Установите зависимости:

```bash
   pip install -r requirements.txt
```

4. Поместите датасет `payments.csv` в папку `data/` (папка не хранится в репозитории).

## Запуск

```bash
python main.py
```

## Пример использования класса

```python
import pandas as pd
from src.reporter import DataFrameReporter

data = pd.read_csv('data/payments.csv')
reporter = DataFrameReporter(float_format='0.02f', percent_format='0.03%', include_all=True)
reporter.show_report(data, 'Мой отчёт:')
```