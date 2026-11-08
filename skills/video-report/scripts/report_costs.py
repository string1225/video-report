"""Report measurable pipeline work without inventing unavailable model bills."""
from __future__ import annotations


def summarize_run_costs(audio_manifest: dict, elapsed_seconds: float,
                        stage_seconds: dict, video_bytes: int) -> dict:
    units = [unit for scene in audio_manifest.get('scenes', []) for unit in scene.get('cache', [])]
    new = [unit for unit in units if unit.get('hit') is False]
    providers = sorted({scene.get('provider', 'unknown') for scene in audio_manifest.get('scenes', [])})
    known_unbilled = all(provider in ('edge-tts', 'external') for provider in providers)
    return {
        'scope': 'This pipeline build only; excludes agent research, software development and initial setup.',
        'build_elapsed_seconds': round(elapsed_seconds, 2),
        'stage_elapsed_seconds': {key: round(value, 2) for key, value in stage_seconds.items()},
        'audio': {'units': len(units), 'cache_hits': sum(unit.get('hit') is True for unit in units),
                  'new_synthesis_units': len(new),
                  'new_synthesis_characters': sum(len(unit.get('spoken', unit.get('text', ''))) for unit in new),
                  'providers': providers,
                  'note': 'Units describe completed synthesis jobs, not HTTP requests or failed retries.'},
        'direct_external_service_cost_cny': 0 if known_unbilled else None,
        'direct_service_basis': 'No paid API credentials or billable service configured in the implemented edge-tts/external-audio pipeline.',
        'model_cost_cny': None,
        'model_usage': 'Not exposed to this script; use the actual Codex/API usage or subscription bill.',
        'local_electricity_and_hardware_cost_cny': None,
        'total_cost_cny': None,
        'total_cost_note': 'Unknown model billing, local power and equipment cost are not treated as zero.',
        'output_video_bytes': video_bytes,
    }
