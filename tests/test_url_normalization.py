import pytest

from utils.common import extract_user_linkedin_page
from utils.find_company_info import extract_company_page


def test_extract_user_linkedin_page_normalization():
    raw = "http://linkedin.com/in/john-doe/?utm=foo"
    assert extract_user_linkedin_page(raw) == "https://www.linkedin.com/in/john-doe"


def test_extract_company_page_normalization():
    raw = "https://uk.linkedin.com/company/acme-inc/?trk=public"
    assert extract_company_page(raw) == "https://www.linkedin.com/company/acme-inc"

