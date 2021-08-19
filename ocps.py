from selenium import webdriver
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import NoSuchElementException, TimeoutException
import pandas as pd
import time
import json
from datetime import datetime
from seleniumwire import webdriver  # Import from seleniumwire


d20212022 = {'file': 'data/2021-2022-cases.csv', 'url': "http://bit.ly/COVIDdashboardOCPS",
             'cutoff': datetime.strptime("2021 August 2", "%Y %B %d")}
d20202021 = {'file': 'data/2020-2021-cases.csv', 'url': "https://app.powerbi.com/view?r=eyJrIjoiMDcyNjNlMmMtMDM1ZS00Mjg3LWI4N2MtYTFjNTJjMzhkYTc2IiwidCI6IjMwYTczNzMxLTdkNWEtNDY5My1hNGFmLTFmNWQ0ZTc0Y2E5MyIsImMiOjF9",
             'cutoff': datetime.strptime("2020 August 21", "%Y %B %d")}


class Driver:

    # This is how we identify which type of rectangle we're collecting data for
    employeeFill = "fill: rgb(18, 35, 158);"
    studentFill = "fill: rgb(230, 108, 55);"
    volFill = "fill: rgb(17, 141, 255);"

    # This is how we index into the correct graph / box on the page
    casesBox = {'title': 'Reported Confirmed Cases',
                'dateTitle': 'Date Reported'}

    def __init__(self, dataset):
        self.dataset = dataset
        options = {
            'addr': 'ocps-covid'  # Address of the machine running Selenium Wire. Explicitly use 127.0.0.1 rather than localhost if remote session is running locally.
        }
        self.driver = webdriver.Remote(
            command_executor='http://selenium-remote:4444/wd/hub',
            seleniumwire_options=options,
            desired_capabilities=DesiredCapabilities.CHROME
        )


    def get(self):
        self.driver.get(self.dataset['url'])
        self.wait()

    def wait(self):
        timeout = 30
        time.sleep(1)
        while len(self.driver.find_elements_by_class_name("circle")) != 0:
            time.sleep(1)
            timeout = timeout - 1
            if timeout == 0:
                break

    def getRectsInView(self, title, type, fill):
        series = self.driver.find_element_by_xpath(
            "//div[starts-with(@aria-label, '%s')]//*[local-name()='g' and @class='series' and @style='%s']" % (title, fill))
        rects = []
        for rect in series.find_elements_by_tag_name("rect"):
            r = {}
            r['type'] = type
            r['x'] = float(rect.get_attribute("x"))
            r['y'] = float(rect.get_attribute("y"))
            r['height'] = float(rect.get_attribute("height"))
            r['width'] = float(rect.get_attribute("width"))

            r['y_end'] = r['y']+r['height']
            r['x_end'] = r['x']+r['width']
            r['rect'] = rect

            rects.append(r)

        return rects

    def getRectValues(self, rects):
        ret = []
        for r in rects:
            r['values'] = self.getValueForRect(r)
            ret.append(r)
        return ret

    def driverMoveTo(self,element):
        # ActionChains(self.driver).move_to_element(rect['rect']).perform()
        # Found one rect that was so small the above did not display a popup, but moving a tiny bit from the corner did work..
        del self.driver.requests
        ActionChains(self.driver).move_to_element_with_offset(
            element, 2, 2).perform()
        try:
            return self.driver.wait_for_request("/public/reports/querydata",15)
        except TimeoutException:
            print("timed out waiting for request, skipping")
            return None

    def getValueForRect(self,rect,date=datetime(1900,1,1),t="Unknown"):
        print("Getting values for %s, %s"%(date,t))
        response = self.driverMoveTo(rect['rect'])
        ret=[]
        if response:
            for k,v in self.getResponse(response).items():
                d={}
                d['location']=k
                d['count']=v
                d['date']=date
                d['type']=t
                ret.append(d)
        else:
            print("Did not get response for %s, %s"%(date,t))
        return ret

    def getDatesInView(self, box):
        elements = self.driver.find_elements_by_xpath(
            "//*[div and starts-with(@aria-label, '%s')]//*[local-name()='g' and @aria-label='%s']//*[local-name()='g' and @class='tick']" % (box['title'], box['dateTitle']))
        return [self.toDatetime(x.text) for x in elements]

    def getTranslate(self, s):
        strs = s.replace('translate(', "").replace(")", "").split(",")
        return [float(strs[0]), float(strs[1])]

    def mapDateToRectsInView(self, dates, *series):
        # Get all the buckets
        buckets = set()
        for s in series:
            for b in s:
                buckets.add(b['x'])

        buckets = list(sorted(buckets))

        ret = {}
        for s in series:
            for r in s:
                date = dates[buckets.index(r['x'])]
                r['date'] = date
                if date not in ret:
                    ret[date] = []
                ret[date].append(r)
        return ret

    def toDatetime(self, s):
        cutoff = self.dataset['cutoff']
        if s == '(Blank)':
            return "1900 January 01"

        day = datetime.strptime(s, "%B %d")
        monthdaycutoff = datetime(day.year, cutoff.month, cutoff.day)
        if day >= monthdaycutoff:
            return datetime.strptime("%s %s" % (cutoff.year, s), "%Y %B %d")
        else:
            return datetime.strptime("%s %s" % (cutoff.year+1, s), "%Y %B %d")

    def hasSlider(self, box):
        try:
            self.driver.find_element_by_xpath(
                "//div[starts-with(@aria-label, '%s')]//*[local-name()='rect' and @class='overlay']" % (box['title']))
            return True
        except NoSuchElementException:
            return False

    def eachView(self, box):
        overlay = self.driver.find_element_by_xpath(
            "//div[starts-with(@aria-label, '%s')]//*[local-name()='rect' and @class='overlay']" % (box['title']))

        selection = self.driver.find_element_by_xpath(
            "//div[starts-with(@aria-label, '%s')]//*[local-name()='rect' and @class='selection']" % (box['title']))
        curX = selection.get_attribute("x")

        # Reset to the left
        while True:
            ActionChains(self.driver).move_to_element_with_offset(
                overlay, 1, 1).click().perform()
            self.wait()
            newX = selection.get_attribute("x")
            if curX == newX:
                break
            else:
                curX = newX

        yield  # Yield the first view

        # Yield on each view after until we hit the end of the scrollbar
        curX = selection.get_attribute("x")
        while True:
            ActionChains(self.driver).move_to_element_with_offset(
                overlay, overlay.size['width'], 1).click().perform()
            self.wait()
            yield
            newX = selection.get_attribute("x")
            if curX == newX:
                break
            else:
                curX = newX

    def rectToValues(self, rects):
        values = []

        for r in rects:
            for v in r['values']:
                v['date'] = r['date']
                v['type'] = r['type']
                values.append(v)

        return values

    def getAllRectsInView(self, box):
        dates = self.getDatesInView(box)
        students = self.getRectsInView(
            box['title'], "Students", self.studentFill)
        employees = self.getRectsInView(
            box['title'], "Employees", self.employeeFill)
        volunteers = self.getRectsInView(
            box['title'], "Volunteers", self.volFill)
        return self.mapDateToRectsInView(dates, students, employees, volunteers)

    def getNewDataInView(self, data, box):
        rectMap = self.getAllRectsInView(box)
        values = []
        for dRects in rectMap.values():
            for dRect in dRects:
                date = dRect['date']
                t = dRect['type']
                if not data.haveDataFor(date, t):
                    values.extend(self.getValueForRect(dRect,date,t))
        return values

    def getNewData(self, data, box):
        newData = self.getNewDataInView(data, box)
        if len(newData) > 0:
            data.addNewData(newData)

    def getAllData(self, data, box, all=False):
        if all:
            # Empty out the dataframe, but keep the columns
            data.df = data.df[0:0]
        if not self.hasSlider(box):
            self.getNewData(data, box)
        else:
            for _ in self.eachView(box):
                self.getNewData(data, box)

    def getResponse(self,response=None):
        if not response:
            for resp in self.driver.requests:
                if resp.path == "/public/reports/querydata":
                    response=resp

        rj = json.loads(response.response.body)
        del self.driver.requests
        return self.parseResult(rj)

    def parseResult(self,result_json):
        ret = {}
        for result in result_json['results']:

            data = result['result']['data']
            descriptor = data['descriptor']
            dsr = data['dsr']
            version = dsr['Version']
            for ds in dsr['DS']:
                value_dicts = ds['N']
                for ph in ds['PH']:

                    if 'DM1' in ph.keys():
                        for dm1 in ph['DM1']:
                            structures=[]
                            if 'S' in dm1.keys():
                                structure = dm1['S']
                                for i in range(len(structure)):
                                    s = structure[i]
                                    key = s['N']
                                    for d in descriptor['Select']:
                                        if d['Value']==key:
                                            if 'GroupKeys' in d:
                                                groupKeys = d['GroupKeys']
                            if 'C' in dm1.keys():
                                c = dm1['C']
                                count=1
                                if len(c) > 1:
                                    count=c[1]
                                ret[c[0]]=count
        return ret


class Data:
    """The Data class is responsible for reading and writing the data files and
    for all the data queries"""

    def __init__(self, df):
        self.df = df

    @staticmethod
    def fromDriver(data):
        return Data(Data.dfFromDriver(data))

    @staticmethod
    def dfFromDriver(data):
        df = pd.DataFrame(data)
        df['count'] = df['count'].apply(pd.to_numeric)
        return df

    @staticmethod
    def fromCsv(path):
        df = pd.read_csv(path)
        df['date'] = df['date'].apply(pd.to_datetime)
        df['count'] = df['count'].apply(pd.to_numeric)
        return Data(df)

    def haveDataFor(self, date, typ):
        return len(self.df[(self.df['type'] == typ) & (self.df['date'] == date)]) > 0

    def getNewDates(self, dates):
        timestamps = self.df['date'][self.df['date'].isin(
            dates)].unique().tolist()
        processedDates = [pd.Timestamp(x) for x in timestamps]
        ret = []
        for d in dates:
            if d not in processedDates:
                ret.append(d)
        return ret

    def toCsv(self, path):
        df = self.df
        df = self.df.sort_values(by=['date', 'type', 'location'])
        df = self.df.dropna().reset_index(drop=True)
        df.to_csv(path, index=False)

    def addNewData(self, data):
        newdata = Data.dfFromDriver(data)
        self.df = self.df.append(newdata)


if __name__ == "__main__":
    # Temporary hack. Can't seem to get docker-compose depends-on / wait working
    time.sleep(10)
    # Update the current dataset
    dataset = d20212022
    d = Driver(dataset)
    d.get()
    d.wait()
    data = Data.fromCsv(dataset['file'])
    # all=True .. looks like they may update previous dates, so my assumption 
    # that we only needed to process new dates may be wrong
    d.getAllData(data, d.casesBox, True)
    data.toCsv(dataset['file'])
