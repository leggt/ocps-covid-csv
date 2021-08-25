import json
import logging
import time
from datetime import datetime

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from seleniumwire import webdriver  # Import from seleniumwire

logger = logging.getLogger("ocps-covid-csv")


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
        logger.info("Initializing driver")
        self.driver = webdriver.Remote(
            command_executor='http://selenium-remote:4444/wd/hub',
            seleniumwire_options=options,
            desired_capabilities=DesiredCapabilities.CHROME
        )
        logger.info("Initializing driver complete")
        # Some elements were so tiny we couldn't click on them. This is probably a temporary hack
        self.driver.set_window_size(2000, 2000)

    def get(self):
        """
        Load the initial dataset url
        """
        url = self.dataset['url']
        logger.info("fetching url: %s" % (url))
        self.driver.get(url)
        logger.info("finished fetching url: %s" % (url))
        self.wait()

    def wait(self, timeout=30):
        """
        This watches the page for 'loading' elements and waits until they're 
        all gone, or we hit the timeout
        """
        logger.debug("waiting for page elements to fully load..")
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
        logger.debug("click see details")
        b = self.driver.find_element_by_xpath(
            "//span[@class='button-text' and text()='See Details']")
        self.driverMoveTo(b, False)
        self.wait()

    def clearRequests(self):
        logger.debug("clearing requests")
        del self.driver.requests

    def clickBack(self):
        logger.debug("click back")
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
        if s == '(Blank)':
            return datetime(1900, 1, 1)

        day = datetime.strptime(s, "%B %d")
        return Driver.applyCuttoff(self.dataset,day)

    @staticmethod
    def applyCuttoff(dataset,day):
        cutoff = dataset['cutoff']
        monthdaycutoff = datetime(day.year, cutoff.month, cutoff.day)
        if day >= monthdaycutoff:
            return datetime(cutoff.year,day.month,day.day)
        else:
            return datetime(cutoff.year+1,day.month,day.day)

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

    def refreshView(self, box):
        """Need to call this to get a fresh set of elements anytime the view changes 
        (e.g. clicking to the details and back, or scrolling the view"""
        overlay = self.driver.find_element_by_xpath(
            "//div[starts-with(@aria-label, '%s')]//*[local-name()='rect' and @class='overlay']" % (box['title']))

        selection = self.driver.find_element_by_xpath(
            "//div[starts-with(@aria-label, '%s')]//*[local-name()='rect' and @class='selection']" % (box['title']))
        curX = selection.get_attribute("x")
        return overlay, curX

    def eachView(self, box):
        """
        Iterate through each view. Returns nothing but sets up the driver to be in a state such that it shows each
        successive view within the box
        """
        # Reset to the left
        while True:
            overlay, curX = self.refreshView(box)
            ActionChains(self.driver).move_to_element_with_offset(
                overlay, 1, 1).click().perform()
            self.wait()
            _, newX = self.refreshView(box)
            if curX == newX:
                break
            else:
                curX = newX

        yield  # Yield the first view

        # Yield on each view after until we hit the end of the scrollbar
        _, curX = self.refreshView(box)
        while True:
            overlay, _ = self.refreshView(box)
            self.scrollRightOne(box)
            self.wait()
            yield
            _, newX = self.refreshView(box)
            if curX == newX:
                break
            else:
                curX = newX

    def scrollRightOne(self, box):
        """Inside of box, find the slider, and scroll right by one page"""
        overlay, _ = self.refreshView(box)
        ActionChains(self.driver).move_to_element_with_offset(
            overlay, overlay.size['width']-1, overlay.size['height']-1).click().perform()

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
        while date not in self.getDatesInView(box):
            self.scrollRightOne(box)
        series = self.getAllRectsInView(box)[date]
        return [d for d in series if d['type'] == t][0]['rect']

    def getNewDataInView(self, data, box):
        """
        Only request data for the dates / type that we do not have.
        """
        logger.debug("getting new data in view")
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

    def getNewDates(self, data, box):
        return data.newDates(self.getDatesInView(box))

    def getAllData(self, data, box, all=False):
        """
        Get all data. If all=True, then clear out whatever data we have
        and get everything
        """

        if all:
            logger.debug("Clearing all data")
            # Empty out the dataframe, but keep the columns
            data.df = data.df[0:0]

        if not self.hasSlider(box):
            new = self.getNewDataInView(data, box)
            data.addNewData(new)
        else:
            for _ in self.eachView(box):
                new = self.getNewDataInView(data, box)
                data.addNewData(new)

    def getResponse(self):
        """
        Look through all the querydata responses
        Try to parse each and return the result
        """
        logger.debug("parseing results")
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
            last_c=0
            for ds in dsr['DS']:
                for ph in ds['PH']:
                    if 'DM1' in ph.keys():
                        for dm1 in ph['DM1']:
                            if 'C' in dm1.keys():
                                c = dm1['C']
                                # They only include a count if it's different than the one before
                                if len(c) > 1:
                                    ret[c[0]] = c[1]
                                    last_c=c[1]
                                else: 
                                    ret[c[0]] = last_c
        return ret
