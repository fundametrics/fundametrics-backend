from scraper.core.shareholding_engine import ShareholdingInsightEngine


def test_shareholding_insight_engine_trends():
    snapshots = {
        "2024-Q1": {"promoter": 70.0, "institutional": 10.0, "public": 8.0},
        "2024-Q2": {"promoter": 68.5, "institutional": 12.5, "public": 10.5},
        "2024-Q3": {"promoter": 67.0, "institutional": 15.5, "public": 13.0},
    }

    engine = ShareholdingInsightEngine()
    insights = engine.generate_insights(snapshots)

    assert insights["promoter_trend"] == "decreasing"
    assert insights["institutional_bias"] == "bullish"
    assert insights["retail_risk"] == "high"

    score = insights.get("ownership_stability_score")
    assert isinstance(score, int)
    assert 0 <= score <= 100
