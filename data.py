from datetime import datetime

import pandas as pd


class Data:
    """The Data class is responsible for reading and writing the data files and
    for all the data queries"""

    def __init__(self, dataset):
        self.dataset = dataset
        df = pd.read_csv(dataset['file'])
        df['date'] = df['date'].apply(pd.to_datetime)
        df['count'] = df['count'].apply(pd.to_numeric)
        self.df = df

    def clearAll(self):
        self.df.drop(self.df.index, inplace=True)

    def getLatestDate(self):
        return self.df.date.max().date()

    def removeDates(self, dates):
        self.df = self.df[~(self.df['date'].isin(pd.to_datetime(dates)))]

    def removeDateTypes(self, *dts):
        for dt in dts:
            date = pd.to_datetime(dt['date'])
            t = dt['type']
            index = self.df[(self.df.date == date) & (self.df.type == t)].index
            self.df.drop(index, inplace=True)

    def haveDataFor(self, date, typ):
        """
        Do we already have data for the given date and type?
        """
        return len(self.df[(self.df['type'] == typ) & (self.df['date'] == date)]) > 0

    def toCsv(self, path):
        """
        Save the csv to path
        """
        df = self.df
        df = self.df.dropna().reset_index(drop=True)
        df = self.df.sort_values(
            by=['date', 'type', 'location'], ascending=False)
        df.to_csv(path, index=False)

    def to_df(self, data):
        df = pd.DataFrame(data)
        df['count'] = df['count'].apply(pd.to_numeric)
        return df

    def append(self, data):
        """
        Append the given data from the driver to the data we already have
        """
        if len(data) > 0:
            df = self.to_df(data)
            self.df = self.df.append(df)
