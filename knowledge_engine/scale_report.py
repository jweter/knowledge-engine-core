from knowledge_engine.scale_readiness import MeasurementSource


def format_measurement(label: str, value: str, source: MeasurementSource) -> str:
    return f"- {label}: `{value}` _(source: {source.value})_"
