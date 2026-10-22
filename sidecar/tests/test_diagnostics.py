"""First-run check: every ok / warn / missing branch, on a fake home folder with a fake command runner (never the real machine)."""
import os
import stat
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from picturebook_sidecar import diagnostics as d
from picturebook_sidecar.app import create_app

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
TOKEN = "t" * 32
AUTH = {"Authorization": f"Bearer {TOKEN}"}


def make_home(tmp_path, gemma=True, klein=True, whisper=True):
    home = tmp_path / "home"
    (home / ".local" / "bin").mkdir(parents=True)
    if gemma:
        g = home / "models" / "gemma_4"
        g.mkdir(parents=True)
        for n in ("gemma-4-E4B-it-qat-UD-Q4_K_XL.gguf", "mmproj-F16.gguf"):
            with open(g / n, "wb") as f:
                f.truncate(60_000_000)                   # sparse file, only its size matters
    for have, repo in ((klein, "hlhc--FLUX.2-klein-4B-bnb-4bit"), (whisper, "openai--whisper-large-v3-turbo")):
        if have:
            s = home / ".cache" / "huggingface" / "hub" / f"models--{repo}" / "snapshots" / "abc123"
            s.mkdir(parents=True)
            (s / "model.safetensors").write_bytes(b"x")
    return home


def fake_run(answers):
    """answers: first matching key (a word that must appear in the command line) -> (returncode, output)."""
    def run(argv, timeout):
        line = " ".join(argv)
        for key, res in answers.items():
            if key in line:
                return res
        return 127, "not found"
    return run


GOOD = {"list short sources": (0, "55\talsa_input.pci-0000.Mic2\tPipeWire\n65\talsa_output.x.monitor\tPipeWire\n"), "nvidia-smi": (0, "NVIDIA RTX A2000, 8192\n"), "import torch": (0, "True 2.12.1+cu130\n"), "version": (0, "version: 0.4.1-dev\n"), "systemd-run": (0, "")}


def env_for(tmp_path, answers=GOOD, meminfo_gib=12.0, disk_gb=200.0, **home_kw):
    tmp_path = Path(tmp_path) / f"env{len(list(Path(tmp_path).glob('env*')))}"
    tmp_path.mkdir(parents=True)
    home = make_home(tmp_path, **home_kw)
    for tool in ("nvidia-smi", "llama", "ffmpeg", "systemd-run", "pactl"):      # fake executables so `which` finds them
        p = home / ".local" / "bin" / tool
        p.write_text("#!/bin/sh\n")
        p.chmod(p.stat().st_mode | stat.S_IXUSR)
    mi = tmp_path / "meminfo"
    mi.write_text(f"MemTotal: 16000000 kB\nMemAvailable: {int(meminfo_gib * 1024 * 1024)} kB\n")
    return d.Env(scripts_dir=SCRIPTS, home=home, path=str(home / ".local" / "bin"), library_dir=tmp_path, run=fake_run(answers), meminfo=str(mi), disk_free=lambda: disk_gb * 1e9)


def by_id(checks):
    return {c.id: c for c in checks}


def test_a_complete_machine_has_no_blockers(tmp_path):
    rep = d.report(d.run_checks(env_for(tmp_path)))
    assert rep["blockers"] == [] and rep["audio_ready"] is True
    assert {c["status"] for c in rep["checks"]} == {"ok"}, [c for c in rep["checks"] if c["status"] != "ok"]


def test_missing_models_block_with_the_exact_fix(tmp_path):
    c = by_id(d.run_checks(env_for(tmp_path, gemma=False, klein=False, whisper=False)))
    assert c["gemma"].blocking and "gemma-4-E4B-it-qat-UD-Q4_K_XL.gguf" in c["gemma"].fix
    assert c["klein"].blocking and "hf download hlhc/FLUX.2-klein-4B-bnb-4bit" in c["klein"].fix and "4.8 GB" in c["klein"].fix
    assert c["whisper"].blocking and c["whisper"].needed_for == "audio"
    rep = d.report(list(c.values()))
    assert set(rep["blockers"]) == {"gemma", "klein", "whisper"} and rep["audio_ready"] is False


def test_a_missing_speech_model_only_blocks_audio_books(tmp_path):
    rep = d.report(d.run_checks(env_for(tmp_path, whisper=False)))
    assert rep["blockers"] == ["whisper"] and rep["audio_ready"] is False
    assert all(c["status"] == "ok" for c in rep["checks"] if c["id"] != "whisper")


def test_an_empty_snapshot_folder_does_not_count_as_downloaded(tmp_path):
    env = env_for(tmp_path)
    snap = next((env.home / ".cache" / "huggingface" / "hub" / "models--hlhc--FLUX.2-klein-4B-bnb-4bit" / "snapshots").iterdir())
    for f in snap.iterdir():
        f.unlink()                                       # an interrupted download leaves the folder but no files
    assert by_id(d.run_checks(env))["klein"].status == d.MISSING


def test_a_truncated_model_file_is_missing(tmp_path):
    env = env_for(tmp_path)
    (env.home / "models" / "gemma_4" / "mmproj-F16.gguf").write_bytes(b"x" * 10)
    c = by_id(d.run_checks(env))["gemma"]
    assert c.status == d.MISSING and "mmproj-F16.gguf" in c.detail and "gemma-4" not in c.detail.split("Missing:")[1].split("mmproj")[0]


@pytest.mark.parametrize("smi,status", [((0, "NVIDIA RTX, 8192\n"), "ok"), ((0, "Small card, 4096\n"), "warn"), ((9, "NVIDIA-SMI has failed"), "missing"), ((0, "garbage"), "missing")])
def test_gpu_states(tmp_path, smi, status):
    env = env_for(tmp_path, {**GOOD, "nvidia-smi": smi})
    assert by_id(d.run_checks(env))["gpu"].status == status


def test_no_nvidia_smi_program_at_all_is_missing(tmp_path):
    env = env_for(tmp_path)
    (env.home / ".local" / "bin" / "nvidia-smi").unlink()
    env.run = None                                       # real runner, but nothing to run
    c = d.check_gpu(env)
    assert c.status == d.MISSING and "driver" in c.fix


@pytest.mark.parametrize("res,status", [((0, "True 2.12.1\n"), "ok"), ((0, "False 2.12.1\n"), "missing"), ((1, "ModuleNotFoundError: torch"), "missing")])
def test_torch_states(tmp_path, res, status):
    c = by_id(d.run_checks(env_for(tmp_path, {**GOOD, "import torch": res})))["torch"]
    assert c.status == status and (status == "ok" or c.fix)


def test_llama_found_in_local_bin_missing_or_not_answering(tmp_path):
    assert by_id(d.run_checks(env_for(tmp_path)))["llama"].detail.startswith("version:")
    env = env_for(tmp_path)
    (env.home / ".local" / "bin" / "llama").unlink()
    assert by_id(d.run_checks(env))["llama"].status == d.MISSING
    assert by_id(d.run_checks(env_for(tmp_path, {**GOOD, "version": (1, "")})))["llama"].status == d.WARN


def test_optional_tools_only_warn(tmp_path):
    env = env_for(tmp_path)
    (env.home / ".local" / "bin" / "ffmpeg").unlink()
    c = by_id(d.run_checks(env))
    assert c["ffmpeg"].status == d.WARN and not c["ffmpeg"].blocking
    c2 = by_id(d.run_checks(env_for(tmp_path, {**GOOD, "systemd-run": (1, "Failed")})))
    assert c2["memory_cap"].status == d.MISSING and c2["memory_cap"].blocking


@pytest.mark.parametrize("gib,status", [(12.0, "ok"), (6.0, "ok"), (5.5, "warn"), (1.0, "warn")])
def test_memory_levels_warn_but_never_block(tmp_path, gib, status):
    c = by_id(d.run_checks(env_for(tmp_path, meminfo_gib=gib)))["ram"]
    assert c.status == status and not c.blocking


@pytest.mark.parametrize("gb,status,blocking", [(200, "ok", False), (10, "ok", False), (6, "warn", False), (1, "missing", True)])
def test_disk_levels(tmp_path, gb, status, blocking):
    c = by_id(d.run_checks(env_for(tmp_path, disk_gb=gb)))["disk"]
    assert (c.status, c.blocking) == (status, blocking)


def test_unreadable_meminfo_is_a_warning_not_a_crash(tmp_path):
    env = env_for(tmp_path)
    env.meminfo = str(tmp_path / "does-not-exist")
    assert by_id(d.run_checks(env))["ram"].status == d.WARN


def test_missing_scripts_folder_is_reported(tmp_path):
    env = env_for(tmp_path)
    env.scripts_dir = tmp_path / "nope"
    checks = d.run_checks(env)
    assert [c.id for c in checks] == ["scripts"] and checks[0].blocking


def test_the_check_uses_the_same_model_locations_as_the_scripts():
    """modelpaths.py is the single source: the scripts' constants and the diagnostics must name the same files."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("mp", SCRIPTS / "modelpaths.py")
    mp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mp)
    text = (SCRIPTS / "common.py").read_text() + (SCRIPTS / "klein.py").read_text() + (SCRIPTS / "transcribe.py").read_text()
    for needle in ("modelpaths.gemma_e4b()", "modelpaths.KLEIN_REPO", "modelpaths.WHISPER_REPO"):
        assert needle in text, needle
    assert "huggingface/hub/models--" not in text and "~/models" not in text, "a script names a model location itself again"


def test_endpoint_needs_the_token_and_returns_the_report(tmp_path):
    with TestClient(create_app(TOKEN, library_root=tmp_path, scripts_dir=SCRIPTS, pipeline_python=os.sys.executable)) as c:
        assert c.get("/diagnostics").status_code == 401
        r = c.get("/diagnostics", headers=AUTH)
        assert r.status_code == 200
        body = r.json()
        assert {x["id"] for x in body["checks"]} >= {"gpu", "torch", "llama", "gemma", "klein", "whisper", "disk", "ram"}
        assert isinstance(body["blockers"], list) and "audio_ready" in body


@pytest.mark.parametrize("res,status", [((0, "55\talsa_input.mic\tPipeWire\n"), "ok"), ((0, "65\talsa_output.x.monitor\tPipeWire\n"), "warn"), ((0, ""), "warn"), ((1, "Connection refused"), "warn")])
def test_microphone_states_only_warn(tmp_path, res, status):
    c = by_id(d.run_checks(env_for(tmp_path, {**GOOD, "list short sources": res})))["microphone"]
    assert c.status == status and not c.blocking


def test_no_pactl_means_unknown_not_missing(tmp_path):
    env = env_for(tmp_path)
    (env.home / ".local" / "bin" / "pactl").unlink()
    c = by_id(d.run_checks(env))["microphone"]
    assert c.status == d.WARN and "pactl" in c.detail
