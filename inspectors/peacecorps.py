#!/usr/bin/env python

import datetime
import logging
import os
import urllib

from bs4 import BeautifulSoup
from utils import utils, inspector

# http://www.peacecorps.gov/about/inspgen/
archive = 1989

# options:
#   standard since/year options for a year range to fetch from.
#
# Notes for IG's web team:
#

REPORTS_URL = "http://www.peacecorps.gov/about/inspgen/reports/"

REPORT_PUBLISHED_MAPPING = {
  "Death_Inquiry_and_Assessment_of_Medical_Care_in_Peace_Corps_Morocco": datetime.datetime(2010,2,1),
  "Burkina_Faso_Medical_Supply_Management_Advisory_Report": datetime.datetime(2013, 3, 14),
  "PCIG_Final_MAR_Certification_of_Volunteer_Payments": datetime.datetime(2013, 9, 24),
  "MAR_Cost_Savings_Opportunity_on_Value_Added_Tax": datetime.datetime(2013, 2, 13),
  "Management_Advisory_Report-Peace_Corps_Drug_Free_Workplace_Program": datetime.datetime(2012, 8, 16),
  "PCIG_2014_Peace_Corps_OIG_Peer_Review_Final": datetime.datetime(2014, 3, 27),
  "MAR_Sierra_Leone": datetime.datetime(2013, 3, 14),
  "Capstone_Report_2012_Medical_Inventory_Issues_Final": datetime.datetime(2013, 8, 26),
  "PCIG_Capstone_Report_Billing_and_Collection_Process": datetime.datetime(2014, 9, 30),
  "PC_Morocco_Assessment_of_Medical_Care": datetime.datetime(2010, 2, 1),
  "PCIG_New_Country_Entries_Lessons_Learned_Final_Report": datetime.datetime(2014, 9, 30),
  "PC_Recurring_Issues_OIG_Post_Audits_Evaluations_FYs_2009-2011": datetime.datetime(2012, 4, 1),
  "PC_Vanuatu_SR_Advice_and_Assistance": datetime.datetime(2010, 5, 12),
  "PC_Gambia_SR_Grant_Activities": datetime.datetime(2010, 5, 14),
  "PC_Ecuador_Special_Review_IG1005SR": datetime.datetime(2010, 9, 1),
  "PCIG_Agency_Policies_Related_to_Volunteer_Sexual_Assault_Allegations": datetime.datetime(2014, 11, 21),
  "PCIG_Investigative_Review_of_a_Volunteer_Death_in_Peace_Corps_China": datetime.datetime(2014, 11, 1),
  "PCIG_Agency_Response_to_the_China_Investigative_Review_Nov_2014": datetime.datetime(2015, 1, 23),
  "PCIG_MAR_Peace_Corps_Cloud_Computing_Pilot_Program": datetime.datetime(2015, 3, 17),
  "MAR_Peace_Corps_Volunteer_Health_Care_Administration_Contract": datetime.datetime(2015, 3, 31),
  "Management_Implication_Report_Peace_Corps_Paraguays_Inappropriate_Use_of_Cooperative_Agreements_to_Obligate_the_Government": datetime.datetime(2010, 3, 15),
  "MAR_Mitigating_a_Potential_Electrica_Safety_Hazard_Redacted_2": datetime.datetime(2011, 5, 17),
  "Safety_and_security_weaknesses_in PC_Cameroon": datetime.datetime(2012, 7, 31),
  "Peace_Corps_Gambia_Grant_Activities": datetime.datetime(2010, 5, 14),
  "OIG_Investigations_have_Disclosed_Improper_Vehicle_Disposal_Practices_and_Vehicle_Sales_that_do_not_generate_Fair_Market_Returns": datetime.datetime(2010, 3, 30),
}

REPORT_TYPE_MAP = {
  'Advisories': 'press',
  'Annual and Strategic Plans': 'other',
  'Semiannual Reports to Congress': 'semiannual_report',
  'Special Reports and Reviews': 'other',
  'Audit Reports': 'audit',
  'Program Evaluation Reports': 'evaluation',
}

def run(options):
  year_range = inspector.year_range(options, archive)

  # Pull the reports
  doc = BeautifulSoup(utils.download(REPORTS_URL))
  results = doc.select("li div li")
  if not results:
    raise inspector.NoReportsFoundError("Peace Corps")
  for result in results:
    report = report_from(result, year_range)
    if report:
      inspector.save_report(report)

def report_from(result, year_range):
  link = result.find("a")
  report_url = link.get('href')
  report_filename = report_url.split("/")[-1]
  report_id, _ = os.path.splitext(report_filename)
  report_id = urllib.parse.unquote(report_id)
  title = link.text

  topic_text = result.find_previous("h2").text.strip()
  report_type = REPORT_TYPE_MAP.get(topic_text, 'other')

  # This report has been uploaded twice, skip it
  if report_id == "Advice_and_Assistance_PC_Vanuatu(SRF)":
    return

  section_title = result.find_previous("h3").text.strip()
  estimated_date = False
  published_on = None
  if report_id in REPORT_PUBLISHED_MAPPING:
    published_on = REPORT_PUBLISHED_MAPPING[report_id]
  if not published_on:
    try:
      published_on_text = title.split("–")[-1].strip()
      published_on = datetime.datetime.strptime(published_on_text, '%B %d, %Y')
    except ValueError:
      pass
  if not published_on:
    try:
      # For reports where we can only find the year, set them to Nov 1st of that year
      published_on_year = int(section_title.lstrip("FY "))
      published_on = datetime.datetime(published_on_year, 11, 1)
      estimated_date = True
    except ValueError:
      pass
  if not published_on:
    raise Exception("Could not find date for %s (%s)" %
                    (repr(title), report_id))

  if published_on.year not in year_range:
    logging.debug("[%s] Skipping, not in requested range." % report_url)
    return

  report = {
    'inspector': 'peacecorps',
    'inspector_url': 'http://www.peacecorps.gov/about/inspgen/',
    'agency': 'peacecorps',
    'agency_name': 'Peace Corps',
    'type': report_type,
    'report_id': report_id,
    'url': report_url,
    'title': title,
    'published_on': datetime.datetime.strftime(published_on, "%Y-%m-%d"),
  }
  if estimated_date:
    report['estimated_date'] = estimated_date
  return report

utils.run(run) if (__name__ == "__main__") else None
