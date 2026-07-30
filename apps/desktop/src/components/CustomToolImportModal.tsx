import { useState } from "react";
import { pickJsonFile } from "../lib/tauri-api";
import { importCustomToolWorkflow } from "../lib/studioBridge";
import {
  parseComfyWorkflowJson,
  detectPotentialBindings,
  type CustomTool,
  type CustomToolBinding,
} from "../lib/customTools";

export function CustomToolImportModal({
  onClose,
  onSave,
  existingTool,
}: {
  onClose: () => void;
  onSave: (tool: CustomTool) => void | Promise<void>;
  existingTool?: CustomTool | null;
}) {
  const [filePath, setFilePath] = useState("");
  const [potentials, setPotentials] = useState<Record<string, any>>({});
  const [name, setName] = useState(existingTool?.name ?? "");
  const [description, setDescription] = useState(existingTool?.description ?? "");
  const [error, setError] = useState<string | null>(null);
  const [warning, setWarning] = useState<string | null>(null);
  const [importable, setImportable] = useState<boolean | null>(null);
  const [uiFormat, setUiFormat] = useState<boolean>(false);

  const [selectedBindings, setSelectedBindings] = useState<Record<string, CustomToolBinding>>(
    existingTool?.bindings ?? {},
  );
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const handlePick = async () => {
    try {
      const path = await pickJsonFile();
      if (!path) return;
      setFilePath(path);
      setWarning(null);
      
      const {
        nodes,
        error,
        importable: canImport,
        uiFormat: isUi,
        warning: repairWarning,
      } = await parseComfyWorkflowJson(path);
      const detected = detectPotentialBindings(nodes);
      setPotentials(detected);
      setImportable(canImport);
      setUiFormat(Boolean(isUi));
      setWarning(repairWarning ?? null);
      setError(canImport ? null : error ?? "Invalid ComfyUI workflow format");
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleToggleBinding = (key: string, binding: CustomToolBinding) => {
    const next = { ...selectedBindings };
    if (next[key]) {
      delete next[key];
    } else {
      next[key] = binding;
    }
    setSelectedBindings(next);
  };

  const handleSave = async () => {
    if (!name || !filePath || importable !== true) return;
    setSaving(true);
    setSaveError(null);
    try {
      const id = existingTool?.id ?? "custom_" + Date.now().toString();
      const managed = await importCustomToolWorkflow(filePath, id);
      await onSave({
        id,
        name,
        description,
        workflow_path: managed.workflow_path,
        source_workflow_path: managed.source_workflow_path,
        workflow_sha256: managed.workflow_sha256,
        workflow_format: managed.workflow_format,
        managed_workflow_version: managed.managed_workflow_version,
        bindings: selectedBindings,
        model_overrides: existingTool?.model_overrides,
      });
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      setSaveError(message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div className="flex max-h-full w-full max-w-xl flex-col overflow-hidden rounded-md bg-[#252526] shadow-xl">
        <div className="flex items-center justify-between border-b border-[#3c3c3c] p-4">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-[#cccccc]">
            {existingTool ? "Relink Custom Tool" : "Import Custom Tool"}
          </h2>
          <button
            onClick={onClose}
            className="text-[#cccccc] hover:text-white"
          >
            &#x2715;
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {error && <div className="text-red-400 text-sm">{error}</div>}
          {saveError && <div className="text-red-400 text-sm">{saveError}</div>}
          {warning && (
            <div className="rounded border border-sky-700/60 bg-sky-950/40 p-2 text-[10px] text-sky-200">
              {warning}
            </div>
          )}
          {uiFormat && (
            <div className="rounded border border-sky-700/60 bg-sky-950/40 p-2 text-[10px] text-sky-200">
              UI workflow detected. DreamForge converts it automatically when you generate — no API export required.
            </div>
          )}
          
          <div className="space-y-2">
            <label className="text-xs font-semibold text-[#cccccc]">Workflow File</label>
            <p className="text-[10px] leading-snug text-[#aaaaaa]">
              Select your normal ComfyUI workflow save (.json). An API export in the same folder is optional.
            </p>
            <div className="flex gap-2">
              <input 
                type="text" 
                readOnly 
                value={filePath} 
                className="flex-1 rounded border border-[#3c3c3c] bg-[#1e1e1e] p-1.5 text-xs text-[#cccccc]"
                placeholder="Select a ComfyUI workflow JSON..."
              />
              <button 
                onClick={handlePick}
                className="rounded bg-[#3c3c3c] px-3 py-1.5 text-xs text-[#cccccc] hover:bg-[#4a4a4a]"
              >
                Browse
              </button>
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-xs font-semibold text-[#cccccc]">Tool Name</label>
            <input 
              type="text" 
              value={name}
              onChange={e => setName(e.target.value)}
              className="w-full rounded border border-[#3c3c3c] bg-[#1e1e1e] p-1.5 text-xs text-[#cccccc]"
              placeholder="e.g. Pixel Art Generator"
            />
          </div>

          <div className="space-y-2">
            <label className="text-xs font-semibold text-[#cccccc]">Description</label>
            <textarea 
              value={description}
              onChange={e => setDescription(e.target.value)}
              className="w-full rounded border border-[#3c3c3c] bg-[#1e1e1e] p-1.5 text-xs text-[#cccccc]"
              placeholder="What does this tool do?"
              rows={2}
            />
          </div>

          {Object.keys(potentials).length > 0 && (
            <div className="space-y-2 pt-2 border-t border-[#3c3c3c]">
              <label className="text-xs font-semibold text-[#cccccc]">Bind Inputs (Optional)</label>
              <p className="text-[10px] text-[#aaaaaa]">
                Select inputs to expose in the DreamForge UI.
              </p>
              <div className="space-y-1">
                {Object.entries(potentials).map(([key, binding]) => (
                  <label key={key} className="flex items-center gap-2 text-xs text-[#cccccc]">
                    <input 
                      type="checkbox"
                      checked={!!selectedBindings[key]}
                      onChange={() => handleToggleBinding(key, binding)}
                    />
                    <span>{binding.label} ({binding.type})</span>
                  </label>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="flex justify-end gap-2 border-t border-[#3c3c3c] p-4 bg-[#1e1e1e]">
          <button 
            onClick={onClose}
            className="rounded px-4 py-1.5 text-xs text-[#cccccc] hover:bg-[#3c3c3c]"
          >
            Cancel
          </button>
          <button 
            onClick={handleSave}
            disabled={!name || !filePath || importable !== true || saving}
            className="rounded bg-[#0e639c] px-4 py-1.5 text-xs text-white hover:bg-[#1177bb] disabled:opacity-50"
          >
            {saving ? "Saving…" : existingTool ? "Relink Tool" : "Import Tool"}
          </button>
        </div>
      </div>
    </div>
  );
}
