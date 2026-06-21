from dreamforge_pipeline_chain import (
    first_image_path,
    post_upscale_method_from_job,
    should_run_post_upscale,
)


class _Job:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


def test_first_image_path_from_images():
    assert first_image_path({"images": [{"path": "D:/out.png"}]}) == "D:/out.png"


def test_should_not_chain_when_primary_failed():
    job = _Job(post_upscale="fast_2x", cn_type="inpaint")
    assert not should_run_post_upscale(job, {}, primary_result={"status": "error"})


def test_should_not_chain_when_already_upscaling():
    job = _Job(post_upscale="fast_2x", cn_type="upscale")
    assert not should_run_post_upscale(job, {}, primary_result={"status": "success"})


def test_post_upscale_guard_prevents_loop():
    job = _Job(post_upscale="fast_2x", _post_upscale_executing=True)
    assert post_upscale_method_from_job(job, {}) is None
