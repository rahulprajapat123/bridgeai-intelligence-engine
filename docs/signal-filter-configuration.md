# Signal Filter configuration

`SignalFilterConfig` contains all thresholds and caps. Defaults preserve the requested 0.82 lexical threshold, 0.60 uniqueness threshold, individual score minimums, total minimum of 15, category caps, total cap of 20, 60 PDF pages, and 40 candidates.

Configuration may be loaded from JSON, optional YAML (when PyYAML is installed), or environment variables prefixed with `SIGNAL_FILTER_`. Complex environment values use JSON, for example:

```powershell
$env:SIGNAL_FILTER_MIN_TOTAL_SCORE = '16'
$env:SIGNAL_FILTER_CATEGORY_CAPS = '{"news":6,"blog":4,"repo":4,"other":4}'
```

Precedence is base configuration, source-type override, domain override, then brief override. Each audit decision records `config_version`; provider decisions also record the provider model version.
