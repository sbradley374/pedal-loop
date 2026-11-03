# Historical material

These files are preserved for reference, not used to run the app. Current functionality and setup are documented in the [project README](../README.md) and [startup guide](../docs/STARTUP.md). Historical performance numbers are tied to their dataset, code revision and machine; they are not current capacity guarantees.

- [Research notes](RESEARCH-2026-10-20.md): early implementation choices and superseded milestone plans.
- [Browser QA](reports/QA-2026-10-20.md): October 20 desktop/responsive checks, before native navigation.
- Reports: [regional benchmark](reports/benchmark-2026-10-20.json), [Boulder benchmark](reports/benchmark-boulder-2026-10-20.json), [concurrency test](reports/load-test-2026-10-20.json). Boulder data is not bundled. The regional matrix includes legitimate no-match cases.
- [GPX examples](examples/README.md): older search/elevation outputs, not audited cycling recommendations or current golden test fixtures.
- Screenshots: [initial planner](screenshots/preview.png), [terrain planner](screenshots/preview-elevation.png). These do not represent the current iPhone UI.
- [Render proposal](deployment/render.yaml.example): unused paid-hosting configuration, renamed so it is not an active root Blueprint. It was never provisioned. To revisit it, copy it to the repository root as `render.yaml`, review current platform settings and cost, and validate it before deployment. Its Docker build assumes the repository root, not this archive directory.

Runtime code, data import tools and regression fixtures remain in their active directories. Old tunnel URLs and transient process IDs were removed from the current handoff; they are not reusable configuration.
