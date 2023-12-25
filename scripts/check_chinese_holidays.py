#!/usr/bin/env python
#-*- coding:utf-8 -*-

# Check if a day is offday or workday in China
# Author: Damon Guo
# Last Modified: 08/14/2023

import os
import sys
import requests
import json
import datetime
import calendar
import re
from ics import Calendar

HOLIDAYS_ICS = "https://calendars.icloud.com/holidays/cn_zh.ics"
HOLIDAYS_FILE = "chinese_holidays.json"

def parse_args():
    """
    Parses the command line arguments and returns the parsed arguments.
    Allows for optional date input. If no date is provided, today's date will be used.
    """
    import argparse
    import textwrap

    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent(
            f'''examples:
              {__file__}
              {__file__} -d 20231001
              {__file__} -d 20231008
              {__file__} -d 20231015'''
        ))
    date_str_today = datetime.date.today().strftime('%Y%m%d')
    parser.add_argument('-d', metavar='date_str', type=str, required=False, default=date_str_today,
                        help='date string, expected format: YYYYMMDD, default: date_str_today')

    return parser.parse_args()

def download_and_convert_holidays_file():
    """
    Downloads the holidays ICS file from HOLIDAYS_URL, 
    converts it to JSON format, and saves it locally.
    """
    try:
        response = requests.get(HOLIDAYS_ICS)
        response.raise_for_status()  # If the request failed, this will raise an exception

        # Parse the ICS content
        calendar = Calendar(response.text)

        # Convert ICS events to desired JSON format
        holidays_data = []
        for event in calendar.events:
            # Assuming each event has a start and end date and a name/summary.
            # Adjust as necessary based on the actual structure of the ICS file.
            entry = {
                "startDate": event.begin.strftime('%Y%m%d'),
                "endDate": event.end.strftime('%Y%m%d'),
                "summary": event.name
                # you might need additional fields here depending on your JSON structure
            }
            holidays_data.append(entry)

        # Save as JSON
        with open(HOLIDAYS_FILE, 'w') as file:
            json.dump(holidays_data, file)
        
        return True  # successful download and conversion

    except (requests.RequestException, ValueError, IOError) as e:
        print(f"ERROR: {e}")
        return False  # an error occurred

def is_valid_date_format(date_str):
    """
    Validates if the given date_str is in the format YYYYMMDD and represents a valid date.
    """
    if not re.match(r'^\d{8}$', date_str):
        return False

    try:
        datetime.datetime.strptime(date_str, "%Y%m%d")
        return True
    except ValueError:
        return False

def get_date_and_summary_from_range(start_date_str, end_date_str, summary):
    """
    Returns a dictionary of dates as keys and the given summary as values,
    for the range between start_date_str and end_date_str.
    """
    dates_dict = {}
    start_date = datetime.datetime.strptime(start_date_str, "%Y%m%d").date()
    end_date = datetime.datetime.strptime(end_date_str, "%Y%m%d").date()
    while start_date < end_date:
        date_str = start_date.strftime('%Y%m%d')
        dates_dict[date_str] = summary
        start_date += datetime.timedelta(days=1)

    return dates_dict

def load_holidays_data(holidays_file):
    """
    Loads the holidays data from the provided JSON file.
    Returns two dictionaries: offdays and workdays, 
    with dates as keys and their respective summaries as values.
    """
    with open(holidays_file, 'r') as f:
        holidays = json.load(f)

    offdays = {}
    workdays = {}
    for holiday in holidays:
        start_date_str = holiday["startDate"]
        end_date_str = holiday.get("endDate")
        summary = holiday["summary"]

        # Fill offdays and workdays dictionaries based on the holiday data
        if '休' in summary:
            if end_date_str:
                offdays.update(get_date_and_summary_from_range(start_date_str, end_date_str, summary))
            else:
                offdays[start_date_str] = summary

        if '班' in summary:
            if end_date_str:
                workdays.update(get_date_and_summary_from_range(start_date_str, end_date_str, summary))
            else:
                workdays[start_date_str] = summary

    return offdays, workdays

def date_status(date_str, offdays, workdays):
    """
    Determines the status (offday or workday) of the given date.
    Returns a tuple containing the status and its summary.
    """
    if date_str in offdays:
        return 'offday', offdays[date_str]
    elif date_str in workdays:
        return 'workday', workdays[date_str]
    else:
        is_offday = datetime.datetime.strptime(date_str, "%Y%m%d").date().weekday() in [5, 6]
        return ('offday' if is_offday else 'workday', calendar.day_name[datetime.datetime.strptime(date_str, "%Y%m%d").date().weekday()])

def main():
    """
    Main function to determine and print the status of the given date.
    """
    args = parse_args()  # Parse command line arguments

    # Validate the given date_str.
    if not is_valid_date_format(args.d):
        print(f"ERROR: Invalid date_str for '{args.d}', '-h' to show help messages")
        return 2

    # Download HOLIDAYS_ICS and convert it to HOLIDAYS_FILE if HOLIDAYS_FILE doesn't exist
    if not os.path.exists(HOLIDAYS_FILE):
        if download_and_convert_holidays_file():
            print(f"INFO: Downloaded {HOLIDAYS_ICS} and converted it to {HOLIDAYS_FILE}") 
            return 0
        else:
            return 2

    offdays, workdays = load_holidays_data('chinese_holidays.json')  # Load the holidays data
    status, summary = date_status(args.d, offdays, workdays)  # Determine the date status
    print(f"INFO: {args.d} is {status}: {summary}")  # Print the result

    return 0

if __name__ == '__main__':
    sys.exit(main())
