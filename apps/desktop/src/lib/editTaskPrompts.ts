import type { EditTask } from "./inpaintIntent";
import type { GenerationSettings } from "./tauri-api";

export const PHOTO_RESTORE_DEFAULT_PROMPT =
  "restore this old photo, high quality, detailed, photorealistic, sharp focus";

export const OUTFIT_TRANSFER_DEFAULT_PROMPT =
  "transfer the outfit from image 2 onto the person in image 1, preserve the face, pose, body shape, background, and lighting";

export const CUTOUT_COMPOSE_DEFAULT_PROMPT =
  "remove the background from the subject in image 1 and place them naturally into the scene in image 2, matching lighting, shadows, perspective, and color grading";

export const EDIT_TASK_DEFAULT_PROMPTS: Partial<Record<EditTask, string>> = {
  photo_restore: PHOTO_RESTORE_DEFAULT_PROMPT,
  outfit_transfer: OUTFIT_TRANSFER_DEFAULT_PROMPT,
  cutout_compose: CUTOUT_COMPOSE_DEFAULT_PROMPT,
};

/** Fill the prompt bar when the user picks a guided edit task and left it empty. */
export function defaultPromptPatchForEditTask(
  task: EditTask,
  settings: GenerationSettings,
): Partial<GenerationSettings> | null {
  if ((settings.prompt ?? "").trim()) return null;
  const prompt = EDIT_TASK_DEFAULT_PROMPTS[task];
  return prompt ? { prompt } : null;
}
