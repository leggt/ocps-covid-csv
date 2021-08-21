from selenium import webdriver
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.common.action_chains import ActionChains
from seleniumwire import webdriver  # Import from seleniumwire
import pandas as pd

file = "data/directory.csv"


class Directory:
    elem_cb = None
    mid_cb = None
    high_cb = None
    checkbox_map = None
    all_b = None
    go_b = None

    def __init__(self):
        self.url = "https://schooldirectory.ocps.net/default.aspx"

        options = {
            # Address of the machine running Selenium Wire. Explicitly use 127.0.0.1 rather than localhost if remote session is running locally.
            'addr': 'ocps-covid'
        }

        print("Initializing driver..")
        self.driver = webdriver.Remote(
            command_executor='http://selenium-remote:4444/wd/hub',
            seleniumwire_options=options,
            desired_capabilities=DesiredCapabilities.CHROME
        )

        print("Getting url %s" % (self.url))
        self.driver.get(self.url)

    def refreshElements(self):
        self.elem_cb = self.driver.find_element_by_xpath(
            '//*[@id="CheckBoxListLevel_0"]')
        self.mid_cb = self.driver.find_element_by_xpath(
            '//*[@id="CheckBoxListLevel_1"]')
        self.high_cb = self.driver.find_element_by_xpath(
            '//*[@id="CheckBoxListLevel_2"]')
        self.checkbox_map = {
            "Elementary": self.elem_cb,
            "Middle": self.mid_cb,
            "High": self.high_cb,
        }
        self.all_b = self.driver.find_element_by_xpath(
            '//*[@id="RadioButtonListLetter_26"]')
        self.go_b = self.driver.find_element_by_xpath('//*[@id="ButtonGo"]')

    def click(self, element):
        ActionChains(self.driver).click(element).perform()

    def uncheckAll(self):
        for e in self.checkbox_map.values():
            if e.get_attribute("checked"):
                self.click(e)

    def refreshNext(self, type):
        self.refreshElements()
        cb = self.checkbox_map[type]
        self.uncheckAll()
        self.click(cb)
        self.click(self.all_b)
        self.click(self.go_b)

    def parsePages(self, type):
        processed = []
        ret = []
        while True:
            self.refreshNext(type)

            page_row = self.driver.find_element_by_xpath(
                "//tr[@style='color:White;background-color:#666666;height:10px;']")
            pages = page_row.find_elements_by_tag_name('a')
            current_page = page_row.find_element_by_tag_name('span').text
            print("Parsing page %s for %s" % (current_page, type))
            ret.extend(self.parsePage(type))
            processed.append(current_page)
            found_new = False
            for p in pages:
                href = p.get_attribute('href')
                num = href.split("$")[1].split("'")[0]
                if num not in processed:
                    found_new = True
                    self.click(p)
                    break
            if not found_new:
                return ret

    def parsePage(self, type):
        ret = []
        rows = self.driver.find_elements_by_xpath(
            "//table[@id='gdvSchools']/tbody/tr")
        # The last row is the page selector
        rows = rows[:-1]
        for row in rows:
            re = row.find_elements_by_xpath("td/table/tbody/tr")
            name = re[0].text
            addr = "%s %s" % (re[1].text, re[2].text)
            ret.append({'name': name, 'addr': addr, 'type': type})
        return ret

    def getAll(self):
        all = []
        for type in ['Elementary', 'Middle', 'High']:
            all.extend(self.parsePages(type))
        df = pd.DataFrame(all)
        df = df.sort_values(by=['type', 'name'])
        df.to_csv(file)


if __name__ == "__main__":
    d = Directory()
    d.getAll()
