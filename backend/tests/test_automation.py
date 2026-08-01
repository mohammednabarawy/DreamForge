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


def test_seed_batch_can_be_deterministic():
    jobs = expand_automation_jobs({"type": "seed_batch", "count": 3, "seed_start": 42, "seed_step": 2})
    assert [job["overrides"]["seed"] for job in jobs] == [42, 44, 46]


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


def test_recipe_batch_uses_recipe_values_and_seed_sweep(tmp_path):
    recipe_file = tmp_path / "recipe.json"
    recipe_file.write_text(
        '{"schema_version":"2.0","model":"model.safetensors",'
        '"positive_prompt":"a fox","negative_prompt":"blur",'
        '"seed":10,"sampler":"euler","cfg_scale":6,"steps":20,'
        '"aspect_ratio":"768x768","settings":{"scheduler":"normal"}}',
        encoding="utf-8",
    )
    jobs = expand_automation_jobs(
        {
            "type": "recipe_batch",
            "recipe_file": str(recipe_file),
            "count": 3,
            "seed_step": 5,
            "base_settings": {"vram_profile": "balanced"},
        }
    )
    assert [job["overrides"]["seed"] for job in jobs] == [10, 15, 20]
    assert jobs[0]["overrides"]["prompt"] == "a fox"
    assert jobs[0]["overrides"]["scheduler"] == "normal"
    assert jobs[0]["overrides"]["vram_profile"] == "balanced"


def test_recipe_batch_rejects_non_recipe_file(tmp_path):
    path = tmp_path / "wrong.json"
    path.write_text("{}", encoding="utf-8")
    assert expand_automation_jobs({"type": "recipe_batch", "recipe_file": str(path)}) == []
    preview = preview_automation({"type": "recipe_batch", "recipe_file": str(path)})
    assert preview["ok"] is False
    assert preview["error"] == "invalid_recipe"


def test_recipe_folder_queues_valid_recipes_only(tmp_path):
    (tmp_path / "01.json").write_text(
        '{"schema_version":"2.0","positive_prompt":"first","seed":1}',
        encoding="utf-8",
    )
    (tmp_path / "02.json").write_text("{}", encoding="utf-8")
    jobs = expand_automation_jobs({"type": "recipe_folder", "recipe_folder": str(tmp_path)})
    assert len(jobs) == 1
    assert jobs[0]["label"] == "01"
    assert jobs[0]["overrides"]["prompt"] == "first"
