# M3 Reference Packs Checklist

Tracks **Reference Packs Before Full Identity Registry** from `DREAMFORGE_V2_IMPLEMENTATION_PLAN.md`.

## Done

| Item | Location |
| --- | --- |
| Local JSON store (`person`, `character`, `product`, `brand`, `style`) | `backend/dreamforge_reference_packs.py` |
| Bridge CRUD | `dreamforge_desktop_bridge.py` |
| Attach pack → reference images + plan metadata | `useDreamForge.ts`, dry-run |
| Inspector attach / create / delete | `InspectorPanel.tsx` |
| Plan panel shows attached pack | `WorkflowPlanPanel.tsx` |
| Tags + notes on pack create | `InspectorPanel.tsx` |
| Tests | `backend/tests/test_reference_packs.py` |

## Not in M3 (M4+)

- SQLite identity registry with embeddings
- Automatic face detection / FaceID pipeline
