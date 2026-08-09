import unittest

from sec_v1_fundamentals import flow_metric, quarter_value_map


def quarterly_point(*, value, fy, fp, start, end, filed):
    return {
        "val": value,
        "fy": fy,
        "fp": fp,
        "form": "10-Q",
        "start": start,
        "end": end,
        "filed": filed,
    }


class SecMetricTagFreshnessTest(unittest.TestCase):
    def setUp(self):
        self.facts = {
            "facts": {
                "us-gaap": {
                    # The preferred tag exists, but the issuer stopped using it.
                    "RevenueFromContractWithCustomerExcludingAssessedTax": {
                        "units": {
                            "USD": [
                                quarterly_point(
                                    value=100,
                                    fy=2021,
                                    fp="Q2",
                                    start="2021-04-01",
                                    end="2021-06-30",
                                    filed="2021-08-01",
                                )
                            ]
                        }
                    },
                    # A fallback tag carries the current filing.
                    "Revenues": {
                        "units": {
                            "USD": [
                                quarterly_point(
                                    value=240,
                                    fy=2026,
                                    fp="Q2",
                                    start="2026-04-01",
                                    end="2026-06-30",
                                    filed="2026-08-01",
                                )
                            ]
                        }
                    },
                }
            }
        }

    def test_flow_metric_chooses_tag_with_freshest_quarter(self):
        metric, audit = flow_metric(self.facts, "revenue", ["USD"])

        self.assertEqual(metric["value"], 240)
        self.assertEqual(metric["quarter"], "Q2 2026")
        self.assertEqual(metric["date"], "2026-06-30")
        self.assertEqual(audit["tag"], "Revenues")

    def test_guidance_quarter_map_uses_same_fresh_tag(self):
        values = quarter_value_map(self.facts, "revenue", ["USD"])

        self.assertNotIn("Q2 2021", values)
        self.assertEqual(values["Q2 2026"]["value"], 240)


if __name__ == "__main__":
    unittest.main()
