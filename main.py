import argparse
import logging
import sys
import time
from datetime import datetime
from datetime import timedelta
import pandas as pd

from data import Data
from driver import Driver

# File = the input/output csv file.
# url = The public url for the dataset
# cuttoff = The webelements on the page did not specify a year, this was a way to know what month/day mapped to what year
d20212022 = {
    'file': 'data/2021-2022-cases.csv',
    'directory': 'data/directory.csv',
    'templates': 'templates/d20212022/',
    'dashboard_url': "http://bit.ly/COVIDdashboardOCPS",
    'request_url': 'https://wabi-us-east2-api.analysis.windows.net/public/reports/querydata?synchronous=true',
    'cutoff': datetime(2021, 8, 2)
}
d20202021 = {
    'file': 'data/2020-2021-cases.csv',
    'directory': 'data/directory.csv',
    'templates': 'templates/d20202021/',
    'dashboard_url': "https://app.powerbi.com/view?r=eyJrIjoiMDcyNjNlMmMtMDM1ZS00Mjg3LWI4N2MtYTFjNTJjMzhkYTc2IiwidCI6IjMwYTczNzMxLTdkNWEtNDY5My1hNGFmLTFmNWQ0ZTc0Y2E5MyIsImMiOjF9",
    'request_url': 'https://wabi-us-east2-api.analysis.windows.net/public/reports/querydata?synchronous=true',
    'start_date': datetime(2021, 8, 1),
    'cutoff': datetime(2020, 8, 21)
}

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

    dataset = d20212022
    # dataset = d20202021

    verbosity_map = {0: logging.WARN, 1: logging.INFO, 2: logging.DEBUG}
    log_level = verbosity_map[args.v if args.v <= 2 else 2]
    log_format = logging.Formatter('%(levelname)s - %(message)s')
    log_handler = logging.StreamHandler()
    log_handler.setLevel(log_level)
    log_handler.setFormatter(log_format)
    logger.addHandler(log_handler)
    logger.setLevel(log_level)

    data = Data(dataset)
    d = Driver(dataset, data)

    if args.nightly:
        logger.info("nightly run. Loop until new data")
        while True:
            latest_date = data.getLatestDate()
            next_date = latest_date + timedelta(days=1)
            if len(d.getDataFor({'date': next_date, 'type': 'Student'})) > 0:
                d.go(args.all)
                sys.exit()
            else:
                sleep = 5
                logger.warning(
                    "Did not find any new data, sleeping for %s minutes.." % (sleep))
                time.sleep(sleep*60)

    d.go(args.all)
