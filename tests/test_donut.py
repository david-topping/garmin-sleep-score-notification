from garmin_sleep_score_notification.donut import Donut


def test_renders_one_sector_per_segment_with_centre_text():
    svg = Donut([("#111111", 0.5), ("#222222", 0.3), ("#333333", 0.2)], "6h 00m", "TOTAL SLEEP").svg()
    assert svg.count("<path") == 3
    assert 'fill="#222222"' in svg
    assert ">6h 00m<" in svg and ">TOTAL SLEEP<" in svg


def test_skips_negligible_segments():
    svg = Donut([("#111111", 1.0), ("#222222", 0.0)], "8h 00m", "TOTAL SLEEP").svg()
    assert svg.count("<path") == 1
