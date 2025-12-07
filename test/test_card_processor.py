from o_event.card_processor import PunchItem, CardProcessor


def test_retime_local_anchors():
    punches = [
        PunchItem(cardNumber=1, code=1, time=1000),  # reliable
        PunchItem(cardNumber=1, code=2, time=1020),  # reliable
        PunchItem(cardNumber=1, code=3, time=1010),  # backward → outlier
        PunchItem(cardNumber=1, code=4, time=70000), # huge forward → outlier
        PunchItem(cardNumber=1, code=5, time=1045),  # reliable
        PunchItem(cardNumber=1, code=6, time=1060),  # reliable
    ]

    retimed = CardProcessor().retime_local_anchors(punches, max_leg=1800)
    times = [p.time for p in retimed]

    # Check strictly monotonic
    for i in range(1, len(times)):
        assert times[i] > times[i - 1], f"Timestamps not strictly increasing at index {i}"

    # Check that genuine timestamps are preserved
    assert retimed[0].time == 1000
    assert retimed[1].time == 1020
    assert retimed[4].time == 1045
    assert retimed[5].time == 1060

    # Check outliers were adjusted
    assert 1020 < retimed[2].time < 1045
    assert 1020 < retimed[3].time < 1045
