from selenium import webdriver
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import NoSuchElementException, TimeoutException
import pandas as pd
import time
import json
import logging
import argparse
import sys
from datetime import datetime
from seleniumwire import webdriver  # Import from seleniumwire


logger = logging.getLogger(__name__)

# File = the input/output csv file.
# url = The public url for the dataset
# cuttoff = The webelements on the page did not specify a year, this was a way to know what month/day mapped to what year
d20212022 = {'file': 'data/2021-2022-cases.csv', 'url': "http://bit.ly/COVIDdashboardOCPS",
             'cutoff': datetime.strptime("2021 August 2", "%Y %B %d")}
d20202021 = {'file': 'data/2020-2021-cases.csv', 'url': "https://app.powerbi.com/view?r=eyJrIjoiMDcyNjNlMmMtMDM1ZS00Mjg3LWI4N2MtYTFjNTJjMzhkYTc2IiwidCI6IjMwYTczNzMxLTdkNWEtNDY5My1hNGFmLTFmNWQ0ZTc0Y2E5MyIsImMiOjF9",
             'cutoff': datetime.strptime("2020 August 21", "%Y %B %d")}


class Driver:
    """
    Driver is mostly responsible for driving the website interactions through selenium
    Initialize with a dataset. d20212022 and d20202021 are two datasets defined above

    Once the first page loads, you have to hover your mouse over individual rectangles
    which causes some network requests to be sent and received.

    This driver loads the first page, and then iterates through all of the rectangles,
    moves the mouse over each one, waits for a response, and parseses it to collect the
    data.

    Development note:
    There's also a bunch of code for mapping up dates to rectangles because early on
    I was not listening for the raw response but was parsing the page elements and that
    was the only way to map dates to data. In the future this may not be necessary, we
    might be able to directly request the data we want using the same calls the page
    uses.
    """

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
            # Address of the machine running Selenium Wire. Explicitly use 127.0.0.1 rather than localhost if remote session is running locally.
            'addr': 'ocps-covid'
        }
        self.driver = webdriver.Remote(
            command_executor='http://selenium-remote:4444/wd/hub',
            seleniumwire_options=options,
            desired_capabilities=DesiredCapabilities.CHROME
        )

    def get(self):
        """
        Load the initial dataset url
        """
        self.driver.get(self.dataset['url'])
        self.wait()

    def wait(self, timeout=30):
        """
        This watches the page for 'loading' elements and waits until they're 
        all gone, or we hit the timeout
        """
        time.sleep(1)
        while len(self.driver.find_elements_by_class_name("circle")) != 0:
            time.sleep(1)
            timeout = timeout - 1
            if timeout == 0:
                break

    def getRectsInView(self, title, type, fill):
        """Find and return all the 'rect' elements of type 'fill' currently displayed in the box with the given title."""
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

    def driverMoveTo(self, element, with_offset=True):
        """
        Move the mouse to the element. Wait for a response for the expected querydata
        """
        if with_offset:
            # Found one rect that was so small the above did not display a popup, but moving a tiny bit from the corner did work..
            ActionChains(self.driver).move_to_element_with_offset(
                element, 2, 2).click().perform()
        else:
            ActionChains(self.driver).move_to_element(
                element).click().perform()

    def clickSeeDetails(self):
        b = self.driver.find_element_by_xpath(
            "//span[@class='button-text' and text()='See Details']")
        self.driverMoveTo(b, False)
        self.wait()

    def clearRequests(self):
        del self.driver.requests

    def clickBack(self):
        e = self.driver.find_element_by_xpath("//i[@title='Previous Page']")
        self.driverMoveTo(e, False)
        self.wait()

    def getValueForRect(self, rect, date=datetime(1900, 1, 1), t="Unknown"):
        """
        Get the data for the given rect
        This handles sending the request, receiving the response, and parsing the results
        """
        logger.info("Getting values for %s, %s" % (date, t))
        self.driverMoveTo(rect, False)
        self.clearRequests()
        self.clickSeeDetails()
        ret = []
        for k, v in self.getResponse().items():
            d = {}
            d['location'] = k
            d['count'] = v
            d['date'] = date
            d['type'] = t
            ret.append(d)
        if len(ret) == 0:
            logger.warning("Did not get response for %s, %s" % (date, t))
        self.clickBack()
        return ret

    def getDatesInView(self, box):
        """
        Get all of the dates displayed in x axis in the given box
        """
        elements = self.driver.find_elements_by_xpath(
            "//*[div and starts-with(@aria-label, '%s')]//*[local-name()='g' and @aria-label='%s']//*[local-name()='g' and @class='tick']" % (box['title'], box['dateTitle']))
        return [self.toDatetime(x.text) for x in elements]

    def mapDateToRectsInView(self, dates, *series):
        """
        Early on this driver scraped only the elements on the page source.
        The only way to map up all of the rects in all of the series to a
        date was to:
        Assign an index to each rect based off it's x axis value.
        Next sort the buckets by x value.
        We expect the number of buckets to match the number of given dates so map
        each (sorted) bucket to each (sorted) date.
        """
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
        """
        Translate the date the web element gives us (e.g. 'August 12')
        into a datetime. Wrap the year around the 'cutoff' in the dataset.
        """
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
        """
        Determine if the box/view has a scroll bar or not. In other words do we see all of the data or not
        """
        try:
            self.driver.find_element_by_xpath(
                "//div[starts-with(@aria-label, '%s')]//*[local-name()='rect' and @class='overlay']" % (box['title']))
            return True
        except NoSuchElementException:
            return False

    def eachView(self, box):
        """
        Iterate through each view. Returns nothing but sets up the driver to be in a state such that it shows each
        successive view within the box
        """
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

    def getAllRectsInView(self, box):
        """
        We expect separate series of students, employees, and volunteers
        Go find each, and map them up to the dates that are displayed
        at the bottom of the view.
        """
        dates = self.getDatesInView(box)
        students = self.getRectsInView(
            box['title'], "Students", self.studentFill)
        employees = self.getRectsInView(
            box['title'], "Employees", self.employeeFill)
        volunteers = self.getRectsInView(
            box['title'], "Volunteers", self.volFill)
        return self.mapDateToRectsInView(dates, students, employees, volunteers)

    def getRectFor(self, date, t, box):
        series = self.getAllRectsInView(box)[date]
        return [d for d in series if d['type'] == t][0]['rect']

    def getNewDataInView(self, data, box):
        """
        Only request data for the dates / type that we do not have.
        """
        rectMap = self.getAllRectsInView(box)
        values = []
        for dRects in rectMap.values():
            for dRect in dRects:
                date = dRect['date']
                t = dRect['type']
                if not data.haveDataFor(date, t):
                    # Now that we're clicking to another page we have to refetch the element here
                    rect = self.getRectFor(date, t, box)
                    values.extend(self.getValueForRect(rect, date, t))
        return values

    def getNewDates(self,data,box):
        return data.newDates(self.getDatesInView(box))

    def getNewData(self, data, box):
        """
        Get new data, and add it
        """
        newData = self.getNewDataInView(data, box)
        if len(newData) > 0:
            data.addNewData(newData)

    def getAllData(self, data, box, all=False):
        """
        Get all data. If all=True, then clear out whatever data we have
        and get everything
        """
        if all:
            # Empty out the dataframe, but keep the columns
            data.df = data.df[0:0]
        if not self.hasSlider(box):
            self.getNewData(data, box)
        else:
            for _ in self.eachView(box):
                self.getNewData(data, box)

    def getResponse(self):
        """
        Look through all the querydata responses
        Try to parse each and return the result
        """
        ret = {}
        for req in self.driver.requests:
            if req.path == "/public/reports/querydata":
                if req.response is not None and req.response.body is not None:
                    rj = json.loads(req.response.body)
                    ret.update(self.parseResult(rj))
        return ret

    def parseResult(self, result_json):
        """
        Read the result json that power bi gives us and translate it to a 
        dictionary of school -> count
        """
        ret = {}
        for result in result_json['results']:
            data = result['result']['data']
            dsr = data['dsr']
            for ds in dsr['DS']:
                for ph in ds['PH']:
                    if 'DM1' in ph.keys():
                        for dm1 in ph['DM1']:
                            if 'C' in dm1.keys():
                                # It seems like they don't return a count, if the count is 1
                                c = dm1['C']
                                count = 1
                                if len(c) > 1:
                                    count = c[1]
                                ret[c[0]] = count
        return ret


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

    def newDates(self,data):
        df2 = pd.DataFrame(data,columns=['date'])
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
        df = self.df.sort_values(by=['date', 'type', 'location'])
        df = self.df.dropna().reset_index(drop=True)
        df.to_csv(path, index=False)

    def addNewData(self, data):
        """
        Append the given data from the driver to the data we already have
        """
        newdata = Data.dfFromDriver(data)
        self.df = self.df.append(newdata)


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("--check",help="Only check for and return any new dates",action='store_true')
    parser.add_argument("--all",help="Refetch all data. By default only get new dates/types",action='store_true')
    parser.add_argument("--sleep",help="Sleep for x seconds before parsng (Hack to ensure selenium is up)")
    args=parser.parse_args()

    if args.sleep is not None:
        time.sleep(int(args.sleep))

    dataset = d20212022
    d = Driver(dataset)
    d.get()
    d.wait()
    data = Data.fromCsv(dataset['file'])

    if args.check:
        sh = logging.StreamHandler()
        sh.setLevel(logging.ERROR)
        logger.addHandler(sh)
        logger.setLevel(logging.ERROR)
        for date in d.getNewDates(data,d.casesBox):
            print(date.strftime("%Y-%m-%d"))
        sys.exit()

    sh = logging.StreamHandler()
    sh.setLevel(logging.INFO)
    logger.addHandler(sh)
    logger.setLevel(logging.INFO)

    d.getAllData(data, d.casesBox, args.all)
    data.toCsv(dataset['file'])
