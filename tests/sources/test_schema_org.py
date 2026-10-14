from braevity.sources.schema_org import SchemaOrgScraper


SAMPLE_HTML = '''
<html><head><title>Careers</title></head><body>
<script type="application/ld+json">
{
  "@context": "https://schema.org/",
  "@type": "JobPosting",
  "title": "Senior Backend Engineer",
  "hiringOrganization": {"@type": "Organization", "name": "Acme Corp"},
  "jobLocation": {"@type": "Place", "address": {"@type": "PostalAddress", "addressLocality": "San Francisco"}},
  "datePosted": "2026-10-01",
  "description": "Build cool stuff",
  "baseSalary": {
    "@type": "MonetaryAmount",
    "currency": "USD",
    "value": {"@type": "QuantitativeValue", "minValue": 150000, "maxValue": 220000}
  },
  "employmentType": "FULL_TIME",
  "jobLocationType": "TELECOMMUTE",
  "url": "https://acme.com/careers/senior-backend"
}
</script>
</body></html>
'''


def test_parse_jsonld_single_posting():
    scraper = SchemaOrgScraper()
    jobs = scraper.parse_jsonld(SAMPLE_HTML, "https://acme.com/careers")
    assert len(jobs) == 1
    job = jobs[0]
    assert job.title == "Senior Backend Engineer"
    assert job.company == "Acme Corp"
    assert job.salary_min == 150000
    assert job.salary_max == 220000
    assert job.salary_currency == "USD"
    assert job.remote is True
    assert job.employment_type == "full_time"
    assert job.source == "schema.org"


def test_parse_jsonld_no_posting():
    html = '<html><body><script type="application/ld+json">{"@type": "Organization"}</script></body></html>'
    scraper = SchemaOrgScraper()
    jobs = scraper.parse_jsonld(html, "https://example.com")
    assert jobs == []


def test_parse_jsonld_malformed_json():
    html = '<html><body><script type="application/ld+json">NOT JSON</script></body></html>'
    scraper = SchemaOrgScraper()
    jobs = scraper.parse_jsonld(html, "https://example.com")
    assert jobs == []


SAMPLE_LIST_HTML = '''
<html><body>
<script type="application/ld+json">
[
  {"@type": "JobPosting", "title": "Job A", "hiringOrganization": {"name": "Co"}, "url": "https://co.com/a"},
  {"@type": "JobPosting", "title": "Job B", "hiringOrganization": {"name": "Co"}, "url": "https://co.com/b"}
]
</script>
</body></html>
'''


def test_parse_jsonld_array():
    scraper = SchemaOrgScraper()
    jobs = scraper.parse_jsonld(SAMPLE_LIST_HTML, "https://co.com/careers")
    assert len(jobs) == 2
    assert jobs[0].title == "Job A"
    assert jobs[1].title == "Job B"
