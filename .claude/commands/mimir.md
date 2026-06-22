# Mimir Project Rules

## Plugin version sync

Whenever any change is made to a source plugin (bug fix, new feature, new field, template change, UI change) that would affect the plugin's behavior or output, two files **must** be updated together:

1. **`mimir-plugin-registry/registry.json`** — update the plugin's `version` field and `changelog` string.
2. **The plugin's own `plugin.json`** — update its `version` field to match.

Both files must always agree on the version number. Never update one without the other.

### Version bump guidelines
- Patch bump (e.g. `1.0.1` → `1.0.2`): bug fixes, copy changes, CSS tweaks, minor template adjustments.
- Minor bump (e.g. `1.0.x` → `1.1.0`): new user-visible fields, new themes, new layout options, new API endpoints.
- Major bump (e.g. `1.x.x` → `2.0.0`): breaking changes to the feed/config schema, removal of fields.

### Changelog format
Keep the `changelog` field in `registry.json` brief — one short sentence describing what changed in this version. Examples:
- `"add high-contrast e-ink themes"`
- `"fix landscape image layout and add font size option"`
- `"add body_size field and responsive template rewrite"`

## Plugin registry location
`mimir-plugin-registry/registry.json` — one entry per plugin, keyed by `id`. The `updated` field at the top of the file should also be bumped to today's date whenever any plugin entry changes.
