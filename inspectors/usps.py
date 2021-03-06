#!/usr/bin/env python

from utils import utils, inspector
from bs4 import BeautifulSoup
from datetime import datetime
import logging
import os.path
import time

archive = 1998
#
# options:
#   standard since/year options for a year range to fetch from.
#
#   types - limit reports fetched to one or more types, comma-separated. e.g. "audit,testimony"
#          can include:
#             audit - Audit Reports
#             testimony - Congressional Testimony
#             press - Press Releases
#             research - Risk Analysis Research Papers
#             interactive - SARC (Interactive)
#             congress - Semiannual Report to Congress
#          defaults to
#             including audits, reports to Congress, and research
#             excluding press releases, SARC, and testimony to Congress

# The report list is not stable, so sometimes we need to fetch the same page of
# results multiple times to get everything. This constant is the maximum number
# of times we will do so.
MAX_RETRIES = 10
REPORTS_PER_PAGE = 10

def run(options):
  year_range = inspector.year_range(options, archive)

  report_types = options.get('types')
  if not report_types:
    report_types = "audit,congress,research"
  report_types = report_types.split(",")
  categories = [tup for tup in CATEGORIES if (tup[0] in report_types)]
  for category_name, category_id in categories:
    pages = get_last_page(options, category_id)

    rows_seen = set()
    pages_to_fetch = range(1, pages + 1)

    # While the reports themselves may shuffle around, the order of the dates
    # of the reports and how many of each date we see on each page will stay
    # constant. This dictionary will hold how many times we see each date.
    # We can stop retrying pages once we have as many unique reports for each
    # date as there are slots for that date.
    date_slot_counts = {}

    # This keeps track of how many unique reports we have found on each date,
    # for comparison with the numbers above.
    date_unique_report_counts = {}

    # This dict maps from a report date to a list of pages on which that date
    # was seen.
    date_to_pages = {}

    for retry in range(MAX_RETRIES):
      for page in pages_to_fetch:
        logging.debug("## Downloading %s, page %i, attempt %i" % \
                             (category_name, page, retry))
        url = url_for(options, page, category_id)
        body = utils.download(url)
        doc = BeautifulSoup(body)

        results = doc.select(".views-row")
        if not results:
          if len(doc.select(".view")[0].contents) == 3 and \
              len(doc.select(".view > .view-filters")) == 1:
            # If we only have the filter box, and no content box or "pagerer,"
            # then that just means this search returned 0 results.
            pass
          else:
            # Otherwise, there's probably something wrong with the scraper.
            raise inspector.NoReportsFoundError("USPS %s" % category_name)
        for result in results:
          if retry == 0:
            timestamp = get_timestamp(result)
            if timestamp in date_slot_counts:
              date_slot_counts[timestamp] = date_slot_counts[timestamp] + 1
            else:
              date_slot_counts[timestamp] = 1
              date_unique_report_counts[timestamp] = 0

            if timestamp in date_to_pages:
              if page not in date_to_pages[timestamp]:
                date_to_pages[timestamp].append(page)
            else:
              date_to_pages[timestamp] = [page]

          row_key = (str(result.text), result.a['href'])
          if not row_key in rows_seen:
            rows_seen.add(row_key)
            timestamp = get_timestamp(result)
            date_unique_report_counts[timestamp] = \
                date_unique_report_counts[timestamp] + 1

            report = report_from(result)
            # inefficient enforcement of --year arg, USPS doesn't support it server-side
            # TODO: change to published_on.year once it's a datetime
            if inspector.year_from(report) not in year_range:
              logging.warn("[%s] Skipping report, not in requested range." % report['report_id'])
              continue

            inspector.save_report(report)

      pages_to_fetch = set()
      for date, report_count in date_unique_report_counts.items():
        if report_count < date_slot_counts[date]:
          for page in date_to_pages[date]:
            pages_to_fetch.add(page)
      if len(pages_to_fetch) == 0:
        break
      pages_to_fetch = list(pages_to_fetch)
      pages_to_fetch.sort()

def get_last_page(options, category_id):
  url = url_for(options, 1, category_id)
  body = utils.download(url)
  doc = BeautifulSoup(body)
  return last_page_for(doc)

def get_timestamp(result):
  pieces = result.select("span span")
  if len(pieces) == 3:
    timestamp = pieces[2].text.strip()
  elif len(pieces) == 2:
    timestamp = pieces[1].text.strip()
  return timestamp

# extract fields from HTML, return dict
def report_from(result):
  report = {
    'inspector': 'usps',
    'inspector_url': 'https://uspsoig.gov/',
    'agency': 'usps',
    'agency_name': 'United States Postal Service'
  }

  pieces = result.select("span span")
  report_type = type_for(pieces[0].text.strip())

  if len(pieces) == 3:
    report['%s_id' % report_type] = pieces[1].text.strip()

  published_on = datetime.strptime(get_timestamp(result), "%m/%d/%Y")

  report['type'] = report_type
  report['published_on'] = datetime.strftime(published_on, "%Y-%m-%d")

  # if there's only one button, use that URL
  # otherwise, look for "Read Full Report" (could be first or last)
  buttons = result.select("a.apbutton")
  if len(buttons) > 1:
    link = None
    for button in buttons:
      if "Full Report" in button.text:
        link = button['href']
  elif len(buttons) == 1:
    link = buttons[0]['href']
  report['url'] = link

  # get filename, use name as report ID, extension for type
  filename = os.path.basename(link)
  report['report_id'] = os.path.splitext(filename)[0]

  report['title'] = result.select("h3")[0].text.strip()

  return report

def type_for(original_type):
  original = original_type.lower()
  if "audit" in original:
    return "audit"
  elif "testimony" in original:
    return "testimony"
  elif "press release" in original:
    return "press"
  elif "research" in original:
    return "research"
  elif "sarc" in original:
    return "interactive"
  elif "report to congress":
    return "congress"
  else:
    return None

# get the last page number, from a page of search results
# e.g. <li class="pager-item active last">of 158</li>
def last_page_for(doc):
  pagers = doc.select("li.pager-item.last")
  if len(pagers) == 0:
    return 1

  page = pagers[0].text.replace("of ", "").strip()
  if page and len(page) > 0:
    return int(page)

  # this means we're on the last page, AFAIK
  else:
    return -1


# The USPS IG only supports a "since" filter.
# So, if we get a --year, we'll use it as "since", and then
# ignore reports after parsing their data (before saving them).
# Inefficient, but more efficient than not supporting --year at all.
def url_for(options, page, category_id):
  year_range = inspector.year_range(options, archive)

  url = "https://uspsoig.gov/document-library"

  # hidden input, always the same
  url += "?type=All"

  # there's always a first year, and it defaults to current year
  datetime_since = datetime(year=year_range[0], month=1, day=1)

  # Expected date format: 2015-02-26
  usps_formatted_datetime = datetime_since.strftime("%Y-%m-%d")
  url += "&field_doc_date_value[value][date]=%s" % usps_formatted_datetime

  url += "&field_doc_cat_tid[]=%s" % category_id

  # they added this crazy thing
  annoying_prefix = "0%2C0%2C0%2C0%2C0%2C0%2C0%2C0%2C0%2C0%2C0%2C0%2C0%2C0%2C0%2C0%2C0%2C0%2C0%2C0%2C0%2C0%2C0%2C0%2C0%2C0%2C0%2C0%2C0%2C0%2C0%2C0%2C0%2C"

  # page is 0-indexed
  if page > 1:
    url += "&page=%s%i" % (annoying_prefix, (page - 1))

  # Add a cache buster, this helps once we start retrying pages
  url += "&t=%i" % int(time.time())

  return url


CATEGORIES = [
  ('audit', '1920'),
  ('testimony', '1933'),
  ('other', '3534'),
  ('press', '1921'),
  ('congress', '1923'),
  ('research', '1922'),
  ('other', '3557'),
]


utils.run(run) if (__name__ == "__main__") else None
