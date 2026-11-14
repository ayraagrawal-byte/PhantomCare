from pipeline.vexcel_imagery import square_wkt


def test_square_wkt_centers_bounded_imagery_request() -> None:
    polygon = square_wkt(34.1866, -118.4042, half_meters=40)

    assert polygon.startswith("POLYGON((")
    assert polygon.endswith("))")
    assert "-118." in polygon
    assert "34." in polygon
