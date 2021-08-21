import pandas as pd
from datetime import datetime


class Data:
    """The Data class is responsible for reading and writing the data files and
    for all the data queries"""

    def __init__(self, df):
        self.df = df

    @staticmethod
    def dfFromDriver(data):
        """
        Translate driver data (a python list of dictionary values)
        into a pandas dataframe and return it
        """
        df = pd.DataFrame(data)
        df['count'] = df['count'].apply(pd.to_numeric)
        return df

    @staticmethod
    def fromCsv(path):
        """
        Read provided csv file at path, translate columns to their respective types,
        and return a Data object
        """
        df = pd.read_csv(path)
        df['date'] = df['date'].apply(pd.to_datetime)
        df['count'] = df['count'].apply(pd.to_numeric)
        return Data(df)

    def newDates(self, data):
        df2 = pd.DataFrame(data, columns=['date'])
        dfnew = df2.date[~df2.date.isin(self.df.date)]
        return pd.to_datetime(dfnew.values).tolist()

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

    def addNewData(self, data):
        """
        Append the given data from the driver to the data we already have
        """
        if len(data) > 0:
            newdata = Data.dfFromDriver(data)
            self.df = self.df.append(newdata)
