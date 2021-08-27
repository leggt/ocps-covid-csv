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

    def haveDataFor(self, dt):
        """
        Do we already have data for the given date and type?
        """
        return len(self.df[(self.df['type'] == dt['type']) & (self.df['date'] == dt['date'])]) > 0

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


class Directory:
    df = None

    nameMap = {
        'LAKE COMO K-8': 'LAKE COMO SCHOOL',
        'AUDUBON PARK K-8': 'AUDUBON PARK SCHOOL',
        'APOPKA MEMORIAL MIDDLE': 'MEMORIAL MIDDLE',
        'WHEATLEY ELEMENTARY': 'PHILLIS WHEATLEY ELEMENTARY',
        'DR. PHILLIPS HIGH': 'DR PHILLIPS HIGH',
        'DILLARD ST. ELEMENTARY': 'DILLARD STREET ELEMENTARY',
        'NORTHLAKE PARK COMMUNITY': 'NORTHLAKE PARK COMMUNITY ELEMENTARY',
        'WINTER PARK 9TH GRADE CENTER': 'WINTER PARK HIGH 9TH GRADE CENTER'
    }

    def __init__(self, dataset, data=None):
        if data is None:
            data = Data(dataset)
        self.dataset = dataset
        self.data = data
        df = pd.read_csv(dataset['directory'])
        self.df = self.mapDataToDirectory(df)

    def mapDataToDirectory(self, data_df):
        data_df.location = data_df.location.apply(
            lambda x: self.mapDirNames(x))

        return data_df.merge(self.data.df, how='left', on='location')

    def mapDirNames(self, name):
        name = name.upper()
        name = name.replace('(', '')
        name = name.replace(')', '')
        name = name.replace(" SCHOOL", "")
        name = name.replace("’", "")

        if name in self.nameMap:
            return self.nameMap[name]

        return name.strip()
