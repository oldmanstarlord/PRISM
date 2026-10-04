from backend.app.correlation_mst.service import mst_configuration


def test_configuration_records_approved_layer_2_contract() -> None:
    configuration = mst_configuration()

    assert configuration["implementation_version"] == "correlation-mst-v1"
    assert configuration["lookback_returns"] == 120
    assert configuration["minimum_pairwise_observations"] == 100
    assert configuration["algorithm"] == "Kruskal with Union-Find"
