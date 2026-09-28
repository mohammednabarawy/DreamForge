import { expect, it } from "vitest";
import { mergeSessionList, outputPathForSession } from "./sessions";

it("saves every image operation in the selected project without allowing path traversal", () => {
  for (const kind of ["gen", "edit", "inpaint", "upscale"] as const) {
    expect(outputPathForSession("verification", kind)).toMatch(new RegExp(`^outputs/verification/${kind}_.*\\.png$`));
    expect(outputPathForSession("root", kind)).toMatch(new RegExp(`^outputs/${kind}_.*\\.png$`));
    expect(outputPathForSession("../../other", kind)).toMatch(/^outputs\/dreamforge\//);
  }
  expect(mergeSessionList([], [{ id: "verification", label: "Verification" }], "verification")
    .map(project => project.id)).toEqual(["verification", "dreamforge"]);
});
