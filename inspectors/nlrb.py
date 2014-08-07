#!/usr/bin/env python

import datetime
import logging
import os
import re

from bs4 import BeautifulSoup
from utils import utils, inspector

# https://www.nlrb.gov/who-we-are/inspector-general
# Oldest report: 1998

# options:
#   standard since/year options for a year range to fetch from.
#
# Notes for IG's web team:
# - Add a published date for 'OIG-F-16-12-01' on
# https://www.nlrb.gov/reports-guidance/reports/oig-audit-reports

AUDIT_REPORTS_URL = "https://www.nlrb.gov/reports-guidance/reports/oig-audit-reports"
INSPECTION_REPORTS_URL = "https://www.nlrb.gov/reports-guidance/reports/oig-inspection-reports"
SEMIANNUAL_REPORTS_URL = "https://www.nlrb.gov/reports-guidance/reports/oig-semiannual-reports"

REPORT_PUBLISHED_MAP = {
  'OIG-F-16-12-01': datetime.datetime(2011, 12, 14),
}


def run(options):
  year_range = inspector.year_range(options)

  # Pull the audit and inspections reports
  for reports_url in [AUDIT_REPORTS_URL, INSPECTION_REPORTS_URL]:
    doc = BeautifulSoup(utils.download(reports_url))
    results = doc.select("div.field-item")
    for result in results:
      report = report_from(result, year_range)
      if report:
        inspector.save_report(report)

  # Pull the semiannual reports
  doc = BeautifulSoup(utils.download(SEMIANNUAL_REPORTS_URL))
  results = doc.select("div.field-item")
  for result in results:
    report = semiannual_report_from(result, year_range)
    if report:
      inspector.save_report(report)

def report_from(result, year_range):
  link = result.find("a")
  report_url = link.get('href')
  report_id, title = link.text.split(maxsplit=1)
  report_id = report_id.rstrip(":").rstrip(",")

  title = title.strip()

  if report_id in REPORT_PUBLISHED_MAP:
    published_on = REPORT_PUBLISHED_MAP[report_id]
  else:
    published_on_text = re.findall('\((.*?)\)', title)[-1]
    try:
      published_on = datetime.datetime.strptime(published_on_text, '%B %d, %Y')
    except ValueError:
      published_on = datetime.datetime.strptime(published_on_text, '%B %Y')

  if published_on.year not in year_range:
    logging.debug("[%s] Skipping, not in requested range." % report_url)
    return

  report = {
    'inspector': 'nlrb',
    'inspector_url': "https://www.nlrb.gov/who-we-are/inspector-general",
    'agency': 'nlrb',
    'agency_name': "National Labor Relations Board",
    'report_id': report_id,
    'url': report_url,
    'title': title,
    'published_on': datetime.datetime.strftime(published_on, "%Y-%m-%d"),
  }
  return report

def semiannual_report_from(result, year_range):
  link = result.find("a")
  report_url = link.get('href')
  report_filename = report_url.split("/")[-1]
  report_id, _ = os.path.splitext(report_filename)

  title = "Semiannual report - {}".format(link.text.strip())

  published_on_text = link.text.split("-")[-1].strip()
  published_on = datetime.datetime.strptime(published_on_text, '%B %d, %Y')

  if published_on.year not in year_range:
    logging.debug("[%s] Skipping, not in requested range." % report_url)
    return

  report = {
    'inspector': 'nlrb',
    'inspector_url': "https://www.nlrb.gov/who-we-are/inspector-general",
    'agency': 'nlrb',
    'agency_name': "National Labor Relations Board",
    'report_id': report_id,
    'url': report_url,
    'title': title,
    'published_on': datetime.datetime.strftime(published_on, "%Y-%m-%d"),
  }
  return report

utils.run(run) if (__name__ == "__main__") else None
