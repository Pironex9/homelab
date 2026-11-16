from app.strings.hu import day_label

EXPECTED = ["1-jén", "2-án", "3-án", "4-én", "5-én", "6-án", "7-én", "8-án",
            "9-én", "10-én", "11-én", "12-én", "13-án", "14-én", "15-én",
            "16-án", "17-én", "18-án", "19-én", "20-án", "21-jén", "22-én",
            "23-án", "24-én", "25-én", "26-án", "27-én", "28-án", "29-én",
            "30-án", "31-én"]


def test_day_label_all_31_days():
    assert [day_label(d) for d in range(1, 32)] == EXPECTED
