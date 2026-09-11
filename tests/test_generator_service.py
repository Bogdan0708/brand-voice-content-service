import pytest
from fastapi import HTTPException
from tests.conftest import generator_module


@pytest.mark.asyncio
async def test_health():
    resp = await generator_module.health()
    assert resp.service == "content-generator"


@pytest.mark.asyncio
async def test_generate_success():
    generator_module.load_brand_voices()

    class DummyMessage:
        def __init__(self, text):
            self.content = [type("Chunk", (), {"text": text})]

    class DummyClient:
        class Messages:
            def create(self, **kwargs):
                return DummyMessage("One\n---\nTwo\n---\nThree")

        @property
        def messages(self):
            return self.Messages()

    req = generator_module.GenerateRequest(
        topic="Spring campaign",
        platform="instagram",
        brand_voice="professional",
        num_variants=2,
    )
    resp = await generator_module.generate_caption(req, client=DummyClient())
    assert resp["variants"] == ["One", "Two"]


@pytest.mark.asyncio
async def test_generate_unknown_voice():
    generator_module.load_brand_voices()
    req = generator_module.GenerateRequest(
        topic="Test",
        platform="instagram",
        brand_voice="does-not-exist",
        num_variants=1,
    )
    with pytest.raises(HTTPException) as exc:
        await generator_module.generate_caption(req, client=None)
    assert exc.value.status_code == 400
