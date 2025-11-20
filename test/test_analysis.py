from o_event.analysis import Analysis


def test_perfect():
    required = [31, 45, 72, 100]
    punches = [(31, 120), (45, 240), (72, 300), (100, 450)]

    res = Analysis().analyse_order(required, punches)
    assert res.all_visited
    assert res.order_correct
    assert res.missing == []
    assert res.extra == []
    assert res.visited == punches


def test_extra_valid():
    required = [31, 45, 72, 100]
    punches = [
        (31, 110), (31, 115), (45, 200), (60, 220),
        (45, 230), (72, 300), (100, 400), (100, 410),
    ]
    res = Analysis().analyse_order(required, punches)
    assert res.all_visited
    assert res.order_correct
    assert res.missing == []
    assert res.extra == [(31, 115), (60, 220), (45, 230), (100, 410)]
    assert res.visited == [(31, 110), (45, 200), (72, 300), (100, 400)]


def test_missing():
    required = [31, 45, 72, 100]
    punches = [(31, 100), (72, 200), (100, 300)]
    res = Analysis().analyse_order(required, punches)
    assert not res.all_visited
    assert not res.order_correct
    assert res.missing == [45]
    assert res.extra == []
    assert res.visited == [(31, 100), (45, None), (72, 200), (100, 300)]


def test_random():
    required = [31, 45, 72, 100]
    punches = [(45, 12), (31, 15), (31, 20), (72, 40), (31, 50), (100, 60), (45, 70)]
    res = Analysis().analyse_order(required, punches)
    assert not res.all_visited
    assert not res.order_correct
    assert res.missing == [31]
    assert res.extra == [(31, 15), (31, 20), (31, 50), (45, 70)]
    assert res.visited == [(31, None), (45, 12), (72, 40), (100, 60)]
