from dreamforge_automation import expand_automation_jobs, preview_automation


def test_seed_batch_expansion():
    jobs = expand_automation_jobs(
        {
            "type": "seed_batch",
            "count": 3,
            "base_settings": {"prompt": "cat", "model": "flux.safetensors"},
            "template_id": "create.default",
        }
    )
    assert len(jobs) == 3
    seeds = {job["overrides"]["seed"] for job in jobs}
    assert len(seeds) == 3
    assert all(job["overrides"]["template_id"] == "create.default" for job in jobs)


def test_prompt_lines_expansion(tmp_path):
    prompt_file = tmp_path / "lines.txt"
    prompt_file.write_text("line one\n\nline two\n", encoding="utf-8")
    jobs = expand_automation_jobs(
        {
            "type": "prompt_lines",
            "prompt_file": str(prompt_file),
            "base_settings": {"model": "flux.safetensors"},
        }
    )
    assert len(jobs) == 2
    assert jobs[0]["overrides"]["prompt"] == "line one"
    assert jobs[1]["overrides"]["prompt"] == "line two"


def test_preview_automation():
    preview = preview_automation({"type": "seed_batch", "count": 2, "base_settings": {}})
    assert preview["job_count"] == 2
    assert len(preview["jobs"]) == 2
