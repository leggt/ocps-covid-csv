import argparse
import logging
import sys
import time
from datetime import datetime

from data import Data
from driver import Driver

# File = the input/output csv file.
# url = The public url for the dataset
# cuttoff = The webelements on the page did not specify a year, this was a way to know what month/day mapped to what year
d20212022 = {'file': 'data/2021-2022-cases.csv', 'url': "http://bit.ly/COVIDdashboardOCPS",
             'cutoff': datetime.strptime("2021 August 2", "%Y %B %d")}
d20202021 = {'file': 'data/2020-2021-cases.csv', 'url': "https://app.powerbi.com/view?r=eyJrIjoiMDcyNjNlMmMtMDM1ZS00Mjg3LWI4N2MtYTFjNTJjMzhkYTc2IiwidCI6IjMwYTczNzMxLTdkNWEtNDY5My1hNGFmLTFmNWQ0ZTc0Y2E5MyIsImMiOjF9",
             'cutoff': datetime.strptime("2020 August 21", "%Y %B %d")}

logger = logging.getLogger("ocps-covid-csv")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--all", help="Refetch all data. By default only get new dates/types", action='store_true')
    parser.add_argument(
        "--nightly", help="Start a nightly run. Keep trying until we find new data", action='store_true')
    parser.add_argument('-v', action='count', default=0,
                        help="Increase verbosity. -v -vv supported")
    args = parser.parse_args()

    verbosity_map = {0: logging.WARN, 1: logging.INFO, 2: logging.DEBUG}
    log_level = verbosity_map[args.v if args.v <= 2 else 2]
    log_format = logging.Formatter('%(levelname)s - %(message)s')
    log_handler = logging.StreamHandler()
    log_handler.setLevel(log_level)
    log_handler.setFormatter(log_format)
    logger.addHandler(log_handler)
    logger.setLevel(log_level)

    dataset = d20212022

    d = Driver(dataset)
    data = Data.fromCsv(dataset['file'], dataset)

    if args.nightly:
        logger.info("nightly run. Loop until new data")
        while True:
            d.get()
            d.wait()
            if len(d.getNewDates(data, d.casesBox)) > 0:
                logger.info("Found new data, processing now..")
                d.getAllData(data, d.casesBox, args.all)
                data.toCsv(dataset['file'])
                sys.exit()
            else:
                if datetime.now().hour >= 1:
                    sleep = 5
                else:
                    sleep = 30
                logger.warning(
                    "Did not find any new data, sleeping for %s minutes.." % (sleep))
                time.sleep(sleep*60)

    if d.getAllData(data, d.casesBox, args.all):
        data.toCsv(dataset['file'])
