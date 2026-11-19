# Developer documentation

| Document | Contents |
|---|---|
| [architecture.md](architecture.md) | Components, source tree, *Generate* sequence, jobset structure, dialog states |
| [pipelines.md](pipelines.md) | Per-layer export, PDF inversion, Gerber extensions, other script jobs, BOM fields discovery |
| [kicad-integration.md](kicad-integration.md) | KiCad behaviours the design relies on (`special_execute`, work dir, plot placement, API quirks), interpreter discovery, data file formats |
| [release.md](release.md) | Packaging, GitHub release workflow and submission to the KiCad Plugin and Content Manager |

## Diagrams

Diagrams are [PlantUML](https://plantuml.com/) sources in [diagrams/](diagrams/), one
`.puml` file per diagram. The Markdown files show them as images rendered on the fly by
the public PlantUML server, from the raw file on the `main` branch:

```
![name](https://www.plantuml.com/plantuml/proxy?cache=no&fmt=svg&src=https://raw.githubusercontent.com/kevinwysocki/kicad_release_wizard/main/doc/diagrams/<name>.puml)
```

- Nothing is generated or committed: edit the `.puml`, push, and the image follows.
- Images always show the `main` version of a diagram, and only once it is pushed.
- To preview locally, open the `.puml` files with a PlantUML extension (VS Code) or
  render them with `java -jar plantuml.jar -tsvg doc/diagrams/*.puml`.
- To add a diagram: create `diagrams/<name>.puml` starting with `@startuml <name>`, and
  embed it with the URL above.
