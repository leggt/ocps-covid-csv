from pdfminer.high_level import extract_pages
import pdfminer
import pandas as pd
import sys
import os


def parsePages(file):
    pages = []
    for p in extract_pages(file):
        lines = {}  # [Map of y value to [map of x value to [text]]]
        for e in p:
            if isinstance(e, pdfminer.layout.LTTextBoxHorizontal):
                # Seems to be equal for all elements on a line
                line_no = e.bbox[1]
                if line_no not in lines:
                    lines[line_no] = {}
                lines[line_no][e.bbox[0]] = e.get_text()
        pages.append(parsePage(lines))
    return pages


def parsePage(page):
    lines = []
    # For each line from top to bottom
    for l in sorted(page.keys(), reverse=True):
        line_element = page[l]
        line = []

        # For each element from left to right
        for t in sorted(line_element.keys()):
            text = line_element[t].strip()
            # Sometimes two % values ended up in the same text box
            if "%" in text:
                text = text.replace('%', '')
                text = text.split(' ')

            if isinstance(text, list):
                line.extend(text)
            else:
                line.append(text)
        lines.append(line)
    return lines


def updateDf(df, pages):
    # For every page except the last 2 summary pages
    for p in pages[:-2]:
        for l in p:
            # Only lines with 11 or 12 elements have the data we want
            if isinstance(l, list) and (len(l) == 12 or len(l) == 11):
                if len(l) == 11:
                    l.append("inf")
                append_df = pd.DataFrame([l], columns=df.columns)
                try:
                    date = pd.to_datetime(pages[0][1][0])
                except:
                    date = pd.to_datetime(pages[0][0][0].split('\n')[1])
                append_df = append_df.assign(date=date)
                cols = df.columns.tolist()[2:]  # Numeric columns
                append_df[cols] = append_df[cols].replace(
                    {',': ''}, regex=True)  # Get rid of commas in the numbers
                append_df[cols] = append_df[cols].apply(pd.to_numeric)
                df = df.append(append_df, ignore_index=True)
    return df


if __name__ == "__main__":
    for file in os.listdir("data"):
        print("Processing %s" % (file))
        f = "data/%s" % (file)
        df = pd.read_csv('../data/demographics.csv')
        pages = parsePages(f)
        df = updateDf(df, pages)
        df.to_csv('../data/demographics.csv', index=False)
