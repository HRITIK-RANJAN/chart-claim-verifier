from chart_claim_verifier.models.vlm import OfflineLLM
from chart_claim_verifier.schemas import Figure, PointQuery
from chart_claim_verifier.tools.cache import ReadingCache
from chart_claim_verifier.tools.vlm_crop import VlmCropTool


def test_offline_miss_is_reported_and_never_cached(tmp_path):
    from PIL import Image
    Image.new("RGB", (60, 40), "white").save(tmp_path / "c.png")
    fig = Figure(figure_id="f", report_id="r", image_path=str(tmp_path / "c.png"), chart_type="line")
    cache = ReadingCache(tmp_path / "c.sqlite")
    tool = VlmCropTool(OfflineLLM("m"), cache)
    r = tool.read(fig, PointQuery(series="A", x="1"))
    assert not r.ok and r.error == "offline_miss"
    assert cache._db.execute("SELECT COUNT(*) FROM readings").fetchone()[0] == 0
