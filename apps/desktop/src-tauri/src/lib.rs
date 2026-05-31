use base64::{engine::general_purpose::STANDARD, Engine as _};
use futures_util::StreamExt;
use image::imageops::FilterType;
use image::GenericImageView;
use notify::{Config, RecommendedWatcher, RecursiveMode, Watcher};
use reqwest::header::{HeaderMap, HeaderValue, AUTHORIZATION};
use serde_json::{json, Value};
use std::{
    fs::{self, OpenOptions},
    io::{BufRead, BufReader, Read, Seek, SeekFrom, Write},
    path::{Component, Path, PathBuf},
    process::{Child, Command, Stdio},
    sync::{Arc, Mutex},
    time::{Duration, Instant},
};
use tauri::{AppHandle, Emitter, Manager, RunEvent, State};
use uuid::Uuid;

#[cfg(windows)]
use std::os::windows::process::CommandExt;

#[cfg(windows)]
const CREATE_NO_WINDOW: u32 = 0x08000000;

const PREVIEW_MAX_BYTES: u64 = 12 * 1024 * 1024;
/// Live step previews (frequent updates) — keep IPC + decode small.
const PREVIEW_LIVE_MAX_EDGE: u32 = 512;
/// Final canvas / gallery quality.
const PREVIEW_FINAL_MAX_EDGE: u32 = 2048;
const LOG_TAIL_CHARS: usize = 4000;
/// Failure diagnostics: include enough of the per-job log for tracebacks.
const JOB_LOG_TAIL_CHARS: usize = 24_000;
const LOG_FULL_CHARS: usize = 100_000;
/// Max wait for PyTorch / pipeline boot (first launch can take several minutes).
const WORKER_BOOT_TIMEOUT_MS: u64 = 300_000;
const WORKER_BOOT_POLL_MS: u64 = 500;
const WORKER_SHUTDOWN_TIMEOUT_MS: u64 = 15_000;
const WORKER_SHUTDOWN_POLL_MS: u64 = 100;
const MAX_WORKER_AUTO_RESTARTS: u8 = 2;
/// Max single-line JSON payload from the Python bridge (list_outputs with long prompts).
const SIDECAR_MAX_RESPONSE_BYTES: usize = 64 * 1024 * 1024;

struct ActiveGeneration {
    job_id: String,
    log_path: PathBuf,
}

struct GpuWorker {
    _child: Arc<Mutex<Child>>,
    stdin: Mutex<std::process::ChildStdin>,
}

/// Long-lived JSON bridge (one Python process, Gradio-style — no spawn per command).
struct PythonSidecar {
    child: Arc<Mutex<Child>>,
    stdin: Mutex<std::process::ChildStdin>,
    stdout: Mutex<BufReader<std::process::ChildStdout>>,
}

impl PythonSidecar {
    fn spawn(root: &Path) -> Result<Self, String> {
        let python = python_exe(root);
        let script = bridge_script(root);
        #[cfg(windows)]
        let exists = python.is_file();
        #[cfg(not(windows))]
        let exists = python.is_file()
            || python.to_string_lossy() == "python3"
            || python.to_string_lossy() == "python";
        if !exists {
            return Err(format!("Python runtime not found: {}", python.display()));
        }
        if !script.is_file() {
            return Err(format!("Bridge script not found: {}", script.display()));
        }

        let mut cmd = Command::new(&python);
        cmd.current_dir(root)
            .arg("-u")
            .arg("-s")
            .arg(&script)
            .env("PYTHONIOENCODING", "utf-8")
            .env("PYTHONUTF8", "1")
            .env("PYTHONUNBUFFERED", "1")
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());
        #[cfg(windows)]
        cmd.creation_flags(CREATE_NO_WINDOW);

        let mut child = cmd
            .spawn()
            .map_err(|e| format!("Failed to start bridge sidecar: {e}"))?;
        let stdin = child
            .stdin
            .take()
            .ok_or_else(|| "Sidecar stdin unavailable".to_string())?;
        let stdout = child
            .stdout
            .take()
            .ok_or_else(|| "Sidecar stdout unavailable".to_string())?;

        Ok(Self {
            child: Arc::new(Mutex::new(child)),
            stdin: Mutex::new(stdin),
            stdout: Mutex::new(BufReader::new(stdout)),
        })
    }

    fn alive(&self) -> bool {
        self.child
            .lock()
            .ok()
            .and_then(|mut c| c.try_wait().ok().flatten())
            .is_none()
    }

    fn read_json_response(stdout: &mut BufReader<std::process::ChildStdout>) -> Result<Value, String> {
        let mut accumulated = String::new();
        for _ in 0..48 {
            let mut line = String::new();
            let n = stdout
                .read_line(&mut line)
                .map_err(|e| format!("Sidecar read failed: {e}"))?;
            if n == 0 {
                if accumulated.is_empty() {
                    return Err("Sidecar closed stdout before sending a response".to_string());
                }
                break;
            }
            let trimmed = line.trim();
            if trimmed.is_empty() {
                if !accumulated.is_empty() {
                    break;
                }
                continue;
            }
            if accumulated.is_empty() {
                match serde_json::from_str::<Value>(trimmed) {
                    Ok(value) => return Ok(value),
                    Err(_) if trimmed.starts_with('{') || trimmed.starts_with('[') => {
                        accumulated.push_str(trimmed);
                    }
                    Err(err) => {
                        return Err(format!(
                            "Sidecar JSON parse failed: {err} (got: {}...)",
                            &trimmed[..trimmed.len().min(160)]
                        ));
                    }
                }
            } else {
                accumulated.push_str(trimmed);
            }
            if accumulated.len() > SIDECAR_MAX_RESPONSE_BYTES {
                return Err("Sidecar response exceeded size limit".to_string());
            }
            if let Ok(value) = serde_json::from_str::<Value>(accumulated.trim()) {
                return Ok(value);
            }
        }
        if accumulated.is_empty() {
            return Err("Sidecar returned no JSON response".to_string());
        }
        serde_json::from_str(accumulated.trim())
            .map_err(|e| format!("Sidecar JSON parse failed: {e}"))
    }

    fn request(&self, cmd: &str, params: Value) -> Result<Value, String> {
        let request = serde_json::to_string(&json!({ "cmd": cmd, "params": params }))
            .map_err(|e| format!("Sidecar request encode failed: {e}"))?;
        let mut stdin = self.stdin.lock().map_err(|e| e.to_string())?;
        writeln!(stdin, "{request}").map_err(|e| format!("Sidecar stdin write failed: {e}"))?;
        stdin
            .flush()
            .map_err(|e| format!("Sidecar stdin flush failed: {e}"))?;

        let mut stdout = self.stdout.lock().map_err(|e| e.to_string())?;
        let response = Self::read_json_response(&mut stdout)?;

        if !self.alive() {
            return Err("Bridge sidecar exited unexpectedly".to_string());
        }

        if response.get("ok") == Some(&Value::Bool(false)) {
            return Err(response
                .get("error")
                .and_then(|v| v.as_str())
                .unwrap_or("bridge_error")
                .to_string());
        }
        Ok(response)
    }
}

fn reset_bridge_sidecar(state: &AppState) {
    let mut guard = match state.sidecar.lock() {
        Ok(g) => g,
        Err(_) => return,
    };
    if let Some(sidecar) = guard.take() {
        if let Ok(mut child) = sidecar.child.lock() {
            let _ = child.kill();
            let _ = child.wait();
        }
    }
}

fn is_sidecar_protocol_error(err: &str) -> bool {
    err.contains("Sidecar JSON parse failed")
        || err.contains("Sidecar closed stdout")
        || err.contains("Sidecar returned no JSON")
        || err.contains("Bridge sidecar exited unexpectedly")
}

fn start_bridge_sidecar(root: &Path, state: &Arc<AppState>) -> Result<(), String> {
    {
        let guard = state.sidecar.lock().map_err(|e| e.to_string())?;
        if let Some(s) = guard.as_ref() {
            if s.alive() {
                return Ok(());
            }
        }
    }
    let _startup = state.bridge_start.lock().map_err(|e| e.to_string())?;
    {
        let guard = state.sidecar.lock().map_err(|e| e.to_string())?;
        if let Some(s) = guard.as_ref() {
            if s.alive() {
                return Ok(());
            }
        }
    }
    let sidecar = PythonSidecar::spawn(root)?;
    sidecar.request("ping", json!({}))?;
    let mut guard = state.sidecar.lock().map_err(|e| e.to_string())?;
    *guard = Some(sidecar);
    Ok(())
}

fn ensure_bridge_sidecar(state: &Arc<AppState>) -> Result<(), String> {
    let root = agent_root();
    let needs = state
        .sidecar
        .lock()
        .map_err(|e| e.to_string())?
        .as_ref()
        .map(|s| !s.alive())
        .unwrap_or(true);
    if needs {
        start_bridge_sidecar(&root, state)?;
    }
    Ok(())
}

fn tail_log_file(path: &Path, max_chars: usize) -> String {
    let Ok(content) = fs::read_to_string(path) else {
        return String::new();
    };
    if content.len() <= max_chars {
        return content;
    }
    content
        .chars()
        .skip(content.chars().count().saturating_sub(max_chars))
        .collect()
}

fn resolve_job_log_path(job_id: &str, state: &AppState) -> PathBuf {
    if let Ok(guard) = state.generation.lock() {
        if let Some(job) = guard.as_ref() {
            if job.job_id == job_id {
                return job.log_path.clone();
            }
        }
    }
    dreamforge_logs_dir(&agent_root()).join(format!("{job_id}.log"))
}

fn generation_failure_log_tail(job_id: &str, state: &AppState, fallback_message: &str) -> String {
    let log_path = resolve_job_log_path(job_id, state);
    let mut tail = tail_log_file(&log_path, JOB_LOG_TAIL_CHARS);
    let fallback = fallback_message.trim();
    if tail.trim().is_empty() {
        tail = fallback.to_string();
    } else if !fallback.is_empty() && !tail.contains(fallback) {
        tail = format!("{fallback}\n\n--- job log ({}) ---\n{tail}", log_path.display());
    }
    if tail.len() < 800 {
        let worker = worker_log_path(&agent_root());
        let worker_tail = tail_log_file(&worker, LOG_TAIL_CHARS);
        if !worker_tail.trim().is_empty() {
            tail.push_str("\n\n--- worker.log ---\n");
            tail.push_str(&worker_tail);
        }
    }
    tail
}

fn spawn_worker_exit_watcher(
    app: AppHandle,
    state: Arc<AppState>,
    child: Arc<Mutex<Child>>,
    worker_log: PathBuf,
    events_path: PathBuf,
) {
    std::thread::spawn(move || loop {
        let exited = child
            .lock()
            .ok()
            .and_then(|mut c| c.try_wait().ok().flatten())
            .is_some();
        if exited {
            drain_worker_events_file(&app, &state, &events_path);
            let was_ready = state.worker_ready.lock().map(|r| *r).unwrap_or(false);
            if let Ok(mut ready) = state.worker_ready.lock() {
                *ready = false;
            }
            if let Ok(mut guard) = state.worker.lock() {
                *guard = None;
            }
            if !was_ready {
                let tail = tail_log_file(&worker_log, LOG_TAIL_CHARS);
                set_engine_health(&app, &state, "dead");
                let _ = app.emit(
                    "worker-failed",
                    json!({
                        "error": "GPU worker exited before it became ready",
                        "log_tail": tail,
                    }),
                );
            } else {
                set_engine_health(&app, &state, "dead");
                let gen_busy = state
                    .generation
                    .lock()
                    .map(|g| g.is_some())
                    .unwrap_or(false);
                let _ = app.emit(
                    "worker-dead",
                    json!({
                        "error": "GPU worker exited unexpectedly",
                        "log_tail": tail_log_file(&worker_log, LOG_TAIL_CHARS),
                    }),
                );
                if gen_busy {
                    let job_id = state
                        .generation
                        .lock()
                        .ok()
                        .and_then(|mut g| g.take().map(|j| j.job_id))
                        .unwrap_or_default();
                    let _ = app.emit(
                        "generation-finished",
                        json!({
                            "job_id": job_id,
                            "success": false,
                            "error": "GPU worker exited during generation",
                        }),
                    );
                } else {
                    let should_restart = state
                        .worker_auto_restarts
                        .lock()
                        .map(|mut n| {
                            if *n < MAX_WORKER_AUTO_RESTARTS {
                                *n += 1;
                                true
                            } else {
                                false
                            }
                        })
                        .unwrap_or(false);
                    if should_restart {
                        let root = agent_root();
                        set_engine_health(&app, &state, "restarting");
                        let _ = app.emit("worker-status", json!({ "status": "restarting" }));
                        if let Err(err) = start_gpu_worker(app.clone(), &root, &state) {
                            set_engine_health(&app, &state, "dead");
                            let _ =
                                app.emit("worker-failed", json!({ "error": err, "log_tail": "" }));
                        }
                    }
                }
            }
            break;
        }
        std::thread::sleep(Duration::from_millis(400));
    });
}

struct AppState {
    watcher: Mutex<Option<RecommendedWatcher>>,
    /// Watches preview.jpg during an active generation (immediate canvas updates).
    preview_watcher: Mutex<Option<RecommendedWatcher>>,
    generation: Arc<Mutex<Option<ActiveGeneration>>>,
    worker: Mutex<Option<GpuWorker>>,
    sidecar: Mutex<Option<PythonSidecar>>,
    /// Serializes bridge sidecar startup (prevents duplicate spawns during boot).
    bridge_start: Mutex<()>,
    worker_ready: Arc<Mutex<bool>>,
    /// Bytes already consumed from worker.events (primary IPC on Windows).
    worker_events_offset: Arc<Mutex<u64>>,
    last_boot_message: Arc<Mutex<String>>,
    last_boot_phase: Arc<Mutex<String>>,
    worker_boot_started: Arc<Mutex<Option<Instant>>>,
    /// alive | booting | dead | restarting | unknown
    engine_health: Arc<Mutex<String>>,
    worker_auto_restarts: Arc<Mutex<u8>>,
    gpu_name: Arc<Mutex<Option<String>>>,
    vram_gb: Arc<Mutex<Option<f64>>>,
    cuda_available: Arc<Mutex<Option<bool>>>,
    mps_available: Arc<Mutex<Option<bool>>>,
    last_generation_progress: Arc<Mutex<Option<Value>>>,
    /// Desktop VRAM preset (16gb / 8gb / 5gb) applied when spawning the GPU worker.
    desktop_vram_profile: Arc<Mutex<String>>,
}

fn map_vram_profile_to_desktop_mode(profile: &str) -> Option<&'static str> {
    match profile.trim().to_lowercase().as_str() {
        "5gb" | "5" | "novram" | "no" => Some("no"),
        "8gb" | "8" | "lowvram" | "low" | "mps" => Some("low"),
        "16gb" | "16" | "normalvram" | "normal" | "highvram" | "high" => Some("normal"),
        _ => None,
    }
}

fn agent_root() -> PathBuf {
    if let Ok(root) = std::env::var("DREAMFORGE_ROOT") {
        return PathBuf::from(root);
    }
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("..")
        .join("..")
        .join("..")
        .join("backend")
        .canonicalize()
        .unwrap_or_else(|_| {
            PathBuf::from(env!("CARGO_MANIFEST_DIR"))
                .join("..")
                .join("..")
                .join("..")
                .join("backend")
        })
}

fn python_exe(root: &Path) -> PathBuf {
    let parent = root.parent().unwrap_or(root);
    #[cfg(windows)]
    {
        let embed = parent.join("python_embeded").join("python.exe");
        if embed.is_file() {
            return embed;
        }
        let venv = parent.join("venv").join("Scripts").join("python.exe");
        if venv.is_file() {
            return venv;
        }
        embed
    }
    #[cfg(not(windows))]
    {
        // Prefer conda env (Apple Silicon PyTorch) over venv
        let conda_python = Path::new("/opt/anaconda3/envs/dreamforge/bin/python");
        if conda_python.is_file() {
            return conda_python.to_path_buf();
        }
        let venv_python = parent.join("venv").join("bin").join("python");
        if venv_python.is_file() {
            venv_python
        } else {
            let core_venv_python = root.join("venv").join("bin").join("python");
            if core_venv_python.is_file() {
                core_venv_python
            } else {
                PathBuf::from("python3")
            }
        }
    }
}

fn bridge_script(root: &Path) -> PathBuf {
    root.join("dreamforge_desktop_bridge.py")
}

fn dreamforge_logs_dir(root: &Path) -> PathBuf {
    outputs_root(root).join("dreamforge").join("logs")
}

fn worker_events_path(root: &Path) -> PathBuf {
    dreamforge_logs_dir(root).join("worker.events")
}

fn worker_log_path(root: &Path) -> PathBuf {
    dreamforge_logs_dir(root).join("worker.log")
}

fn reset_worker_events_file(root: &Path) {
    let path = worker_events_path(root);
    let _ = fs::write(&path, "");
}

fn outputs_root(root: &Path) -> PathBuf {
    root.parent().unwrap_or(root).join("outputs")
}

fn models_root(root: &Path) -> PathBuf {
    root.join("models")
}

fn safe_model_filename(name: &str) -> Result<String, String> {
    let path = Path::new(name);
    if path.components().any(|c| {
        matches!(
            c,
            Component::ParentDir | Component::RootDir | Component::Prefix(_)
        )
    }) {
        return Err("Invalid model filename".to_string());
    }
    let file = path
        .file_name()
        .and_then(|s| s.to_str())
        .ok_or_else(|| "Invalid model filename".to_string())?
        .trim();
    if file.is_empty() {
        return Err("Invalid model filename".to_string());
    }
    Ok(file
        .chars()
        .map(|c| {
            if matches!(c, '<' | '>' | ':' | '"' | '/' | '\\' | '|' | '?' | '*') {
                '_'
            } else {
                c
            }
        })
        .collect())
}

fn live_preview_candidates() -> Vec<PathBuf> {
    let root = agent_root();
    vec![
        root.join("outputs").join("preview.jpg"),
        outputs_root(&root).join("preview.jpg"),
    ]
}

fn sanitize_preview_job_id(job_id: &str) -> String {
    let cleaned: String = job_id
        .trim()
        .chars()
        .map(|c| {
            if c.is_ascii_alphanumeric() || c == '-' || c == '_' {
                c
            } else {
                '_'
            }
        })
        .take(80)
        .collect();
    if cleaned.is_empty() {
        "live".to_string()
    } else {
        cleaned
    }
}

fn live_preview_candidates_for_job(job_id: Option<&str>) -> Vec<PathBuf> {
    let root = agent_root();
    let mut candidates = Vec::new();
    if let Some(id) = job_id {
        let safe = sanitize_preview_job_id(id);
        let name = format!("preview-{safe}.jpg");
        candidates.push(root.join("outputs").join(&name));
        candidates.push(outputs_root(&root).join(&name));
    }
    candidates.extend(live_preview_candidates());
    candidates
}

fn preview_file_matches_job(path: &Path, job_id: &str) -> bool {
    let Some(name) = path.file_name().and_then(|n| n.to_str()) else {
        return false;
    };
    let safe = sanitize_preview_job_id(job_id);
    name.eq_ignore_ascii_case("preview.jpg")
        || name.eq_ignore_ascii_case(&format!("preview-{safe}.jpg"))
}

fn resolve_preview_file(path_str: &str) -> Option<PathBuf> {
    let path = PathBuf::from(path_str);
    if path.is_file() {
        return Some(path);
    }
    let root = agent_root();
    let relative = path.strip_prefix(&root).ok().map(|p| root.join(p));
    if let Some(candidate) = relative {
        if candidate.is_file() {
            return Some(candidate);
        }
    }
    for candidate in live_preview_candidates() {
        if candidate.is_file() {
            return Some(candidate);
        }
    }
    None
}

fn resolve_image_file(path_str: &str) -> Option<PathBuf> {
    let path = PathBuf::from(path_str);
    if path.is_file() {
        return Some(path);
    }
    let root = agent_root();
    if !path.is_absolute() {
        let candidate = root.parent().unwrap_or(&root).join(&path);
        if candidate.is_file() {
            return Some(candidate);
        }
    }
    let parts: Vec<_> = path.components().collect();
    if let Some(idx) = parts.iter().position(|c| {
        c.as_os_str()
            .to_string_lossy()
            .eq_ignore_ascii_case("outputs")
    }) {
        let mut candidate = outputs_root(&root);
        for component in parts.iter().skip(idx + 1) {
            candidate.push(component.as_os_str());
        }
        if candidate.is_file() {
            return Some(candidate);
        }
    }
    None
}

fn preview_bytes_with_retry(path: &Path, attempts: u32, max_edge: u32) -> Option<Vec<u8>> {
    for attempt in 0..attempts {
        if path.is_file() {
            if let Some(bytes) = preview_bytes_from_path(path, max_edge) {
                return Some(bytes);
            }
        }
        if attempt + 1 < attempts {
            std::thread::sleep(Duration::from_millis(40));
        }
    }
    None
}

/// Wait until the file exists and size is stable (flush complete).
fn preview_bytes_with_retry_stable(path: &Path, max_edge: u32, max_attempts: u32) -> Option<Vec<u8>> {
    let mut last_size: u64 = 0;
    let mut stable = 0u32;
    for _ in 0..max_attempts {
        if path.is_file() {
            if let Ok(meta) = fs::metadata(path) {
                let size = meta.len();
                if size > 128 {
                    if size == last_size {
                        stable += 1;
                        if stable >= 2 {
                            if let Some(bytes) = preview_bytes_from_path(path, max_edge) {
                                return Some(bytes);
                            }
                        }
                    } else {
                        stable = 0;
                    }
                    last_size = size;
                }
            }
        }
        std::thread::sleep(Duration::from_millis(50));
    }
    preview_bytes_with_retry(path, 6, max_edge)
}

fn attach_resolved_paths(payload: &mut Value, path: &Path) {
    if let Some(obj) = payload.as_object_mut() {
        obj.insert(
            "preview_path".into(),
            json!(path.to_string_lossy()),
        );
    }
}

fn attach_preview_bytes(payload: &mut Value, path: &Path, bytes: &[u8]) {
    attach_resolved_paths(payload, path);
    if let Some(obj) = payload.as_object_mut() {
        obj.insert(
            "data_url".into(),
            json!(format!("data:image/png;base64,{}", STANDARD.encode(bytes))),
        );
        obj.insert("mime".into(), json!("image/png"));
    }
}

fn emit_live_preview_from_disk(app: &AppHandle, job_id: Option<&str>) {
    for candidate in live_preview_candidates_for_job(job_id) {
        if !candidate.is_file() {
            continue;
        }
        let Some(bytes) = preview_bytes_with_retry(&candidate, 3, PREVIEW_LIVE_MAX_EDGE) else {
            continue;
        };
        let mut payload = json!({
            "type": "preview",
            "has_preview": true,
            "live": true,
            "final_preview": false,
        });
        if let Some(id) = job_id {
            payload["job_id"] = json!(id);
        }
        attach_preview_bytes(&mut payload, &candidate, &bytes);
        let _ = app.emit("generation-preview", payload);
        return;
    }
}

fn stop_live_preview_watch(state: &AppState) {
    if let Ok(mut guard) = state.preview_watcher.lock() {
        *guard = None;
    }
}

fn start_live_preview_watch(app: &AppHandle, state: &Arc<AppState>, job_id: &str) {
    stop_live_preview_watch(state);
    let app_handle = app.clone();
    let job = job_id.to_string();
    let Ok(mut watcher) = RecommendedWatcher::new(
        move |res: notify::Result<notify::Event>| {
            let Ok(event) = res else {
                return;
            };
            let is_preview = event.paths.iter().any(|p| {
                preview_file_matches_job(p, &job)
            });
            if !is_preview {
                return;
            }
            emit_live_preview_from_disk(&app_handle, Some(&job));
        },
        Config::default().with_poll_interval(Duration::from_millis(80)),
    ) else {
        return;
    };

    let root = agent_root();
    let outputs = outputs_root(&root);
    let _ = fs::create_dir_all(&outputs);
    let _ = watcher.watch(&outputs, RecursiveMode::Recursive);
    let legacy = root.join("outputs");
    let _ = fs::create_dir_all(&legacy);
    let _ = watcher.watch(&legacy, RecursiveMode::Recursive);

    if let Ok(mut guard) = state.preview_watcher.lock() {
        *guard = Some(watcher);
    }
}

fn emit_final_preview_for_path(app: &AppHandle, path_str: &str, job_id: &str) {
    let file = resolve_image_file(path_str)
        .or_else(|| {
            let p = PathBuf::from(path_str);
            if p.is_file() {
                Some(p)
            } else {
                None
            }
        });
    let Some(file) = file else {
        return;
    };
    let Some(bytes) = preview_bytes_with_retry_stable(&file, PREVIEW_FINAL_MAX_EDGE, 40) else {
        return;
    };
    let mut payload = json!({
        "type": "preview",
        "job_id": job_id,
        "live": false,
        "final_preview": true,
        "has_preview": true,
    });
    attach_preview_bytes(&mut payload, &file, &bytes);
    let _ = app.emit("generation-preview", payload);
}

fn preview_bytes_from_path(path: &Path, max_edge: u32) -> Option<Vec<u8>> {
    let meta = fs::metadata(path).ok()?;
    if meta.len() > PREVIEW_MAX_BYTES {
        return None;
    }
    let img = image::open(path).ok()?;
    let (w, h) = img.dimensions();
    let bytes = if w <= max_edge && h <= max_edge {
        let mut buf = Vec::new();
        img.write_to(&mut std::io::Cursor::new(&mut buf), image::ImageFormat::Png)
            .ok()?;
        buf
    } else {
        let thumb = img.resize(max_edge, max_edge, FilterType::Triangle);
        let mut buf = Vec::new();
        thumb
            .write_to(&mut std::io::Cursor::new(&mut buf), image::ImageFormat::Png)
            .ok()?;
        buf
    };
    Some(bytes)
}

fn worker_script(root: &Path) -> PathBuf {
    root.join("dreamforge_desktop_worker.py")
}

fn set_engine_health(app: &AppHandle, state: &AppState, health: &str) {
    let prev = state
        .engine_health
        .lock()
        .map(|g| g.clone())
        .unwrap_or_else(|_| "unknown".to_string());
    if let Ok(mut guard) = state.engine_health.lock() {
        *guard = health.to_string();
    }
    if prev != health {
        let _ = app.emit(
            "engine-health-status",
            json!({ "health": health, "previous": prev }),
        );
    }
}

fn emit_preview_from_event(app: &AppHandle, value: &Value) {
    let mut payload = value.clone();
    let is_final = value.get("final_preview") == Some(&Value::Bool(true))
        || value.get("final") == Some(&Value::Bool(true));
    let is_live = !is_final
        && (value.get("live") == Some(&Value::Bool(true))
            || value.get("has_preview") == Some(&Value::Bool(true)));
    let max_edge = if is_final {
        PREVIEW_FINAL_MAX_EDGE
    } else {
        PREVIEW_LIVE_MAX_EDGE
    };

    if let Some(obj) = payload.as_object_mut() {
        obj.insert("live".into(), json!(is_live && !is_final));
        obj.insert("final_preview".into(), json!(is_final));
    }

    if let Some(b64) = value.get("image_b64").and_then(|v| v.as_str()) {
        let mime = value
            .get("image_mime")
            .and_then(|v| v.as_str())
            .unwrap_or("image/jpeg");
        payload["data_url"] = json!(format!("data:{mime};base64,{b64}"));
        if is_live {
            if let Some(path_str) = value.get("preview_path").and_then(|v| v.as_str()) {
                if let Some(path) = resolve_preview_file(path_str) {
                    attach_resolved_paths(&mut payload, &path);
                }
            }
        }
    } else if let Some(path_str) = value.get("preview_path").and_then(|v| v.as_str()) {
        if let Some(path) = resolve_preview_file(path_str) {
            let attempts = if is_final { 20u32 } else { 4 };
            if let Some(bytes) = preview_bytes_with_retry(&path, attempts, max_edge) {
                attach_preview_bytes(&mut payload, &path, &bytes);
            } else {
                attach_resolved_paths(&mut payload, &path);
            }
        } else {
            payload["preview_path"] = json!(path_str);
        }
    } else if value.get("has_preview") == Some(&Value::Bool(true)) {
        let job_id = value.get("job_id").and_then(|v| v.as_str());
        for candidate in live_preview_candidates_for_job(job_id) {
            if candidate.is_file() {
                if let Some(bytes) = preview_bytes_with_retry(&candidate, 3, PREVIEW_LIVE_MAX_EDGE)
                {
                    attach_preview_bytes(&mut payload, &candidate, &bytes);
                } else {
                    attach_resolved_paths(&mut payload, &candidate);
                }
                break;
            }
        }
    }
    let _ = app.emit("generation-preview", payload);
}

fn append_generation_log(state: &AppState, value: &Value) {
    let job_id = value.get("job_id").and_then(|v| v.as_str()).unwrap_or("");
    if job_id.is_empty() {
        return;
    }
    let log_path = {
        let Ok(guard) = state.generation.lock() else {
            return;
        };
        guard
            .as_ref()
            .filter(|job| job.job_id == job_id)
            .map(|job| job.log_path.clone())
            .unwrap_or_else(|| dreamforge_logs_dir(&agent_root()).join(format!("{job_id}.log")))
    };
    if let Some(parent) = log_path.parent() {
        let _ = fs::create_dir_all(parent);
    }
    let event_type = value.get("type").and_then(|v| v.as_str()).unwrap_or("event");
    let message = value
        .get("message")
        .or_else(|| value.get("title"))
        .or_else(|| value.get("error"))
        .and_then(|v| v.as_str())
        .unwrap_or("");
    let line = if message.is_empty() {
        format!("{event_type}: {value}\n")
    } else {
        format!("{event_type}: {message}\n")
    };
    if let Ok(mut file) = OpenOptions::new().create(true).append(true).open(&log_path) {
        let _ = file.write_all(line.as_bytes());
    }
}

fn handle_worker_event(app: &AppHandle, state: &AppState, value: &Value, emit_boot_progress: bool) {
    append_generation_log(state, value);
    let event_type = value.get("type").and_then(|v| v.as_str()).unwrap_or("");
    let generation_arc = &state.generation;
    let worker_ready = &state.worker_ready;

    match event_type {
        "boot_progress" => {
            if state.worker_ready.lock().map(|r| *r).unwrap_or(false) {
                return;
            }
            let msg = value
                .get("message")
                .and_then(|v| v.as_str())
                .unwrap_or("Loading…");
            let phase = value
                .get("phase")
                .and_then(|v| v.as_str())
                .unwrap_or("loading_pipeline");
            if let Ok(mut last) = state.last_boot_message.lock() {
                *last = msg.to_string();
            }
            if let Ok(mut phase_guard) = state.last_boot_phase.lock() {
                *phase_guard = phase.to_string();
            }
            set_engine_health(app, state, "booting");
            if emit_boot_progress {
                let _ = app.emit(
                    "worker-boot-progress",
                    json!({ "message": msg, "phase": phase }),
                );
            }
        }
        "ready" => {
            if let Ok(mut ready) = worker_ready.lock() {
                *ready = true;
            }
            if let Ok(mut last) = state.last_boot_message.lock() {
                last.clear();
            }
            if let Ok(mut phase_guard) = state.last_boot_phase.lock() {
                *phase_guard = "ready".to_string();
            }
            if let Ok(mut restarts) = state.worker_auto_restarts.lock() {
                *restarts = 0;
            }
            if let Some(name) = value.get("gpu_name").and_then(|v| v.as_str()) {
                if let Ok(mut g) = state.gpu_name.lock() {
                    *g = Some(name.to_string());
                }
            }
            if let Some(vram) = value.get("vram_gb").and_then(|v| v.as_f64()) {
                if let Ok(mut g) = state.vram_gb.lock() {
                    *g = Some(vram);
                }
            }
            if let Some(cuda) = value.get("cuda_available").and_then(|v| v.as_bool()) {
                if let Ok(mut g) = state.cuda_available.lock() {
                    *g = Some(cuda);
                }
            }
            if let Some(mps) = value.get("mps_available").and_then(|v| v.as_bool()) {
                if let Ok(mut g) = state.mps_available.lock() {
                    *g = Some(mps);
                }
            }
            set_engine_health(app, state, "alive");
            let _ = app.emit(
                "worker-ready",
                json!({
                    "ready": true,
                    "preview_path": value.get("preview_path"),
                    "gpu_name": value.get("gpu_name"),
                    "vram_gb": value.get("vram_gb"),
                }),
            );
        }
        "progress" => {
            if let Ok(mut slot) = state.last_generation_progress.lock() {
                *slot = Some(value.clone());
            }
            let _ = app.emit("generation-progress", value.clone());
        }
        "preview" | "started" => {
            emit_preview_from_event(app, value);
        }
        "finished" => {
            let job_id = value
                .get("job_id")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string();
            let success = value.get("success") == Some(&Value::Bool(true));
            let result = value.get("result");
            let code = if success {
                None
            } else {
                result
                    .and_then(|r| r.get("code"))
                    .and_then(|v| v.as_str())
                    .map(|s| s.to_string())
                    .or_else(|| {
                        result
                            .and_then(|r| r.get("error"))
                            .and_then(|v| v.as_str())
                            .map(|s| s.to_string())
                    })
            };
            let message = result
                .and_then(|r| r.get("message"))
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string();
            let suggestions = result
                .and_then(|r| r.get("suggestions"))
                .cloned()
                .unwrap_or(Value::Null);
            let details = result
                .and_then(|r| r.get("details"))
                .cloned()
                .unwrap_or(Value::Null);
            let recoverable = result
                .and_then(|r| r.get("recoverable"))
                .and_then(|v| v.as_bool());
            let log_tail = if success {
                String::new()
            } else if !job_id.is_empty() {
                let fallback = if !message.is_empty() {
                    message.clone()
                } else {
                    code.clone().unwrap_or_else(|| "generation_failed".to_string())
                };
                generation_failure_log_tail(&job_id, state, &fallback)
            } else if !message.is_empty() {
                message.clone()
            } else {
                code.clone().unwrap_or_default()
            };

            if let Ok(mut guard) = generation_arc.lock() {
                if guard.is_some()
                    && (job_id.is_empty()
                        || guard.as_ref().map(|g| g.job_id.as_str()) == Some(job_id.as_str()))
                {
                    *guard = None;
                }
            }
            if let Ok(mut prog) = state.last_generation_progress.lock() {
                *prog = Some(json!({
                    "phase": "complete",
                    "progress": 100,
                    "message": "Complete",
                }));
            }

            let err_field = if success {
                Value::Null
            } else {
                json!(code.clone().unwrap_or_else(|| "generation_failed".to_string()))
            };

            let mut finish_preview_path: Option<String> = None;
            let mut finish_data_url: Option<String> = None;
            if success {
                if let Some(images) = result.and_then(|r| r.get("images")).and_then(|v| v.as_array()) {
                    if let Some(first) = images.first().and_then(|i| i.get("path")).and_then(|p| p.as_str()) {
                        if !job_id.is_empty() {
                            emit_final_preview_for_path(app, first, &job_id);
                        }
                        if let Some(file) = resolve_image_file(first) {
                            finish_preview_path = Some(file.to_string_lossy().to_string());
                            if let Some(bytes) =
                                preview_bytes_with_retry_stable(&file, PREVIEW_FINAL_MAX_EDGE, 40)
                            {
                                finish_data_url = Some(format!(
                                    "data:image/png;base64,{}",
                                    STANDARD.encode(bytes)
                                ));
                            }
                        }
                    }
                }
            }

            stop_live_preview_watch(state);

            let payload = json!({
                "job_id": job_id,
                "success": success,
                "code": if success { Value::Null } else { json!(code.clone().unwrap_or_else(|| "generation_failed".to_string())) },
                "error": err_field,
                "message": if success { Value::Null } else { json!(message) },
                "suggestions": if success { Value::Null } else { suggestions },
                "details": if success { Value::Null } else { details },
                "recoverable": if success { Value::Null } else { json!(recoverable) },
                "log_tail": log_tail,
                "result": result,
                "preview_path": finish_preview_path,
                "data_url": finish_data_url,
            });
            let _ = app.emit("generation-finished", payload);
            if success {
                let _ = app.emit("outputs-changed", json!({}));
            } else if code.as_deref() == Some("out_of_memory") {
                // OOM leaves VRAM fragmented; mark worker not ready so the UI restarts before the next job.
                if let Ok(mut ready) = worker_ready.lock() {
                    *ready = false;
                }
                set_engine_health(app, state, "dead");
            }
        }
        "warning" => {
            // Advisory events (low_disk_space, vram_headroom_low, ...).
            // Forwarded verbatim so the UI can render them as informational
            // toasts without aborting the generation.
            let _ = app.emit("generation-warning", value.clone());
        }
        "error" => {
            let job_id = value.get("job_id").and_then(|v| v.as_str()).unwrap_or("");
            // Prefer the new structured `code` field, fall back to legacy `error`.
            let code = value
                .get("code")
                .and_then(|v| v.as_str())
                .or_else(|| value.get("error").and_then(|v| v.as_str()))
                .unwrap_or("worker_error")
                .to_string();
            let message = value
                .get("message")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string();
            let suggestions = value.get("suggestions").cloned().unwrap_or(Value::Null);
            let details = value.get("details").cloned().unwrap_or(Value::Null);
            let recoverable = value
                .get("recoverable")
                .and_then(|v| v.as_bool());

            if job_id.is_empty() {
                let root = agent_root();
                let log = worker_log_path(&root);
                let tail = tail_log_file(&log, LOG_TAIL_CHARS);
                set_engine_health(app, state, "dead");
                let _ = app.emit(
                    "worker-failed",
                    json!({
                        "error": code,
                        "code": code,
                        "message": message,
                        "suggestions": suggestions,
                        "details": details,
                        "log_tail": tail,
                    }),
                );
                return;
            }
            if code == "generation_in_progress" {
                let _ = app.emit(
                    "generation-busy",
                    json!({
                        "code": 409,
                        "error": code,
                        "message": message,
                    }),
                );
            }
            if let Ok(mut guard) = generation_arc.lock() {
                *guard = None;
            }
            stop_live_preview_watch(state);
            let log_tail = if job_id.is_empty() {
                String::new()
            } else {
                let fallback = if !message.is_empty() {
                    message.clone()
                } else {
                    code.clone()
                };
                generation_failure_log_tail(job_id, state, &fallback)
            };
            let _ = app.emit(
                "generation-finished",
                json!({
                    "job_id": job_id,
                    "success": false,
                    "error": code,
                    "code": code,
                    "message": message,
                    "suggestions": suggestions,
                    "details": details,
                    "recoverable": recoverable,
                    "log_tail": log_tail,
                }),
            );
        }
        _ => {}
    }
}

/// Authoritative boot state from worker.events (survives missed Tauri events).
fn parse_worker_events_snapshot(events_path: &Path) -> Option<WorkerEventsSnapshot> {
    let content = fs::read_to_string(events_path).ok()?;
    let mut snap = WorkerEventsSnapshot {
        ready: false,
        boot_message: String::new(),
        boot_phase: "starting".to_string(),
        gpu_name: None,
        vram_gb: None,
        cuda_available: None,
        mps_available: None,
    };
    for line in content.lines() {
        let line = line.trim();
        if line.is_empty() {
            continue;
        }
        // Skip malformed lines (e.g. partial writes during boot) instead of aborting.
        let Ok(value) = serde_json::from_str::<Value>(line) else {
            continue;
        };
        let event_type = value.get("type").and_then(|v| v.as_str()).unwrap_or("");
        match event_type {
            "boot_progress" => {
                snap.boot_message = value
                    .get("message")
                    .and_then(|v| v.as_str())
                    .unwrap_or("")
                    .to_string();
                snap.boot_phase = value
                    .get("phase")
                    .and_then(|v| v.as_str())
                    .unwrap_or("loading_pipeline")
                    .to_string();
            }
            "ready" => {
                snap.ready = true;
                snap.boot_phase = "ready".to_string();
                snap.boot_message.clear();
                snap.gpu_name = value
                    .get("gpu_name")
                    .and_then(|v| v.as_str())
                    .map(|s| s.to_string());
                snap.vram_gb = value.get("vram_gb").and_then(|v| v.as_f64());
                snap.cuda_available = value.get("cuda_available").and_then(|v| v.as_bool());
                snap.mps_available = value.get("mps_available").and_then(|v| v.as_bool());
            }
            "error" if value.get("job_id").is_none() => {
                snap.ready = false;
                snap.boot_phase = "failed".to_string();
                snap.boot_message = value
                    .get("error")
                    .and_then(|v| v.as_str())
                    .unwrap_or("worker_error")
                    .to_string();
            }
            _ => {}
        }
    }
    Some(snap)
}

struct WorkerEventsSnapshot {
    ready: bool,
    boot_message: String,
    boot_phase: String,
    gpu_name: Option<String>,
    vram_gb: Option<f64>,
    cuda_available: Option<bool>,
    mps_available: Option<bool>,
}

fn worker_child_alive(state: &AppState) -> bool {
    let Ok(guard) = state.worker.lock() else {
        return false;
    };
    let Some(worker) = guard.as_ref() else {
        return false;
    };
    gpu_worker_alive(worker)
}

fn gpu_worker_alive(worker: &GpuWorker) -> bool {
    worker
        ._child
        .lock()
        .ok()
        .and_then(|mut c| c.try_wait().ok().flatten())
        .is_none()
}

fn drain_worker_events_file(app: &AppHandle, state: &AppState, events_path: &Path) -> bool {
    let already_ready = state.worker_ready.lock().map(|r| *r).unwrap_or(false);
    let file_len = fs::metadata(events_path).ok().map(|m| m.len()).unwrap_or(0);
    let mut offset = match state.worker_events_offset.lock() {
        Ok(g) => g,
        Err(_) => return already_ready,
    };
    if file_len <= *offset {
        return already_ready;
    }

    let Ok(content) = fs::read_to_string(events_path) else {
        return already_ready;
    };

    let start = *offset as usize;
    let new_part = &content[start..];
    let mut saw_ready = already_ready;
    for line in new_part.lines() {
        let line = line.trim();
        if line.is_empty() {
            continue;
        }
        if let Ok(value) = serde_json::from_str::<Value>(line) {
            if value.get("type").and_then(|v| v.as_str()) == Some("ready") {
                saw_ready = true;
            }
            // Emit incremental boot progress to the UI; handle_worker_event ignores
            // boot_progress once worker_ready is already true.
            handle_worker_event(app, state, &value, true);
        }
    }
    *offset = content.len() as u64;
    drop(offset);

    if !saw_ready && !state.worker_ready.lock().map(|r| *r).unwrap_or(false) {
        if let Some(snap) = parse_worker_events_snapshot(events_path) {
            if snap.ready {
                if let Ok(mut ready) = state.worker_ready.lock() {
                    *ready = true;
                }
                if let Ok(mut phase) = state.last_boot_phase.lock() {
                    *phase = "ready".to_string();
                }
                if let Ok(mut last) = state.last_boot_message.lock() {
                    last.clear();
                }
                if let Some(name) = &snap.gpu_name {
                    if let Ok(mut g) = state.gpu_name.lock() {
                        *g = Some(name.clone());
                    }
                }
                if let Some(vram) = snap.vram_gb {
                    if let Ok(mut g) = state.vram_gb.lock() {
                        *g = Some(vram);
                    }
                }
                set_engine_health(app, state, "alive");
                let _ = app.emit(
                    "worker-ready",
                    json!({
                        "ready": true,
                        "gpu_name": snap.gpu_name,
                        "vram_gb": snap.vram_gb,
                    }),
                );
            }
        }
    }

    state.worker_ready.lock().map(|r| *r).unwrap_or(false)
}

fn spawn_worker_stderr_reader(stderr: impl Read + Send + 'static, worker_log: PathBuf) {
    std::thread::spawn(move || {
        let reader = BufReader::new(stderr);
        let mut log_file = OpenOptions::new()
            .create(true)
            .append(true)
            .open(&worker_log)
            .ok();
        for line in reader.lines() {
            let Ok(line) = line else { break };
            if line.is_empty() {
                continue;
            }
            if let Some(f) = log_file.as_mut() {
                let _ = writeln!(f, "{line}");
                let _ = f.flush();
            }
        }
    });
}

fn spawn_worker_events_poller(
    app: AppHandle,
    state: Arc<AppState>,
    child: Arc<Mutex<Child>>,
    events_path: PathBuf,
) {
    std::thread::spawn(move || loop {
        drain_worker_events_file(&app, &state, &events_path);
        let exited = child
            .lock()
            .ok()
            .and_then(|mut c| c.try_wait().ok().flatten())
            .is_some();
        if exited {
            drain_worker_events_file(&app, &state, &events_path);
            break;
        }
        let ready = state.worker_ready.lock().map(|r| *r).unwrap_or(false);
        let generating = state
            .generation
            .lock()
            .map(|g| g.is_some())
            .unwrap_or(false);
        let sleep_ms = if generating {
            50
        } else if ready {
            2000
        } else {
            500
        };
        std::thread::sleep(Duration::from_millis(sleep_ms));
    });
}

fn spawn_boot_timeout_watcher(
    app: AppHandle,
    state: Arc<AppState>,
    child: Arc<Mutex<Child>>,
    worker_log: PathBuf,
    events_path: PathBuf,
) {
    std::thread::spawn(move || {
        let polls = WORKER_BOOT_TIMEOUT_MS / WORKER_BOOT_POLL_MS;
        for _ in 0..polls {
            // spawn_worker_events_poller drains worker.events — avoid duplicate IO here.
            if state.worker_ready.lock().map(|r| *r).unwrap_or(false) {
                return;
            }
            let exited = child
                .lock()
                .ok()
                .and_then(|mut c| c.try_wait().ok().flatten())
                .is_some();
            if exited {
                drain_worker_events_file(&app, &state, &events_path);
                return;
            }
            std::thread::sleep(Duration::from_millis(WORKER_BOOT_POLL_MS));
        }
        if state.worker_ready.lock().map(|r| *r).unwrap_or(false) {
            return;
        }
        let tail = tail_log_file(&worker_log, LOG_TAIL_CHARS);
        let _ = app.emit(
            "worker-failed",
            json!({
                "error": "GPU worker did not become ready in time. See worker.log for details.",
                "log_tail": tail,
            }),
        );
    });
}

fn reset_worker_runtime_state(state: &AppState) {
    if let Ok(mut ready) = state.worker_ready.lock() {
        *ready = false;
    }
    if let Ok(mut phase) = state.last_boot_phase.lock() {
        *phase = "starting".to_string();
    }
    if let Ok(mut started) = state.worker_boot_started.lock() {
        *started = None;
    }
    if let Ok(mut off) = state.worker_events_offset.lock() {
        *off = 0;
    }
}

fn request_worker_shutdown(worker: &GpuWorker) {
    if !gpu_worker_alive(worker) {
        return;
    }
    if let Ok(mut stdin) = worker.stdin.lock() {
        let _ = writeln!(stdin, "{}", json!({ "cmd": "shutdown" }));
        let _ = stdin.flush();
    }
}

fn wait_for_worker_exit(child_arc: &Arc<Mutex<Child>>, timeout_ms: u64) {
    let deadline = Instant::now() + Duration::from_millis(timeout_ms);
    while Instant::now() < deadline {
        if let Ok(mut child) = child_arc.lock() {
            if child.try_wait().ok().flatten().is_some() {
                return;
            }
        }
        std::thread::sleep(Duration::from_millis(WORKER_SHUTDOWN_POLL_MS));
    }
}

fn stop_gpu_worker(state: &AppState) -> Result<(), String> {
    reset_worker_runtime_state(state);

    let child_arc = {
        let guard = state.worker.lock().map_err(|e| e.to_string())?;
        guard.as_ref().and_then(|worker| {
            if gpu_worker_alive(worker) {
                request_worker_shutdown(worker);
                Some(Arc::clone(&worker._child))
            } else {
                None
            }
        })
    };

    if let Some(child_arc) = child_arc {
        wait_for_worker_exit(&child_arc, WORKER_SHUTDOWN_TIMEOUT_MS);
    }

    let mut guard = state.worker.lock().map_err(|e| e.to_string())?;
    if let Some(worker) = guard.take() {
        if let Ok(mut child) = worker._child.lock() {
            if child.try_wait().ok().flatten().is_none() {
                let _ = child.kill();
            }
            let _ = child.wait();
        }
    }
    Ok(())
}

fn shutdown_all_services(state: &AppState) {
    let _ = stop_gpu_worker(state);
    reset_bridge_sidecar(state);
}

async fn wait_for_worker_ready(app: &AppHandle, state: &Arc<AppState>) -> Result<(), String> {
    let events_path = worker_events_path(&agent_root());
    let polls = WORKER_BOOT_TIMEOUT_MS / WORKER_BOOT_POLL_MS;
    for _ in 0..polls {
        drain_worker_events_file(app, state, &events_path);
        if *state.worker_ready.lock().map_err(|e| e.to_string())? {
            return Ok(());
        }
        tokio::time::sleep(Duration::from_millis(WORKER_BOOT_POLL_MS)).await;
    }
    drain_worker_events_file(app, state, &events_path);
    let root = agent_root();
    let log = worker_log_path(&root);
    let tail = tail_log_file(&log, LOG_TAIL_CHARS);
    Err(format!(
        "GPU worker did not become ready in time. Check {}. {}",
        log.display(),
        tail.lines().last().unwrap_or("")
    ))
}

fn start_gpu_worker(app: AppHandle, root: &Path, state: &Arc<AppState>) -> Result<(), String> {
    let events_path = worker_events_path(root);
    {
        let guard = state.worker.lock().map_err(|e| e.to_string())?;
        if guard.is_some() {
            if guard.as_ref().map(gpu_worker_alive).unwrap_or(false) {
                drain_worker_events_file(&app, state, &events_path);
                return Ok(());
            }
        }
    }
    // Stale handle (process exited) — shut down cleanly before respawn.
    stop_gpu_worker(state)?;

    let _ = app.emit("worker-status", json!({ "status": "booting" }));
    let mut guard = state.worker.lock().map_err(|e| e.to_string())?;
    set_engine_health(&app, state, "booting");
    if let Ok(mut phase) = state.last_boot_phase.lock() {
        *phase = "starting".to_string();
    }

    let python = python_exe(root);
    let script = worker_script(root);
    #[cfg(windows)]
    let exists = python.is_file();
    #[cfg(not(windows))]
    let exists = python.is_file()
        || python.to_string_lossy() == "python3"
        || python.to_string_lossy() == "python";
    if !exists {
        return Err(format!("Python runtime not found: {}", python.display()));
    }
    if !script.is_file() {
        return Err(format!("Worker script not found: {}", script.display()));
    }

    if let Ok(mut ready) = state.worker_ready.lock() {
        *ready = false;
    }
    if let Ok(mut started) = state.worker_boot_started.lock() {
        *started = Some(Instant::now());
    }

    let logs_dir = dreamforge_logs_dir(root);
    fs::create_dir_all(&logs_dir).map_err(|e| e.to_string())?;
    let worker_log = worker_log_path(root);
    reset_worker_events_file(root);
    if let Ok(mut off) = state.worker_events_offset.lock() {
        *off = 0;
    }
    if let Ok(mut msg) = state.last_boot_message.lock() {
        msg.clear();
    }
    let _ = OpenOptions::new()
        .create(true)
        .write(true)
        .truncate(true)
        .open(&worker_log);

    let mut cmd = Command::new(&python);
    cmd.current_dir(root)
        .arg("-u")
        .arg("-s")
        .arg(&script)
        .env("PYTHONIOENCODING", "utf-8")
        .env("PYTHONUTF8", "1")
        .env("PYTHONUNBUFFERED", "1")
        .env("HF_HUB_OFFLINE", "1")
        .env("TRANSFORMERS_OFFLINE", "1")
        .env("TOKENIZERS_PARALLELISM", "false")
        .env("DREAMFORGE_HEADLESS", "1")
        .env("DREAMFORGE_USE_COMFY_SERVER", "1");
    if let Ok(slot) = state.desktop_vram_profile.lock() {
        if let Some(mode) = map_vram_profile_to_desktop_mode(&slot) {
            cmd.env("DREAMFORGE_DESKTOP_VRAM_MODE", mode);
        }
    }
    cmd.stdin(Stdio::piped())
        .stdout(Stdio::null())
        .stderr(Stdio::piped());
    #[cfg(windows)]
    cmd.creation_flags(CREATE_NO_WINDOW);

    let mut child = cmd
        .spawn()
        .map_err(|e| format!("Failed to start GPU worker: {e}"))?;
    let stdin = child
        .stdin
        .take()
        .ok_or_else(|| "Worker stdin unavailable".to_string())?;
    let stderr = child
        .stderr
        .take()
        .ok_or_else(|| "Worker stderr unavailable".to_string())?;

    let child_arc = Arc::new(Mutex::new(child));
    let state_arc = Arc::clone(state);
    spawn_worker_stderr_reader(stderr, worker_log.clone());
    spawn_worker_events_poller(
        app.clone(),
        state_arc.clone(),
        Arc::clone(&child_arc),
        events_path.clone(),
    );
    spawn_worker_exit_watcher(
        app.clone(),
        Arc::clone(state),
        Arc::clone(&child_arc),
        worker_log.clone(),
        events_path.clone(),
    );
    spawn_boot_timeout_watcher(
        app.clone(),
        state_arc,
        Arc::clone(&child_arc),
        worker_log,
        events_path,
    );

    *guard = Some(GpuWorker {
        _child: child_arc,
        stdin: Mutex::new(stdin),
    });

    Ok(())
}

fn bridge_request_once(state: &Arc<AppState>, cmd: &str, params: Value) -> Result<Value, String> {
    let guard = state.sidecar.lock().map_err(|e| e.to_string())?;
    let sidecar = guard
        .as_ref()
        .ok_or_else(|| "Bridge sidecar not running".to_string())?;
    sidecar.request(cmd, params)
}

fn bridge_request(state: &Arc<AppState>, cmd: &str, params: Value) -> Result<Value, String> {
    ensure_bridge_sidecar(state)?;
    match bridge_request_once(state, cmd, params.clone()) {
        Ok(value) => Ok(value),
        Err(err) if is_sidecar_protocol_error(&err) => {
            reset_bridge_sidecar(state);
            ensure_bridge_sidecar(state)?;
            bridge_request_once(state, cmd, params)
        }
        Err(err) => Err(err),
    }
}

async fn bridge_request_async(
    state: &Arc<AppState>,
    cmd: &str,
    params: Value,
) -> Result<Value, String> {
    let state = Arc::clone(state);
    let cmd = cmd.to_string();
    tokio::task::spawn_blocking(move || bridge_request(&state, &cmd, params))
        .await
        .map_err(|e| format!("bridge task failed: {e}"))?
}

fn tail_file(path: &Path, max_chars: usize) -> String {
    let Ok(mut file) = fs::File::open(path) else {
        return String::new();
    };
    let len = file.metadata().map(|m| m.len()).unwrap_or(0);
    let start = len.saturating_sub(max_chars as u64);
    let _ = file.seek(SeekFrom::Start(start));
    let mut buf = String::new();
    let _ = file.read_to_string(&mut buf);
    if start > 0 {
        if let Some(idx) = buf.find('\n') {
            buf = buf[idx + 1..].to_string();
        }
    }
    buf
}

#[tauri::command]
async fn get_paths(state: State<'_, Arc<AppState>>) -> Result<Value, String> {
    bridge_request_async(state.inner(), "get_paths", json!({})).await
}

#[tauri::command]
async fn get_inventory(
    state: State<'_, Arc<AppState>>,
    include_fonts: Option<bool>,
    force_refresh: Option<bool>,
) -> Result<Value, String> {
    bridge_request_async(
        state.inner(),
        "get_inventory",
        json!({
            "include_fonts": include_fonts.unwrap_or(false),
            "force_refresh": force_refresh.unwrap_or(false),
        }),
    )
    .await
}

#[tauri::command]
async fn list_outputs(
    state: State<'_, Arc<AppState>>,
    since: Option<f64>,
    limit: Option<u32>,
    offset: Option<u32>,
    session: Option<String>,
) -> Result<Value, String> {
    bridge_request_async(
        state.inner(),
        "list_outputs",
        json!({
            "since": since,
            "limit": limit.unwrap_or(50),
            "offset": offset.unwrap_or(0),
            "session": session,
        }),
    )
    .await
}

#[tauri::command]
async fn search_outputs(
    state: State<'_, Arc<AppState>>,
    query: String,
    limit: Option<u32>,
    offset: Option<u32>,
) -> Result<Value, String> {
    bridge_request_async(
        state.inner(),
        "search_outputs",
        json!({
            "query": query,
            "limit": limit.unwrap_or(50),
            "offset": offset.unwrap_or(0),
        }),
    )
    .await
}

#[tauri::command]
async fn delete_output(
    state: State<'_, Arc<AppState>>,
    manifest_path: String,
) -> Result<Value, String> {
    bridge_request_async(
        state.inner(),
        "delete_output",
        json!({ "manifest_path": manifest_path }),
    )
    .await
}

#[tauri::command]
async fn delete_output_image(
    state: State<'_, Arc<AppState>>,
    manifest_path: String,
    image_path: String,
) -> Result<Value, String> {
    bridge_request_async(
        state.inner(),
        "delete_output_image",
        json!({ "manifest_path": manifest_path, "image_path": image_path }),
    )
    .await
}

#[tauri::command]
async fn delete_session(
    state: State<'_, Arc<AppState>>,
    session: String,
) -> Result<Value, String> {
    bridge_request_async(
        state.inner(),
        "delete_session",
        json!({ "session": session }),
    )
    .await
}

#[tauri::command]
fn reveal_path_in_explorer(path: String) -> Result<(), String> {
    let path = path.trim();
    if path.is_empty() {
        return Err("empty path".into());
    }
    let p = PathBuf::from(path);
    if !p.exists() {
        return Err(format!("path not found: {path}"));
    }

    #[cfg(windows)]
    {
        use std::process::Command;
        let status = if p.is_file() {
            Command::new("explorer")
                .arg(format!("/select,{}", p.display()))
                .status()
        } else {
            Command::new("explorer").arg(&p).status()
        }
        .map_err(|e| e.to_string())?;
        if status.success() {
            Ok(())
        } else {
            Err("explorer failed to open path".into())
        }
    }

    #[cfg(target_os = "macos")]
    {
        use std::process::Command;
        let status = if p.is_file() {
            Command::new("open").arg("-R").arg(&p).status()
        } else {
            Command::new("open").arg(&p).status()
        }
        .map_err(|e| e.to_string())?;
        if status.success() {
            Ok(())
        } else {
            Err("open failed".into())
        }
    }

    #[cfg(all(not(windows), not(target_os = "macos")))]
    {
        use std::process::Command;
        let dir = if p.is_file() {
            p.parent().map(PathBuf::from).unwrap_or(p)
        } else {
            p
        };
        Command::new("xdg-open")
            .arg(dir)
            .status()
            .map_err(|e| e.to_string())?;
        Ok(())
    }
}

#[tauri::command]
async fn dry_run(state: State<'_, Arc<AppState>>, params: Value) -> Result<Value, String> {
    let mut p = params;
    if let Some(obj) = p.as_object_mut() {
        obj.insert("dry_run".to_string(), Value::Bool(true));
    }
    bridge_request_async(state.inner(), "dry_run", p).await
}

#[tauri::command]
async fn list_styles(state: State<'_, Arc<AppState>>) -> Result<Value, String> {
    bridge_request_async(state.inner(), "list_styles", json!({})).await
}

#[tauri::command]
async fn get_ui_defaults(state: State<'_, Arc<AppState>>) -> Result<Value, String> {
    bridge_request_async(state.inner(), "get_ui_defaults", json!({})).await
}

#[tauri::command]
async fn get_model_gallery(
    state: State<'_, Arc<AppState>>,
    filter: Option<String>,
    force_refresh: Option<bool>,
) -> Result<Value, String> {
    bridge_request_async(
        state.inner(),
        "get_model_gallery",
        json!({
            "filter": filter.unwrap_or_default(),
            "force_refresh": force_refresh.unwrap_or(false),
        }),
    )
    .await
}

#[tauri::command]
async fn get_lora_gallery(
    state: State<'_, Arc<AppState>>,
    filter: Option<String>,
    force_refresh: Option<bool>,
) -> Result<Value, String> {
    bridge_request_async(
        state.inner(),
        "get_lora_gallery",
        json!({
            "filter": filter.unwrap_or_default(),
            "force_refresh": force_refresh.unwrap_or(false),
        }),
    )
    .await
}

#[tauri::command]
async fn refresh_model_library_cache(state: State<'_, Arc<AppState>>) -> Result<Value, String> {
    bridge_request_async(state.inner(), "refresh_model_library_cache", json!({})).await
}

#[tauri::command]
async fn resolve_model_profile(
    state: State<'_, Arc<AppState>>,
    params: Value,
) -> Result<Value, String> {
    bridge_request_async(state.inner(), "resolve_model_profile", params).await
}

#[tauri::command]
async fn check_model_dependencies(
    state: State<'_, Arc<AppState>>,
    model: String,
    performance: Option<String>,
) -> Result<Value, String> {
    bridge_request_async(
        state.inner(),
        "check_model_dependencies",
        json!({ "model": model, "performance": performance }),
    )
    .await
}

#[tauri::command]
async fn download_model_companions(
    state: State<'_, Arc<AppState>>,
    model: String,
    ids: Option<Vec<String>>,
) -> Result<Value, String> {
    bridge_request_async(
        state.inner(),
        "download_model_companions",
        json!({ "model": model, "ids": ids }),
    )
    .await
}

#[tauri::command]
async fn bridge_invoke(
    state: State<'_, Arc<AppState>>,
    cmd: String,
    params: Value,
) -> Result<Value, String> {
    bridge_request_async(state.inner(), &cmd, params).await
}

#[tauri::command]
fn write_temp_png(data_base64: String) -> Result<String, String> {
    let payload = data_base64
        .strip_prefix("data:image/png;base64,")
        .or_else(|| data_base64.strip_prefix("data:image/jpeg;base64,"))
        .unwrap_or(&data_base64);
    let bytes = base64::Engine::decode(&base64::engine::general_purpose::STANDARD, payload)
        .or_else(|_| {
            base64::Engine::decode(
                &base64::engine::general_purpose::STANDARD_NO_PAD,
                payload,
            )
        })
        .map_err(|e| format!("invalid base64: {e}"))?;
    let root = agent_root();
    let dir = root.join("temp").join("studio_masks");
    fs::create_dir_all(&dir).map_err(|e| e.to_string())?;
    let name = format!(
        "mask_{}.png",
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|d| d.as_millis())
            .unwrap_or(0)
    );
    let path = dir.join(name);
    fs::write(&path, bytes).map_err(|e| e.to_string())?;
    Ok(path.to_string_lossy().into_owned())
}

#[tauri::command]
fn pick_image_file() -> Result<Option<String>, String> {
    let picked = rfd::FileDialog::new()
        .add_filter(
            "Images",
            &["png", "jpg", "jpeg", "webp", "bmp", "gif", "tif", "tiff"],
        )
        .pick_file();
    Ok(picked.map(|path| path.to_string_lossy().into_owned()))
}

#[tauri::command]
async fn read_image_preview(path: String, quality: Option<String>) -> Result<Value, String> {
    tokio::task::spawn_blocking(move || {
        let file = resolve_image_file(&path).ok_or_else(|| format!("File not found: {path}"))?;
        let live = quality.as_deref() == Some("live");
        let max_edge = if live {
            PREVIEW_LIVE_MAX_EDGE
        } else {
            PREVIEW_FINAL_MAX_EDGE
        };
        let attempts = if live { 4 } else { 20 };
        let bytes = if live {
            preview_bytes_with_retry(&file, attempts, max_edge)
        } else {
            preview_bytes_with_retry_stable(&file, max_edge, attempts)
        }
        .ok_or_else(|| format!("Cannot read preview: {}", file.display()))?;
        Ok(json!({
            "path": file.to_string_lossy(),
            "mime": "image/png",
            "quality": if live { "live" } else { "final" },
            "data_url": format!("data:image/png;base64,{}", STANDARD.encode(bytes))
        }))
    })
    .await
    .map_err(|e| format!("preview task failed: {e}"))?
}

#[tauri::command]
async fn read_live_preview(state: State<'_, Arc<AppState>>) -> Result<Value, String> {
    let job_id = state
        .generation
        .lock()
        .ok()
        .and_then(|guard| guard.as_ref().map(|job| job.job_id.clone()));
    tokio::task::spawn_blocking(move || {
        for candidate in live_preview_candidates_for_job(job_id.as_deref()) {
            if !candidate.is_file() {
                continue;
            }
            if let Some(bytes) =
                preview_bytes_with_retry(&candidate, 3, PREVIEW_LIVE_MAX_EDGE)
            {
                return Ok(json!({
                    "path": candidate.to_string_lossy(),
                    "mime": "image/png",
                    "quality": "live",
                    "data_url": format!("data:image/png;base64,{}", STANDARD.encode(bytes))
                }));
            }
        }
        Err("No live preview file available".to_string())
    })
    .await
    .map_err(|e| format!("live preview task failed: {e}"))?
}

#[tauri::command]
fn generation_status(state: State<'_, Arc<AppState>>) -> Result<Value, String> {
    let guard = state.generation.lock().map_err(|e| e.to_string())?;
    let progress = state
        .last_generation_progress
        .lock()
        .ok()
        .and_then(|p| p.clone())
        .unwrap_or(json!({ "phase": "idle", "progress": 0 }));
    if let Some(job) = guard.as_ref() {
        Ok(json!({
            "running": true,
            "job_id": job.job_id,
            "log_path": job.log_path,
            "phase": progress.get("phase").unwrap_or(&Value::Null),
            "progress": progress.get("progress").unwrap_or(&Value::Null),
            "message": progress.get("message").unwrap_or(&Value::Null),
        }))
    } else {
        Ok(json!({
            "running": false,
            "phase": "idle",
            "progress": 0,
        }))
    }
}

#[tauri::command]
fn get_generation_progress(state: State<'_, Arc<AppState>>) -> Result<Value, String> {
    let running = state
        .generation
        .lock()
        .map_err(|e| e.to_string())?
        .is_some();
    let snapshot = state
        .last_generation_progress
        .lock()
        .ok()
        .and_then(|p| p.clone())
        .unwrap_or(json!({
            "phase": if running { "preparing" } else { "idle" },
            "progress": 0,
            "message": "",
        }));
    Ok(json!({
        "running": running,
        "phase": snapshot.get("phase").cloned().unwrap_or(Value::Null),
        "progress": snapshot.get("progress").cloned().unwrap_or(Value::Null),
        "message": snapshot.get("message").cloned().unwrap_or(Value::Null),
        "job_id": snapshot.get("job_id").cloned().unwrap_or(Value::Null),
    }))
}

#[tauri::command]
fn read_job_log(job_id: String, state: State<'_, Arc<AppState>>) -> Result<Value, String> {
    let guard = state.generation.lock().map_err(|e| e.to_string())?;
    let log_path = if let Some(job) = guard.as_ref() {
        if job.job_id == job_id {
            job.log_path.clone()
        } else {
            dreamforge_logs_dir(&agent_root()).join(format!("{job_id}.log"))
        }
    } else {
        dreamforge_logs_dir(&agent_root()).join(format!("{job_id}.log"))
    };
    Ok(json!({
        "job_id": job_id,
        "log_path": log_path.to_string_lossy(),
        "tail": tail_file(&log_path, JOB_LOG_TAIL_CHARS),
    }))
}

#[tauri::command]
fn cancel_generation(state: State<'_, Arc<AppState>>) -> Result<Value, String> {
    stop_live_preview_watch(state.inner());
    let job_id = {
        let mut guard = state.generation.lock().map_err(|e| e.to_string())?;
        guard.take().map(|j| j.job_id)
    };
    if let Some(id) = job_id {
        if let Ok(worker_guard) = state.worker.lock() {
            if let Some(worker) = worker_guard.as_ref() {
                if let Ok(mut stdin) = worker.stdin.lock() {
                    let _ = writeln!(stdin, "{}", json!({ "cmd": "stop", "job_id": id }));
                    let _ = stdin.flush();
                }
            }
        }
        Ok(json!({ "cancelled": true, "job_id": id }))
    } else {
        Ok(json!({ "cancelled": false }))
    }
}

#[tauri::command]
async fn invoke_generation(
    app: AppHandle,
    state: State<'_, Arc<AppState>>,
    params: Value,
) -> Result<Value, String> {
    {
        let guard = state.generation.lock().map_err(|e| e.to_string())?;
        if guard.is_some() {
            return Err(
                "generation_in_progress: A generation is already running. Wait for it to finish or cancel first.".into(),
            );
        }
    }

    let root = agent_root();
    if let Some(p) = params.get("vram_profile").and_then(|v| v.as_str()) {
        if let Ok(mut slot) = state.desktop_vram_profile.lock() {
            *slot = p.to_string();
        }
    }
    start_gpu_worker(app.clone(), &root, &state)?;
    wait_for_worker_ready(&app, &state).await?;

    let job_id = Uuid::new_v4().to_string();
    let logs_dir = dreamforge_logs_dir(&root);
    fs::create_dir_all(&logs_dir).map_err(|e| e.to_string())?;
    let log_path = logs_dir.join(format!("{job_id}.log"));

    {
        let mut guard = state.generation.lock().map_err(|e| e.to_string())?;
        *guard = Some(ActiveGeneration {
            job_id: job_id.clone(),
            log_path: log_path.clone(),
        });
    }
    if let Ok(mut prog) = state.last_generation_progress.lock() {
        *prog = Some(json!({
            "phase": "loading_models",
            "progress": 0,
            "message": "Starting generation…",
            "job_id": job_id,
        }));
    }

    let worker_guard = state.worker.lock().map_err(|e| e.to_string())?;
    let worker = worker_guard
        .as_ref()
        .ok_or_else(|| "GPU worker not running".to_string())?;
    let mut stdin = worker.stdin.lock().map_err(|e| e.to_string())?;
    let request = json!({
        "cmd": "generate",
        "job_id": job_id,
        "params": params,
    });
    writeln!(stdin, "{request}").map_err(|e| format!("Failed to send job to GPU worker: {e}"))?;
    stdin
        .flush()
        .map_err(|e| format!("Failed to flush GPU worker stdin: {e}"))?;

    start_live_preview_watch(&app, state.inner(), &job_id);

    let _ = app.emit(
        "generation-started",
        json!({
            "job_id": job_id,
            "log_path": log_path.to_string_lossy(),
            "mode": "worker",
        }),
    );
    let _ = app.emit(
        "generation-progress",
        json!({
            "phase": "loading_models",
            "progress": 0,
            "message": "Starting generation…",
            "job_id": job_id,
        }),
    );

    Ok(json!({
        "job_id": job_id,
        "status": "started",
        "log_path": log_path.to_string_lossy(),
    }))
}

#[tauri::command]
fn start_outputs_watch(app: AppHandle, state: State<'_, Arc<AppState>>) -> Result<Value, String> {
    let root = agent_root();
    let outputs = outputs_root(&root);
    fs::create_dir_all(&outputs).map_err(|e| e.to_string())?;

    let mut guard = state.watcher.lock().map_err(|e| e.to_string())?;
    if guard.is_some() {
        return Ok(json!({ "watching": true, "path": outputs }));
    }

    let app_handle = app.clone();
    let mut watcher = RecommendedWatcher::new(
        move |res: notify::Result<notify::Event>| {
            if res.is_ok() {
                let _ = app_handle.emit("outputs-changed", json!({}));
            }
        },
        Config::default().with_poll_interval(Duration::from_millis(1500)),
    )
    .map_err(|e| e.to_string())?;

    watcher
        .watch(&outputs, RecursiveMode::Recursive)
        .map_err(|e| e.to_string())?;
    *guard = Some(watcher);
    Ok(json!({ "watching": true, "path": outputs }))
}

#[tauri::command]
fn window_drag(app: AppHandle) -> Result<(), String> {
    if let Some(window) = app.get_webview_window("main") {
        window.start_dragging().map_err(|e| e.to_string())?;
    }
    Ok(())
}

#[tauri::command]
async fn download_model(
    app: AppHandle,
    url: String,
    category: String,
    filename: String,
    api_key: Option<String>,
) -> Result<(), String> {
    let root = agent_root();
    let category = match category.as_str() {
        "checkpoints" | "loras" | "vae" | "controlnet" | "clip" | "text_encoders"
        | "upscale_models" | "diffusion_models" => category,
        other => return Err(format!("Unsupported model category: {other}")),
    };
    let filename = safe_model_filename(&filename)?;
    let dest_dir = models_root(&root).join(&category);
    fs::create_dir_all(&dest_dir).map_err(|e| e.to_string())?;
    let dest_path = dest_dir.join(&filename);
    let part_path = dest_dir.join(format!("{filename}.part"));
    if dest_path.exists() {
        let size = fs::metadata(&dest_path).ok().map(|m| m.len()).unwrap_or(0);
        let payload = json!({
            "filename": filename,
            "percentage": 100,
            "downloaded": size,
            "total": size,
            "status": "exists",
            "path": dest_path.to_string_lossy(),
            "category": category,
        });
        let _ = app.emit("download-progress", payload.clone());
        let _ = app.emit("download-complete", payload);
        return Ok(());
    }

    let mut headers = HeaderMap::new();
    let token = api_key
        .filter(|t| !t.is_empty())
        .or_else(|| std::env::var("HF_TOKEN").ok())
        .or_else(|| std::env::var("HUGGING_FACE_HUB_TOKEN").ok());
    if let Some(token) = token {
        if let Ok(val) = HeaderValue::from_str(&format!("Bearer {}", token)) {
            headers.insert(AUTHORIZATION, val);
        }
    }

    let client = reqwest::Client::builder()
        .default_headers(headers)
        .build()
        .map_err(|e| e.to_string())?;

    let response = client
        .get(&url)
        .send()
        .await
        .map_err(|e| format!("Request failed: {}", e))?;

    if !response.status().is_success() {
        return Err(format!(
            "Download failed with status: {}",
            response.status()
        ));
    }

    let total_size = response.content_length().unwrap_or(0);
    let _ = fs::remove_file(&part_path);
    let mut file = fs::File::create(&part_path).map_err(|e| e.to_string())?;
    let mut downloaded: u64 = 0;
    let mut stream = response.bytes_stream();
    let _ = app.emit(
        "download-progress",
        json!({
            "filename": filename,
            "percentage": 0,
            "downloaded": 0,
            "total": total_size,
            "status": "downloading",
            "category": category,
        }),
    );

    while let Some(chunk) = stream.next().await {
        let chunk = chunk.map_err(|e| e.to_string())?;
        file.write_all(&chunk).map_err(|e| e.to_string())?;
        downloaded += chunk.len() as u64;

        let percentage = if total_size > 0 {
            ((downloaded as f64 / total_size as f64) * 100.0) as u8
        } else {
            0
        };

        let _ = app.emit(
            "download-progress",
            json!({
                "filename": filename,
                "percentage": percentage,
                "downloaded": downloaded,
                "total": total_size,
                "status": "downloading",
                "category": category,
            }),
        );
    }
    file.flush().map_err(|e| e.to_string())?;
    drop(file);
    fs::rename(&part_path, &dest_path).map_err(|e| e.to_string())?;
    let complete = json!({
        "filename": filename,
        "percentage": 100,
        "downloaded": downloaded,
        "total": if total_size == 0 { downloaded } else { total_size },
        "status": "complete",
        "path": dest_path.to_string_lossy(),
        "category": category,
    });
    let _ = app.emit("download-progress", complete.clone());
    let _ = app.emit("download-complete", complete);
    let _ = app.emit("outputs-changed", json!({ "kind": "models" }));
    Ok(())
}

/// Pure, fast, side-effect-free status snapshot.
///
/// IMPORTANT: this command MUST NOT do file IO, parsing, or `app.emit`.
/// It runs on the Tauri main thread (sync `#[command]`) and is polled by the
/// frontend every 500 ms — any heavy work here freezes the OS message pump
/// and makes the window unresponsive (no DevTools, no input).
///
/// The background `spawn_worker_events_poller` thread (250 ms) is responsible
/// for draining `worker.events`, mutating shared state, and emitting events.
/// This command only reads that already-mutated state from mutexes.
#[tauri::command]
async fn get_engine_status(state: State<'_, Arc<AppState>>) -> Result<Value, String> {
    let root = agent_root();
    let events_path = worker_events_path(&root);

    let worker_alive = worker_child_alive(state.inner());
    let worker_registered = state.worker.lock().map(|g| g.is_some()).unwrap_or(false);
    let ready = state.worker_ready.lock().map(|g| *g).unwrap_or(false);

    let ui_ready = ready && worker_alive;

    let boot_message = if ui_ready {
        String::new()
    } else if !worker_alive && worker_registered {
        "GPU worker stopped — click Restart GPU engine".to_string()
    } else {
        state
            .last_boot_message
            .lock()
            .map(|m| m.clone())
            .unwrap_or_default()
    };
    let boot_phase = if ui_ready {
        "ready".to_string()
    } else {
        state
            .last_boot_phase
            .lock()
            .map(|p| p.clone())
            .unwrap_or_else(|_| "unknown".to_string())
    };
    let boot_elapsed_secs = state
        .worker_boot_started
        .lock()
        .ok()
        .and_then(|s| s.as_ref().map(|t| t.elapsed().as_secs()));
    let health = state
        .engine_health
        .lock()
        .map(|h| h.clone())
        .unwrap_or_else(|_| "unknown".to_string());
    let bridge_alive = state
        .sidecar
        .lock()
        .ok()
        .and_then(|g| g.as_ref().map(|s| s.alive()))
        .unwrap_or(false);
    let generation_running = state
        .generation
        .lock()
        .map(|g| g.is_some())
        .unwrap_or(false);
    let gpu_name = state.gpu_name.lock().ok().and_then(|g| g.clone());
    let vram_gb = state.vram_gb.lock().ok().and_then(|g| *g);
    let cuda_available = state.cuda_available.lock().ok().and_then(|g| *g);
    let mps_available = state.mps_available.lock().ok().and_then(|g| *g);
    Ok(json!({
        "ready": ui_ready,
        "events_ready": ready,
        "worker_running": worker_registered,
        "worker_alive": worker_alive,
        "health": health,
        "boot_phase": boot_phase,
        "boot_message": boot_message,
        "boot_elapsed_secs": boot_elapsed_secs,
        "bridge_alive": bridge_alive,
        "generation_running": generation_running,
        "gpu_name": gpu_name,
        "vram_gb": vram_gb,
        "cuda_available": cuda_available,
        "mps_available": mps_available,
        "bridge_health": serde_json::Value::Null,
        "worker_log": worker_log_path(&root).to_string_lossy(),
        "events_log": events_path.to_string_lossy(),
    }))
}

#[tauri::command]
fn read_worker_log() -> Result<Value, String> {
    let path = worker_log_path(&agent_root());
    Ok(json!({
        "path": path.to_string_lossy(),
        "tail": tail_file(&path, LOG_TAIL_CHARS),
    }))
}

#[tauri::command]
fn read_full_worker_log() -> Result<Value, String> {
    let path = worker_log_path(&agent_root());
    Ok(json!({
        "path": path.to_string_lossy(),
        "tail": tail_file(&path, LOG_FULL_CHARS),
    }))
}

#[tauri::command]
async fn restart_gpu_worker(
    app: AppHandle,
    state: State<'_, Arc<AppState>>,
) -> Result<Value, String> {
    let root = agent_root();
    if let Ok(mut n) = state.worker_auto_restarts.lock() {
        *n = 0;
    }
    set_engine_health(&app, state.inner(), "restarting");
    stop_gpu_worker(state.inner())?;
    let _ = app.emit("worker-status", json!({ "status": "booting" }));
    start_gpu_worker(app.clone(), &root, state.inner())?;
    wait_for_worker_ready(&app, state.inner()).await?;
    Ok(json!({ "ready": true }))
}

#[tauri::command]
async fn show_generation_notification(
    app: AppHandle,
    title: String,
    body: String,
) -> Result<(), String> {
    use tauri_plugin_notification::NotificationExt;
    app.notification()
        .builder()
        .title(title)
        .body(body)
        .show()
        .map_err(|e| e.to_string())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_notification::init())
        .manage(Arc::new(AppState {
            watcher: Mutex::new(None),
            preview_watcher: Mutex::new(None),
            generation: Arc::new(Mutex::new(None)),
            worker: Mutex::new(None),
            sidecar: Mutex::new(None),
            bridge_start: Mutex::new(()),
            worker_ready: Arc::new(Mutex::new(false)),
            worker_events_offset: Arc::new(Mutex::new(0)),
            last_boot_message: Arc::new(Mutex::new(String::from("Starting GPU engine…"))),
            last_boot_phase: Arc::new(Mutex::new(String::from("starting"))),
            worker_boot_started: Arc::new(Mutex::new(None)),
            engine_health: Arc::new(Mutex::new(String::from("booting"))),
            worker_auto_restarts: Arc::new(Mutex::new(0)),
            gpu_name: Arc::new(Mutex::new(None)),
            vram_gb: Arc::new(Mutex::new(None)),
            cuda_available: Arc::new(Mutex::new(None)),
            mps_available: Arc::new(Mutex::new(None)),
            last_generation_progress: Arc::new(Mutex::new(None)),
            desktop_vram_profile: Arc::new(Mutex::new(String::from("auto"))),
        }))
        .invoke_handler(tauri::generate_handler![
            get_paths,
            get_inventory,
            list_outputs,
            search_outputs,
            delete_output,
            delete_output_image,
            delete_session,
            reveal_path_in_explorer,
            dry_run,
            list_styles,
            get_ui_defaults,
            get_model_gallery,
            get_lora_gallery,
            refresh_model_library_cache,
            resolve_model_profile,
            check_model_dependencies,
            download_model_companions,
            bridge_invoke,
            write_temp_png,
            read_image_preview,
            pick_image_file,
            read_live_preview,
            invoke_generation,
            generation_status,
            read_job_log,
            cancel_generation,
            start_outputs_watch,
            window_drag,
            show_generation_notification,
            get_engine_status,
            get_generation_progress,
            read_worker_log,
            read_full_worker_log,
            restart_gpu_worker,
            download_model,
        ])
        .setup(|app| {
            let root = agent_root();
            let outputs = outputs_root(&root);
            let _ = fs::create_dir_all(outputs.join("dreamforge"));
            let _ = fs::create_dir_all(dreamforge_logs_dir(&root));
            let app_handle = app.handle().clone();
            let state: tauri::State<Arc<AppState>> = app.state();
            let state_arc = Arc::clone(state.inner());
            let boot_app = app.handle().clone();
            std::thread::spawn(move || {
                if let Err(err) = start_bridge_sidecar(&root, &state_arc) {
                    eprintln!("DreamForge bridge sidecar failed to start: {err}");
                }
                if let Err(err) = start_gpu_worker(boot_app.clone(), &root, &state_arc) {
                    let _ = boot_app.emit("worker-failed", json!({ "error": err, "log_tail": "" }));
                }
            });
            let mut guard = state.watcher.lock().expect("watcher lock");
            if guard.is_none() {
                if let Ok(mut watcher) = RecommendedWatcher::new(
                    move |res: notify::Result<notify::Event>| {
                        let Ok(event) = res else {
                            return;
                        };
                        // worker.events / worker.log churn during GPU boot — ignore.
                        if event.paths.iter().any(|p| {
                            let s = p.to_string_lossy();
                            s.contains("/logs/") || s.contains("\\logs\\")
                        }) {
                            return;
                        }
                        let _ = app_handle.emit("outputs-changed", json!({}));
                    },
                    Config::default().with_poll_interval(Duration::from_millis(3000)),
                ) {
                    if watcher.watch(&outputs, RecursiveMode::Recursive).is_ok() {
                        *guard = Some(watcher);
                    }
                }
            }
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app_handle, event| {
            if let RunEvent::Exit = event {
                if let Some(state) = app_handle.try_state::<Arc<AppState>>() {
                    shutdown_all_services(state.inner());
                }
            }
        });
}
