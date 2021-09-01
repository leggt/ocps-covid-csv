# OCPS Covid CSV


This project scrapes the Orange County (FL) Public School (OCPS) Covid [Dashboard](http://bit.ly/COVIDdashboardOCPS) into a csv file.

----------

You can grab the most up to date csv files here:
- [2021-2022-cases.csv](https://raw.githubusercontent.com/leggt/ocps-covid-csv/main/data/2021-2022-cases.csv) - Updated daily
- [2020-2021-cases.csv](https://raw.githubusercontent.com/leggt/ocps-covid-csv/main/data/2020-2021-cases.csv)
- [directory.csv](https://raw.githubusercontent.com/leggt/ocps-covid-csv/main/data/directory.csv) - csv of school name, address, and type
- [demographics.csv](https://raw.githubusercontent.com/leggt/ocps-covid-csv/main/data/demographics.csv) - csv of the data found [here](https://www.ocps.net/departments/student_enrollment/demographics). Looks like they update the data twice a month. This contains enrollment counts per school.

This page includes the source files for generating this data along with the data. The 2021-2022 school year data will be updated here daily.

## Running

The easiest way to run the project is to use the provided docker configuration. If you want to run the project yourself, clone the repository and execute:

`docker-compose up` 

This will run ocps-covid-csv, and update the 2021-2022-cases dataset.





