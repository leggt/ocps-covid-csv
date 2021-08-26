import json
import logging
from datetime import datetime
from datetime import timedelta
from string import Template
import requests
from data import *
import pandas as pd


logger = logging.getLogger("ocps-covid-csv")


def readFile(file, mode="r"):
    with open(file, mode) as f:
        return f.read()


def writeFile(st, file, mode="w"):
    with open(file, mode) as f:
        return f.write(st)


person_types = ['Student', 'Employee', 'Vendor/Visitor']


class Driver:
    def __init__(self, dataset, data):
        self.data = data
        self.dataset = dataset
        self.url = dataset['request_url']
        self.request = readFile("%s/request.json" % (dataset['templates']))
        self.headers = {}
        headers_str = readFile("%s/request-headers" % (dataset['templates']))
        for line in headers_str.split("\n"):
            s = line.split(":", 1)
            if len(s) == 2:
                self.headers[s[0].strip()] = s[1].strip()

    def go(self, all=False):
        if all:
            self.data.clearAll()
        for dt in self.iterAllDateTypes():
            logger.info("Getting data for %s %s" % (dt['date'], dt['type']))
            data = self.getDataFor(dt)
            if len(data) == 0:
                logger.warn("Did not get any data for %s %s" %
                            (dt['date'], dt['type']))
            else:
                self.data.append(data)

        self.data.toCsv(self.dataset['file'])

    def iterAllDateTypes(self):
        if "start_date" in self.dataset:
            start_date = self.dataset['start_date']
        else:
            start_date = datetime.today()
        for pt in person_types:
            day = datetime(start_date.year, start_date.month, start_date.day)
            while day >= self.dataset['cutoff']:
                date = datetime(day.year, day.month, day.day)
                yield {'date': date, 'type': pt}
                day = day-timedelta(days=1)

    def datetimeToQuery(self, d):
        return datetime.strftime(d, "%Y-%m-%d")

    def getDataFor(self, dt):
        src = Template(self.request)
        date = self.datetimeToQuery(dt['date'])
        m = {'date': date, 'type': dt['type']}
        js = json.loads(src.substitute(m))

        resp = requests.post(self.url, json=js, headers=self.headers)

        results = self.parseResult(json.loads(resp.text))
        ret = []
        for result in results:
            r = m.copy()
            r.update(result)
            ret.append(r)
        return ret

    def parseResult(self, result_json):
        """
        Read the result json that power bi gives us and translate it to a 
        dictionary of school -> count
        """
        ret = []
        for result in result_json['results']:
            data = result['result']['data']
            dsr = data['dsr']
            last_c = 0
            for ds in dsr['DS']:
                for ph in ds['PH']:
                    if 'DM1' in ph.keys():
                        for dm1 in ph['DM1']:
                            if 'C' in dm1.keys():
                                c = dm1['C']
                                name = c[0]
                                # They only include a count if it's different than the one before
                                if len(c) > 1:
                                    count = c[1]
                                    last_c = c[1]
                                else:
                                    count = last_c
                                res = {'location': name, 'count': count}
                                ret.append(res)
        return ret
