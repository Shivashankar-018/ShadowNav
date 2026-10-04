# ShadowNav

Hyper-local urban heat island prediction and cool-route navigation (final-year CSE project).

This repository is under step-by-step development. For the current API request
examples, validation rules, and errors, see [`docs/API.md`](docs/API.md). The
broader architecture and prototype limitations are in
[`docs/SYSTEM_DESIGN.md`](docs/SYSTEM_DESIGN.md). Local security settings and
their limits are summarized in [`docs/SECURITY.md`](docs/SECURITY.md).
Run the local automated checks with the instructions in [`docs/TESTING.md`](docs/TESTING.md).
Validation stages and the blank ground-truth data template are described in
[`docs/VALIDATION.md`](docs/VALIDATION.md).
The optional, not-yet-connected sensor extension is described in
[`docs/IOT_EXTENSION.md`](docs/IOT_EXTENSION.md).
The synthetic-only training and evaluation workflow is described in
[`docs/ML_PIPELINE.md`](docs/ML_PIPELINE.md). Its sample target is simulated
for teaching and must not be interpreted as measured street temperature.
For a public demo link, see [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md). Public
mode disables shared history to protect visitors' route locations.
