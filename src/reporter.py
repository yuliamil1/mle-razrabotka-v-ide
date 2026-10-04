class DataFrameReporter:
    def __init__(
        self,
        float_format='0.05f',
        percent_format='0.02%',
        include_all=False
    ):
        self.float_format = float_format
        self.percent_format = percent_format
        self.include_all = include_all

    def show_report(self, df, title=None):
        if title:
            print(title)

        print('Количество столбцов:', df.shape[1])
        print('Количество строк:', df.shape[0])

        duplicates = df.duplicated().sum()
        print('Количество дубликатов:', duplicates)
        print('Доля дубликатов:', format(duplicates / df.shape[0], self.percent_format))
        